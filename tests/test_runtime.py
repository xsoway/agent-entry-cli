#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : test_runtime.py
# @Author   : Alan_Hsu
"""Exercise the real SDK loop with a deterministic provider, never business acceptance."""

import asyncio
import importlib
import json

import pytest
from agents import Model, ModelResponse, Runner
from agents.usage import Usage
from openai.types.responses import Response, ResponseCompletedEvent, ResponseTextDeltaEvent


def response(text="hello", usage=True):
    from openai.types.responses import ResponseOutputMessage, ResponseOutputText

    return ModelResponse(
        output=[
            ResponseOutputMessage(
                id="msg",
                role="assistant",
                status="completed",
                type="message",
                content=[
                    ResponseOutputText(type="output_text", text=text, annotations=[], logprobs=[])
                ],
            )
        ],
        usage=Usage(requests=1, input_tokens=2, output_tokens=3, total_tokens=5)
        if usage
        else Usage(),
        response_id="test",
        raw_usage={"total_tokens": 5} if usage else None,
    )


class Scripted(Model):
    def __init__(self, results):
        self.results = iter(results)

    async def get_response(self, *args, **kwargs):
        return next(self.results)

    async def stream_response(self, *args, **kwargs):
        result = next(self.results)
        yield ResponseTextDeltaEvent(
            type="response.output_text.delta",
            delta="hello",
            content_index=0,
            item_id="msg",
            logprobs=[],
            output_index=0,
            sequence_number=1,
        )
        usage = (
            {
                "input_tokens": 2,
                "output_tokens": 3,
                "total_tokens": 5,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 0},
            }
            if result.raw_usage
            else None
        )
        yield ResponseCompletedEvent(
            type="response.completed",
            sequence_number=2,
            response=Response(
                id="r",
                created_at=0,
                model="test",
                object="response",
                output=result.output,
                parallel_tool_calls=False,
                tool_choice="auto",
                tools=[],
                status="completed",
                usage=usage,
            ),
        )


def setup(tmp_path, model, **kwargs):
    api = importlib.import_module("agent_entry_cli")
    return api.Runtime(
        api.Project(tmp_path, instructions="Helpful assistant."),
        api.Config(model="fixture", **kwargs),
        model=model,
    )


def test_sdk_answer_records_usage_but_not_raw_chat(tmp_path):
    runtime = setup(tmp_path, Scripted([response("RAW_OUTPUT")]))
    result = asyncio.run(runtime.run("RAW_REQUEST"))
    assert result.status == "completed" and result.output == "RAW_OUTPUT"
    assert result.observed_tokens == 5 and result.cleanup_complete
    body = result.ledger_path.read_text()
    assert "RAW_REQUEST" not in body and "RAW_OUTPUT" not in body
    assert runtime.conversation.usage["known_tokens"] == 5


def test_stream_delivers_before_completion_and_cancel_waits_cleanup(tmp_path):
    class Slow(Scripted):
        async def stream_response(self, *args, **kwargs):
            try:
                yield ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    delta="hello",
                    content_index=0,
                    item_id="msg",
                    logprobs=[],
                    output_index=0,
                    sequence_number=1,
                )
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0.05)
                self.closed = True

        async def _cleanup_on_run_end(self, owner):
            await asyncio.sleep(0.05)
            self.provider_closed = True

    async def run():
        model = Slow([])
        model.closed = False
        model.provider_closed = False
        runtime = setup(tmp_path, model)
        chunks = []
        task = asyncio.create_task(runtime.run("hello", on_text=chunks.append))
        while not chunks:
            await asyncio.sleep(0.005)
        assert not task.done()
        runtime.cancel()
        result = await asyncio.wait_for(task, 3)
        assert result.status == "cancelled" and result.output is None
        assert result.observed_tokens is None and result.cleanup_complete
        assert model.closed and model.provider_closed

    asyncio.run(run())


