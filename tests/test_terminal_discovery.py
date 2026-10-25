#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:51
# @Filename : test_terminal_discovery.py
# @Author   : Alan_Hsu
"""使用者可发现的中文命令、摘要与执行状态。"""

import json
import os
from io import StringIO

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from rich.console import Console

from agent_entry_cli import Config, Project, Tool
from agent_entry_cli.conversation import SUMMARY_FIELDS
from agent_entry_cli.terminal import Terminal


def capture(tmp_path, **kwargs):
    out = StringIO()
    terminal = Terminal(
        Project(tmp_path, **kwargs),
        Config(model="fixture"),
        plain=True,
        console=Console(file=out, width=180),
    )
    return terminal, out


def test_help_completion_and_tools_discover_project_without_authorizing(tmp_path, monkeypatch):
    import agent_entry_cli.terminal as module

    called = []

    async def write_note() -> str:
        return "private result"

    terminal, out = capture(
        tmp_path,
        tools=(Tool(write_note, side_effect=True),),
        commands={"status": lambda: "业务状态"},
        authorize=lambda call: called.append(call) or True,
    )
    terminal.command("/help")
    assert "/status" in out.getvalue() and "/stop" in out.getvalue() and "/tools" in out.getvalue()
    terminal.command("/tools")
    assert "write_note" in out.getvalue() and "写" in out.getvalue() and "授权" in out.getvalue()
    assert called == []
    with create_pipe_input() as pipe:
        original = module.PromptSession
        monkeypatch.setattr(
            module, "PromptSession", lambda **kw: original(input=pipe, output=DummyOutput(), **kw)
        )
        completer = terminal.session().completer
        candidates = {c.text for c in completer.get_completions(Document("/st"), CompleteEvent())}
        assert {"/stop", "/status"} <= candidates


def test_command_errors_explain_recovery_without_exception_body(tmp_path):
    terminal, out = capture(
        tmp_path, commands={"bad": lambda: (_ for _ in ()).throw(ValueError("PRIVATE_ERROR_BODY"))}
    )
    terminal.command("/resume bad-id")
    assert "ID" in out.getvalue() and "/sessions" in out.getvalue()
    terminal.command("/bad")
    assert "PRIVATE_ERROR_BODY" not in out.getvalue()
    terminal.command('/project "')
    assert "引号" in out.getvalue()


def test_progress_and_context_show_metadata_not_payloads(tmp_path, monkeypatch):
    terminal, out = capture(tmp_path, instructions="INSTRUCTION_SECRET")
    monkeypatch.setenv("OPENAI_API_KEY", "credential-for-progress")
    terminal.observe(
        {"event": "model", "status": "started", "model_calls": 2, "context_estimate": 512}
    )
    terminal.observe(
        {"event": "tool", "status": "started", "tool_name": "lookup", "side_effect": False}
    )
    terminal.observe({"event": "cleanup", "status": "started"})
    terminal.command("/context")
    terminal.command("/usage")
    terminal.command("/status")
    rendered = out.getvalue()
    for word in ["模型", "2/12", "lookup", "清理", "上下文", "预留", "累计", "UTF-8"]:
        assert word in rendered
    assert "INSTRUCTION_SECRET" not in rendered and "credential-for-progress" not in rendered


