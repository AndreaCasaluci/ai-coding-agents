# AI Coding Agents — A Crash Course from Zero

A vendor-neutral, hands-on course about how AI coding agents actually work:
the loop, the context, the tools, the guardrails, and the workflows that make
them useful instead of dangerous.

No prior agent experience assumed. Some Python and Git familiarity helps.

## Why this exists

Most material about coding agents is either marketing or a manual for one
specific product. This course teaches the *mechanics* — the parts every agent
shares — so that whatever tool you pick up next (Claude Code, Codex, Cursor,
Copilot, Aider, OpenCode, something that ships next year) is a variation on a
model you already understand.

The core idea: **you cannot debug what you cannot name.** By the end you will
be able to name every moving part of an agent run and point at the one that
broke.

## How the course works

```
lessons/       16 modules, read in order
mini_agent/    a toy agent harness you build up, one module at a time
labs/          one runnable script per module
capstone/      a real project that uses everything
docs/          reference material, cheat sheets
```

Every module has the same shape:

1. **Objectives** — what you should be able to do afterwards.
2. **Lesson** — the concept, with diagrams and the failure modes.
3. **Lab** — runnable code that demonstrates the concept, not a toy example
   that only prints "hello".
4. **Checkpoint** — questions you should be able to answer cold.

The `mini_agent/` package grows across the course. By module 15 it is a small
but complete agent: LLM abstraction, tool registry, sandboxed filesystem,
context budgeting, instruction loading, skills, hooks, subagents, an
MCP-shaped protocol, and an eval runner. It is not production software — it is
a *readable* reference implementation of every concept in the lessons.

## Quickstart

```bash
git clone <this-repo> && cd ai_coding_agents

# No dependencies. Python 3.10+.
python3 -m mini_agent --help
python3 -m mini_agent "list the files and summarise the repo"

# Run every lab and test
make test
make labs
```

The harness ships with a **scripted mock model** so everything works offline
with zero API keys. Set `MINI_AGENT_PROVIDER=openai` and `OPENAI_API_KEY` to
run the same code against a real model.

## Start here

1. Read [`CURRICULUM.md`](CURRICULUM.md) — the map.
2. Open [`lessons/00-orientation.md`](lessons/00-orientation.md).
3. Tick boxes in [`PROGRESS.md`](PROGRESS.md) as you go.

## Ground rules

- **Read the code in `mini_agent/`.** The lessons explain it, but the point is
  that it is small enough to hold in your head.
- **Break things on purpose.** Most labs have a "now break it" step. Failure
  modes are the curriculum.
- **Vendor-neutral by design.** Product names appear only in "In practice"
  boxes, and only to map a concept onto tools you may already use.

## Status

Course content is under active development. See `PROGRESS.md`.

## License

MIT — see [`LICENSE`](LICENSE).
