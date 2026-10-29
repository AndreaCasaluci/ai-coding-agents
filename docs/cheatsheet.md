# Cheat sheet

One page. Print it.

## The loop

```
budget → model(transcript, tools) → assistant message
      → no tool calls? DONE
      → for each call: pre-hook → dispatch → post-hook → tool message
      → repeat
```

Invariants: tool call ids are paired, results follow in order, a run is done
only when a reply has no tool calls.

## The five components

| Component | Owns | Failure |
|---|---|---|
| Model | next token | hallucination, staleness |
| Harness | loop, context, limits | bad trimming, runaway |
| Tools | actions | wrong schema, blast radius |
| Environment | repo, runtime, secrets | missing deps, leaks |
| Human | task, approval, review | vague task, rubber stamp |

## Context budget

```
usable = window − reserve_for_reply
```

Spend it in this order: task → rules → narrow code → evidence → recent turns →
background. Everything else is retrieval or a skill.

- Cost grows ~quadratically with turns (each turn resends the transcript).
- Compaction is lossy; mark summaries as summaries.
- Smaller, relevant context beats larger, complete context.

## Tool design

- Flat parameters, few of them, enums over strings.
- Descriptions are prompt text: say *what* and *when*.
- Errors are messages, never exceptions.
- Truncate with a marker; paginate reads.
- Declare side effects; keep the surface under ~20.

## Instructions / skills / tools

| | Loaded | Contains | Example |
|---|---|---|---|
| `AGENTS.md` | always | constraints | "run `make test`" |
| Skill | on demand | procedure | "how to write a migration" |
| Tool | schema always | action | `read_file` |

Description formula for skills: **output + when to use + user phrases.**

## Hooks

| Event | Can |
|---|---|
| `pre_tool` | block, rewrite args |
| `post_tool` | redact, truncate |
| `pre_edit` | block a path |
| `post_edit` | format, typecheck |
| `session_start/end` | setup, metrics |

- A prompt is a suggestion; a hook is a rule.
- Fail closed for guards.
- Return `None` to abstain, not `True`.
- Layers: instruction < hook < permission < sandbox.

## Subagents

- Trade: fidelity + money → context headroom + parallelism.
- Task statement must be self-contained.
- Return structured, cited summaries, not prose.
- Fan out for reading; serialise for writing.
- Reviewer pattern: fresh context, read-only, cites `file:line`.

## MCP

- JSON-RPC 2.0 over stdio or HTTP.
- `initialize` → `tools/list` → `tools/call`.
- Tools (model), resources (app), prompts (user).
- A server is a program you are handing your agent.
- Notifications have no `id` and no response.

## Verification ladder

```
compile → lint → types → unit → integration → manual review
```

A model's "done" is text. A test result is evidence.

## Evals

- Task + fresh environment + outcome grader.
- Grade the workspace, not the transcript.
- Include a refusal case and a no-op case.
- Report pass@k; one run is noise.
- Every incident becomes a permanent case.

## Safety

- Threats: mistake, injection, supply chain, exfiltration.
- Injection cannot be fixed with a prompt; instructions and data share a channel.
- Make success uninteresting: no secrets, no network, no shell.
- Default deny for side effects; approval for push, delete, install, deploy.
- Path jail = correctness. Container = security.

## Workflow

```
explore → plan → execute → verify → report
```

- Plan before editing; read before writing.
- TDD: the test is a fixed target and its failure is evidence.
- One concern per session; fresh session after three failures.
- Cap diff size; review before commit; human commits.
- Stop when: same failure twice, diff grows while red, scope creep, or you
  cannot explain the change.

## Metrics

Acceptance rate, revert rate, human edit rate, cycle time, cost per merged PR,
escaped defects. Not lines generated.

## When something goes wrong

1. Stop the session.
2. Preserve the transcript.
3. Read the diff, not the summary.
4. Revert to a known state.
5. Write an eval that reproduces it.
6. Add a control at the lowest layer that would have prevented it.
