#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : cli.py
# @Author   : Alan_Hsu
"""Data-only defaults and explicit loading of trusted project code."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from uuid import uuid4

from .config import load_config
from .privacy import clean
from .project import Project
from .runtime import Runtime


def load_project(root: Path, plugin: Path | None = None) -> Project:
    root = root.expanduser().resolve()
    if plugin is None:
        return Project(root)
    path = plugin.expanduser().resolve()
    name = "_agent_entry_plugin_" + uuid4().hex
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ValueError
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        # Trusted plugins can do anything; suppress incidental Python output in CLI startup.
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            spec.loader.exec_module(module)
            project = module.build_project(root)
        if not isinstance(project, Project) or project.root != root:
            raise ValueError
        return project
    except Exception:
        raise ValueError("project_plugin_rejected") from None
    finally:
        sys.modules.pop(name, None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A project-aware terminal for your main agent.")
    parser.add_argument("--version", action="version", version="agent-entry-cli 0.1.0")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument(
        "--plugin", type=Path, help="Explicitly execute trusted local build_project(root) code."
    )
    parser.add_argument("--model")
    parser.add_argument("--message", help="One noninteractive request.")
    parser.add_argument("--plain", action="store_true")
    parser.add_argument(
        "--json", action="store_true", help="Metadata and final response for a one-shot request."
    )
    parser.add_argument("--diagnostics", action="store_true")
    parser.add_argument(
        "--init", action="store_true", help="Create data-only agent-entry.toml without overwriting."
    )
    args = parser.parse_args(argv)
    try:
        root = args.project.expanduser().resolve()
        if not root.is_dir():
            raise ValueError("project_directory_required")
        if args.init:
            fd = os.open(
                root / "agent-entry.toml",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
            with os.fdopen(fd, "w") as stream:
                stream.write(
                    '# Credentials belong in the environment, never this file.\nmodel = ""\napi = "chat_completions"\ncontext_window = 65536\noutput_reserve = 4096\nsystem_reserve = 8192\n'
                )
            print("Created agent-entry.toml. Set model and OPENAI_API_KEY.")
            return 0
        config = load_config(root, model=args.model)
        project = load_project(root, args.plugin)
        if args.diagnostics:
            print(json.dumps(asdict(config), ensure_ascii=False, indent=2))
            return 0
        if args.json and args.message is None:
            raise ValueError("json_requires_message")
        if args.message is not None:
            config.credential()

            async def one_shot():
                result = await Runtime(project, config).run(args.message)
                render_result(result)
                return result

            def render_result(result):
                row = {**asdict(result), "ledger_path": str(result.ledger_path)}
                print(
                    json.dumps(row, ensure_ascii=False)
                    if args.json
                    else clean(
                        f"{result.status}: {result.reason}\n{result.output or ''}\nExecution: {result.execution_id}\nLedger: {result.ledger_path}"
                    )
                )

            result = asyncio.run(one_shot())
            return 0 if result.status == "completed" else 130 if result.status == "cancelled" else 1
        if not sys.stdin.isatty():
            raise ValueError("interactive_tty_required")
        from .terminal import Terminal

        return Terminal(
            project, config, plain=args.plain, plugin=args.plugin, model_override=args.model
        ).run()
    except (ValueError, OSError):
        print(
            "Startup rejected: check project, config, explicit plugin, model and credential environment.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
