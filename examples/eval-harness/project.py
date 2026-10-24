#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : project.py
# @Author   : Alan_Hsu
"""Optional read-only integration; agent-eval must be installed separately."""

import asyncio
from pathlib import Path

from agent_entry_cli import Project, Tool


def build_project(root: Path) -> Project:
    async def workflow_status() -> str:
        """Read the existing evaluation Core workflow status. Never approve or run evaluations."""
        start = asyncio.create_task(
            asyncio.create_subprocess_exec(
                "agent-eval",
                "status",
                str(root),
                "--format",
                "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        )
        process = None
        try:
            process = await asyncio.shield(start)
            output, _ = await asyncio.wait_for(process.communicate(), 10)
            if process.returncode:
                return "Core status command failed; inspect project configuration locally."
            if len(output) > 32768:
                return "Core status output exceeded the adapter limit."
            return output.decode(errors="replace")
        finally:

            async def reap():
                owned = process if process is not None else await start
                if owned.returncode is None:
                    owned.kill()
                await owned.wait()

            # A cancelled subprocess launch can still have created a child.
            cleanup = asyncio.create_task(reap())
            cancelled = False
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cancelled = True
            cleanup.result()
            if cancelled:
                raise asyncio.CancelledError

    return Project(
        root,
        instructions="Explain evaluation workflow status using the read-only Core tool. Business decisions, plan/dataset review and Golden release remain in the existing evaluation framework. Never claim approval or execution.",
        tools=(Tool(workflow_status),),
    )
