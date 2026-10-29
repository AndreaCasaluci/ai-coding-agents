"""LLM abstraction.

Two implementations ship with the course:

* ``ScriptedLLM`` — replays canned responses. Lets every lab and test run
  offline, deterministically, with no API key. This is how you should test an
  agent harness: the model is the flaky dependency, so fake it.
* ``OpenAICompatLLM`` — talks to any OpenAI-compatible ``/chat/completions``
  endpoint (OpenAI, local servers, gateways). Stdlib only.

The ``LLM`` protocol is intentionally one method. Everything a harness needs
to know about a model is: give me the next assistant message.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol, Sequence

from .messages import Message, ToolCall


class LLM(Protocol):
    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        """Return the next assistant message given the transcript and tools."""
        ...


class ScriptedLLM:
    """Replays a fixed list of assistant messages, in order.

    When the script runs out it raises. That is intentional: a runaway loop
    should fail loudly in tests, not silently return filler.
    """

    def __init__(self, *responses: Message | str):
        self.responses = [r if isinstance(r, Message) else Message("assistant", r) for r in responses]
        self.calls: list[list[Message]] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        self.calls.append(list(messages))
        if not self.responses:
            raise RuntimeError(
                "ScriptedLLM exhausted: the agent asked for another turn but the "
                "script had none. This usually means the loop did not terminate."
            )
        return self.responses.pop(0)


class PolicyLLM:
    """A model stand-in defined by a function.

    Useful when you want *reactive* behaviour (look at the transcript, decide)
    without a real model. Signature: ``fn(messages, tools) -> Message``.
    """

    def __init__(self, policy: Callable[[Sequence[Message], Sequence[dict[str, Any]]], Message]):
        self.policy = policy
        self.calls: list[list[Message]] = []

    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        self.calls.append(list(messages))
        return self.policy(messages, tools)


class OpenAICompatLLM:
    """Minimal client for any OpenAI-compatible chat completions endpoint.

    Env vars:
      MINI_AGENT_BASE_URL   default https://api.openai.com/v1
      MINI_AGENT_MODEL      default gpt-4o-mini
      MINI_AGENT_API_KEY    or OPENAI_API_KEY
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.0,
        timeout: int = 120,
    ):
        self.model = model or os.environ.get("MINI_AGENT_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("MINI_AGENT_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("MINI_AGENT_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
        self.temperature = temperature
        self.timeout = timeout
        if not self.api_key:
            raise RuntimeError(
                "No API key. Set MINI_AGENT_API_KEY (or OPENAI_API_KEY), or use the "
                "offline scripted model."
            )

    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
            body["tool_choice"] = "auto"

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:800]
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM connection failed: {exc.reason}") from exc

        choice = payload["choices"][0]["message"]
        return Message.from_openai(choice)


def default_llm() -> LLM:
    """Pick a model from the environment, falling back to a helpful mock."""
    provider = os.environ.get("MINI_AGENT_PROVIDER", "mock").lower()
    if provider in {"openai", "compat", "real"}:
        return OpenAICompatLLM()
    return HeuristicLLM()


class HeuristicLLM:
    """A tiny rule-based 'model' so the CLI does something sensible offline.

    It is not intelligent. It demonstrates the *shape* of agent behaviour:
    inspect the task, request a tool, read the result, answer. If you are ever
    unsure whether a bug is in your harness or your model, swap this in — a
    deterministic model isolates harness bugs perfectly.
    """

    def complete(self, messages: Sequence[Message], tools: Sequence[dict[str, Any]]) -> Message:
        last = messages[-1]
        tool_names = {t["name"] for t in tools}

        # Already have tool output? Summarise and stop.
        if last.role == "tool":
            return Message("assistant", f"Done. Tool `{last.name}` said:\n{last.content[:500]}")

        task = last.content.lower() if last.role == "user" else ""
        turn = sum(1 for m in messages if m.role == "assistant")

        if turn == 0 and "list" in task and "list_files" in tool_names:
            return Message("assistant", "Let me look at the workspace.", [ToolCall("c1", "list_files", {"path": "."})])
        if turn == 0 and "search" in task and "search" in tool_names:
            return Message("assistant", "Searching.", [ToolCall("c1", "search", {"pattern": "."})])
        return Message("assistant", "I have no tools that help with that. Describe the task more concretely.")
