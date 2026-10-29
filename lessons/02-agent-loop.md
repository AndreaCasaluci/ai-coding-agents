# 02 — The Agent Loop

> **Objectives**
> - Trace a run as a state machine.
> - Implement the loop, including termination and error handling.
> - Recognise the four classic loop bugs.

## Anatomy of a turn

```
        ┌────────────────────────────────────────────┐
        │ 1. enforce budget on transcript            │
        │ 2. model(transcript, tool_schemas)         │
        │ 3. append assistant message                │
        │ 4. if no tool calls → DONE                 │
        │ 5. for each tool call:                     │
        │      pre-hook → dispatch → post-hook       │
        │      append tool result                    │
        └───────────────────┬────────────────────────┘
                            └──► next turn
```

That is `Agent.run` in `mini_agent/agent.py`, minus logging. The whole file is
worth reading once, slowly.

## The transcript is the state

There is no hidden memory. The state of the run is the message list:

```python
[
  Message("system", "..."),
  Message("user", "fix the bug"),
  Message("assistant", "", [ToolCall("c1", "read_file", {...})]),
  Message("tool", "...file contents...", tool_call_id="c1"),
  Message("assistant", "Fixed it."),
]
```

Three invariants:

1. **Pairing.** Each `ToolCall.id` gets exactly one `tool` message with the
   same id, immediately after. Break this and the API returns 400.
2. **Order.** Tool results follow their assistant message, in the same order.
3. **Roles.** `system` first, then alternating-ish `user`/`assistant`, with
   `tool` messages only after an assistant tool call.

Most "agent is broken" bugs are a violated invariant, not a bad model.

## Termination

An agent needs at least four exits:

| Exit | Trigger | Result |
|---|---|---|
| `completed` | assistant replies with no tool calls | success |
| `max_turns` | loop counter hit the limit | partial, needs review |
| `error` | model/transport raised | failure with message |
| `budget` | transcript cannot fit | failure or forced compaction |

`max_turns` is not a nicety. Models get stuck in retry loops — calling the same
failing tool with the same arguments, forever. A bound turns an infinite bill
into a debuggable transcript.

```python
for turns in range(1, max_turns + 1):
    ...
else:
    stopped = "max_turns"
```

Note the `for/else`: the `else` runs only if no `break`, i.e. the model never
finished. That is exactly the semantic you want.

## Failure containment

The loop must survive:

- **Tool errors** → returned as a `tool` message, so the model can adapt.
- **Denied actions** → returned as `DENIED: reason`, so the model can choose
  another path instead of crashing.
- **Model errors** → captured in `RunResult.error`, transcript preserved.
- **Malformed tool arguments** → rejected by dispatch, reported as text.

```python
result = tools.dispatch(call.name, args)   # never raises
```

Compare with the naive version, `getattr(tools, name)(**args)`, which turns one
bad argument into a dead session.

## The four classic loop bugs

**1. The orphan tool call.** You trim history and cut between an assistant tool
call and its result. Fix: trim at turn boundaries (see `ContextBudget.enforce`).

**2. The silent retry.** A tool fails; the harness swallows the error and
returns an empty string. The model sees "success", retries the same action, and
you burn 20 turns. Fix: errors are messages, always.

**3. The unbounded loop.** No turn limit, no budget. Fix: both, always.

**4. The lost final answer.** The model's last turn contains both a tool call
and prose; you return the prose before the tool result arrives. Fix: a run is
complete only when a reply has *no* tool calls.

## ReAct, briefly

The 2022 ReAct paper formalised *reason → act → observe* interleaving. Modern
agents are ReAct with better tooling, but the label still appears in papers and
job posts. What matters practically:

- Reasoning text before a tool call improves tool selection.
- Reasoning text is **not** verified. "I checked the tests" can be a lie; only
  the tool result is evidence.

That asymmetry — reasoning is cheap talk, tool results are evidence — is the
core of module 11.

## Observability

Every turn should emit structured events. The harness here emits
`turn_start`, `tool`, `tool_denied`, `edit_denied`, `turn_end`, `session_end`.
You do not need a dashboard on day one; you need a transcript and a log you can
grep when something goes wrong at 5pm.

```python
agent = Agent(..., on_event=lambda e, p: print(e, p))
```

## Lab

```bash
python3 labs/L02_loop.py
```

The lab runs four scenarios: a clean two-turn task, a tool error the model
recovers from, a model stuck in a retry loop that hits `max_turns`, and a
denied action. Read each transcript.

🔬 **Break it:** delete the `break` when there are no tool calls and watch the
scripted model exhaust. Then remove the turn limit and watch it never stop.

## ✅ Checkpoint

1. What are the three transcript invariants, and what breaks if you violate
   each?
2. Why return tool errors as messages instead of raising?
3. When is a run "complete"?
4. Why does the loop enforce the budget *before* the model call?
5. What is the difference between reasoning text and evidence?

<details>
<summary>Answers</summary>

1. Pairing (API 400), order (API 400 / confused model), roles (API 400).
2. So the model can adapt; a raise kills the run and loses the work.
3. When an assistant message has no tool calls.
4. Overflow is unrecoverable mid-call; trimming after is too late.
5. Reasoning is unverified text; tool results are observations from the
   environment.
</details>
