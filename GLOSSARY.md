# Glossary

Terms are defined as this course uses them. Where the industry is inconsistent,
the most common meaning wins and the alternative is noted.

**Agent** — A system that repeatedly calls a language model, lets it act
through tools, and feeds the results back, until a stopping condition is met.
A chatbot with one model call is not an agent. The loop is what makes it one.

**Agent loop** — The cycle of *model call → tool call(s) → observation →
model call*. Also called the ReAct loop, after the 2022 paper, though every
implementation differs.

**AGENTS.md** — A convention for a Markdown file at a repo root (or in
subdirectories) holding instructions for coding agents. Read automatically by
many tools; the closest thing to a cross-vendor standard for agent context.

**Allowlist** — The set of commands, paths, or tools an agent may use without
asking. Everything else is denied or prompts the human.

**Context window** — The maximum number of tokens a model can attend to in one
call, counting system prompt, history, tool results, and the reply. Not memory;
it is recomputed (or cached) every call.

**Compaction** — Replacing old conversation with a summary so the run can
continue past the context limit. Lossy by definition, which is why it is a
source of subtle bugs.

**Eval** — A repeatable test of agent behaviour: a task, an environment, and a
grader. The agent equivalent of a unit test, but with a non-deterministic
subject.

**Function calling / tool calling** — The model emitting a structured request
("call `read_file` with `{"path": "a.py"}`") that the harness executes. The
model never executes anything itself.

**Hook** — A user-defined handler bound to a lifecycle event (before a tool
runs, after an edit, on session start). Hooks are code, not prompts, so they
are deterministic.

**MCP (Model Context Protocol)** — A JSON-RPC-based protocol for exposing
tools, resources, and prompts to agents over a standard interface, so one
server works with many clients.

**Prompt injection** — Instructions hidden in content the agent reads (a file,
a web page, a tool result) that redirect its behaviour. The central unsolved
security problem for agents.

**Progressive disclosure** — Loading only a small description of a skill or
tool up front, and its full content only when needed. The main technique for
keeping large capability sets inside a context budget.

**Sandbox** — An enforced boundary around what the agent can touch: a
container, a worktree, a path jail, a permission profile. Enforcement is
outside the model.

**Skill** — A packaged, discoverable procedure (usually a folder with a
`SKILL.md` and optional scripts/resources) that an agent loads when a task
matches its description.

**Subagent** — A separate agent run, usually with its own context window,
spawned by a parent agent for a subtask. Returns a summary, not its full
transcript.

**System prompt** — The harness-supplied instructions that frame every call:
identity, rules, tool guidance. Not user-editable in most products, but the
first thing to understand when behaviour seems wrong.

**Token** — A subword unit of text. Roughly 4 characters of English, but code
and non-English text are less efficient. All limits and costs are in tokens.

**Tool** — A capability exposed to the model as a name, a description, and a
JSON schema. The description is prompt text: it changes behaviour.

**Turn** — One model call plus the tool executions it requested. A task is many
turns.

**Worktree** — A separate checkout of a repo on its own branch, sharing the
same object store. Cheap isolation for parallel agent runs.
