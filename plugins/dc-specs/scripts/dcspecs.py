#!/usr/bin/env python3
"""dc-specs helper: the deterministic parts of the spec lifecycle.

Tracker specs arrive on stdin or as a saved JSON file (the agent fetches them over MCP); GitHub and
markdown specs are read with gh and git. Output is JSON unless noted.

Runs on Python 3.9 or later, standard library only, on macOS, Linux and Windows.
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import difflib
import hashlib
import html
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

SOURCES = ("markdown", "github", "jira", "linear", "ado")
REQUIRED_KEYS = {"markdown": [], "github": ["repo"], "jira": ["site", "project"], "linear": ["team"],
                 "ado": ["org", "project"]}
OPTIONAL_KEYS = {"markdown": ["dir", "id_prefix"], "github": [], "jira": ["issue_type"], "linear": [],
                 "ado": ["work_item_type"]}
ADO_ORG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,49}")
ADO_DEFAULT_TYPE = "User Story"
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_TEMPLATES = os.path.join(PLUGIN_ROOT, "templates")
VERDICT_TEMPLATE = os.path.join(PLUGIN_TEMPLATES, "verdict.md")
EVIDENCE_SUFFIX = ".evidence.md"
FALLBACK_EVIDENCE = "feature"
TEMPLATE_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")

FREEZE_TAG = "dc-specs freeze"
_Q = "[\"\u201c\u201d]"
FREEZE_RE = re.compile(
    r"dc\\?-specs\s+freeze\W+fingerprint\W+([0-9a-f]{12})"
    r"(?:\W+status\s+\\?" + _Q + r"([^\"\u201c\u201d\\]*)\\?" + _Q + r")?"
    r"(?:\W+approved\s+([\dT:\-]+Z|unknown))?"
    r"(?:\W+(\d{4}-\d{2}-\d{2}T[\d:]+Z))?"
)
AC_ID = r"AC\d+\b"
AC_LABEL = r"\**(" + AC_ID + r")\**(?:\s*\\?\[([^\]\\]+)\\?\])?\**"      # AC3 [billing-api]
AC_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)?(?:\\?\[[ xX]\\?\]\s+)?" + AC_LABEL
                   + r"\s*[:.)\-]?\**\s*(.*)$")
AC_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+(?=\**AC\d+\**(?:\s*\\?\[[^\]]+\\?\])?\**\s*[:.)\-]?\**\s*Given\b)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
AMEND_RE = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])\s+(\d{4}-\d{2}-\d{2})\s+((?:AC\d+)(?:\s*,\s*AC\d+)*|general)\s*:\s*(.+)$")
RULE_RE = re.compile(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?")
HTML_TAGS = "b|i|u|s|a|p|br|hr|em|strong|code|kbd|sub|sup|span|div|img|del|ins|mark|small|pre|details|summary|ul|ol|li|table|tr|td|th"
PLACEHOLDER_RE = re.compile(r"<(?!(?:" + HTML_TAGS + r")\b)[a-z][a-z0-9 ,.:'-]*>")


class SpecError(Exception):
    """A spec, config or tool problem the helper reports to the user, exiting with status 2."""
    pass


def _proc(cmd, **kw):
    """Run a tool found on PATH as UTF-8 text, raising FileNotFoundError when it is not there.

    shutil.which finds az.cmd and gh.exe on Windows, which a bare name passed to subprocess does not.

    A .cmd or .bat tool runs through cmd.exe, which splits an unquoted argument at characters such as & and drops
    the rest of the command (#18). So every argument is quoted and the line handed to cmd.exe /s /c. cmd.exe has no
    safe way to pass a double quote inside a quoted argument, so such an argument is refused.

    Raises:
        SpecError: When an argument for a .cmd or .bat tool contains a double quote.
    """
    exe = shutil.which(cmd[0])
    if exe is None:
        raise FileNotFoundError(cmd[0])
    args = [exe] + list(cmd[1:])
    if exe.lower().endswith((".cmd", ".bat")):
        if any('"' in a for a in args):
            raise SpecError(f"{cmd[0]} runs through cmd.exe, which cannot pass an argument containing a double quote")
        line = " ".join(f'"{a}"' for a in args)
        args = f'"{os.environ.get("COMSPEC", "cmd.exe")}" /d /s /c "{line}"'
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


# ---------------------------------------------------------------- time

def parse_ts(raw: str | None):
    """Parse a tracker or git timestamp into an aware UTC datetime, or None for empty, 'unknown' or bad input.

    Accepts ISO 8601 with Z, +hh:mm or +hhmm offsets, fractional seconds of any length, and times without seconds.
    A timestamp without an offset is taken as UTC.
    """
    if not raw or raw == "unknown":
        return None
    s = raw.strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    s = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], s)
    s = re.sub(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})([+-]\d{2}:\d{2})$", r"\1:00\2", s)
    try:
        t = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)).astimezone(_dt.timezone.utc)


def fmt_ts(t) -> str:
    """Format a UTC datetime as an ISO 8601 timestamp with a Z suffix, such as 2026-10-01T14:03:00Z."""
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- config

def _unquoted(s: str):
    """Yield (index, char) for each character of s outside single or double quotes."""
    q = None
    for i, ch in enumerate(s):
        if q:
            q = None if ch == q else q
        elif ch in "\"'":
            q = ch
        else:
            yield i, ch


def _strip_comment(line: str) -> str:
    """Remove a YAML comment: a # outside quotes at the start of the line or after whitespace."""
    for i, ch in _unquoted(line):
        if ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def _split_list(s: str) -> list:
    """Split the inside of an inline YAML list on commas outside quotes, dropping empty items."""
    cuts = [-1] + [i for i, ch in _unquoted(s) if ch == ","] + [len(s)]
    return [s[a + 1:b].strip() for a, b in zip(cuts, cuts[1:]) if s[a + 1:b].strip()]


def _scalar(v: str):
    """Convert a YAML scalar to None, a list, an unquoted string, a bool, an int or the string itself."""
    v = v.strip()
    if not v:
        return None
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in _split_list(v[1:-1])]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    return int(v) if re.fullmatch(r"-?\d+", v) else v


def parse_yaml_subset(text: str) -> dict:
    """Parse the YAML subset that specs/config.yaml uses.

    Supports nested mappings by space indentation, scalars, inline [lists] and '- item' lists, comments, CRLF line
    endings and a leading BOM. Anything else is an error.

    Raises:
        SpecError: When a line is indented with tabs, is not 'key: value', or is a list item without a key.
    """
    lines = [_strip_comment(l).rstrip() for l in text.replace("\r\n", "\n").lstrip("\ufeff").split("\n")]
    root: dict = {}
    stack = [(-1, root)]
    last_key: dict = {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise SpecError(f"config line {n}: indent with spaces, not tabs")
        indent, body = len(line) - len(line.lstrip(" ")), line.strip()
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if body.startswith("- "):
            key = last_key.get(id(parent))
            if key is None or not isinstance(parent.get(key), list):
                raise SpecError(f"config line {n}: list item without a key")
            parent[key].append(_scalar(body[2:]))
            continue
        if ":" not in body:
            raise SpecError(f"config line {n}: expected 'key: value'")
        key, _, val = body.partition(":")
        key = key.strip()
        last_key[id(parent)] = key
        if val.strip():
            parent[key] = _scalar(val)
            continue
        nxt = next((lines[j] for j in range(n, len(lines)) if lines[j].strip()), "")
        if nxt.strip().startswith("- "):
            parent[key] = []
        else:
            parent[key] = {}
            stack.append((indent, parent[key]))
    return root


def git_root(start: str = ".") -> str | None:
    """The real path of the git repo containing start, or None outside a repo or without git."""
    try:
        out = _proc(["git", "-C", start, "rev-parse", "--show-toplevel"], check=True)
        return os.path.realpath(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        return None


def load_config(path: str | None, start: str = ".") -> dict:
    """Read and validate specs/config.yaml.

    Args:
        path: The config file, or None for specs/config.yaml at the git root of start.

    Returns:
        The parsed config, with _path set to the file's real path and _root to the directory that holds specs/.

    Raises:
        SpecError: When the config is missing or invalid.
    """
    if not path:
        path = os.path.join(git_root(start) or os.path.realpath(start), "specs", "config.yaml")
        if not os.path.isfile(path):
            raise SpecError("no specs/config.yaml in this repo. Run the spec-setup skill to set one up, then retry.")
    elif not os.path.isfile(path):
        raise SpecError(f"config not found: {path}")
    with open(path, encoding="utf-8") as f:
        cfg = parse_yaml_subset(f.read())
    errors = validate_config(cfg)
    if errors:
        raise SpecError("invalid specs/config.yaml: " + "; ".join(errors))
    cfg["_path"] = os.path.realpath(path)
    cfg["_root"] = os.path.dirname(os.path.dirname(cfg["_path"]))
    return cfg


def validate_config(cfg: dict) -> list:
    """One message per problem with a parsed config's source, approval status or required keys."""
    errs = []
    src = cfg.get("source")
    if src not in SOURCES:
        errs.append(f"source must be one of {', '.join(SOURCES)} (got {src!r})")
    appr = cfg.get("approval")
    if not isinstance(appr, dict) or not appr.get("status"):
        errs.append("approval.status is required (the status, label or frontmatter value that freezes a spec)")
    if REQUIRED_KEYS.get(src):
        block = cfg.get(src)
        if not isinstance(block, dict):
            errs.append(f"a {src}: block is required")
        else:
            errs += [f"{src}.{k} is required" for k in REQUIRED_KEYS[src] if not block.get(k)]
            if src == "github" and block.get("repo") and not re.fullmatch(r"[\w.-]+/[\w.-]+", str(block["repo"])):
                errs.append("github.repo must be owner/name")
            if src == "ado" and block.get("org") and not ADO_ORG_RE.fullmatch(str(block["org"])):
                errs.append("ado.org must be the organization name (the part after dev.azure.com/), not a URL")
    return errs


def frozen_statuses(cfg: dict) -> list:
    """Every status that freezes a spec, in order: approval, in progress, done, then also frozen."""
    appr = cfg.get("approval")
    if not isinstance(appr, dict):
        return []
    extra = appr.get("also_frozen") or []
    vals = [appr.get("status"), appr.get("in_progress"), appr.get("done")]
    vals += [extra] if isinstance(extra, str) else list(extra)
    return [str(v).strip() for v in vals if v]


def is_frozen_status(value, cfg: dict) -> bool:
    """Whether a status, or any of a list of labels, is a frozen status, ignoring case."""
    frozen = {s.casefold() for s in frozen_statuses(cfg)}
    values = value if isinstance(value, list) else [value]
    return any(v is not None and str(v).strip().casefold() in frozen for v in values)


# ---------------------------------------------------------------- setup

def _yq(v) -> str:
    """Quote a YAML scalar when the subset parser would misread it."""
    v = str(v)
    if v == "" or re.search(r"[#:,\[\]'\"]|^\s|\s$|^-|^(true|false|-?\d+)$", v):
        return "'" + v + "'" if '"' in v else '"' + v + '"'
    return v


def build_config(source: str, approval: str, in_progress: str | None = None, done: str | None = None,
                 also_frozen: list | None = None, **opts) -> str:
    """The text of specs/config.yaml for a source and its frozen statuses.

    Args:
        in_progress: The status while the spec is built, also frozen.
        done: The status once the spec is closed, also frozen.
        **opts: The source's keys (repo, site, project, issue_type, team, org, work_item_type, dir, id_prefix) and
            templates, the folder of the repo's own templates.

    Raises:
        SpecError: When the source is unknown, the approval status is empty, a markdown frozen status is 'draft', or
            the result does not validate.
    """
    if source not in SOURCES:
        raise SpecError(f"source must be one of {', '.join(SOURCES)}")
    clean = lambda v: v.strip() if isinstance(v, str) else v
    approval, in_progress, done = clean(approval), clean(in_progress), clean(done)
    also_frozen = [clean(x) for x in also_frozen or [] if clean(x)]
    if not approval:
        raise SpecError("approval status is empty")
    if source == "markdown" and any(v and v.casefold() == "draft" for v in [approval, in_progress, done] + also_frozen):
        raise SpecError("a frozen status cannot be 'draft': new markdown specs are created as draft, "
                        "so every spec would be frozen on its first commit")
    lines = ["# dc-specs: where specs live and what freezes them. See the plugin's references/config.md.",
             f"source: {source}", "approval:", f"  status: {_yq(approval)}"]
    lines += [f"  {k}: {_yq(v)}" for k, v in (("in_progress", in_progress), ("done", done)) if v]
    if also_frozen:
        lines += ["  also_frozen:"] + [f"    - {_yq(x)}" for x in also_frozen]
    block = [(k, clean(opts.get(k))) for k in REQUIRED_KEYS[source] + OPTIONAL_KEYS[source] if clean(opts.get(k))]
    if block or source != "markdown":
        lines += [f"{source}:"] + [f"  {k}: {_yq(v)}" for k, v in block]
    if opts.get("templates"):
        lines.append(f"templates: {_yq(clean(opts['templates']))}")
    text = "\n".join(lines) + "\n"
    errs = validate_config(parse_yaml_subset(text))
    if errs:
        raise SpecError("; ".join(errs))
    return text


def config_changes(old: dict, new: dict, prefix: str = "") -> list:
    """[{key, from, to}] for each dotted key that differs between two configs, sorted by key."""
    out = []
    for k in sorted(set(old) | set(new)):
        a, b = old.get(k), new.get(k)
        if isinstance(a, dict) or isinstance(b, dict):
            out += config_changes(a if isinstance(a, dict) else {}, b if isinstance(b, dict) else {}, f"{prefix}{k}.")
        elif a != b:
            out.append({"key": prefix + k, "from": a, "to": b})
    return out


def init_config(root: str, text: str, force: bool, dry_run: bool) -> dict:
    """Write specs/config.yaml, refusing to change an existing one without force.

    Returns:
        {path, exists, written, changes, source_changed, location_changed, needs_force, warnings, config}. warnings
            says when specs in the old place will no longer be found.
    """
    path = os.path.join(root, "specs", "config.yaml")
    new = parse_yaml_subset(text)
    out = {"path": path, "exists": os.path.isfile(path), "written": False, "changes": [],
           "source_changed": False, "location_changed": False, "needs_force": False, "warnings": [], "config": text}
    if out["exists"]:
        with open(path, encoding="utf-8", errors="replace") as f:
            try:
                old = parse_yaml_subset(f.read())
            except SpecError:
                old = {}
        if not old or validate_config(old):
            out["warnings"].append("the existing config is invalid; it will be replaced")
        out["changes"] = config_changes(old, new)
        src = old.get("source")
        where = REQUIRED_KEYS.get(src) or ["dir"]
        if src and src != new.get("source"):
            out["source_changed"] = True
        elif isinstance(old.get(src), dict) and any(old[src].get(k) != (new.get(src) or {}).get(k) for k in where):
            out["location_changed"] = True
        if out["source_changed"] or out["location_changed"]:
            out["warnings"].append("specs written in the old place stay there, and the skills will no longer find "
                                   "them: finish in-flight work first or move those specs by hand.")
        out["needs_force"] = bool(out["changes"])
    if dry_run or (out["needs_force"] and not force):
        return out
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    out["written"] = True
    return out


def _git(args, cwd):
    """Run git in cwd, raising FileNotFoundError when git is not installed."""
    return _proc(["git"] + args, cwd=cwd)


def default_branch(root: str) -> str | None:
    """The default branch (origin's HEAD such as origin/main, else a local main or master), or None."""
    r = _git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], root)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return next((b for b in ("main", "master") if _git(["rev-parse", "--verify", "--quiet", b], root).returncode == 0),
                None)


