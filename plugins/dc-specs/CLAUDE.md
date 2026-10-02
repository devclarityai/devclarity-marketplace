# dc-specs - working on the plugin

## The helper

- `scripts/dcspecs.py` runs on Python 3.9 or later, standard library only, on macOS, Linux and Windows. Run the tests with `python3 -m unittest discover -s tests`, and also with `/usr/bin/python3` on a Mac, which is 3.9.
- Launch external tools through `_proc`, never `subprocess.run` directly: it finds `az.cmd` on Windows and decodes output as UTF-8. Open files with `encoding="utf-8"`.
- A new external tool needs an `INSTALL` entry for each OS, a `SOURCE_TOOLS` entry for the source that uses it, and a `deps` test, so `spec-setup` can walk people through installing it.
- Every module-level function and class has a Google-style docstring. A function with 8 or fewer code lines, or a private or `cmd_` function with 15 or fewer, gets one line. Test methods are exempt; their names say what they check.
- Longer docstrings add `Args:` only for parameters whose meaning is not obvious from the name, `Returns:` only for structures (dict keys, tuples, sentinels such as None or ''), and `Raises:` for exceptions raised directly. Never document `cfg`, `a`, or what the summary already says, and keep any paragraph that explains a non-obvious reason.
- Skills never do by eye what the helper can do deterministically (fingerprints, criteria parsing, amendment format, evidence and verdict coverage). Add a helper command rather than prose instructions for anything countable.

## Skills and references

- Rules shared by more than one skill live in `references/framework.md`, not in each SKILL.md.
- Source-specific steps live only in `references/sources/<source>.md`. Skills name operations (Read, Amend, Freeze record); adapters say how.
- Quote a SKILL.md `description` that contains a colon followed by a space.

## Session hook

`hooks/hooks.json` runs `dcspecs.py session-context` at session start, trying `python3`, `python` and `py` in turn.

- It stays silent outside opted-in repos, never exits non-zero, and makes no network calls.
- It prints statements of fact, because imperatives can trip prompt-injection defenses.
- It never echoes text a repo controls, such as config values or branch names. It prints only fixed words, the source, a validated project or team key, and a derived spec id.
- It does not read configs over 64 KB.

## Releasing

- Bump `version` in `.claude-plugin/plugin.json` for every change to shipped files, or `claude plugin update` will not pick it up.
