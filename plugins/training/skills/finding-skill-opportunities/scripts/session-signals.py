#!/usr/bin/env python3
"""session-signals.py - Deterministic coding-session analysis for spotting skill opportunities.

The git-history companion (git-signals.sh) can only see work that ended in a
commit. This script reads local Claude Code session transcripts
(~/.claude/projects/<encoded-cwd>/*.jsonl) and prints the same shape of signals
for what people actually *asked for* and *did* in their sessions:

  - session volume + how many already routed through a skill
  - recurring request clusters (verb + object of the asks)
  - recurring task keywords (same vocabulary as git-signals.sh, for corroboration)
  - repeated tool-call sequences (n-grams = automatable procedures)
  - hot files and co-edited file pairs (including work never committed)
  - skills already invoked (so you do not propose duplicates)
  - friction signal: how many sessions contained correction-shaped turns

Read-only. Output is sorted (count desc, then key asc) and carries no wall-clock
timestamps beyond the resolved window, so two runs over the same window and the
same transcripts are byte-identical.

Usage:
  session-signals.py [--repo DIR] [--days N | --since YYYY-MM-DD] [--top N]
                     [--scope repo|all] [--transcripts-dir DIR] [--no-examples]

  --repo DIR           Repo whose sessions to analyze (default: current directory)
  --days N             Look back N days (default: 30)
  --since YYYY-MM-DD   Absolute cutoff; overrides --days
  --top N              Rows per ranked section (default: 20)
  --scope repo|all     repo = only sessions whose cwd is the repo or below it
                       (default); all = every project transcript on this machine
  --transcripts-dir D  Override the transcript root (default ~/.claude/projects)
  --no-examples        Omit verbatim prompt snippets from the output. Use when the
                       report will be shared - prompts can contain client detail.

PRIVACY: transcripts are the user's own prompts and may quote client or customer
material. This script only reads them and writes to stdout; it uploads nothing.
Still, treat the output as sensitive and prefer --no-examples before sharing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Same vocabulary git-signals.sh greps commit subjects for. Sharing the list is
# the point: a keyword that ranks high in BOTH outputs is a corroborated signal.
TASK_KEYWORDS = """release deploy migrate migration bump upgrade update dependency
dependencies regenerate generate backfill rotate seed sync publish hotfix
changelog version refactor rename scaffold boilerplate setup config configure
provision lint format""".split()

ACTION_RE = re.compile(
    r"\b(draft|create|write|generate|build|make|fix|update|review|analyze|"
    r"summarize|find|search|run|send|check|add|remove|refactor|debug|"
    r"convert|prepare|plan|design|implement|explain|investigate|audit|"
    r"deploy|release|migrate|rename|bump|test)\b",
    re.I,
)

STOPWORDS = {
    "the", "a", "an", "of", "for", "to", "in", "on", "with", "my", "this",
    "that", "it", "and", "or", "but", "is", "are", "was", "were", "be",
    "from", "by", "at", "as", "i", "we", "you", "me", "please", "can", "could",
    "would", "should", "our", "your", "its", "all", "any", "so", "then", "just",
    # Fillers that otherwise become the "object" of a cluster key and produce
    # meaningless rows like "make sure" or "add new".
    "sure", "new", "other", "another", "thing", "things", "stuff", "way",
    "bit", "little", "more", "less", "better", "again", "now", "here", "there",
    "those", "these", "them", "what", "which", "when", "where", "how", "why",
    "into", "out", "up", "down", "over", "back", "also", "still", "one", "two",
}

# Correction-shaped turns: a terse critique after a long assistant turn. Kept
# deliberately shallow - deep correction mining belongs to the pattern-audit
# skill; here it is only a count that says "guidance is missing somewhere".
CRITIQUE_RE = re.compile(
    r"\b(too \w+|overly|instead|rephrase|reword|rewrite|tone down|soften|"
    r"shorten|trim|revert|undo|wrong|dont|don't|doesnt|doesn't|"
    r"shouldn't|isn't|no,)",
    re.I,
)

FILE_TOOLS = {"Edit", "Write", "Read", "NotebookEdit", "MultiEdit"}

# Tools whose calls say nothing about a procedure's shape.
NOISE_TOOLS = {"TodoWrite", "TaskCreate", "TaskUpdate", "ToolSearch"}

# Every session edits files, so an n-gram made only of these describes "editing
# code", not a procedure. A sequence earns its place by including something more
# specific: a Skill, an MCP tool, a browser, a subagent.
GENERIC_TOOLS = {"Bash", "PowerShell", "Read", "Edit", "Write", "Grep", "Glob", "MultiEdit"}


def parse_args(argv):
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--repo", default=".")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--since")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--scope", choices=("repo", "all"), default="repo")
    p.add_argument("--transcripts-dir")
    p.add_argument("--no-examples", action="store_true")
    p.add_argument("-h", "--help", action="store_true")
    args = p.parse_args(argv)
    if args.help:
        print(__doc__)
        raise SystemExit(0)
    return args


def resolve_cutoff(args):
    if args.since:
        try:
            dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
        except ValueError:
            print("ERROR: --since must be YYYY-MM-DD, got '%s'." % args.since, file=sys.stderr)
            raise SystemExit(2)
        return dt, "since %s" % args.since
    dt = datetime.now(timezone.utc) - timedelta(days=args.days)
    return dt, "last %d days (>= %s)" % (args.days, dt.date().isoformat())


def load_events(path):
    events = []
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a partially-flushed final line is normal
    except OSError:
        return []
    return events


def block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


def is_synthetic(text):
    """Hook output, harness plumbing, reminders - not something a human typed.

    Without this the top "requests" are all '[Request interrupted by user]' and
    task notifications, which say nothing about what anyone was trying to do.
    """
    return text.startswith((
        "<command", "<local-command", "<system-reminder", "<user-prompt",
        "Caveat:", "Base directory for this skill:", "<bash-input",
        "<task-notification", "[Request interrupted", "[Image:", "[Pasted text",
        "API Error", "<attachment", "<ide_", "<agent-",
    ))


def analyze(events):
    """Reduce one transcript to the facts the ranked sections need."""
    prompts = []
    tools = []
    files = set()
    skills = set()
    corrections = 0
    cwd = ""
    branch = ""
    first_ts = last_ts = None
    prev_assistant_len = 0

    for e in events:
        ts = e.get("timestamp")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        cwd = cwd or e.get("cwd") or ""
        branch = branch or e.get("gitBranch") or ""
        etype = e.get("type")
        msg = e.get("message") or {}

        if etype == "user":
            content = msg.get("content")
            # tool_result-only turns are the harness talking, not the user
            if isinstance(content, list) and content and isinstance(content[0], dict) \
               and content[0].get("type") == "tool_result":
                continue
            text = block_text(content).strip()
            if not text or is_synthetic(text):
                continue
            prompts.append(text)
            if len(text) < 400 and prev_assistant_len > 800 and CRITIQUE_RE.search(text):
                corrections += 1
            prev_assistant_len = 0

        elif etype == "assistant":
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    prev_assistant_len += len(c.get("text", ""))
                elif c.get("type") == "tool_use":
                    name = c.get("name", "")
                    inp = c.get("input") or {}
                    if name == "Skill":
                        s = inp.get("skill")
                        if s:
                            skills.add(s)
                    if name in FILE_TOOLS:
                        fp = inp.get("file_path") or inp.get("notebook_path")
                        if fp:
                            # The same file shows up with both separators across
                            # tools; without normalizing, one file ranks twice.
                            files.add(str(fp).replace("\\", "/"))
                    if name and name not in NOISE_TOOLS:
                        tools.append(name)

    return {
        "prompts": prompts, "tools": tools, "files": files, "skills": skills,
        "corrections": corrections, "cwd": cwd, "branch": branch,
        "first_ts": first_ts, "last_ts": last_ts,
    }


def normalize(text):
    text = text.strip().lower()
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # drop pasted code
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s/._-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def salient(text, min_len):
    """Content words, punctuation trimmed so 'prs.' and 'prs' are one token."""
    out = []
    for w in re.findall(r"[a-z][a-z0-9._/-]*", text):
        w = w.strip("._-/")
        if w and w not in STOPWORDS and len(w) > min_len:
            out.append(w)
    return out


def cluster_key(prompt):
    """(verb, up-to-3 salient object words) - the repeated *ask*, normalized."""
    norm = normalize(prompt)
    m = ACTION_RE.search(norm)
    if m:
        return m.group(1).lower(), tuple(salient(norm[m.end():m.end() + 120], 2)[:3])
    return "?", tuple(salient(norm, 3)[:3])


def ranked(counts, top, min_count=1):
    """Sorted by count desc then key asc - stable across runs."""
    rows = [(k, v) for k, v in counts.items() if v >= min_count]
    rows.sort(key=lambda kv: (-kv[1], str(kv[0])))
    return rows[:top]


def section(title):
    print("\n========== %s ==========" % title)


def emit(rows, fmt=lambda k: k):
    if not rows:
        print("  (none)")
        return
    for key, count in rows:
        print("%7d %s" % (count, fmt(key)))


def main(argv):
    args = parse_args(argv)
    cutoff, window_label = resolve_cutoff(args)

    root = Path(args.transcripts_dir) if args.transcripts_dir else Path.home() / ".claude" / "projects"
    if not root.is_dir():
        print("ERROR: transcript root '%s' not found. Pass --transcripts-dir, "
              "or run with --source git only." % root, file=sys.stderr)
        return 1

    repo = Path(args.repo).resolve()
    repo_prefix = str(repo).replace("\\", "/").rstrip("/") + "/"
    transcripts = sorted(root.glob("*/*.jsonl"))

    scanned = 0
    sessions = []
    by_cwd = 0
    by_files = 0
    for path in transcripts:
        events = load_events(path)
        if not events:
            continue
        scanned += 1
        s = analyze(events)
        if not s["first_ts"]:
            continue
        try:
            started = datetime.fromisoformat(s["first_ts"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if started < cutoff:
            continue
        if args.scope == "repo":
            # Two ways a session counts as being about this repo. cwd alone is not
            # enough: people routinely run Claude from one directory (a notes vault,
            # a workspace root) while editing another repo, and scoping on cwd only
            # reports 0 sessions for a repo with hundreds of edits.
            cwd_match = False
            cwd = s["cwd"]
            if cwd:
                try:
                    cwd_path = Path(cwd).resolve()
                    cwd_match = cwd_path == repo or repo in cwd_path.parents
                except OSError:
                    cwd_match = False
            file_match = any(f.startswith(repo_prefix) for f in s["files"])
            if not (cwd_match or file_match):
                continue
            if cwd_match:
                by_cwd += 1
            else:
                by_files += 1
        s["path"] = path
        sessions.append(s)

    # A session with one prompt and no tools is a question, not a procedure.
    substantive = [s for s in sessions if len(s["prompts"]) >= 2 or len(s["tools"]) >= 3]
    with_skill = [s for s in substantive if s["skills"]]
    no_skill = [s for s in substantive if not s["skills"]]

    section("SESSION SUMMARY")
    print("transcripts root  : %s" % root)
    print("scope             : %s%s" % (args.scope, " (%s)" % repo if args.scope == "repo" else ""))
    print("window            : %s" % window_label)
    print("transcripts read  : %d" % scanned)
    print("sessions in scope : %d" % len(sessions))
    if args.scope == "repo":
        print("  matched by cwd  : %d" % by_cwd)
        print("  by files edited : %d  (session ran elsewhere)" % by_files)
    print("  substantive     : %d" % len(substantive))
    print("  used a skill    : %d" % len(with_skill))
    print("  no skill (pool) : %d" % len(no_skill))
    if sessions:
        starts = sorted(s["first_ts"][:10] for s in sessions if s["first_ts"])
        print("date range        : %s -> %s" % (starts[0], starts[-1]))
        branches = Counter(s["branch"] for s in sessions if s["branch"])
        if branches:
            print("branches          : " + ", ".join(
                "%s (%d)" % (b, n) for b, n in ranked(branches, 5)))
    if not sessions:
        print("\nNo sessions matched. Widen with --days N, or --scope all if the work "
              "happened from a different working directory.")
        return 0

    # The opportunity pool is the no-skill sessions: work not yet covered.
    section("RECURRING REQUEST CLUSTERS (no-skill sessions; count = sessions)")
    clusters = defaultdict(list)
    for s in no_skill:
        seen = set()
        for p in s["prompts"]:
            k = cluster_key(p)
            if not k[1] or k in seen:
                continue
            seen.add(k)
            clusters[k].append(p)
    # Drop the verbless bucket: with no action verb the key is just three common
    # words ("? alright", "? keep going"), which is chatter, not a procedure.
    counts = Counter({k: len(v) for k, v in clusters.items() if k[0] != "?"})
    rows = ranked(counts, args.top, min_count=2)
    emit(rows, fmt=lambda k: "%s %s" % (k[0], " ".join(k[1])))
    if not no_skill:
        # An empty pool is a finding, not a dead end - and the fix for it is the
        # opposite of widening the window, so say which case this is.
        print("  Every substantive session in scope already used a skill. The")
        print("  opportunity here is sharpening those skills (see SKILLS ALREADY USED")
        print("  and FRICTION, then the skill-improver skill), not adding new ones.")
    elif not rows:
        print("  Too few sessions for a repeated verb+object phrasing to emerge. Read")
        print("  ACTION VOLUME and REPEATED TOOL SEQUENCES below instead, or widen")
        print("  the window with --days N.")
    if rows and not args.no_examples:
        print("\n  examples (first prompt per top cluster):")
        for key, _ in rows[:5]:
            sample = " ".join(clusters[key][0].split())[:140]
            print("    [%s %s] %s" % (key[0], " ".join(key[1]), sample))

    # Coarser than the clusters above and always populated: which KINDS of ask
    # dominate. On its own it never names a candidate - pair a heavy verb with a
    # tool sequence or a hot file to find the procedure underneath it.
    section("ACTION VOLUME (no-skill sessions asking for each action)")
    verbs = Counter()
    for s in no_skill:
        seen_v = set()
        for p in s["prompts"]:
            v = cluster_key(p)[0]
            if v != "?" and v not in seen_v:
                seen_v.add(v)
                verbs[v] += 1
    emit(ranked(verbs, args.top))

    section("RECURRING TASK KEYWORDS (in user prompts)")
    kw = Counter()
    for s in substantive:
        blob = normalize(" ".join(s["prompts"]))
        for k in TASK_KEYWORDS:
            if k in blob:
                kw[k] += 1  # sessions mentioning it, not raw mentions
    emit(ranked(kw, args.top))

    section("REPEATED TOOL SEQUENCES (3-grams; generic edit-loops excluded)")
    ngrams = Counter()
    for s in no_skill:
        # Collapse runs first: Bash,Bash,Bash,Read is one step then another, and
        # without collapsing the top rows are all permutations of the same loop.
        seq = [t for i, t in enumerate(s["tools"]) if i == 0 or t != s["tools"][i - 1]]
        for i in range(len(seq) - 2):
            tri = tuple(seq[i:i + 3])
            if all(t in GENERIC_TOOLS for t in tri):
                continue
            ngrams[tri] += 1
    emit(ranked(ngrams, args.top, min_count=3), fmt=lambda t: " -> ".join(t))

    # In repo scope, a session's files can live anywhere the user wandered
    # (plugin caches, other repos). Rank only files belonging to the repo under
    # audit, and report the rest as a single count so nothing is silently cut.
    def in_scope(path):
        return args.scope == "all" or path.startswith(repo_prefix)

    def show(path):
        """Repo-relative, so these rows line up with git-signals.sh hot files."""
        return path[len(repo_prefix):] if path.startswith(repo_prefix) else path

    outside = 0
    for s in substantive:
        outside += sum(1 for f in s["files"] if not in_scope(f))

    section("HOT FILES (count = sessions touching it)")
    hot = Counter()
    for s in substantive:
        for f in s["files"]:
            if in_scope(f):
                hot[f] += 1
    emit(ranked(hot, args.top, min_count=2), fmt=show)
    if outside:
        print("  (%d file-touches outside %s not ranked; use --scope all to include)"
              % (outside, repo))

    section("CO-EDITED FILE PAIRS (count = sessions touching both)")
    pairs = Counter()
    for s in substantive:
        fs = sorted(f for f in s["files"] if in_scope(f))
        if not 2 <= len(fs) <= 40:      # bulk sessions add noise and O(n^2)
            continue
        for i in range(len(fs)):
            for j in range(i + 1, len(fs)):
                pairs[(fs[i], fs[j])] += 1
    emit(ranked(pairs, args.top, min_count=2),
         fmt=lambda p: "%s\t%s" % (show(p[0]), show(p[1])))

    section("SKILLS ALREADY USED (do NOT propose these - find gaps)")
    used = Counter()
    for s in substantive:
        for sk in s["skills"]:
            used[sk] += 1
    emit(ranked(used, args.top))

    section("FRICTION (sessions containing correction-shaped turns)")
    friction = sum(1 for s in substantive if s["corrections"])
    total_corr = sum(s["corrections"] for s in substantive)
    print("  %d of %d substantive sessions, %d turns total"
          % (friction, len(substantive), total_corr))
    print("  A high rate means guidance is missing, but WHICH guidance needs the")
    print("  pattern-audit skill - this is a volume signal only.")

    print("\nDone. Interpret these signals with SKILL.md (Signal interpretation).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
