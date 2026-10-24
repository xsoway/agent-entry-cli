#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : privacy.py
# @Author   : Alan_Hsu
"""Best-effort credential redaction and terminal-control filtering, not a DLP system."""

from __future__ import annotations

import re

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-_])")
_CONTROLS = dict.fromkeys([*range(9), *range(11, 32), *range(127, 160)])
_AUTH = re.compile(r'(?i)\b(?:Bearer|Basic)\s+[^\s,;"\']+')
_KEY = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16})\b")
_NAMED = re.compile(
    r'(?i)\b(?:api_key|password|secret|access_token)\s*[:=]\s*(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s,;}]+)'
)


def redact_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    for value in secrets:
        if value:
            text = text.replace(value, "***")
    return _NAMED.sub("***", _KEY.sub("***", _AUTH.sub("***", text)))


def clean(text: str) -> str:
    return _ANSI.sub("", text).translate(_CONTROLS)
