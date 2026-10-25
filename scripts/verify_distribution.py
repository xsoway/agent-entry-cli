#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 10:00
# @Filename : verify_distribution.py
# @Author   : Alan_Hsu
"""Install the built wheel into an independent uv project and run outside the checkout."""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Require a complete uv cache")
    settings = parser.parse_args()
    network_flags = ("--offline",) if settings.offline else ()
    repository = Path(__file__).resolve().parents[1]
    wheels = list((repository / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Build exactly one wheel before distribution verification.")
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("AH_FRAMEWORK_ROOT", None)
    with tempfile.TemporaryDirectory(prefix="agent-entry-wheel-") as directory:
        root = Path(directory).resolve()
        (root / "pyproject.toml").write_text(
            '[project]\nname="wheel-smoke"\nversion="0.0.0"\nrequires-python=">=3.13"\n'
            'dependencies=["agent-entry-cli"]\n[tool.uv.sources]\n'
            f"agent-entry-cli={{path={json.dumps(str(wheels[0]))}}}\n"
        )
        # Seed version preferences, then resolve a new root and wheel source independently.
        shutil.copyfile(repository / "uv.lock", root / "uv.lock")

        def run(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                args, cwd=root, env=env, text=True, capture_output=True, timeout=180, check=True
            )

        run("uv", "lock", *network_flags)
        run("uv", "sync", "--locked", *network_flags)
        result = run("uv", "run", "--locked", "agent-entry", "--version")
        assert "agent-entry-cli 0.1.0" in result.stdout
        run("uv", "run", "--locked", "agent-entry", "--init")
        diagnostics = run("uv", "run", "--locked", "agent-entry", "--diagnostics")
        assert json.loads(diagnostics.stdout)["context_window"] == 65536
        code = 'import importlib.util; from pathlib import Path; import agent_entry_cli; assert Path(agent_entry_cli.__file__).is_relative_to(Path.cwd()/".venv"); assert importlib.util.find_spec("agent_eval_harness") is None; print("standalone wheel imports passed")'
        check = run("uv", "run", "--locked", "python", "-I", "-c", code)
        print(check.stdout.strip())
        print("Independent wheel installation, init and diagnostics passed.")


if __name__ == "__main__":
    main()
