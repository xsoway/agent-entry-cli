#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:48
# @Filename : test_observability.py
# @Author   : Alan_Hsu
"""SDK 安全观察边界：元数据、原子上下文和错误类别。"""

import asyncio
import json

import httpx2 as httpx
import pytest
from agents import ModelResponse
from agents.usage import Usage
from openai import AuthenticationError, RateLimitError
from openai.types.responses import ResponseFunctionToolCall, ResponseReasoningTextDeltaEvent
from test_runtime import Scripted, response

from agent_entry_cli import Config, Project, Runtime, Tool
from agent_entry_cli.conversation import Conversation


def tool_response(name, arguments):
    return ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call", call_id="c", name=name, arguments=json.dumps(arguments)
            )
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="call",
        raw_usage={"total_tokens": 2},
    )


def test_observer_receives_tool_loop_metadata_without_payloads(tmp_path):
    async def lookup(query: str) -> str:
        return "PRIVATE_TOOL_RESULT"

    events = []
    runtime = Runtime(
        Project(tmp_path, tools=(Tool(lookup),)),
        Config(model="fixture"),
        model=Scripted(
            [tool_response("lookup", {"query": "PRIVATE_TOOL_ARGUMENT"}), response("PUBLIC_OUTPUT")]
        ),
    )
    result = asyncio.run(runtime.run("PRIVATE_REQUEST", on_event=events.append))
    assert result.status == "completed" and result.model_calls == 2
    assert [(e["tool_name"], e["status"]) for e in events if e["event"] == "tool"] == [
        ("lookup", "started"),
        ("lookup", "settled"),
    ]
    assert [
        e["model_calls"] for e in events if e["event"] == "model" and e["status"] == "started"
    ] == [1, 2]
    assert events[-1]["event"] == "ended" and events[-1]["cleanup_complete"]
    assert all(
        event["execution_id"] == result.execution_id and event["duration_ms"] >= 0
        for event in events
    )
    assert any(e["event"] == "cleanup" for e in events)
    combined = json.dumps(events) + result.ledger_path.read_text()
    for secret in [
        "PRIVATE_REQUEST",
        "PRIVATE_TOOL_RESULT",
        "PRIVATE_TOOL_ARGUMENT",
        "PUBLIC_OUTPUT",
    ]:
        assert secret not in combined


def test_broken_observer_does_not_break_execution_or_inject_ledger_payload(tmp_path):
    def observe(event):
        event["tool_arguments"] = "SECRET_OBSERVER"
        raise ValueError("SECRET_CALLBACK")

    runtime = Runtime(Project(tmp_path), Config(model="fixture"), model=Scripted([response()]))
    result = asyncio.run(runtime.run("hello", on_event=observe))
    assert result.status == "completed" and result.output == "hello"
    assert "SECRET" not in result.ledger_path.read_text()


def test_private_reasoning_events_never_reach_text_or_observer(tmp_path):
    class Reasoning(Scripted):
        async def stream_response(self, *args, **kwargs):
            yield ResponseReasoningTextDeltaEvent(
                type="response.reasoning_text.delta",
                delta="PRIVATE_REASONING",
                item_id="reason",
                output_index=0,
                content_index=0,
                sequence_number=0,
            )
            async for event in super().stream_response(*args, **kwargs):
                yield event

    events, chunks = [], []
    runtime = Runtime(Project(tmp_path), Config(model="fixture"), model=Reasoning([response()]))
    result = asyncio.run(runtime.run("question", on_event=events.append, on_text=chunks.append))
    assert result.status == "completed" and "".join(chunks) == "hello"
    phases = [e.get("status") for e in events if e["event"] == "model"]
    assert "reasoning" in phases and "streaming" in phases
    assert "PRIVATE_REASONING" not in json.dumps(events) + result.ledger_path.read_text()