def _run(cmd):
    """Run a tool, returning None instead of raising when it is not on PATH."""
    try:
        return _proc(cmd)
    except FileNotFoundError:
        return None


# ---------------------------------------------------------------- dependencies

INSTALL = {
    "python": {"macos": "xcode-select --install, or brew install python",
               "linux": "the package manager: sudo apt install python3, or sudo dnf install python3",
               "windows": "winget install --id Python.Python.3.13 -e"},
    "git": {"macos": "xcode-select --install, or brew install git",
            "linux": "the package manager: sudo apt install git, or sudo dnf install git",
            "windows": "winget install --id Git.Git -e"},
    "gh": {"macos": "brew install gh", "linux": "https://github.com/cli/cli/blob/trunk/docs/install_linux.md",
           "windows": "winget install --id GitHub.cli -e"},
    "az": {"macos": "brew install azure-cli", "linux": "https://learn.microsoft.com/cli/azure/install-azure-cli-linux",
           "windows": "winget install --id Microsoft.AzureCLI -e"},
}
SOURCE_TOOLS = {"markdown": [], "github": ["gh"], "jira": [], "linear": [], "ado": ["az"]}
SOURCE_MCP = {
    "jira": "Confirm the Atlassian MCP server is connected: getAccessibleAtlassianResources answers. If not, stop and "
            "tell the human to connect it (claude.ai connectors, or claude mcp add).",
    "linear": "Confirm a Linear MCP server is connected: its team list answers. If not, stop and tell the human to "
              "connect it (claude.ai connectors, or claude mcp add).",
}


def os_name() -> str:
    """The OS as INSTALL keys it: macos, windows, or linux for anything else."""
    return {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "linux")


def install_hint(tool: str) -> str:
    """The install command or URL for a tool on this OS."""
    return INSTALL[tool][os_name()]


def deps(source: str | None) -> dict:
    """Check the tools the helper and the source need, each found or with its install step for this OS.

    Python and git are always checked. GitHub adds gh, and Azure DevOps adds az and its azure-devops extension. az is
    found by path only, because az --version can make a network call.

    Returns:
        {os, source, ok, checks, agent_checks}. checks is [{tool, ok, detail}], with install on each missing tool.
            agent_checks lists the MCP connections the agent confirms for Jira and Linear.
    """
    checks = []

    def add(tool, ok, detail, install):
        checks.append({"tool": tool, "ok": bool(ok), "detail": detail, **({} if ok else {"install": install})})

    add("python", sys.version_info >= (3, 9), f"{platform.python_version()} at {sys.executable}",
        install_hint("python") + " (3.9 or later)")
    for tool in ["git"] + SOURCE_TOOLS.get(source or "", []):
        path = shutil.which(tool)
        r = _run([tool, "--version"]) if path and tool != "az" else None   # az --version can call home
        add(tool, path, ((r.stdout or "").strip().split("\n")[0] if r and r.returncode == 0 else path) or "not found",
            install_hint(tool))
    if source == "ado" and shutil.which("az"):
        r = _run(["az", "extension", "show", "--name", "azure-devops", "-o", "json"])
        add("azure-devops extension", r and r.returncode == 0, "installed" if r and r.returncode == 0 else "missing",
            "az extension add --name azure-devops")
    return {"os": os_name(), "source": source, "ok": all(c["ok"] for c in checks), "checks": checks,
            "agent_checks": [SOURCE_MCP[source]] if source in SOURCE_MCP else []}


# ---------------------------------------------------------------- report-issue

REPORT_REPO = "devclarityai/devclarity-marketplace"
REPORT_LINK_LIMIT = 8000
REPORT_LABELS = ("bug", "enhancement")


def plugin_version() -> str:
    """This plugin's version from .claude-plugin/plugin.json, or 'unknown'."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".claude-plugin", "plugin.json")
    try:
        with open(path, encoding="utf-8") as f:
            return str(json.load(f)["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "unknown"


def _version_in(text: str) -> str:
    """The first dotted version number in text, or 'unknown', so no path in a tool's output is echoed."""
    m = re.search(r"\d+(?:\.\d+)+", text or "")
    return m.group(0) if m else "unknown"


def report_env(cfg: dict | None) -> dict:
    """The environment for a dc-specs issue, with nothing from the reporter's repo in it.

    Only version numbers are kept from tool output, so install paths and usernames never appear. The config gives
    only its source type; repos, project keys, URLs and other values are left out.

    Returns:
        {dc_specs, os, python, source, tools}, where source is None without a valid config and tools maps git and the
            source's tools to a version, 'not found' or 'unknown'.
    """
    source = cfg["source"] if cfg else None
    tools = {}
    for tool in ["git"] + SOURCE_TOOLS.get(source or "", []):
        if not shutil.which(tool):
            tools[tool] = "not found"
        elif tool == "az":   # az --version can call home; az version reads only what is installed
            r = _run(["az", "version", "-o", "json"])
            try:
                info = json.loads(r.stdout) if r and r.returncode == 0 else {}
            except ValueError:
                info = {}
            ext = info.get("extensions", {}).get("azure-devops")
            tools["az"] = _version_in(str(info.get("azure-cli", "")))
            tools["azure-devops extension"] = _version_in(str(ext)) if ext else "not installed" if info else "unknown"
        else:
            r = _run([tool, "--version"])
            tools[tool] = _version_in((r.stdout or "").split("\n")[0]) if r and r.returncode == 0 else "unknown"
    if source == "ado" and "azure-devops extension" not in tools:
        tools["azure-devops extension"] = "not found"
    return {"dc_specs": plugin_version(), "os": f"{os_name()} {_version_in(platform.release())}",
            "python": platform.python_version(), "source": source, "tools": tools}


def report_link(title: str, label: str, body: str) -> dict:
    """A prefilled new-issue link on the dc-specs repo, for a reporter without a working gh.

    The body goes into the link only while the whole link stays within REPORT_LINK_LIMIT characters, which browsers
    and GitHub accept. Otherwise the link carries the title and label, and the body comes back to paste.

    Returns:
        {url, length, body_in_link}, plus body when body_in_link is false.
    """
    base = f"https://github.com/{REPORT_REPO}/issues/new?" + urllib.parse.urlencode({"title": title, "labels": label})
    full = base + "&" + urllib.parse.urlencode({"body": body}) if body else base
    if len(full) <= REPORT_LINK_LIMIT:
        return {"url": full, "length": len(full), "body_in_link": True}
    return {"url": base, "length": len(base), "body_in_link": False, "body": body}


def setup_check(cfg: dict) -> dict:
    """Check that a repo's setup works: git, the config's branch, repo templates and the source's connection.

    GitHub and Azure DevOps are checked here through gh and az. Jira and Linear are reached over MCP, so their checks
    come back as instructions for the agent.

    Returns:
        {source, ok, checks, agent_checks}. checks is [{check, ok, level, detail}], with level ok, warning or error;
            ok is False when any check is an error.
    """
    checks, todo = [], []

    def add(name, ok, detail="", level="error"):
        checks.append({"check": name, "ok": bool(ok), "level": "ok" if ok else level, "detail": detail})

    root, src = cfg["_root"], cfg["source"]
    in_git = git_root(root) is not None
    add("git repo", in_git, root)
    if in_git:
        rel, br = os.path.relpath(cfg["_path"], root).replace(os.sep, "/"), default_branch(root)
        on = bool(br) and _git(["cat-file", "-e", f"{br}:{rel}"], root).returncode == 0
        add("config on the default branch", on, f"{rel} is on {br}" if on else
            f"{rel} is not on {br or 'the default branch'} yet; until it merges, dc-specs only works on a branch that "
            "has it", "warning")
    evidence = list_templates(cfg, evidence=True)
    for kind, found in (("template", list_templates(cfg)), ("evidence template", evidence)):
        for t in found.values():
            if t["source"] != "repo":
                continue
            add(f"{kind} '{t['name']}'", not t["errors"], "; ".join(t["errors"]) or "usable")
            if kind == "template" and t["name"] not in evidence:
                add(f"evidence template for '{t['name']}'", False,
                    f"none: evidence render uses the '{FALLBACK_EVIDENCE}' one", "warning")
    if src == "github":
        repo = cfg["github"]["repo"]
        r = _run(["gh", "auth", "status", "--hostname", "github.com"])
        if r is None:
            add("gh installed", False, "install gh (" + install_hint("gh") + "), then gh auth login")
        else:
            add("gh logged in to github.com", r.returncode == 0,
                "yes" if r.returncode == 0 else (r.stderr or r.stdout).strip().split("\n")[0][:160])
        if r is not None and r.returncode == 0:
            for label in frozen_statuses(cfg):
                q = _run(["gh", "api", f"repos/{repo}/labels/" + urllib.parse.quote(label, safe="")])
                add(f"label '{label}'", q.returncode == 0, "exists" if q.returncode == 0 else
                    "missing or unreadable: gh label create " + shlex.quote(label) + " --repo " + shlex.quote(repo))
    elif src == "jira":
        j = cfg["jira"]
        todo += [
            f"Call getAccessibleAtlassianResources and confirm a site matching {j['site']}.",
            f"Call searchJiraIssuesUsingJql with 'project = {j['project']} order by created DESC', maxResults 50, "
            "fields [status, issuetype], and getTransitionsForJiraIssue with includeUnavailableTransitions true on one "
            f"of them. Confirm {', '.join(frozen_statuses(cfg))} all appear among the statuses, and issue type "
            f"{j.get('issue_type') or 'Story'} among the issue types.",
            "Confirm the approval status is not the status new issues are created in.",
        ]
    elif src == "ado":
        ado_checks(cfg, add)
    elif src == "linear":
        todo += [
            "Confirm a Linear MCP server is connected. If not, stop: tell the human to connect it.",
            f"List team {cfg['linear']['team']}'s workflow states; confirm {', '.join(frozen_statuses(cfg))} all exist, "
            "and that the approval state is not the default state for new issues.",
        ]
    return {"source": src, "ok": not [c for c in checks if c["level"] == "error"], "checks": checks,
            "agent_checks": todo}


def ado_checks(cfg: dict, add):
    """Check the Azure DevOps setup: az and its extension, the project, the work item type and its states.

    Also checks that the approval state is not the one new work items start in.

    Args:
        add: setup_check's callback, add(name, ok, detail), that records one check.
    """
    a = cfg["ado"]
    r = _run(["az", "extension", "show", "--name", "azure-devops", "-o", "json"])
    if r is None:
        return add("az installed", False, "install the Azure CLI (" + install_hint("az") + ")")
    add("azure-devops extension", r.returncode == 0,
        "installed" if r.returncode == 0 else "missing: az extension add --name azure-devops")
    if r.returncode != 0:
        return
    try:
        _az(["devops", "project", "show", "--project", a["project"]], cfg)
        add("project readable", True, f"{a['project']} in {ado_org_url(cfg)}")
    except SpecError as e:
        return add("project readable", False, f"{e} (sign in with az login, or set AZURE_DEVOPS_EXT_PAT)")
    kind = a.get("work_item_type") or ADO_DEFAULT_TYPE
    try:
        got = _ado_invoke(cfg, "workItemTypeStates", {"project": a["project"], "type": kind}).get("value") or []
    except SpecError as e:
        return add(f"work item type '{kind}'", False, f"{e}; set ado.work_item_type to one the process has")
    names = {st.get("name", "").casefold(): st for st in got}
    add(f"work item type '{kind}'", bool(got), f"states: {', '.join(st.get('name', '') for st in got)}")
    for status in frozen_statuses(cfg):
        add(f"state '{status}'", status.casefold() in names, "exists" if status.casefold() in names else
            f"not a state of {kind}")
    first = got[0].get("name", "") if got else ""
    approval = str(cfg["approval"]["status"]).strip()
    bad = approval.casefold() == first.casefold() or \
        (names.get(approval.casefold()) or {}).get("category") == "Proposed"
    add("approval state is not a new item's state", not bad,
        f"{approval} is where new {kind} items start; pick a state items are moved into" if bad else "yes")


# ---------------------------------------------------------------- spec text

def _lf(text: str) -> str:
    """Normalize text to LF line endings and drop a leading byte order mark."""
    return text.lstrip("\ufeff").replace("\r\n", "\n")


def _strip_comments(text: str) -> str:
    """Remove every HTML comment, including multi-line ones."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def split_frontmatter(text: str):
    """(fields, body) of markdown: top-level frontmatter keys to scalar values ({} without any), and the body.

    The body is always a suffix of the LF-normalized text.
    """
    text = _lf(text)
    end = text.find("\n---", 4) if text.startswith("---\n") else -1
    if end == -1:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            fm[k.strip()] = _scalar(_strip_comment(v))
    rest = text[end + 4:]
    return fm, rest[1:] if rest.startswith("\n") else rest


def spec_meta(text: str) -> dict:
    """A markdown spec's frontmatter id, title, status and template, each None when absent."""
    fm, _ = split_frontmatter(text)
    return {k: fm.get(k) for k in ("id", "title", "status", "template")}


def sections(body: str):
    """Every heading outside code fences and the section it opens.

    A section ends at the next heading of the same or a higher level.

    Returns:
        (sections, lines): sections is [(title, level, start, end)], with start the heading's line index and end the
            index after the section, and lines is the body split on LF.
    """
    lines, heads, fence = body.split("\n"), [], False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING_RE.match(line)
        if m:
            heads.append((m.group(2).strip(), len(m.group(1)), i))
    out = [(title, level, start, next((s for _, l, s in heads[n + 1:] if l <= level), len(lines)))
           for n, (title, level, start) in enumerate(heads)]
    return out, lines


def _norm_title(t: str) -> str:
    """Normalize a heading title for comparison: lowercase, no emphasis or escapes, nothing after a colon."""
    t = re.sub(r"[*_`\\]", "", t)
    t = re.sub(r"\s*:.*$", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def section(body: str, title: str):
    """(level, start, end, lines) of the first section with this title, or None."""
    secs, lines = sections(body)
    want = _norm_title(title)
    return next(((lvl, st, en, lines) for t, lvl, st, en in secs if _norm_title(t) == want), None)


def section_text(body: str, title: str) -> str | None:
    """The text of the first section with this title, without its heading, or None."""
    hit = section(body, title)
    return None if hit is None else "\n".join(hit[3][hit[1] + 1:hit[2]])


def frozen_part(text: str) -> str:
    """The spec text the freeze covers: the body before the Amendments heading, without frontmatter."""
    _, body = split_frontmatter(text)
    hit = section(body, "Amendments")
    return "\n".join(hit[3][:hit[1]]) if hit else body


_SMART = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-",
          "\u00a0": " ", "\u2026": "..."}


