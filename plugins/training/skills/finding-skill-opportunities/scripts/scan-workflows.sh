#!/usr/bin/env bash
#
# scan-workflows.sh — Find workflow encodings already living in a codebase.
#
# Recurring procedures are often half-captured as Makefile targets, package.json
# scripts, CI jobs, shell scripts, or "How to..." doc sections. Each is a
# ready-made skill candidate: the steps already exist, they just need to be
# turned into a SKILL.md an agent can follow. This script inventories them and
# flags any skills that already exist (so you don't propose duplicates).
#
# Read-only. Uses git to respect tracked files when available, else falls back
# to find.
#
# Usage:
#   scan-workflows.sh [--repo DIR]
#
set -euo pipefail
export LC_ALL=C

REPO="."
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

cd "$REPO"

# List tracked files (deterministic, ignores build artifacts) or fall back.
list_files() {
  if git rev-parse --git-dir >/dev/null 2>&1; then
    git ls-files
  else
    find . -type f -not -path '*/.git/*' | sed 's|^\./||'
  fi
}

FILES="$(list_files | sort)"
section() { printf '\n========== %s ==========\n' "$1"; }
have() { printf '%s\n' "$FILES" | grep -iE "$1" || true; }

# ---------------------------------------------------------------------------
section "MAKEFILE TARGETS"
mf="$(printf '%s\n' "$FILES" | grep -iE '(^|/)(GNUmakefile|[Mm]akefile)$' | head -1 || true)"
if [ -n "$mf" ]; then
  echo "# from $mf"
  # Real targets look like `name:` at column 0; skip .PHONY and pattern rules.
  grep -nE '^[a-zA-Z0-9][a-zA-Z0-9_.-]*:' "$mf" | grep -v '^[0-9]*:\.' || true
else
  echo "(no Makefile)"
fi

# ---------------------------------------------------------------------------
section "PACKAGE.JSON SCRIPTS"
pkgs="$(printf '%s\n' "$FILES" | grep -iE '(^|/)package\.json$' || true)"
if [ -n "$pkgs" ]; then
  for p in $pkgs; do
    echo "# from $p"
    # Print the "scripts" block keys without needing jq.
    awk '
      /"scripts"[[:space:]]*:[[:space:]]*\{/ { inb=1; next }
      inb && /\}/ { inb=0 }
      inb && /:/ {
        line=$0; sub(/^[[:space:]]*"/,"",line); sub(/".*/,"",line)
        if (line != "") print "  " line
      }
    ' "$p"
  done
else
  echo "(no package.json)"
fi

# ---------------------------------------------------------------------------
section "TASK RUNNERS (justfile / Taskfile / Rakefile / Procfile)"
have '(^|/)(justfile|Justfile|Taskfile\.ya?ml|Rakefile|Procfile)$' | sed 's/^/  /' | grep . || echo "(none)"

# ---------------------------------------------------------------------------
section "CI / AUTOMATION WORKFLOWS"
have '(^|/)\.github/workflows/.*\.ya?ml$|(^|/)\.gitlab-ci\.yml$|(^|/)\.circleci/|(^|/)azure-pipelines\.yml$|(^|/)\.pre-commit-config\.yaml$' | sed 's/^/  /' | grep . || echo "(none)"

# ---------------------------------------------------------------------------
section "STANDALONE SCRIPTS (scripts/, bin/, *.sh)"
have '(^|/)(scripts?|bin)/|\.sh$' | sed 's/^/  /' | grep . || echo "(none)"

# ---------------------------------------------------------------------------
# "How to" / runbook prose in docs is procedural knowledge waiting to be a skill.
section "HOW-TO / RUNBOOK DOC SECTIONS"
docs="$(printf '%s\n' "$FILES" | grep -iE '\.(md|mdx|rst|txt)$' || true)"
if [ -n "$docs" ]; then
  # -I skips binary, headings that read like procedures.
  echo "$docs" | tr '\n' '\0' | xargs -0 grep -inE '^#{1,4}.*(how to|setup|getting started|deploy|release|migrat|onboard|workflow|runbook|step[ -]?by[ -]?step|guide)' 2>/dev/null | head -40 || true
else
  echo "(no docs)"
fi

# ---------------------------------------------------------------------------
section "EXISTING SKILLS (avoid proposing duplicates)"
have '(^|/)skills/.*/SKILL\.md$|(^|/)SKILL\.md$|(^|/)\.claude/(commands|skills)/' | sed 's/^/  /' | grep . || echo "(none found)"

echo
echo "Done. Map each encoded workflow to a candidate skill in SKILL.md (Synthesis)."
