#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : test_state.py
# @Author   : Alan_Hsu
"""Project isolation, safe persistence and context boundary regressions."""

import importlib
import json
from dataclasses import replace

import pytest


def api():
    return importlib.import_module("agent_entry_cli")


def test_package_provides_a_project_entry_not_framework_import(tmp_path):
    project = api().Project(root=tmp_path, instructions="Read docs.")
    assert project.root == tmp_path.resolve()
    assert project.tools == ()


def test_tool_is_async_and_side_effects_default_deny(tmp_path):
    async def write_note(text: str) -> str:
        return text

    tool = api().Tool(write_note, side_effect=True)
    project = api().Project(tmp_path, tools=(tool,))
    assert project.permit(tool, {"text": "hello"}) is False
    allowed = api().Project(
        tmp_path, tools=(tool,), authorize=lambda call: call.name == "write_note"
    )
    assert allowed.permit(tool, {"text": "hello"}) is True
    with pytest.raises(ValueError):
        api().Tool(lambda: "blocking")


def test_config_data_does_not_execute_plugin_and_rejects_unknown_fields(tmp_path, monkeypatch):
    cfg = importlib.import_module("agent_entry_cli.config")
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    (tmp_path / "agent-entry.toml").write_text('model = "example"\nplugin = "pwn.py"')
    with pytest.raises(ValueError):
        cfg.load_config(tmp_path)
    (tmp_path / "agent-entry.toml").write_text('model = "example"\napi = "chat_completions"')
    assert cfg.load_config(tmp_path).model == "example"


def summary(goal="KEEP_GOAL"):
    return json.dumps(
        {
            key: [goal] if key == "goals" else []
            for key in (
                "goals",
                "constraints",
                "decisions",
                "pending",
                "task",
                "blockers",
                "references",
                "next_steps",
            )
        }
    )


def test_history_never_silently_drops_the_latest_long_turn():
    conv = importlib.import_module("agent_entry_cli.conversation").Conversation()
    conv.remember("KEEP_REQUEST", "中" * 6000)
    assert "KEEP_REQUEST" in conv.compose("follow up") and "中" * 6000 in conv.compose("follow up")


def test_invalid_summary_cannot_mutate_history():
    conv = importlib.import_module("agent_entry_cli.conversation").Conversation()
    conv.remember("KEEP_REQUEST", "answer")
    with pytest.raises(ValueError):
        conv.commit_summary('{"approved": true}', 2)
    assert "KEEP_REQUEST" in conv.compose("next")


def test_summary_files_are_immutable_scoped_and_without_raw_messages(tmp_path):
    conv = importlib.import_module("agent_entry_cli.conversation").Conversation()
    Store = importlib.import_module("agent_entry_cli.storage").SummaryStore
    conv.remember("RAW_SECRET_MARKER", "reply")
    conv.commit_summary(summary(), 2)
    conv.record_usage({"model_calls": 1, "observed_tokens": 10})
    store = Store(tmp_path / "summaries", "scope-a")
    first, second = store.save(conv), store.save(conv)
    assert first != second
    path = tmp_path / "summaries" / f"{first}.json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert "RAW_SECRET_MARKER" not in path.read_text() and "messages" not in json.loads(
        path.read_text()
    )
    restored = store.load(first, conv.limits)
    assert restored.usage["known_tokens"] == 10 and "KEEP_GOAL" in restored.compose("next")
    with pytest.raises(ValueError):
        Store(tmp_path / "summaries", "scope-b").load(first, conv.limits)
    with pytest.raises(ValueError):
        store.load("../escape", conv.limits)


def test_summary_restore_checks_current_window_and_symlinks(tmp_path):
    conv = importlib.import_module("agent_entry_cli.conversation").Conversation()
    Store = importlib.import_module("agent_entry_cli.storage").SummaryStore
    data = json.loads(summary())
    data["goals"] = ["x" * 2000] * 4
    conv.commit_summary(json.dumps(data), 0)
    store = Store(tmp_path / "state", "scope")
    identifier = store.save(conv)
    with pytest.raises(ValueError):
        store.load(
            identifier,
            replace(conv.limits, context_window=6144, output_reserve=1024, system_reserve=1024),
        )
    (tmp_path / "link").symlink_to(tmp_path / "state", target_is_directory=True)
    with pytest.raises(ValueError):
        Store(tmp_path / "link", "scope").load(identifier, conv.limits)


def test_clear_does_not_reset_known_usage_and_unknown_remains_visible():
    conv = importlib.import_module("agent_entry_cli.conversation").Conversation()
    conv.record_usage({"model_calls": 1, "observed_tokens": 7})
    conv.record_usage({"model_calls": 2, "observed_tokens": None, "known_tokens": 3})
    conv.clear()
    assert conv.usage["known_tokens"] == 10 and conv.usage["unknown_executions"] == 1
    assert conv.usage["complete"] is False and conv.usage["cost"] is None


def test_metadata_has_no_raw_or_exception_body(tmp_path):
    EventLog = importlib.import_module("agent_entry_cli.events").EventLog
    log = EventLog(tmp_path, "abc")
    with pytest.raises(ValueError):
        log.emit("tool", {"prompt": "RAW", "arguments": {"password": "private"}})
    log.emit("ended", {"status": "cancelled", "known_tokens": 3, "observed_tokens": None})
    assert "RAW" not in log.path.read_text() and "private" not in log.path.read_text()