def normalize(text: str) -> str:
    """Reduce text to one line of wording that is stable across tracker markdown re-rendering.

    Ignored: list markers, emphasis, heading and blockquote markers, escapes, hard breaks, link syntax, table rules,
    HTML comment markers, smart quotes and whitespace. Kept: every word, digit and operator, ~~strikethrough~~,
    task-box state, table cells and link targets.
    """
    text = _lf(text).replace("<!--", " ").replace("-->", " ")
    for a, b in _SMART.items():
        text = text.replace(a, b)
    out = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("```"):
            continue
        s = re.sub(r"\\$", "", s)                                    # hard break
        s = re.sub(r"^(?:>\s*)+", "", s)                              # blockquote
        s = re.sub(r"^#{1,6}\s+", "", s)                              # heading
        s = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", s)                   # list marker
        s = re.sub(r"^\\?\[([ xX])\\?\]\s+", lambda m: "[x] " if m.group(1) in "xX" else "[ ] ", s)
        s = re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", s)                  # escapes
        s = re.sub(r"(!?)\[([^\]]*)\]\(([^)\s]*)[^)]*\)", _link, s)  # [text](url)
        s = re.sub(r"<(https?://[^>\s]+)>", r"\1", s)                 # <autolink>
        if RULE_RE.fullmatch(s) or re.fullmatch(r"-{3,}|\*{3,}", s):
            continue                                                  # table rule / hr
        s = re.sub(r"(?<!~)~(?!~)", " ", s)
        s = re.sub(r"[*_`]", " ", s)
        out.append(re.sub(r"\s*\|\s*", " | ", s).strip(" |"))
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def _link(m) -> str:
    """A markdown link in normal form: the label alone when the url is empty or repeats it, else 'label (url)'."""
    bang, label, url = m.group(1), m.group(2), m.group(3)
    if not url or url == label or url.rstrip("/").endswith("/" + label):
        return label
    return f"{bang}{label} ({url})"


def fingerprint(text: str) -> str:
    """The first 12 hex characters of the SHA-256 of the normalized frozen part."""
    return hashlib.sha256(normalize(frozen_part(text)).encode("utf-8")).hexdigest()[:12]


def _cells(line: str) -> list:
    """The stripped cells of a markdown table row. An escaped pipe does not split a cell."""
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def parse_criteria(text: str):
    """Parse the numbered criteria from the Acceptance criteria section.

    Criteria may be bullets, numbered items, headings, task boxes or table rows, and several may share one line.
    Lines inside code fences and HTML comments are skipped.

    Returns:
        [{id, tag, text, gwt}] in order, where tag is the bracketed repo or None and gwt says whether the text has
            Given, When and Then. None when there is no Acceptance criteria section.
    """
    body = section_text(split_frontmatter(text)[1], "Acceptance criteria")
    if body is None:
        return None
    crit, cur, fence = [], None, False
    for raw in body.split("\n"):
        if raw.strip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        parts = [raw] if raw.strip().startswith("|") else [p for p in AC_SPLIT_RE.split(raw) if p.strip()] or [raw]
        for line in parts:
            s = line.strip()
            if s.startswith("|"):
                cells = _cells(s)
                m = re.match("^" + AC_LABEL + "$", cells[0])
                if m:
                    cur = {"id": m.group(1), "tag": m.group(2), "text": " ".join(c for c in cells[1:] if c)}
                    crit.append(cur)
                continue
            m = AC_RE.match(line)
            if m:
                cur = {"id": m.group(1), "tag": m.group(2), "text": m.group(3).strip()}
                crit.append(cur)
            elif HEADING_RE.match(line):
                cur = None
            elif cur is not None and s and not s.startswith("<!--"):
                cur["text"] = (cur["text"] + " " + s).strip()
    for c in crit:
        t = re.sub(r"\s+", " ", re.sub(r"\*\*|\\(?=[^\w\s])", "", c["text"])).strip(" *")
        c["text"] = re.sub(r"\s+(?:[-*+]|\[[ xX]\])(?:\s+\[[ xX]\])?$", "", t)
        c["gwt"] = {"given", "when", "then"} <= set(re.findall(r"[a-z]+", c["text"].lower()))
    return crit


def parse_amendments(text: str):
    """Parse the dated amendments from the Amendments section.

    An indented line continues the amendment above it. HTML comments are skipped.

    Returns:
        (amendments, bad): [{date, criteria, text}] and the non-blank lines that are not amendments. (None, [])
            when there is no Amendments section.
    """
    body = section_text(split_frontmatter(text)[1], "Amendments")
    if body is None:
        return None, []
    good, bad, in_comment = [], [], False
    for line in body.split("\n"):
        s = line.strip()
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            continue
        m = AMEND_RE.match(line)
        if m:
            good.append({"date": m.group(1), "criteria": m.group(2), "text": m.group(3).strip()})
        elif s and line[:1].isspace() and good:
            good[-1]["text"] += " " + s
        elif s:
            bad.append(s)
    return good, bad


def structure_errors(body: str) -> list:
    """Errors unless Acceptance criteria and Amendments exist and only a Closing note follows Amendments."""
    errors = [f"missing section: {s}" for s in ("Acceptance criteria", "Amendments") if not section(body, s)]
    hit = section(body, "Amendments")
    if hit:
        errors += [f"section '{t}' comes after Amendments; Amendments must be last (only a Closing note may follow it)"
                   for t, lvl, st, _ in sections(body)[0]
                   if st > hit[1] and lvl <= hit[0] and _norm_title(t) != "closing note"]
    return errors


