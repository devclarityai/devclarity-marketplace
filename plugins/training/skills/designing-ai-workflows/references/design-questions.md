# Design Questions Reference

Trade-offs, recommendation heuristics, and examples for each design area. Read this fully before starting an interview.

## Contents

- Interview style: draft early, steer often
- Framing: the Plan → Implement → Verify flow
- Area 1: Context
- Area 2: Structure
- Area 3: Alignment
- Area 4: Verification
- Area 5: Feedback
- Cross-cutting red flags

## Interview style: draft early, steer often

- **Sequence:** topic → frame (unit of work, done, shape) → draft skeleton → per-phase detail. The skeleton lands as early as possible, and detail questions attach to the phase they affect.
- **Why not batch:** users react better to a draft than to a long list of abstract questions. Front-loaded gathering produces answers ungrounded in any structure, and the answers to detail questions (freedom, context placement) depend on steps that don't exist yet.
- **Propose vs. poll:** if the conversation plus the domain gives you a defensible answer, state it and invite correction ("I'd put X here because Y. Move it?"). Use a structured question only where the user holds information you can't infer or the trade-off is theirs to make.
- **High-level answers open options:** when the user answers at a high level, name the design directions it opens ("that implies A, B, or C, because...") and let the user choose. Don't fold the answer silently into one design decision. Inference is for skipping already-answered questions, not for choosing among directions an answer leaves open.
- **No tech trivia:** ask about the workflow (unit of work, risk points, verification), not the technology (versions, dialects, frameworks), unless the answer changes a design decision. "What's the unit of work per run?" beats "Which Java version?".

## Framing: the Plan → Implement → Verify flow

Most workflows follow **Plan → Implement → Verify**.

- **Plan:** explore the codebase and problem space, make sure all needed information is gathered from the user, then propose a plan. A tool's built-in plan mode, if it has one, is fine for general tasks. A workflow with a specific goal usually wants a more consistent plan output (a defined artifact).
- **Implement:** execute the plan.
- **Verify:** confirm the AI did what was asked. AI-assisted work often falls short here, so budget for verification.

Frame questions that shape everything downstream:

- **Unit of work per run:** one module, one ticket, one feature slice. Sets the blast radius, the verification scope, and how often checkpoints fire.
- **Does needed documentation exist?** Sometimes creating it is an upfront discovery phase, e.g., documenting a legacy system before a modernization workflow can plan against it.

If the user's task doesn't fit this shape (such as pure analysis or documentation), adapt. Verify-equivalents (review against a rubric) almost always still apply.

## Area 1: Context

**Questions to cover (per phase of the agreed skeleton):**

1. What does this phase need to know, and where does it come from: existing docs, an artifact created by an earlier phase, or the user's head?
2. Where should each piece live?

**Placement: three destinations. Propose a table and let the user move rows.**

| Destination | Belongs there | Test |
|---|---|---|
| **Project instructions** (`AGENTS.md`, `CLAUDE.md`, ...) | Project-wide knowledge: conventions, idioms, stack standards, style | Would the user's *other* AI work also need this? Then it's not the skill's. |
| **SKILL.md** | Workflow-specific, needed **every run** | Putting it in references adds a read step for no benefit |
| **`references/`** | Workflow-specific, needed **some runs** | Putting it in SKILL.md adds its cost to every run |

- Often misplaced: target-language idioms and team conventions feel like skill content but belong in **project instructions**. Every code-writing task needs them, not just this workflow.
- Examples of `references/` content: mocking patterns for a particular type of testing, migration or modernization pattern mappings, page object model patterns, per-module-type discovery patterns.
- Litmus question: "what is relevant to *this task* but not to all code you write?" That's the skill's context, and the rest is project instructions.
- Don't ask the user "light SKILL.md or everything in SKILL.md?" That's an abstract poll. Enumerate the context, trace its source, propose the placement, iterate.

## Area 2: Structure

**Questions to cover:**

1. One skill or several: where are the logical seams?
2. At each seam, which mechanism (thread, script, subagent, separate skill) and what artifact crosses it?
3. Degrees of freedom **per phase**, which is only answerable once the skeleton exists and usually differs phase to phase
4. Where can determinism be introduced?

