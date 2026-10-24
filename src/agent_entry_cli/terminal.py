#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : terminal.py
# @Author   : Alan_Hsu
"""Terminal UI and bounded next-turn input; no implicit shell or approval commands."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shlex
import sys
from contextlib import suppress
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.text import Text

from .config import Config, load_config
from .conversation import Conversation
from .privacy import clean, redact_text
from .project import Project
from .runtime import Result, Runtime
from .storage import SummaryStore

COMMANDS = [
    "/help",
    "/context",
    "/compact",
    "/save",
    "/sessions",
    "/resume",
    "/model",
    "/usage",
    "/clear",
    "/queue",
    "/next",
    "/drop",
    "/project",
    "/details",
    "/quit",
]
HELP = """/context /compact       Window estimate / summarize context
/save /sessions /resume ID  Explicit summary checkpoints, no raw transcript
/model [name] /usage       Model settings and cumulative observed usage
/clear                    Clear context, preserve usage
/project PATH             Switch scope (plugin reloaded only when explicit)
/details                  Last safe execution metadata
/queue /next /drop         Inspect, resume or clear next-turn input
/quit                     Exit
During execution: Esc or /stop cancels; ordinary text queues next-turn input.
Enhanced editor: Enter sends; Alt+Enter inserts newline; Tab completes commands."""


class Terminal:
    def __init__(
        self,
        project: Project,
        config: Config,
        *,
        plain: bool = False,
        console: Console | None = None,
        plugin: Path | None = None,
        model_override: str | None = None,
    ):
        self.project, self.config, self.plugin = project, config, plugin
        self.enhanced = (
            not plain
            and sys.stdin.isatty()
            and sys.stdout.isatty()
            and os.environ.get("TERM") != "dumb"
        )
        self.console = console or Console(
            highlight=False,
            color_system="auto" if self.enhanced and not os.environ.get("NO_COLOR") else None,
        )
        self.conversation = Conversation(config.limits)
        self.queue: list[str] = []
        self.paused = False
        self.last: Result | None = None
        self.exit = False
        self._pending = ""
        self._stream_bytes = 0
        self._session = None
        self._runtime: Runtime | None = None
        self._model_override = model_override
        self._unsettled: Runtime | None = None

    def show(self, value: str) -> None:
        self.console.print(
            Text(clean(redact_text(value, (os.environ.get(self.config.api_key_env, ""),))))
        )

    def store(self) -> SummaryStore:
        scope = hashlib.sha256(str(self.project.root).encode()).hexdigest()
        return SummaryStore(self.project.root / ".agent-entry/summaries", scope)

    def stream_text(self, delta: str) -> None:
        self._stream_bytes += len(delta.encode())
        if self._stream_bytes > 65536:
            raise ValueError("stream_too_large")
        pending = self._pending + delta
        match = re.search(
            r"(?i)(?:Bearer|Basic)\s+[A-Za-z0-9._~-]*$|[A-Za-z0-9_./:@=+~-]+$", pending
        )
        cut = match.start() if match else len(pending)
        self._pending = pending[cut:]
        if cut:
            self.console.print(
                Text(
                    clean(
                        redact_text(pending[:cut], (os.environ.get(self.config.api_key_env, ""),))
                    )
                ),
                end="",
            )

    def finish_stream(self) -> None:
        if self._pending:
            self.show(self._pending)
        elif self._stream_bytes:
            self.console.print()
        self._pending = ""
        self._stream_bytes = 0

    def intervene(self, text: str, runtime: Any) -> bool:
        text = text.strip()
        if text == "/stop":
            runtime.cancel()
            return True
        if not text or text.startswith("/") or len(text.encode()) > 40000 or len(self.queue) >= 8:
            self.show("Only next-turn text or /stop is accepted while running.")
            return False
        self.queue.append(text)
        self.show(f"Queued next-turn input ({len(self.queue)}).")
        return True

    def session(self) -> PromptSession:
        if self._session is None:
            keys = KeyBindings()

            @keys.add("escape")
            def stop(event):
                if self._runtime is not None:
                    self._runtime.cancel()

            @keys.add("c-c")
            def interrupt(event):
                if self._runtime is not None:
                    self._runtime.cancel()
                else:
                    event.current_buffer.reset()

            @keys.add("escape", "enter")
            def newline(event):
                event.current_buffer.insert_text("\n")

            self._session = PromptSession(
                color_depth=ColorDepth.DEPTH_1_BIT if os.environ.get("NO_COLOR") else None,
                completer=WordCompleter(COMMANDS, ignore_case=True),
                key_bindings=keys,
                multiline=False,
            )
        return self._session

    async def turn(
        self, request: str, *, compact: bool = False, all_messages: bool = False
    ) -> Result:
        runtime = Runtime(self.project, self.config, self.conversation)
        self._runtime = runtime
        worker = asyncio.create_task(
            runtime.run(
                request, on_text=self.stream_text, compact=compact, all_messages=all_messages
            )
        )
        editor = None
        fd = None
        loop = asyncio.get_running_loop()

        async def input_loop():
            while not worker.done():
                try:
                    text = await self.session().prompt_async("running > ")
                except (EOFError, KeyboardInterrupt):
                    runtime.cancel()
                    return
                self.intervene(text, runtime)

        try:
            if self.enhanced:
                editor = asyncio.create_task(input_loop())
            elif sys.stdin.isatty():
                fd = sys.stdin.fileno()
                pending = bytearray()

                def read():
                    value = os.read(fd, 4096)
                    if not value:
                        runtime.cancel()
                        return
                    pending.extend(value)
                    while b"\n" in pending:
                        line, _, rest = pending.partition(b"\n")
                        pending[:] = rest
                        self.intervene(line.decode(errors="replace"), runtime)

                loop.add_reader(fd, read)
            result = await worker
            self.last = result
            if not result.cleanup_complete:
                self._unsettled = runtime
            if result.status != "completed":
                self.paused = True
            return result
        finally:
            if fd is not None:
                loop.remove_reader(fd)
            if editor is not None:
                editor.cancel()
                with suppress(asyncio.CancelledError):
                    await editor
            self.finish_stream()
            self._runtime = None

    async def execute(
        self, request: str, *, compact: bool = False, all_messages: bool = False
    ) -> Result:
        if self._unsettled is not None and self._unsettled.cleanup_pending:
            raise ValueError("previous_cleanup_pending")
        self.config.credential()
        result = await self.turn(request, compact=compact, all_messages=all_messages)
        self.show(
            f"{result.status}: {result.reason}\nExecution: {result.execution_id}\nLedger: {result.ledger_path}"
        )
        return result

    async def dispatch_command(self, text: str) -> None:
        parts = shlex.split(text)
        if parts and parts[0] in {"/save", "/compact"}:
            name = parts[0]
            if len(parts) != 1:
                raise ValueError("unexpected_command_arguments")
            if not self.conversation.messages and self.conversation.summary is None:
                self.show("No context to summarize.")
                return
            if self.conversation.messages or name == "/compact":
                result = await self.execute("", compact=True, all_messages=name == "/save")
                if result.status != "completed":
                    return
            if name == "/save":
                self.show("Summary ID: " + self.store().save(self.conversation))
        else:
            self.command(text)

    def command(self, text: str) -> None:
        try:
            parts = shlex.split(text)
            name, *values = parts
            if (
                name
                in {
                    "/help",
                    "/context",
                    "/compact",
                    "/save",
                    "/sessions",
                    "/usage",
                    "/clear",
                    "/queue",
                    "/next",
                    "/drop",
                    "/details",
                    "/quit",
                }
                and values
            ):
                raise ValueError("unexpected_command_arguments")
            if name == "/quit":
                self.exit = True
            elif name == "/help":
                self.show(HELP)
            elif name == "/context":
                self.show(json.dumps(self.conversation.diagnostics(), indent=2))
            elif name == "/usage":
                self.show(
                    json.dumps(
                        {
                            **self.conversation.usage,
                            "cost_status": "unavailable",
                            "max_session_tokens": self.config.max_session_tokens,
                        },
                        indent=2,
                    )
                )
            elif name == "/clear":
                self.conversation.clear()
            elif name == "/queue":
                self.show(
                    json.dumps(
                        {"paused": self.paused, "next_turn": self.queue},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif name == "/next":
                self.paused = False
            elif name == "/drop":
                self.queue.clear()
            elif name == "/sessions":
                self.show(
                    "\n".join(self.store().list_sessions(self.config.limits))
                    or "No saved summaries."
                )
            elif name == "/resume":
                if len(values) != 1:
                    raise ValueError("summary_id_required")
                candidate = self.store().load(values[0], self.config.limits)
                self.conversation = candidate
                self.queue.clear()
                self.show(
                    "Summary and usage restored. Tool authorization still comes from the project."
                )
            elif name == "/model":
                if len(values) > 1:
                    raise ValueError("invalid_model")
                if values:
                    candidate = replace(self.config, model=values[0])
                    candidate.credential()
                    self.config = candidate
                    self._model_override = values[0]
                self.show(
                    json.dumps(
                        {
                            **asdict(self.config),
                            "window_source": "application config, not inferred from model",
                        },
                        indent=2,
                    )
                )
            elif name == "/details":
                self.show(
                    json.dumps(
                        {**asdict(self.last), "ledger_path": str(self.last.ledger_path)}, indent=2
                    )
                    if self.last
                    else "No execution yet."
                )
            elif name == "/project":
                if self._unsettled is not None and self._unsettled.cleanup_pending:
                    raise ValueError("previous_cleanup_pending")
                if len(values) != 1:
                    raise ValueError("project_required")
                from .cli import load_project

                root = Path(values[0]).expanduser().resolve()
                candidate = load_config(root, model=self._model_override)
                project = load_project(root, self.plugin)
                self.project, self.config = project, candidate
                self.conversation = Conversation(candidate.limits)
                self.queue.clear()
                self.paused = False
                self.last = None
                self.show("Project: " + str(root))
            elif name[1:] in self.project.commands and not values:
                self.show(self.project.commands[name[1:]]())
            else:
                self.show("Unknown command. Use /help.")
        except Exception:
            self.show(
                "Command rejected. Check arguments, config, summary scope/window or credential environment. Current context is preserved."
            )

    async def run_async(self) -> int:
        self.show(
            f"Agent Entry CLI · {self.project.root.name}\nModel: {self.config.model or 'not configured'}\n/help for commands; /stop during execution."
        )
        while not self.exit:
            try:
                if self.queue and not self.paused:
                    request = self.queue.pop(0)
                elif self.enhanced:
                    request = await self.session().prompt_async("agent > ")
                else:
                    request = await asyncio.to_thread(input, "agent > ")
                if not request.strip():
                    continue
                if request.startswith("/"):
                    await self.dispatch_command(request)
                else:
                    await self.execute(request)
            except EOFError:
                break
            except KeyboardInterrupt:
                self.show("Interrupted.")
                self.paused = True
            except Exception:
                self.paused = True
                self.show(
                    "Request rejected. Check /model, credentials, /context and /usage; no automatic retry."
                )
        return 0

    def run(self) -> int:
        if self.enhanced:
            with patch_stdout(raw=True):
                return asyncio.run(self.run_async())
        return asyncio.run(self.run_async())