def test_callback_failure_waits_for_event_iterator_finalizer(tmp_path, monkeypatch):
    original = Runner.run_streamed
    closed = []

    def streamed(*args, **kwargs):
        result = original(*args, **kwargs)
        method = result.stream_events

        async def events():
            iterator = method()
            try:
                async for event in iterator:
                    yield event
            finally:
                await asyncio.sleep(0.05)
                await iterator.aclose()
                closed.append(True)

        monkeypatch.setattr(result, "stream_events", events)
        return result

    monkeypatch.setattr(Runner, "run_streamed", streamed)

    def fail(_):
        raise ValueError("SECRET_EXCEPTION_BODY")

    result = asyncio.run(setup(tmp_path, Scripted([response()])).run("hello", on_text=fail))
    assert result.status == "failed" and result.cleanup_complete and closed
    assert "SECRET_EXCEPTION_BODY" not in result.ledger_path.read_text()


def test_tool_policy_is_enforced_by_sdk_dispatch(tmp_path):
    from openai.types.responses import ResponseFunctionToolCall

    api = importlib.import_module("agent_entry_cli")
    calls = []

    async def write_note(text: str) -> str:
        calls.append(text)
        return "saved"

    tool = api.Tool(write_note, side_effect=True)
    call = ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call", call_id="c", name="write_note", arguments='{"text":"private"}'
            )
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="call",
        raw_usage={"total_tokens": 2},
    )
    runtime = api.Runtime(
        api.Project(tmp_path, tools=(tool,)),
        api.Config(model="fixture"),
        model=Scripted([call, response("denied")]),
    )
    result = asyncio.run(runtime.run("write"))
    assert result.status == "completed" and calls == []
    assert "private" not in result.ledger_path.read_text()


def test_allowed_async_tool_runs_and_records_metadata(tmp_path):
    from openai.types.responses import ResponseFunctionToolCall

    api = importlib.import_module("agent_entry_cli")
    calls = []

    async def search(query: str) -> str:
        calls.append(query)
        return "doc found"

    call = ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call", call_id="c", name="search", arguments='{"query":"notes"}'
            )
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="call",
        raw_usage={"total_tokens": 2},
    )
    runtime = api.Runtime(
        api.Project(tmp_path, tools=(api.Tool(search),)),
        api.Config(model="fixture"),
        model=Scripted([call, response("found")]),
    )
    result = asyncio.run(runtime.run("search"))
    assert result.status == "completed" and calls == ["notes"]
    assert result.model_calls == 2 and result.observed_tokens == 7


def test_failed_provider_is_unknown_usage_and_does_not_commit_history(tmp_path):
    class Failed(Scripted):
        async def get_response(self, *args, **kwargs):
            raise ValueError("SECRET_PROVIDER_BODY")

    runtime = setup(tmp_path, Failed([]))
    runtime.conversation.remember("KEEP", "old")
    result = asyncio.run(runtime.run("new"))
    assert result.status == "failed" and result.observed_tokens is None
    assert "KEEP" in runtime.conversation.compose("next")
    assert "SECRET_PROVIDER_BODY" not in result.ledger_path.read_text()


def test_summary_failure_leaves_original_history(tmp_path):
    runtime = setup(tmp_path, Scripted([response('{"invalid":true}')]))
    runtime.conversation.remember("KEEP", "old")
    result = asyncio.run(runtime.run("", compact=True))
    assert result.status == "failed" and "KEEP" in runtime.conversation.compose("next")
    assert result.reason == "conversation_summary_invalid"


def test_successful_summary_and_next_answer_share_execution_budget(tmp_path):
    from test_state import summary

    runtime = setup(tmp_path, Scripted([response(summary()), response("answer")]))
    runtime.conversation.remember("OLD", "x" * 41000)
    result = asyncio.run(runtime.run("next"))
    assert result.status == "completed" and result.model_calls == 2
    assert runtime.conversation.summary["goals"] == ["KEEP_GOAL"]
    assert "OLD" not in runtime.conversation.compose("next")


def test_unknown_cumulative_budget_blocks_new_calls(tmp_path):
    runtime = setup(tmp_path, Scripted([]), max_session_tokens=100)
    runtime.conversation.record_usage({"model_calls": 1, "observed_tokens": None})
    result = asyncio.run(runtime.run("next"))
    assert result.status == "failed" and result.model_calls == 0