**Skill boundaries:**

- Split where you want a **separate context window** for the next set of steps. Canonical example: legacy-codebase discovery should not pollute the context that writes new code, where it risks carrying over bad practices or creating confusion.
- Default recommendation: one skill until there's a concrete reason to split (context pollution, reuse of a phase across workflows, or a natural handoff artifact between phases).

**The options, cheapest first.** The choice is made per seam, and the options combine: a phase promoted to a separate skill can and usually should use scripts and subagents internally.

| Option | What it is | What it costs |
|---|---|---|
| **Stay in the thread** | No seam. The next phase inherits every file, dead end and correction this one produced. | No cost now, a large one later if the phase read a lot |
| **Script** | A script or hook produces the distilled result, so no window ever holds the raw material. The seam disappears instead of being managed. | Writing the script once |
| **Subagent** | One in-skill subagent. The model spawns it mid-run, and the user doesn't interact with it. | Latency, plus re-gathering what it needs. It can read a large amount and return only a short summary |
| **Parallel subagents** | N subagents in parallel over N independent items or lenses, merged by the caller. | The same, times N, plus a merge step |
| **Separate skill** | A skill the human starts in a fresh session, reading a named artifact the previous one wrote. | A human action between phases |
| **Independent skills** | Several independently-invoked skills the human chains as the situation wants. The human picks the order each time. | Nothing enforces the order |

Leave compaction (`/compact` in Claude Code, or automatic) off the list. It only recovers from a missing seam, so never write it into a design.

**Subagent or its own skill?** They isolate the same way: by default a subagent starts with a fresh context and doesn't see your conversation or the files already read. Choose between them on two points.

- **Can a human act inside the seam.** Claude Code strips its question tool from every subagent. Treat subagents in any tool as unable to reach the user unless yours documents otherwise. A subagent that hits an ambiguity cannot ask, so it guesses. Claude Code can resume a subagent, but design as if each run is one-shot: "change that one thing and redo it" usually means running the subagent again. Three triggers, any one of which forces a human-restarted window: the phase asks the user questions mid-run, the plausible response to its output is *revision* rather than accept or reject, or the user needs to watch the work happen (first runs, trust-building, anything where "how did it conclude that" matters).
- **Reuse and invocability.** A skill is a directory a human can run on its own and other workflows can call. A subagent is an implementation detail of one step in one skill, invisible from outside. Default to a fixed sequence of skills, and make them independently invocable only when a second caller actually exists.

More rules for placing seams:

- **Ask about raw material before anything else.** "Does anything downstream need the actual files this phase read, or only its conclusions?" settles most seams. Asking it *first* keeps plan approval from turning into a skill split. A downstream phase that keeps re-reading the findings *document* is still a clean seam: a doc on disk is rereadable from any window.
- **Scope wider than one run.** If a phase's scope is wider than one run's unit of work (it documents the whole system while runs are per-module), treat it as a seam that hands over a condensed doc, even when a single run consults the raw material. It is amortized across runs and should not be re-paid per run. This is what distinguishes legacy-system discovery (its own skill) from understanding the module you are migrating now (the Plan half of Plan → Implement, same window).
- **A checkpoint is not a seam.** A human-in-the-loop point stays inside the window. Splitting there separates phases that share their context. Plan approval is a `-> STOP` inside one window, because the approver wants to talk to the thing that wrote the plan. The exception is approval that comes later or from someone else, such as a tech lead reviewing the next day. Then a plan-file handoff is right.
- **Name what crosses the seam.** Every seam names its artifact. For a handoff, a path the upstream skill's last step writes and the downstream skill's first step reads. For a subagent, the *shape of the return* ("a findings list, each item with file:line and a severity"), not "a summary".
- **Seams are most useful at the ends.** Discovery ahead of Plan → Implement, and review after it, are the usual places a seam pays off (review as in-skill subagents, see Area 4), because a reviewer that watched the code being written shares the author's blind spots. A seam between Plan and Implement rarely helps.
- **Try determinism first.** A hook or script that filters tool output before the agent sees it can remove the reason for a seam entirely. Claude Code's [costs guide](https://code.claude.com/docs/en/costs) shows a hook that trims a log before the agent reads it.

