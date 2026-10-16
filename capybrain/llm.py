"""OpenAI-compatible chat client (W&B Inference by default) with streaming tool calls."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterator

from openai import OpenAI

from . import config


@lru_cache(maxsize=1)
def client() -> OpenAI:
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not set; copy .env.example to .env and fill it in")
    return OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, timeout=120, max_retries=2)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str = ""

    def args(self) -> dict:
        try:
            return json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}


@dataclass
class Turn:
    content: str = ""
    reasoning: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


def stream_turn(messages: list[dict], tools: list[dict] | None = None, *, max_tokens: int = 1500,
                temperature: float = 0.2) -> Iterator[tuple[str, object]]:
    """Stream one assistant turn. Yields ("reasoning", str), ("content", str) deltas and
    finally ("turn", Turn) with the accumulated content and tool calls."""
    kwargs = dict(model=config.LLM_MODEL, messages=messages, max_tokens=max_tokens,
                  temperature=temperature, stream=True)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    turn = Turn()
    calls: dict[int, ToolCall] = {}
    for chunk in client().chat.completions.create(**kwargs):
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        extra = delta.model_extra or {}
        r = extra.get("reasoning") or extra.get("reasoning_content")
        if r:
            turn.reasoning += r
            yield "reasoning", r
        if delta.content:
            turn.content += delta.content
            yield "content", delta.content
        for tc in delta.tool_calls or []:
            call = calls.setdefault(tc.index, ToolCall(id=tc.id or f"call_{tc.index}", name=""))
            if tc.id:
                call.id = tc.id
            if tc.function and tc.function.name:
                call.name += tc.function.name
            if tc.function and tc.function.arguments:
                call.arguments += tc.function.arguments
    turn.tool_calls = [calls[i] for i in sorted(calls)]
    turn.content = turn.content.strip()
    yield "turn", turn


def complete(messages: list[dict], *, max_tokens: int = 1500, temperature: float = 0.2, think: bool = True) -> str:
    extra = {} if think else {"extra_body": config.LLM_NO_THINK}
    resp = client().chat.completions.create(model=config.LLM_MODEL, messages=messages,
                                            max_tokens=max_tokens, temperature=temperature, **extra)
    return (resp.choices[0].message.content or "").strip()


def parse_json(text: str):
    """Pull the first JSON object or array out of a model reply."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON in model reply: {text[:200]}")


def complete_json(system: str, user: str, *, max_tokens: int = 2000, think: bool = False):
    """JSON-only completion. Thinking is off by default for speed; turn it on for judgement calls
    (reasoning tokens count against max_tokens, so give those calls a larger budget)."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    reply = complete(msgs, max_tokens=max_tokens, temperature=0.0, think=think)
    try:
        return parse_json(reply)
    except ValueError:
        msgs += [{"role": "assistant", "content": reply},
                 {"role": "user", "content": "Reply with valid JSON only, no prose."}]
        return parse_json(complete(msgs, max_tokens=max_tokens, temperature=0.0, think=False))
