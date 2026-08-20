#!/usr/bin/env bash
#
# git-signals.sh — Deterministic git-history analysis for spotting skill opportunities.
#
# Reads a repo's git history and prints structured, sorted signals that hint at
# recurring, multi-step procedures worth capturing as Claude Code skills:
#   - commit volume + contributor summary
#   - conventional-commit / message-prefix frequency
#   - recurring chore keywords (release, deploy, migrate, ...)
#   - hot files (changed most often)
#   - co-changed file pairs (files that keep moving together)
#   - busiest directories
#
# Output is sorted and contains no timestamps, so repeated runs on the same
# history are byte-identical (deterministic).
#
# Usage:
#   git-signals.sh [--repo DIR] [--days N | --since DATE] [--top N]
#
#   --repo DIR    Repository to analyze (default: current directory)
#   --days N      Only consider commits from the last N days. Sugar for
#                 --since "N days ago", so one lookback window can drive both
#                 this script and session-signals.py --days N.
#   --since DATE  Only consider commits after DATE (e.g. "1 year ago", 2024-01-01).
#                 Wins if both are given.
#   --top N       How many rows per ranked section (default: 20)
#
# No pipefail: we deliberately pipe `git log` into `head`, which closes the
# pipe early and makes git exit with SIGPIPE — harmless here, but pipefail would
# abort the run.
set -eu
export LC_ALL=C

REPO="."
SINCE=""
DAYS=""
TOP=20

while [ $# -gt 0 ]; do
  case "$1" in
    --repo)  REPO="$2"; shift 2 ;;
    --since) SINCE="$2"; shift 2 ;;
    --days)  DAYS="$2"; shift 2 ;;
    --top)   TOP="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

# --days is sugar over git's approxidate parser; an explicit --since wins.
if [ -n "$DAYS" ]; then
  case "$DAYS" in
    ''|*[!0-9]*) echo "ERROR: --days must be a whole number, got '$DAYS'." >&2; exit 2 ;;
  esac
  [ -z "$SINCE" ] && SINCE="$DAYS days ago"
fi

if ! git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ERROR: '$REPO' is not a git repository." >&2
  exit 1
fi

# Common log filter args (since is optional).
SINCE_ARGS=()
[ -n "$SINCE" ] && SINCE_ARGS=(--since="$SINCE")

g() { git -C "$REPO" "$@"; }

section() { printf '\n========== %s ==========\n' "$1"; }

# ---------------------------------------------------------------------------
section "REPO SUMMARY"
commits=$(g rev-list --count ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} HEAD)
first=$(g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --reverse --format=%as | head -1)
last=$(g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%as | head -1)
authors=$(g shortlog -sn ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} HEAD | wc -l | tr -d ' ')
echo "commits analyzed : $commits"
echo "date range       : ${first:-n/a} -> ${last:-n/a}"
echo "contributors     : $authors"
[ -n "$SINCE" ] && echo "(filtered --since: $SINCE)"

# ---------------------------------------------------------------------------
# Conventional-commit type / message prefix frequency.
# Looks at the token before the first ':' in the subject (feat, fix, chore, ...),
# stripping any scope in parentheses. Subjects with no prefix are bucketed as
# "(none)".
section "COMMIT MESSAGE PREFIXES (type before ':')"
g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%s |
  awk '{
    if (match($0, /^[a-zA-Z]+(\([^)]*\))?!?:/)) {
      p = substr($0, 1, RLENGTH)
      sub(/\(.*/, "", p)      # drop scope
      sub(/!?:$/, "", p)      # drop trailing !:
      print tolower(p)
    } else {
      print "(none)"
    }
  }' |
  sort | uniq -c | sort -rn | head -n "$TOP"

# ---------------------------------------------------------------------------
# Recurring chore keywords anywhere in the subject. These name the kinds of
# repeated procedures that most often deserve a skill.
section "RECURRING TASK KEYWORDS (in commit subjects)"
g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%s |
  awk '
    BEGIN {
      n = split("release deploy migrate migration bump upgrade update dependency dependencies regenerate generate backfill rotate seed sync publish hotfix changelog version refactor rename scaffold boilerplate setup config configure provision lint format", kw, " ")
    }
    {
      line = tolower($0)
      for (i = 1; i <= n; i++) if (index(line, kw[i])) counts[kw[i]]++
    }
    END { for (k in counts) printf "%7d %s\n", counts[k], k }
  ' |
  sort -rn | head -n "$TOP"

# ---------------------------------------------------------------------------
# Hot files: changed in the most commits. Frequently touched files often hide a
# repeated editing procedure.
section "HOT FILES (most-changed, count = commits touching it)"
g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%H --name-only |
  awk 'NF && $0 !~ /^[0-9a-f]{40}$/' |
  sort | uniq -c | sort -rn | head -n "$TOP"

# ---------------------------------------------------------------------------
# Co-changed file pairs: files that repeatedly appear in the same commit.
# Strong pairs reveal a manual "change A, then remember to change B" ritual.
# Commits touching more than MAXFILES files are skipped (bulk/merge commits add
# noise and O(n^2) blowup).
section "CO-CHANGED FILE PAIRS (count = commits changing both)"
g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%H --name-only |
  awk -v MAXFILES=40 '
    function flush(   i, j) {
      if (nf >= 2 && nf <= MAXFILES) {
        for (i = 1; i < nf; i++)
          for (j = i + 1; j <= nf; j++) {
            a = files[i]; b = files[j]
            if (a < b) print a "\t" b; else print b "\t" a
          }
      }
      nf = 0
    }
    /^[0-9a-f]{40}$/ { flush(); next }
    NF { files[++nf] = $0 }
    END { flush() }
  ' |
  sort | uniq -c | sort -rn | awk '$1 >= 2' | head -n "$TOP"

# ---------------------------------------------------------------------------
# Busiest directories: where churn concentrates.
section "BUSIEST DIRECTORIES (count = file-changes under it)"
g log ${SINCE_ARGS[@]+"${SINCE_ARGS[@]}"} --format=%H --name-only |
  awk 'NF && $0 !~ /^[0-9a-f]{40}$/ {
    n = split($0, parts, "/")
    print (n > 1 ? parts[1] : "(root)")
  }' |
  sort | uniq -c | sort -rn | head -n "$TOP"

echo
echo "Done. Interpret these signals with SKILL.md (Signal interpretation)."