def test_actual_tool_schema_participates_in_window_admission(tmp_path):
    api = importlib.import_module("agent_entry_cli")

    async def search(q: str) -> str:
        return q

    search.__doc__ = "x" * 5000
    cfg = api.Config(model="fixture", context_window=4096, system_reserve=512, output_reserve=512)
    runtime = api.Runtime(
        api.Project(tmp_path, tools=(api.Tool(search),)), cfg, model=Scripted([response()])
    )
    result = asyncio.run(runtime.run("hi"))
    assert result.status == "failed" and result.model_calls == 0


def test_uncertain_write_prevents_model_retry_and_history_commit(tmp_path):
    from openai.types.responses import ResponseFunctionToolCall

    api = importlib.import_module("agent_entry_cli")
    calls = []

    async def write_note(text: str) -> str:
        calls.append(text)
        raise RuntimeError("SECRET_WRITE_ERROR")

    call = ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call", call_id="c", name="write_note", arguments='{"text":"private"}'
            )
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="call",
        raw_usage={"total_tokens": 2},
    )
    runtime = api.Runtime(
        api.Project(
            tmp_path, tools=(api.Tool(write_note, side_effect=True),), authorize=lambda _: True
        ),
        api.Config(model="fixture"),
        model=Scripted([call, call, response("oops")]),
    )
    result = asyncio.run(runtime.run("write"))
    assert calls == ["private"] and result.pending_writes == 1
    assert result.status == "interrupted" and result.model_calls == 1
    assert not runtime.conversation.messages


def test_failed_metadata_initialization_does_not_poison_runtime(tmp_path):
    runtime = setup(tmp_path, Scripted([response()]))
    (tmp_path / ".agent-entry").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        asyncio.run(runtime.run("hello"))
    assert runtime.running is False


@pytest.mark.parametrize("stream", [False, True])
def test_reported_token_overshoot_stops_before_final_answer(tmp_path, stream):
    runtime = setup(tmp_path, Scripted([response()]), max_session_tokens=1)
    result = asyncio.run(runtime.run("hello", on_text=(lambda _: None) if stream else None))
    assert result.observed_tokens == 5
    assert result.status == "failed" and result.output is None
    assert result.known_tokens == 5 and not runtime.conversation.messages


def test_multiple_tool_calls_cannot_write_after_an_unknown_write(tmp_path):
    from openai.types.responses import ResponseFunctionToolCall

    api = importlib.import_module("agent_entry_cli")
    calls = []

    async def write_note(text: str) -> str:
        calls.append(text)
        await asyncio.sleep(0.01)
        raise RuntimeError("write outcome unknown")

    call = ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call",
                call_id=str(i),
                name="write_note",
                arguments=json.dumps({"text": str(i)}),
            )
            for i in range(2)
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="c",
        raw_usage={"total_tokens": 2},
    )
    runtime = api.Runtime(
        api.Project(
            tmp_path, tools=(api.Tool(write_note, side_effect=True),), authorize=lambda _: True
        ),
        api.Config(model="fixture"),
        model=Scripted([call, response()]),
    )
    result = asyncio.run(runtime.run("write"))
    assert len(calls) == 1 and result.pending_writes == 1
    assert result.status == "interrupted"


def test_over_budget_tool_response_cannot_dispatch_side_effect(tmp_path):
    from openai.types.responses import ResponseFunctionToolCall

    api = importlib.import_module("agent_entry_cli")
    calls = []

    async def write_note(text: str) -> str:
        calls.append(text)
        return "saved"

    call = ModelResponse(
        output=[
            ResponseFunctionToolCall(
                type="function_call", call_id="c", name="write_note", arguments='{"text":"no"}'
            )
        ],
        usage=Usage(requests=1, total_tokens=2, input_tokens=1, output_tokens=1),
        response_id="c",
        raw_usage={"total_tokens": 2},
    )
    runtime = api.Runtime(
        api.Project(
            tmp_path, tools=(api.Tool(write_note, side_effect=True),), authorize=lambda _: True
        ),
        api.Config(model="fixture", max_session_tokens=1),
        model=Scripted([call, response()]),
    )
    result = asyncio.run(runtime.run("write"))
    assert calls == [] and result.known_tokens == 2 and result.status == "failed"
