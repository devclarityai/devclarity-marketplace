"""The PR description and the verdict comment, rendered from and checked against their templates."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dcspecs as d  # noqa: E402

H = [sys.executable, os.path.join(ROOT, "scripts", "dcspecs.py")]
HEAD = "b0109b572f5cc67680e91a28d0ab9eb95db98d71"
PARENT = "8de76a0c1d2e3f405162738495a6b7c8d9e0f1a2"
URL = "https://example.test/issues/6"

MOCKUPS = """## TUI mockups

<!-- - Slide 9: <state> -->

- Slide 1: slotting a task - keys `jjj`, `p` - split, 154 columns

![Slide 1: slotting](https://example.test/mock1.png)

- Slide 2: task list focused - keys `p`, `esc` - split, 154 columns

"""

FEATURE = """# Plan a whole day

## Intent

Slot a day's tasks in one sitting.

## User-facing behavior

A plan view.

""" + MOCKUPS + """## Constraints

No live calendar in tests.

## Acceptance criteria

- AC1 Given the queue with a task under the cursor, when p is pressed, then the plan view opens with that task.
- AC2 Given the plan view on a future day, when it renders, then the task list shows the tasks due that day.
- AC3 [billing-api] Given a slotted task, when it is written, then billing records it.

## Out of scope

Moving meetings.

## Amendments

- 2026-09-29 AC2: due means the task's own date (answered by Parker)
"""

BUGFIX = """# Double reminder after DST

## Reproduction

- R1 Given a check-in due the day after DST ends, when the job runs, then two reminders go out.

## Expected behavior

One reminder.

## Acceptance criteria

- AC1 Given the fix is in place, when the R1 reproduction test runs, then it passes.
- AC2 Given a check-in on an ordinary day, when the job runs, then one reminder goes out.

## Amendments
"""

REFACTOR = """# Split the reminder job

## Behavior preserved

No user-visible change.

## Acceptance criteria

- AC1 Given the existing jobs suite, when it runs against the refactored code, then every test passes.

## Amendments
"""

FILL = {"<one of: pass, fail, not verified>": "pass", "<test name>": "TestX", "<path>": "x_test.go",
        "<the assertion that proves the then clause, and why>": "asserts the row", "<command>": "go test ./...",
        "<the rendered still>": "![still](https://example.test/still.png)", "<the criteria it shows>": "AC1",
        "<slide mockup>": "![mock](https://example.test/m.png)", "<parent commit, or the fix reverted>": PARENT[:7],
        "<head commit>": HEAD[:7], "<base commit>": PARENT[:7], "<result>": "12 passed",
        "<link to the CI run for the head commit>": "https://example.test/actions/runs/1",
        "- <constraint>: <how it was kept>": "None", "- <decision>: <what was built instead, and why>": "None",
        "- <file>: <why it changed>": "None"}


def repo():
    """A temp git repo with a GitHub-source config, as (root, cfg)."""
    root = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q", "-b", "main", root], check=True)
    d.init_config(root, d.build_config("github", "spec:approved", repo="acme/app"), False, False)
    return root, d.load_config(os.path.join(root, "specs", "config.yaml"))


def fill(body, values=FILL):
    """Replace each placeholder in values with its text."""
    for hole, value in values.items():
        body = body.replace(hole, value)
    return body


def errs(res):
    """A check result's errors, one per line, for assertion messages."""
    return "\n".join(res["errors"])


class EvidenceTemplates(unittest.TestCase):
    """Checking evidence templates."""
    def test_defaults_are_valid_and_paired(self):
        _, cfg = repo()
        self.assertEqual(sorted(d.list_templates(cfg, evidence=True)), ["bugfix", "feature", "refactor"])
        for t in d.template_list(cfg):
            self.assertEqual((t["evidence"]["name"], t["evidence"]["paired"], t["evidence"]["errors"]),
                             (t["name"], True, []))

    def test_check_rules(self):
        with open(os.path.join(ROOT, "templates", "bugfix.evidence.md")) as f:
            good = f.read()
        self.assertEqual(d.template_errors(good, "bugfix", True), [])
        for text, want in ((good.replace("version: 2\n", ""), "version must be"),
                           (good.replace("<each criterion>", "AC1"), "'<each criterion>' row"),
                           (good, "must match the file name")):
            self.assertTrue(any(want in e for e in d.template_errors(text, "other" if want.startswith("must") else
                                                                    "bugfix", True)), want)

    def test_a_template_without_evidence_falls_back(self):
        root, cfg = repo()
        os.makedirs(os.path.join(root, "specs", "templates"))
        with open(os.path.join(root, "specs", "templates", "qa-plan.md"), "w") as f:
            f.write("---\nname: qa-plan\ndescription: A QA plan\n---\n## Acceptance criteria\n\n"
                    "- AC1 Given a, when b, then c.\n\n## Amendments\n")
        t = {t["name"]: t for t in d.template_list(cfg)}["qa-plan"]
        self.assertEqual((t["evidence"]["name"], t["evidence"]["paired"]), ("feature", False))
        levels = {c["check"]: c["level"] for c in d.setup_check(cfg)["checks"]}
        self.assertEqual(levels["evidence template for 'qa-plan'"], "warning")
        qa = "---\nid: SPEC-3\ntitle: QA\ntemplate: qa-plan\nstatus: approved\n---\n## Acceptance criteria\n\n" \
             "- AC1 Given a, when b, then c.\n\n## Amendments\n"
        self.assertEqual(d.render_evidence(cfg, qa)["template"], "feature")


class RenderEvidence(unittest.TestCase):
    """Rendering the PR description from a spec and its evidence template."""
    def setUp(self):
        _, self.cfg = repo()

    def test_header_rows_slides_and_conditional_sections(self):
        body = d.render_evidence(self.cfg, FEATURE, spec_id="#6", url=URL, repo_tag="app")["body"]
        self.assertTrue(body.startswith("## Spec evidence: #6 Plan a whole day\n"))
        self.assertIn(f"frozen at fingerprint `{d.fingerprint(FEATURE)}` · 1 amendment", body)
        self.assertIn("**Evidence template:** `feature` v2\n**CI:** " + d.P_CI, body)
        self.assertIn("| AC3 [billing-api] | other repo | - | - | - |", body)
        self.assertIn("| 1. slotting a task | ![Slide 1: slotting](https://example.test/mock1.png) |", body)
        self.assertIn("| 2. task list focused | <slide mockup> |", body)
        self.assertNotIn("| 9.", body)                   # a commented slide is not a slide
        self.assertIn("### Constraints", body)
        self.assertNotIn("### Deviations", body)         # the spec has no Technical approach
        self.assertNotIn("<!--", body)
        no_slides = d.render_evidence(self.cfg, FEATURE.replace(MOCKUPS, ""))["body"]
        self.assertNotIn("### Visual evidence", no_slides)

    def test_template_is_inferred(self):
        self.assertEqual(d.render_evidence(self.cfg, FEATURE)["template"], "feature")
        self.assertEqual(d.render_evidence(self.cfg, BUGFIX)["template"], "bugfix")
        self.assertEqual(d.render_evidence(self.cfg, REFACTOR)["template"], "refactor")
        md = "---\nid: SPEC-1\ntitle: T\ntemplate: refactor\nstatus: approved\n---\n" + FEATURE
        self.assertEqual(d.render_evidence(self.cfg, md)["template"], "refactor")

    def test_merge_carries_filled_rows_and_ci(self):
        old = fill(d.render_evidence(self.cfg, FEATURE, url=URL, repo_tag="app")["body"])
        amended = FEATURE.replace("(answered by Parker)", "(answered by Parker)\n- 2026-09-30 AC1: x (answered by P)")
        res = d.render_evidence(self.cfg, amended, url=URL, repo_tag="app", merge=old)
        self.assertIn("· 2 amendments", res["body"])
        self.assertIn("| AC1 | pass | `TestX`", res["body"])
        self.assertIn("**CI:** https://example.test/actions/runs/1", res["body"])
        self.assertIn("AC1", res["carried"])
        self.assertTrue(d.evidence_check(self.cfg, amended, res["body"])["ok"])

    def test_refuses_a_changed_spec(self):
        with self.assertRaises(d.SpecError):
            d.render_evidence(self.cfg, FEATURE, frozen="000000000000")


class EvidenceCheck(unittest.TestCase):
    """Checking a filled-in PR description against its template and the spec."""
    def setUp(self):
        _, self.cfg = repo()
        self.ev = fill(d.render_evidence(self.cfg, FEATURE, url=URL, repo_tag="app")["body"])

    def check(self, body, spec=FEATURE, **kw):
        return d.evidence_check(self.cfg, spec, body, **kw)

    def row(self, key):
        return next(l for l in self.ev.split("\n") if l.startswith(f"| {key}"))

    def test_filled_evidence_passes(self):
        res = self.check(self.ev, repo_tag="app", frozen=d.fingerprint(FEATURE))
        self.assertTrue(res["ok"], errs(res))
        self.assertEqual(res["counts"], {"pass": 2, "fail": 0, "not verified": 0, "other repo": 1})

    def test_rows(self):
        a1, a2 = self.row("AC1 "), self.row("AC2 ")
        cases = {
            "the Test cell is blank": self.ev.replace(a1, "| AC1 | pass | - | x | `go test` |"),
            "Result must be one of": self.ev.replace("| AC1 | pass |", "| AC1 | passed |"),
            "no row for AC2": self.ev.replace(a2 + "\n", ""),
            "AC1 has more than one row": self.ev.replace(a2, a1),
            "not in spec order": self.ev.replace(a1, "@").replace(a2, a1).replace("@", a2),
            "the AC1 row needs 5 cells": self.ev.replace(a1, "| AC1 | pass | x |"),
            "no row for 2": self.ev.replace(self.row("2. ") + "\n", ""),
        }
        for want, body in cases.items():
            self.assertIn(want, errs(self.check(body)), want)

    def test_other_repo(self):
        self.assertIn("tagged for this repo", errs(self.check(self.ev, repo_tag="billing-api")))
        self.assertIn("only for criteria tagged", errs(self.check(self.ev.replace(
            self.row("AC1 "), "| AC1 | other repo | - | - | - |"))))

    def test_header_sections_and_placeholders(self):
        cases = {
            "the spec has 1": self.ev.replace("· 1 amendment", "· 0 amendments"),
            "run evidence render --merge": self.ev.replace("`feature` v2", "`feature` v1"),
            "'**CI:**'": self.ev.replace("**CI:** https://example.test/actions/runs/1", ""),
            "missing section: Constraints": self.ev.replace("### Constraints", "### Other"),
            "section is empty: Outside the spec's scope": self.ev.replace(
                "### Outside the spec's scope\n\nNone", "### Outside the spec's scope\n"),
            "placeholder left in: <file>": self.ev.replace("### Outside the spec's scope\n\nNone",
                                                           "### Outside the spec's scope\n\n- <file>: x"),
        }
        for want, body in cases.items():
            self.assertIn(want, errs(self.check(body)), want)
        self.assertIn("the spec's is", errs(self.check(self.ev, spec=FEATURE.replace("future", "later"))))

    def test_fixed_rows(self):
        bug = fill(d.render_evidence(self.cfg, BUGFIX, url=URL)["body"])
        self.assertTrue(self.check(bug, spec=BUGFIX)["ok"], errs(self.check(bug, spec=BUGFIX)))
        self.assertIn("Result must be fail", errs(self.check(bug.replace(f"{PARENT[:7]} | fail", f"{PARENT[:7]} | pass"),
                                                             spec=BUGFIX)))
        self.assertIn("no row for adjacent behavior", errs(self.check(
            "\n".join(l for l in bug.split("\n") if not l.startswith("| Adjacent")), spec=BUGFIX)))
        ref = fill(d.render_evidence(self.cfg, REFACTOR, url=URL)["body"])
        self.assertTrue(self.check(ref, spec=REFACTOR)["ok"], errs(self.check(ref, spec=REFACTOR)))


VERDICT_FILL = {"<one of: confirmed, disputed, weak, unverifiable, waived>": "confirmed",
                "<what you broke and that the test then failed, or why it is not confirmed>":
                    "returned early in `plan.go`; the test failed",
                "<one of: matches, differs, no deterministic renderer>": "matches",
                "<files no criterion needs, or None>": "None",
                "<none touched, or which ones and the rows they weaken>": "none touched"}


def verdict(cfg, ev, verdicts=None):
    """A filled-in verdict for FEATURE. Criteria not named in verdicts are confirmed."""
    body = d.render_verdict(cfg, FEATURE, ev, HEAD, spec_id="#6")["body"]
    for cid, v in (verdicts or {}).items():
        body = re.sub(rf"^\| {cid} \| <one of: [^>]+>", f"| {cid} | {v}", body, flags=re.M)
    body = fill(body, VERDICT_FILL)
    found = [c for c in ("AC1", "AC2") if f"| {c} |" in body]
    return body.replace("**Result:** <overall>", d.result_line(
        [(verdicts or {}).get(c, "confirmed") for c in found] + ["other repo"]))


class Verdict(unittest.TestCase):
    """Rendering and checking verdict comments."""
    def setUp(self):
        _, self.cfg = repo()
        self.ev = fill(d.render_evidence(self.cfg, FEATURE, url=URL, repo_tag="app")["body"])

    def check(self, v, **kw):
        kw.setdefault("evidence", self.ev)
        return d.verdict_check(FEATURE, v, **kw)

    def test_render_pins_head_spec_and_template(self):
        body = d.render_verdict(self.cfg, FEATURE, self.ev, HEAD)["body"]
        self.assertIn(f"**Head commit:** `{HEAD}`", body)
        self.assertIn(f"**Spec:** {URL} · frozen at fingerprint `{d.fingerprint(FEATURE)}` · 1 amendment", body)
        self.assertIn("**Evidence template:** `feature` v2", body)
        self.assertIn("| AC3 [billing-api] | other repo | - |", body)
        self.assertIn("| 1. slotting a task | <one of: matches", body)
        with self.assertRaises(d.SpecError):
            d.render_verdict(self.cfg, FEATURE, self.ev, HEAD[:7])

    def test_filled_verdict_passes_and_the_worst_row_is_the_result(self):
        res = self.check(verdict(self.cfg, self.ev), head=HEAD[:7], frozen=d.fingerprint(FEATURE), repo_tag="app")
        self.assertTrue(res["ok"], errs(res))
        self.assertEqual((res["overall"], res["conclusion"]), ("confirmed", "success"))
        v = verdict(self.cfg, self.ev, {"AC2": "disputed"})
        res = self.check(v)
        self.assertEqual((res["ok"], res["overall"], res["conclusion"]), (True, "disputed", "failure"), errs(res))
        self.assertEqual(d.overall_result(["confirmed", "weak", "unverifiable"]), "weak")
        self.assertIn("the Result line must read: **Result:** disputed",
                      errs(self.check(v.replace("**Result:** disputed", "**Result:** confirmed"))))

    def test_rows_and_pins(self):
        v = verdict(self.cfg, self.ev)
        cases = {
            "the Detail cell is blank": (v.replace("| AC1 | confirmed | returned early in `plan.go`; the test failed |",
                                                   "| AC1 | confirmed | - |"), {}),
            "Verdict must be one of": (v.replace("| AC1 | confirmed |", "| AC1 | pass |"), {}),
            "only a claimed pass can be confirmed": (v, {"evidence": self.ev.replace("| AC1 | pass |", "| AC1 | fail |")}),
            "stale: the verdict audited": (v, {"head": "1234567"}),
            "Evidence template line does not match": (v, {"evidence": self.ev.replace("v2", "v7")}),
            "missing section: Unrequested changes": (v.replace("### Unrequested changes", "### Other"), {}),
        }
        for want, (body, kw) in cases.items():
            self.assertIn(want, errs(self.check(body, **kw)), want)

    def test_waivers(self):
        v = verdict(self.cfg, self.ev, {"AC2": "waived"})
        self.assertIn("AC2: marked waived with no waiver line", errs(self.check(v)))
        ok = v + "\n### Waivers\n\n- AC2: waived by Parker Kain until 2026-10-15 - no DST fixture yet\n"
        res = self.check(ok, today="2026-10-15")                    # the expiry day itself still counts
        self.assertTrue(res["ok"], errs(res))
        self.assertEqual(res["overall"], "confirmed")
        self.assertIn("expired on 2026-10-15", errs(self.check(ok, today="2026-10-16")))
        self.assertIn("not a real YYYY-MM-DD date", errs(self.check(ok.replace("2026-10-15", "2026-13-45"),
                                                                    today="2026-09-29")))
        self.assertIn("waiver not in", errs(self.check(ok.replace(" - no DST fixture yet", ""), today="2026-09-29")))
        stray = verdict(self.cfg, self.ev) + "\n### Waivers\n\n- AC2: waived by P until 2026-10-15 - x\n"
        self.assertIn("its row is not marked waived", errs(self.check(stray, today="2026-09-29")))

    def test_freeze_waiver(self):
        v = verdict(self.cfg, self.ev)
        ok = v + "\n### Waivers\n\n- freeze: waived by Parker Kain until 2026-10-20 - az fails on Windows\n"
        res = self.check(ok, today="2026-10-19")
        self.assertTrue(res["ok"], errs(res))
        self.assertEqual(res["result_line"], self.check(v)["result_line"])
        self.assertIn("freeze waiver expired on 2026-10-20", errs(self.check(ok, today="2026-10-21")))
        bad = errs(self.check(ok.replace(" until 2026-10-20", ""), today="2026-10-19"))
        self.assertIn("- freeze: waived by <name> until YYYY-MM-DD - <reason>", bad)


class VerdictLatest(unittest.TestCase):
    """Finding the latest verdict comment for a PR head."""
    def setUp(self):
        _, self.cfg = repo()
        self.ev = fill(d.render_evidence(self.cfg, FEATURE, url=URL, repo_tag="app")["body"])
        self.v = verdict(self.cfg, self.ev)

    def comments(self, *items):
        return {"comments": [{"body": b, "createdAt": at, "url": f"u{i}"} for i, (b, at) in enumerate(items)]}

    def test_newest_current_verdict_wins(self):
        data = self.comments((self.v, "2026-09-29T10:00:00Z"), ("unrelated", "2026-09-29T09:00:00Z"),
                             (self.v.replace(HEAD, PARENT), "2026-09-29T11:00:00Z"))
        res = d.verdict_latest(data, HEAD, FEATURE, self.ev)
        self.assertEqual((res["latest"]["url"], res["latest"]["overall"]), ("u0", "confirmed"))
        self.assertIn("audited 8de76a0c1d2e", res["verdicts"][1]["stale_because"][0])
        more = FEATURE.replace("(answered by Parker)", "(answered by Parker)\n- 2026-09-30 AC1: x (answered by P)")
        self.assertIsNone(d.verdict_latest(data, HEAD, more)["latest"])
        self.assertIsNone(d.verdict_latest(data, HEAD, FEATURE, self.ev.replace("v2", "v3"))["latest"])


class Cli(unittest.TestCase):
    """The evidence and verdict commands run through the CLI."""
    def test_evidence_and_verdict_commands(self):
        root, cfg = repo()
        spec, ev, com = (os.path.join(root, n) for n in ("spec.md", "ev.md", "c.json"))
        with open(spec, "w") as f:
            f.write(FEATURE)
        run = lambda *a: subprocess.run(H + list(a), cwd=root, capture_output=True, text=True)
        r = run("evidence", "render", "--spec", spec, "--out", ev)
        self.assertEqual(json.loads(r.stdout)["template"], "feature", r.stderr)
        self.assertEqual(run("evidence", "check", "--spec", spec, "--evidence", ev).returncode, 1)
        self.assertIn("## Spec evidence:", run("evidence", "render", "--spec", spec, "--merge", ev).stdout)
        with open(com, "w") as f:
            json.dump([{"body": verdict(cfg, fill(d.render_evidence(cfg, FEATURE)["body"])),
                        "createdAt": "2026-09-29T10:00:00Z"}], f)
        self.assertEqual(run("verdict", "latest", "--comments", com, "--head", HEAD).returncode, 0)
        self.assertEqual(run("verdict", "latest", "--comments", com, "--head", PARENT).returncode, 1)


if __name__ == "__main__":
    unittest.main()
