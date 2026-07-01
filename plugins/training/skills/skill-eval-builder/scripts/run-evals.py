#!/usr/bin/env python3
"""run-evals.py — run a skill's eval cases and print a scorecard.

Reads a `cases.md` (see eval-anatomy.md for the format), and for each case:
  - sends `prompt` to the skill's agent via `claude -p` (headless),
  - times the run,
  - decides whether the skill FIRED (its declared side-effect appeared),
  - runs the case's `validate` command on the output,
and prints a scorecard: cases x {Fires?, Valid?, Duration vs budget}. The same
table is written to results.md next to the cases file.

This is intentionally NOT a test harness: it is one small script over a folder
of real cases. Runs are not byte-identical — evaluating a skill means running a
model, and that variance is the thing you are measuring.

Usage:
  run-evals.py [--cases PATH] [--skill NAME] [--dry-run] [--claude-bin BIN]

  --cases PATH    cases file (default: cases.md next to this script)
  --skill NAME    skill name, used for the default fire-detection grep
                  (default: the name of the directory containing evals/)
  --dry-run       parse + validate cases and render the empty scorecard
                  WITHOUT invoking claude (no tokens spent) — use to check
                  your cases file
  --claude-bin    claude executable (default: claude)
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CASES = os.path.join(SCRIPT_DIR, "cases.md")
WIDE = {"✅", "❌", "⚠"}  # these render 2 columns wide but len()==1


def display_width(s):
    return sum(2 if ch in WIDE else 1 for ch in s)


def parse_cases(path):
    """Parse cases.md into a list of dicts. Raises ValueError on bad structure."""
    if not os.path.isfile(path):
        raise ValueError(f"cases file not found: {path}")
    cases, cur = [], None
    field_re = re.compile(r"^([A-Za-z_]+):\s*(.*)$")
    head_re = re.compile(r"^##\s+Case:\s*(.+?)\s*$")
    for lineno, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        m = head_re.match(line)
        if m:
            cur = {"name": m.group(1), "_line": lineno}
            cases.append(cur)
            continue
        if cur is None:
            continue  # preamble before the first case
        stripped = line.lstrip()
        if not line.strip() or stripped.startswith("<!--") or stripped.startswith("#"):
            continue
        fm = field_re.match(line.strip())
        if fm:
            cur[fm.group(1).lower()] = fm.group(2).strip()
    for c in cases:
        if "prompt" not in c:
            raise ValueError(f"case '{c['name']}' (line {c['_line']}) has no `prompt:`")
        c["expect"] = c.get("expect", "fire").lower()
        if c["expect"] not in ("fire", "quiet"):
            raise ValueError(f"case '{c['name']}': expect must be 'fire' or 'quiet'")
        if "budget_s" in c:
            try:
                c["budget_s"] = float(c["budget_s"])
            except ValueError:
                raise ValueError(f"case '{c['name']}': budget_s must be a number")
    if not cases:
        raise ValueError(f"no '## Case:' blocks found in {path}")
    return cases


def sh(cmd, out_path):
    """Run a shell command with EVAL_OUTPUT set to the captured output file.
    Returns True if it exits 0."""
    env = dict(os.environ, EVAL_OUTPUT=out_path)
    return subprocess.run(cmd, shell=True, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def run_case(c, skill_name, claude_bin, claude_args, timeout):
    """Invoke claude on the prompt, then evaluate firing / validity / duration."""
    with tempfile.NamedTemporaryFile("w+", suffix=".out", delete=False) as tf:
        out_path = tf.name
    cmd = [claude_bin, "-p", c["prompt"]] + claude_args
    start = time.monotonic()
    timed_out = False
    try:
        with open(out_path, "w") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.DEVNULL, timeout=timeout)
        rc = proc.returncode
    except FileNotFoundError:
        raise SystemExit(f"ERROR: '{claude_bin}' not found. Install Claude Code or pass --claude-bin.")
    except subprocess.TimeoutExpired:
        rc, timed_out = -1, True
    dur = time.monotonic() - start
    if timed_out:
        os.unlink(out_path)
        return {"fired": False, "valid": False, "dur": dur, "rc": rc, "timeout": True}

    fired_cmd = c.get("fired_when") or f'grep -qi "{skill_name}" "$EVAL_OUTPUT"'
    fired = sh(fired_cmd, out_path)

    valid = None
    if c["expect"] == "fire" and c.get("validate"):
        valid = sh(c["validate"], out_path)

    os.unlink(out_path)
    return {"fired": fired, "valid": valid, "dur": dur, "rc": rc}


def cell_fire(c, r):
    if r is None:
        return "pending"
    if r.get("timeout"):
        return "❌ timeout"
    if c["expect"] == "quiet":
        return "✅ quiet" if not r["fired"] else "❌ fired"
    return "✅" if r["fired"] else "❌"


def cell_valid(c, r):
    if r is None or c["expect"] == "quiet" or r["valid"] is None:
        return "–"
    return "✅" if r["valid"] else "❌"


def cell_dur(c, r):
    if r is None or c["expect"] == "quiet":
        return "–"
    d = f"{r['dur']:.0f}s"
    if "budget_s" in c:
        ok = "✅" if r["dur"] <= c["budget_s"] else "❌"
        return f"{d} / {c['budget_s']:.0f}s {ok}"
    return d


def render(cases, results):
    headers = ["Case", "Fires?", "Valid?", "Duration vs budget"]
    rows = [[c["name"], cell_fire(c, r), cell_valid(c, r), cell_dur(c, r)]
            for c, r in zip(cases, results)]
    widths = [max([display_width(headers[i])] + [display_width(row[i]) for row in rows])
              for i in range(len(headers))]

    def pad(s, w):
        return s + " " * (w - display_width(s))

    def bar(l, m, r):
        return l + m.join("─" * (w + 2) for w in widths) + r

    def line(cells):
        return "│ " + " │ ".join(pad(cells[i], widths[i]) for i in range(len(cells))) + " │"

    out = [bar("┌", "┬", "┐"), line(headers), bar("├", "┼", "┤")]
    out += [line(row) for row in rows]
    out.append(bar("└", "┴", "┘"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Run a skill's eval cases and print a scorecard.")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--skill", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--claude-bin", default="claude")
    ap.add_argument("--claude-args", default="", help="extra args passed to claude, e.g. \"--dangerously-skip-permissions\"")
    ap.add_argument("--timeout", type=int, default=300, help="per-case timeout in seconds (default 300)")
    args = ap.parse_args()

    skill_name = args.skill or os.path.basename(
        os.path.dirname(os.path.dirname(os.path.abspath(args.cases))))

    try:
        cases = parse_cases(args.cases)
    except ValueError as e:
        raise SystemExit(f"ERROR: {e}")

    if args.dry_run:
        results = [None] * len(cases)
        print(f"[dry-run] {len(cases)} case(s) parsed OK from {args.cases}\n")
    else:
        extra = shlex.split(args.claude_args)
        results = [run_case(c, skill_name, args.claude_bin, extra, args.timeout) for c in cases]

    table = render(cases, results)
    print(table)

    results_path = os.path.join(os.path.dirname(os.path.abspath(args.cases)), "results.md")
    with open(results_path, "w", encoding="utf-8") as f:
        f.write(f"# Eval results: {skill_name}\n\n")
        f.write("_Model runs vary; re-run to see stability. Generated by run.py._\n\n")
        f.write("```\n" + table + "\n```\n")
    if not args.dry_run:
        print(f"\nScorecard written to {results_path}")


if __name__ == "__main__":
    main()
