#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : test_cli.py
# @Author   : Alan_Hsu
"""User-facing setup, local controls and explicit project loading."""

import importlib
import json
from pathlib import Path

import pytest


def cli():
    return importlib.import_module("agent_entry_cli.cli")


def test_init_creates_data_only_config_and_never_overwrites(tmp_path):
    assert cli().main(["--project", str(tmp_path), "--init"]) == 0
    original = (tmp_path / "agent-entry.toml").read_text()
    assert "api_key =" not in original and not (tmp_path / "plugin.py").exists()
    assert cli().main(["--project", str(tmp_path), "--init"]) == 2
    assert (tmp_path / "agent-entry.toml").read_text() == original


def test_help_and_diagnostics_do_not_require_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(SystemExit) as stopped:
        cli().main(["--help"])
    assert stopped.value.code == 0
    assert cli().main(["--project", str(tmp_path), "--diagnostics"]) == 0
    assert "context_window" in capsys.readouterr().out
    assert not (tmp_path / ".agent-entry").exists()


def test_plugins_only_load_when_explicit_and_must_keep_selected_root(tmp_path):
    plugin = tmp_path / "plugin.py"
    marker = tmp_path / "executed"
    plugin.write_text(
        "from pathlib import Path\nfrom agent_entry_cli import Project\n"
        + f"Path({str(marker)!r}).touch()\n"
        + "def build_project(root):\n    return Project(root)\n"
    )
    assert cli().main(["--project", str(tmp_path), "--diagnostics"]) == 0
    assert not marker.exists()
    loaded = cli().load_project(tmp_path, plugin)
    assert marker.exists() and loaded.root == tmp_path
    plugin.write_text(
        "from agent_entry_cli import Project\ndef build_project(root):\n    return Project(root.parent)\n"
    )
    with pytest.raises(ValueError):
        cli().load_project(tmp_path, plugin)


def test_bad_plugin_cannot_print_exception_body(tmp_path, capsys):
    plugin = tmp_path / "plugin.py"
    plugin.write_text('raise ValueError("SECRET_PLUGIN_BODY")')
    assert cli().main(["--project", str(tmp_path), "--plugin", str(plugin), "--diagnostics"]) == 2
    captured = capsys.readouterr()
    assert "SECRET_PLUGIN_BODY" not in captured.out + captured.err


def test_local_commands_and_queue_cannot_grant_tool_authorization(tmp_path, capsys):
    from agent_entry_cli import Config, Project

    Terminal = importlib.import_module("agent_entry_cli.terminal").Terminal
    terminal = Terminal(Project(tmp_path), Config(model="fixture"), plain=True)

    class Cancel:
        stopped = False

        def cancel(self):
            self.stopped = True

    current = Cancel()
    assert terminal.intervene("/run approve", current) is False
    assert terminal.intervene("next instruction", current) is True
    assert terminal.intervene("/stop", current) is True and current.stopped
    terminal.paused = True
    terminal.command("/queue")
    assert "next instruction" in capsys.readouterr().out
    terminal.command("/drop")
    assert terminal.queue == []
    terminal.conversation.remember("KEEP", "answer")
    terminal.command("/resume invalid")
    assert "KEEP" in terminal.conversation.compose("next")


def test_project_switch_failure_preserves_old_context(tmp_path):
    from agent_entry_cli import Config, Project

    Terminal = importlib.import_module("agent_entry_cli.terminal").Terminal
    terminal = Terminal(Project(tmp_path), Config(model="fixture"), plain=True)
    terminal.conversation.remember("KEEP", "answer")
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "agent-entry.toml").write_text("bad = true")
    terminal.command("/project " + str(broken))
    assert terminal.project.root == tmp_path and "KEEP" in terminal.conversation.compose("next")


def test_stream_output_filters_controls_and_secrets_split_across_chunks(tmp_path):
    from io import StringIO

    from rich.console import Console

    from agent_entry_cli import Config, Project

    Terminal = importlib.import_module("agent_entry_cli.terminal").Terminal
    out = StringIO()
    terminal = Terminal(
        Project(tmp_path),
        Config(model="fixture"),
        plain=True,
        console=Console(file=out, color_system=None),
    )
    for delta in ["Safe\x1b[2J Bearer ", "abcdefghijkl", "mnopqrstuvwx", "。"]:
        terminal.stream_text(delta)
    terminal.finish_stream()
    assert "abcdefghijkl" not in out.getvalue() and "\x1b" not in out.getvalue()
    assert "Safe" in out.getvalue()


def test_knowledge_example_blocks_escape_and_bounds_results(tmp_path):
    project = cli().load_project(
        tmp_path, Path(__file__).parents[1] / "examples/knowledge/project.py"
    )
    import asyncio

    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/a.md").write_text("needle source")
    outside = tmp_path / "private.md"
    outside.write_text("needle PRIVATE")
    (tmp_path / "notes/link.md").symlink_to(outside)
    result = asyncio.run(project.tools[0].function("needle"))
    assert "notes/a.md" in result and "PRIVATE" not in result


