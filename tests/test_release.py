#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/25 10:09
# @Filename : test_release.py
# @Author   : Alan_Hsu
"""Release gates operate on real temporary Git repositories, without publishing."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_release.py"
PUBLIC_EMAIL = "42+maintainer@users.noreply.github.com"


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout


def repository(tmp_path, email=PUBLIC_EMAIL):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "maintainer")
    git(tmp_path, "config", "user.email", email)
    (tmp_path / "README.md").write_text("release example\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial")
    return tmp_path


def check(root):
    assert SCRIPT.exists(), "release preflight must exist"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True
    )


def test_public_identity_clean_snapshot_passes(tmp_path):
    result = check(repository(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_private_commit_email_fails_without_disclosure(tmp_path):
    private = "private-person" + "@" + "example.net"
    result = check(repository(tmp_path, private))
    assert result.returncode == 1
    assert "commit_identity" in result.stdout
    assert private not in result.stdout + result.stderr


def test_secret_in_old_revision_is_still_rejected(tmp_path):
    root = repository(tmp_path)
    secret = "sk-" + "X" * 32
    (root / "settings.txt").write_text(secret)
    git(root, "add", ".")
    git(root, "commit", "-m", "add settings")
    (root / "settings.txt").write_text("placeholder")
    git(root, "add", ".")
    git(root, "commit", "-m", "remove settings")
    result = check(root)
    assert result.returncode == 1
    assert "history:settings.txt" in result.stdout and "credential" in result.stdout
    assert secret not in result.stdout + result.stderr


def test_untracked_source_and_modified_tree_are_rejected(tmp_path):
    root = repository(tmp_path)
    (root / "new_tool.py").write_text("pass\n")
    (root / "README.md").write_text("changed\n")
    result = check(root)
    assert result.returncode == 1
    assert "incomplete_snapshot" in result.stdout


def test_private_path_and_untracked_secret_are_rejected(tmp_path):
    root = repository(tmp_path)
    secret = "ghp_" + "Y" * 36
    (root / "leak.txt").write_text(secret + "\n" + "/" + "Users/private/work")
    result = check(root)
    assert result.returncode == 1
    assert "credential" in result.stdout and "local_path" in result.stdout
    assert secret not in result.stdout + result.stderr


def test_github_generated_commit_identity_is_public(tmp_path):
    email = "noreply" + "@" + "github.com"
    result = check(repository(tmp_path, email))
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("historical", [False, True])
def test_mixed_encoding_does_not_hide_ascii_credential(tmp_path, historical):
    root = repository(tmp_path)
    secret = "sk-" + "Z" * 32
    (root / "legacy.dat").write_bytes(b"\xff\xfe" + secret.encode())
    git(root, "add", ".")
    git(root, "commit", "-m", "legacy file")
    if historical:
        (root / "legacy.dat").write_bytes(b"clean")
        git(root, "add", ".")
        git(root, "commit", "-m", "clean file")
    result = check(root)
    assert result.returncode == 1
    assert "credential" in result.stdout
    assert secret not in result.stdout + result.stderr


@pytest.mark.parametrize("kind", ["commit", "tag"])
def test_reachable_messages_cannot_publish_credentials(tmp_path, kind):
    root = repository(tmp_path)
    secret = "ghp_" + "Z" * 36
    if kind == "commit":
        git(root, "commit", "--allow-empty", "-m", secret)
    else:
        git(root, "tag", "-a", "release-test", "-m", secret)
    result = check(root)
    assert result.returncode == 1
    assert "credential" in result.stdout and f"history:{kind}:" in result.stdout
    assert secret not in result.stdout + result.stderr
