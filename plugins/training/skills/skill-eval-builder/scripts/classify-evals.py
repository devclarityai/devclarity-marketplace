#!/usr/bin/env python3
"""classify-evals.py — test a skill's classification gate against labeled examples.

Many skills open with a classification step: route feature vs bug, or decide
whether to continue at all. This checks that gate: given a label set, the gate's
decision instruction, and a list of examples each tagged with its correct label,
it asks `claude -p` to classify each and reports accuracy + a confusion summary.

The examples file (classify-cases.md) is where the real data goes — hand-written,
or pulled from your tracker (e.g. `gh issue list --json title,body,labels`) with
each item's existing label as ground truth. This script only reads them.

Not a harness: one small script over a labeled list. Runs call a model, so they
vary — that variance is what you're measuring.

Usage:
  classify-evals.py [--cases PATH] [--skill NAME] [--dry-run]
                    [--claude-bin BIN] [--claude-args STR] [--timeout SEC]
"""
import argparse
import os
import re
import shlex
import subprocess
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CASES = os.path.join(SCRIPT_DIR, "classify-cases.md")
WIDE = {"✅", "❌", "⚠"}


def display_width(s):
    return sum(2 if ch in WIDE else 1 for ch in s)


def parse_cases(path):
    """Parse classify-cases.md -> (labels[list], instruction[str], examples[list])."""
    if not os.path.isfile(path):
        raise ValueError(f"cases file not found: {path}")
    labels, instruction, examples = [], "", []
    cur = None
    head_re = re.compile(r"^##\s+(.+?)\s*$")
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        m = head_re.match(line)
        if m:
            cur = {"label": m.group(1).strip().lower(), "text": []}
            examples.append(cur)
            continue
        if cur is not None:
            cur["text"].append(line)
            continue
        # header region (before first '## ')
        low = line.strip().lower()
        if low.startswith("labels:"):
            labels = [x.strip().lower() for x in line.split(":", 1)[1].split(",") if x.strip()]
        elif low.startswith("classify:"):
            instruction = line.split(":", 1)[1].strip()
    if not labels:
        raise ValueError("no `labels:` line found in header")
    if not instruction:
        raise ValueError("no `classify:` instruction found in header")
    for e in examples:
        e["text"] = "\n".join(e["text"]).strip()
        if not e["text"]:
            raise ValueError(f"example labeled '{e['label']}' has no item text")
        if e["label"] not in labels:
            raise ValueError(f"example label '{e['label']}' is not in labels {labels}")
    if not examples:
        raise ValueError("no '## <label>' examples found")
    return labels, instruction, examples


def extract_label(raw, labels):
    """Pick the model's FINAL label decision — robust to self-correction and prose
    (e.g. "feature... wait, that's broken behavior... bug")."""
    out = raw.lower()
    lines = [ln.strip(" \t.`*-:\"'") for ln in out.splitlines() if ln.strip()]
    if lines and lines[-1] in labels:            # clean case: last line is the label
        return lines[-1]
    found = [(out.rfind(lab), lab) for lab in labels
             if re.search(r"\b" + re.escape(lab) + r"\b", out)]
    if found:
        return max(found)[1]                      # last-mentioned label = final verdict
    return "(none)"


def predict(labels, instruction, item, claude_bin, claude_args, timeout):
    prompt = (f"{instruction}\n\nLabels: {', '.join(labels)}\n"
              f"Answer with ONLY the single best label from that set, on its own line, "
              f"with no explanation.\n\nItem:\n{item}")
    with tempfile.NamedTemporaryFile("w+", suffix=".out", delete=False) as tf:
        out_path = tf.name
    try:
        with open(out_path, "w") as fh:
            subprocess.run([claude_bin, "-p", prompt] + claude_args,
                           stdout=fh, stderr=subprocess.DEVNULL, timeout=timeout)
    except FileNotFoundError:
        raise SystemExit(f"ERROR: '{claude_bin}' not found. Install Claude Code or pass --claude-bin.")
    except subprocess.TimeoutExpired:
        os.unlink(out_path)
        return "(timeout)"
    raw = open(out_path, encoding="utf-8", errors="replace").read()
    os.unlink(out_path)
    return extract_label(raw, labels)


def trunc(s, n=34):
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def render(rows, skill, correct, total):
    pct = f"{100 * correct // total}%" if total else "n/a"
    headers = ["Item", "Expected", "Predicted", "OK"]
    widths = [max([display_width(headers[i])] + [display_width(r[i]) for r in rows])
              for i in range(len(headers))]

    def pad(s, w):
        return s + " " * (w - display_width(s))

    def bar(l, m, r):
        return l + m.join("─" * (w + 2) for w in widths) + r

    def line(c):
        return "│ " + " │ ".join(pad(c[i], widths[i]) for i in range(len(c))) + " │"

    out = [f"Classification: {skill} — {correct}/{total} correct ({pct})",
           bar("┌", "┬", "┐"), line(headers), bar("├", "┼", "┤")]
    out += [line(r) for r in rows]
    out.append(bar("└", "┴", "┘"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Test a classification gate against labeled examples.")
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--skill", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--claude-bin", default="claude")
    ap.add_argument("--claude-args", default="")
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    skill = args.skill or os.path.basename(
        os.path.dirname(os.path.dirname(os.path.abspath(args.cases))))
    try:
        labels, instruction, examples = parse_cases(args.cases)
    except ValueError as e:
        raise SystemExit(f"ERROR: {e}")

    rows, correct = [], 0
    if args.dry_run:
        print(f"[dry-run] {len(examples)} example(s), labels={labels}. Not calling claude.\n")
        for e in examples:
            rows.append([trunc(e["text"]), e["label"], "pending", "–"])
    else:
        extra = shlex.split(args.claude_args)
        for e in examples:
            pred = predict(labels, instruction, e["text"], args.claude_bin, extra, args.timeout)
            ok = pred == e["label"]
            correct += ok
            rows.append([trunc(e["text"]), e["label"], pred, "✅" if ok else "❌"])

    table = render(rows, skill, correct, len(examples))
    print(table)

    if not args.dry_run:
        mism = {}
        for e, r in zip(examples, rows):
            if r[3] == "❌":
                mism[f"{e['label']}→{r[2]}"] = mism.get(f"{e['label']}→{r[2]}", 0) + 1
        if mism:
            print("Confusion: " + ", ".join(f"{k} x{v}" for k, v in sorted(mism.items())))
        results_path = os.path.join(os.path.dirname(os.path.abspath(args.cases)), "classify-results.md")
        with open(results_path, "w", encoding="utf-8") as f:
            f.write(f"# Classification results: {skill}\n\n")
            f.write("_Model runs vary; re-run to see stability. Generated by classify.py._\n\n")
            f.write("```\n" + table + "\n```\n")
        print(f"\nSaved to {results_path}")


if __name__ == "__main__":
    main()