def _without_code(text: str) -> str:
    """Drop fenced code blocks and inline code spans."""
    kept, fence = [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            kept.append(re.sub(r"`[^`]*`", "", line))
    return "\n".join(kept)


def _for_placeholder_scan(text: str) -> str:
    """Drop comments, code and <each ...> markers before a placeholder scan."""
    return re.sub(r"<each\b[^>]*>", "", _without_code(_strip_comments(text)))


def _loose_placeholders(body: str) -> list:
    """Placeholder hits in level-2 sections above Amendments, except Acceptance criteria."""
    secs, lines = sections(body)
    amend = section(body, "Amendments")
    found = []
    for title, level, st, en in secs:
        if level == 2 and st < (amend[1] if amend else len(lines)) and _norm_title(title) != "acceptance criteria":
            visible = _for_placeholder_scan("\n".join(lines[st + 1:en]))
            found += [f"placeholder {hit} left in section: {title}" for hit in PLACEHOLDER_RE.findall(visible)]
    return found


def _relative_url(url: str) -> bool:
    """Whether an image destination is a path relative to the spec file, not an absolute or remote URL."""
    return not re.match(r"[A-Za-z][A-Za-z0-9+.-]*://", url) and not os.path.isabs(url)


def _image_urls(text: str) -> list:
    """The destinations of Markdown images in text, in order."""
    return re.findall(r"!\[[^\]]*\]\(([^)\s]+)", text)


def _published_image_errors(text: str, source: str | None, spec_path: str | None) -> list:
    """Local tracker image urls, or relative markdown image paths that are not beside the spec file."""
    if source in ("github", "jira", "linear", "ado"):
        visible = _without_code(frozen_part(text))
        return [f"image not uploaded: {url}" for url in _image_urls(visible)
                if not url.startswith(("http://", "https://"))]
    if source != "markdown" or not spec_path:
        return []
    folder = os.path.dirname(os.path.abspath(spec_path))
    return [f"image not found: {url}" for url in _image_urls(text)
            if _relative_url(url) and not os.path.isfile(os.path.join(folder, url))]


def lint(text: str, approved: bool = False, published: bool = False, source: str | None = None,
         spec_path: str | None = None) -> dict:
    """Check a spec's sections, criteria, amendments, mockup slides and placeholders.

    Args:
        approved: Report the slide-image, loose-placeholder and published-image checks as warnings.
        published: Also check that tracker images are uploaded, or markdown image files exist.
        source: The config's source. Used only when published is set.
        spec_path: The spec file. Markdown image paths resolve against its folder.

    Returns:
        {template, errors, warnings, criteria (the ids), amendments (the count), fingerprint, ok}.
    """
    _, body = split_frontmatter(text)
    errors, warnings = structure_errors(body), []
    crit = parse_criteria(text)
    amends, bad = parse_amendments(text)
    ids = [c["id"] for c in crit or []]
    if crit == []:
        errors.append("Acceptance criteria has no numbered criteria (AC1, AC2, ...)")
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        errors.append("duplicate criterion ids: " + ", ".join(dupes))
    for c in crit or []:
        if not c["gwt"]:
            warnings.append(f"{c['id']} is not written as Given/When/Then")
        quoted = re.sub(r"`[^`]*`", "", c["text"])
        if PLACEHOLDER_RE.search(quoted) or re.search(r"\bTODO\b|FILL", c["text"]):
            errors.append(f"{c['id']} still has a template placeholder")
    errors += [f"amendment not in '- YYYY-MM-DD ACn: text' form: {b[:80]}" for b in bad]
    errors += [f"amendment {a['date']} cites {cid}, which is not a criterion"
               for a in amends or [] for cid in re.findall(r"AC\d+", a["criteria"]) if cid not in ids]
    secs, lines = sections(body)
    for title, level, st, en in secs:
        if level == 2 and _norm_title(title) not in ("amendments", "closing note") \
                and not _strip_comments("\n".join(lines[st + 1:en])).strip():
            warnings.append(f"section is empty: {title} (write 'None' if that is intended)")
    fresh = [f"Slide {s['n']} has no image" for s in mockup_slides(text) if not s["image"]]
    fresh += _loose_placeholders(body)
    if published:
        fresh += _published_image_errors(text, source, spec_path)
    (warnings if approved else errors).extend(fresh)
    return {"template": spec_meta(text)["template"], "errors": errors, "warnings": warnings, "criteria": ids,
            "amendments": len(amends or []), "fingerprint": fingerprint(text), "ok": not errors}


def insert_amendment(text: str, criteria: str, note: str, by: str | None, date: str | None = None) -> str:
    """Add a dated amendment to a spec's Amendments section.

    Creates the section, before any Closing note, when it is missing. Drops the template's
    'Added after approval only' comment. Keeps the text's CRLF line endings if it has them.

    Args:
        criteria: Comma-separated criterion ids such as 'AC1,AC3', or 'general'.
        by: Who gave the answer, added as '(answered by ...)', or None.
        date: YYYY-MM-DD. Defaults to today.

    Raises:
        SpecError: When a cited criterion is not in the spec, or the note is empty.
    """
    crlf = "\r\n" in text
    raw = _lf(text)
    ids = [c["id"] for c in parse_criteria(raw) or []]
    criteria = re.sub(r"\s+", "", criteria)
    if criteria != "general":
        for cid in criteria.split(","):
            if cid not in ids:
                raise SpecError(f"{cid} is not a criterion in this spec ({', '.join(ids) or 'none'})")
        criteria = ", ".join(criteria.split(","))
    note = " ".join(note.split())
    if not note:
        raise SpecError("amendment text is empty")
    line = f"- {date or _dt.date.today().isoformat()} {criteria}: {note}" + (f" (answered by {by})" if by else "")
    _, body = split_frontmatter(raw)
    head, lines = raw[:len(raw) - len(body)], body.split("\n")
    hit = section(body, "Amendments")
    if hit:
        _, start, end, _ = hit
        kept, in_comment = [], False
        for l in lines[start + 1:end]:
            if in_comment or l.strip().startswith("<!-- Added after approval only"):
                in_comment = "-->" not in l
                continue
            kept.append(l)
        while kept and not kept[-1].strip():
            kept.pop()
        while kept and not kept[0].strip():
            kept.pop(0)
        new = lines[:start + 1] + [""] + kept + [line, ""] + lines[end:]
    else:
        closing = section(body, "Closing note")
        at = closing[1] if closing else len(lines)
        before = lines[:at]
        while before and not before[-1].strip():
            before.pop()
        new = before + ["", "## Amendments", "", line, ""] + lines[at:]
    out = head + "\n".join(new).rstrip("\n") + "\n"
    return out.replace("\n", "\r\n") if crlf else out


def amended(text: str, criteria: str, note: str, by: str | None, date: str | None = None) -> str:
    """insert_amendment, raising SpecError when the result would change the frozen text."""
    new = insert_amendment(text, criteria, note, by, date)
    if fingerprint(new) != fingerprint(text):
        raise SpecError("refusing to write: the amendment would change the frozen text")
    return new


def freeze_record(fp: str, status: str, approved_at: str | None) -> str:
    """The freeze record line, stamped with the current UTC time. approved_at None means unknown."""
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    return f'{FREEZE_TAG} · fingerprint {fp} · status "{status}" · approved {approved_at or "unknown"} · {ts}'


def find_freeze_records(text: str) -> list:
    """[{fingerprint, status, approved, at}] for each freeze record in text, None for missing parts."""
    return [{"fingerprint": m.group(1), "status": m.group(2), "approved": m.group(3), "at": m.group(4)}
            for m in FREEZE_RE.finditer(text)]


# ---------------------------------------------------------------- freeze state, trackers

def freeze_decision(body: str, status_now, frozen_now: bool, approvals: list, body_edits: list,
                    comments: list, history_complete: bool = True) -> dict:
    """Work out the freeze state of a tracker spec from its history.

    A freeze record counts only for the approval it names or, naming none, if it was posted after the latest
    approval. The earliest counting record is the freeze.

    Args:
        approvals: Timestamps when the spec entered a frozen status from a non-frozen one.
        body_edits: [{at, by}] edits to the description or body.
        comments: [{body, at}].
        history_complete: Whether the history was fetched in full. False adds a warning.

    Returns:
        A dict whose state is not-approved, needs-confirmation, needs-freeze, frozen or changed, with
            fingerprint_now, status_now, latest_approval, freeze_records, frozen_fingerprint, edits_after_approval,
            record_to_post (when one is needed), warnings and a message for the human.
    """
    fp_now = fingerprint(body)
    appr_times = sorted(t for t in (parse_ts(a) for a in approvals) if t)
    latest = appr_times[-1] if appr_times else None
    records = [dict(r, comment_at=c.get("at")) for c in comments for r in find_freeze_records(c.get("body") or "")]
    out = {"state": None, "fingerprint_now": fp_now, "status_now": status_now,
           "latest_approval": fmt_ts(latest) if latest else None, "freeze_records": records,
           "frozen_fingerprint": None, "edits_after_approval": [], "record_to_post": None, "warnings": [],
           "message": ""}
    if not history_complete:
        out["warnings"].append("history is incomplete (paged or unavailable); approval and edit times may be missing")
    if not frozen_now:
        out.update(state="not-approved", message="The spec is not in an approved status. Nothing is frozen.")
        return out
    rec_time = lambda r: parse_ts(r.get("comment_at")) or parse_ts(r.get("at"))

    def counts(r):
        """A record counts only for the approval it names, or, naming none, if it was posted after it."""
        approved = parse_ts(r.get("approved"))
        if approved:
            return abs((approved - latest).total_seconds()) < 1
        return rec_time(r) is None or rec_time(r) >= latest

    valid = [r for r in records if counts(r)] if latest else list(records)
    if not latest:
        out["warnings"].append("no approval time found in the history, so re-approval cannot be detected: the "
                               "earliest freeze record counts. To re-approve, a human deletes the old freeze record.")
    valid.sort(key=lambda r: rec_time(r) or _dt.datetime.max.replace(tzinfo=_dt.timezone.utc))
    if not valid:
        edits = [{"at": fmt_ts(t), "by": e.get("by")} for e in body_edits
                 for t in [parse_ts(e.get("at"))] if latest and t and t > latest]
        out["edits_after_approval"] = edits
        out["record_to_post"] = freeze_record(fp_now, str(status_now), fmt_ts(latest) if latest else None)
        confirmed = latest and any(re.search(r"confirmed as approved", a["text"], re.I) and a["date"] >= fmt_ts(latest)[:10]
                                   for a in parse_amendments(body)[0] or [])
        if edits and not confirmed:
            out.update(state="needs-confirmation", message=(
                "The body was edited after approval and before the first freeze record. A human confirms the current "
                "text is what they approved (a 'general' amendment), or re-approves. Then post record_to_post."))
        else:
            out.update(state="needs-freeze", message="Approved with no freeze record yet. Post record_to_post.")
        return out
    out["frozen_fingerprint"] = valid[0]["fingerprint"]
    if valid[0]["fingerprint"] == fp_now:
        out.update(state="frozen", message="Frozen, and unchanged since freeze.")
    else:
        out.update(state="changed", message=(
            "The frozen text changed after freeze. An amendment cannot absorb this: a human reverts the edit, or "
            "re-approves (moves the spec out of the approved status and back), which freezes the edited text."))
    return out


def jira_events(issue: dict, cfg: dict) -> dict:
    """Freeze events from a saved getJiraIssue response, in the shape decide takes.

    The response must be fetched with fields description, status and comment, the changelog expanded, and
    responseContentFormat 'markdown'. A search response is accepted and its first issue used.

    Raises:
        SpecError: When the response has no issue, or the description is not markdown.
    """
    if "issues" in issue:
        nodes = issue["issues"].get("nodes") or []
        if not nodes:
            raise SpecError("the saved Jira response has no issue")
        issue = nodes[0]
    fields = issue.get("fields") or {}
    body = fields.get("description")
    if not isinstance(body, str):
        raise SpecError("description is not markdown: fetch with responseContentFormat 'markdown'")
    status = (fields.get("status") or {}).get("name")
    cblock, cl = fields.get("comment") or {}, issue.get("changelog")
    comments = [{"body": c.get("body") if isinstance(c.get("body"), str) else json.dumps(c.get("body")),
                 "at": c.get("created")} for c in cblock.get("comments") or []]
    histories = (cl or {}).get("histories") or []
    complete = cl is not None and (cl.get("total") or 0) <= len(histories) \
        and (cblock.get("total") or 0) <= len(cblock.get("comments") or [])
    approvals, edits = [], []
    for h in histories:
        for it in h.get("items") or []:
            if it.get("field") == "status" and is_frozen_status(it.get("toString"), cfg) \
                    and not is_frozen_status(it.get("fromString"), cfg):
                approvals.append(h.get("created"))
            elif it.get("field") == "description":
                edits.append({"at": h.get("created"), "by": (h.get("author") or {}).get("displayName")})
    return {"body": body, "status_now": status, "approvals": approvals, "body_edits": edits,
            "comments": comments, "history_complete": complete, "id": issue.get("key"), "url": issue.get("webUrl")}


def generic_events(data: dict) -> dict:
    """Events from a saved events JSON for any tracker: {body, status, approvals[], body_edits[], comments[]}.

    Only body is required.
    """
    if "body" not in data:
        raise SpecError("events JSON needs 'body'")
    return {"body": data["body"], "status_now": data.get("status"), "approvals": data.get("approvals") or [],
            "body_edits": data.get("body_edits") or [], "comments": data.get("comments") or [],
            "history_complete": bool(data.get("history_complete", True)), "id": data.get("id"), "url": data.get("url")}


def decide(ev: dict, cfg: dict) -> dict:
    """A tracker spec's freeze state from its events, plus id, url, title, criteria, amendments and body_edits.

    A list status_now is a set of GitHub labels, and the record names the frozen one.
    """
    status = ev["status_now"]
    frozen_now = is_frozen_status(status, cfg)
    if isinstance(status, list):          # GitHub labels: the record names the frozen one
        status = next((l for l in status if is_frozen_status(l, cfg)), "")
    res = freeze_decision(ev["body"], status, frozen_now, ev["approvals"], ev["body_edits"], ev["comments"],
                          ev.get("history_complete", True))
    lint_res = lint(ev["body"])
    res.update({"id": ev.get("id"), "url": ev.get("url"), "title": ev.get("title"), "criteria": lint_res["criteria"],
                "amendments": lint_res["amendments"], "body_edits": ev["body_edits"]})
    return res


# ---------------------------------------------------------------- freeze state, markdown

def _file_history(root: str, rel: str) -> list:
    """[(sha, commit date, path at that commit)] for a file, oldest first, following renames."""
    r = _git(["log", "--follow", "--topo-order", "--format=%x00%H %cI", "--name-only", "--", rel], root)
    out = []
    for chunk in r.stdout.split("\x00"):
        if chunk.strip():
            head, *rest = chunk.strip().split("\n")
            sha, when = head.split(" ", 1)
            paths = [p for p in rest if p.strip()]
            out.append((sha, when, paths[-1] if paths else rel))
    return out[::-1]


def md_status(path: str, cfg: dict) -> dict:
    """Work out a markdown spec's freeze state from its git history.

    The approving commit is the latest one that moved the frontmatter status into a frozen value from a
    non-frozen one.

    Returns:
        A dict whose state is not-approved, needs-freeze, frozen or changed, with path, status, template, frozen,
            uncommitted_changes, fingerprint_now, approval (commit, path and fingerprint), frozen_fingerprint,
            branch, diff (the last 6000 characters, when changed), warnings and a message.

    Raises:
        SpecError: When the file is not in a git repo.
    """
    path = os.path.realpath(path)
    root = git_root(os.path.dirname(path))
    if not root:
        raise SpecError(f"{path} is not in a git repo")
    rel = os.path.relpath(path, root)
    with open(path, encoding="utf-8") as f:
        now_text = f.read()
    history = _file_history(root, rel)
    approving, prev_frozen = None, False
    for sha, when, p in history:
        shown = _git(["show", f"{sha}:{p}"], root)
        frozen = shown.returncode == 0 and is_frozen_status(spec_meta(shown.stdout)["status"], cfg)
        if frozen and not prev_frozen:
            approving = {"commit": sha, "date": when, "path": p, "fingerprint": fingerprint(shown.stdout),
                         "created_approved": sha == history[0][0]}
        if not frozen:
            approving = None
        prev_frozen = frozen
    fp_now, status_now = fingerprint(now_text), spec_meta(now_text)["status"]
    out = {"path": rel, "status": status_now, "template": spec_meta(now_text)["template"], "state": None,
           "frozen": False, "uncommitted_changes": bool(_git(["status", "--porcelain", "--", rel], root).stdout.strip()),
           "fingerprint_now": fp_now, "approval": approving,
           "frozen_fingerprint": approving["fingerprint"] if approving else None,
           "branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], root).stdout.strip(),
           "diff": None, "warnings": [], "message": ""}
    if not is_frozen_status(status_now, cfg):
        out.update(state="not-approved", message=f"status is {status_now!r}, not an approved value on this branch.")
    elif approving is None:
        out.update(state="needs-freeze", message=f"status is {status_now!r} but no commit has it yet. "
                                                 "Commit the approval to freeze the spec.")
    else:
        out["frozen"] = True
        if approving["created_approved"]:
            out["warnings"].append("the file was created already approved (a squash merge, or no draft history), so "
                                   "this commit cannot show what was approved. Compare against the fingerprint in "
                                   "the PR's latest verdict, or re-approve.")
        if fp_now == approving["fingerprint"]:
            out.update(state="frozen", message="Frozen, and unchanged since freeze.")
        else:
            out.update(state="changed", diff=_git(["diff", approving["commit"], "--", rel], root).stdout[-6000:],
                       message="The frozen text changed after the approving commit. An amendment cannot absorb this: "
                               "a human reverts the edit, or re-approves (commits status: draft, then the approved "
                               "value), which freezes the edited text.")
    return out


def md_next_id(cfg: dict) -> str:
    """The next unused markdown spec id, such as SPEC-4, one past the highest in the specs folder."""
    md = cfg.get("markdown") or {}
    prefix = md.get("id_prefix") or "SPEC"
    d = os.path.join(cfg["_root"], md.get("dir") or "specs")
    nums = [int(m.group(1)) for n in (os.listdir(d) if os.path.isdir(d) else [])
            for m in [re.match(re.escape(prefix) + r"-(\d+)\b", n)] if m]
    return f"{prefix}-{max(nums, default=0) + 1}"


# ---------------------------------------------------------------- freeze state, github

def _gh(args, stdin: str | None = None) -> str:
    """Run gh and return its stdout, raising SpecError when gh is missing or fails."""
    try:
        r = _proc(["gh"] + args, input=stdin)
    except FileNotFoundError:
        raise SpecError("gh is not installed: " + install_hint("gh"))
    if r.returncode != 0:
        raise SpecError("gh " + " ".join(args[:3]) + " failed: " + (r.stderr.strip() or r.stdout.strip()))
    return r.stdout


def gh_events(repo: str, number: str, cfg: dict) -> dict:
    """The freeze events of a GitHub issue, read through gh, in the shape decide takes.

    Labels stand in for statuses: an approval is the moment the issue's labels first became frozen. Body edits come
    from the GraphQL userContentEdits, which the REST timeline does not expose.
    """
    issue = json.loads(_gh(["api", f"repos/{repo}/issues/{number}"]))
    labels = [l["name"] for l in issue.get("labels") or []]
    pages = json.loads(_gh(["api", f"repos/{repo}/issues/{number}/timeline?per_page=100", "--paginate", "--slurp"]))
    approvals, comments, current = [], [], set()
    for ev in (e for page in pages for e in (page if isinstance(page, list) else [page])):
        kind = ev.get("event")
        if kind in ("labeled", "unlabeled"):
            before = is_frozen_status(sorted(current), cfg)
            (current.add if kind == "labeled" else current.discard)((ev.get("label") or {}).get("name", ""))
            if not before and is_frozen_status(sorted(current), cfg):
                approvals.append(ev.get("created_at"))
        elif kind == "commented":
            comments.append({"body": ev.get("body") or "", "at": ev.get("created_at")})
    owner, name = repo.split("/", 1)
    q = ("query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n){issue(number:$i)"
         "{userContentEdits(first:100){totalCount nodes{editedAt editor{login}}}}}}")
    uce = json.loads(_gh(["api", "graphql", "-f", f"query={q}", "-F", f"o={owner}", "-F", f"n={name}",
                          "-F", f"i={number}"]))["data"]["repository"]["issue"]["userContentEdits"]
    created = parse_ts(issue.get("created_at"))
    edits = [{"at": n["editedAt"], "by": (n.get("editor") or {}).get("login")} for n in uce["nodes"]
             if not created or (parse_ts(n["editedAt"]) or created) > created]
    return {"body": issue.get("body") or "", "status_now": labels, "approvals": approvals, "body_edits": edits,
            "comments": comments, "history_complete": uce.get("totalCount", 0) <= len(uce["nodes"]),
            "id": f"{repo}#{number}", "url": issue.get("html_url"), "title": issue.get("title")}


def gh_amend(repo: str, number: str, cfg: dict, criterion: str, note: str, by: str | None) -> dict:
    """Add a dated amendment to a GitHub issue body.

    Returns:
        {written ('owner/name#N'), fingerprint (of the body read back), unchanged (whether it matches the one before)}.

    Raises:
        SpecError: When the frozen text already changed, the amendment would change it, or the body changed while
            amending.
    """
    ev = gh_events(repo, number, cfg)
    if decide(ev, cfg)["state"] == "changed":
        raise SpecError("the frozen text changed since freeze; resolve that before amending")
    before = ev["body"]
    new = amended(before, criterion, note, by)
    read_body = lambda: json.loads(_gh(["api", f"repos/{repo}/issues/{number}"])).get("body") or ""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(new)
    try:
        if read_body() != before:
            raise SpecError("the issue body changed while amending; re-read and try again")
        _gh(["issue", "edit", str(number), "--repo", repo, "--body-file", f.name])
    finally:
        os.unlink(f.name)
    back = fingerprint(read_body())
    return {"written": f"{repo}#{number}", "fingerprint": back, "unchanged": back == fingerprint(before)}


# ---------------------------------------------------------------- freeze state, ado
#
# Azure DevOps Services through the az CLI and its azure-devops extension. az boards cannot write Markdown, so
# every description write is a raw JSON patch through az devops invoke that also sets the field's format.

ADO_MD_OP = {"op": "add", "path": "/multilineFieldsFormat/System.Description", "value": "Markdown"}
ADO_PAGE = 200
ADO_ITEM_API = "7.2-preview.3"          # the first version whose work items report multilineFieldsFormat
ADO_COMMENT_API = "7.2-preview"         # Markdown comments (format=0); invoke cannot pass a resource version
ADO_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"  # the Azure DevOps app id, for az rest's AAD token


def ado_number(target) -> str:
    """The digits of a work item id given as 1234, #1234 or AB#1234, raising SpecError otherwise."""
    m = re.fullmatch(r"\s*(?:AB)?#?(\d{1,9})\s*", str(target or ""), re.I)
    if not m:
        raise SpecError(f"not an Azure DevOps work item id: {target!r} (use 1234, #1234 or AB#1234)")
    return m.group(1)


def ado_org_url(cfg: dict) -> str:
    """The organization URL for az's --org: https://dev.azure.com/<org>."""
    return "https://dev.azure.com/" + cfg["ado"]["org"]


def _az(args, cfg: dict, org: bool = True) -> dict:
    """Run az and parse its JSON output ({} when empty), raising SpecError when az is missing or fails."""
    try:
        r = _proc(["az"] + args + (["--org", ado_org_url(cfg)] if org else []) + ["-o", "json"])
    except FileNotFoundError:
        raise SpecError("az is not installed: " + install_hint("az") + ", then az extension add --name azure-devops")
    if r.returncode != 0:
        raise SpecError("az " + " ".join(args[:3]) + " failed: " + (r.stderr.strip() or r.stdout.strip())[:400])
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _ado_invoke(cfg: dict, resource: str, route: dict, query: dict | None = None, method: str | None = None,
                body=None, api: str = "7.1", media: str | None = None) -> dict:
    """Call a work item tracking REST resource through az devops invoke, passing any body through a temp file."""
    args = ["devops", "invoke", "--area", "wit", "--resource", resource, "--api-version", api,
            "--route-parameters"] + [f"{k}={v}" for k, v in route.items()]
    if query:
        args += ["--query-parameters"] + [f"{k}={v}" for k, v in query.items()]
    if method:
        args += ["--http-method", method]
    if media:
        args += ["--media-type", media]
    if body is None:
        return _az(args, cfg)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(body, f)
    try:
        return _az(args + ["--in-file", f.name], cfg)
    finally:
        os.unlink(f.name)


def _ado_rest(cfg: dict, n: str, query: dict | None = None, method: str = "GET", body=None) -> dict:
    """Call one work item by id through az rest. n is the id, or '$<type>' to create one.

    az devops invoke cannot reach it: for the workitems resource it picks the create route, which needs {type}, and it
    cannot pass a resource version such as 7.2-preview.3. With AZURE_DEVOPS_EXT_PAT set, the PAT is sent as basic auth;
    otherwise az supplies an AAD token for the Azure DevOps app.
    """
    url = (f"{ado_org_url(cfg)}/{urllib.parse.quote(str(cfg['ado']['project']))}/_apis/wit/workitems/{n}?"
           + urllib.parse.urlencode(dict(query or {}, **{"api-version": ADO_ITEM_API})))
    headers = {"Content-Type": "application/json-patch+json"} if body is not None else {}
    pat = os.environ.get("AZURE_DEVOPS_EXT_PAT")
    if pat:
        headers["Authorization"] = "Basic " + base64.b64encode((":" + pat).encode()).decode()
    args = ["rest", "--method", method, "--uri", url]
    args += ["--skip-authorization-header"] if pat else ["--resource", ADO_RESOURCE]
    files = []
    try:
        for flag, data in (("--headers", headers), ("--body", body)):
            if data is None or data == {}:
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
                json.dump(data, f)
            files.append(f.name)
            args += [flag, "@" + f.name]
        return _az(args, cfg, org=False)
    finally:
        for name in files:
            os.unlink(name)


def ado_item(cfg: dict, n: str) -> dict:
    """One work item with all its fields, relations and links, as the REST API returns it."""
    return _ado_rest(cfg, n, {"$expand": "all"})


def ado_body(item: dict) -> str:
    """The Description as Markdown, or '' when empty.

    Azure DevOps may hand Markdown back with HTML entities escaped, so they are unescaped.
    """
    return html.unescape((item.get("fields") or {}).get("System.Description") or "")


def ado_fetch(cfg: dict, n: str) -> tuple:
    """(item, updates, {comments, totalCount}) for a work item, following every page.

    ado_events compares totalCount with the comments read to tell whether paging finished.
    """
    project = cfg["ado"]["project"]
    item = ado_item(cfg, n)
    updates, skip = [], 0
    while True:
        page = _ado_invoke(cfg, "updates", {"project": project, "id": n}, {"$top": ADO_PAGE, "$skip": skip})
        got = page.get("value") or []
        updates += got
        if len(got) < ADO_PAGE:
            break
        skip += len(got)
    comments, total, token = [], 0, None
    for _ in range(100):
        query = {"$top": ADO_PAGE}
        if token:
            query["continuationToken"] = token
        page = _ado_invoke(cfg, "comments", {"project": project, "workItemId": n}, query, api=ADO_COMMENT_API)
        comments += page.get("comments") or []
        total, token = page.get("totalCount") or 0, page.get("continuationToken")
        if not token:
            break
    return item, updates, {"comments": comments, "totalCount": total}


def _ado_markdown(item: dict) -> bool:
    """Whether multilineFieldsFormat marks the Description as Markdown."""
    fmt = {k.casefold(): str(v).casefold() for k, v in (item.get("multilineFieldsFormat") or {}).items()}
    return fmt.get("system.description") == "markdown"


def _ado_html(item: dict) -> bool:
    """Whether the Description is stored as HTML (the default), and so cannot hold a spec."""
    body = ((item.get("fields") or {}).get("System.Description") or "").strip()
    return bool(body) and not _ado_markdown(item)


def _ado_changed(u: dict):
    """When a work item update happened: its System.ChangedDate, else revisedDate."""
    f = u.get("fields") or {}
    return (f.get("System.ChangedDate") or {}).get("newValue") or u.get("revisedDate")


def ado_events(item: dict, updates: list, comments: dict, cfg: dict) -> dict:
    """The freeze events of a work item, in the shape decide takes.

    Raises:
        SpecError: When the Description is HTML, not Markdown.
    """
    fields = item.get("fields") or {}
    body = ado_body(item)
    if _ado_html(item):
        raise SpecError("the work item's Description is HTML, not Markdown: write the spec with "
                        "'ado describe', which converts it (one way)")
    approvals, edits = [], []
    for u in sorted(updates, key=lambda u: u.get("rev") or 0):
        f = u.get("fields") or {}
        st = f.get("System.State")
        if st and is_frozen_status(st.get("newValue"), cfg) and not is_frozen_status(st.get("oldValue"), cfg):
            approvals.append(_ado_changed(u))
        if "System.Description" in f and (u.get("rev") or 0) > 1:
            edits.append({"at": _ado_changed(u), "by": (u.get("revisedBy") or {}).get("displayName")})
    got = [c for c in comments.get("comments") or [] if not c.get("isDeleted")]
    text = lambda c: html.unescape(c.get("text") or "") if str(c.get("format", 0)).casefold() in ("0", "markdown") \
        else html_text(c.get("text") or "")
    n = item.get("id")
    return {"body": body, "status_now": fields.get("System.State"), "approvals": approvals, "body_edits": edits,
            "comments": [{"body": text(c), "at": c.get("createdDate")} for c in got],
            "history_complete": (comments.get("totalCount") or 0) <= len(comments.get("comments") or []),
            "id": f"AB#{n}", "url": ((item.get("_links") or {}).get("html") or {}).get("href"),
            "title": fields.get("System.Title")}


def ado_status(cfg: dict, n: str) -> dict:
    """The freeze state of a work item.

    When the state is changed and an earlier revision matches the frozen fingerprint, it adds diff, a unified diff
    of at most 6000 characters.
    """
    item, updates, comments = ado_fetch(cfg, n)
    res = decide(ado_events(item, updates, comments, cfg), cfg)
    if res["state"] == "changed" and res.get("frozen_fingerprint"):
        bodies = [html.unescape(str(((u.get("fields") or {}).get("System.Description") or {}).get("newValue") or ""))
                  for u in sorted(updates, key=lambda u: u.get("rev") or 0)]
        frozen = next((b for b in reversed(bodies) if fingerprint(b) == res["frozen_fingerprint"]), None)
        if frozen is not None:
            res["diff"] = "".join(difflib.unified_diff(frozen.splitlines(True), ado_body(item).splitlines(True),
                                                       "frozen", "now"))[-6000:]
    return res


def html_text(s: str) -> str:
    """Rough text of an HTML comment, enough to find a freeze record in one."""
    s = re.sub(r"<br\s*/?>|</(?:p|div|li)>", "\n", s, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\u00a0", " ")


def ado_escape(text: str) -> str:
    """Markdown as Azure DevOps's own editor stores it, with &, < and > as entities.

    The server strips anything shaped like an HTML tag, even inside a code span (`<id>` comes back empty), and renders
    the entities as the characters.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ado_set_description(cfg: dict, n: str, text: str, rev) -> dict:
    """Write the Description as Markdown, failing if the work item moved past revision rev.

    A JSON patch test op on the revision makes the server refuse the write when someone edited it since.
    """
    ops = [{"op": "test", "path": "/rev", "value": rev},
           {"op": "replace", "path": "/fields/System.Description", "value": ado_escape(text)}, ADO_MD_OP]
    return _ado_rest(cfg, n, method="PATCH", body=ops)


def ado_edit_url(cfg: dict, n) -> str:
    """The web URL that opens work item n for editing."""
    return f"{ado_org_url(cfg)}/{urllib.parse.quote(str(cfg['ado']['project']))}/_workitems/edit/{n}"


def ado_amend(cfg: dict, n: str, criterion: str, note: str, by: str | None) -> dict:
    """Add a dated amendment to a work item's Description.

    Returns:
        {written ('AB#N'), fingerprint (of the Description read back), unchanged (whether it matches the one before)}.

    Raises:
        SpecError: When the frozen text already changed, or the amendment would change it.
    """
    item, updates, comments = ado_fetch(cfg, n)
    ev = ado_events(item, updates, comments, cfg)
    if decide(ev, cfg)["state"] == "changed":
        raise SpecError("the frozen text changed since freeze; resolve that before amending")
    before = ev["body"]
    new = amended(before, criterion, note, by)
    ado_set_description(cfg, n, new, item.get("rev"))
    back = fingerprint(ado_body(ado_item(cfg, n)))
    return {"written": f"AB#{n}", "fingerprint": back, "unchanged": back == fingerprint(before)}


def ado_describe(cfg: dict, n: str, text: str) -> dict:
    """Set a work item's Description to a spec, as Markdown. An HTML Description is converted, one way.

    Returns:
        {written ('AB#N'), url, converted_from_html, fingerprint (of the Description read back), round_trip (whether
            it matches the text written)}.

    Raises:
        SpecError: When the work item is in a frozen state.
    """
    item = ado_item(cfg, n)
    fields = item.get("fields") or {}
    if is_frozen_status(fields.get("System.State"), cfg):
        raise SpecError(f"AB#{n} is in a frozen state ({fields.get('System.State')}); add an amendment instead")
    was_html = _ado_html(item)
    ado_set_description(cfg, n, text, item.get("rev"))
    back = ado_body(ado_item(cfg, n))
    return {"written": f"AB#{n}", "url": ado_edit_url(cfg, n), "converted_from_html": was_html,
            "fingerprint": fingerprint(back), "round_trip": fingerprint(back) == fingerprint(html.unescape(text))}


def ado_create(cfg: dict, title: str, text: str, kind: str | None) -> dict:
    """Create a work item with a title and a Markdown Description in one call.

    One call means a failure leaves no empty work item behind. kind None uses ado.work_item_type (default
    'User Story'). Returns the same shape as ado_describe.

    Raises:
        SpecError: When the create call returns no id.
    """
    kind = kind or cfg["ado"].get("work_item_type") or ADO_DEFAULT_TYPE
    ops = [{"op": "add", "path": "/fields/System.Title", "value": title},
           {"op": "add", "path": "/fields/System.Description", "value": ado_escape(text)}, ADO_MD_OP]
    made = _ado_rest(cfg, "$" + urllib.parse.quote(kind), method="POST", body=ops)  # one call: no empty item on failure
    n = str(made.get("id") or "")
    if not n:
        raise SpecError("creating the work item returned no id")
    back = ado_body(ado_item(cfg, n))
    return {"written": f"AB#{n}", "url": ado_edit_url(cfg, n), "converted_from_html": False,
            "fingerprint": fingerprint(back), "round_trip": fingerprint(back) == fingerprint(html.unescape(text))}


def ado_comment(cfg: dict, n: str, text: str) -> dict:
    """Post a Markdown comment on a work item and return {commented, comment_id, url}."""
    c = _ado_invoke(cfg, "comments", {"project": cfg["ado"]["project"], "workItemId": n}, {"format": 0},
                    method="POST", body={"text": ado_escape(text)}, api=ADO_COMMENT_API)
    return {"commented": f"AB#{n}", "comment_id": c.get("id"), "url": ado_edit_url(cfg, n)}


# ---------------------------------------------------------------- templates

def template_errors(text: str, stem: str, evidence: bool) -> list:
    """Why a spec or evidence template cannot be used. An empty list means it is usable.

    Args:
        stem: The file name without its extension, which the frontmatter name must match.
    """
    fm, body = split_frontmatter(text)
    if not fm:
        return ["no frontmatter: start the file with ---, a name: line, a description: line, and ---"]
    keys = {"name", "description", "version"} if evidence else {"name", "description"}
    errors = []
    if set(fm) - keys:
        errors.append(f"frontmatter may only have {', '.join(sorted(keys))} (found {', '.join(sorted(set(fm) - keys))})")
    name = fm.get("name")
    if not isinstance(name, str) or not TEMPLATE_NAME_RE.fullmatch(name):
        errors.append("name must be lowercase letters, digits and hyphens, like 'feature' or 'qa-plan'")
    elif name != stem:
        errors.append(f"name '{name}' must match the file name")
    if not isinstance(fm.get("description"), str):
        errors.append("description must be one line saying when to use this template")
    if re.search(r"^# ", body, re.M):
        errors.append("remove the '# ' title heading; dc-specs writes the title")
    if evidence:
        v = fm.get("version")
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            errors.append("version must be a whole number from 1; bump it on every change")
        if "<each criterion>" not in body:
            errors.append("needs a table with an '<each criterion>' row")
    else:
        errors += structure_errors(body)
        if section(body, "Acceptance criteria") and not parse_criteria(body):
            errors.append("Acceptance criteria needs at least one example criterion, like "
                          "'- AC1 Given <state>, when <action>, then <result>.'")
        amends, bad = parse_amendments(body)
        if amends or bad:
            errors.append("Amendments must be empty in a template")
    return errors


def list_templates(cfg: dict, evidence: bool = False) -> dict:
    """The spec or evidence templates this repo can use, by name.

    A repo's own template in its templates folder replaces the plugin's default of the same name. README.md and the
    verdict template are skipped.

    Returns:
        name -> {name, path, source (default or repo), overrides_default, description, version, text, errors}. An
            unreadable file has empty text and the read error in errors.
    """
    repo_dir = os.path.join(cfg["_root"], cfg.get("templates") or "specs/templates")
    suffix = EVIDENCE_SUFFIX if evidence else ".md"
    found = {}
    for source, d in (("default", PLUGIN_TEMPLATES), ("repo", repo_dir)):
        for fname in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            path = os.path.join(d, fname)
            if not fname.endswith(suffix) or not os.path.isfile(path) or fname.lower() == "readme.md" \
                    or (not evidence and fname.endswith(EVIDENCE_SUFFIX)) or path == VERDICT_TEMPLATE:
                continue
            stem = fname[:-len(suffix)]
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                errors = template_errors(text, stem, evidence)
            except (OSError, UnicodeDecodeError) as e:
                text, errors = "", [f"cannot read: {e}"]
            fm, _ = split_frontmatter(text)
            found[stem] = {"name": stem, "path": path, "source": source, "overrides_default": stem in found,
                           "description": fm.get("description"), "version": fm.get("version"), "text": text,
                           "errors": errors}
    return found


def template_list(cfg: dict) -> list:
    """Each spec template with the evidence template it pairs with, repo templates first, for the templates command.

    Returns:
        [{name, description, source, overrides_default, path, valid, errors, evidence}]. evidence is {name, source,
            path, version, paired, valid, errors}, using the fallback evidence template when none shares the name, or
            None when there is neither.
    """
    evidence = list_templates(cfg, evidence=True)
    out = []
    for t in sorted(list_templates(cfg).values(), key=lambda x: (x["source"] != "repo", x["name"])):
        e = evidence.get(t["name"]) or evidence.get(FALLBACK_EVIDENCE)
        out.append({"name": t["name"], "description": t["description"], "source": t["source"],
                    "overrides_default": t["overrides_default"], "path": t["path"], "valid": not t["errors"],
                    "errors": t["errors"], "evidence": e and {
                        "name": e["name"], "source": e["source"], "path": e["path"], "version": e["version"],
                        "paired": e["name"] == t["name"], "valid": not e["errors"], "errors": e["errors"]}})
    return out


def _usable(found: dict, name: str, what: str) -> dict:
    """The template named name from found, raising SpecError when it is missing or has errors."""
    t = found.get(name)
    if t is None:
        raise SpecError(f"no {what} named '{name}'. Available: " + ", ".join(sorted(found)))
    if t["errors"]:
        raise SpecError(f"{what} '{name}' ({t['path']}) cannot be used: " + "; ".join(t["errors"]))
    return t


def render_template(cfg: dict, name: str, title: str, spec_id: str | None) -> str:
    """Render a new spec from a template, with the header for this repo's source.

    A markdown spec gets frontmatter and an `# <id>: <title>` heading. A tracker spec gets only the heading, and the
    template's HTML comments are removed. For markdown, spec_id None takes the next free id.

    Raises:
        SpecError: When the title is empty.
    """
    title = " ".join(str(title).split())
    if not title:
        raise SpecError("title is empty")
    _, body = split_frontmatter(_usable(list_templates(cfg), name, "template")["text"])
    body = body.strip("\n") + "\n"
    if cfg.get("source") == "markdown":
        spec_id = spec_id or md_next_id(cfg)
        return f"---\nid: {spec_id}\ntitle: {title}\ntemplate: {name}\nstatus: draft\n---\n\n# {spec_id}: {title}\n\n" + body
    body = re.sub(r"[ \t]*<!--.*?-->[ \t]*\n?", "", body, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", (f"# {spec_id}: {title}" if spec_id else f"# {title}") + "\n\n" + body)


# ---------------------------------------------------------------- evidence and verdict documents
#
# The PR description (evidence) and the verdict comment are rendered from, and checked against, a template:
# its level-2 sections, in order. A section is free text, or holds one table whose rows are either fixed
# (their first cell names the row) or expand from the spec: '<each criterion>' gives one row per criterion,
# '<each slide>' one per mockup slide, and a per-slide table with no slides is left out. A cell
# '<one of: a, b>' takes one of those values; any other '<...>' is a placeholder to fill; any other text
# must stay as written. A section whose comment says "Only when the spec has a X section" appears only then.

TITLES = {"evidence": "Spec evidence", "verdict": "Spec verdict"}
P_LINK, P_NAME, P_CI, P_FILL = ("<link to the spec>", "<spec id and title>",
                                "<link to the CI run for the head commit>", "<fill in, or None>")
P_RESULT = "<overall>"
RANK = {"confirmed": 0, "waived": 0, "other repo": 0, "unverifiable": 1, "weak": 2, "disputed": 3}
OVERALL = ("confirmed", "unverifiable", "weak", "disputed")
WAIVER_RE = re.compile(r"^\s*[-*+]\s+\**(" + AC_ID + r"|freeze)\**\s*:\s*waived by\s+(.+?)\s+until\s+(\S+)\s+-\s+(.*)$", re.I)
SLIDE_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?\**Slide\s+(\d+)\**\s*[:.)\-]?\**\s*(.*)$", re.I)
IMG_RE = re.compile(r"!\[[^\]]*\]\([^)\s]+[^)]*\)")


def mockup_slides(spec_text: str) -> list:
    """[{n, state, detail, image}] from a spec's mockups section, by slide number, or [] without one.

    Each slide is a line `- Slide N: state - detail`. Its image is the first Markdown image on or after that line, or
    None.
    """
    secs, lines = sections(split_frontmatter(spec_text)[1])
    hit = next(((st, en) for t, _, st, en in secs if _norm_title(t).endswith("mockups")), None)
    if not hit:
        return []
    slides, cur = {}, None
    for line in _strip_comments("\n".join(lines[hit[0] + 1:hit[1]])).split("\n"):
        m = SLIDE_RE.match(line)
        if m:
            parts = [p.strip() for p in re.split(r"\s+-\s+", IMG_RE.sub("", m.group(2)).strip()) if p.strip()]
            cur = slides.setdefault(int(m.group(1)), {"n": int(m.group(1)), "state": parts[0] if parts else "",
                                                      "detail": " - ".join(parts[1:]), "image": None})
        img = IMG_RE.search(line)
        if img and cur and not cur["image"]:          # a slide's image is the first one after its line
            cur["image"] = img.group(0)
    return [slides[k] for k in sorted(slides)]


def spec_heading(spec_text: str) -> tuple:
    """(id, title) from markdown frontmatter or the first # heading, either None when not found.

    A title that starts with `<id>:` has that prefix removed.
    """
    fm, body = split_frontmatter(spec_text)
    sid, title = fm.get("id"), fm.get("title")
    if not title:
        m = re.search(r"^#\s+(.+?)\s*#*\s*$", body, re.M)
        title = m.group(1) if m else None
    if sid and title and str(title).startswith(f"{sid}:"):
        title = str(title)[len(str(sid)) + 1:].strip()
    return (str(sid) if sid else None), (str(title) if title else None)


def _choices(cell: str):
    """The values a `<one of: a, b>` cell allows, or None when the cell is not one."""
    m = re.fullmatch(r"<one of: (.+)>", cell.strip("` "))
    return [x.strip() for x in m.group(1).split(",")] if m else None


def _key(cell: str) -> str:
    """A row's identity: its criterion id, slide number, or normalized first cell."""
    m = re.match(r"\**(AC\d+|\d+)\b", cell)
    return m.group(1) if m else _norm_title(cell)


def _blank(cell: str) -> bool:
    """Whether a cell is empty or just a dash, ignoring Markdown emphasis and code marks."""
    return cell.strip("`*_ ") in ("", "-")


def _table(text: str):
    """(header, rows) of the table in a section, as cell lists, or (None, []) when there is none."""
    rows = [_cells(l) for l in _strip_comments(text).split("\n")
            if l.strip().startswith("|") and not RULE_RE.fullmatch(l.strip())]
    return (rows[0], rows[1:]) if rows else (None, [])


def _md_table(header: list, rows: list) -> list:
    """A Markdown table as lines, with a separator row after the header."""
    return ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(r) + " |" for r in rows]


def _holes(template_text: str) -> set:
    """Every placeholder a document can be left with: the template's and the header's, not `<each ...>` markers."""
    body = _strip_comments(split_frontmatter(template_text)[1]).replace("<each criterion>", "").replace("<each slide>", "")
    return set(PLACEHOLDER_RE.findall(body)) | {P_LINK, P_NAME, P_CI, P_FILL, P_RESULT}


def doc_sections(template_text: str, spec_text: str) -> list:
    """[(title, header, template rows, section text)] for each level-2 section a document has for this spec.

    A section whose text says "only when the spec has a X section" is left out when the spec lacks it, and a
    per-slide table is left out when the spec has no slides. header is None and rows [] for a free-text section.
    """
    secs, lines = sections(split_frontmatter(template_text)[1])
    spec_body, slides = split_frontmatter(spec_text)[1], mockup_slides(spec_text)
    out = []
    for title, level, st, en in secs:
        text = "\n".join(lines[st + 1:en])
        when = re.search(r"only when the spec has an? (.+?) section", text, re.I)
        header, rows = _table(text)
        if level != 2 or (when and not section(spec_body, when.group(1))) \
                or (not slides and any(r[0] == "<each slide>" for r in rows)):
            continue
        out.append((title, header, rows, text))
    return out


def _expand(rows: list, spec_text: str, other=()) -> list:
    """[(key, template row, rendered row)] with `<each criterion>` and `<each slide>` rows expanded from the spec.

    Fixed rows stay as they are. Criteria in `other` are proved in another repo, so their choice cells are prefilled
    with 'other repo' and the rest with '-'.
    """
    out = []
    for r in rows:
        if r[0] == "<each criterion>":
            for c in parse_criteria(spec_text) or []:
                cells = [c["id"] + (f" [{c['tag']}]" if c["tag"] else "")]
                cells += [("other repo" if _choices(x) else "-") for x in r[1:]] if c["id"] in other else r[1:]
                out.append((c["id"], r, cells))
        elif r[0] == "<each slide>":
            for s in mockup_slides(spec_text):
                fill = lambda x: x.replace("<slide mockup>", s["image"] or "<slide mockup>").replace(
                    "<slide detail>", s["detail"].replace("|", "\\|") or "<slide detail>")
                out.append((str(s["n"]), r, [f"{s['n']}. " + s["state"].replace("|", "\\|")] + [fill(x) for x in r[1:]]))
        else:
            out.append((_key(r[0]), r, r))
    return out


def _spec_line(link: str, spec_text: str) -> str:
    """The document's **Spec:** header line, with the spec's fingerprint and amendment count."""
    n = len(parse_amendments(spec_text)[0] or [])
    return f"**Spec:** {link} · frozen at fingerprint `{fingerprint(spec_text)}` · {n} amendment" + ("" if n == 1 else "s")


def render_doc(kind: str, spec_text: str, template_text: str, header: list, spec_id: str | None = None,
               other=(), merge: str | None = None) -> tuple:
    """Render an evidence or verdict document from its template.

    Args:
        header: The header lines that go under the title.
        other: Criterion ids proved in another repo.
        merge: An earlier document whose filled rows and sections replace unfilled new ones.

    Returns:
        (body, carried): the document text, and the row keys and section titles carried from merge.
    """
    sid, title = spec_heading(spec_text)
    holes, old = _holes(template_text), _lf(merge) if merge is not None else None
    filled = lambda text: not any(h in text for h in holes)
    out = [f"## {TITLES[kind]}: " + (" ".join(x for x in (spec_id or sid, title) if x) or P_NAME), ""] + header + [""]
    carried = []
    for stitle, head, rows, text in doc_sections(template_text, spec_text):
        prev = section_text(old, stitle) if old is not None else None
        if rows:
            done = {_key(r[0]): r for r in _table(prev or "")[1] if filled(" ".join(r))}
            new = []
            for key, _, cells in _expand(rows, spec_text, other):
                if key in done and not filled(" ".join(cells)):
                    cells = done[key]
                    carried.append(key)
                new.append(cells)
            lines = _md_table(head, new)
        elif prev and _strip_comments(prev).strip() and filled(prev):
            lines = [_strip_comments(prev).strip("\n")]
            carried.append(stitle)
        else:
            lines = [_strip_comments(text).strip("\n") or P_FILL]
        out += [f"### {stitle}", ""] + lines + [""]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).rstrip("\n") + "\n", carried


