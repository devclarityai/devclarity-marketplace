# Skill Authoring Reference

Condensed from Anthropic's [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), plus additions not in that guide (the subagents section and the anti-patterns that follow from it). Follow this when scaffolding the skill in Step 7.

## Contents

- Frontmatter rules
- Naming and descriptions
- Conciseness
- Structure and progressive disclosure
- Workflows, checkpoints, and feedback loops
- Degrees of freedom → file types
- Subagents in a generated skill
- Anti-patterns
- Pre-delivery checklist

## Frontmatter rules

- `name`: max 64 chars, lowercase letters, numbers, and hyphens only. The words "anthropic" and "claude" are reserved. Prefer **gerund form**: `migrating-endpoints`, `writing-e2e-tests`.
- `description`: non-empty, max 1024 chars, **third person**, and must say both **what the skill does and when to use it**, including trigger terms the user would actually say. This field alone drives skill selection.

## Naming and descriptions

- Good: `processing-pdfs`, `analyzing-spreadsheets`. Avoid vague names (`helper`, `utils`) and generic ones (`documents`, `data`).
- Description pattern: "*Does X, Y, Z. Use when [task contexts / trigger words].*"

## Conciseness

- **Default assumption: the model is already very smart.** Only include what it doesn't know: domain-specific guardrails, limits, team conventions, anti-patterns. Cut explanations of general concepts and generic best practices.
- Challenge every paragraph: "Does this justify its token cost?"
- Keep the SKILL.md body **under 500 lines**, and well under where you can. Use **consistent terminology** throughout (one term per concept).

## Structure and progressive disclosure

- SKILL.md is a table of contents that points to detail loaded on demand.
- **References one level deep only.** Every reference file links directly from SKILL.md, because the model may read nested references only partially.
- Reference files **over 100 lines get a table of contents** at the top so partial reads can navigate.
- Organize references by domain (`references/finance.md`, not `docs/file2.md`), and name files descriptively.
- Every-run content lives in SKILL.md, and some-runs content lives in `references/`.

## Workflows, checkpoints, and feedback loops

- Break complex tasks into sequential steps with a **copyable checklist** at the top that the model checks off as it goes.
- Mark human checkpoints with explicit **`-> STOP`** markers stating what to share and what to ask.
- Build **feedback loops**: run validator → fix errors → repeat, and only proceed when the check passes.
- For conditional paths, use explicit decision points: "Creating new? → workflow A. Editing existing? → workflow B."

## Degrees of freedom → file types

| Freedom | Provide | Lives in |
|---|---|---|
| High | Prose heuristics, ordered steps | SKILL.md |
| Medium | Templates, pseudocode, 2-3 input→output example pairs | `assets/` |
| Low | Exact scripts ("run exactly this, don't modify"), strict templates | `scripts/`, `assets/` |
| Any, delegated | A subagent prompt: task, inputs by absolute path, return shape and length cap, what not to return | `references/` (`assets/` only when the agent's output format is fixed and parsed) |

- Prefer **executing** scripts over reading them: "Run `scripts/parse_results.py`" (only the output consumes tokens, not the code). Say explicitly whether a script is to run or to read as reference.
- Scripts handle their own errors: no magic numbers, no punting failures back to the model.
- For high-stakes batch operations, use **plan-validate-execute**: write a plan file, validate it with a script, then apply.

## Subagents in a generated skill

Where the design resolved a seam to an in-skill subagent, this is what gets written.

- **Try a script first.** A script that filters output removes the reason for the agent.
- **Name the agent type and the count in SKILL.md** (a read-only search agent for search where the tool has one, a general agent otherwise), and spawn parallel agents **in one message**.
- **One agent per dimension or lens, never one per section of the input.** A section-scoped reviewer cannot see a pattern that only exists across the whole artifact.
- **Give inputs as absolute paths**, enumerated explicitly, and say not to error on missing ones. Where withholding context is the point, say what the agent may not see and why.
- **State the return shape and a length cap in every prompt.** The returned message *is* the deliverable, and an uncapped agent returns unpredictable prose into the context the agent was meant to protect.
- **Say what not to return:** no rewrites, no raw payload quoted back, no proposals outside its remit. Reviewer prompts end with a verbatim line to the effect of "Do not edit the file. Return a findings report only."
- **Ask each agent to say what it checked**, so an empty findings list is distinguishable from an agent that never looked.
- **Read-only reviewers, one editor.** The orchestrator synthesizes and is the only writer. Never paste raw agent output to the user.
- **Count an agent that did not run as an unmet check**, and say it did not run.
- **Long prompts, or several agents, go to `references/agent-prompts.md`**: shared rules first, one `##` section per agent, a TOC if it passes 100 lines. A short single prompt can sit inline in the step. Prompts belong in `references/`, not `assets/`, because a prompt is read and adapted by the model, which is what a reference is. Put a file in `assets/` only when the agent's output has a fixed format the orchestrator parses.
- **No agent definition file by default** (`.claude/agents/` or your tool's equivalent). Write one only for reuse across skills, a tool list that must be *enforced* rather than requested, or standalone invocability, and propose it to the user's project the way project-instructions additions are proposed. A bare skill directory can't install an agent definition into someone's repo, though a plugin that bundles both can.

## Anti-patterns

- **Emojis: never use them anywhere in drafted skill files** (SKILL.md, references, assets, scripts). Use plain-text markers instead: `-> STOP`, `FAILED:`, `[ ]`.
- Time-sensitive content ("before August 2025 use the old API"): use a collapsed "old patterns" section instead.
- Offering many alternatives: provide one default plus an escape hatch.
- Windows-style paths: forward slashes always.
- Assuming packages are installed: state dependencies explicitly.
- **A subagent doing what a script could do:** parsing logs, test output, a CSV.
- **An agent per phase:** a fan-out across phases that share context pays the isolation cost for nothing.
- **A subagent with no stated return shape or length cap:** the summary comes back into the context the agent was meant to protect.

## Pre-delivery checklist

- [ ] Description: what + when, third person, includes trigger terms
- [ ] SKILL.md body under 500 lines, and as short as the job allows, with some-runs detail moved to `references/`
- [ ] References one level deep, and reference files over 100 lines have a TOC
- [ ] Checklist workflow with explicit `-> STOP` checkpoints
- [ ] No emojis anywhere in the generated files
- [ ] At least one verification or feedback loop
- [ ] Every spawned subagent names its type, its inputs by absolute path, its return shape with a length cap, and what it must not return
- [ ] Parallel agents are spawned in one message, one per dimension, read-only, with the orchestrator as the only editor
- [ ] Any agent definition file is proposed to the user's project, not written inside the skill directory
- [ ] Every generated file traces back to an interview decision, nothing speculative
- [ ] Suggest testing on a real task in a fresh session before sharing
