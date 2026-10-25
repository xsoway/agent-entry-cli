#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:46
# @Filename : test_terminal_basics.py
# @Author   : Alan_Hsu
"""真实终端生命周期回归；仅隔离临时目录，不调用外部模型。"""

import fcntl
import json
import os
import pty
import re
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest


class PtyProcess:
    def __init__(self, args, *, width=80, no_color=False):
        self.fd, slave = pty.openpty()
        env = dict(os.environ, TERM="xterm-256color", OPENAI_API_KEY="fixture")
        if no_color:
            env["NO_COLOR"] = "1"
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, width, 0, 0))
        # Python 3.13 禁止在有 SDK 后台线程的 pytest 进程中使用 Python fork 钩子。
        # 由 Popen 先 exec 新解释器，再在新会话中获取控制终端。
        bootstrap = "import fcntl,os,sys,termios; fcntl.ioctl(0,termios.TIOCSCTTY,0); os.execv(sys.executable,[sys.executable,*sys.argv[1:]])"
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-c", bootstrap, *args],
                stdin=slave,
                stdout=slave,
                stderr=slave,
                env=env,
                start_new_session=True,
            )
        finally:
            os.close(slave)
        self.pid = self.process.pid
        self.output = bytearray()
        self.status = None

    def wait(self, predicate, timeout=8):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if select.select([self.fd], [], [], 0.05)[0]:
                try:
                    self.output.extend(os.read(self.fd, 65536))
                except OSError:
                    pass
            if self.status is None:
                self.status = self.process.poll()
            if predicate():
                return True
        return False

    def send(self, value):
        os.write(self.fd, value)

    def close(self):
        if self.status is None:
            self.process.kill()
            self.process.wait(timeout=3)
        os.close(self.fd)


@pytest.mark.parametrize("plain", [False, True])
@pytest.mark.parametrize("key", [b"\x03", b"\x04"])
def test_idle_control_key_exits_real_terminal(tmp_path, plain, key):
    child = PtyProcess(
        ["-m", "agent_entry_cli.cli", "--project", str(tmp_path)] + (["--plain"] if plain else [])
    )
    try:
        assert child.wait(lambda: b"agent >" in child.output), "startup prompt missing"
        child.send(key)
        assert child.wait(lambda: child.status is not None, 3), "idle terminal did not exit"
        assert child.status in (0, 130)
        assert b"Traceback" not in child.output
    finally:
        child.close()


@pytest.mark.parametrize("plain", [False, True])
@pytest.mark.parametrize(
    "action", ["cancel", "double", "quit", "exit", "eof", "signal", "double_signal"]
)
def test_running_controls_cleanup_without_replay(tmp_path, plain, action):
    # 真实 SDK 脚本模型，延迟公开文本后等待取消；终端仍经过真实 CLI 入口。
    tests = str(Path(__file__).parent)
    program = f"""
import sys, asyncio
sys.path.insert(0, {tests!r})
from test_runtime import Scripted
from openai.types.responses import ResponseTextDeltaEvent
from agent_entry_cli import Runtime
import agent_entry_cli.terminal as terminal
from agent_entry_cli.cli import main
class Slow(Scripted):
    async def stream_response(self, *args, **kwargs):
        yield ResponseTextDeltaEvent(type="response.output_text.delta",delta="VISIBLE_READY。",content_index=0,item_id="msg",logprobs=[],output_index=0,sequence_number=1)
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(.3)
terminal.Runtime = lambda p,c,v: Runtime(p,c,v,model=Slow([]))
raise SystemExit(main(sys.argv[1:]))
"""
    args = ["-c", program, "--project", str(tmp_path), "--model", "fixture"] + (
        ["--plain"] if plain else []
    )
    child = PtyProcess(args)
    try:
        assert child.wait(lambda: b"agent >" in child.output)
        child.send(b"hello\r")
        assert child.wait(lambda: b"VISIBLE_READY" in child.output)
        before = len(child.output)
        if action in {"signal", "double_signal"}:
            import signal

            os.kill(child.pid, signal.SIGINT)
            if action == "double_signal":
                time.sleep(0.05)
                os.kill(child.pid, signal.SIGINT)
        elif action == "eof":
            child.send(b"\x04")
        elif action in ("quit", "exit"):
            child.send(("/" + action + "\r").encode())
        else:
            child.send(b"\x03")
            if action == "double":
                time.sleep(0.05)
                child.send(b"\x03")
        if action in {"cancel", "signal"}:
            assert child.wait(lambda: b"agent >" in child.output[before:])
            assert child.status is None
            child.send(b"/quit\r")
        assert child.wait(lambda: child.status is not None, 4)
        assert b"Traceback" not in child.output
        receipts = list((tmp_path / ".agent-entry/executions").glob("*.jsonl"))
        assert len(receipts) == 1
        text = receipts[0].read_text()
        assert "user_cancelled" in text and '"cleanup_complete": true' in text
        assert "hello" not in text and "VISIBLE_READY" not in text
    finally:
        child.close()


