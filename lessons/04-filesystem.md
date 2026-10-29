# 04 — The Filesystem as the World

> **Objectives**
> - Explain why coding agents are filesystem-shaped.
> - Design a read/search/edit tool surface that survives stale state.
> - Recognise the path and patch failure modes before they cost you a file.

## Why the repo is the interface

An agent that can read, search, and edit files can work on any language, any
framework, any build system — without a bespoke integration. The filesystem is
the lowest common denominator of software work, and it already has the
properties you need: durable, diffable, versioned, and inspectable.

This is why the dominant coding-agent design is "a shell with opinions", not
"a plugin for each IDE".

## The canonical surface

Six tools cover almost everything:

| Tool | Purpose | Read/write |
|---|---|---|
| `list_files(path, depth)` | orientation | read |
| `read_file(path, start, end)` | inspect | read |
| `search(pattern, glob)` | locate | read |
| `write_file(path, content)` | create / replace | write |
| `edit_file(path, old, new)` | surgical change | write |
| `delete_file(path)` | remove | write |

Notice what is missing: no `move`, no `chmod`, no `git`. Add them only when the
task demands it. Every extra tool is context spent and a new way to be wrong.

## Read before edit is not optional

The model's knowledge of a file is a **copy in the transcript**. That copy goes
stale the moment anything else touches the file: another agent, the user, a
formatter, a build step.

```
turn 3: read_file("app.py")      → copy A in context
turn 4: user edits app.py        → disk is now B
turn 5: model edits based on A   → corrupts the user's change
```

The harness cannot fully prevent this. It can make it *detectable*:

- **Unique-anchor edits.** `edit_file(old, new)` fails if `old` is missing or
  appears more than once. A stale copy usually fails loudly instead of
  silently overwriting.
- **Read-before-write tracking.** Some harnesses refuse an edit to a file that
  was not read in this session, or whose mtime changed since the read.
- **Small reads.** Re-read the changed region before a second edit, not the
  whole file.

## Why patches beat rewrites

`write_file` with full content is the most dangerous tool in the box:

```
model has stale copy (200 lines)
write_file(path, stale_content)
→ 3 lines of the user's new work are gone
```

`edit_file(old, new)` with a unique anchor:

```
old = "def parse_date(s):\n    return datetime.strptime(s, FMT)"
new = "def parse_date(s):\n    if not s:\n        raise ValueError('empty')\n    return datetime.strptime(s, FMT)"
```

is bounded: it either matches exactly once and applies, or it fails and says
why. The blast radius is the anchor, not the file.

> Rule of thumb: **rewrite only when creating a new file.** For existing files,
> edit.

## Staleness in practice

The most common agent loop is:

1. Read a 300-line file (7k tokens).
2. Make edit #1.
3. Make edit #2 using the *pre-edit* content as the anchor.
4. Edit #2 fails or, worse, applies in the wrong place.

Mitigations, in order of effectiveness:

- **Edit in one call when possible** — one `old`/`new` covering both changes.
- **Re-read the region** between edits (cheap: `start`/`end`).
- **Anchor on small, unique strings**, not whole functions.
- **Verify after editing**: read back the region or run the tests.

## Search is the real superpower

An agent with `grep` does not need the repo in context. It needs to know *where
to look*.

Good search output:

```
src/dates.py:41: def parse_date(s):
tests/test_dates.py:12: from src.dates import parse_date
```

Bad search output:

```
[7000 lines of matches]
```

Design rules:

- Cap matches (200 is plenty) and say when you capped.
- Include path and line number so the next read is a range, not a file.
- Support a glob filter (`*.py`) — it is the cheapest precision tool available.
- Return `(no matches)` explicitly. Silence reads as success.

## Large files

A 5,000-line generated file will blow the budget on one read. The tool must:

- truncate at a known character limit and **say so**,
- support line ranges,
- never truncate silently mid-token without a marker.

`Workspace.read` does this with `MAX_READ_CHARS` and an explicit
`[truncated: ...]` suffix. The model can then ask for a range. Without the
marker, it believes it saw the whole file and edits blind.

## Path safety

The agent supplies paths as text. Text can escape:

```
../../etc/passwd
/absolute/path
link → /etc/passwd        (symlink)
a/../../b
```

The only reliable check is: **resolve to a real path, then verify containment**.

```python
real = (root / path).resolve()
if real != root and root not in real.parents:
    raise WorkspaceError(...)
```

Note `.resolve()` follows symlinks, so the symlink case is caught. Note also
that this is a *correctness* boundary, not a security boundary against a
hostile process — a determined attacker with code execution can bypass it. Real
isolation is a container (module 12).

## Git is your undo button

Before an agent session on a real repo:

```bash
git status          # know what is already dirty
git switch -c agent/task-name
```

After:

```bash
git diff            # the only honest summary of what happened
```

An agent's prose summary is a claim. `git diff` is evidence. Make reviewing the
diff a habit and the agent's self-report becomes optional.

For parallel agents, use **worktrees** — separate checkouts on separate
branches sharing one object store. Cheap isolation, no stashing, no conflicts
until merge.

## Lab

```bash
python3 labs/L04_filesystem.py
```

The lab demonstrates the path jail (including a symlink escape), unique-anchor
editing, ambiguous-match rejection, truncation with a marker, and a stale-copy
corruption that a rewrite causes and an edit prevents.

🔬 **Break it:** comment out the containment check in `Workspace.resolve` and
re-run. Watch `../../etc/passwd` resolve.

## ✅ Checkpoint

1. Why is the filesystem the natural interface for a coding agent?
2. What makes `edit_file(old, new)` safer than `write_file(content)`?
3. How does a stale read produce a wrong edit, and what detects it?
4. Why must truncation be announced?
5. What is the difference between a correctness boundary and a security
   boundary here?

<details>
<summary>Answers</summary>

1. It is universal, durable, diffable, and versioned.
2. The blast radius is bounded by the anchor; ambiguity fails loudly.
3. The model's copy diverges from disk; unique-anchor failure or read-back
   detects it.
4. Otherwise the model believes it saw the whole file and edits blind.
5. The path jail prevents mistakes; it does not stop code execution or a
   determined attacker. Only isolation does.
</details>
