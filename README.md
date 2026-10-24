<div align="center">

# 🧭 Agent Entry CLI

**Give an existing project a main-agent terminal, with a small Python integration.**

![Python](https://img.shields.io/badge/Python-3.13%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Alpha-orange)

Streaming · Context summaries · Explicit project tools · Safe session controls

[简体中文](README.zh-CN.md) · [Integration](docs/integration.md) · [Architecture](docs/architecture.md)

</div>

## Why use it?

| Integration task | Application code usually needs | This package provides |
|---|---|---|
| Start a main agent | Terminal input, output and command plumbing | A project-aware terminal and an embeddable entry point |
| Support longer conversations | Window checks, summaries, restore and usage tracking | Shared conversation lifecycle with explicit summary checkpoints |
| Add business tools | UI work mixed with service calls | Async tools and a per-call project authorization callback |
| Handle interruptions | Stream cleanup and follow-up state | SDK-owned cancellation, visible execution metadata and paused queues |

**Keep your business services in your project. Supply instructions and async tools.**
This is an alpha Python library, not a sandbox, a generic coding agent or an approval system.

## Preview

<table>
<tr>
<td width="50%"><img src="docs/assets/help.svg" alt="Actual CLI help output"><br><b>Command-line entry</b> · Generated from actual local help output</td>
<td width="50%"><img src="docs/assets/context.svg" alt="Actual context diagnostic output"><br><b>Context diagnostics</b> · Local controls, no model call</td>
</tr>
</table>

## Features

- **Project entry:** `Project(root, instructions, tools)` and `run_cli(project)`.
- **Explicit tools:** async Python tools; declared writes require project authorization on every call.
- **Streaming controls:** Esc or `/stop`; ordinary input queues for the next turn. Failure pauses the queue.
- **Context:** configurable window checks, automatic/manual structured summaries, no silent deletion of the latest turn.
- **Checkpoints:** explicit `/save` and scope-validated `/resume`; no default transcript persistence.
- **Diagnostics:** model settings, execution IDs, metadata ledgers, cumulative known/unknown usage. Unknown price stays unavailable.
- **Examples:** bounded read-only note search and an optional existing evaluation CLI status adapter.

## Requirements and installation

Python **3.13+**, [uv](https://docs.astral.sh/uv/) and macOS or Linux. Windows is not currently supported.
The first backend uses OpenAI Agents SDK 0.22.x with Chat Completions or Responses APIs.
Use your provider's actual model, endpoint and window settings; arbitrary providers are not automatically supported.

From a clone of this repository:

```bash
uv sync --locked --extra dev
uv run --locked agent-entry --help
```

There is no claim of an existing PyPI or GitHub release. To install the local package as a tool:

```bash
uv tool install .
agent-entry --help
```

## Configuration

⚠️ Keep credentials in environment variables. `.env` files and `.agent-entry/` are ignored by Git.
The CLI does **not** automatically load `.env` or execute Python from a configuration file.

```bash
export OPENAI_API_KEY='your-provider-key'
export OPENAI_DEFAULT_MODEL='your-model'
# Optional compatible endpoint:
# export OPENAI_BASE_URL='http://localhost:8000/v1'
```

To configure a project file explicitly:

```bash
uv run --locked agent-entry --project /path/to/project --init
```

Edit the generated `agent-entry.toml` and set its `model`. `--init` refuses to overwrite an existing file.
A file's model overrides environment fallback; `--model` overrides both and survives project switches.
See [agent-entry.example.toml](agent-entry.example.toml) for all settings.
The window is application configuration, not inferred official model capacity.

## Run

```bash
# Interactive pure chat: no business tools registered by default
uv run --locked agent-entry --model your-model

# Read-only knowledge project; this explicitly executes trusted project.py
uv run --locked agent-entry --project examples/knowledge --plugin examples/knowledge/project.py

# One-shot request with explicit response on stdout
uv run --locked agent-entry --model your-model --message 'Explain this project briefly.' --json

# Configuration diagnostics: no model request or credential needed
uv run --locked agent-entry --diagnostics
```

Use `/help` for controls. Enhanced mode supports command completion and Alt+Enter for newline;
`--plain` removes the enhanced editor. `NO_COLOR=1` disables color output.
Plain running input uses `/stop` followed by Enter.

## Add your project

```python
from pathlib import Path
from agent_entry_cli import Project, Tool, run_cli


async def service_health() -> str:
    """Read service health through your existing application API."""
    return "Sample result; connect your application's read-only API here."


raise SystemExit(
    run_cli(
        Project(
            root=Path.cwd(),
            instructions="You are this project's main assistant. Cite tool evidence.",
            tools=(Tool(service_health),),
        )
    )
)
```

For a plugin, expose `build_project(root: Path) -> Project` and pass the file through `--plugin`.
See [integration](docs/integration.md) for policies, local commands and embedding the headless runtime.
The optional [evaluation adapter](examples/eval-harness/README.md) reads Core status only;
formal human review and business execution stay with the original application.

## Repository layout

```text
src/agent_entry_cli/     Public project API, runtime, terminal, context and metadata
examples/knowledge/     Read-only project integration and sample notes
examples/eval-harness/  Optional read-only integration with an existing CLI
tests/                  Deterministic SDK and application regressions
docs/                   Architecture, integration and acceptance evidence
.github/                CI, issue templates and contribution workflow
```

## Development

```bash
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev pyright
uv build
```

Unit tests require no credentials. [CONTRIBUTING.md](CONTRIBUTING.md) describes regression expectations.
CI is configured for macOS/Linux; local acceptance is recorded in [docs/acceptance.md](docs/acceptance.md).
Configured GitHub Actions are not a claim that remote CI has run.

## Limits and security

Plugins are trusted code, not an OS sandbox. Declaring a tool read-only does not prove it.
Async tools must cooperate with cancellation; non-cooperative code can prevent process shutdown.
A persistent terminal loop can display interrupted results and block new model turns while cleanup is pending.

Raw chat is memory-only by default. Explicit summaries use best-effort redaction, not complete DLP.
A restored summary never authorizes a tool or replays a write. Unknown writes require project-side verification.
Usage caps settle after provider responses and can overshoot; they are not a billing guarantee.

Read [SECURITY.md](SECURITY.md) and [architecture](docs/architecture.md) before integrating sensitive tools.
See [CHANGELOG.md](CHANGELOG.md), [third-party notices](docs/third-party.md) and [NOTICE](NOTICE).

## License

[MIT](LICENSE), copyright Alan Hsu. Dependency licenses remain their upstream licenses.
