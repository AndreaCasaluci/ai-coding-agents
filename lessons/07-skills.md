# 07 — Skills

> **Objectives**
> - Explain progressive disclosure and why it is the core idea.
> - Write a `SKILL.md` whose description actually triggers.
> - Choose between a skill, a tool, and an instruction.

## The capability explosion

An agent that can do 50 things cannot hold 50 procedures in context. Forty
skills at ~800 tokens each is 32k tokens of instructions — the entire budget
spent on capability the task does not need. Quality drops, cost rises.

The fix is not better summarisation. It is **not loading what you do not need**.

## Progressive disclosure

```
L1  catalog: name + one-line description        ~50 tokens/skill, always loaded
     │
     ├─ task matches description?
     ▼
L2  SKILL.md body: the procedure               ~500–2,000 tokens, loaded on demand
     │
     ├─ procedure needs a template or script?
     ▼
L3  resources: files, scripts, examples        unbounded, read/executed on demand
```

Ten skills cost ~500 tokens at L1. Only the one you use costs its full body.
That is a 60× reduction in fixed cost, and — more importantly — it keeps the
context focused.

This is exactly how you already work: you know which runbooks exist, you open
one when the incident matches.

## Anatomy of a skill

```
skills/
  release-notes/
    SKILL.md          ← required
    template.md       ← optional resource
    collect.py        ← optional script
```

```markdown
---
name: release-notes
description: Write release notes from git history. Use when asked to prepare
  a release, changelog, or "what changed since vX".
---

# Release notes

1. Determine the range: `git log --oneline <last-tag>..HEAD`.
2. Group commits: features, fixes, breaking changes, chores.
3. Drop merge commits and version bumps.
4. Follow `template.md` exactly. Keep each bullet under 100 chars.
5. If a breaking change exists, put it first and mark it **BREAKING**.
```

Two fields in the frontmatter matter:

- **`name`** — stable identifier, matches the folder.
- **`description`** — **the trigger**. This is prompt text, and it is the only
  thing the model sees before deciding to load the skill.

## The description is the whole game

A skill that never loads is dead weight; a skill that loads for everything is
context poison.

| Bad description | Why |
|---|---|
| "Helps with releases" | Vague; competes with everything |
| "A skill for doing release notes" | Restates the name, adds no trigger |
| "Release notes, changelogs, version bumps, tags, GitHub releases, semver, git log, commit messages, …" | Keyword soup; loads too often |

| Good description | Why |
|---|---|
| "Write release notes from git history. Use when asked to prepare a release, changelog, or 'what changed since vX'." | Says *what* and *when*, in the user's words |

Formula: **what it produces + when to use it + the phrases a user would say.**

## Skills vs tools vs instructions

| | Instruction (`AGENTS.md`) | Skill | Tool |
|---|---|---|---|
| Loaded | always | on demand | schema always, result on call |
| Contains | rules, commands, traps | a procedure | an action |
| Changes | how the model behaves | what the model knows how to do | what the model can do |
| Cost | small, fixed | medium, when used | schema always + result |
| Example | "run `make test`" | "how to write a migration" | `read_file` |

A useful test: if it can be *done*, it is a tool. If it is a *procedure*, it is
a skill. If it is a *constraint*, it is an instruction.

## Scripts and resources

Skills can ship code. Two patterns:

**Resource** — a template the model reads and fills:

```markdown
Follow `template.md`. Do not invent sections.
```

**Script** — a deterministic step the model should not re-derive:

```
skills/
  db-migration/
    SKILL.md
    new_migration.py     ← generates a correctly-named, timestamped file
```

```markdown
Run `python3 skills/db-migration/new_migration.py <name>`.
Do not create the file by hand — the timestamp format matters.
```

This is the same principle as hooks: **deterministic work belongs in code, not
in a prompt.** A skill can carry the code and the instructions for using it.

⚠️ A skill script is executed code. Treat a third-party skill folder like a
third-party dependency.

## Failure modes

| Failure | Cause | Fix |
|---|---|---|
| Skill never loads | Vague description | Rewrite trigger in user language |
| Skill loads for everything | Description too broad | Add "Use when…" and negative scope |
| Skill loads but is ignored | Body is prose, not steps | Numbered steps, concrete commands |
| Skill contradicts `AGENTS.md` | Two sources of truth | Delete one; keep rules in instructions |
| Skill is 3,000 tokens of context | No progressive disclosure inside | Move detail to resources (L3) |
| Model re-derives instead of running the script | Not told to run it | "Run X. Do not do Y by hand." |

## Authoring checklist

- [ ] Name matches folder, lowercase, hyphens.
- [ ] Description states output + trigger phrases, under ~200 chars.
- [ ] Body is numbered steps, not an essay.
- [ ] Every command is copy-pasteable and correct.
- [ ] Detail lives in resources, not the body.
- [ ] No rule duplicated from `AGENTS.md`.
- [ ] Tested: does it load for the intended task and *not* for a neighbouring
      task?

## Lab

```bash
python3 labs/L07_skills.py
```

You will create two skills, inspect the L1 catalog cost, load one to L2, read a
resource at L3, and see a vague description fail to match while a specific one
succeeds.

🔬 **Break it:** give two skills nearly identical descriptions and watch the
matcher pick arbitrarily.

## ✅ Checkpoint

1. What problem does progressive disclosure solve, in token terms?
2. What are the three disclosure levels?
3. What makes a description good or bad?
4. Skill, tool, or instruction: "never touch `legacy/`"?
5. Why ship a script with a skill instead of describing the steps?

<details>
<summary>Answers</summary>

1. Fixed context cost: N skills cost ~50 tokens each instead of ~800.
2. Catalog line, full body, resources/scripts.
3. Good: output + when + user phrases. Bad: vague or keyword soup.
4. Instruction.
5. Deterministic work (naming, timestamps, formatting) should not be
   re-derived by a probabilistic model.
</details>
