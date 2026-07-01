#!/usr/bin/env python3
"""scaffold-evals.py — create an evals/ folder next to a target skill.

Default: scaffolds a behavior eval (does the skill fire, is output valid, is it
in budget):
  cases.md    template cases to edit
  run.py      copy of run-evals.py (python run.py)
  results.md  placeholder

With --classify: scaffolds a classification-gate eval instead (does the skill's
opening classifier route inputs to the right label):
  classify-cases.md    labels + instruction + labeled examples
  classify.py          copy of classify-evals.py (python classify.py)
  classify-results.md  placeholder

Refuses to overwrite an existing *-cases.md unless --force; always refreshes the
runner copy.

Usage:
  scaffold-evals.py <target-skill-dir> [--classify] [--force]
"""
import argparse
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CASES_TEMPLATE = '''# Evals for {skill}

<!--
Each case is a "## Case: <name>" block followed by key: value lines:
  prompt:      (required) the user message sent to `claude -p`
  expect:      fire | quiet   (default: fire) — should this skill activate?
  fired_when:  shell cmd; exit 0 => the skill fired. $EVAL_OUTPUT = captured
               output file. Prefer an observable side-effect over a grep.
  validate:    shell cmd; exit 0 => output is valid (fire cases only)
  budget_s:    duration budget in seconds
Keep 3-5 REAL cases, including at least one "quiet" case. See eval-anatomy.md.
Run:  python run.py            (add --dry-run to check parsing without spending tokens)
-->

## Case: <a should-fire prompt>
prompt: <the real user request that should trigger {skill}>
expect: fire
fired_when: test -f <the artifact the skill produces>
validate: <shell check that the output/artifact is well-formed>
budget_s: 60

## Case: <a related prompt that should NOT trigger>
prompt: <a nearby request the skill should stay quiet on>
expect: quiet
'''

CLASSIFY_TEMPLATE = '''# Classification eval for {skill}

<!--
Test a classification gate: does the skill route/branch inputs to the right label?
  labels:    the allowed labels, comma-separated
  classify:  the gate's decision instruction (copy it from the skill's gate)
Then one "## <label>" block per example — heading = the CORRECT label, body = the
item text. Gather real examples and use their existing labels as ground truth, e.g.
  gh issue list --limit 10 --json title,body,labels
  (or your tracker / an MCP tool)
Run:  python classify.py        (add --dry-run to check parsing without tokens)
-->

labels: <label-a>, <label-b>, <label-c>
classify: <how to decide the label — paste the skill gate's own instruction>

## <label-a>
<a real example that should get label-a>

## <label-b>
<a real example that should get label-b>

## <label-a>
<another real label-a example>
'''

PLACEHOLDER = "# {title}: {skill}\n\n_Not run yet. Run `python {runner}` in this folder._\n"


def write(path, text, force):
    if os.path.exists(path) and not force:
        print(f"kept    {path} (exists; --force to overwrite)")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote   {path}")


def copy_runner(src_name, dst_path):
    src = os.path.join(SCRIPT_DIR, src_name)
    if not os.path.isfile(src):
        raise SystemExit(f"ERROR: runner not found next to me: {src}")
    shutil.copyfile(src, dst_path)
    os.chmod(dst_path, 0o755)
    print(f"wrote   {dst_path}")


def main():
    ap = argparse.ArgumentParser(description="Scaffold an evals/ folder next to a skill.")
    ap.add_argument("target", help="path to the target skill directory (containing SKILL.md)")
    ap.add_argument("--classify", action="store_true", help="scaffold a classification-gate eval instead of a behavior eval")
    ap.add_argument("--force", action="store_true", help="overwrite an existing *-cases.md")
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if not os.path.isdir(target):
        raise SystemExit(f"ERROR: not a directory: {target}")
    if not os.path.isfile(os.path.join(target, "SKILL.md")):
        raise SystemExit(f"ERROR: no SKILL.md in {target} — point me at a skill directory.")

    skill = os.path.basename(target.rstrip("/"))
    evals = os.path.join(target, "evals")
    os.makedirs(evals, exist_ok=True)

    if args.classify:
        write(os.path.join(evals, "classify-cases.md"), CLASSIFY_TEMPLATE.format(skill=skill), args.force)
        copy_runner("classify-evals.py", os.path.join(evals, "classify.py"))
        write(os.path.join(evals, "classify-results.md"),
              PLACEHOLDER.format(title="Classification results", skill=skill, runner="classify.py"), force=False)
        print(f"\nNext: fill {os.path.join(evals, 'classify-cases.md')} with labels + real labeled examples, then `python {os.path.join(evals, 'classify.py')}`.")
    else:
        write(os.path.join(evals, "cases.md"), CASES_TEMPLATE.format(skill=skill), args.force)
        copy_runner("run-evals.py", os.path.join(evals, "run.py"))
        write(os.path.join(evals, "results.md"),
              PLACEHOLDER.format(title="Eval results", skill=skill, runner="run.py"), force=False)
        print(f"\nNext: edit {os.path.join(evals, 'cases.md')} with 3-5 real cases, then `python {os.path.join(evals, 'run.py')}`.")


if __name__ == "__main__":
    main()
