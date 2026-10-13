"""Turns Microsoft Agent Framework workflow events into a small, replayable event log."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from agent_framework import chat_middleware

from .specs import Scenario, TaskSpec

MAX_TEXT = 6000
MAX_RESULT_CHARS = 4000
HANDOFF_PREFIX = "handoff_to_"


def parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text[:1] in "[{":
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(value, list):
        return [parse_json(item) for item in value]
    return value


def result_value(raw: Any) -> Any:
    """Function results arrive as str, list[Content] or arbitrary objects."""
    if isinstance(raw, list):
        texts = [getattr(item, "text", None) for item in raw]
        if texts and all(isinstance(t, str) for t in texts):
            raw = "".join(texts)
    value = parse_json(raw)
    if isinstance(value, str) and len(value) > MAX_RESULT_CHARS:
        return value[:MAX_RESULT_CHARS] + " …"
    if not isinstance(value, (str, dict, list, int, float, bool, type(None))):
        return str(value)[:MAX_RESULT_CHARS]
    return value


class Recorder:
    def __init__(
        self,
        scenario: Scenario,
        task: TaskSpec,
        *,
        mode: str,
        model: str | None,
        emit: Callable[[dict], None] | None = None,
    ) -> None:
        self.scenario = scenario
        self.task = task
        self.mode = mode
        self.model = model
        self.emit = emit
        self.events: list[dict] = []
        self.started_at = datetime.now(timezone.utc)
        self._t0 = time.monotonic()
        self._agents = {a.id for a in scenario.agents}
        self._agent_steps = {a.id: a.step for a in scenario.agents}
        self._tools = {t.id: t for t in scenario.tools}
        self._buffers: dict[str, list[str]] = {}
        self._calls: dict[str, tuple[str, str]] = {}
        # Function-call arguments stream in deltas; emit one tool_call once a call is complete.
        self._pending: dict[str, dict] = {}
        self._code: dict[str, dict] = {}
        self._active: str | None = None
        self.stats: dict[str, Any] = {
            "model_calls": 0,
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "approvals": 0,
            "handoffs": 0,
            "messages": 0,
            "per_agent": {a.id: {"model_calls": 0, "tool_calls": 0, "tokens": 0} for a in scenario.agents},
        }

    # ------------------------------------------------------------------ basics
    def add(self, kind: str, **data: Any) -> dict:
        event = {"seq": len(self.events) + 1, "t": round(time.monotonic() - self._t0, 2), "type": kind}
        event.update(data)
        self.events.append(event)
        if self.emit:
            self.emit(event)
        return event

    def start(self, prompt: str) -> None:
        self.add("run_start", task=self.task.id, prompt=prompt)

    def finish(self, status: str, error: str | None = None) -> None:
        self.flush_all()
        self.add("run_end", status=status, error=error)

    def _agent_stats(self, agent: str) -> dict:
        return self.stats["per_agent"].setdefault(agent, {"model_calls": 0, "tool_calls": 0, "tokens": 0})

    # ------------------------------------------------------------ middleware
    def middleware_for(self, agent_id: str):
        @chat_middleware
        async def count_model_calls(context, call_next):  # type: ignore[no-untyped-def]
            self.model_call(agent_id)
            await call_next()
            usage = getattr(context.result, "usage_details", None)
            if usage:
                self.add_tokens(agent_id, usage)

        return count_model_calls

    def model_call(self, agent: str) -> None:
        self.stats["model_calls"] += 1
        self._agent_stats(agent)["model_calls"] += 1
        self.add("model_call", agent=agent)

    def add_tokens(self, agent: str, usage: Any) -> None:
        get = usage.get if isinstance(usage, dict) else lambda k, d=0: getattr(usage, k, d)
        inp = int(get("input_token_count", 0) or 0)
        out = int(get("output_token_count", 0) or 0)
        self.stats["input_tokens"] += inp
        self.stats["output_tokens"] += out
        self._agent_stats(agent)["tokens"] += inp + out

    # ------------------------------------------------------------- text flow
    def flush(self, agent: str | None) -> None:
        if not agent:
            return
        parts = self._buffers.pop(agent, [])
        text = "".join(parts).strip()
        if text.startswith("The group chat has reached its termination condition"):
            return
        if text:
            if len(text) > MAX_TEXT:
                text = text[:MAX_TEXT] + " …"
            self.stats["messages"] += 1
            self.add("message", agent=agent, text=text, step=self._agent_steps.get(agent, "plan"))

    def flush_all(self) -> None:
        self._flush_pending()
        self._flush_code()
        for agent in list(self._buffers):
            self.flush(agent)

    def _set_active(self, agent: str) -> None:
        if self._active != agent:
            self.flush_all()
            self._active = agent
            self.add("agent_start", agent=agent)

    # ------------------------------------------------------- event mapping
    def consume(self, ev: Any) -> None:
        kind = getattr(ev, "type", None)
        data = getattr(ev, "data", None)
        executor = getattr(ev, "executor_id", None)

        if kind not in ("intermediate", "output"):
            self._flush_pending()
            self._flush_code()
        if kind == "executor_invoked":
            if executor in self._agents and getattr(data, "should_respond", True) is not False:
                self._set_active(executor)
        elif kind == "executor_completed":
            if executor in self._agents:
                self.flush(executor)
        elif kind in ("intermediate", "output") and hasattr(data, "contents"):
            agent = executor if executor in self._agents else getattr(data, "author_name", None)
            if agent in self._agents:
                if self._active != agent:
                    self._set_active(agent)
                self._consume_contents(agent, data.contents)
        elif kind == "request_info":
            self._approval_request(getattr(ev, "request_id", None), data)
        elif kind == "handoff_sent":
            source = getattr(data, "source", None)
            target = getattr(data, "target", None)
            if source in self._agents and target in self._agents:
                self.flush(source)
                self.stats["handoffs"] += 1
                self.add("handoff", source=source, target=target)
        elif kind == "group_chat" and type(data).__name__ == "GroupChatRequestSentEvent":
            name = getattr(data, "participant_name", None)
            if name in self._agents:
                self.flush_all()
                self.add("speaker", agent=name, round=getattr(data, "round_index", None))

    def _consume_contents(self, agent: str, contents: list[Any]) -> None:
        for content in contents:
            ctype = getattr(content, "type", None)
            if ctype != "function_call":
                self._flush_pending()
            if ctype not in ("code_interpreter_tool_call", "code_interpreter_tool_result"):
                self._flush_code()
            if ctype == "text":
                self._buffers.setdefault(agent, []).append(getattr(content, "text", "") or "")
            elif ctype == "function_call":
                self._function_call(agent, content)
            elif ctype == "function_result":
                self._function_result(agent, content)
            elif ctype == "code_interpreter_tool_call":
                entry = self._code_entry(agent, content)
                inputs = getattr(content, "inputs", None) or []
                entry["parts"].extend(getattr(item, "text", "") or "" for item in inputs)
            elif ctype == "code_interpreter_tool_result":
                entry = self._code_entry(agent, content)
                outputs = getattr(content, "outputs", None) or []
                entry["outputs"].extend(getattr(o, "text", "") for o in outputs if getattr(o, "text", None))
            elif ctype == "usage":
                usage = getattr(content, "usage_details", None)
                if usage:
                    self.add_tokens(agent, usage)

    def _function_call(self, agent: str, content: Any) -> None:
        call_id = getattr(content, "call_id", None) or next(reversed(self._pending), None) or "call"
        entry = self._pending.get(call_id)
        if entry is None:
            self._flush_pending()
            entry = self._pending[call_id] = {"agent": agent, "name": None, "parts": [], "dict": None}
        entry["name"] = entry["name"] or getattr(content, "name", None)
        args = getattr(content, "arguments", None)
        if isinstance(args, str):
            entry["parts"].append(args)
        elif isinstance(args, dict):
            entry["dict"] = args

    def _flush_pending(self) -> None:
        while self._pending:
            call_id = next(iter(self._pending))
            entry = self._pending.pop(call_id)
            agent, name = entry["agent"], entry["name"] or "tool"
            self._calls[call_id] = (agent, name)
            if name.startswith(HANDOFF_PREFIX):
                continue
            self.flush(agent)
            spec = self._tools.get(name)
            self.stats["tool_calls"] += 1
            self._agent_stats(agent)["tool_calls"] += 1
            args = entry["dict"] if entry["dict"] is not None else parse_json("".join(entry["parts"]) or "{}")
            self.add(
                "tool_call",
                agent=agent,
                tool=name,
                call_id=call_id,
                args=args,
                step=spec.step if spec else "act",
                approval=bool(spec and spec.approval),
            )

    def _function_result(self, agent: str, content: Any) -> None:
        call_id = getattr(content, "call_id", None)
        owner, name = self._calls.get(call_id, (agent, "tool"))
        if name.startswith(HANDOFF_PREFIX):
            return
        raw = getattr(content, "result", None)
        if raw is None:
            raw = getattr(content, "items", None)
        exception = getattr(content, "exception", None)
        self.add(
            "tool_result",
            agent=owner,
            tool=name,
            call_id=call_id,
            ok=exception is None,
            result=result_value(raw) if exception is None else str(exception)[:500],
        )

    def _code_entry(self, agent: str, content: Any) -> dict:
        call_id = getattr(content, "call_id", None) or "code"
        if call_id not in self._code:
            self.flush(agent)
            self._code[call_id] = {"agent": agent, "parts": [], "outputs": []}
        return self._code[call_id]

    def _flush_code(self) -> None:
        """Hosted code-interpreter results can arrive before the streamed code itself."""
        while self._code:
            call_id = next(iter(self._code))
            entry = self._code.pop(call_id)
            agent = entry["agent"]
            self.stats["tool_calls"] += 1
            self._agent_stats(agent)["tool_calls"] += 1
            self.add(
                "tool_call",
                agent=agent,
                tool="run_python",
                call_id=call_id,
                args={"code": "".join(entry["parts"]).strip()},
                step=self._tools["run_python"].step if "run_python" in self._tools else "check",
                approval=False,
            )
            self.add(
                "tool_result",
                agent=agent,
                tool="run_python",
                call_id=call_id,
                ok=True,
                result="\n".join(entry["outputs"])
                or "Ran in the hosted sandbox; the agent reads the output and reports it.",
            )

    def _approval_request(self, request_id: str | None, data: Any) -> None:
        if getattr(data, "type", None) != "function_approval_request":
            return
        call = getattr(data, "function_call", None)
        name = getattr(call, "name", None) or "action"
        owner = self._calls.get(getattr(call, "call_id", None), (self._active or "", name))[0]
        self.flush_all()
        self.add(
            "approval_request",
            request_id=request_id,
            agent=owner,
            tool=name,
            args=parse_json(getattr(call, "arguments", None) or {}),
        )

    def approval_response(self, request_id: str, approved: bool, by: str) -> None:
        self.stats["approvals"] += 1
        self.add("approval_response", request_id=request_id, approved=approved, by=by)

    def code_step(self, node: str, title: str, passed: bool, checks: list[dict]) -> None:
        self.flush_all()
        self.add("code_step", node=node, title=title, passed=passed, checks=checks, step="check")

    # ----------------------------------------------------------------- export
    def to_run(self, *, run_id: str, status: str, error: str | None, result: dict, framework: str) -> dict:
        seconds = self.events[-1]["t"] if self.events else 0
        return {
            "schema": "agent-workflows.run/1",
            "id": run_id,
            "scenario": self.scenario.id,
            "pattern": self.scenario.pattern,
            "task": {"id": self.task.id, "label": self.task.label, "prompt": self.task.prompt, "truth": self.task.truth},
            "mode": self.mode,
            "model": self.model,
            "framework": framework,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "seconds": seconds,
            "status": status,
            "error": error,
            "stats": self.stats,
            "result": result,
            "events": self.events,
        }
