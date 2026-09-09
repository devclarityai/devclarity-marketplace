#!/usr/bin/env python3
"""
context-coverage collector
===========================
Scans a set of repositories and measures how well each is covered by
agent context (CLAUDE.md / AGENTS.md), skills, and commands -- cross-
referenced against how *real*, *big*, *active*, and *fresh* each repo is.

Three modes:
  --dir  <folder>   Scan every git repo that is an immediate subdirectory
                    (full fidelity: real LOC, commit history, nested context).
  --org  <name>     Use the `gh` CLI to enumerate an org's repos and inspect
                    each via the GitHub trees/commits API without cloning
                    (lighter fidelity: byte-based size estimate).
  --repo <path>     One repo. With --scope "apps/web,libs/ui", each subpath is
                    analyzed as its own unit -- every measurement, git history
                    included, restricted to that subtree -- so a team in a
                    monorepo sees only the area it owns. Context above a scope
                    still governs it and is reported as inherited.

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


# ---------------------------------------------------------------------------
# Monorepo scoping helpers -- a "scope" is a subdirectory of one repo that is
# analyzed as its own unit, so a team sees only the area they own.
# ---------------------------------------------------------------------------
def norm_scope(scope):
    """Normalize a scope subpath: POSIX separators, no leading/trailing slash."""
    return (scope or "").replace("\\", "/").strip("/")


def under_scope(path, scope):
    """Is this repo-relative path inside the scope? (whole repo if no scope)"""
    return True if not scope else path == scope or path.startswith(scope + "/")


def rel_to_scope(path, scope):
    """Re-root a repo-relative path onto the scope, so the scope's own
    directory looks like a repo root to every downstream measurement."""
    return path[len(scope) + 1:] if scope and path.startswith(scope + "/") else path


def ancestor_dirs(scope):
    """Every directory above the scope, root ('') first. A CLAUDE.md in any of
    them genuinely governs the scope, so it is counted as inherited rather
    than ignored."""
    out = [""]
    parts = [p for p in norm_scope(scope).split("/") if p]
    for i in range(1, len(parts)):
        out.append("/".join(parts[:i]))
    return out


def context_governing_dir(path):
    """The directory a context artifact governs, or None if `path` is not one.

    A CLAUDE.md/AGENTS.md governs its own directory. A rule file governs the
    directory holding its `rules/` dir, stepping over a tool surface first, so
    `.cursor/rules/style.mdc` and `.claude/rules/r.md` govern the root exactly
    as a bare `rules/r.md` does. A skill governs the directory holding its
    surface. Fixed-path files (`.cursorrules`, `.github/copilot-instructions.md`)
    only ever exist at the root, so they govern the root."""
    segs = path.split("/")
    low = [s.lower() for s in segs]
    base = low[-1]
    if path.lower() in EXTRA_CONTEXT_FILES:
        return ""
    if base in ("claude.md", "agents.md"):
        return "/".join(segs[:-1])
    dirs = low[:-1]
    if base == "skill.md":
        for i, s in enumerate(dirs):
            if s in SURFACE_DIRS:
                return "/".join(segs[:i])
        return "/".join(segs[:-1])
    if os.path.splitext(base)[1] in RULE_EXTS:
        idx = max((i for i, s in enumerate(dirs) if s in RULES_DIR_NAMES),
                  default=-1)
        if idx >= 0:
            if idx > 0 and dirs[idx - 1] in SURFACE_DIRS:
                idx -= 1
            return "/".join(segs[:idx])
    return None


def ancestor_context_paths(paths, scope):
    """Every context artifact above the scope that still governs it -- any kind
    the unscoped scan would count, not just CLAUDE.md. A file inside the scope
    is the area's own and is never inherited, so a scope that is itself named
    `rules` keeps its own rule files."""
    anc = set(ancestor_dirs(scope))
    found = [p for p in paths
             if not under_scope(p, scope) and context_governing_dir(p) in anc]
    return sorted(found, key=lambda x: (x.count("/"), x))


def repo_dirs(root):
    """Every directory in the repo that holds tracked files, repo-relative and
    POSIX. Used to validate a --scope against what the scan will actually
    measure, which `os.path.isdir` does not: on a case-insensitive filesystem
    it happily accepts `Apps/Web` for `apps/web`, and the scan then matches
    nothing."""
    rc, out, _ = sh(["git", "ls-files", "-z"], cwd=root)
    dirs = set()
    if rc == 0:
        for f in out.split("\0"):
            parts = f.split("/")[:-1] if f else []
            for i in range(1, len(parts) + 1):
                dirs.add("/".join(parts[:i]))
        return dirs
    for dp, _, _ in walk_pruned(root):                  # not a git repo
        rel = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel != ".":
            dirs.add(rel)
    return dirs


def resolve_scope(requested, dirs):
    """Validate one --scope against the repo's real directories, returning
    (canonical_scope, error). Resolves case so the file filter and the git
    pathspec agree with what was typed, and rejects anything that would
    silently measure nothing (or everything)."""
    raw = (requested or "").strip()
    s = norm_scope(raw)
    if os.path.isabs(raw) or (len(raw) > 1 and raw[1] == ":"):
        return None, "must be relative to the repo root"
    if not s:
        return None, "is empty -- name a subdirectory, or drop --scope to scan the whole repo"
    if any(seg in (".", "..") for seg in s.split("/")):
        return None, "must not contain '.' or '..' segments"
    if any(ch in s for ch in "*?[]:"):
        return None, "must be a plain path (no glob or git pathspec magic)"
    if s in dirs:
        return s, None
    matches = sorted(d for d in dirs if d.lower() == s.lower())
    if len(matches) == 1:
        return matches[0], None
    if matches:
        return None, "matches several directories by case: " + ", ".join(matches)
    return None, "is not a directory holding tracked files in this repo"


def add_inherited_anchors(r, path, inherited):
    """Fold ancestor context into the scope's record: each file becomes an
    anchor governing the scope root (dir ''), flagged `inherited` so the report
    can show it as borrowed, and its lines count toward coverage. Skills and
    fixed-path files carry no line count, matching how the unscoped scan
    counts them."""
    r["inherited_context_lines"] = 0
    r["inherited_skills_count"] = 0
    if not inherited:
        return
    rules_by_dir, total, skills, extra = {}, 0, 0, set()
    for p in inherited:
        low = p.lower()
        base = low.rsplit("/", 1)[-1]
        if low in EXTRA_CONTEXT_FILES:
            extra.add(EXTRA_CONTEXT_FILES[low])
            continue
        if base == "skill.md":
            skills += 1
            continue
        n = count_lines(os.path.join(path, p))
        total += n
        if base in ("claude.md", "agents.md"):
            r["context_anchors"].append({
                "dir": "", "lines": n, "path": p, "inherited": True,
                "kind": "claude" if base == "claude.md" else "agents"})
        else:
            rules_by_dir[_dir_of(p)] = rules_by_dir.get(_dir_of(p), 0) + n
    for d, n in sorted(rules_by_dir.items()):
        r["context_anchors"].append({"dir": "", "lines": n, "path": d,
                                     "kind": "rules", "inherited": True})
    r["inherited_context_lines"] = total
    r["total_context_lines"] = (r.get("total_context_lines") or 0) + total
    r["inherited_skills_count"] = skills
    r["skills_count"] = (r.get("skills_count") or 0) + skills
    r["extra_context"] = sorted(set(r.get("extra_context") or []) | extra)
    if rules_by_dir:
        r["has_rules"] = True


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
def scan_local_repo(path, name, scope=None):
    """Scan a repo (or, with `scope`, one subdirectory of it as its own unit).

    Under a scope every measurement is restricted to that subtree -- LOC, file
    counts, the folder tree, and (crucially in a monorepo) git activity, which
    is filtered with a pathspec so another team's churn never makes this area
    look stale. Context above the scope is picked up separately as inherited."""
    scope = norm_scope(scope)
    r = {"name": name, "mode": "local", "errors": []}
    if scope:
        r["scope"] = scope
        r["repo"] = os.path.basename(os.path.abspath(path))
    is_git = os.path.isdir(os.path.join(path, ".git"))
    r["is_git"] = is_git
    # Pathspec limiting every git query to the scope (empty = whole repo).
    pathspec = ["--", scope] if scope else []

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
        for repo_rel in tracked:
            if not under_scope(repo_rel, scope):
                continue
            rel = rel_to_scope(repo_rel, scope)
            file_count += 1
            low = rel.lower()
            if "/" not in low and low.startswith("readme"):
                has_readme = True
            if low in EXTRA_CONTEXT_FILES:
                extra_ctx.add(EXTRA_CONTEXT_FILES[low])
            ext = os.path.splitext(rel)[1].lower()
            if ext in CODE_EXTS:
                code_files += 1
                nl = count_lines(os.path.join(path, repo_rel))
                loc += nl
                file_locs.append((rel, nl))
    else:
        base_dir = os.path.join(path, scope) if scope else path
        for dp, _, fns in walk_pruned(base_dir):
            for fn in fns:
                file_count += 1
                rel = os.path.relpath(os.path.join(dp, fn), base_dir).replace("\\", "/")
                low = rel.lower()
                if dp == base_dir and fn.lower().startswith("readme"):
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
        rc, out, _ = sh(["git", "rev-list", "--count", "HEAD"] + pathspec, cwd=path)
        r["commits_total"] = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
        since = datetime.fromtimestamp(NOW - MODEL["active_window_days"] * DAY,
                                       tz=timezone.utc).strftime("%Y-%m-%d")
        rc, out, _ = sh(["git", "rev-list", "--count", "--since", since, "HEAD"] + pathspec, cwd=path)
        r["commits_recent"] = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
        rc, out, _ = sh(["git", "log", "-1", "--format=%ct"] + pathspec, cwd=path)
        r["last_commit_days"] = round((NOW - int(out.strip())) / DAY, 1) if rc == 0 and out.strip().isdigit() else None
        # age: oldest commit touching this area (the whole repo, unscoped)
        rc2, out2, _ = sh(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=path) if not scope \
            else sh(["git", "log", "--format=%ct", "--reverse"] + pathspec, cwd=path)
        first = None
        if rc2 == 0 and out2.strip():
            if scope:
                head = out2.strip().splitlines()[0]
                if head.isdigit():
                    first = round((NOW - int(head)) / DAY, 1)
            else:
                fsha = out2.strip().splitlines()[-1]
                rc3, o3, _ = sh(["git", "log", "-1", "--format=%ct", fsha], cwd=path)
                if rc3 == 0 and o3.strip().isdigit():
                    first = round((NOW - int(o3.strip())) / DAY, 1)
        r["age_days"] = first
        rc, out, _ = sh(["git", "shortlog", "-sne", "HEAD"] + pathspec, cwd=path)
        r["contributors"] = len([l for l in out.splitlines() if l.strip()]) if rc == 0 else 0
    else:
        r.update(commits_total=0, commits_recent=0, last_commit_days=None,
                 age_days=None, contributors=0)

    # --- context inventory --------------------------------------------------
    inventory_context(path, r, tracked, scope)
    return r


def inventory_context(path, r, tracked, scope=None):
    """Local context inventory: classify paths, read real line counts, assemble,
    then measure freshness from git.

    With a scope, only context inside that subtree is the area's *own*; context
    in ancestor directories is added as `inherited` (it does govern the area),
    and freshness is measured against commits to the scope only."""
    scope = norm_scope(scope)
    if tracked is not None:
        paths = [p for p in tracked if not any(s in PRUNE_DIRS for s in p.split("/"))]
    else:
        paths = []
        base = os.path.abspath(path)
        for dp, _, fns in walk_pruned(path):
            for fn in fns:
                ap = os.path.abspath(os.path.join(dp, fn))
                paths.append(ap[len(base):].lstrip("/\\").replace("\\", "/") if ap.startswith(base) else fn)

    inherited = ancestor_context_paths(paths, scope) if scope else []
    own_paths = [rel_to_scope(p, scope) for p in paths if under_scope(p, scope)] if scope else paths
    c = classify_context_paths(own_paths)
    if scope:
        # Re-rooting strips the `rules/` marker from a scope that is itself a
        # rules dir (--scope rules -> `rules/r.md` becomes `r.md`), so recover
        # those from the repo-relative path. They govern the scope root.
        known = set(c["rules"])
        for p in paths:
            low = p.lower()
            if (under_scope(p, scope)
                    and os.path.splitext(low)[1] in RULE_EXTS
                    and any(s in RULES_DIR_NAMES for s in low.split("/")[:-1])):
                rp = rel_to_scope(p, scope)
                if rp not in known:
                    c["rules"].append(rp)
                    known.add(rp)
    ctx = context_files(c)                                   # scope-relative
    repo_ctx = [(scope + "/" + p if scope else p) for p in ctx]   # repo-relative
    lines = {p: count_lines(os.path.join(path, scope, p) if scope
                            else os.path.join(path, p)) for p in ctx}
    finish_context(r, c, lines)
    add_inherited_anchors(r, path, inherited)

    # --- context freshness (git) -------------------------------------------
    r["context_last_updated_days"] = None
    r["commits_since_context"] = None
    # Freshness measures the same kinds in both modes -- prose and rules, not
    # skills or fixed-path files -- or a skill edit would reset a scoped area's
    # clock while leaving the unscoped run's untouched.
    all_ctx = repo_ctx + [p for p in inherited
                          if p.lower() not in EXTRA_CONTEXT_FILES
                          and p.rsplit("/", 1)[-1].lower() != "skill.md"]
    if r.get("is_git") and all_ctx:
        rc, out, _ = sh(["git", "log", "-1", "--format=%ct", "--"] + all_ctx, cwd=path)
        if rc == 0 and out.strip().isdigit():
            ts = int(out.strip())
            r["context_last_updated_days"] = round((NOW - ts) / DAY, 1)
            since = datetime.fromtimestamp(ts + 1, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            # scoped: only commits touching this area count against its context
            rc2, out2, _ = sh(["git", "rev-list", "--count", "--since", since, "HEAD"]
                              + (["--", scope] if scope else []), cwd=path)
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

    # What the unit owns, vs what governs it from above. Equal to the totals
    # unless a scope inherited something.
    anchors = r.get("context_anchors") or []
    inh_lines = r.get("inherited_context_lines") or 0
    r["own_context_lines"] = max(0, ctx_lines - inh_lines)
    r["own_skills_count"] = max(0, (r.get("skills_count") or 0)
                                - (r.get("inherited_skills_count") or 0))
    r["own_rules"] = any(a.get("kind") == "rules" and not a.get("inherited")
                         for a in anchors)
    r["has_front_door"] = bool(r.get("has_claude_md") or r.get("has_agents_md")
                               or any(a.get("kind") in ("claude", "agents")
                                      and a.get("inherited") for a in anchors))
    r["owns_no_context"] = bool(anchors) and not r["own_context_lines"]

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
    g.add_argument("--repo", help="a single repo (monorepo mode); pair with --scope to analyze only your area")
    ap.add_argument("--scope", default="",
                     help="--repo only: comma-separated subpaths to analyze as separate units "
                          "(e.g. 'apps/web,libs/ui'). Everything outside them is ignored; "
                          "CLAUDE.md above a scope is counted as inherited context.")
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

    scopes = [s for s in args.scope.split(",") if s.strip()]
    if scopes and not args.repo:
        sys.exit("--scope only applies to --repo (a single repo). For a folder of clones use --dir.")

    repos = []
    source = {}
    if args.repo:
        # --- monorepo mode: one repo, optionally split into per-team areas ---
        root = os.path.abspath(args.repo)
        if not os.path.isdir(root):
            sys.exit(f"not a directory: {root}")
        repo_name = os.path.basename(root.rstrip(os.sep)) or root
        if scopes:
            dirs = repo_dirs(root)
            resolved, bad = [], []
            for s in scopes:
                canon, err = resolve_scope(s, dirs)
                (bad if err else resolved).append(f"  {s!r} {err}" if err else canon)
            if bad:
                sys.exit(f"bad --scope for {repo_name}:\n" + "\n".join(bad))
            seen = set()
            scopes = [s for s in resolved if not (s in seen or seen.add(s))]
        source = {"mode": "repo", "path": root, "repo": repo_name, "scopes": scopes}
        units = [(s, f"{repo_name}/{s}") for s in scopes] or [("", repo_name)]
        for i, (s, label) in enumerate(units, 1):
            print(f"[{i}/{len(units)}] scanning {label}...", file=sys.stderr)
            repos.append(classify(scan_local_repo(root, label, s)))
        # an explicitly named repo/area is always analyzed -- no activity cutoff
        for r in repos:
            r["in_scope"] = True
    elif args.dir:
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
