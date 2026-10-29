# Reading list

Canonical sources, in rough order of usefulness. Links are to primary material;
blog posts are included only where they named a problem better than the paper.

## Protocols and conventions

- **Model Context Protocol** — <https://modelcontextprotocol.io>
  The spec and the primitive model (tools / resources / prompts).
- **AGENTS.md** — <https://agents.md>
  The cross-vendor instruction-file convention.
- **JSON-RPC 2.0** — <https://www.jsonrpc.org/specification>
  Short, and you will need it to read MCP traces.

## Agents

- **ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al.,
  2022) — <https://arxiv.org/abs/2210.03629>
  Where the reason/act/observe loop comes from.
- **Building Effective Agents** (Anthropic) —
  <https://www.anthropic.com/research/building-effective-agents>
  Workflows vs agents, and why the simplest thing that works usually wins.
- **Lost in the Middle** (Liu et al., 2023) — <https://arxiv.org/abs/2307.03172>
  The empirical basis for "context rot".

## Security

- **OWASP Top 10 for LLM Applications** —
  <https://owasp.org/www-project-top-10-for-large-language-model-applications/>
  Prompt injection, excessive agency, supply chain.
- **Simon Willison's prompt injection tag** —
  <https://simonwillison.net/tags/prompt-injection/>
  The best running record of what actually breaks, and why prompts do not fix it.
- **The lethal trifecta** (private data + untrusted content + external
  communication) — the mental model for exfiltration risk.

## Evaluation

- **pass@k** — the HumanEval paper (Chen et al., 2021) introduced the metric;
  the idea generalises to any non-deterministic agent.
- **SWE-bench** — <https://www.swebench.com>
  The reference benchmark for repo-level coding agents; read the task format
  even if you never run it.
- **Your own incident log** — the highest-value eval suite you will ever have.

## Practice

- **Google's "Code Review" guide** —
  <https://google.github.io/eng-practices/review/>
  Written for humans, applies directly to reviewing agent diffs.
- **Git worktrees** — <https://git-scm.com/docs/git-worktree>
  The cheapest isolation primitive for parallel agents.

## A note on staleness

Product documentation changes monthly; the concepts above do not. If a lesson
and a vendor doc disagree about *configuration*, trust the vendor. If they
disagree about *mechanism*, trust the mechanism — and check the trace.
