# 08 — Hooks & Lifecycle Events

> **Objectives**
> - Explain why some behaviour must not live in a prompt.
> - Implement observe / block / mutate hooks.
> - Layer hooks, permissions, and sandboxes correctly.

## Prompts are suggestions. Hooks are rules.

You can write "never edit `.env`" in `AGENTS.md`. The model will usually
comply. Usually is not a security property.

A hook is **code bound to an event**. It runs every time, in a deterministic
order, and its verdict is enforced by the harness:

```python
hooks.on(PRE_EDIT, deny_paths((".env", ".git", "secrets")))
```

That is not a suggestion. It is a branch in the harness's control flow.

The design principle:

> If violating the rule is unacceptable, it must not depend on the model's
> cooperation.

## The event surface

| Event | When | Typical use |
|---|---|---|
| `session_start` | before the first model call | load context, print a banner |
| `user_prompt` | task text, before it enters the transcript | rewrite, redact, reject |
| `pre_tool` | before any tool runs | block, rewrite arguments, approve |
| `post_tool` | after any tool runs | redact secrets, truncate, log |
| `pre_edit` | before a write/edit/delete | protect paths, enforce style |
| `post_edit` | after a successful write/edit | format, typecheck, stage |
| `session_end` | after the loop finishes | summary, metrics, cleanup |

`pre_*` events are **gates**. `post_*` events are **filters and side effects**.
Confusing the two produces hooks that cannot prevent anything.

## Three verbs

### Observe

```python
def audit(handle):
    def hook(payload):
        handle.write(json.dumps(payload) + "\n")
        return None          # None = abstain
    return hook
```

Cheap, boring, invaluable. When an agent does something strange, the audit log
tells you what it actually called.

### Block

```python
def deny_paths(prefixes):
    def hook(payload):
        path = payload["path"]
        if any(path.startswith(p) for p in prefixes):
            return HookResult(allow=False, reason=f"protected: {path}")
        return None
    return hook
```

The denial becomes a `DENIED: …` tool message. The model sees it and can choose
another path. Blocking is not crashing.

### Mutate

```python
def redact(payload):
    cleaned = SECRET_RX.sub("[REDACTED]", payload["content"])
    if cleaned != payload["content"]:
        return HookResult(payload={**payload, "content": cleaned})
    return None
```

Mutation is powerful and dangerous. Rewriting a tool's *arguments* changes what
the model asked for; rewriting its *result* changes what it believes happened.
Prefer blocking over silently rewriting — the model can reason about "denied",
but not about a lie.

## Fail closed

```python
try:
    result = hook(payload)
except Exception as exc:
    return HookResult(False, f"hook raised {exc}")
```

If a safety hook crashes, the safe default is *deny*. The harness here does
this. Note the trade-off: a buggy hook can halt all work. That is usually the
right trade for a guard, and the wrong one for a formatter — so keep formatting
in `post_edit` where a failure cannot block a write.

## Hooks you will actually write

| Hook | Event | Effect |
|---|---|---|
| Protect `.env`, `.git`, `secrets/` | `pre_edit` | block |
| Redact API keys from tool output | `post_tool` | mutate |
| Auto-format after edit | `post_edit` | side effect |
| Run typecheck after edit | `post_edit` | side effect; surface errors |
| Require approval for `git push` | `pre_tool` | block until human says yes |
| Block `rm -rf`, `--force`, `DROP TABLE` | `pre_tool` | block |
| Append every call to a JSONL log | `pre_tool` | observe |
| Enforce a max diff size | `pre_edit` | block |
| Add a co-author trailer on commit | `post_edit` | mutate |

## Hooks vs permissions vs sandboxes

These are three layers of the same defence, at increasing strength:

```
┌─────────────────────────────────────────────┐
│ instruction   "please don't"      weakest   │
├─────────────────────────────────────────────┤
│ hook          deterministic policy          │
├─────────────────────────────────────────────┤
│ permission    allowlist / approval / modes  │
├─────────────────────────────────────────────┤
│ sandbox       OS/container enforcement      │  strongest
└─────────────────────────────────────────────┘
```

- A **hook** sees structured events and can reason about intent ("is this path
  protected?", "does this command contain `--force`?"). It runs in-process, so
  a compromised agent process can bypass it.
- A **permission system** decides whether a *class* of action is allowed at
  all: read-only mode, allowlisted commands, per-tool approval.
- A **sandbox** enforces at the OS level: no network, read-only mounts, a
  container with no host access. It holds even if the agent is fully hostile.

Use all three. Hooks for policy and observability, permissions for coarse
capability, sandboxes for blast radius.

## Testing hooks

Hooks are code, so test them like code:

```python
def test_deny_env():
    hook = deny_paths((".env",))
    assert hook({"path": ".env"}).allow is False
    assert hook({"path": "src/app.py"}) is None
```

Two properties worth asserting for every guard:

1. It denies what it should.
2. It **abstains** on everything else — a guard that returns `HookResult(True)`
   for unrelated payloads will silently swallow payload mutations from other
   hooks.

## Lab

```bash
python3 labs/L08_hooks.py
```

You will build a bus with an audit hook, a path guard, and a secret redactor,
then watch a write to `.env` get denied, a key get scrubbed from output, and a
crashing hook fail closed.

🔬 **Break it:** make the guard return `HookResult(True)` instead of `None` for
unrelated paths and watch a later mutation get discarded.

## ✅ Checkpoint

1. Why can't "never edit `.env`" live only in `AGENTS.md`?
2. What is the difference between `pre_*` and `post_*` events?
3. Why prefer blocking over silently rewriting a result?
4. Why should a guard hook fail closed, but a formatter hook need not?
5. What does a sandbox add that a hook cannot?

<details>
<summary>Answers</summary>

1. Prompts are probabilistic; hooks are enforced control flow.
2. `pre_*` can prevent; `post_*` can only filter or react.
3. The model can reason about "denied"; a silent rewrite gives it a false
   picture of the world.
4. A broken guard must not open the gate; a broken formatter just skips
   formatting.
5. Enforcement outside the agent process, which survives a compromised or
   hostile agent.
</details>
