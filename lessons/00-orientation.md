# 00 — Orientation

> **Objectives**
> - Define "coding agent" precisely enough to argue about it.
> - Name the five components every agent has.
> - Read a transcript and say what happened, in order.

## The one-sentence definition

A coding agent is **a language model in a loop, with tools, inside an
environment, under some budget, steered by a human.**

Every word is load-bearing. Remove the loop and you have a chatbot. Remove the
tools and you have a code explainer. Remove the environment and you have a
text generator. Remove the budget and you have a runaway process. Remove the
human and you have a very confident intern with root access.

## What it is not

| Thing | Why it is not an agent |
|---|---|
| Autocomplete | One prediction, no actions, no loop |
| Chat assistant | Can talk about code, cannot run or change it |
| "AI-powered IDE" | A product; may or may not contain an agent |
| Workflow engine | Deterministic graph; the model is not choosing the path |
| Agent *framework* | A library for building agents, not an agent |

The distinction that matters: **who decides the next action?** In a workflow,
a human wrote the graph. In an agent, the model chooses at each step, within
bounds the harness sets.

## The five components

```
            ┌──────────────────────────────────────────┐
            │                  HUMAN                   │
            │        task, approvals, review           │
            └───────────────────┬──────────────────────┘
                                │
        ┌───────────────────────▼───────────────────────┐
        │                  HARNESS                      │
        │  system prompt · context budget · loop ·      │
        │  permissions · hooks · logging                │
        └───────┬───────────────────────────┬───────────┘
                │                           │
      ┌─────────▼─────────┐       ┌─────────▼─────────┐
      │       MODEL       │       │      TOOLS        │
      │  next-token       │       │  read · edit ·    │
      │  prediction       │       │  search · shell   │
      └───────────────────┘       └─────────┬─────────┘
                                            │
                                  ┌─────────▼─────────┐
                                  │   ENVIRONMENT     │
                                  │  repo, runtime,   │
                                  │  network, secrets │
                                  └───────────────────┘
```

1. **Model** — stateless function: text in, text out. No memory between calls.
2. **Harness** — the program around it. Owns the loop, the transcript, the
   budget, and the guardrails. This is what you actually configure.
3. **Tools** — the model's only way to affect the world. Described in text.
4. **Environment** — the repo, the shell, the test suite, the credentials.
5. **Human** — sets the task, approves risky actions, judges the result.

The harness is the part people underestimate. Two products with the same model
can behave completely differently because their harnesses differ. When someone
says "model X is better at coding", ask which harness they used.

## One run, step by step

Task: *"The `parse_date` function crashes on empty input. Fix it."*

```
turn 1  model: I should find parse_date.        → search("def parse_date")
        tool : src/dates.py:41: def parse_date(s):
turn 2  model: Read it.                          → read_file("src/dates.py", 35, 55)
        tool : [50 lines of code]
turn 3  model: Add a guard.                      → edit_file(path, old, new)
        tool : Edited src/dates.py (1 replacement)
turn 4  model: Verify.                           → run_tests("tests/test_dates.py")
        tool : FAILED test_empty_string
turn 5  model: The test expects ValueError, not None. Fix the guard.
                                                 → edit_file(...)
turn 6  model: Verify again.                     → run_tests(...)
        tool : 12 passed
turn 7  model: Done. Guard added, tests pass.
```

Seven model calls, four tool calls, one failed attempt. **The failure is the
interesting part**: it is the loop, not the model, that turned a wrong first
guess into a correct fix.

## Why the loop is the unit of design

A single model call cannot recover from its own mistake. A loop can, because
the tool result re-enters the context and the model gets another chance. That
is the entire value proposition — and also the entire risk, because a loop
that cannot recognise failure will happily make things worse for twenty turns.

So the harness's job is to make failure *visible and cheap*:

- tool errors returned as text, not exceptions,
- tests as ground truth,
- turn and budget limits,
- a transcript you can read afterwards.

## Where this course goes

Modules 1–3 give you the primitives: tokens, the loop, tools. Modules 4–8
build the machinery that makes agents usable: the filesystem, context
management, instructions, skills, hooks. Modules 9–12 cover scale and safety.
Modules 13–14 are practice and teams. Module 15 is a capstone where you build
one.

Everything is demonstrated in `mini_agent/`, about 2,000 lines of dependency-free
Python. Read it alongside the lessons.

## Lab

```bash
python3 labs/L00_orientation.py
```

The lab runs a scripted agent and prints the raw transcript. Your job is to
annotate it: which messages came from the model, which from tools, and where
the context grew.

## ✅ Checkpoint

1. Why is a chat assistant that can "write code for you" not an agent?
2. Name the five components and one failure mode of each.
3. In the walkthrough above, what would have happened without the test tool?
4. Why can two products with the same model behave differently?
5. What is the harness's job when a tool fails?

<details>
<summary>Answers</summary>

1. It does not act. No tools, no loop, no environment changes.
2. Model (hallucination, staleness), harness (bad context/limits), tools
   (wrong schema, dangerous side effects), environment (missing deps, secrets),
   human (vague task, rubber-stamping).
3. The agent would have declared success after turn 3, with a fix that fails
   the actual spec.
4. Different harnesses: prompts, tools, context management, guardrails.
5. Turn it into a message the model can read and react to, without crashing
   the run.
</details>
