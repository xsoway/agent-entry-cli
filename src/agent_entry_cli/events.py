#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : events.py
# @Author   : Alan_Hsu
"""Allowlisted execution metadata; raw payloads and exception text are rejected."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_FIELDS = {
    "execution_id",
    "status",
    "reason",
    "model_calls",
    "known_tokens",
    "observed_tokens",
    "cleanup_complete",
    "pending_writes",
    "tool_name",
    "side_effect",
    "duration_ms",
    "context_estimate",
}


class EventLog:
    def __init__(self, directory: Path, execution_id: str):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", execution_id):
            raise ValueError("invalid_execution_id")
        if any(p.is_symlink() for p in (directory, *directory.parents)):
            raise ValueError("unsafe_event_path")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / (execution_id + ".jsonl")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)

    def emit(self, event: str, attributes: dict[str, Any]) -> None:
        if (
            event not in {"started", "model", "tool", "ended", "compaction", "cleanup"}
            or set(attributes) - _FIELDS
        ):
            raise ValueError("event_payload_not_allowed")
        if any(
            not (value is None or type(value) in (str, int, float, bool))
            for value in attributes.values()
        ):
            raise ValueError("event_payload_not_allowed")
        body = (
            json.dumps({"event": event, **attributes}, ensure_ascii=False, allow_nan=False) + "\n"
        )
        fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        with os.fdopen(fd, "a") as stream:
            stream.write(body)