def test_saved_summaries_sorted_by_time_with_preview_and_latest_restore(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import agent_entry_cli.storage as storage

    identifiers = iter(["f" * 32, "0" * 32])
    monkeypatch.setattr(storage, "uuid4", lambda: SimpleNamespace(hex=next(identifiers)))
    terminal, out = capture(tmp_path)
    ids = []
    for goal in ["较早任务", "最新任务"]:
        terminal.conversation.summary = {
            key: [goal] if key == "task" else [] for key in SUMMARY_FIELDS
        }
        ids.append(terminal.store().save(terminal.conversation))
    for identifier, timestamp in zip(ids, [100, 200], strict=True):
        os.utime(terminal.store().directory / (identifier + ".json"), (timestamp, timestamp))
    assert terminal.store().list_sessions(terminal.config.limits) == ids[::-1]
    terminal.command("/sessions")
    rendered = out.getvalue()
    assert "最新任务" in rendered and "1970-" in rendered
    assert rendered.index(ids[1]) < rendered.index(ids[0])
    terminal.conversation.summary = None
    terminal.command("/resume latest")
    assert terminal.conversation.summary["task"] == ["最新任务"]
    body = json.loads((terminal.store().directory / (ids[1] + ".json")).read_text())
    assert set(body) == {"schema", "scope", "summary", "usage"}


def test_running_readonly_controls_never_queue_commands_or_authorize(tmp_path):
    terminal, out = capture(tmp_path)

    class Cancel:
        def cancel(self):
            pass

    assert terminal.intervene("/status", Cancel()) is True
    assert "状态" in out.getvalue()
    assert terminal.queue == []
    assert terminal.intervene("/clear", Cancel()) is False


def test_startup_errors_are_specific_chinese_and_do_not_leak(tmp_path, capsys):
    from agent_entry_cli.cli import main

    assert main(["--project", str(tmp_path / "missing")]) == 2
    error = capsys.readouterr().err
    assert "目录" in error and "project_directory_required" in error
    (tmp_path / "agent-entry.toml").write_text("invalid_field = true")
    assert main(["--project", str(tmp_path), "--diagnostics"]) == 2
    assert "agent-entry.toml" in capsys.readouterr().err


def test_live_context_and_usage_distinguish_inflight_from_settled(tmp_path):
    terminal, out = capture(tmp_path)
    terminal.observe(
        {"event": "model", "status": "started", "model_calls": 1, "context_estimate": 12345}
    )
    terminal.observe(
        {
            "event": "model",
            "status": "completed",
            "model_calls": 1,
            "known_tokens": 7,
            "observed_tokens": 7,
        }
    )
    terminal.command("/context")
    terminal.command("/usage")
    assert "12345" in out.getvalue() and "实际准入" in out.getvalue()
    assert "本轮尚未结算" in out.getvalue() and "7" in out.getvalue()
    assert terminal.conversation.usage["known_tokens"] == 0


def test_progress_does_not_flush_partial_credentials_from_sdk_stream(tmp_path, monkeypatch):
    import asyncio

    from openai.types.responses import ResponseTextDeltaEvent
    from test_runtime import Scripted, response

    import agent_entry_cli.terminal as module
    from agent_entry_cli import Runtime

    secret = "credential-for-test"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    class Split(Scripted):
        async def stream_response(self, *args, **kwargs):
            yield ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta="credential-",
                content_index=0,
                item_id="msg",
                logprobs=[],
                output_index=0,
                sequence_number=1,
            )
            await asyncio.sleep(0.05)
            yield ResponseTextDeltaEvent(
                type="response.output_text.delta",
                delta="for-test。",
                content_index=0,
                item_id="msg",
                logprobs=[],
                output_index=0,
                sequence_number=2,
            )
            async for event in super().stream_response(*args, **kwargs):
                if event.type != "response.output_text.delta":
                    yield event

    monkeypatch.setattr(
        module, "Runtime", lambda p, c, v: Runtime(p, c, v, model=Split([response(secret + "。")]))
    )
    terminal, out = capture(tmp_path)
    result = asyncio.run(terminal.turn("hello"))
    assert result.status == "completed"
    assert "credential-" not in out.getvalue() and "for-test" not in out.getvalue()
    assert "***" in out.getvalue()


def test_project_switch_drops_old_input_history_but_failed_switch_preserves_it(
    tmp_path, monkeypatch
):
    import agent_entry_cli.terminal as module

    terminal, _ = capture(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with create_pipe_input() as pipe:
        original = module.PromptSession
        monkeypatch.setattr(
            module, "PromptSession", lambda **kw: original(input=pipe, output=DummyOutput(), **kw)
        )
        terminal.session().history.append_string("PRIVATE_OLD_PROJECT")
        terminal.command("/project " + str(tmp_path / "missing"))
        assert "PRIVATE_OLD_PROJECT" in terminal.session().history.get_strings()
        terminal.command("/project " + str(other))
        assert terminal.project.root == other
        assert "PRIVATE_OLD_PROJECT" not in terminal.session().history.get_strings()
