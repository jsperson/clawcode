---
title: "feat: Life Agent Problem Solver"
type: feat
status: completed
date: 2026-02-26
origin: docs/brainstorms/2026-02-26-life-agent-problem-solver-brainstorm.md
---

# Life Agent Problem Solver

On-demand parallel research engine for life problems. User describes a problem, agent researches it from multiple angles simultaneously, synthesizes findings, and optionally creates a living project plan.

## Overview

The Problem Solver adds a new command (`/life:solve`) to the existing Life Agent plugin. It follows the same orchestrator→subagent architecture as `/life:overnight` and `/life:evening`, using the Task tool to spawn parallel research agents that each investigate from a dynamically chosen lens.

Three depth tiers — quick (just answer), medium (1-2 agents + synthesis), full (3-4 agents + synthesis). Agent always asks which tier before proceeding.

Output lands in `{notes_path}/Projects/` as a structured doc with TL;DR, tagged with frontmatter so the evening review can discover and track it.

(see brainstorm: docs/brainstorms/2026-02-26-life-agent-problem-solver-brainstorm.md)

## Problem Statement / Motivation

The Life Agent handles daily planning and evening reviews — recurring, scheduled cycles. But life throws unscheduled curveballs: a kid being bullied, a parent's declining health, a bathroom remodel, a career change. These need structured research from multiple angles, not a single ChatGPT answer.

The Problem Solver fills this gap: the agent's equivalent of calling a smart, resourceful friend who will research broadly, consider angles you haven't thought of, and distill it into "here's what the best thinking says you should do."

## Proposed Solution

### New Plugin Files

All files live in the Life Agent plugin at:
`~/.claude/plugins/marketplaces/life-agent/plugins/life-agent/`

```
commands/life/
  solve.md                              # /life:solve orchestrator command

agents/problem-solver/
  researcher.md                         # Parallel research agent (one instance per lens)
  synthesizer.md                        # Distills all research into final doc
```

No new skills needed — existing `planning` and `principles` skills are sufficient.

### Command: `/life:solve`

**File:** `commands/life/solve.md`

**Frontmatter:**
```yaml
---
name: life:solve
description: "Research any life problem from multiple angles and synthesize actionable recommendations. Supports quick answers, focused research, or full parallel investigation."
argument-hint: "[problem description]"
---
```

**Process (8 steps):**

#### Step 1: Read Config
Same pattern as `/life:overnight`:
- Read pointer file at `~/.claude/life-agent/config.yaml`
- Read full config at `{data_path}/config.yaml`
- Extract `notes_path` and `capabilities`

#### Step 2: Problem Understanding (Interactive)
If the user provided a problem description in the argument, use it as the starting point. Otherwise, ask.

Conversational dialogue (not a questionnaire) to understand:
- **Situation** — what's happening, facts not assumptions
- **Constraints** — budget, time, location, values, family dynamics
- **Prior attempts** — what's been tried already
- **Success criteria** — what does "solved" look like
- **Urgency** — how time-sensitive is this

