---
name: sequential-thinking
description: Structured step-by-step problem solving with numbered thoughts, revisions and branches, modeled on the Sequential Thinking MCP server. Use for complex or unclear problems where the plan may change along the way - debugging failures with no obvious cause, planning migrations or multi-step changes, comparing architecture options, or when the user asks to think "Schritt für Schritt", "step by step" or to show the reasoning.
---

# Sequential Thinking

Method from https://github.com/modelcontextprotocol/servers/tree/main/src/sequentialthinking, applied without the MCP server.

## Process

Work through the problem as a numbered sequence of thoughts. Each thought tracks:

- **Thought N of ~T** - T is an estimate; raise or lower it whenever the scope turns out different.
- **Content** - one concrete step: a fact checked, an assumption stated, a hypothesis, a test of it.
- **Revision** - when a later finding invalidates an earlier thought, say `Revises thought K` and state what changed. Do not silently drop it.
- **Branch** - when two approaches are both plausible, fork with `Branch A from thought K` / `Branch B from thought K`, follow each far enough to compare, then pick one and say why.
- **Next needed?** - stop only when a hypothesis has been verified against the evidence (code, logs, test output), not when it merely sounds right.

## Rules

- Start with a rough estimate of total steps and the unknowns that matter.
- Filter out information that does not bear on the question.
- Verify hypotheses with tools (read the code, run the test, check the log) before concluding.
- Keep thoughts in internal reasoning by default. Show the numbered sequence to the user only when they ask to see the reasoning, or for a plan they need to review.
- End with one clear answer or plan, plus what was verified and what remains assumed.
