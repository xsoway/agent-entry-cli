#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/25 10:10
# @Filename : check_release.py
# @Author   : Alan_Hsu
"""Fail closed on incomplete Git snapshots and common publication leaks.

This is a focused release gate, not a comprehensive secret scanner or DLP system.
It checks working files, reachable history blobs and commit email metadata.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

RULES = {
    "credential": re.compile(
        r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
        r"|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{15,}|AKIA[0-9A-Z]{16}"
    ),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),
    "local_path": re.compile(r"/(?:Users|home)/[^\s/\"'<>]+"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}
PUBLIC_EMAIL = re.compile(
    r"(?:[A-Za-z0-9_+.\[\]-]+@users\.noreply\.github\.com|(?:noreply|support)@github\.com)"
)


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=True, timeout=30
    ).stdout


def scan(location: str, data: bytes) -> list[tuple[str, str]]:
    # Preserve ASCII secret bytes even inside mixed-encoding or binary content.
    text = data.decode("utf-8", errors="surrogateescape")
    findings = []
    for rule, pattern in RULES.items():
        for match in pattern.finditer(text):
            if rule == "email" and PUBLIC_EMAIL.fullmatch(match.group()):
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append((rule, f"{location}:{line}"))
    return findings


def inspect(root: Path) -> list[tuple[str, str]]:
    findings = []
    if git(root, "status", "--porcelain", "--untracked-files=all").strip():
        findings.append(("incomplete_snapshot", "worktree"))
    files = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for name in sorted(set(files.decode().split("\0")) - {""}):
        path = root / name
        if path.is_symlink():
            findings.extend(scan(name, str(path.readlink()).encode()))
        elif path.is_file():
            if (path.name.startswith(".env") and path.name != ".env.example") or any(
                part in {".agent-entry", ".venv"} for part in Path(name).parts
            ):
                findings.append(("private_file", name))
            findings.extend(scan(name, path.read_bytes()))
    commits = git(root, "log", "--all", "--format=%h%x00%ae%x00%ce").decode().splitlines()
    if not commits:
        findings.append(("missing_history", "repository"))
    for row in commits:
        revision, author, committer = row.split("\0")
        if not all(PUBLIC_EMAIL.fullmatch(email) for email in (author, committer)):
            findings.append(("commit_identity", revision))
    for row in git(root, "rev-list", "--objects", "--all").decode().splitlines():
        oid, _, name = row.partition(" ")
        kind = git(root, "cat-file", "-t", oid).decode().strip()
        if kind in {"blob", "commit", "tag"}:
            label = f"history:{name or oid}" if kind == "blob" else f"history:{kind}:{oid}"
            findings.extend(scan(label, git(root, "cat-file", kind, oid)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        findings = inspect(args.root.resolve())
    except (OSError, ValueError, subprocess.SubprocessError):
        print("FAIL release_check_failed (repository unavailable or unreadable)")
        return 1
    for rule, location in sorted(set(findings)):
        # Even a filename can contain a secret. Never copy its matching text into a report.
        for pattern in RULES.values():
            location = pattern.sub("<redacted>", location)
        print(f"FAIL {rule} {json.dumps(location, ensure_ascii=False)}")
    if findings:
        return 1
    print("PASS: complete snapshot, public commit emails, no matched content leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