def _header_fields(text: str) -> dict:
    """{fingerprint, amendments, template, version, head} from a document's header, None when absent."""
    fp = re.search(r"fingerprint\W+([0-9a-f]{12})\b", text)
    am = re.search(r"fingerprint\W+[0-9a-f]{12}\W+(\d+)\s+amendments?\b", text)
    et = re.search(r"evidence template\W+([a-z0-9][a-z0-9-]*)\W+v(\d+)\b", text, re.I)
    head = re.search(r"head commit\W+([0-9a-f]{7,40})\b", text, re.I)
    return {"fingerprint": fp and fp.group(1), "amendments": am and int(am.group(1)),
            "template": et and et.group(1), "version": et and int(et.group(2)), "head": head and head.group(1).lower()}


def _check_table(title: str, header: list, rows: list, text: str, spec_text: str, repo_tag, errors: list) -> dict:
    """Check one table against its template and the spec, appending problems to errors.

    Checks for missing, unexpected and repeated rows, spec order, cell counts, choice values, blank cells and fixed
    cells, and that "other repo" is used only for criteria tagged with another repo.

    Returns:
        Row key -> the value of its `<one of: ...>` cell, or "other repo".
    """
    want = _expand(rows, spec_text)
    tmpl = {k: r for k, r, _ in want}
    tags = {c["id"]: c["tag"] for c in parse_criteria(spec_text) or []}
    got = _table(text)[1]
    keys, want_keys = [_key(c[0]) for c in got], [k for k, _, _ in want]
    errors += [f"{title}: no row for {k}" for k in want_keys if k not in keys]
    errors += [f"{title}: {k} is not a row it should have" for k in dict.fromkeys(keys) if k not in tmpl]
    errors += [f"{title}: {k} has more than one row" for k in dict.fromkeys(keys) if keys.count(k) > 1]
    common = [k for k in dict.fromkeys(keys) if k in tmpl]
    if common != [k for k in want_keys if k in common]:
        errors.append(f"{title}: rows are not in spec order: " + ", ".join(common))
    values = {}
    for cells in got:
        k, r = _key(cells[0]), tmpl.get(_key(cells[0]))
        if r is None or k in values:
            continue
        if len(cells) != len(r):
            errors.append(f"{title}: the {k} row needs {len(r)} cells")
            continue
        vals = [c.strip("`* ").lower() for c in cells]
        if k in tags and "other repo" in vals:
            values[k] = "other repo"
            if not tags[k]:
                errors.append(f"{k}: 'other repo' is only for criteria tagged with a repo")
            elif repo_tag and tags[k] == repo_tag:
                errors.append(f"{k}: tagged for this repo ({repo_tag}), so it must be verified here")
            continue
        for i in range(1, len(r)):
            choices = _choices(r[i])
            if choices:
                values[k] = vals[i]
                if vals[i] not in choices:
                    errors.append(f"{title}: {k}: {header[i]} must be one of " + ", ".join(choices))
            elif _blank(cells[i]):
                errors.append(f"{title}: {k}: the {header[i]} cell is blank")
            elif not PLACEHOLDER_RE.search(r[i]) and cells[i].strip() != r[i].strip():
                errors.append(f"{title}: {k}: {header[i]} must be {r[i]}")
    return values


