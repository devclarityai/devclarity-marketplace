"""Unit tests for #24: spec-implement and spec-verify keep the AC process and do the work the repo's way."""
from __future__ import annotations

import json
import os
import re
import unittest

from test_dcspecs import ROOT


def read(*parts):
    """The text of a file under the plugin root."""
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def section(text, start, end):
    """The text between two headings, or to the end when end is None."""
    body = text.split(start, 1)[1]
    return body.split(end, 1)[0] if end else body


def framework_split():
    """The framework's Process and the repo's way section."""
    return section(read("references", "framework.md"), "## Process and the repo's way", "\n## ")


def implement():
    """spec-implement's SKILL.md."""
    return read("skills", "spec-implement", "SKILL.md")


def verify_audit():
    """spec-verify's audit step."""
    return section(read("skills", "spec-verify", "SKILL.md"), "## 2.", "## 3.")


class Framework(unittest.TestCase):
    def test_ac1_dc_specs_owns_the_process(self):
        self.assertIn("dc-specs owns the process: the frozen spec, scope, a plan that covers every criterion, "
                      "the consult loop and amendments, evidence, the verdict and the PR.", framework_split())

    def test_ac2_the_repo_owns_how_the_work_is_done(self):
        self.assertIn("The repo owns how the work is done: branch names, code and test style, frameworks, "
                      "how tests are run, and any skill that covers part of the work.", framework_split())

    def test_ac3_a_repo_skill_never_changes_the_process(self):
        self.assertIn("A repo skill never widens scope, drops a criterion, or changes what counts as evidence "
                      "or how the verdict is reached.", framework_split())


class Branch(unittest.TestCase):
    def step(self):
        return section(implement(), "## 2. Branch", "## 3.")

    def test_ac4_branch_follows_the_repo_convention(self):
        self.assertIn("named by the convention the repo states in its `CLAUDE.md` files, a contributing guide, "
                      "or a skill", self.step())

    def test_ac5_adapter_convention_is_the_fallback(self):
        self.assertIn("When the repo states no convention, use the adapter's.", self.step())

    def test_ac6_adapters_branch_line_is_the_fallback(self):
        for source in ("github", "jira", "linear", "ado"):
            lines = [l for l in read("references", "sources", f"{source}.md").splitlines() if "branch names" in l.lower()]
            self.assertEqual(len(lines), 1, source)
            self.assertTrue(lines[0].startswith("When the repo states no branch convention, branch names"), source)


class Plan(unittest.TestCase):
    def step(self):
        return section(implement(), "## 3. Plan", "## 4.")

    def test_ac7_step_names_the_matching_skill(self):
        self.assertIn("A step names the available skill that covers its kind of work, when one does", self.step())

    def test_ac8_step_with_no_matching_skill_names_none(self):
        self.assertIn("a step with no matching skill names none", self.step())

    def test_ac9_every_criterion_is_covered(self):
        self.assertIn("every criterion covered", self.step())


class Build(unittest.TestCase):
    def step(self):
        return section(implement(), "## 4. Build", "## 5.")

    def test_ac10_each_step_uses_the_named_skill(self):
        self.assertIn("using the skill the plan named for it", self.step())

    def test_ac11_a_skill_does_not_replace_the_process(self):
        self.assertIn("A skill that covers one step, such as adding an endpoint, does not replace the rest of "
                      "the process.", self.step())

    def test_ac12_tests_first_is_not_required(self):
        text = self.step()
        self.assertNotIn("tests first", text.lower())
        self.assertNotIn("see it fail for the right reason", text)
        self.assertIn("Tests may come before or after the code, as the repo works.", text)

    def test_ac13_every_criterion_ends_with_a_passing_test(self):
        self.assertIn("Every criterion ends with a passing test that checks the criterion as written, not the "
                      "code's current behavior.", self.step())

    def test_ac14_bugfix_reproduction_comes_first(self):
        self.assertIn("**Reproduction:** for a bugfix, commit the failing reproduction test on its own before "
                      "the fix", self.step())

    def test_ac15_process_wins_over_a_repo_skill(self):
        self.assertIn("When a repo skill would widen scope, skip a criterion, or change the evidence or the PR, "
                      "follow dc-specs' process.", self.step())

    def test_ac16_unclear_goes_through_the_consult_loop(self):
        self.assertIn("When it is unclear which applies, ask through the consult loop.", self.step())


class Release(unittest.TestCase):
    def test_ac17_description_does_not_say_tests_first(self):
        desc = next(l for l in implement().splitlines() if l.startswith("description:"))
        for phrase in ("tests first", "test first", "before the code", "fail first"):
            self.assertNotIn(phrase, desc.lower())
        self.assertIn("builds each step the repo's way with its own skills and a passing test per criterion", desc)

    def test_ac18_verify_runs_tests_the_repo_way(self):
        self.assertIn("the way the repo says to run tests, using a repo skill or the commands it states",
                      verify_audit())

    def test_ac19_verify_audit_is_unchanged(self):
        text = verify_audit()
        for step in ("1. **Read**", "2. **Run**", "3. **Break it:**"):
            self.assertIn(step, text)
        self.assertIn("never the audit: every criterion is still read, run and broken, and no PR claim is trusted",
                      text)

    def test_ac20_readme_row_does_not_say_test_first(self):
        row = next(l for l in read("README.md").splitlines() if l.startswith("| 4 | `spec-implement`"))
        for phrase in ("test first", "tests first", "before the code", "fail first"):
            self.assertNotIn(phrase, row.lower())
        self.assertIn("Builds it the repo's way, with its own skills and a passing test per criterion", row)

    def test_ac21_version_is_above_0_9_8(self):
        version = json.loads(read(".claude-plugin", "plugin.json"))["version"]
        self.assertGreater(tuple(int(p) for p in re.findall(r"\d+", version)), (0, 9, 8))


if __name__ == "__main__":
    unittest.main()
