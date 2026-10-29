# Curriculum

Sixteen modules. Roughly 1–3 hours each including the lab. Modules 0–3 are the
foundation; 4–8 are the machinery; 9–14 are the professional practice; 15 is
the capstone.

## Part I — Foundations

| # | Module | Core question | Lab |
|---|--------|---------------|-----|
| 00 | [Orientation](lessons/00-orientation.md) | What *is* a coding agent, precisely? | `labs/L00_orientation.py` |
| 01 | [LLMs, tokens, context](lessons/01-llms-tokens-context.md) | What are the model's actual constraints? | `labs/L01_tokens.py` |
| 02 | [The agent loop](lessons/02-agent-loop.md) | How does a single turn become a task? | `labs/L02_loop.py` |
| 03 | [Tools & function calling](lessons/03-tools.md) | How does a model *do* anything? | `labs/L03_tools.py` |

## Part II — The machinery

| # | Module | Core question | Lab |
|---|--------|---------------|-----|
| 04 | [The filesystem as the world](lessons/04-filesystem.md) | Why do agents live in a repo? | `labs/L04_filesystem.py` |
| 05 | [Context engineering](lessons/05-context-engineering.md) | What should be in the window, and what should not? | `labs/L05_context.py` |
| 06 | [Instructions & rules files](lessons/06-instructions.md) | How do you steer an agent without retyping yourself? | `labs/L06_instructions.py` |
| 07 | [Skills](lessons/07-skills.md) | How do you give an agent expertise on demand? | `labs/L07_skills.py` |
| 08 | [Hooks & lifecycle events](lessons/08-hooks.md) | How do you make behaviour deterministic? | `labs/L08_hooks.py` |

## Part III — Scale and safety

| # | Module | Core question | Lab |
|---|--------|---------------|-----|
| 09 | [Subagents & orchestration](lessons/09-subagents.md) | How do you parallelise without losing the plot? | `labs/L09_subagents.py` |
| 10 | [MCP & interoperability](lessons/10-mcp.md) | How do tools become portable? | `labs/L10_mcp.py` |
| 11 | [Verification & evals](lessons/11-verification-evals.md) | How do you know the agent was right? | `labs/L11_evals.py` |
| 12 | [Safety, permissions, sandboxing](lessons/12-safety.md) | How do you bound the blast radius? | `labs/L12_safety.py` |

## Part IV — Practice

| # | Module | Core question | Lab |
|---|--------|---------------|-----|
| 13 | [Workflows that work](lessons/13-workflows.md) | What does a good agent session look like? | `labs/L13_workflows.py` |
| 14 | [Teams, CI, measurement](lessons/14-teams-ci.md) | How does this survive contact with a team? | `labs/L14_ci.py` |
| 15 | [Capstone](lessons/15-capstone.md) | Can you build and defend a real one? | `capstone/` |

## Learning outcomes

By the end you should be able to:

- Explain an agent run as a sequence of model calls, tool calls, and context
  mutations — and locate a failure in that sequence.
- Write a tool schema and a dispatcher, and reason about its failure modes.
- Design an instruction file and a skill that actually change model behaviour.
- Implement a hook that blocks an unsafe action deterministically.
- Decide when a subagent is worth its cost, and when it is just context loss.
- Explain what MCP standardises and where its trust boundary sits.
- Build an eval suite that catches regressions instead of flattering the model.
- Run an agent session on a real repo without breaking it.

## Pacing

- **Weekend sprint:** modules 0–3, 5, 8, 12. You will understand agents and
  their risks, not build them.
- **Two weeks:** everything except the capstone.
- **Full course:** all sixteen, capstone included. Recommended.

## Conventions used in lessons

- `💡 In practice` — how this concept shows up in real tools. Safe to skip.
- `⚠️ Failure mode` — the specific way this goes wrong.
- `🔬 Break it` — a deliberate exercise in making it fail.
- `✅ Checkpoint` — questions to answer before moving on.