@pytest.mark.parametrize("width", [32, 100])
def test_real_sdk_tool_progress_in_narrow_no_color_terminal(tmp_path, width):
    tests = str(Path(__file__).parent)
    program = f"""
import sys, asyncio
sys.path.insert(0, {tests!r})
from test_runtime import Scripted, response
from test_observability import tool_response
from agent_entry_cli import Runtime, Tool, Project
from agent_entry_cli.cli import main
import agent_entry_cli.terminal as terminal
async def lookup(query: str) -> str:
    await asyncio.sleep(.1)
    return "PRIVATE_TOOL_RESULT"
Original = terminal.Runtime
terminal.Runtime = lambda p,c,v: Original(Project(p.root, tools=(Tool(lookup),)),c,v,model=Scripted([tool_response("lookup", {{"query":"PRIVATE_TOOL_ARGUMENT"}}),response("hello")]))
raise SystemExit(main(sys.argv[1:]))
"""
    child = PtyProcess(
        ["-c", program, "--project", str(tmp_path), "--model", "fixture"],
        width=width,
        no_color=True,
    )
    try:
        assert child.wait(lambda: b"agent >" in child.output)
        child.send(b"hello\r")
        assert child.wait(lambda: "执行结果".encode() in child.output)
        child.send(b"/context\r/usage\r")
        assert child.wait(lambda: "累计已知用量".encode() in child.output)
        child.send(b"/quit\r")
        assert child.wait(lambda: child.status is not None)
        assert child.status == 0
        assert b"lookup" in child.output and b"2/12" in child.output
        assert b"PRIVATE_TOOL" not in child.output and b"Traceback" not in child.output
        for sgr in re.findall(rb"\x1b\[([\d;]*)m", child.output):
            values = [int(value) for value in sgr.split(b";") if value]
            assert not any(30 <= value <= 49 or 90 <= value <= 107 for value in values)
        ledgers = list((tmp_path / ".agent-entry/executions").glob("*.jsonl"))
        assert len(ledgers) == 1
        rows = [json.loads(line) for line in ledgers[0].read_text().splitlines()]
        assert rows[-1]["model_calls"] == 2 and rows[-1]["cleanup_complete"]
        assert b"PRIVATE_TOOL" not in ledgers[0].read_bytes()
    finally:
        child.close()


def test_real_sigint_handler_survives_between_enhanced_prompts(tmp_path):
    # 在两个真实 prompt 之间留一个异步窗口，检验 handler 归属；不依赖 raw Ctrl+C。
    program = """
import asyncio, sys
from agent_entry_cli.terminal import Terminal
from agent_entry_cli.cli import main
original = Terminal.read_line
async def read_line(self, **kwargs):
    value = await original(self, **kwargs)
    if value == "/help":
        print("SIGINT_GAP_READY", flush=True)
        for _ in range(150):
            if self.exit:
                break
            await asyncio.sleep(.02)
    return value
Terminal.read_line = read_line
raise SystemExit(main(sys.argv[1:]))
"""
    child = PtyProcess(["-c", program, "--project", str(tmp_path)])
    try:
        assert child.wait(lambda: b"agent >" in child.output)
        child.send(b"/help\r")
        assert child.wait(lambda: b"SIGINT_GAP_READY" in child.output)
        import signal

        os.kill(child.pid, signal.SIGINT)
        assert child.wait(lambda: child.status is not None, 1), "SIGINT was lost between prompts"
        assert child.status == 0 and b"Traceback" not in child.output
    finally:
        child.close()
