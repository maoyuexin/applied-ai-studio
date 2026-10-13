"""Builds a scenario's workflow, drives it to completion and pauses for approvals."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.metadata
import inspect
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx
from agent_framework import Agent

from .config import Settings
from .recorder import Recorder
from .specs import AgentSpec, Scenario, TaskSpec

Decide = Callable[[dict], Awaitable[bool]]


def framework_version() -> str:
    try:
        return "Microsoft Agent Framework " + importlib.metadata.version("agent-framework-core")
    except importlib.metadata.PackageNotFoundError:
        return "Microsoft Agent Framework"


@dataclass
class BuildContext:
    client: Any
    recorder: Recorder
    settings: Settings
    http: httpx.AsyncClient
    task: TaskSpec
    stack: contextlib.AsyncExitStack
    outbox: list[dict] = field(default_factory=list)

    def service(self, name: str) -> str:
        return self.settings.services[name].rstrip("/")

    def agent(self, spec: AgentSpec, tools: list[Any] | None = None, **kwargs: Any) -> Agent:
        return Agent(
            client=self.client,
            name=spec.id,
            description=spec.role,
            instructions=spec.instructions,
            tools=tools or None,
            middleware=[self.recorder.middleware_for(spec.id)],
            **kwargs,
        )

    def file_action(self, action: str, **fields: Any) -> str:
        """Approved actions land in a per-run outbox; nothing reaches a real system."""
        entry = {"action": action, **fields}
        self.outbox.append(entry)
        return f"Approved by a person and completed: {action} (reference #{len(self.outbox)})."


def make_client(settings: Settings) -> Any:
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import AzureCliCredential

    return FoundryChatClient(
        project_endpoint=settings.project_endpoint,
        model=settings.model,
        credential=AzureCliCredential(),
    )


async def _drive(workflow: Any, prompt: str, recorder: Recorder, decide: Decide) -> None:
    from agent_framework.orchestrations import HandoffAgentUserRequest

    stream = workflow.run(prompt, stream=True)
    while True:
        pending: dict[str, Any] = {}
        async for event in stream:
            recorder.consume(event)
            if getattr(event, "type", None) == "request_info":
                pending[event.request_id] = event.data
        if not pending:
            return
        responses: dict[str, Any] = {}
        for request_id, data in pending.items():
            if getattr(data, "type", None) == "function_approval_request":
                call = data.function_call
                approved = await decide(
                    {
                        "request_id": request_id,
                        "tool": call.name,
                        "arguments": call.arguments,
                    }
                )
                recorder.approval_response(request_id, approved, by="person")
                responses[request_id] = data.to_function_approval_response(approved=approved)
            elif isinstance(data, HandoffAgentUserRequest):
                responses[request_id] = HandoffAgentUserRequest.terminate()
        if not responses:
            return
        stream = workflow.run(stream=True, responses=responses)


async def run_scenario(
    scenario: Scenario,
    task_id: str,
    settings: Settings,
    *,
    mode: str,
    decide: Decide,
    emit: Callable[[dict], None] | None = None,
    client: Any = None,
    run_id: str | None = None,
) -> dict:
    if scenario.builder is None:
        raise ValueError(f"{scenario.id} has no live workflow")
    task = scenario.task(task_id)
    recorder = Recorder(scenario, task, mode=mode, model=settings.model, emit=emit)
    run_id = run_id or uuid.uuid4().hex[:12]
    status, error = "completed", None
    async with httpx.AsyncClient(timeout=30) as http, contextlib.AsyncExitStack() as stack:
        ctx = BuildContext(
            client=client or make_client(settings),
            recorder=recorder,
            settings=settings,
            http=http,
            task=task,
            stack=stack,
        )
        recorder.start(task.prompt)
        try:
            workflow = scenario.builder(ctx)
            if inspect.isawaitable(workflow):
                workflow = await workflow
            await asyncio.wait_for(
                _drive(workflow, task.prompt, recorder, decide), timeout=settings.run_timeout_seconds
            )
        except asyncio.TimeoutError:
            status, error = "timeout", f"Stopped after {settings.run_timeout_seconds} s"
        except asyncio.CancelledError:
            status, error = "stopped", "Stopped by the presenter"
        except Exception as exc:  # surfaced to the UI, never swallowed silently
            status, error = "error", f"{type(exc).__name__}: {exc}"[:400]
        recorder.finish(status, error)
        result = scenario.summarize(recorder.events, ctx.outbox) if scenario.summarize else {}
        result.setdefault("outbox", ctx.outbox)
    return recorder.to_run(
        run_id=run_id, status=status, error=error, result=result, framework=framework_version()
    )
