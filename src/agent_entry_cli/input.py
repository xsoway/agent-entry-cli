#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:47
# @Filename : input.py
# @Author   : Alan_Hsu
"""POSIX 普通终端的可取消行输入，不创建阻塞线程。"""

from __future__ import annotations

import asyncio
import os


class LineInput:
    def __init__(self, fd: int):
        self.fd = fd
        self.pending = bytearray()
        self.eof = False
        self.waiter: asyncio.Future[None] | None = None

    def interrupt(self) -> None:
        """唤醒空闲输入；不抢占运行时的清理任务。"""
        if self.waiter is not None and not self.waiter.done():
            self.waiter.set_exception(EOFError())

    async def readline(self) -> str:
        loop = asyncio.get_running_loop()
        while b"\n" not in self.pending:
            if self.eof:
                if self.pending:
                    value = self.pending.decode(errors="replace")
                    self.pending.clear()
                    return value
                raise EOFError
            waiter = loop.create_future()
            self.waiter = waiter

            def read(waiter: asyncio.Future[None] = waiter) -> None:
                try:
                    value = os.read(self.fd, 4096)
                    if value:
                        self.pending.extend(value)
                    else:
                        self.eof = True
                    if not waiter.done():
                        waiter.set_result(None)
                except OSError as error:
                    if not waiter.done():
                        waiter.set_exception(error)

            loop.add_reader(self.fd, read)
            try:
                await waiter
            finally:
                loop.remove_reader(self.fd)
                self.waiter = None
        line, _, rest = self.pending.partition(b"\n")
        self.pending[:] = rest
        return line.decode(errors="replace").rstrip("\r")
