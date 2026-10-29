"""Lab 08 — Hooks: observe, block, mutate, fail closed.

Run: python3 labs/L08_hooks.py

Goal: build a hook bus, watch a denial and a redaction, and see a crashing
guard fail closed.
"""

from __future__ import annotations

from _helpers import note, section, temp_ws

from mini_agent import Agent, Message, ToolCall, Workspace, make_fs_tools
from mini_agent.hooks import (
    POST_TOOL,
    PRE_EDIT,
    PRE_TOOL,
    HookBus,
    HookResult,
    deny_paths,
    redact_secrets,
)
from mini_agent.llm import ScriptedLLM


def main() -> None:
    bus = HookBus()

    section("1. OBSERVE")
    events: list[dict] = []
    bus.on(PRE_TOOL, lambda p: (events.append(dict(p)), None)[-1], name="collect")
    bus.emit(PRE_TOOL, {"tool": "read_file", "arguments": {"path": "src/a.py"}})
    bus.emit(PRE_TOOL, {"tool": "write_file", "arguments": {"path": "src/b.py"}})
    print(f"  recorded {len(events)} events")
    note("Audit hooks are cheap and answer 'what did it actually call?' later.")

    section("2. BLOCK")
    bus.on(PRE_EDIT, deny_paths((".env", ".git", "secrets")), name="protect-paths")
    for path in (".env", ".git/config", "secrets/prod.yaml", "src/app.py"):
        decision = bus.emit(PRE_EDIT, {"tool": "write_file", "path": path})
        print(f"  {path:<20} allow={decision.allow!s:<5} {decision.reason}")

    section("3. MUTATE (REDACT)")
    bus.on(POST_TOOL, redact_secrets(), name="redact")
    dirty = "token=ghp_" + "a" * 24 + " and key=sk-" + "b" * 20
    decision = bus.emit(POST_TOOL, {"tool": "read_file", "content": dirty})
    print(f"  before: {dirty}")
    print(f"  after : {decision.payload['content']}")
    note("Mutation changes what the model believes it saw. Use it for redaction, sparingly.")

    section("4. ORDER AND FIRST-DENIAL-WINS")
    order: list[str] = []
    bus2 = HookBus()
    bus2.on(PRE_TOOL, lambda p: (order.append("first"), None)[-1], name="first")
    bus2.on(PRE_TOOL, lambda p: HookResult(False, "stop here"), name="second")
    bus2.on(PRE_TOOL, lambda p: (order.append("third"), None)[-1], name="third")
    result = bus2.emit(PRE_TOOL, {"tool": "rm_rf"})
    print(f"  ran: {order}, allow={result.allow}, reason={result.reason}")
    note("Later hooks do not run after a denial.")

    section("5. FAIL CLOSED")
    bus3 = HookBus()
    bus3.on(PRE_TOOL, lambda p: 1 / 0, name="broken-guard")
    result = bus3.emit(PRE_TOOL, {"tool": "write_file"})
    print(f"  allow={result.allow}, reason={result.reason}")
    note("A crashed safety hook denies. A crashed formatter just skips formatting.")

    section("6. A FULL RUN WITH GUARDS")
    with temp_ws("hooks") as tmp:
        ws = Workspace(tmp)
        ws.write("src/app.py", "print('hi')\n")
        bus4 = HookBus()
        bus4.on(PRE_EDIT, deny_paths((".env", ".git")), name="protect-paths")
        bus4.on(POST_TOOL, redact_secrets(), name="redact")

        llm = ScriptedLLM(
            Message("assistant", "Writing the env file.", [ToolCall("c1", "write_file", {"path": ".env", "content": "SECRET=1"})]),
            Message("assistant", "Reading the log.", [ToolCall("c2", "read_file", {"path": "app.log"})]),
            "Blocked on the first, redacted the second.",
        )
        ws.write("app.log", "key=sk-" + "z" * 24 + "\n")
        agent = Agent(llm, make_fs_tools(ws), workspace=ws, hooks=bus4, max_turns=5)
        result = agent.run("write .env then read app.log")
        for message in result.messages[1:]:
            print("   " + message.text().replace("\n", "\n   ")[:200])

        print(f"\n  .env exists? {ws.resolve('.env').exists()}")
        note("The denial reached the model as text; the write never happened.")
        note("The secret in the log was scrubbed before the model saw it.")

    section("7. HOOKS ARE TESTABLE")
    guard = deny_paths((".env",))
    print(f"  deny .env      -> {guard({'path': '.env'}).allow}")
    print(f"  abstain on src -> {guard({'path': 'src/app.py'})}")
    note("Abstaining (None) matters: a guard that returns True swallows later mutations.")


if __name__ == "__main__":
    main()
