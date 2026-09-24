---
name: designing-ai-workflows
description: Interviews the user through the design of a new AI-enabled workflow. Frames it, drafts a skeleton early, then refines context, freedom, alignment, verification, and feedback phase by phase, including where the context window resets (same thread, a script, an in-skill subagent, or a separate skill) and where to fan out parallel agents. Scaffolds the result as one or more skills plus a living design-summary HTML with a visual flow map. Use when the user wants to design or build a new workflow or skill for a task type (integrations, modernization, maintenance, testing, incident triage, etc.), asks when to use subagents versus separate skills, or asks to be interviewed about a workflow.
---

# Designing AI Workflows

Interview the user through the design of a new AI-enabled workflow, then scaffold it as one or more skills. **Draft early and refine iteratively with the user.** Ask the high-level questions, show a draft skeleton, then sharpen each part in context. Don't gather everything up front: users react better to a draft than to a long list of abstract questions.

Before starting, read [references/design-questions.md](references/design-questions.md). It holds the trade-offs, recommendation heuristics, and examples behind each design area.

Terms are tool-neutral. **Project instructions** is the always-loaded file (`AGENTS.md`, `CLAUDE.md`, or your tool's equivalent). A **fresh session** is a cleared context or a new chat (`/clear` in Claude Code). A **structured question** is your tool's multiple-choice prompt (AskUserQuestion in Claude Code). Where there is none, ask in plain conversation.

## Interview rules

- **Topic first.** Get the topic or use case before planning any other questions, so every later question can be pointed at the domain.
- **Design the workflow, not the tech.** Skip technical details (language pairs, framework versions, system internals) unless the answer changes the workflow's design. The unit of work changes the design. The language choice usually doesn't.
- **Propose, don't poll.** When you can infer a good answer from the conversation, propose it concretely and ask for a reaction. Reserve **structured questions** for real decision points with trade-offs: recommended option first, labeled "(Recommended)", pros and cons in the descriptions. Never ask abstract either/or questions about things you could draft instead. Don't ask "light SKILL.md or heavy?" Propose a placement table and let the user move rows.
- **High-level answers open options, so surface them.** When the user answers at a high level, name the design directions it opens ("that implies A, B, or C, because...") and let the user pick. Inference is for skipping questions already answered, not for choosing among directions an answer leaves open.
- **Ask at the moment of relevance.** Detail questions belong inside the refinement of the phase they affect, not in an up-front batch. A *comparative* decision waits until every input exists, which is why the seams resolve at the close of Step 4.
- After each phase or area, give a **one-line recap** before moving on.
- If answers combine badly (such as high freedom everywhere plus no verification), **say so** and propose a fix rather than silently recording a weak design.

## Workflow checklist

Copy this checklist and check off steps as you complete them:

```
Design Progress:
- [ ] Step 1: Get the topic
- [ ] Step 2: Frame the workflow
- [ ] Step 3: Draft the skeleton
- [ ] Step 4: Refine phase by phase, then resolve the seams
- [ ] Step 5: Confirm verification and feedback
- [ ] Step 6: Design summary checkpoint
- [ ] Step 7: Scaffold the skill(s)
- [ ] Step 8: Update the design summary
- [ ] Step 9: Dry run and refine
```

## Step 1: Get the topic

Ask for the topic or use case in plain conversation, one question. Do not plan, batch, or ask anything else until you have it.

## Step 2: Frame the workflow

With the topic known, ask only what shapes the workflow (structured questions fit here, since these are real decision points):

- **Unit of work per run:** what one execution handles (a module, a ticket, a test suite, ...)
- **What "done" looks like:** the final artifact(s) (a merge request, a mapping doc, a test suite, ...)
- **Shape:** does **Plan → Implement → Verify** fit, or does it differ? In particular, does the documentation the workflow needs already exist, or is *creating it* an upfront discovery phase?

Recap the frame in a few lines.

## Step 3: Draft the skeleton

From the frame, **propose** a draft structure rather than interviewing your way to it:

- Phases in order, each with a one-line purpose and its output artifact
- A first guess at **skill boundaries**: where a fresh context window is needed, and the handoff artifact at each seam

**Mark the seams explicitly.** A seam is a boundary where the context window resets. Walk the phases in order and say, for each boundary, whether the window carries on or resets and what crosses it. Each boundary either carries on in the same thread (no seam) or resets through one of three mechanisms: a **script or hook** that removes the need for a window at all, an **in-skill subagent** the model spawns mid-run, or a **separate skill** the user invokes on its own.

**A checkpoint is not a seam.** "The user approves the plan" is a `-> STOP` inside one window, not a boundary. Splitting there separates two phases that share their context. Keep Plan and Implement in one window unless someone else approves the plan later.

State the reset in the skeleton: "Discover, then Plan" and "Discover in its own window, hand over a findings doc, then Plan" are different designs. Mark each boundary as a seam or not. *Which* mechanism fills it is settled at the close of Step 4, once the phases have real steps.

**-> STOP. Share the skeleton and iterate until the user agrees the shape is right. Every later question is asked against this draft, so do not proceed on a skeleton the user hasn't reacted to.**

## Step 4: Refine phase by phase

Walk the agreed skeleton one phase at a time. For each phase, infer what you can and ask only what you can't. Cover:

- **Context:** what this phase needs to know and where it comes from (existing docs, docs created by an earlier phase, the user's head). Then **propose a placement table**: project-wide knowledge the user's other work also needs (conventions, idioms, stack standards) goes to **project instructions**, every-run workflow-specific knowledge to **SKILL.md**, and some-runs knowledge to **references/**. Let the user move rows.
- **Freedom:** propose high, medium, or low for *this phase* with a rationale. The answer differs per phase and can't be set before the steps exist. Medium or low means naming the template or input→output example pairs (`assets/`). Sub-steps code could do go to `scripts/`, or to hooks where the tool supports them.
- **Alignment:** where AI struggles in this phase gets a focusing **artifact**. Decide whether the phase ends in a **checkpoint** (high rework cost if slightly off), and whether the user co-builds or approves there.
- **Delegable side work:** look for it in every phase, not just at seams. Two shapes are worth delegating: a sub-step that **reads a lot and hands back a little** (a log, a test run, a wide search, a verbose API payload, a transcript), and **the same operation repeated over N independent items** (per service, per module, per file, per tenant). Neither creates a seam, and the phase continues in the thread around it. Propose these without waiting for the user to ask, and say what each one returns.
- **Window:** confirm the seam you marked in Step 3 still holds now the phase has real steps. A phase that turned out to read a lot and never reference it again wants its own window. A phase you planned to isolate but that keeps needing the user mid-run wants to stay in the thread. Note whether this phase needs the user mid-run, because that answer drives the close below.

One-line recap per phase before moving to the next. Update the skeleton as decisions land, so the user always sees the current draft.

**Close the walk: resolve every seam at once.** The choice is comparative: three skills with two handoffs is a different design from one skill with two in-skill subagents. Answering phase by phase gives each seam a sensible answer and the set an incoherent one. Propose all the seams together and let the user move rows. First, account for the delegable side work: if a subagent already takes the heavy reading off a phase, judge its seam on what the phase does after that, not on what it used to read. Then, per boundary, in order:

1. **Does anything downstream need the raw material this phase read** (the actual files and command output), or only its conclusions? Raw material, and the phase covers only this run's unit of work: no seam, stop here. Raw material, but the phase covers more than one run (documenting a whole system): a separate skill that hands over a condensed doc, so the cost is paid once rather than every run. Conclusions only: go on. A downstream phase that re-reads a findings *document* is still a clean seam, since a doc on disk is rereadable from any window.
2. **Could a script produce those conclusions instead?** Wholly: `scripts/`, and the seam disappears rather than being managed. Partly: carve the deterministic half out first, then **keep going with what's left**. Semi-structured output (an observability query, a stack trace, a flaky test run) is where a script narrows the payload and an agent still judges the remainder.
3. **Is what's left small, or is the user working in the thread anyway?** Either one: carry on in the same thread, no seam, stop here. This is the usual answer once a subagent has taken the heavy reading, and for a phase like live incident triage that the user watches as it runs.
4. **Must a human act inside this seam?** Any one of these: it needs to ask the user something mid-run, the user is likely to revise the phase's own output ("change that and redo it"), or the user needs to watch it work. The main thread acting on a reviewer's findings is not a revision. A subagent can't ask the user or take a revision mid-run (see the reference, Area 2).
5. **No human in the seam:** an **in-skill subagent**. Two or more independent items or lenses: spawn them in parallel, one per lens. Before recording it, check the overrides in [design-questions.md](references/design-questions.md) Area 2, which can flip this answer.
6. **Human in the seam:** a **separate skill**. Name the handoff file now, as a path.

Default to staying in the thread unless a gate moved it. That default doesn't cover the side work flagged per phase, since a subagent inside a phase adds only its summary to the main thread. The gates give a starting design, and Step 9's dry run corrects it. One-line recap of the resolved structure before Step 5.

## Step 5: Confirm verification and feedback

These usually fall out of the Step 4 walk. Confirm and fill gaps rather than re-ask:

- **Verification:** the minimum machine bar (compiles, no LSP errors, lints, existing tests), stronger checks (tests against acceptance criteria, AI-run "manual" tests producing an example artifact, adversarial review), and whether a **parallel fan-out** of reviewers is worth its cost. If yes, name each perspective and what each one is blind to.
- **Review defaults to in-skill subagents, and a fan-out is not a seam.** One reviewer or several, read-only and findings-only. Make review a separate skill only if people will run it on its own. A fan-out over N independent items from Step 4 follows the same rules inside the phase that spawns it: read-only when it gathers (triage per tenant), and it may write when it does the work (one item each). Neither goes through the Step 4 gates. Record both in the Structure section as subagent blocks, one chip per lens or item class.
- **Feedback:** what the workflow's final step updates so it improves over time: the skill's own `references/`, a docs system, or a runbook.

## Step 6: Design summary checkpoint

Fill in [assets/design-summary-template.html](assets/design-summary-template.html) with every decision, chosen and inferred, and save it as `design-summary.html` in the project. Mark inferred answers with *(inferred)*. Open it for the user, or give them the path if your tool can't open files.

The summary's sections follow the design areas, in this order: **The task → Structure** (the visual flow: skills as columns, subagents as detached boxes, steps with freedom levels, handoff artifacts, checkpoints) **→ Context → Alignment → Verification → Feedback → Files to generate**. This file is the workflow's living design document, and Step 8 updates it after scaffolding.

**-> STOP. Present the completed summary and get explicit approval before scaffolding. Changes cost less now than after scaffolding.**

## Step 7: Scaffold the skill(s)

Read [references/skill-authoring.md](references/skill-authoring.md) and follow it. The seams resolved at the close of Step 4 determine how many skills to create, **one directory per skill**. Generate only what the design called for:

- One `SKILL.md` per skill: frontmatter, checklist workflow, and the checkpoints from Step 4 as explicit `-> STOP` markers
- Where skills were split for a fresh context window, make the **handoff artifact explicit**: the upstream skill's last step writes it, the downstream skill's first step reads it, and each description says where it sits in the sequence
- `references/`: one stub per some-runs context item, each with a note on what to fill in and an example of the expected detail
- `assets/` templates and `scripts/` stubs, only where the design chose medium or low freedom or determinism
- Where a seam resolved to an **in-skill subagent**, the step that spawns it carries the full contract: agent type and count, spawned in one message, inputs by absolute path, the return shape with a length cap, and what it must **not** return or read. Long or multiple agent prompts move to `references/agent-prompts.md`
- Context the design routed to **project instructions** is not part of the skill. Propose those additions to the user's instructions file separately, along with any agent definition file (a bare skill directory can't install one into the user's project)

**-> STOP. Walk the user through the generated files, mapping each file back to the design decision that created it.**

## Step 8: Update the design summary

Update `design-summary.html` to match what was actually scaffolded: renamed skills, moved files, decisions that shifted during drafting. The Structure section's flow must show every skill, its steps in order, subagent and fan-out blocks, handoff artifacts, checkpoints, and freedom levels as built. The Files section must list exactly the generated files.

**-> STOP. Open the updated summary for the user and confirm it matches the scaffolded skills.**

## Step 9: Dry run and refine

Suggest running the new skill on one real unit of work from Step 2 **in a fresh session**. Tell the user what to watch for: Did checkpoints fire where expected? Did it read the right references? Did verification catch anything? Offer to refine the skill based on what they observe.