def check_doc(kind: str, spec_text: str, body: str, template_text: str, repo_tag=None, frozen=None) -> tuple:
    """Check an evidence or verdict document against its template and the spec.

    Returns:
        (errors, values, fields): the error messages, row key -> choice value from every table, and the header
            fields from _header_fields.
    """
    body = _lf(body)
    f = _header_fields(body)
    errors = [] if re.search(r"^#{1,6}\s+" + TITLES[kind] + r"\b", body, re.M) else \
        [f"missing the '## {TITLES[kind]}: <spec>' heading"]
    fp_now, n = fingerprint(spec_text), len(parse_amendments(spec_text)[0] or [])
    if not f["fingerprint"] or f["amendments"] is None:
        errors.append("the '**Spec:**' header line needs 'frozen at fingerprint `...` · N amendments'")
    else:
        if f["fingerprint"] != fp_now or (frozen and f["fingerprint"] != frozen):
            errors.append(f"it cites fingerprint {f['fingerprint']}; the spec's is {fp_now}"
                          + (f" and the frozen one {frozen}" if frozen else ""))
        if f["amendments"] != n:
            errors.append(f"it says {f['amendments']} amendments; the spec has {n}")
    if not f["template"]:
        errors.append("missing the '**Evidence template:** `name` vN' header line")
    values = {}
    for title, header, rows, text in doc_sections(template_text, spec_text):
        got = section_text(body, title)
        if got is None:
            errors.append(f"missing section: {title}")
        elif rows:
            values.update(_check_table(title, header, rows, got, spec_text, repo_tag, errors))
        elif not _strip_comments(got).strip():
            errors.append(f"section is empty: {title} (write 'None' if that is intended)")
    errors += [f"placeholder left in: {h}" for h in sorted(_holes(template_text)) if h in _strip_comments(body)]
    return errors, values, f


