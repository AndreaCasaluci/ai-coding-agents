# 03 — Tools & Function Calling

> **Objectives**
> - Explain the function-calling round trip precisely.
> - Write schemas and descriptions that get called correctly.
> - Design a tool surface small enough to choose from.

## The round trip

```
harness                          model
   │                               │
   │  messages + [tool schemas] ──►│
   │                               │  decides: call read_file
   │◄── assistant.tool_calls ──────│
   │                               │
   │  executes read_file(...)      │
   │                               │
   │  tool message (result) ──────►│
   │                               │  continues reasoning
```

The model emits a *request*. The harness validates, executes, and appends the
result. **The model never runs anything.** This is the security boundary and
the debugging boundary: if a tool did something wrong, the harness did it.

## A tool is a prompt

```python
@tool
def read_file(path: str, start: int = 1, end: int | None = None) -> str:
    """Read a text file. Optionally read only lines [start, end]."""
    ...
```

becomes:

```json
{
  "name": "read_file",
  "description": "Read a text file. Optionally read only lines [start, end].",
  "parameters": {
    "type": "object",
    "properties": {
      "path":  {"type": "string"},
      "start": {"type": "integer", "default": 1},
      "end":   {"type": "integer", "default": null}
    },
    "required": ["path"]
  }
}
```

The description is **prompt text**. "Read a file" and "Read a text file.
Optionally read only lines [start, end]. Use this before editing." produce
different behaviour. Write descriptions for the model, not for your IDE.

### Schema design rules

| Rule | Why |
|---|---|
| Flat parameters | Nested objects are where models hallucinate structure |
| Few parameters | Each one is a chance to get it wrong |
| Enums over free strings | `mode: "fast" \| "thorough"` beats `mode: "..."` |
| Defaults for everything optional | Reduces required-field failures |
| Names that say the verb | `search_code` > `query` |
| No secrets in defaults | Schemas are sent to a third party |

## Dispatch: validate, execute, contain

```python
def dispatch(self, name, arguments):
    tool = self.get(name)
    if tool is None:
        return ToolResult(False, f"Unknown tool `{name}`")
    if "__parse_error__" in arguments:
        return ToolResult(False, "Could not parse arguments")
    return tool.run(arguments)          # catches TypeError and Exception
```

Three failure classes, all returned as text:

1. **Unknown tool** — the model hallucinated a name. Include the available list
   so it can recover.
2. **Malformed arguments** — JSON parse error or wrong keys. Say which.
3. **Tool exception** — the function blew up. Include the type and message.

Never let a tool exception escape the loop. The model cannot fix a problem it
cannot see.

## Tool result design

Results go straight into the context window, so their size is a design
decision:

- **Truncate at a known limit** and say so: `[truncated: 120k chars, showing 40k]`.
- **Paginate by lines** for reads; let the model ask for a range.
- **Summarise noisy commands**: `pytest -q` not `pytest -vv` unless debugging.
- **Include the location** in search results (`path:line: text`) so the next
  read is targeted.
- **Return stable text**, not ANSI colour codes or progress bars.

A tool that returns 50k tokens per call will destroy the session in four turns.
That is a harness bug, not a model bug.

## Side effects

Mark tools that change state. The harness uses this for permissions, hooks, and
UI prompts:

```python
@tool(side_effect=True, needs_permission=True)
def write_file(path: str, content: str) -> str: ...
```

Read-only tools can usually run unattended. Writes, deletes, network calls, and
shell commands need a policy. Module 12 is entirely about that policy.

## How many tools?

Two opposing pressures:

- Too few → the model cannot express the task.
- Too many → selection accuracy drops, schemas eat context, and similar names
  get confused.

Practical guidance:

- **Under ~20 tools** is comfortable; beyond that, group or load on demand.
- **Avoid near-duplicates.** `read_file` and `cat_file` will be confused.
- **Prefer one flexible tool** over five narrow ones when the parameter space
  is the same (`search(pattern, glob)` beats `search_py`, `search_js`).
- **Load tool sets per task** (module 07's progressive disclosure applies to
  tools too).

💡 *In practice* — Most coding agents converge on a similar core: read, write,
edit, list/glob, grep, run command. The differences are in permission models
and result formatting, not in the verbs.

## The shell tool is special

A shell tool is the most powerful and most dangerous tool you can expose. It
subsumes every other tool (`cat`, `sed`, `find`, `git`) and every attack
(`rm -rf`, `curl | sh`, `git push --force`).

If you expose one, the harness must:

- run it in a sandbox or with an allowlist,
- cap output,
- set a timeout,
- never pass model text through a shell unquoted.

Module 12 covers the specifics. For now: treat `run_shell` as a loaded weapon,
not a convenience.

## Lab

```bash
python3 labs/L03_tools.py
```

You will inspect generated schemas, dispatch valid and invalid calls, and watch
a bad description cause a wrong tool choice in a scripted policy.

🔬 **Break it:** add a second tool named `read` that also reads files. Watch the
policy choose the wrong one.

## ✅ Checkpoint

1. Who executes a tool call? What does the model actually emit?
2. Why are tool errors returned as messages?
3. Give three schema rules and the failure each prevents.
4. What is the cost of a tool that returns 50k tokens?
5. Why is a shell tool categorically different from `read_file`?

<details>
<summary>Answers</summary>

1. The harness. The model emits a name + JSON arguments.
2. So the model can adapt and the run survives.
3. Flat (hallucinated nesting), enums (invalid values), defaults (missing
   required fields).
4. It consumes the context budget and evicts the actual task.
5. It subsumes all other tools and all destructive operations; its blast radius
   is the whole machine.
</details>
