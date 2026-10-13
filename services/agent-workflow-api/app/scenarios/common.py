from __future__ import annotations

import json
import re
from typing import Any

CODE_BLOCK = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.S)


def first_result(events: list[dict], tool: str) -> Any:
    for event in events:
        if event["type"] == "tool_result" and event.get("tool") == tool:
            return event.get("result")
    return None


def last_result(events: list[dict], tool: str) -> Any:
    found = None
    for event in events:
        if event["type"] == "tool_result" and event.get("tool") == tool:
            found = event.get("result")
    return found


def final_message(events: list[dict], agent: str | None = None) -> str:
    for event in reversed(events):
        if event["type"] == "message" and (agent is None or event.get("agent") == agent):
            return event["text"]
    return ""


def messages_from(events: list[dict], agent: str) -> list[str]:
    return [e["text"] for e in events if e["type"] == "message" and e.get("agent") == agent]


def outbox_actions(outbox: list[dict], action: str) -> list[dict]:
    return [entry for entry in outbox if entry.get("action") == action]


def last_code_block(texts: list[str], language_hint: str | None = None) -> str | None:
    for text in reversed(texts):
        blocks = CODE_BLOCK.findall(text)
        if blocks:
            return blocks[-1].strip()
    return None


def last_json_block(texts: list[str]) -> dict | None:
    for text in reversed(texts):
        for block in reversed(CODE_BLOCK.findall(text)):
            try:
                value = json.loads(block)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return None