def _column(text: str, name: str) -> dict:
    """Criterion id -> the lowercased value of column `name` in the Criteria table, or {} without one."""
    header, rows = _table(section_text(_lf(text), "Criteria") or "")
    i = next((i for i, h in enumerate(header or []) if h.lower() == name.lower()), None)
    return {} if i is None else {_key(r[0]): r[i].strip("`* ").lower() for r in rows
                                 if len(r) > i and re.fullmatch(r"AC\d+", _key(r[0]))}


def _check_frozen(spec_text: str, frozen: str | None) -> str:
    """The spec's fingerprint, raising SpecError when it differs from frozen (None skips the check)."""
    fp = fingerprint(spec_text)
    if frozen and fp != frozen:
        raise SpecError(f"the spec's fingerprint is {fp}, not the frozen {frozen}: the spec changed since freeze")
    return fp


def infer_template(cfg: dict, spec_text: str) -> tuple:
    """(template name, reason): the spec's frontmatter template, else the one sharing most section titles."""
    named = spec_meta(spec_text)["template"]
    if named:
        return str(named), "the spec's frontmatter names it"
    titles = lambda text: {_norm_title(t) for t, lvl, _, _ in sections(split_frontmatter(text)[1])[0] if lvl == 2}
    have = titles(spec_text)
    best = max(list_templates(cfg).values(), key=lambda t: (len(have & titles(t["text"])), t["name"] == FALLBACK_EVIDENCE))
    return best["name"], f"the spec's sections match the '{best['name']}' template best"


def render_evidence(cfg: dict, spec_text: str, template: str | None = None, spec_id: str | None = None,
                    url: str | None = None, repo_tag: str | None = None, frozen: str | None = None,
                    spec_path: str | None = None, merge: str | None = None) -> dict:
    """Render the PR description: the evidence for each acceptance criterion.

    Args:
        template: The evidence template name. None infers it from the spec, falling back to the default one.
        repo_tag: This repo's tag. Criteria tagged with another repo are prefilled as "other repo".
        spec_path: The markdown spec's path, linked relative to the repo root when there is no url.
        merge: An earlier evidence document to carry filled rows, sections and the CI line from.

    Returns:
        {template, template_reason, version, fingerprint, amendments, carried, body}.

    Raises:
        SpecError: When the spec has no numbered acceptance criteria.
    """
    fp = _check_frozen(spec_text, frozen)
    crit = parse_criteria(spec_text)
    if not crit:
        raise SpecError("the spec has no numbered acceptance criteria")
    found = list_templates(cfg, evidence=True)
    why = "named with --template"
    if not template:
        template, why = infer_template(cfg, spec_text)
        if template not in found:
            template, why = FALLBACK_EVIDENCE, f"{why}, which has no evidence template, so '{FALLBACK_EVIDENCE}'"
    t = _usable(found, template, "evidence template")
    link = url or P_LINK
    if not url and cfg.get("source") == "markdown" and spec_path:
        link = f"`{os.path.relpath(os.path.realpath(spec_path), cfg['_root'])}`"
    ci = re.search(r"^\**CI:?\**\s*(.+)$", _lf(merge or ""), re.I | re.M)
    header = [_spec_line(link, spec_text), f"**Evidence template:** `{t['name']}` v{t['version']}",
              f"**CI:** {ci.group(1).strip() if ci and P_CI not in ci.group(1) else P_CI}"]
    other = {c["id"] for c in crit if c["tag"] and repo_tag and c["tag"] != repo_tag}
    body, carried = render_doc("evidence", spec_text, t["text"], header, spec_id, other, merge)
    return {"template": t["name"], "template_reason": why, "version": t["version"], "fingerprint": fp,
            "amendments": len(parse_amendments(spec_text)[0] or []), "carried": carried, "body": body}


def evidence_check(cfg: dict, spec_text: str, body: str, repo_tag: str | None = None, frozen: str | None = None) -> dict:
    """Check a PR description against its evidence template and the spec.

    Returns:
        {ok, errors, results, counts, frozen_fingerprint, amendments, evidence_template}. results maps each
            criterion id to its result, and counts tallies pass, fail, not verified and other repo.
    """
    f = _header_fields(_lf(body))
    errors, t = [], None
    if f["template"]:
        try:
            t = _usable(list_templates(cfg, evidence=True), f["template"], "evidence template")
        except SpecError as e:
            errors.append(str(e))
    if t and t["version"] != f["version"]:
        errors.append(f"the evidence is from '{t['name']}' v{f['version']}; it is v{t['version']} now: "
                      "run evidence render --merge on it")
    if not re.search(r"^\**CI:?\**\s*\S", _lf(body), re.I | re.M):
        errors.append("missing the '**CI:**' line linking the CI run for the head commit")
    more, values, _ = check_doc("evidence", spec_text, body, t["text"] if t else "", repo_tag, frozen)
    errors += more
    results = {k: v for k, v in values.items() if re.fullmatch(r"AC\d+", k)}
    return {"ok": not errors, "errors": errors, "results": results,
            "counts": {r: list(results.values()).count(r) for r in ("pass", "fail", "not verified", "other repo")},
            "frozen_fingerprint": f["fingerprint"], "amendments": f["amendments"],
            "evidence_template": {"name": f["template"], "version": f["version"]}}


def overall_result(verdicts: list) -> str:
    """The worst verdict: disputed, weak, unverifiable, then confirmed (also for none).

    Waived and other-repo criteria count as confirmed.
    """
    return OVERALL[max([RANK[v] for v in verdicts if v in RANK] or [0])]


def result_line(verdicts: list) -> str:
    """The verdict's **Result:** line: the overall verdict, then a count of each verdict used."""
    overall = overall_result(verdicts)
    keys = ["confirmed", "disputed", "weak", "unverifiable"] + [k for k in ("waived", "other repo") if k in verdicts]
    return f"**Result:** {overall} · " + " · ".join(f"{verdicts.count(k)} {k}" for k in keys)


def _verdict_template() -> str:
    """The text of the plugin's templates/verdict.md."""
    with open(VERDICT_TEMPLATE, encoding="utf-8") as f:
        return f.read()


def render_verdict(cfg: dict, spec_text: str, evidence: str, head: str, url: str | None = None,
                   spec_id: str | None = None, frozen: str | None = None) -> dict:
    """A verdict comment drafted from the spec and the PR description, with each criterion row to fill.

    Args:
        url: A link to the spec. Defaults to the one in the PR description.

    Returns:
        {body, evidence_ok, evidence_errors}, the last two from checking the PR description.

    Raises:
        SpecError: When head is not a full 40-character sha.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", head or ""):
        raise SpecError("--head must be the PR's full 40-character head commit sha (gh pr view --json headRefOid)")
    _check_frozen(spec_text, frozen)
    ev = evidence_check(cfg, spec_text, evidence, frozen=frozen)
    ef = _header_fields(_lf(evidence))
    link = url or (re.search(r"^\**spec:?\**\s*(.+?)\s*·\s*frozen at", _lf(evidence), re.I | re.M) or [None, P_LINK])[1]
    header = [f"**Head commit:** `{head}`", _spec_line(link, spec_text),
              f"**Evidence template:** `{ef['template']}` v{ef['version']}" if ef["template"] else
              "**Evidence template:** none named in the PR description", f"**Result:** {P_RESULT}"]
    other = {k for k, v in _column(evidence, "Result").items() if v == "other repo"}
    body, _ = render_doc("verdict", spec_text, _verdict_template(), header, spec_id, other)
    return {"body": body, "evidence_ok": ev["ok"], "evidence_errors": ev["errors"]}


def verdict_check(spec_text: str, verdict: str, evidence: str | None = None, head: str | None = None,
                  frozen: str | None = None, repo_tag: str | None = None, today: str | None = None) -> dict:
    """Check a verdict comment against its template, the spec, the PR description and its waivers.

    Args:
        evidence: The PR description. When given, its evidence template must match and only a claimed pass can be
            confirmed.
        head: The PR's head commit sha. A verdict that audited another commit is stale.
        today: The date waivers expire against, as YYYY-MM-DD. Defaults to today.

    Returns:
        {ok, errors, overall, result_line, conclusion, head, frozen fingerprint, amendment count, evidence template,
            waivers by criterion id or "freeze"}. result_line is the line the comment must carry.
    """
    verdict = _lf(verdict)
    errors, values, v = check_doc("verdict", spec_text, verdict, _verdict_template(), repo_tag, frozen)
    if not v["head"] or len(v["head"]) != 40:
        errors.append("the '**Head commit:**' line needs the full 40-character sha the verdict audited")
    elif head and not v["head"].startswith(head.lower()):
        errors.append(f"stale: the verdict audited {v['head'][:12]}, but the PR's head is {head[:12]}")
    claims = {}
    if evidence is not None:
        ef = _header_fields(_lf(evidence))
        if (ef["template"], ef["version"]) != (v["template"], v["version"]):
            errors.append("the verdict's Evidence template line does not match the PR description's")
        claims = _column(evidence, "Result")
    verdicts = {k: x for k, x in values.items() if re.fullmatch(r"AC\d+", k)}
    errors += [f"{k}: only a claimed pass can be confirmed (the PR description says {claims[k]})"
               for k, x in verdicts.items() if x == "confirmed" and k in claims and claims[k] != "pass"]
    today = today or _dt.date.today().isoformat()
    waivers = {}
    for line in _strip_comments(section_text(verdict, "Waivers") or "").split("\n"):
        if not line.strip() or line.strip().lower().rstrip(".") == "none":
            continue
        m = WAIVER_RE.match(line)
        if not m or _blank(m.group(2)) or _blank(m.group(4)):
            errors.append("waiver not in '- ACn: waived by <name> until YYYY-MM-DD - <reason>' or "
                          f"'- freeze: waived by <name> until YYYY-MM-DD - <reason>' form: {line.strip()[:80]}")
            continue
        cid, until = m.group(1), m.group(3)
        cid = "freeze" if cid.lower() == "freeze" else cid
        waivers[cid] = {"by": m.group(2).strip(), "until": until, "reason": m.group(4).strip()}
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", until) or not _real_date(until):
            errors.append(f"{cid}: the waiver's date {until!r} is not a real YYYY-MM-DD date")
        elif until < today:
            errors.append("the freeze waiver expired on " + until if cid == "freeze" else
                          f"{cid}: the waiver expired on {until}")
        if cid != "freeze" and verdicts.get(cid) != "waived":
            errors.append(f"{cid}: has a waiver but its row is not marked waived")
    errors += [f"{k}: marked waived with no waiver line" for k, x in verdicts.items() if x == "waived" and k not in waivers]
    want = result_line(list(verdicts.values()))
    got = re.search(r"^\**result:?\**.*$", verdict, re.I | re.M)
    if not got or re.sub(r"[*\s]", "", got.group(0)).lower() != re.sub(r"[*\s]", "", want).lower():
        errors.append(f"the Result line must read: {want}")
    overall = overall_result(list(verdicts.values()))
    return {"ok": not errors, "errors": errors, "overall": overall, "result_line": want,
            "conclusion": "success" if overall == "confirmed" else "failure", "head": v["head"],
            "frozen_fingerprint": v["fingerprint"], "amendments": v["amendments"],
            "evidence_template": {"name": v["template"], "version": v["version"]}, "waivers": waivers}


def _real_date(s: str) -> bool:
    """Whether s is a calendar date that exists, in YYYY-MM-DD form (2026-02-30 is not)."""
    try:
        return _dt.date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


def verdict_latest(comments, head: str, spec_text: str | None = None, evidence: str | None = None) -> dict:
    """The newest verdict comment that is not stale, from `gh pr view --json comments` output.

    A verdict is stale when it audited another head commit, the spec's fingerprint or amendment count has changed,
    or the PR description's evidence template version differs. spec_text and evidence are optional; without them
    those two checks are skipped.

    Args:
        comments: The comments list, or the dict gh prints with a comments key.

    Returns:
        {latest, verdicts}: the newest current verdict or None, and every verdict found, oldest first.
    """
    head = (head or "").lower()
    if isinstance(comments, dict):
        comments = comments.get("comments") or []
    ef = _header_fields(_lf(evidence)) if evidence is not None else None
    found = []
    for i, c in enumerate(x for x in comments if isinstance(x, dict)):
        body = _lf(c.get("body") or "")
        if not re.search(r"^#{1,6}\s+" + TITLES["verdict"] + r"\b", body, re.M):
            continue
        v = _header_fields(body)
        stale = []
        if not head or not v["head"] or not v["head"].startswith(head):
            stale.append(f"audited {(v['head'] or 'no commit')[:12]}, the PR's head is {head[:12] or 'unknown'}")
        if spec_text is not None and (v["fingerprint"], v["amendments"]) != (
                fingerprint(spec_text), len(parse_amendments(spec_text)[0] or [])):
            stale.append("the spec's fingerprint or amendment count has changed")
        if ef is not None and (ef["template"], ef["version"]) != (v["template"], v["version"]):
            stale.append("the PR description's evidence template version differs")
        res = re.search(r"^\**result:?\**\s*([a-z ]+?)\s*(?:·|$)", body, re.I | re.M)
        found.append({"index": i, "url": c.get("url"), "at": c.get("createdAt"), "head": v["head"],
                      "frozen_fingerprint": v["fingerprint"], "amendments": v["amendments"],
                      "overall": res.group(1).strip().lower() if res else None, "stale": bool(stale),
                      "stale_because": stale})
    found.sort(key=lambda x: (parse_ts(x["at"]) or _dt.datetime.min.replace(tzinfo=_dt.timezone.utc), x["index"]))
    current = [x for x in found if not x["stale"]]
    return {"latest": current[-1] if current else None, "verdicts": found}


# ---------------------------------------------------------------- session note

NOTE_LIMIT = 600
CONFIG_SIZE_LIMIT = 64 * 1024
_SAFE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,9}")


def _quiet_git(args, cwd):
    """Git output for the session note, or None when git is missing, fails or takes over 1.5 seconds.

    It runs without locks, prompts or stdin so a session start never blocks.
    """
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    try:
        r = _proc(["git"] + args, cwd=cwd, timeout=1.5, env=env, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def branch_spec_id(branch: str, cfg: dict) -> str | None:
    """The spec id a branch is named for, such as OPS-412, #42 or AB#42, or None.

    It is built only from the config's validated key and digits, so no branch text reaches the note.
    """
    src = cfg.get("source")
    if not branch:
        return None
    if src in ("github", "ado"):
        m = re.match(r"(\d{1,6})-(?=[A-Za-z])", branch)
        return (f"#{m.group(1)}" if src == "github" else f"AB#{m.group(1)}") if m else None
    if src in ("jira", "linear"):
        key = str((cfg.get(src) or {}).get("project" if src == "jira" else "team") or "")
    elif src == "markdown":
        key = str((cfg.get("markdown") or {}).get("id_prefix") or "SPEC")
    else:
        return None
    if not _SAFE_KEY.fullmatch(key):
        return None
    m = re.search(r"(?<![A-Za-z0-9])" + re.escape(key) + r"-(\d{1,7})(?!\d)", branch, re.I)
    return f"{key.upper()}-{m.group(1)}" if m else None


def _where_line(cfg: dict) -> str:
    """The note's first line, saying where this repo's specs live.

    Only fixed words and validated keys go in, so nothing a repo can phrase reaches the note.
    """
    src = cfg["source"]
    if src == "markdown":
        where = "markdown files in the repo"
    elif src == "github":
        where = "GitHub issues"
    elif src == "ado":
        where = "Azure DevOps work items"
    else:
        key = str((cfg.get(src) or {}).get("project" if src == "jira" else "team") or "")
        name = "Jira project" if src == "jira" else "Linear team"
        where = f"{name} {key.upper()}" if _SAFE_KEY.fullmatch(key) else name.split()[0]
    return (f"This repo uses dc-specs: its specs are {where}, as set in specs/config.yaml, "
            "which also names the status that approves and freezes a spec.")


def session_context(cwd: str) -> str:
    """The session-start note, a fixed line when the config cannot be read, or '' outside opted-in repos.

    It never raises, so a broken repo cannot fail a session.
    """
    try:
        if os.environ.get("DC_SPECS_SESSION_NOTE", "").strip().lower() in ("off", "0", "false", "no"):
            return ""
        root = _quiet_git(["rev-parse", "--show-toplevel"], cwd)
        if not root:
            return ""
        path = os.path.join(root, "specs", "config.yaml")
        if not os.path.isfile(path):
            return ""
        unreadable = "specs/config.yaml exists but dc-specs cannot read it; spec-setup is the skill that writes it."
        if os.path.getsize(path) > CONFIG_SIZE_LIMIT:
            return unreadable
        try:
            with open(path, encoding="utf-8") as f:
                cfg = parse_yaml_subset(f.read())
            if validate_config(cfg):
                raise SpecError("invalid")
        except (SpecError, OSError, UnicodeDecodeError, AttributeError, TypeError, ValueError):
            return unreadable
        lines = [_where_line(cfg)]
        sid = branch_spec_id(_quiet_git(["branch", "--show-current"], root) or "", cfg)
        if sid:
            lines.append(f"The current branch is named for spec {sid}.")
        lines.append("An approved spec is only changed below its Amendments heading.")
        text = "\n".join(lines)
        if len(text) > NOTE_LIMIT:
            text = "\n".join(l for l in lines if "named for spec" not in l)[:NOTE_LIMIT]
        return text
    except Exception:
        return ""


# ---------------------------------------------------------------- cli

def _read(path: str | None) -> str:
    """A file's text with line endings kept, or stdin for '-' or no path, raising SpecError on empty stdin."""
    if path in (None, "-"):
        data = sys.stdin.read()
        if not data.strip():
            raise SpecError("no input: pass a file, or pipe the text on stdin")
        return data
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def _need(value, flag: str):
    """A value required only by some actions, raising SpecError naming flag when it is empty."""
    if not value:
        raise SpecError(f"{flag} is required here")
    return value


