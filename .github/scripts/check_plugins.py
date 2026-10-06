#!/usr/bin/env python3
"""Check the marketplace's plugins: manifests, skill frontmatter and, on a PR, version bumps.

Usage:
  check_plugins.py                 manifests and skills
  check_plugins.py --base <ref>    also require a plugin.json version bump for each plugin the diff touches
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Changes here do not ship anything new to someone who installs the plugin.
NO_BUMP_NEEDED = re.compile(r"^plugins/[^/]+/(tests/|README\.md$|\.gitignore$)")

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"::error::{msg}")


def load_json(rel: str):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"{rel}: {e}")
        return None


def frontmatter(path: str) -> dict[str, str] | None:
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return None


def check_plugin(name: str, source: str) -> None:
    plugin_dir = os.path.normpath(os.path.join(ROOT, source))
    rel_dir = os.path.relpath(plugin_dir, ROOT)
    manifest = load_json(os.path.join(rel_dir, ".claude-plugin", "plugin.json"))
    if manifest is None:
        return
    if manifest.get("name") != name:
        fail(f"{rel_dir}/.claude-plugin/plugin.json: name is {manifest.get('name')!r}, marketplace says {name!r}")
    if not re.match(r"^\d+\.\d+\.\d+$", str(manifest.get("version", ""))):
        fail(f"{rel_dir}/.claude-plugin/plugin.json: version {manifest.get('version')!r} is not x.y.z")

    skills_dir = os.path.join(plugin_dir, "skills")
    if not os.path.isdir(skills_dir):
        return
    for skill in sorted(os.listdir(skills_dir)):
        skill_md = os.path.join(skills_dir, skill, "SKILL.md")
        rel = os.path.relpath(skill_md, ROOT)
        if not os.path.isfile(skill_md):
            fail(f"{rel}: missing")
            continue
        fm = frontmatter(skill_md)
        if fm is None:
            fail(f"{rel}: no YAML frontmatter between '---' lines")
            continue
        if fm.get("name") != skill:
            fail(f"{rel}: name is {fm.get('name')!r}, folder is {skill!r}")
        if not NAME_RE.match(skill):
            fail(f"{rel}: folder name {skill!r} must be lowercase letters, digits and hyphens")
        if not fm.get("description"):
            fail(f"{rel}: missing description")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def check_version_bumps(base: str, plugins: dict[str, str]) -> None:
    changed = git("diff", "--name-only", f"{base}...HEAD").split()
    for name, source in plugins.items():
        rel_dir = os.path.relpath(os.path.normpath(os.path.join(ROOT, source)), ROOT)
        touched = [f for f in changed if f.startswith(rel_dir + "/") and not NO_BUMP_NEEDED.match(f)]
        if not touched:
            continue
        manifest_rel = f"{rel_dir}/.claude-plugin/plugin.json"
        try:
            old = json.loads(git("show", f"{base}:{manifest_rel}")).get("version")
        except subprocess.CalledProcessError:
            continue
        new = (load_json(manifest_rel) or {}).get("version")
        if old == new:
            fail(f"{manifest_rel}: {name} changed ({touched[0]}{' and more' if len(touched) > 1 else ''}) but version is still {old}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="git ref the PR merges into, such as origin/main")
    args = ap.parse_args()

    marketplace = load_json(".claude-plugin/marketplace.json") or {}
    plugins = {p["name"]: p["source"] for p in marketplace.get("plugins", []) if "name" in p and "source" in p}
    for name, source in plugins.items():
        if not os.path.isdir(os.path.join(ROOT, source)):
            fail(f".claude-plugin/marketplace.json: {name} source {source} does not exist")
            continue
        check_plugin(name, source)

    listed = {os.path.basename(os.path.normpath(s)) for s in plugins.values()}
    for d in sorted(os.listdir(os.path.join(ROOT, "plugins"))):
        if os.path.isdir(os.path.join(ROOT, "plugins", d)) and d not in listed:
            fail(f"plugins/{d}: not listed in .claude-plugin/marketplace.json")

    if args.base:
        check_version_bumps(args.base, plugins)

    print(f"{len(errors)} error(s)" if errors else "ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
