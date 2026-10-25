#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : storage.py
# @Author   : Alan_Hsu
"""Explicit immutable summary checkpoints; never transcripts or execution grants."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .config import Limits
from .conversation import Conversation, estimate_tokens, parse_summary, serialized


@dataclass(frozen=True)
class SummaryStore:
    directory: Path
    scope: str

    def safe(self):
        if any(path.is_symlink() for path in (self.directory, *self.directory.parents)):
            raise ValueError("unsafe_summary_path")

    def save(self, state: Conversation) -> str:
        if state.summary is None or state.messages:
            raise ValueError("summary_required")
        row = {
            "schema": "agent-entry-summary-v1",
            "scope": self.scope,
            "summary": parse_summary(serialized(state.summary)),
            "usage": state.usage,
        }
        body = serialized(row)
        if len(body.encode()) > 32768:
            raise ValueError("summary_too_large")
        self.safe()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        identifier = uuid4().hex
        fd = os.open(
            self.directory / (identifier + ".json"),
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(fd, "w") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        return identifier

    def load(self, identifier: str, limits: Limits) -> Conversation:
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("invalid_summary_id")
        self.safe()
        fd = os.open(self.directory / (identifier + ".json"), os.O_RDONLY | os.O_NOFOLLOW)
        try:
            with os.fdopen(fd, "r") as stream:
                raw = stream.read(32769)
            if len(raw.encode()) > 32768:
                raise ValueError
            row = json.loads(raw)
            if (
                not isinstance(row, dict)
                or set(row) != {"schema", "scope", "summary", "usage"}
                or row["schema"] != "agent-entry-summary-v1"
                or row["scope"] != self.scope
            ):
                raise ValueError
            state = Conversation(limits)
            state.summary = parse_summary(serialized(row["summary"]))
            usage = row["usage"]
            if not isinstance(usage, dict) or set(usage) != set(state.usage):
                raise ValueError
            for key in ("executions", "model_calls", "known_tokens", "unknown_executions"):
                if type(usage[key]) is not int or not 0 <= usage[key] <= 10**12:
                    raise ValueError
            if (
                type(usage["complete"]) is not bool
                or usage["complete"] != (usage["unknown_executions"] == 0)
                or usage["cost"] is not None
            ):
                raise ValueError
            last = usage["last"]
            if last is not None:
                if not isinstance(last, dict) or set(last) != {
                    "model_calls",
                    "observed_tokens",
                    "known_tokens",
                }:
                    raise ValueError
                for key, value in last.items():
                    if key == "observed_tokens" and value is None:
                        continue
                    if type(value) is not int or not 0 <= value <= 10**12:
                        raise ValueError
                if last["known_tokens"] > usage["known_tokens"]:
                    raise ValueError
            if (
                estimate_tokens(state.compose("")) + limits.output_reserve + limits.system_reserve
                > limits.context_window
            ):
                raise ValueError
            state.usage = usage
            return state
        except (ValueError, TypeError, KeyError, RecursionError):
            raise ValueError("invalid_summary") from None

    def entries(self, limits: Limits) -> list[dict[str, str]]:
        """按本地保存时间列出有效摘要；预览只读取已经显式保存的材料。"""
        self.safe()
        candidates = []
        for path in self.directory.glob("*.json"):
            try:
                candidates.append((path.stat(follow_symlinks=False).st_mtime_ns, path))
            except OSError:
                continue
        result = []
        for timestamp, path in sorted(
            candidates, key=lambda item: (item[0], item[1].name), reverse=True
        ):
            try:
                state = self.load(path.stem, limits)
                summary = state.summary or {}
                preview = " ".join(summary.get("task") or summary.get("goals") or ["未命名摘要"])
                result.append(
                    {
                        "id": path.stem,
                        "saved_at": datetime.fromtimestamp(timestamp / 10**9, UTC).isoformat(
                            timespec="seconds"
                        ),
                        "preview": re.sub(r"\s+", " ", preview)[:100],
                    }
                )
                if len(result) >= 100:
                    break
            except (ValueError, OSError, OverflowError):
                continue
        return result

    def list_sessions(self, limits: Limits) -> list[str]:
        return [entry["id"] for entry in self.entries(limits)]
