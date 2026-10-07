"""Unit tests for report-issue: the helper's report-env and report-link commands, and the skill's instructions."""
from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import unittest
import urllib.parse

from test_dcspecs import ROOT, d, git_repo, run, without

SKILL = os.path.join(ROOT, "skills", "report-issue", "SKILL.md")
NEW_ISSUE = "https://github.com/devclarityai/devclarity-marketplace/issues/new?"


def configured(source, **opts):
    """A git repo with specs/config.yaml for source, as its path."""
    root, _ = git_repo()
    approval = "spec:approved" if source == "github" else "Approved"
    d.init_config(root, d.build_config(source, approval, **opts), False, False)
    return root


def env_json(cwd, env=None):
    """report-env run in cwd, as (exit code, raw output, parsed JSON)."""
    r = run("report-env", cwd=cwd, env=env)
    return r.returncode, r.stdout, json.loads(r.stdout or "null")


class ReportEnv(unittest.TestCase):
    """report-env: the environment block for an issue, with nothing from the reporter's repo in it."""
    def test_configured_repo_has_versions_and_source_tools(self):
        code, _, res = env_json(configured("github", repo="a/b"))
        self.assertEqual(code, 0)
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            self.assertEqual(res["dc_specs"], json.load(f)["version"])
        self.assertIn(res["os"].split()[0], ("macos", "linux", "windows"))
        self.assertRegex(res["python"], r"^3\.\d+\.\d+")
        self.assertEqual(res["source"], "github")
        self.assertEqual(list(res["tools"]), ["git", "gh"])
        self.assertRegex(res["tools"]["git"], r"^\d+(\.\d+)+$")

    def test_ado_lists_az_and_its_extension(self):
        without(self, "az")
        res = d.report_env({"source": "ado"})
        self.assertEqual(list(res["tools"]), ["git", "az", "azure-devops extension"])
        self.assertEqual(res["tools"]["az"], "not found")

    def test_no_config_exits_0_with_no_source(self):
        root, _ = git_repo()
        code, _, res = env_json(root)
        self.assertEqual(code, 0)
        self.assertIsNone(res["source"])
        self.assertEqual(list(res["tools"]), ["git"])

    def test_invalid_config_counts_as_none(self):
        root, _ = git_repo()
        os.makedirs(os.path.join(root, "specs"))
        with open(os.path.join(root, "specs", "config.yaml"), "w", encoding="utf-8") as f:
            f.write("source: jira\n")
        code, _, res = env_json(root)
        self.assertEqual((code, res["source"]), (0, None))

    def test_config_values_never_appear(self):
        cases = [("github", {"repo": "secretorg/secretrepo"}, ["secretorg", "secretrepo"]),
                 ("jira", {"site": "hush.atlassian.net", "project": "HUSHKEY", "issue_type": "Story"},
                  ["hush", "HUSHKEY"]),
                 ("ado", {"org": "quietorg", "project": "Quiet Project", "work_item_type": "Bug"},
                  ["quietorg", "Quiet Project", "dev.azure.com"]),
                 ("linear", {"team": "MUTE"}, ["MUTE"])]
        for source, opts, secrets in cases:
            _, out, res = env_json(configured(source, **opts))
            self.assertEqual(res["source"], source)
            for s in secrets:
                self.assertNotIn(s.lower(), out.lower(), source)
            self.assertNotIn("http", out)

    @unittest.skipIf(os.name == "nt", "fake tools are shell scripts")
    def test_no_paths_for_tools_under_home(self):
        home = os.path.realpath(tempfile.mkdtemp())
        bindir = os.path.join(home, "bin")
        os.makedirs(bindir)
        path = os.path.join(bindir, "gh")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"#!/bin/sh\necho 'gh version 2.101.0 (installed at {path})'\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        root = configured("github", repo="a/b")
        env = dict(os.environ, HOME=home, PATH=bindir + os.pathsep + os.environ["PATH"])
        code, out, res = env_json(root, env)
        self.assertEqual(code, 0)
        self.assertEqual(res["tools"]["gh"], "2.101.0")
        self.assertNotIn(home, out)
        self.assertNotIn(root, out)
        for value in [res["os"], res["python"], *res["tools"].values()]:
            self.assertNotRegex(value, r"[/\\]")


class ReportLink(unittest.TestCase):
    """report-link: the prefilled new-issue link the skill falls back to without gh."""
    def body_file(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def link(self, label, body):
        r = run("report-link", "--title", "dc-specs 0.9.7: lint & status fail", "--label", label,
                "--body-file", self.body_file(body))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_short_body_is_prefilled(self):
        body = "**What happens:** `H status 4` fails with ≥ in the body\n"
        res = self.link("bug", body)
        self.assertTrue(res["url"].startswith(NEW_ISSUE))
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)
        self.assertEqual((q["title"], q["labels"], q["body"]), (["dc-specs 0.9.7: lint & status fail"], ["bug"], [body]))
        self.assertTrue(res["body_in_link"])
        self.assertNotIn("body", res)

    def test_long_body_leaves_the_link_and_is_shown_to_paste(self):
        body = "x é " * 3000
        res = self.link("enhancement", body)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(res["url"]).query)
        self.assertEqual((q["title"], q["labels"]), (["dc-specs 0.9.7: lint & status fail"], ["enhancement"]))
        self.assertNotIn("body", q)
        self.assertFalse(res["body_in_link"])
        self.assertEqual(res["body"], body)
        self.assertLessEqual(len(res["url"]), d.REPORT_LINK_LIMIT)

    def test_limit_is_8000(self):
        self.assertEqual(d.REPORT_LINK_LIMIT, 8000)
        url = d.report_link("t", "bug", "")["url"]
        room = d.REPORT_LINK_LIMIT - len(url) - len("&body=")
        self.assertTrue(d.report_link("t", "bug", "a" * room)["body_in_link"])
        self.assertFalse(d.report_link("t", "bug", "a" * (room + 1))["body_in_link"])

    def test_only_bug_and_enhancement_labels(self):
        r = run("report-link", "--title", "t", "--label", "spec:approved", "--body-file", self.body_file("b"))
        self.assertEqual(r.returncode, 2)


