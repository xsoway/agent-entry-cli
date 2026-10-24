#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : project.py
# @Author   : Alan_Hsu
"""Small trusted project API; no automatic Python discovery or implicit writes."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class Tool:
    function: Callable[..., Any]
    side_effect: bool = False

    def __post_init__(self):
        if not inspect.iscoroutinefunction(self.function) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]{0,63}", self.function.__name__
        ):
            raise ValueError("tool_requires_named_async_function")
        if type(self.side_effect) is not bool:
            raise ValueError("invalid_tool_effect")

    @property
    def name(self) -> str:
        return self.function.__name__


@dataclass(frozen=True)
class ToolCall:
    root: Path
    name: str
    arguments: Any = field(repr=False)
    side_effect: bool = False


@dataclass(frozen=True)
class Project:
    root: Path
    instructions: str = "You are the main assistant for this project. Ask when facts are missing."
    tools: tuple[Tool, ...] = ()
    authorize: Callable[[ToolCall], bool] | None = field(default=None, repr=False)
    commands: dict[str, Callable[[], str]] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "root", Path(self.root).expanduser().resolve())
        object.__setattr__(self, "tools", tuple(self.tools))
        if (
            not self.root.is_dir()
            or not isinstance(self.instructions, str)
            or not 0 < len(self.instructions.encode()) <= 32768
        ):
            raise ValueError("invalid_project")
        if any(not isinstance(tool, Tool) for tool in self.tools) or len(
            {tool.name for tool in self.tools}
        ) != len(self.tools):
            raise ValueError("duplicate_or_invalid_tools")
        if self.authorize is not None and (
            not callable(self.authorize) or inspect.iscoroutinefunction(self.authorize)
        ):
            raise ValueError("authorization_must_be_sync")
        if any(
            not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name) or not callable(fn)
            for name, fn in self.commands.items()
        ):
            raise ValueError("invalid_command")

    def permit(self, tool: Tool, arguments: dict[str, Any]) -> bool:
        if self.authorize is None:
            return not tool.side_effect
        try:
            return (
                self.authorize(
                    ToolCall(self.root, tool.name, MappingProxyType(arguments), tool.side_effect)
                )
                is True
            )
        except Exception:
            return False
