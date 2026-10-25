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
import signal
import sys
import time
from contextlib import suppress
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.styles import Style
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .config import Config, load_config
from .conversation import Conversation
from .display import COMMANDS, HELP, format_context, format_result, format_usage, progress_text
from .errors import explain, safe_reason
from .input import LineInput
from .privacy import clean, redact_text
from .project import Project
from .runtime import Result, Runtime, context_diagnostics
from .storage import SummaryStore


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
            color_system="auto" if self.enhanced and "NO_COLOR" not in os.environ else None,
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
        self._line_input: LineInput | None = None
        self._interrupt_requested = False
        self._phase = "就绪"
        self._started_at: float | None = None
        self._model_calls = 0
        self._last_duration = 0.0
        self._context_estimate: int | None = None
        self._current_known = 0
        self._usage_pending = False
        self._total_stream_bytes = 0

    def safe_text(self, value: str) -> str:
        """对所有展示字段执行同一套脱敏与终端控制过滤。"""
        return clean(redact_text(value, (os.environ.get(self.config.api_key_env, ""),)))

    def show(self, value: str) -> None:
        self.console.print(Text(self.safe_text(value)))

    def panel(self, value: str, title: str, *, style: str = "cyan") -> None:
        """增强模式展示面板；普通模式保留可读文本，不解析外部标记。"""
        if not self.enhanced:
            self.show(value)
            return
        self.console.print(
            Panel(
                Text(self.safe_text(value)),
                title=Text(self.safe_text(title)),
                title_align="left",
                border_style=style if "NO_COLOR" not in os.environ else "",
                box=box.ROUNDED,
                padding=(0, 1),
            )
        )

    def available_commands(self) -> list[str]:
        return sorted(set(COMMANDS) | {"/" + name for name in self.project.commands})

    def toolbar(self) -> FormattedText:
        """刷新安全状态与耗时，不展示模型内部推理。"""
        state = "执行中" if self._runtime is not None else "已暂停" if self.paused else "就绪"
        elapsed = time.monotonic() - self._started_at if self._started_at is not None else 0
        info = self.safe_text(
            f" {state} · {self.project.root.name} · {self.config.model or '未配置模型'}"
            f" · 队列 {len(self.queue)}"
            + (
                f" · {self._phase} · {elapsed:.1f}s · 模型 {self._model_calls}/{self.config.max_model_calls}"
                if self._runtime is not None
                else ""
            )
        )
        hint = (
            " Esc / Ctrl+C 取消 · 再次 Ctrl+C 退出 · Enter 排队 · /status 查看"
            if self._runtime is not None
            else " Enter 发送 · Alt+Enter 换行 · Tab 补全 · Ctrl+C / Ctrl+D 退出"
        )
        return FormattedText([("class:status", info), ("class:hint", "\n" + hint)])

    def observe(self, event: dict[str, Any]) -> None:
        """仅消费运行时构造的允许字段，渲染层仍统一脱敏和过滤。"""
        self._model_calls = event.get("model_calls", self._model_calls)
        if event.get("event") == "model":
            self._usage_pending = True
            self._context_estimate = event.get("context_estimate", self._context_estimate)
            self._current_known = event.get("known_tokens", self._current_known)
        if event.get("event") == "ended":
            self._usage_pending = False
            self._phase = explain(event["reason"])
            self._last_duration = event.get("duration_ms", 0) / 1000
        label = progress_text(event, self.config.max_model_calls)
        if label:
            self._phase = label
            # 模型生产者事件可能早于文本消费者；不得刷新跨 chunk 脱敏尾串。
            if self._stream_bytes:
                self.console.print()
            self.show("· " + label)
        if self._session is not None and self._session.app.is_running:
            self._session.app.invalidate()

    async def heartbeat(self) -> None:
        while True:
            await asyncio.sleep(5)
            if not self.enhanced and self._runtime is not None:
                elapsed = time.monotonic() - (self._started_at or time.monotonic())
                self.show(f"· {self._phase} · 已等待 {elapsed:.0f}s（/stop 取消，/status 查看）")

    def prompt(self, *, running: bool = False) -> FormattedText:
        """保留原提示词便于终端识别，用边界和背景区分输入区域。"""
        return FormattedText(
            [
                (
                    "class:frame",
                    "╭─ " + ("下一轮输入 / 中断控制" if running else "输入消息") + "\n",
                ),
                ("class:prompt", "╰ running > " if running else "╰ agent > "),
            ]
        )

    def request_exit(self) -> None:
        """请求退出；运行中的 SDK 清理仍由原任务负责。"""
        self.exit = True
        if self._runtime is not None:
            self._runtime.cancel()
        elif self._line_input is not None:
            self._line_input.interrupt()
        if self._runtime is None and self._session is not None:
            app = self._session.app
            if app.is_running:
                app.exit(exception=EOFError())

    def interrupt(self) -> None:
        """运行中首次取消，再次请求退出；空闲立即退出。"""
        if self._runtime is None or self._interrupt_requested:
            self.request_exit()
        else:
            self._interrupt_requested = True
            self._runtime.cancel()
            self.show("正在取消，等待清理；再次 Ctrl+C 将在清理后退出。")

    async def read_line(self, *, running: bool = False) -> str:
        if self.enhanced:
            return await self.session().prompt_async(
                self.prompt(running=running), handle_sigint=False
            )
        if self._line_input is None:
            self._line_input = LineInput(sys.stdin.fileno())
        if not running:
            self.console.print("agent > ", end="")
        return await self._line_input.readline()

    def store(self) -> SummaryStore:
        scope = hashlib.sha256(str(self.project.root).encode()).hexdigest()
        return SummaryStore(self.project.root / ".agent-entry/summaries", scope)

    def stream_text(self, delta: str) -> None:
        self._stream_bytes += len(delta.encode())
        self._total_stream_bytes += len(delta.encode())
        if self._total_stream_bytes > 65536:
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
        if text in {"/quit", "/exit"}:
            self.request_exit()
            return True
        if text == "/stop":
            runtime.cancel()
            return True
        if text in {
            "/help",
            "/status",
            "/context",
            "/usage",
            "/tools",
            "/details",
            "/queue",
            "/model",
        }:
            self.command(text)
            return True
        if not text or text.startswith("/") or len(text.encode()) > 40000 or len(self.queue) >= 8:
            self.show("运行中仅接受下一轮文字、只读控制、/stop 或 /quit；控制命令不能排队。")
            return False
        self.queue.append(text)
        self.show(f"已加入下一轮队列（{len(self.queue)} 条）。")
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
                self.interrupt()

            @keys.add("escape", "enter")
            def newline(event):
                event.current_buffer.insert_text("\n")

            styles = {
                "": "bg:#202b36 #e5eaf0",
                "frame": "#73b8c6",
                "prompt": "#73b8c6 bold",
                "status": "bg:#293847 #b6d7cf",
                "hint": "bg:default ansibrightblack",
                "completion-menu.completion": "bg:#293847 #e5eaf0",
                "completion-menu.completion.current": "bg:#376273 #ffffff bold",
            }
            if "NO_COLOR" in os.environ:
                styles = dict.fromkeys(styles, "")
            self._session = PromptSession(
                style=Style.from_dict(styles),
                reserve_space_for_menu=6,
                color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
                completer=WordCompleter(self.available_commands, ignore_case=True, sentence=True),
                bottom_toolbar=self.toolbar,
                refresh_interval=0.5,
                key_bindings=keys,
                multiline=False,
            )
        return self._session

    async def turn(
        self, request: str, *, compact: bool = False, all_messages: bool = False
    ) -> Result:
        runtime = Runtime(self.project, self.config, self.conversation)
        self._runtime = runtime
        self._interrupt_requested = False
        self._started_at = time.monotonic()
        self._model_calls = 0
        self._phase = "准备执行"
        self._context_estimate = None
        self._current_known = 0
        self._usage_pending = True
        self._total_stream_bytes = 0
        worker = asyncio.create_task(
            runtime.run(
                request,
                on_text=self.stream_text,
                on_event=self.observe,
                compact=compact,
                all_messages=all_messages,
            )
        )
        editor = None
        heartbeat = asyncio.create_task(self.heartbeat())

        async def input_loop():
            while not worker.done():
                try:
                    text = await self.read_line(running=True)
                except EOFError:
                    self.request_exit()
                    return
                except KeyboardInterrupt:
                    self.interrupt()
                    continue
                self.intervene(text, runtime)

        try:
            if self.enhanced or sys.stdin.isatty():
                editor = asyncio.create_task(input_loop())
            result = await worker
            self.last = result
            if not result.cleanup_complete:
                self._unsettled = runtime
            if result.status != "completed":
                self.paused = True
            return result
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            if editor is not None:
                editor.cancel()
                with suppress(asyncio.CancelledError):
                    await editor
            self.finish_stream()
            self._last_duration = time.monotonic() - (self._started_at or time.monotonic())
            self._started_at = None
            self._runtime = None

    async def execute(
        self, request: str, *, compact: bool = False, all_messages: bool = False
    ) -> Result:
        if self._unsettled is not None and self._unsettled.cleanup_pending:
            raise ValueError("previous_cleanup_pending")
        self.config.credential()
        if self.enhanced:
            self.panel(
                "正在整理上下文…" if compact else request,
                "上下文" if compact else "你",
                style="blue",
            )
            self.console.rule(Text("助手"), style="cyan" if "NO_COLOR" not in os.environ else "")
        result = await self.turn(request, compact=compact, all_messages=all_messages)
        self.panel(
            format_result(asdict(result), self.config.max_model_calls)
            + f"\n耗时：{self._last_duration:.1f}s",
            "执行结果",
            style="green" if result.status == "completed" else "yellow",
        )
        return result

    async def dispatch_command(self, text: str) -> None:
        try:
            parts = shlex.split(text)
        except ValueError:
            raise ValueError("invalid_command_syntax") from None
        if parts and parts[0] in {"/save", "/compact"}:
            name = parts[0]
            if len(parts) != 1:
                raise ValueError("unexpected_command_arguments")
            if not self.conversation.messages and self.conversation.summary is None:
                self.show("没有可整理的上下文。")
                return
            if self.conversation.messages or name == "/compact":
                result = await self.execute("", compact=True, all_messages=name == "/save")
                if result.status != "completed":
                    return
            if name == "/save":
                self.show("摘要已保存，ID：" + self.store().save(self.conversation))
        else:
            self.command(text)

    def command(self, text: str) -> None:
        try:
            try:
                parts = shlex.split(text)
            except ValueError:
                raise ValueError("invalid_command_syntax") from None
            if not parts:
                return
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
                    "/exit",
                    "/stop",
                    "/tools",
                    "/status",
                }
                and values
            ):
                raise ValueError("unexpected_command_arguments")
            if name in {"/quit", "/exit"}:
                self.request_exit()
            elif name == "/help":
                custom = "、".join("/" + item for item in self.project.commands)
                self.show(HELP + ("\n项目命令：" + custom + "（内置命令优先）" if custom else ""))
            elif name == "/stop":
                self.show("当前没有执行中的任务。")
            elif name == "/status":
                elapsed = (
                    time.monotonic() - self._started_at
                    if self._started_at is not None
                    else self._last_duration
                )
                self.show(
                    f"状态：{self._phase}；模型循环 {self._model_calls}/{self.config.max_model_calls}；最近执行耗时 {elapsed:.1f}s；队列 {len(self.queue)} 条，{'已暂停' if self.paused else '可继续'}。"
                )
            elif name == "/tools":
                rows = [
                    f"{tool.name} · {'写操作，需逐次授权' if tool.side_effect else '只读声明，非沙箱'}"
                    for tool in self.project.tools
                ]
                policy = (
                    "已配置，逐次检查；此列表不表示已批准"
                    if self.project.authorize is not None
                    else "未配置，声明写操作默认拒绝"
                )
                self.show(
                    "项目工具：\n" + ("\n".join(rows) or "未注册工具") + "\n授权策略：" + policy
                )
            elif name == "/context":
                self.show(
                    format_context(
                        context_diagnostics(self.project, self.config, self.conversation)
                    )
                )
                if self._context_estimate is not None:
                    self.show(
                        f"最近执行的实际准入估算：{self._context_estimate}（包含本轮输入及工具循环材料）。"
                    )
            elif name == "/usage":
                self.show(format_usage(self.conversation.usage, self.config.max_session_tokens))
                if self._usage_pending:
                    self.show(
                        f"本轮尚未结算：已知部分 {self._current_known} token；最终总量尚未确定，未重复计入累计用量。"
                    )
            elif name == "/clear":
                self.conversation.clear()
                self.show("上下文已清空，累计用量保留。")
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
                rows = self.store().entries(self.config.limits)
                self.show(
                    "本地保存时间（UTC） · 摘要 ID · 任务预览\n"
                    + "\n".join(
                        f"{row['saved_at']} · {row['id']} · {row['preview']}" for row in rows
                    )
                    if rows
                    else "没有已保存的摘要；使用 /save 显式保存。"
                )
            elif name == "/resume":
                if len(values) != 1:
                    raise ValueError("summary_id_required")
                identifier = values[0]
                if identifier == "latest":
                    available = self.store().list_sessions(self.config.limits)
                    if not available:
                        raise ValueError("no_saved_summaries")
                    identifier = available[0]
                candidate = self.store().load(identifier, self.config.limits)
                self.conversation = candidate
                self.queue.clear()
                self.show("摘要与历史用量快照已恢复；工具仍需项目授权，不代表账户计费状态。")
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
                            "window_source": "应用配置，非推断出的模型容量",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            elif name == "/details":
                self.show(
                    json.dumps(
                        {
                            **{
                                key: value
                                for key, value in asdict(self.last).items()
                                if key != "output"
                            },
                            "ledger_path": str(self.last.ledger_path),
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    if self.last
                    else "尚无执行记录；运行中使用 /status 查看。"
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
                self._phase = "就绪"
                self._model_calls = 0
                self._last_duration = 0
                self._context_estimate = None
                self._current_known = 0
                self._usage_pending = False
                self._session = None
                self._unsettled = None
                self.show("当前项目：" + str(root))
            elif name[1:] in self.project.commands and not values:
                self.show(self.project.commands[name[1:]]())
            else:
                self.show("未知命令；使用 /help 查看可用命令。")
        except Exception as error:
            self.show(explain(safe_reason(error)))

    async def run_async(self) -> int:
        loop = asyncio.get_running_loop()
        previous = signal.getsignal(signal.SIGINT)
        loop.add_signal_handler(signal.SIGINT, self.interrupt)
        try:
            return await self._run_session()
        finally:
            loop.remove_signal_handler(signal.SIGINT)
            signal.signal(signal.SIGINT, previous)

    async def _run_session(self) -> int:
        self.panel(
            f"项目：{self.project.root.name}\n{self.project.root}\n"
            f"模型：{self.config.model or '未配置'}；工具：{len(self.project.tools)} 个\n\n"
            "输入任务开始 · /help 帮助 · /tools 工具 · Ctrl+C / Ctrl+D 退出",
            "Agent Entry CLI",
        )
        while not self.exit:
            try:
                if self.queue and not self.paused:
                    request = self.queue.pop(0)
                else:
                    request = await self.read_line()
                if not request.strip():
                    continue
                if request.startswith("/"):
                    await self.dispatch_command(request)
                else:
                    await self.execute(request)
            except EOFError:
                break
            except KeyboardInterrupt:
                self.request_exit()
            except Exception as error:
                self.paused = True
                self.show(explain(safe_reason(error)))
        return 0

    def run(self) -> int:
        if self.enhanced:
            with patch_stdout(raw=True):
                return asyncio.run(self.run_async())
        return asyncio.run(self.run_async())
