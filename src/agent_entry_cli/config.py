#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : config.py
# @Author   : Alan_Hsu
"""Strict data-only project configuration; credentials stay in the environment."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Limits:
    context_window: int = 65536
    output_reserve: int = 4096
    system_reserve: int = 8192
    max_session_tokens: int | None = None

    def __post_init__(self):
        for value in (self.context_window, self.output_reserve, self.system_reserve):
            if type(value) is not int or not 0 < value <= 10**8:
                raise ValueError("invalid_context_limits")
        if self.output_reserve + self.system_reserve >= self.context_window:
            raise ValueError("invalid_context_limits")
        if self.max_session_tokens is not None and (
            type(self.max_session_tokens) is not int or self.max_session_tokens < 1
        ):
            raise ValueError("invalid_session_budget")


@dataclass(frozen=True)
class Config(Limits):
    model: str = ""
    api: str = "chat_completions"
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    max_model_calls: int = 12
    timeout_seconds: float = 120
    cleanup_seconds: float = 5

    def __post_init__(self):
        super().__post_init__()
        if (
            not isinstance(self.model, str)
            or len(self.model) > 128
            or (self.model and not re.fullmatch(r"[A-Za-z0-9_.:/-]+", self.model))
        ):
            raise ValueError("invalid_model")
        if self.api not in ("chat_completions", "responses"):
            raise ValueError("invalid_api")
        if not isinstance(self.api_key_env, str) or not re.fullmatch(
            r"[A-Z_][A-Z0-9_]*", self.api_key_env
        ):
            raise ValueError("invalid_credential_env")
        if self.base_url is not None:
            if not isinstance(self.base_url, str):
                raise ValueError("invalid_base_url")
            value = urlsplit(self.base_url)
            if (
                value.scheme not in ("http", "https")
                or not value.hostname
                or value.username
                or value.password
                or value.query
                or value.fragment
            ):
                raise ValueError("invalid_base_url")
        if type(self.max_model_calls) is not int or not 1 <= self.max_model_calls <= 100:
            raise ValueError("invalid_model_budget")
        for value in (self.timeout_seconds, self.cleanup_seconds):
            if type(value) not in (float, int) or not 0 < value <= 3600:
                raise ValueError("invalid_timeout")

    @property
    def limits(self) -> Limits:
        return Limits(
            self.context_window, self.output_reserve, self.system_reserve, self.max_session_tokens
        )

    def credential(self) -> str:
        value = os.environ.get(self.api_key_env, "")
        if not self.model or not value:
            raise ValueError("model_and_credential_required")
        return value


def load_config(root: Path, *, model: str | None = None) -> Config:
    path = root / "agent-entry.toml"
    try:
        if path.is_symlink() or (path.exists() and path.stat().st_size > 32768):
            raise ValueError("unsafe_config")
        data = tomllib.loads(path.read_text()) if path.exists() else {}
        if set(data) - {field.name for field in fields(Config)}:
            raise ValueError("unknown_config_field")
        data.setdefault(
            "model", os.environ.get("OPENAI_DEFAULT_MODEL", os.environ.get("LLM_MODEL_NAME", ""))
        )
        data.setdefault(
            "base_url", os.environ.get("OPENAI_BASE_URL", os.environ.get("LLM_BASE_URL"))
        )
        if model is not None:
            data["model"] = model
        return Config(**data)
    except (OSError, TypeError, ValueError):
        raise ValueError("invalid_project_config") from None