def _written(res: dict, out: str | None):
    """The rendered body, or with out, the body written there and the other fields plus `written`."""
    if not out:
        return res["body"]
    with open(out, "w", encoding="utf-8") as f:
        f.write(res["body"])
    return dict({k: v for k, v in res.items() if k != "body"}, written=out)


def cmd_config(a):
    """The config command: the validated config without internal keys, plus its path."""
    cfg = load_config(a.config)
    return dict({k: v for k, v in cfg.items() if not k.startswith("_")}, path=cfg["_path"])


def cmd_init(a):
    """The init command: write <repo root>/specs/config.yaml. Exit 1 when a change needs --force.

    Refuses --config, and a directory that is not a git repo root.
    """
    if a.config:
        raise SpecError("init always writes <repo root>/specs/config.yaml; pass --root instead of --config")
    root = git_root(a.root or ".")
    if not root or (a.root and root != os.path.realpath(a.root)):
        raise SpecError(f"--root must be the root of a git repo" if a.root else
                        "not in a git repo: run from the repo, or pass --root")
    opts = {k: getattr(a, k) for k in ("repo", "site", "project", "issue_type", "team", "org", "work_item_type",
                                       "dir", "id_prefix", "templates")}
    res = init_config(root, build_config(a.source, a.approval, a.in_progress, a.done, a.also_frozen, **opts),
                      a.force, a.dry_run)
    return res, 1 if res["needs_force"] and not a.force and not a.dry_run else 0


def cmd_setup_check(a):
    """The setup-check command. Exit 1 when a check failed."""
    res = setup_check(load_config(a.config))
    return res, 0 if res["ok"] else 1


def cmd_lint(a):
    """The lint command. Exit 1 on errors; exit 2 when --published has no usable config or spec file."""
    source, spec_path = None, None if a.spec in (None, "-") else a.spec
    if a.published:
        try:
            source = load_config(a.config)["source"]
        except SpecError as e:
            raise SpecError(f"a config is needed for --published ({e})")
        if source == "markdown" and not spec_path:
            raise SpecError("stdin has no folder to resolve image paths against")
    res = lint(_read(a.spec), a.approved, a.published, source, spec_path)
    return res, 0 if res["ok"] else 1


def cmd_fingerprint(a):
    """The fingerprint command, and with --frozen, whether the fingerprint differs."""
    fp = fingerprint(_read(a.spec))
    return {"fingerprint": fp, "frozen": a.frozen, "changed_since_freeze": fp != a.frozen} if a.frozen else \
        {"fingerprint": fp}


def cmd_amend(a):
    """The amend command: add a dated amendment to a spec file, stdin, a GitHub issue or an ADO work item.

    Returns:
        The new body for stdin, or a result naming what was written and its fingerprint.

    Raises:
        SpecError: When --issue or --item does not match the source, the spec no longer matches --frozen, or the
            amendment would change the frozen text.
    """
    if a.item:
        cfg = load_config(a.config)
        if cfg["source"] != "ado":
            raise SpecError("--item is for an ado source; pass --spec with the spec's text")
        return ado_amend(cfg, ado_number(a.item), a.criterion, a.text, a.by)
    if a.issue:
        cfg = load_config(a.config)
        if cfg["source"] != "github":
            raise SpecError("--issue is for a github source; pass --spec with the spec's text")
        return gh_amend(cfg["github"]["repo"], a.issue.lstrip("#"), cfg, a.criterion, a.text, a.by)
    body = _read(a.spec)
    if a.frozen and fingerprint(body) != a.frozen:
        raise SpecError(f"the spec no longer matches frozen fingerprint {a.frozen}; resolve that before amending")
    new = amended(body, a.criterion, a.text, a.by, a.date)
    if a.spec in (None, "-"):
        return new
    with open(a.spec, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    return {"written": a.spec, "fingerprint": fingerprint(new)}


def cmd_status(a):
    """The status command: the freeze state, read the way the target's source needs."""
    cfg = load_config(a.config, os.path.dirname(os.path.realpath(a.target)) if a.target.endswith(".md") else ".")
    src = cfg["source"]
    if src == "markdown":
        return md_status(a.target, cfg)
    if src == "github":
        return decide(gh_events(cfg["github"]["repo"], a.target.lstrip("#"), cfg), cfg)
    if src == "ado":
        return ado_status(cfg, ado_number(a.target))
    with open(a.target, encoding="utf-8") as f:
        data = json.load(f)
    return decide(jira_events(data, cfg) if src == "jira" else generic_events(data), cfg)


def cmd_ado(a):
    """The ado command: create a work item, set its Description, or comment, in Markdown. Needs the ado source."""
    cfg = load_config(a.config)
    if cfg["source"] != "ado":
        raise SpecError("ado commands need an ado source in specs/config.yaml")
    if a.action == "create":
        return ado_create(cfg, " ".join(_need(a.title, "--title").split()), _read(a.body_file), a.type)
    n = ado_number(_need(a.item, "--item"))
    text = _read(a.body_file)
    return ado_describe(cfg, n, text) if a.action == "describe" else ado_comment(cfg, n, text)


def cmd_deps(a):
    """The deps command, for --source or the config's source. Exit 1 when a tool is missing."""
    source = a.source
    if not source:
        try:
            source = load_config(a.config)["source"]
        except SpecError:
            pass
    res = deps(source)
    return res, 0 if res["ok"] else 1


def cmd_report_env(a):
    """The report-env command: the environment for an issue, with no source when there is no valid config."""
    try:
        cfg = load_config(a.config)
    except SpecError:
        cfg = None
    return report_env(cfg)


def cmd_evidence(a):
    """The evidence command: render the PR description, or check it (exit 1 on errors)."""
    cfg, spec = load_config(a.config), _read(a.spec)
    if a.action == "check":
        res = evidence_check(cfg, spec, _read(_need(a.evidence, "--evidence")), a.repo_tag, a.frozen)
        return res, 0 if res["ok"] else 1
    return _written(render_evidence(cfg, spec, a.template, a.id, a.url, a.repo_tag, a.frozen,
                                    None if a.spec == "-" else a.spec, _read(a.merge) if a.merge else None), a.out)


def cmd_verdict(a):
    """The verdict command: render, check (exit 1 on errors) or find the latest (exit 1 when none is current)."""
    if a.action == "latest":
        with open(_need(a.comments, "--comments"), encoding="utf-8") as f:
            comments = json.load(f)
        res = verdict_latest(comments, _need(a.head, "--head"), _read(a.spec) if a.spec else None,
                             _read(a.evidence) if a.evidence else None)
        return res, 0 if res["latest"] else 1
    spec = _read(_need(a.spec, "--spec"))
    if a.action == "check":
        res = verdict_check(spec, _read(_need(a.verdict, "--verdict")), _read(a.evidence) if a.evidence else None,
                            a.head, a.frozen, a.repo_tag, a.today)
        return res, 0 if res["ok"] else 1
    return _written(render_verdict(load_config(a.config), spec, _read(_need(a.evidence, "--evidence")), a.head,
                                   a.url, a.id, a.frozen), a.out)


# name: (handler, help, arguments). An argument ending in ! is required, * repeats, ? is a switch;
# one without dashes is positional, and name=a|b limits it to those values.
CLI = {
    "deps": (cmd_deps, "check the tools the helper and the source need, with install steps for this OS",
             "--source=markdown|github|jira|linear|ado"),
    "config": (cmd_config, "validate specs/config.yaml and print it", ""),
    "init": (cmd_init, "write specs/config.yaml; replacing one needs --force",
             "--source! --approval! --in-progress --done --also-frozen* --repo --site --project --issue-type --team "
             "--org --work-item-type --dir --id-prefix --templates --root --force? --dry-run?"),
    "setup-check": (cmd_setup_check, "check the config, connection, labels and repo templates", ""),
    "templates": (lambda a: template_list(load_config(a.config)), "the spec templates this repo can use", ""),
    "render": (lambda a: render_template(load_config(a.config), a.template, a.title, a.id),
               "a new spec from a template, with the header for this repo's source", "--template! --title! --id"),
    "lint": (cmd_lint, "check sections, criteria, amendments, slide images, placeholders and published images",
             "--spec --approved? --published?"),
    "fingerprint": (cmd_fingerprint, "the fingerprint of a spec's frozen part", "--spec --frozen"),
    "amend": (cmd_amend, "add a dated amendment, refusing if the frozen text would change",
              "--spec --issue --item --criterion! --text! --by --date --frozen"),
    "status": (cmd_status, "the freeze state: a markdown spec path, a GitHub issue or Azure DevOps work item "
                           "number, or a saved Jira issue or Linear events JSON file", "target"),
    "ado": (cmd_ado, "Azure DevOps writes as Markdown: create a work item, set its description, or comment",
            "action=create|describe|comment --item --title --type --body-file"),
    "evidence": (cmd_evidence, "render or check the PR description",
                 "action=render|check --spec! --evidence --template --id --url --repo-tag --frozen --merge --out"),
    "verdict": (cmd_verdict, "render or check a verdict comment, or find the latest one",
                "action=render|check|latest --spec --evidence --verdict --head --comments --id --url --repo-tag "
                "--frozen --today --out"),
    "report-env": (cmd_report_env, "the dc-specs, OS, Python and tool versions for an issue, with no paths or "
                                   "config values", ""),
    "report-link": (lambda a: report_link(a.title, a.label, _read(a.body_file)),
                    "a prefilled new-issue link on the dc-specs repo, with the body only when it fits",
                    "--title! --label=bug|enhancement! --body-file!"),
    "session-context": (None, "the session-start note; prints nothing unless this repo uses dc-specs", ""),
}
FLAG_KINDS = {"!": {"required": True}, "*": {"action": "append", "default": []}, "?": {"action": "store_true"}}


def _parser():
    """The argument parser built from CLI, accepting --config before or after the command name."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", dest="config_sub", help="path to specs/config.yaml")
    p = argparse.ArgumentParser(prog="dcspecs", description=(__doc__ or "").split("\n")[0])
    p.add_argument("--config", help="path to specs/config.yaml (default: <git root>/specs/config.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, (_, hlp, args) in CLI.items():
        sp = sub.add_parser(name, parents=[common], help=hlp)
        for arg in args.split():
            kw = dict(FLAG_KINDS.get(arg[-1], {}))
            arg, _, choices = arg.rstrip("!*?").partition("=")
            if choices:
                kw["choices"] = choices.split("|")
            sp.add_argument(arg, **kw)
    return p


def _emit(obj):
    """Print a result: text as it is, anything else as indented JSON."""
    if isinstance(obj, str):
        sys.stdout.write(obj if obj.endswith("\n") else obj + "\n")
    else:
        json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")


def _utf8_stdio():
    """Switch stdin, stdout and stderr to UTF-8.

    Windows consoles and pipes default to the ANSI code page, and specs and JSON are UTF-8.
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def main(argv=None) -> int:
    """Run one helper command and return its exit code: 0 for success, 1 when a check failed, 2 for an error.

    session-context runs before argument parsing and always exits 0, so the session hook never fails.
    """
    _utf8_stdio()
    if (sys.argv[1:] if argv is None else argv)[:1] == ["session-context"]:
        try:
            note = session_context(os.getcwd())
            if note:
                sys.stdout.write(note + "\n")
        except Exception:
            pass
        return 0
    args = _parser().parse_args(argv)
    args.config = args.config_sub or args.config
    try:
        res = CLI[args.cmd][0](args)
        out, code = res if isinstance(res, tuple) else (res, 0)
        _emit(out)
        return code
    except SpecError as e:
        sys.stderr.write(f"dcspecs: {e}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