def skill_text():
    """SKILL.md split into frontmatter and its numbered steps, as (frontmatter, {step number: text})."""
    with open(SKILL, encoding="utf-8") as f:
        text = f.read()
    _, front, body = text.split("---\n", 2)
    steps = dict(re.findall(r"^## (\d+)\. [^\n]*\n(.*?)(?=^## |\Z)", body, re.M | re.S))
    return front, {int(k): " ".join(v.split()) for k, v in steps.items()}, " ".join(body.split())


class ReportIssueSkill(unittest.TestCase):
    """The report-issue SKILL.md says what the spec's criteria require, in the step that does it."""
    @classmethod
    def setUpClass(cls):
        cls.front, cls.steps, cls.body = skill_text()

    def step(self, title_word):
        with open(SKILL, encoding="utf-8") as f:
            n = re.search(r"^## (\d+)\. " + title_word, f.read(), re.M)
        self.assertIsNotNone(n, title_word)
        return self.steps[int(n.group(1))]

    def test_frontmatter(self):
        self.assertRegex(self.front, r"(?m)^name: report-issue$")
        desc = re.search(r"(?m)^description: (.*)$", self.front).group(1)
        for want in ("dc-specs", "bug", "feature request", "GitHub issue", '"report issue"'):
            self.assertIn(want, desc)

    def test_runs_without_config(self):
        self.assertIn("does not need specs/config.yaml", self.body)

    def test_other_plugins_are_turned_away(self):
        s = self.step("Triage")
        self.assertIn("files dc-specs issues only", s)
        self.assertIn("training", s)
        self.assertIn("create nothing", s)

    def test_dedupe_searches_open_and_closed_twice(self):
        s = self.step("Dedupe")
        self.assertIn("--repo devclarityai/devclarity-marketplace --state all", s)
        self.assertIn("at least twice, with different phrasings", s)

    def test_duplicate_that_adds_nothing_stops(self):
        s = self.step("Dedupe")
        self.assertIn("adds nothing", s)
        self.assertIn("its number and state, and stop. Write nothing.", s)

    def test_duplicate_that_adds_something_gets_a_comment(self):
        s = self.step("Dedupe")
        self.assertIn("adds something new", s)
        self.assertIn("draft a comment on it instead of a new issue", s)

    def test_draft_has_environment_and_failing_command(self):
        s = self.step("Draft")
        self.assertIn("`H report-env`", s)
        self.assertIn("## Environment", s)
        self.assertIn("the failing command and its error text", s)

    def test_client_data_is_redacted(self):
        s = self.step("Keep client data out")
        for word in ("spec text", "file paths", "repo or org names", "tracker project keys", "URLs",
                     "config values", "unless the reporter typed it"):
            self.assertIn(word, s)
        self.assertIn("`<path>`", s)
        self.assertIn("`<repo>`", s)
        self.assertIn("say in the draft what was redacted", s)

    def test_title_and_label(self):
        s = self.step("Title and label")
        self.assertIn("`dc-specs <version>: `", s)
        self.assertIn("`dc_specs` from `H report-env`", s)
        self.assertIn("`bug` for a bug", s)
        self.assertIn("`enhancement` for a feature request", s)
        self.assertIn("no other label", s)

    def test_confirm_shows_everything_and_waits(self):
        s = self.step("Confirm")
        self.assertIn("full title, label and body", s)
        self.assertIn("which parts are guesses", s)
        self.assertIn("Until the reporter says yes, create no issue and post no comment", s)

    def test_files_and_reads_back(self):
        s = self.step("File")
        self.assertIn("gh issue create --repo devclarityai/devclarity-marketplace", s)
        self.assertIn("gh issue view", s)
        self.assertIn("give the reporter the URL it returns", s)

    def test_fallback_uses_report_link(self):
        s = self.step("Fallback")
        self.assertIn("gh is missing, not logged in", s)
        self.assertIn("`H report-link --title", s)
        self.assertIn("`body_in_link` is false", s)
        self.assertIn("show `body` for the reporter to paste", s)


class ReportIssueDocs(unittest.TestCase):
    """The framework's helper table and the plugin README name the new commands and skill."""
    def test_framework_lists_the_commands(self):
        with open(os.path.join(ROOT, "references", "framework.md"), encoding="utf-8") as f:
            rows = [l for l in f if l.startswith("| `")]
        self.assertTrue(any(r.startswith("| `report-env`") for r in rows))
        self.assertTrue(any(r.startswith("| `report-link ") for r in rows))

    def test_readme_section(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            text = f.read()
        section = re.search(r"^## Reporting a problem\n(.*?)(?=^## )", text, re.M | re.S)
        self.assertIsNotNone(section)
        self.assertIn("`report-issue`", section.group(1))
        self.assertNotIn("The six skills", text)


if __name__ == "__main__":
    unittest.main()
