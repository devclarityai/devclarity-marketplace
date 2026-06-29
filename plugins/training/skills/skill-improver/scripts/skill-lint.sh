#!/usr/bin/env bash
#
# skill-lint.sh — Deterministic mechanical facts about a skill, for skill-improver.
#
# Gathers the things you can check without judgment — frontmatter validity, name
# format, description shape, SKILL.md size, which preferred sections exist, what
# files are bundled, and which bundled files are actually referenced. The skill's
# qualitative review (is the name clear? is the scope right?) is left to the
# model; this script just removes guesswork from the mechanical parts.
#
# Read-only. Output is sorted/stable so reruns on unchanged input match.
#
# Usage:
#   skill-lint.sh <skill-dir-or-SKILL.md>
#
set -eu
export LC_ALL=C

TARGET="${1:-.}"
if [ -d "$TARGET" ]; then
  DIR="$TARGET"; MD="$TARGET/SKILL.md"
else
  MD="$TARGET"; DIR="$(dirname "$TARGET")"
fi

section() { printf '\n========== %s ==========\n' "$1"; }
flag()    { printf '  [FLAG] %s\n' "$1"; }
ok()      { printf '  [ok]   %s\n' "$1"; }

if [ ! -f "$MD" ]; then
  echo "ERROR: no SKILL.md found at '$MD'." >&2
  exit 1
fi

# --- Extract YAML frontmatter (between the first two '---' lines) -------------
FM="$(awk 'NR==1 && $0=="---"{f=1;next} f && $0=="---"{exit} f{print}' "$MD")"
NAME="$(printf '%s\n' "$FM"  | awk -F': *' '/^name:/{sub(/^name: */,""); print; exit}')"
DESC="$(printf '%s\n' "$FM"  | awk -F': *' '/^description:/{sub(/^description: */,""); print; exit}')"
FM_CHARS=$(printf '%s' "$FM" | wc -c | tr -d ' ')

section "FRONTMATTER"
if [ -z "$FM" ]; then
  flag "no YAML frontmatter found (must start with '---')"
else
  echo "  frontmatter chars: $FM_CHARS (limit 1024)"
  [ "$FM_CHARS" -gt 1024 ] && flag "frontmatter exceeds 1024 chars"
  if [ -n "$NAME" ]; then ok "name: $NAME"; else flag "missing 'name:' field"; fi
  if [ -n "$DESC" ]; then ok "description present (${#DESC} chars)"; else flag "missing 'description:' field"; fi
fi

# --- Name format: letters, numbers, hyphens only -----------------------------
section "NAME & SCOPE"
if [ -n "$NAME" ]; then
  if printf '%s' "$NAME" | grep -qE '^[a-zA-Z0-9-]+$'; then
    ok "name uses only letters/numbers/hyphens"
  else
    flag "name has characters outside [a-zA-Z0-9-]: '$NAME'"
  fi
  # Action/role oriented? Accept a gerund at the start (finding-skill-...),
  # or a last segment that is an agent-noun / verb (...-writer, ...-generator,
  # ...-review). A bare-noun topic (unit-test) gets a nudge toward the action.
  last="${NAME##*-}"
  if printf '%s' "$NAME" | grep -qiE '^[a-z]+ing(-|$)' \
     || printf '%s' "$last" | grep -qiE '(ing|er|or)$' \
     || printf '%s' "$last" | grep -qiwE 'write|create|build|make|generate|deploy|release|fix|debug|trace|refactor|analyze|optimize|migrate|review|lint|format|convert|extract|summarize|audit|plan|setup|find|grade|improve'; then
    ok "name reads as an action/role (good)"
  else
    flag "name reads as a topic, not an action — prefer the action/role (e.g. 'unit-test-writer', not 'unit-test')"
  fi
fi
echo "  (judge clarity & whether scope is single-purpose by hand)"