**Exit criteria:** The agent has enough context to pick research lenses. For urgent problems (furnace broke, it's -10), 1-2 exchanges max. For exploratory problems (career change), 3-5 exchanges. The agent calibrates to the urgency.

**Discord behavior:** Each question is output as text, then STOP. User replies in next message. Session state persists across messages natively (per bot context: "This is a multi-turn conversation. Sessions persist across messages.").

#### Step 3: Depth Check
Always ask the user. Agent proposes a tier based on problem complexity, but user decides.

> "This sounds like [quick question / focused problem / major life situation]. Want me to [just answer / do some focused research / go deep with full parallel research]?"

**If the user's choice seems mismatched** (urgent emergency + "quick", or trivial question + "full"), the agent pushes back once: "This might benefit from [deeper/lighter] research because [reason]. Your call though." Then respects the decision. (per SOUL.md: push back when it matters, but questions are not commands)

**Quick tier:** Skip to Step 8 — just answer conversationally. No file output. No subagents. Done.

**Medium tier:** Continue to Step 4. Orchestrator picks 1-2 lenses.

**Full tier:** Continue to Step 4. Orchestrator picks 3-4 lenses.

#### Step 4: Determine Research Lenses
The orchestrator analyzes the problem and determines the right lenses. Fully dynamic — no template library.

Each lens gets:
- **Name** — short label (e.g., "Medical & Care Options")
- **Focus** — what this lens investigates
- **Search guidance** — what to look for in QMD/vault/web

The orchestrator announces the lenses to the user before spawning agents:
> "Researching from 3 angles: Medical & Care Options, Financial & Legal, Family & Logistics. This will take a few minutes."

This serves as both a progress indicator and a chance for the user to redirect ("add an emotional/grief angle too").

#### Step 5: Pre-fetch Context
The orchestrator gathers context that requires Bash or is shared across all lenses:

- **QMD search** for prior conversations about this topic (MCP tool — available to orchestrator)
- **Vault search** for related notes (Glob/Grep — available to orchestrator)
- Read `{data_path}/principles/core.md` and `{data_path}/principles/current-priorities.md` (for principles-aware research)

This shared context is passed to every research agent so they don't duplicate the same vault/QMD searches.

**Note:** Unlike `/life:overnight`, the orchestrator does NOT need to pre-fetch calendar/weather/tasks via Bash. Research agents have access to WebSearch, WebFetch, QMD MCP tools, Read, Glob, and Grep — everything they need for research. The pre-fetch here is about efficiency (shared context), not capability limitations.

#### Step 6: Parallel Research (Task Tool)
Spawn one Task subagent per lens, all in parallel.

Each researcher agent receives via the Task tool prompt:
- The problem description and understanding from Step 2
- Their specific lens (name, focus, search guidance)
- The shared pre-fetched context from Step 5
- The user's principles (so research is values-aware)
- Instructions to search web (WebSearch + WebFetch) for current information
- Instructions to return structured findings

**subagent_type:** `life-agent:problem-solver:researcher`

Each researcher returns structured findings:
```markdown
## [Lens Name]

### Key Findings
- Finding 1 (source: URL or vault path)
- Finding 2 ...

### Recommendations
- Recommendation 1
- Recommendation 2

### Watch Out For
- Risk or caveat 1

### Sources
- [Source title](URL)
- vault: path/to/related/note.md
```

**Failure handling:** If a research agent fails (timeout, error, empty results):
- Orchestrator notes the gap
- Synthesis proceeds with available results
- The gap is flagged in the output: "Note: [Lens Name] research was incomplete — consider investigating this angle manually."

#### Step 7: Synthesis (Task Tool)
Spawn a single synthesizer agent with all research results.

**subagent_type:** `life-agent:problem-solver:synthesizer`

The synthesizer receives:
- The problem description and understanding
- All researcher outputs (combined)
- The user's principles
- The target output path: `{notes_path}/Projects/YYYY-MM-DD-{topic-slug}.md`

The synthesizer produces the final document and writes it using the Write tool.

**Output format:**

```yaml
---
type: problem-solver
status: active
date: YYYY-MM-DD
topic: "{descriptive topic}"
depth: medium|full
lenses: [lens1, lens2, lens3]
principles_applied: [core.md, current-priorities.md]
---
```

```markdown
# {Problem Title}

## TL;DR
- Bullet 1 (3-5 bullets max, the "read this if nothing else" summary)
- Bullet 2
- Bullet 3

## Situation
[Clear framing of the problem based on Phase 1 dialogue]

## Expert Consensus
[What the best thinking says, with inline source links]

## Key People & Resources
[Who to talk to, what to look into, local resources if applicable]

## Recommended Actions
1. [Highest priority action] — why this first
2. [Next action]
3. [Next action]
(Prioritized by urgency and impact)

## Things to Watch For
[Red flags, common mistakes, timing considerations]

## Where Experts Disagree
[Divergent opinions — don't hide complexity]

## Research Notes
[Per-lens summaries for reference, collapsed or at the end]

## Sources
[All URLs and vault references, grouped by lens]
```

**Topic slug generation:** The synthesizer generates a short, descriptive kebab-case slug from the problem (e.g., `elder-care-options`, `bathroom-remodel`, `career-change`). Max 4 words.

**Same-day collision:** If `YYYY-MM-DD-{slug}.md` already exists, append a counter: `-2`, `-3`, etc.

#### Step 8: Confirm and Next Steps
- Read back the file to verify it was written
- Print summary: topic, depth, lenses used, number of sources, file path

Offer options:
1. **Open in editor** — `open {file_path}` to view in Obsidian
2. **Convert to living plan** — add checkboxes to Recommended Actions, activate evening review tracking
3. **Refine** — re-run specific lenses, add a lens, adjust recommendations
4. **Done** — file is written, that's it

**If user selects "Convert to living plan":**
- Read the synthesis doc
- Convert Recommended Actions into checkbox items with owners and rough timelines
- Add a `## Action Plan` section with `- [ ]` items
- Update frontmatter: `status: active` (already set), add `has_action_plan: true`
- Confirm: "Living plan active. Evening reviews will check in on open items."

### Agent: Researcher

**File:** `agents/problem-solver/researcher.md`

**Frontmatter:**
```yaml
---
name: researcher
description: "Researches a specific angle of a life problem using web search, vault search, and QMD. Spawned in parallel — one instance per research lens."
model: inherit
---
```

**Capabilities:** Read, Glob, Grep, WebSearch, WebFetch, QMD MCP tools.

**Behavior:**
- Receives a single lens with focus and search guidance
- Searches in order: shared pre-fetched context first (already provided), then web for current/authoritative information
- Returns structured findings (key findings, recommendations, watch-outs, sources)
- Does NOT write files — returns results to the orchestrator
- If a search angle yields nothing, explicitly says so rather than padding with low-quality content

**Guidelines:**
- Prioritize authoritative sources (research institutions, professional organizations, government resources) over blog posts and forums
- Include local/regional context when relevant (the user's location is in the pre-fetched context)
- Flag when information is time-sensitive or jurisdiction-dependent
- Keep findings concise — the synthesizer handles integration

### Agent: Synthesizer

**File:** `agents/problem-solver/synthesizer.md`

**Frontmatter:**
```yaml
---
name: synthesizer
description: "Distills parallel research findings into a structured document with TL;DR, expert consensus, and actionable recommendations."
model: inherit
---
```

**Capabilities:** Read, Write (to write the output file).

**Behavior:**
- Receives all researcher outputs + problem context + principles
- Deduplicates overlapping findings across lenses
- Resolves contradictions by noting disagreement (not hiding it)
- Writes the final document to the specified path
- Applies the user's principles when prioritizing recommendations (e.g., if "family first" is a core value, family-impact recommendations rank higher)

**Guidelines:**
- TL;DR must stand alone — someone reading only those 3-5 bullets should know what to do
- Recommended Actions must be concrete and sequenced (not "consider your options")
- Sources must be traceable — every major claim links to a source
- Don't hide complexity behind false certainty
- If research was incomplete (agent failure), flag the gap explicitly

### Evening Review Integration

The evening command (`commands/life/evening.md`) needs a new step between "Read Principles" and "Review Conversation":

**New Step: Check Active Problem-Solver Projects**

1. Glob for `{notes_path}/Projects/*.md`
2. Read frontmatter of each file, filter for `type: problem-solver` AND `status: active` AND `has_action_plan: true`
3. For each active project, extract unchecked action items (`- [ ]`)
4. Pass these to the review-conversation agent as additional context: "Active projects with open items: [list]"
5. The review-conversation agent asks about specific items during the evening dialogue

**This is a modification to an existing file** (`commands/life/evening.md`), not a new file. Add the step and pass the data through.

### Natural Language Recognition

The `/life:solve` command is the explicit entry point. Natural language recognition is handled by the agent's normal conversation flow — when someone describes a problem that would benefit from structured research, the agent can suggest:

> "This sounds like something that would benefit from structured research. Want me to run `/life:solve` on this?"

This does NOT require any new code or configuration. It's just the agent being helpful in conversation, recognizing the pattern, and offering to invoke the command. The orchestrator identity/soul instructions already support this kind of initiative.

## Technical Considerations

### Subagent Tool Access
Research agents (spawned via Task tool) have access to: Read, Glob, Grep, WebSearch, WebFetch, and MCP tools (QMD). They do NOT have Bash access. This is sufficient for all research needs — no Bash-dependent data sources are required.

### Token Budget
Full parallel research spawns 3-4 agents + 1 synthesizer. Each agent uses its own context window. The orchestrator's context carries the problem understanding, shared pre-fetch, and all agent results. Estimate ~50k tokens orchestrator context for a full run.

### Discord Output
The synthesis doc will exceed Discord's 2000-char limit. The orchestrator should:
- Post the TL;DR (3-5 bullets) + file path to Discord
- Full doc is in the vault at the written path
- User reads the full version in Obsidian

### Error Handling
- **Research agent timeout/failure:** Synthesis proceeds with partial results, gap flagged in output
- **All agents fail:** Orchestrator apologizes and offers to try a simpler approach (medium or quick)
- **QMD unavailable:** Research proceeds without personal context, user warned
- **Web search returns nothing:** Agent reports the gap, doesn't fabricate

### Plugin Version
This adds 3 new files and modifies 1 existing file. Bump plugin version from `0.4.1` to `0.5.0` (new feature).

## Acceptance Criteria

- [x] `/life:solve` command exists and can be invoked explicitly
- [x] Phase 1 dialogue works in both CLI and Discord (multi-turn)
- [x] Depth check always asks before proceeding
- [x] Quick tier answers conversationally with no file output
- [x] Medium tier spawns 1-2 research agents + synthesizer
- [x] Full tier spawns 3-4 research agents + synthesizer
- [x] Research agents search web + vault + QMD
- [x] Synthesizer produces structured doc with TL;DR at `{notes_path}/Projects/`
- [x] Output files have correct frontmatter (`type: problem-solver`, `status`, `depth`, `lenses`)
- [x] Living plan conversion adds checkboxes and `has_action_plan: true`
- [x] Evening review discovers active problem-solver projects and asks about open items
- [x] Failed research agents produce a flagged gap, not a silent omission
- [x] Same-day filename collisions handled with counter suffix

## Dependencies & Risks

**Dependencies:**
- QMD MCP server running (for vault/session search) — graceful degradation if unavailable
- WebSearch/WebFetch available to subagents
- Existing evening review command must be modified for integration

**Risks:**
- **Research quality varies.** Dynamic lens selection means lens quality depends entirely on the orchestrator's reasoning. Mitigated by announcing lenses to user before spawning (chance to redirect).
- **Wall-clock time.** Full parallel research may take 2-5 minutes. User needs the progress indicator (lens announcement) to know it's working.
- **Rate limits.** 4 parallel agents + synthesizer hitting WebSearch could trigger rate limits. Mitigated by QMD/vault search reducing web dependency.

## Implementation Order

1. **`agents/problem-solver/researcher.md`** — the research agent definition
2. **`agents/problem-solver/synthesizer.md`** — the synthesis agent definition
3. **`commands/life/solve.md`** — the orchestrator command
4. **Modify `commands/life/evening.md`** — add active project detection step
5. **Bump `plugin.json` version** to 0.5.0
6. **Deploy** — copy to marketplace, sync to cache, restart

## Sources & References

### Origin
- **Brainstorm document:** [docs/brainstorms/2026-02-26-life-agent-problem-solver-brainstorm.md](docs/brainstorms/2026-02-26-life-agent-problem-solver-brainstorm.md) — Key decisions carried forward: dual invocation, always-ask depth, full context sources (web+vault+QMD), output to `{notes_path}/Projects/`, dynamic lens selection, evening review integration, structured doc + TL;DR format.

### Internal References
- Overnight command pattern: `~/.claude/plugins/cache/life-agent/life-agent/0.4.1/commands/life/overnight.md`
- Evening command (to modify): `~/.claude/plugins/cache/life-agent/life-agent/0.4.1/commands/life/evening.md`
- Agent definition examples: `~/.claude/plugins/cache/life-agent/life-agent/0.4.1/agents/planning/daily-planner.md`
- Plugin conventions: `~/.claude/plugins/cache/life-agent/life-agent/0.4.1/CLAUDE.md`
- Config pointer: `~/.claude/life-agent/config.yaml`

### Design Documents
- Problem Solver design: `vault/projects/life-agent/problem-solver.md`
- Architecture principles: `vault/projects/life-agent/architecture-principles.md`
- Overnight deep work (Phase 2, deferred): `vault/projects/life-agent/overnight-deep-work.md`
