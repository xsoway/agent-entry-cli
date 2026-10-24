#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : __init__.py
# @Author   : Alan_Hsu
"""A project supplies instructions and async tools; the CLI supplies the lifecycle."""

from .config import Config, load_config
from .project import Project, Tool, ToolCall
from .runtime import Result, Runtime


def run_cli(project: Project, settings: Config | None = None) -> int:
    from .terminal import Terminal

    return Terminal(project, settings or load_config(project.root)).run()


__all__ = ["Config", "Project", "Tool", "ToolCall", "Result", "Runtime", "run_cli"]
__version__ = "0.1.0"