# --- Description shape --------------------------------------------------------
section "DESCRIPTION (for invocation)"
if [ -n "$DESC" ]; then
  # The point of a description is INVOCATION: it must say WHEN to reach for the
  # skill (triggers / symptoms / situations), not just what the skill does.
  if printf '%s' "$DESC" | grep -qiE '\bwhen\b'; then
    if printf '%s' "$DESC" | grep -qiE '^use when'; then
      ok "leads with 'Use when' (ideal triggering framing)"
    else
      ok "names triggering conditions ('when ...'); consider leading with 'Use when'"
    fi
  else
    flag "reads as what-it-does, not WHEN to invoke — add triggers, e.g. 'Use when the user asks about X / hits error Y'"
  fi
  [ "${#DESC}" -gt 500 ] && flag "description >500 chars; tighten to triggers only"
  printf '%s' "$DESC" | grep -qiE "(^|[^a-z])(I|I'll|we|our|my)([^a-z]|\$)" \
    && flag "not third person (avoid I/we/our/my)" || true
else
  flag "no description to evaluate"
fi

# --- SKILL.md size (lean?) ---------------------------------------------------
section "SKILL.md SIZE (lean?)"
WORDS=$(wc -w < "$MD" | tr -d ' ')
LINES=$(wc -l < "$MD" | tr -d ' ')
echo "  words: $WORDS   lines: $LINES"
[ "$WORDS" -gt 500 ] && flag "over ~500 words; consider moving detail to references/" || ok "within ~500-word guideline"

# Total lines inside fenced code blocks — large inline code is a script/reference candidate.
CODE_LINES=$(awk '/^```/{f=!f; next} f{c++} END{print c+0}' "$MD")
echo "  fenced-code lines: $CODE_LINES"
[ "$CODE_LINES" -gt 50 ] && flag "lots of inline code; extract to scripts/ or example files"

# --- Preferred structure: overview, inputs, steps, guidelines, output --------
section "STRUCTURE (prefer: overview, inputs, steps, guidelines, output)"
HEADINGS="$(grep -E '^#{1,4} ' "$MD" || true)"
check_section() {
  if printf '%s\n' "$HEADINGS" | grep -qiE "$2"; then ok "$1 section present"; else flag "$1 section missing"; fi
}
check_section "Overview"        'overview|purpose'
check_section "Inputs"          'input|argument|parameter|prerequisite'
check_section "Steps"           'step|workflow|process|procedure|how to'
check_section "Guidelines"      'guideline|principle|rule|best practice|common mistake'
check_section "Output format"   'output|result|report|deliverable'

# --- Bundled assets and whether they're referenced ---------------------------
section "BUNDLED FILES & REFERENCES"
BUNDLED="$(cd "$DIR" && find . -type f ! -name 'SKILL.md' ! -path '*/.git/*' 2>/dev/null | sed 's|^\./||' | sort)"
if [ -z "$BUNDLED" ]; then
  echo "  (no bundled scripts/references/assets)"
  flag "no scripts/ — check Steps for repeatable mechanical actions that could be deterministic scripts"
  flag "no references/ — check for heavy inline content (APIs, long tables) that belongs in a reference file"
else
  BODY="$(awk 'NR==1 && $0=="---"{f=1;next} f && $0=="---"{f=0;next} !f{print}' "$MD")"
  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    base="$(basename "$rel")"
    if printf '%s' "$BODY" | grep -qF "$rel" || printf '%s' "$BODY" | grep -qF "$base"; then
      ok "referenced: $rel"
    else
      flag "ORPHAN (bundled but not mentioned in SKILL.md): $rel"
    fi
  done <<EOF
$BUNDLED
EOF
  # Determinism hint for scripts.
  # Bracketed chars (da[t]e, [$]RANDOM, uuid[4]) keep these patterns matching real
  # usages while preventing this detector line from matching its own source.
  for s in $(printf '%s\n' "$BUNDLED" | grep -E '\.(sh|py|js)$' || true); do
    if grep -qE 'da[t]e \+%|[$]RANDOM|Math[.]random|datetime[.]now|Date[.]now|uuid[g]en|uuid[4]' "$DIR/$s" 2>/dev/null; then
      flag "script may be non-deterministic (time/random): $s"
    fi
  done
fi

section "SUMMARY"
echo "  Flags above are improvement leads, not failures. Hand them to SKILL.md (Steps)"
echo "  for prioritization and concrete rewrites."