def test_cli_model_override_survives_project_switch(tmp_path, monkeypatch):
    from agent_entry_cli import Config, Project

    Terminal = importlib.import_module("agent_entry_cli.terminal").Terminal
    dest = tmp_path / "other"
    dest.mkdir()
    (dest / "agent-entry.toml").write_text('model="project-model"')
    terminal = Terminal(
        Project(tmp_path), Config(model="chosen"), plain=True, model_override="chosen"
    )
    terminal.command("/project " + str(dest))
    assert terminal.config.model == "chosen"


def test_interrupted_turn_can_be_rendered_without_closing_event_loop(tmp_path, monkeypatch, capsys):
    import asyncio
    import types

    from agent_entry_cli import Config, Project
    from agent_entry_cli.runtime import Result

    module = importlib.import_module("agent_entry_cli.terminal")
    terminal = module.Terminal(Project(tmp_path), Config(model="fixture"), plain=True)

    async def interrupted(self, request, **kwargs):
        return Result(
            "interrupted",
            "cleanup_incomplete",
            "id",
            tmp_path / "events",
            None,
            1,
            None,
            0,
            False,
            0,
        )

    monkeypatch.setattr(terminal, "turn", types.MethodType(interrupted, terminal))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture")

    async def run():
        result = await terminal.execute("hello")
        assert result.status == "interrupted"
        assert "cleanup_incomplete" in capsys.readouterr().out

    asyncio.run(run())


def test_headless_text_filters_terminal_control_sequences(tmp_path, monkeypatch, capsys):
    from test_runtime import Scripted, response

    from agent_entry_cli import Runtime

    module = cli()
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setattr(
        module,
        "Runtime",
        lambda project, config: Runtime(
            project, config, model=Scripted([response("safe\x1b[2J text")])
        ),
    )
    assert (
        module.main(["--project", str(tmp_path), "--model", "fixture", "--message", "hello"]) == 0
    )
    assert "\x1b" not in capsys.readouterr().out


def test_enhanced_running_escape_cancels_and_follows_same_loop(tmp_path, monkeypatch):
    import asyncio

    from openai.types.responses import ResponseTextDeltaEvent
    from prompt_toolkit import PromptSession
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput
    from test_runtime import Scripted

    from agent_entry_cli import Config, Project, Runtime

    module = importlib.import_module("agent_entry_cli.terminal")

    class Slow(Scripted):
        async def stream_response(self, *args, **kwargs):
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

    monkeypatch.setattr(
        module,
        "Runtime",
        lambda project, config, conversation: Runtime(
            project, config, conversation, model=Slow([])
        ),
    )

    async def run():
        terminal = module.Terminal(Project(tmp_path), Config(model="fixture"), plain=True)
        terminal.enhanced = True
        with create_pipe_input() as pipe:
            monkeypatch.setattr(
                module,
                "PromptSession",
                lambda **kwargs: PromptSession(input=pipe, output=DummyOutput(), **kwargs),
            )
            task = asyncio.create_task(terminal.turn("hello"))
            for _ in range(100):
                if terminal._stream_bytes:
                    break
                await asyncio.sleep(0.01)
            pipe.send_text("next context\r")
            for _ in range(100):
                if terminal.queue:
                    break
                await asyncio.sleep(0.01)
            pipe.send_text("\x1b")
            result = await asyncio.wait_for(task, 3)
            assert result.status == "cancelled" and result.cleanup_complete
            assert terminal.queue == ["next context"] and terminal.paused

    asyncio.run(run())


def test_evaluation_example_uses_current_readonly_status_contract(tmp_path, monkeypatch):
    import asyncio
    import os

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "agent-eval"
    executable.write_text(
        "#!/usr/bin/env python3\nimport sys,json\nexpected="
        + repr(["status", str(tmp_path), "--format", "json"])
        + '\nif sys.argv[1:] != expected: raise SystemExit(3)\nprint(json.dumps({"stage":"EMPTY"}))\n'
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    project = cli().load_project(
        tmp_path, Path(__file__).parents[1] / "examples/eval-harness/project.py"
    )
    output = asyncio.run(project.tools[0].function())
    assert json.loads(output)["stage"] == "EMPTY"


def test_evaluation_adapter_reaps_child_when_cancelled_during_start(tmp_path, monkeypatch):
    import asyncio
    import os

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "agent-eval"
    executable.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(20)\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    project = cli().load_project(
        tmp_path, Path(__file__).parents[1] / "examples/eval-harness/project.py"
    )
    original = asyncio.create_subprocess_exec

    async def run():
        children = []

        async def delayed_start(*args, **kwargs):
            child = await original(*args, **kwargs)
            children.append(child)
            await asyncio.sleep(0.1)
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_start)
        task = asyncio.create_task(project.tools[0].function())
        try:
            while not children:
                await asyncio.sleep(0.001)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 2)
            assert children[0].returncode is not None, "subprocess escaped cancelled startup"
        finally:
            for child in children:
                if child.returncode is None:
                    child.kill()
                await child.wait()

    asyncio.run(run())