@pytest.mark.parametrize(
    "kind, code",
    [
        (AuthenticationError, "provider_authentication_failed"),
        (RateLimitError, "provider_rate_limited"),
    ],
)
def test_provider_errors_have_safe_specific_reason(tmp_path, kind, code):
    class Broken(Scripted):
        async def get_response(self, *args, **kwargs):
            raise kind(
                "PRIVATE_EXCEPTION_BODY",
                response=httpx.Response(
                    401 if kind is AuthenticationError else 429,
                    request=httpx.Request("POST", "https://example.invalid"),
                ),
                body={"secret": "PRIVATE_BODY"},
            )

    result = asyncio.run(
        Runtime(Project(tmp_path), Config(model="fixture"), model=Broken([])).run("hello")
    )
    assert result.reason == code and result.observed_tokens is None
    assert "PRIVATE" not in result.ledger_path.read_text()


def test_summary_event_only_reports_commit_after_cleanup(tmp_path):
    from agent_entry_cli.conversation import SUMMARY_FIELDS

    conversation = Conversation()
    conversation.remember("old", "answer")
    events = []
    summary = json.dumps({key: ["goal"] if key == "goals" else [] for key in SUMMARY_FIELDS})
    runtime = Runtime(
        Project(tmp_path),
        Config(model="fixture"),
        conversation,
        model=Scripted([response(summary)]),
    )
    result = asyncio.run(runtime.run("", compact=True, on_event=events.append))
    assert result.status == "completed" and conversation.summary["goals"] == ["goal"]
    kinds = [(e["event"], e.get("status")) for e in events]
    assert (
        kinds.index(("compaction", "prepared"))
        < kinds.index(("cleanup", "completed"))
        < kinds.index(("compaction", "completed"))
    )


def test_context_diagnostics_include_instructions_schema_and_reserves(tmp_path):
    from agent_entry_cli.runtime import context_diagnostics

    async def lookup(query: str) -> str:
        """查询工具的结构也必须计入窗口。"""
        return query

    conversation = Conversation()
    conversation.remember("question", "answer")
    data = context_diagnostics(
        Project(tmp_path, instructions="x" * 5000, tools=(Tool(lookup),)),
        Config(model="fixture"),
        conversation,
    )
    assert data["instructions_estimate"] >= 5000
    assert data["tools_estimate"] > 50
    assert data["request_estimate"] > 5000
    assert data["remaining_estimate"] < 65536 - 5000 - 4096 - 8192
    assert data["estimator"] == "utf8_bytes_conservative_estimate"


def test_large_instructions_trigger_compaction_before_request_rejection(tmp_path):
    from agent_entry_cli.conversation import SUMMARY_FIELDS

    conversation = Conversation()
    for _ in range(5):
        conversation.remember("x" * 1000, "y" * 1000)
    summary = json.dumps({key: [] for key in SUMMARY_FIELDS})
    cfg = Config(model="fixture", context_window=20000, output_reserve=1000, system_reserve=1000)
    project = Project(tmp_path, instructions="i" * 12000)
    result = asyncio.run(
        Runtime(
            project, cfg, conversation, model=Scripted([response(summary), response("done")])
        ).run("next")
    )
    assert result.status == "completed" and result.model_calls == 2
    assert conversation.compactions == 1


def test_loop_limit_has_specific_reason_without_extra_model_call(tmp_path):
    async def lookup() -> str:
        return "result"

    runtime = Runtime(
        Project(tmp_path, tools=(Tool(lookup),)),
        Config(model="fixture", max_model_calls=1),
        model=Scripted([tool_response("lookup", {}), response("must not run")]),
    )
    result = asyncio.run(runtime.run("hello"))
    assert result.status == "failed" and result.reason == "model_call_budget_exceeded"
    assert result.model_calls == 1


@pytest.mark.parametrize("allowed, tool_status", [(False, "denied"), (True, "failed")])
def test_denied_and_failed_tools_have_safe_status(tmp_path, allowed, tool_status, caplog):
    async def write_note() -> str:
        raise ValueError("PRIVATE_TOOL_EXCEPTION")

    events = []
    project = Project(
        tmp_path, tools=(Tool(write_note, side_effect=True),), authorize=lambda call: allowed
    )
    runtime = Runtime(
        project,
        Config(model="fixture"),
        model=Scripted([tool_response("write_note", {}), response("next")]),
    )
    result = asyncio.run(runtime.run("hello", on_event=events.append))
    assert any(e["event"] == "tool" and e["status"] == tool_status for e in events)
    assert (
        "PRIVATE_TOOL_EXCEPTION"
        not in json.dumps(events) + result.ledger_path.read_text() + caplog.text
    )
    if allowed:
        assert result.reason == "write_result_unknown" and result.pending_writes == 1
        assert result.model_calls == 1