**Overrides, checked after the ladder. Any one of these changes the answer:**

- **The phase needs its own fan-out:** not a subagent. Nested subagents are limited or unavailable depending on the tool, so a phase that must spawn parallel subagents belongs in the main thread or its own skill.
- **Expensive and hard to redo** (long runs, paid calls, irreversible writes): prefer a handoff. A subagent that fails partway loses any work it didn't write to disk, while a skill leaves its partial artifact on disk and the human resumes.
- **Latency matters and the phase is small:** stay in the thread, even if the raw material is never reused. For a small read, a seam costs more than it saves.

**Signs of the wrong pick:**

| Wrong pick | Sign |
|---|---|
| Stayed in the thread where a seam was right | Quality drops in the back half, the model cites a file from several phases ago as current, someone compacts the context. In code workflows, legacy idioms read during discovery show up in the new code |
| Subagent where a separate skill was right | The return is "looks good" and nothing in it is auditable. It hit an ambiguity, could not ask, and picked. The human wants one change and the only option is a full rerun |
| Separate skill where a subagent was right | The handoff file has one reader, and the human's only role is starting a fresh session and typing a skill name. Or run 2 silently reuses run 1's file |
| Parallel subagents where one was right | The returns say the same thing in different words, and the caller spends more context reconciling them than one agent would have spent doing the work |
| Seam where staying in the thread was right | The downstream skill's first act is re-reading the files the upstream one read. Tell: the handoff doc says "see the code for details" |

**Worked examples:**

- **Incident triage that reads observability data** (such as Datadog). The triage phase pulls logs, traces and dashboards, and the fix phase never re-reads any of it. A script narrows the query and formats the payload, and judging the remaining semi-structured output is a **subagent**. It returns a ranked list of candidate causes with the log lines supporting each. It sits *inside* the triage phase, which continues in the main thread.
- **The same triage across N tenants or environments.** Each tenant is an independent item inside one run, so N tenants is **parallel subagents**: one agent per tenant, spawned in one message, each returning the same structured shape so the orchestrator can rank across them. Name that shape, because N agents improvising N formats are hard to merge. Guard: the tenants must be independent. If what you find in one changes what you look for in the next, it is sequential work, not a fan-out. When one shared incident links them, run the fan-out twice: once to find the common cause, then again over the tenants it affects.

**Degrees of freedom (assessed per phase, against the drafted skeleton):**

| Level | Form | Use when |
|---|---|---|
| High | Prose / heuristics | Multiple approaches valid, context drives decisions (writing new code) |
| Medium | Pseudocode / templates | A preferred pattern exists, some variation OK (tests, docs of a given type) |
| Low | Exact script or clear example | Fragile or consistency-critical operations, handoff artifacts |

- Templates live in `assets/`. A strong medium-freedom technique: provide **2-3 input→output example pairs** (few-shot) instead of describing the format.
- Recommend: match strictness to fragility. New-code phases lean high, test-writing and documentation lean medium, and conversions, migrations, and handoff artifacts lean low. Propose a level per phase with the rationale. Don't ask for one global setting.

**Determinism:**

- **Make everything that can be deterministic, deterministic.** If code can do part of a conversion, scaffold a template, or map dependencies, let it.
- Examples: parse test or log output with a script instead of burning context (or a subagent) reading it, scaffolding templates, generating dependency maps.
- `scripts/` are deterministic steps the skill runs. **Hooks**, where the tool supports them, are deterministic enforcement the tool runs. Key distinction to share: **context rules are advisory, and hooks are deterministic** (guaranteed action). If the user hasn't seen hooks, give that one-line intro.

