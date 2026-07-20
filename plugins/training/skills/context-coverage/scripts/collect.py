#!/usr/bin/env python3
"""
context-coverage collector
===========================
Scans a set of repositories and measures how well each is covered by
agent context (CLAUDE.md / AGENTS.md), skills, and commands -- cross-
referenced against how *real*, *big*, *active*, and *fresh* each repo is.

Two modes:
  --dir  <folder>   Scan every git repo that is an immediate subdirectory
                    (full fidelity: real LOC, commit history, nested context).
  --org  <name>     Use the `gh` CLI to enumerate an org's repos and inspect
                    each via the GitHub trees/commits API without cloning
                    (lighter fidelity: byte-based size estimate).

Output: a single JSON document on stdout (or --out FILE) that render.py turns
into a self-contained HTML report.

Pure standard library -- runs on any Python 3.8+. Requires `git` on PATH for
--dir mode and `gh` (authenticated) for --org mode.
"""
import argparse
import concurrent.futures as cf
import fnmatch
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

NOW = time.time()
DAY = 86400.0

# ---------------------------------------------------------------------------
# Tunable classification model (surfaced in the report so it's not a black box)
# ---------------------------------------------------------------------------
MODEL = {
    # A repo is dropped from scope ("throwaway") if its name contains one of
    # these markers (scratch/demo/test/legacy/etc.). Override with --include.
    "throwaway": {
        "name_markers": ["test", "demo", "scratch", "tmp", "temp", "sandbox",
                          "example", "sample", "poc", "hello", "playground",
                          "xrepo", "starter", "boilerplate", "wip", "draft",
                          "spike", "prototype", "experiment", "dummy", "foo"],
        "stale_markers": ["legacy", "deprecated", "archive", "archived", "old",
                          "backup", "bak", "retired", "sunset"],
    },
    # Context is "stale" if this many code commits landed since the newest
    # context file was last touched, OR context age exceeds max_age_days while
    # the repo is still active.
    "stale_commits_since": 25,
    "stale_max_age_days": 240,
    "active_window_days": 90,
    # In-scope cutoff: a repo must have a commit within this many days to be
    # analyzed at all (matches the AI-SDLC maturity model's "active repos").
    "active_days": 90,
    # Problem-area detection (folder-level, computed in the renderer).
    "problem": {
        "dense_loc": 3000,             # a folder this big deserves its own context
        "loc_per_ctxline_warn": 180,   # LOC governed per line of context — amber
        "loc_per_ctxline_bad": 450,    # ... red
        "oversized_claude_lines": 300, # a single CLAUDE.md longer than this = bloated
    },
}

# Context files that live at a fixed path (beyond CLAUDE.md / AGENTS.md).
EXTRA_CONTEXT_FILES = {
    ".cursorrules": "cursorrules",
    ".github/copilot-instructions.md": "copilot",
    ".windsurfrules": "windsurfrules",
}
# Directories that hold rule files (Cursor/Cline/etc. "rules").
RULES_DIR_NAMES = {"rules"}
RULE_EXTS = {".md", ".mdc"}

# Org mode has no line counts (no clone), only blob byte sizes; estimate LOC at
# this many bytes/line (whole-corpus average). Flagged with * in the report.
BYTES_PER_LINE = 38

# Directories that are never "the repo's own" content -- vendored deps, build
# output, caches. Pruned everywhere so we never count a skill/CLAUDE.md that
# ships inside a dependency.
PRUNE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "env", "site-packages",
    "vendor", "dist", "build", "out", ".next", ".nuxt", "target",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".gradle", ".idea",
    ".tox", "bower_components", "Pods", ".terraform", "coverage",
    ".cache", "bin", "obj", ".svelte-kit", "_build", "deps",
}

# Agent-context "surfaces": tool-specific config roots. Presence of several
# signals a deliberately context-rich repo.
SURFACE_DIRS = [".claude", ".cursor", ".gemini", ".github", ".windsurf",
                ".codeium", ".aider", ".continue"]

CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".rb", ".go", ".rs", ".java",
    ".kt", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php", ".swift",
    ".scala", ".sh", ".bash", ".ps1", ".sql", ".vue", ".svelte", ".r",
    ".jl", ".ex", ".exs", ".erl", ".clj", ".lua", ".dart", ".m", ".mm",
    ".pl", ".groovy", ".gradle", ".tf", ".css", ".scss", ".sass", ".less",
    ".html", ".htm", ".astro", ".elm", ".hs", ".ml", ".fs", ".vb",
}


_GH_FAILURES = {"rate_limit": 0, "other": 0}


def sh(args, cwd=None, timeout=60):
    """Run a command, return (rc, stdout, stderr) as text. Never raises.
    Tracks gh API failures so the run can warn instead of silently zeroing."""
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        rc, out, err = p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        rc, out, err = 1, "", str(e)
    if rc != 0 and args and args[0] == "gh":
        low = (err or "").lower()
        key = "rate_limit" if ("rate limit" in low or "403" in low) else "other"
        _GH_FAILURES[key] += 1
    return rc, out, err


def walk_pruned(root):
    """os.walk that prunes vendored/build dirs in-place."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        yield dirpath, dirnames, filenames


def count_lines(path, cap_bytes=2_000_000):
    """Fast newline count; skips huge/binary-ish files."""
    try:
        if os.path.getsize(path) > cap_bytes:
            return 0
        with open(path, "rb") as f:
            data = f.read()
        if b"\x00" in data[:4096]:
            return 0  # binary
        return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    except OSError:
        return 0


def build_dir_tree(file_locs, max_depth=3, min_loc=80, max_children=14):
    """Aggregate (relpath, loc) pairs into a pruned directory tree for the
    per-repo drill-down: {name, loc, children:[...]}. Deep paths fold into
    their depth-`max_depth` ancestor; tiny/overflow dirs are dropped so the
    JSON stays small even for a 10k-file monorepo."""
    root = {"name": "", "loc": 0, "children": {}}
    for path, loc in file_locs:
        if not loc:
            continue
        parts = path.split("/")[:-1]           # directory components only
        node = root
        node["loc"] += loc
        for i, part in enumerate(parts):
            if i >= max_depth:
                break
            node = node["children"].setdefault(part, {"name": part, "loc": 0, "children": {}})
            node["loc"] += loc

    def finalize(node, depth=0):
        kids = sorted(node["children"].values(), key=lambda c: -c["loc"])
        kids = [k for k in kids if k["loc"] >= min_loc][:max_children]
        node["children"] = [finalize(k, depth + 1) for k in kids]
        return node
    return finalize(root)


# ---------------------------------------------------------------------------
# Context inventory -- shared by local and org mode so the two never drift.
# One classifier over repo-relative paths, one assembler; only how line counts
# get resolved differs (local reads files, org fetches via the API).
# ---------------------------------------------------------------------------
def _dir_of(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def classify_context_paths(paths):
    """Sort repo-relative POSIX paths into context artifacts (CLAUDE.md /
    AGENTS.md / rules / skills / commands / surfaces / other-tool files)."""
    claude, agents, rules, skills, commands = [], [], [], [], []
    surfaces, extra = set(), set()
    for p in paths:
        low = p.lower()
        segs = low.split("/")
        base = segs[-1]
        if segs[0] in SURFACE_DIRS:
            surfaces.add(segs[0])
        if low in EXTRA_CONTEXT_FILES:
            extra.add(EXTRA_CONTEXT_FILES[low])
        if base == "claude.md":
            claude.append(p)
        elif base == "agents.md":
            agents.append(p)
        elif base == "skill.md":
            skills.append(p)
        elif base.endswith(".md") and "/commands/" in "/" + low and ".claude" in low:
            commands.append(p)
        elif os.path.splitext(base)[1] in RULE_EXTS and any(s in RULES_DIR_NAMES for s in segs[:-1]):
            rules.append(p)
    return {"claude": claude, "agents": agents, "rules": rules,
            "skills": skills, "surfaces": surfaces, "extra": sorted(extra)}


def finish_context(r, c, lines):
    """Assemble the context fields from a classification `c` and a resolved
    {context_path: line_count} map. Rules files are first-class context: their
    lines count toward total_context_lines and their /rules/ dir (which governs
    the repo root) becomes an anchor."""
    claude = sorted(c["claude"], key=lambda x: (x.count("/"), x))
    agents = sorted(c["agents"], key=lambda x: (x.count("/"), x))
    root_claude = next((p for p in claude if p.lower() == "claude.md"), None)
    root_agents = next((p for p in agents if p.lower() == "agents.md"), None)
    anchors = []
    for p in claude:
        anchors.append({"dir": _dir_of(p), "lines": lines.get(p, 0), "kind": "claude", "path": p})
    for p in agents:
        anchors.append({"dir": _dir_of(p), "lines": lines.get(p, 0), "kind": "agents", "path": p})
    rules_by_dir = {}
    for p in c["rules"]:
        d = _dir_of(p)
        rules_by_dir[d] = rules_by_dir.get(d, 0) + lines.get(p, 0)
    for rd, ln in sorted(rules_by_dir.items()):
        anchors.append({"dir": "", "lines": ln, "kind": "rules", "path": rd})
    r["has_claude_md"] = root_claude is not None
    r["claude_md_lines"] = lines.get(root_claude, 0) if root_claude else 0
    r["nested_claude_count"] = max(0, len(claude) - (1 if root_claude else 0))
    r["has_agents_md"] = root_agents is not None
    r["total_context_lines"] = sum(lines.values())
    r["skills_count"] = len(c["skills"])
    r["has_rules"] = bool(rules_by_dir)
    r["context_anchors"] = anchors
    r["extra_context"] = c["extra"]


def context_files(c):
    """The context files whose line counts we need, root-first."""
    return (sorted(c["claude"], key=lambda x: (x.count("/"), x))
            + sorted(c["agents"], key=lambda x: (x.count("/"), x))
            + c["rules"])


# ---------------------------------------------------------------------------
# Local directory mode
# ---------------------------------------------------------------------------
def scan_local_repo(path, name):
    r = {"name": name, "mode": "local", "errors": []}
    is_git = os.path.isdir(os.path.join(path, ".git"))
    r["is_git"] = is_git

    # --- size: LOC + file/content signals, respecting .gitignore when possible
    loc = 0
    file_count = 0
    code_files = 0
    has_readme = False
    file_locs = []                    # (relpath, loc) for the dir tree
    extra_ctx = set()
    tracked = None
    if is_git:
        rc, out, _ = sh(["git", "ls-files", "-z"], cwd=path)
        if rc == 0:
            tracked = [f for f in out.split("\0") if f]
    if tracked is not None:
        for rel in tracked:
            file_count += 1
            low = rel.lower()
            if "/" not in low and low.startswith("readme"):
                has_readme = True
            if low in EXTRA_CONTEXT_FILES:
                extra_ctx.add(EXTRA_CONTEXT_FILES[low])
            ext = os.path.splitext(rel)[1].lower()
            if ext in CODE_EXTS:
                code_files += 1
                nl = count_lines(os.path.join(path, rel))
                loc += nl
                file_locs.append((rel, nl))
    else:
        for dp, _, fns in walk_pruned(path):
            for fn in fns:
                file_count += 1
                rel = os.path.relpath(os.path.join(dp, fn), path).replace("\\", "/")
                low = rel.lower()
                if dp == path and fn.lower().startswith("readme"):
                    has_readme = True
                if low in EXTRA_CONTEXT_FILES:
                    extra_ctx.add(EXTRA_CONTEXT_FILES[low])
                if os.path.splitext(fn)[1].lower() in CODE_EXTS:
                    code_files += 1
                    nl = count_lines(os.path.join(dp, fn))
                    loc += nl
                    file_locs.append((rel, nl))
    r["loc"] = loc
    r["file_count"] = file_count
    r["code_file_count"] = code_files
    r["has_readme"] = has_readme
    r["is_fork"] = None  # not cheaply knowable for a local clone
    r["extra_context"] = sorted(extra_ctx)
    r["dir_tree"] = build_dir_tree(file_locs)

    # --- git activity -------------------------------------------------------
    if is_git:
        rc, out, _ = sh(["git", "rev-list", "--count", "HEAD"], cwd=path)
        r["commits_total"] = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
        since = datetime.fromtimestamp(NOW - MODEL["active_window_days"] * DAY,
                                       tz=timezone.utc).strftime("%Y-%m-%d")
        rc, out, _ = sh(["git", "rev-list", "--count", "--since", since, "HEAD"], cwd=path)
        r["commits_recent"] = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
        rc, out, _ = sh(["git", "log", "-1", "--format=%ct"], cwd=path)
        r["last_commit_days"] = round((NOW - int(out.strip())) / DAY, 1) if rc == 0 and out.strip().isdigit() else None
        # first commit (age)
        rc2, out2, _ = sh(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=path)
        first = None
        if rc2 == 0 and out2.strip():
            fsha = out2.strip().splitlines()[-1]
            rc3, o3, _ = sh(["git", "log", "-1", "--format=%ct", fsha], cwd=path)
            if rc3 == 0 and o3.strip().isdigit():
                first = round((NOW - int(o3.strip())) / DAY, 1)
        r["age_days"] = first
        rc, out, _ = sh(["git", "shortlog", "-sne", "HEAD"], cwd=path)
        r["contributors"] = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else 0
    else:
        r.update(commits_total=0, commits_recent=0, last_commit_days=None,
                 age_days=None, contributors=0)

    # --- context inventory --------------------------------------------------
    inventory_context(path, r, tracked)
    return r


def inventory_context(path, r, tracked):
    """Local context inventory: classify paths, read real line counts, assemble,
    then measure freshness from git."""
    if tracked is not None:
        paths = [p for p in tracked if not any(s in PRUNE_DIRS for s in p.split("/"))]
    else:
        paths = []
        base = os.path.abspath(path)
        for dp, _, fns in walk_pruned(path):
            for fn in fns:
                ap = os.path.abspath(os.path.join(dp, fn))
                paths.append(ap[len(base):].lstrip("/\\").replace("\\", "/") if ap.startswith(base) else fn)
    c = classify_context_paths(paths)
    ctx = context_files(c)
    lines = {p: count_lines(os.path.join(path, p)) for p in ctx}
    finish_context(r, c, lines)

    # --- context freshness (git) -------------------------------------------
    r["context_last_updated_days"] = None
    r["commits_since_context"] = None
    if r.get("is_git") and ctx:
        rc, out, _ = sh(["git", "log", "-1", "--format=%ct", "--"] + ctx, cwd=path)
        if rc == 0 and out.strip().isdigit():
            ts = int(out.strip())
            r["context_last_updated_days"] = round((NOW - ts) / DAY, 1)
            since = datetime.fromtimestamp(ts + 1, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            rc2, out2, _ = sh(["git", "rev-list", "--count", "--since", since, "HEAD"], cwd=path)
            if rc2 == 0 and out2.strip().isdigit():
                r["commits_since_context"] = int(out2.strip())


# ---------------------------------------------------------------------------
# Org mode (gh API, no clone)
# ---------------------------------------------------------------------------
def gh_json(endpoint):
    rc, out, err = sh(["gh", "api", "--paginate", endpoint], timeout=90)
    if rc != 0:
        return None, err
    try:
        # --paginate concatenates JSON arrays with no separator sometimes; the
        # simple case (single object/array) parses directly.
        return json.loads(out), None
    except json.JSONDecodeError:
        # fall back: wrap concatenated arrays
        try:
            fixed = "[" + out.replace("][", "],[") + "]"
            merged = []
            for chunk in json.loads(fixed):
                merged.extend(chunk)
            return merged, None
        except Exception as e:
            return None, str(e)


def scan_org_repo(owner, meta):
    name = meta["name"]
    r = {"name": name, "mode": "org", "errors": [], "is_git": True,
         "default_branch": meta.get("defaultBranchRef", {}).get("name") if isinstance(meta.get("defaultBranchRef"), dict) else meta.get("default_branch")}
    branch = r["default_branch"] or "main"
    r["is_archived"] = meta.get("isArchived", meta.get("archived", False))
    r["is_fork"] = meta.get("isFork", meta.get("fork", False))
    r["primary_language"] = (meta.get("primaryLanguage") or {}).get("name") if isinstance(meta.get("primaryLanguage"), dict) else meta.get("language")

    pushed = meta.get("pushedAt") or meta.get("pushed_at")
    r["last_commit_days"] = _iso_days(pushed)
    created = meta.get("createdAt") or meta.get("created_at")
    r["age_days"] = _iso_days(created)

    # tree (one recursive call gives the whole file list + blob sizes)
    tree, err = gh_json(f"repos/{owner}/{name}/git/trees/{branch}?recursive=1")
    code_bytes = 0
    file_count = 0
    code_files = 0
    has_readme = False
    tracked = []
    extra_ctx = set()
    file_locs = []                    # (path, loc estimate) for the dir tree
    if isinstance(tree, dict) and tree.get("tree"):
        if tree.get("truncated"):
            r["errors"].append("tree truncated by GitHub API (very large repo) — counts are partial")
        for node in tree["tree"]:
            if node.get("type") != "blob":
                continue
            p = node.get("path", "")
            if any(seg in PRUNE_DIRS for seg in p.split("/")):
                continue
            tracked.append(p)
            file_count += 1
            low = p.lower()
            if "/" not in low and low.startswith("readme"):
                has_readme = True
            if low in EXTRA_CONTEXT_FILES:
                extra_ctx.add(EXTRA_CONTEXT_FILES[low])
            if os.path.splitext(p)[1].lower() in CODE_EXTS:
                code_files += 1
                b = node.get("size", 0) or 0
                code_bytes += b
                file_locs.append((p, int(b / BYTES_PER_LINE)))
    else:
        r["errors"].append("tree unavailable: " + (err or "empty"))
    r["file_count"] = file_count
    r["code_file_count"] = code_files
    r["has_readme"] = has_readme
    r["extra_context"] = sorted(extra_ctx)
    # LOC estimate from code bytes (~38 bytes/line average across languages)
    r["loc"] = int(code_bytes / BYTES_PER_LINE) if code_bytes else 0
    r["loc_is_estimate"] = True
    r["dir_tree"] = build_dir_tree(file_locs)

    # commit activity (last 90d, capped)
    since = datetime.fromtimestamp(NOW - MODEL["active_window_days"] * DAY,
                                   tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits, _ = gh_json(f"repos/{owner}/{name}/commits?since={since}&per_page=100")
    r["commits_recent"] = len(commits) if isinstance(commits, list) else 0

    _inventory_from_paths(r, tracked, owner, name, branch)
    return r


# Safety cap on context files fetched per repo (line count + last-commit date).
# High enough that deeply-nested CLAUDE.md/rules are still measured exactly;
# it only guards against a pathological repo with hundreds of rule files.
CTX_FETCH_CAP = 60
CTX_FETCH_WORKERS = 4     # per-repo fetch concurrency (nested under --jobs)


def _fetch_ctx_meta(owner, name, branch, files):
    """For each context file, fetch (line_count, last_commit_date) -- in
    parallel, falling back to sequential if the thread pool errors."""
    def one(p):
        return p, _gh_file_lines(owner, name, branch, p), _gh_file_last_commit(owner, name, branch, p)
    out = {}
    if not files:
        return out
    try:
        with cf.ThreadPoolExecutor(max_workers=min(CTX_FETCH_WORKERS, len(files))) as ex:
            for p, ln, d in ex.map(one, files):
                out[p] = (ln, d)
    except Exception:
        for p in files:
            _, ln, d = one(p)
            out[p] = (ln, d)
    return out


def _inventory_from_paths(r, tracked, owner=None, name=None, branch=None):
    """Org context inventory: same classifier/assembler as local, but line
    counts + edit dates come from the contents/commits API (fetched in parallel;
    files past the cap estimated at the mean)."""
    c = classify_context_paths(tracked)
    ctx_files = context_files(c)
    r["context_last_updated_days"] = None
    r["commits_since_context"] = None

    head = ctx_files[:CTX_FETCH_CAP]
    meta = _fetch_ctx_meta(owner, name, branch, head)
    lines = {p: meta[p][0] for p in head}
    measured = [v for v in lines.values() if v] or [40]
    mean_ln = round(sum(measured) / len(measured))
    for p in ctx_files[CTX_FETCH_CAP:]:
        lines[p] = mean_ln
    finish_context(r, c, lines)

    # --- freshness: newest context-file edit date, then commits since --------
    dates = [meta[p][1] for p in head if meta[p][1]]
    newest = max(dates) if dates else None
    if newest:
        r["context_last_updated_days"] = _iso_days(newest)
        # count commits strictly AFTER the context commit (matches local mode,
        # which uses since=ts+1 -- avoids off-by-one from same-second commits)
        try:
            since = (datetime.fromisoformat(newest.replace("Z", "+00:00"))
                     + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            since = newest
        commits, _ = gh_json(f"repos/{owner}/{name}/commits?sha={quote(branch, safe='')}&since={since}&per_page=100")
        r["commits_since_context"] = len(commits) if isinstance(commits, list) else 0


def _gh_file_last_commit(owner, name, branch, path):
    """ISO date of the most recent commit touching `path` on the branch."""
    if not path:
        return None
    rc, out, _ = sh(["gh", "api",
                     f"repos/{owner}/{name}/commits?sha={quote(branch, safe='')}&path={quote(path, safe='/')}&per_page=1",
                     "--jq", ".[0].commit.committer.date"], timeout=30)
    return out.strip() if rc == 0 and out.strip() and out.strip() != "null" else None


def _gh_file_lines(owner, name, branch, path):
    if not path:
        return 0
    rc, out, _ = sh(["gh", "api", f"repos/{owner}/{name}/contents/{quote(path, safe='/')}?ref={quote(branch, safe='')}",
                     "--jq", ".content"], timeout=30)
    if rc != 0 or not out.strip():
        return 0
    import base64
    try:
        raw = base64.b64decode(out.strip())
        return raw.count(b"\n") + 1
    except Exception:
        return 0


def _iso_days(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return round((NOW - dt.timestamp()) / DAY, 1)
    except Exception:
        return None


def _org_stub(meta, err):
    """Minimal, render-safe repo record for a repo whose scan raised. Keeps the
    whole run alive; the error is surfaced in the JSON and the table."""
    return {
        "name": meta.get("name", "?"), "mode": "org",
        "errors": [f"scan failed: {err}"],
        "loc": 0, "loc_is_estimate": True, "code_file_count": 0,
        "commits_recent": 0, "last_commit_days": _iso_days(meta.get("pushedAt")),
        "is_archived": meta.get("isArchived", False), "is_fork": meta.get("isFork", False),
        "extra_context": [], "dir_tree": {"name": "", "loc": 0, "children": []},
        "context_anchors": [], "has_claude_md": False, "has_agents_md": False,
        "claude_md_lines": 0, "total_context_lines": 0, "nested_claude_count": 0,
        "has_rules": False, "skills_count": 0,
        "context_last_updated_days": None, "commits_since_context": None,
    }


# ---------------------------------------------------------------------------
# Scoring / classification -- applied uniformly to both modes
# ---------------------------------------------------------------------------
def classify(r):
    """Derive only directly-measured metrics and simple, transparent flags --
    no invented 0-100 composite scores. Everything here is either a raw count,
    a real ratio, or a single-rule boolean."""
    loc = r.get("loc") or 0
    commits_recent = r.get("commits_recent") or 0
    name = r["name"].lower()
    tw = MODEL["throwaway"]

    # --- scope: two plain rules, not a blended score ------------------------
    last = r.get("last_commit_days")
    ad = MODEL["active_days"]
    r["is_active"] = (ad <= 0) or (last is not None and last <= ad)
    marker = next((m for m in tw["name_markers"] + tw["stale_markers"] if m in name), None)
    r["throwaway_reason"] = ("archived" if r.get("is_archived") else
                             "fork" if r.get("is_fork") else
                             f"name marker '{marker}'" if marker else
                             f"only {loc} LOC" if loc < 50 else "")
    r["looks_throwaway"] = bool(r["throwaway_reason"])
    r["in_scope"] = r["is_active"] and not r["looks_throwaway"]

    # --- context presence (CLAUDE.md / AGENTS.md / cursor / copilot / rules) -
    extra = r.get("extra_context") or []
    r["has_rules"] = bool(r.get("has_rules"))
    ctx_lines = r.get("total_context_lines") or 0
    r["has_context"] = bool(r.get("has_claude_md") or r.get("has_agents_md")
                            or ctx_lines or extra or r["has_rules"])
    r["has_nested_or_rules"] = bool(r.get("nested_claude_count") or r["has_rules"])

    # --- density: LOC per line of context (a real ratio, repo-wide) ---------
    r["loc_per_context_line"] = round(loc / ctx_lines) if ctx_lines else None

    # --- freshness: measured directly from git history in BOTH modes --------
    csc = r.get("commits_since_context")
    cage = r.get("context_last_updated_days")
    if not r["has_context"]:
        r["freshness"] = "none"
    elif csc is None and cage is None:
        r["freshness"] = "unknown"
    else:
        why = []
        if csc is not None and csc >= MODEL["stale_commits_since"]:
            why.append(f"{csc} commits to code since context last edited")
        if cage is not None and cage > MODEL["stale_max_age_days"] and commits_recent:
            why.append(f"context {int(cage)}d old while repo is active")
        r["freshness"] = "stale" if why else "fresh"
    return r


def apply_overrides(r, include, exclude, opt_in_only):
    """Force a repo in/out of scope. exclude wins over include."""
    name = r["name"].lower()
    match = lambda pats: any(fnmatch.fnmatch(name, p.lower()) for p in pats)
    if match(exclude):
        r["in_scope"] = False
    elif match(include):
        r["in_scope"] = True
    elif opt_in_only:
        r["in_scope"] = False
    return r


def main():
    ap = argparse.ArgumentParser(description="Measure agent-context coverage across repos.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dir", help="folder containing cloned repos (scans immediate subdirs)")
    g.add_argument("--org", help="GitHub org/user login (uses gh CLI, no clone)")
    ap.add_argument("--out", help="write JSON here instead of stdout")
    ap.add_argument("--limit", type=int, default=300, help="max repos (org mode)")
    ap.add_argument("--include", default="", help="comma-separated name globs to force IN scope (opt-in, ignores cutoff)")
    ap.add_argument("--exclude", default="", help="comma-separated name globs to force OUT of scope (opt-out)")
    ap.add_argument("--overrides", help="JSON file: {\"include\":[...],\"exclude\":[...],\"opt_in_only\":bool}")
    ap.add_argument("--opt-in-only", action="store_true", help="only --include/overrides repos are in scope")
    ap.add_argument("--active-days", type=int, default=None,
                     help=f"in-scope cutoff: exclude repos with no commit in the last N days (default {MODEL['active_days']}; 0 = no cutoff)")
    ap.add_argument("--repos", default="",
                     help="comma-separated repo names to scan ONLY these (both modes); forces them all in scope")
    ap.add_argument("--clone", action="store_true",
                     help="org mode: clone each repo to measure EXACT LOC/context/freshness (slower; no byte estimate)")
    ap.add_argument("--jobs", type=int, default=8,
                     help="org mode: repos to scan in parallel (default 8; 1 = sequential)")
    args = ap.parse_args()

    if args.active_days is not None:
        MODEL["active_days"] = args.active_days
    only = [p.strip().lower() for p in args.repos.split(",") if p.strip()]

    # merge overrides file + CLI flags
    include = [p.strip() for p in args.include.split(",") if p.strip()]
    exclude = [p.strip() for p in args.exclude.split(",") if p.strip()]
    opt_in_only = args.opt_in_only
    if args.overrides:
        if not os.path.isfile(args.overrides):
            sys.exit(f"overrides file not found: {args.overrides}")
        try:
            with open(args.overrides, encoding="utf-8") as f:
                ov = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            sys.exit(f"could not read overrides file {args.overrides}: {e}")
        include += [p for p in ov.get("include", []) if p not in include]
        exclude += [p for p in ov.get("exclude", []) if p not in exclude]
        opt_in_only = opt_in_only or bool(ov.get("opt_in_only"))

    repos = []
    source = {}
    if args.dir:
        root = os.path.abspath(args.dir)
        source = {"mode": "local", "path": root}
        if not os.path.isdir(root):
            sys.exit(f"not a directory: {root}")
        subs = sorted([d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d)) and not d.startswith(".")])
        if only:
            subs = [d for d in subs if d.lower() in only]
        for i, d in enumerate(subs, 1):
            print(f"[{i}/{len(subs)}] scanning {d}...", file=sys.stderr)
            repos.append(classify(scan_local_repo(os.path.join(root, d), d)))
    else:
        source = {"mode": "org", "org": args.org}
        rc, out, err = sh(["gh", "repo", "list", args.org, "--limit", str(args.limit),
                           "--json", "name,pushedAt,createdAt,isArchived,isFork,primaryLanguage,defaultBranchRef"],
                          timeout=90)
        if rc != 0:
            sys.exit(f"gh repo list failed: {err}")
        metas = json.loads(out)
        if only:
            metas = [m for m in metas if m["name"].lower() in only]
        if args.clone:
            import shutil
            import tempfile
            tmp = tempfile.mkdtemp(prefix="ctxcov-")
            try:
                for i, meta in enumerate(metas, 1):
                    nm = meta["name"]
                    print(f"[{i}/{len(metas)}] cloning {nm}...", file=sys.stderr)
                    dest = os.path.join(tmp, nm)
                    rc, _, err = sh(["gh", "repo", "clone", f"{args.org}/{nm}", dest, "--", "--quiet"], timeout=300)
                    if rc != 0:
                        print(f"    clone failed ({(err or '').strip()[:80]}); using API scan", file=sys.stderr)
                        repos.append(classify(scan_org_repo(args.org, meta)))
                        continue
                    r = scan_local_repo(dest, nm)      # exact LOC + context + git freshness
                    r["is_archived"] = meta.get("isArchived", False)
                    r["is_fork"] = meta.get("isFork", False)
                    repos.append(classify(r))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
        else:
            def scan_one(meta):
                """Scan one repo, never raising -- a failure yields a stub with
                the error noted so one bad repo can't sink the whole run."""
                try:
                    return classify(scan_org_repo(args.org, meta))
                except Exception as e:                       # noqa: BLE001
                    return classify(_org_stub(meta, e))
            done = [0]
            def progress(meta):
                done[0] += 1
                print(f"[{done[0]}/{len(metas)}] inspected {meta['name']}", file=sys.stderr)
            jobs = max(1, args.jobs)
            if jobs > 1 and len(metas) > 1:
                try:
                    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
                        futs = {ex.submit(scan_one, m): m for m in metas}
                        for fut in cf.as_completed(futs):
                            progress(futs[fut])
                            repos.append(fut.result())
                except Exception as e:                       # pool-level failure -> sequential
                    print(f"parallel scan failed ({e}); falling back to sequential", file=sys.stderr)
                    repos = [scan_one(m) for m in metas]
            else:
                for m in metas:
                    progress(m)
                    repos.append(scan_one(m))
        if _GH_FAILURES["rate_limit"]:
            print(f"WARNING: {_GH_FAILURES['rate_limit']} gh calls hit the API rate limit — "
                  f"some line counts / freshness are missing. Wait for the limit to reset "
                  f"(gh api rate_limit) or scan fewer repos with --repos.", file=sys.stderr)
        elif _GH_FAILURES["other"]:
            print(f"note: {_GH_FAILURES['other']} gh calls failed (non-rate-limit); "
                  f"affected repos have partial data.", file=sys.stderr)

    # a hard --repos selection means "analyze exactly these" -> all in scope
    if only:
        found = {r["name"].lower() for r in repos}
        missing = [n for n in only if n not in found]
        if missing:
            print(f"warning: --repos names matched nothing: {', '.join(missing)}", file=sys.stderr)
        for r in repos:
            r["in_scope"] = True
    if include or exclude or opt_in_only:
        for r in repos:
            apply_overrides(r, include, exclude, opt_in_only)

    doc = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": source,
        "model": MODEL,
        "selection": only,
        "overrides": {"include": include, "exclude": exclude, "opt_in_only": opt_in_only},
        "repos": repos,
    }
    text = json.dumps(doc, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out} ({len(repos)} repos)", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
