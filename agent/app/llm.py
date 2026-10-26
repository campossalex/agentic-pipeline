"""LLM layer.

The agent's conversation state is a list of Open Responses items
(`message`, `function_call`, `function_call_output`). Model calls go through
agentgateway's OpenAI-compatible chat-completions endpoint, which translates to
the Anthropic Messages API or Ollama based on the model prefix. This module
converts between the two shapes.
"""
import json
import re
import uuid
from typing import Any

import httpx

from . import config

_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


# --------------------------------------------------------------------------- items

def user_message(text: str) -> dict:
    return {
        "type": "message",
        "id": new_id("msg"),
        "role": "user",
        "status": "completed",
        "content": [{"type": "input_text", "text": text}],
    }


def assistant_message(text: str) -> dict:
    return {
        "type": "message",
        "id": new_id("msg"),
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def function_call(call_id: str, name: str, arguments: str) -> dict:
    return {
        "type": "function_call",
        "id": new_id("fc"),
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def function_call_output(call_id: str, output: str) -> dict:
    return {
        "type": "function_call_output",
        "id": new_id("fco"),
        "call_id": call_id,
        "output": output,
        "status": "completed",
    }


def message_text(item: dict) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if isinstance(part, dict))


def normalize_input(raw: Any) -> list[dict]:
    """Accept an Open Responses `input`: a string, or a list of items / easy messages."""
    if isinstance(raw, str):
        return [user_message(raw)]
    items = []
    for item in raw or []:
        kind = item.get("type", "message")
        if kind == "message":
            role = item.get("role", "user")
            text = message_text(item)
            items.append(user_message(text) if role == "user" else {
                **assistant_message(text), "role": role,
            })
        else:
            items.append(item)
    return items


# --------------------------------------------------------------------------- conversion

def items_to_messages(system: str, items: list[dict]) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": system}]
    for item in items:
        kind = item.get("type")
        if kind == "message":
            role = item["role"]
            if role == "developer":
                role = "system"
            messages.append({"role": role, "content": message_text(item)})
        elif kind == "function_call":
            last = messages[-1]
            call = {
                "id": item["call_id"],
                "type": "function",
                "function": {"name": item["name"], "arguments": item.get("arguments") or "{}"},
            }
            # Parallel calls (and text + calls) from one model turn share one assistant message.
            if last["role"] == "assistant":
                last.setdefault("tool_calls", []).append(call)
            else:
                messages.append({"role": "assistant", "content": None, "tool_calls": [call]})
        elif kind == "function_call_output":
            messages.append({
                "role": "tool",
                "tool_call_id": item["call_id"],
                "content": item.get("output", ""),
            })
    return messages


def completion_to_items(message: dict) -> list[dict]:
    items = []
    text = _THINK.sub("", message.get("content") or "").strip()
    if text:
        items.append(assistant_message(text))
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        args = fn.get("arguments") or "{}"
        if not isinstance(args, str):
            args = json.dumps(args)
        items.append(function_call(call.get("id") or new_id("call"), fn.get("name", ""), args))
    return items


# --------------------------------------------------------------------------- transport

class LLMError(RuntimeError):
    pass


async def complete(model: str, system: str, items: list[dict], tools: list[dict]) -> tuple[list[dict], dict]:
    """One model turn. Returns (new output items, usage)."""
    # OpenAI's reasoning models reject `max_tokens`; the other routes expect it.
    limit_key = "max_completion_tokens" if model.startswith("openai/") else "max_tokens"
    body: dict[str, Any] = {
        "model": model,
        "messages": items_to_messages(system, items),
        limit_key: config.MAX_TOKENS,
    }
    if tools:
        body["tools"] = [{"type": "function", "function": t} for t in tools]
    async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as client:
        try:
            resp = await client.post(f"{config.LLM_BASE_URL}/v1/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise LLMError(f"gateway unreachable: {exc}") from exc
    if resp.status_code >= 400:
        raise LLMError(f"{resp.status_code} from gateway for model '{model}': {resp.text[:800]}")
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    usage = data.get("usage") or {}
    return completion_to_items(choice.get("message") or {}), {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
