# Agent Entry CLI development

<!-- code_project: parent-agents-required -->

In this workspace read `../../../AGENTS.md`, `../../AGENTS.md`, then this file.
When cloned independently, follow the standalone rules below; absent parent files are not required.

Use Karpathy guidelines before planning; use engineering-acceptance-harness and autonomous-loop for implementation when available. Preserve existing work. Keep the library independent of agent-eval-harness.

Use Python 3.13+, `uv sync --locked --extra dev`, and the project `.venv`.
Run `uv run --locked --extra dev pytest -q`, `ruff check .`, `pyright` and `uv build` before delivery.
New Python files include encoding, creation time, filename and author headers.

Project adapters are trusted local code, not a sandbox. Never import project plugins automatically.
Do not log raw messages, tool arguments, tool results, credentials or private reasoning by default.
Only explicit `/save` persists summaries. A restored summary never grants tool authorization.
Side-effect tools require a project authorization callback on every invocation. Never automatically replay writes.
Preserve stream cleanup ownership, incomplete usage and scope isolation regression tests.