Sources for this section (Claude Code docs. Check your own tool's docs, since details differ.): https://code.claude.com/docs/en/sub-agents, https://code.claude.com/docs/en/skills, https://code.claude.com/docs/en/costs, https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

## Area 3: Alignment

**Questions to cover (per phase where relevant):**

1. Where has the user seen AI struggle on this task?
2. Where should the human be in the loop?

**Heuristics and trade-offs:**

- Struggle points get an **artifact** for additional focus. Examples: recognizing existing code that should be reused rather than rewritten, understanding a particular part of the codebase, overwriting certain types of code.
- Checkpoints go at **high-risk points where being slightly off causes significant rework**. Examples: choosing mapping patterns (migrations are rarely 1:1 in functionality), approving the proposed plan, reviewing assumptions and decisions after implementation completes.
- Second checkpoint trigger: places where the *user* doesn't yet know what's needed and should be pulled in to co-build the process as it runs.
- Trade-off to present: each checkpoint costs flow interruption. Recommend checkpoints only where rework cost outweighs interruption cost. Keep them few, and include plan approval whenever the workflow has a plan phase.

## Area 4: Verification

**Questions to cover:**

1. How can the work be verified as correct?
2. Would multiple perspectives help?

**Heuristics and trade-offs:**

- Ladder, weakest to strongest: it compiles → LSP reports no errors → AI navigates and runs commands to check further → tests written against acceptance criteria → AI runs the user's "manual" tests and produces an example document (an artifact) → an automated **adversarial review** step.
- Recommend at least one machine-verifiable check (compile, LSP, tests) plus one artifact the human reviews.
- **Multiple perspectives** is where a parallel fan-out enters: different lenses for different kinds of review (such as conventions vs. security vs. reuse). Trade-off: more tokens and time. Recommend it only when a single review demonstrably misses things, or stakes are high.
- **Review defaults to in-skill subagents**, one reviewer or several. Make it a separate skill only if people will run it on its own. Choosing how many lenses does not re-open the seam resolution.
- **How reviewer prompts are written** (one agent per lens, read-only reviewers with one editor, a return shape and length cap) is in skill-authoring.md, used at Step 7.
- **Name what each lens is blind to.** A reviewer given all the source material will fill gaps from it and pass an artifact that does not stand alone. One meant to test whether the artifact stands by itself must be run deliberately without that material.
## Area 5: Feedback

**Questions to cover:**

1. Where does the workflow learn, so it improves over time?

**Heuristics:**

- Does the last step update some form of documentation? Options: inside the skill (`references/`), a documentation system (such as a wiki), or a runbook.
- Recommend defaulting to the skill's own `references/`, which keeps improvements where the next run will actually read them. External systems are right when other teams or non-AI processes consume the same knowledge.

## Cross-cutting red flags

Call these out if the interview produces them:

- **Batch info-gathering without steering:** a wall of questions before any draft exists. Put a skeleton on the table first.
- **Abstract polls instead of proposals:** "light or heavy SKILL.md?"-style questions. Draft the placement and let the user move rows.
- **Tech-detail questions that don't change the design:** versions, dialects, frameworks.
- **High freedom everywhere plus thin verification:** fast but unreviewable. Tighten verification or reduce freedom.
- **No checkpoints before expensive work:** plan approval costs little next to rework.
- **Project-wide knowledge stuffed into the skill:** idioms and conventions belong in project instructions, where all the user's work benefits.
- **All context in SKILL.md:** a cost paid on every run. Move some-runs content to `references/`.
- **AI reading what a script could parse:** test output, logs, large generated files. Introduce a script.
- **A skeleton with no seams, or a seam at every step:** one window carrying a whole long workflow is likely to hit compaction, and a subagent per phase pays the isolation cost where phases share context. Name the mechanism at each boundary and the artifact that crosses it.
- **A separate skill where an in-skill subagent would do:** a skill the user will never invoke on its own is a subagent with extra files and a fresh session the human has to remember to start. Conversely, **a subagent where the human needed to act**, which leaves it guessing.
- **A verbose side task left in the main thread:** the workflow greps a log, queries an observability tool, or reads a transcript mid-phase and carries the whole payload for the rest of the run. Move it to a subagent.
- **A "for each service / module / tenant" phase with no fan-out:** the same operation over independent items, run serially in one window that accumulates all of them. Use parallel subagents.
- **Subagents considered only at phase boundaries:** the gates were run on the skeleton's seams and never on the work inside a phase, so the two shapes that usually justify an agent were never looked for.
- **No feedback step:** nothing carries lessons from one run to the next.