def test_metadata_failure_blocks_followup_tools_and_model_calls(tmp_path, monkeypatch):
    from agent_entry_cli.events import EventLog

    calls = []

    async def write_note() -> str:
        calls.append("write")
        return "done"

    original = EventLog.emit

    def broken(self, event, attributes):
        if event == "tool" and attributes.get("status") == "settled":
            raise OSError("PRIVATE_DISK_ERROR")
        return original(self, event, attributes)

    monkeypatch.setattr(EventLog, "emit", broken)
    first = tool_response("write_note", {})
    first.output.append(
        ResponseFunctionToolCall(
            type="function_call", call_id="d", name="write_note", arguments="{}"
        )
    )
    project = Project(
        tmp_path, tools=(Tool(write_note, side_effect=True),), authorize=lambda call: True
    )
    result = asyncio.run(
        Runtime(
            project, Config(model="fixture"), model=Scripted([first, response("must not run")])
        ).run("hello")
    )
    assert calls == ["write"]
    assert result.reason == "metadata_write_failed" and result.model_calls == 1
    assert "PRIVATE_DISK_ERROR" not in result.ledger_path.read_text()


@pytest.mark.parametrize("streaming", [False, True])
def test_unsettled_provider_finalizer_never_records_complete_zero_usage(tmp_path, streaming):
    from openai.types.responses import ResponseTextDeltaEvent

    async def run():
        ready = asyncio.Event()

        class Delayed(Scripted):
            async def get_response(self, *args, **kwargs):
                ready.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0.15)

            async def stream_response(self, *args, **kwargs):
                yield ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    delta="visible",
                    content_index=0,
                    item_id="msg",
                    logprobs=[],
                    output_index=0,
                    sequence_number=1,
                )
                ready.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0.15)

        cfg = Config(model="fixture", cleanup_seconds=0.01, max_session_tokens=10000)
        runtime = Runtime(Project(tmp_path), cfg, model=Delayed([]))
        task = asyncio.create_task(
            runtime.run("hello", on_text=(lambda text: None) if streaming else None)
        )
        await ready.wait()
        runtime.cancel()
        result = await task
        try:
            assert result.reason == "cleanup_incomplete"
            assert result.observed_tokens is None
            assert runtime.conversation.usage["known_tokens"] == 0
            assert runtime.conversation.usage["complete"] is False
            assert runtime.conversation.usage["unknown_executions"] == 1
        finally:
            await asyncio.sleep(0.2)
        followup = Runtime(
            Project(tmp_path), cfg, runtime.conversation, model=Scripted([response()])
        )
        blocked = await followup.run("next")
        assert blocked.reason == "session_budget_unavailable" and blocked.model_calls == 0

    asyncio.run(run())


def test_tool_only_cleanup_timeout_retains_known_model_usage(tmp_path):
    async def run():
        ready = asyncio.Event()

        async def lookup() -> str:
            ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                deadline = asyncio.get_running_loop().time() + 0.15
                while asyncio.get_running_loop().time() < deadline:
                    try:
                        await asyncio.sleep(max(0, deadline - asyncio.get_running_loop().time()))
                    except asyncio.CancelledError:
                        pass
            return "unused"

        runtime = Runtime(
            Project(tmp_path, tools=(Tool(lookup),)),
            Config(model="fixture", cleanup_seconds=0.01),
            model=Scripted([tool_response("lookup", {})]),
        )
        task = asyncio.create_task(runtime.run("hello"))
        await ready.wait()
        runtime.cancel()
        result = await task
        try:
            assert result.reason == "cleanup_incomplete"
            assert result.observed_tokens == 2 and runtime.conversation.usage["complete"]
        finally:
            await asyncio.sleep(0.2)

    asyncio.run(run())
