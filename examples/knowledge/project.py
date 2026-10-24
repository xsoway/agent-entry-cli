#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : project.py
# @Author   : Alan_Hsu
"""An explicit trusted, read-only Markdown search adapter."""

from pathlib import Path

from agent_entry_cli import Project, Tool


def build_project(root: Path) -> Project:
    async def search_notes(query: str) -> str:
        """Search notes/*.md; return bounded source references and matching lines."""
        if not query.strip() or len(query) > 200:
            return "Query must be 1..200 characters."
        directory = root / "notes"
        hits = []
        if directory.is_symlink():
            return "Notes directory cannot be a symlink."
        for path in sorted(directory.glob("*.md"))[:100]:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
                continue
            if not path.resolve().is_relative_to(directory.resolve()):
                continue
            for line_no, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if query.casefold() in line.casefold():
                    hits.append(f"{path.relative_to(root)}:{line_no}: {line[:300]}")
                if len(hits) >= 20:
                    break
            if len(hits) >= 20:
                break
        return "\n".join(hits) or "No matching notes."

    return Project(
        root,
        instructions="You are the main knowledge assistant. Search notes before factual answers and cite returned file:line references. Never invent sources.",
        tools=(Tool(search_notes),),
    )
