# Integrate a project

## One explicit local entry point

Create a trusted `project_agent.py` in your own project:

```python
from pathlib import Path
from agent_entry_cli import Project, Tool


def build_project(root: Path) -> Project:
    async def lookup_ticket(ticket_id: str) -> str:
        """Read an authorized ticket from your existing service."""
        # Replace with your service's read-only API; validate user access there.
        return "No ticket backend configured."

    return Project(
        root=root,
        instructions="You are the project's main assistant. Cite tool evidence.",
        tools=(Tool(lookup_ticket),),
    )
```

```bash
agent-entry --project /path/to/project --plugin /path/to/project/project_agent.py
```

Import your business library from the environment where the CLI is installed. Plugins
are not automatically imported from cwd or TOML. `--plugin` executes trusted Python code;
config files never grant permission to execute code. The returned root must match the
explicit selected project.

## Embed without plugin loading

```python
from pathlib import Path
from agent_entry_cli import Project, Tool, run_cli


async def health() -> str:
    """Read a service health result."""
    return "Example health result; replace with your service."


raise SystemExit(run_cli(Project(Path.cwd(), tools=(Tool(health),))))
```

For controlled writes, declare `Tool(fn, side_effect=True)` and provide
`Project(..., authorize=policy)`. A policy receives `ToolCall(root, name, arguments,
side_effect)` and must return exactly `True` to permit a call. It must check real
project authorization and business gates each time. Without a policy, declared read
operations are allowed and writes are denied. A policy can deny reads as well.
Do not use `lambda _: True` in a real application or treat a model's approval as a user grant.

Local custom commands use `commands={"status": callable_returning_text}`. Built-in commands
keep precedence; local commands are invoked by the terminal user and are never queued
from model output. Plugin commands are trusted code too.

## Command reference

| Command | Purpose |
|---|---|
| `/help` | List controls |
| `/context`, `/compact` | Inspect window estimate / summarize explicitly |
| `/save`, `/sessions`, `/resume ID` | Explicit scope-bound summary checkpoints |
| `/model [name]`, `/usage` | Effective settings / known and unknown usage |
| `/clear` | Clear memory context while retaining cumulative usage |
| `/project PATH` | Preflight and switch scope; same explicit plugin is rebuilt |
| `/queue`, `/next`, `/drop` | Inspect, resume paused queue, discard follow-ups |
| `/details` | Last safe execution metadata and ledger path |
| `/quit` | Exit |

During a run, `/stop` cancels and ordinary text queues for the next turn. Slash commands
cannot enter the queue as approvals. Failure/cancellation pauses the queue. Enhanced
mode also uses Esc to stop; plain mode uses `/stop` plus Enter. Follow-ups do not modify
a tool call that has already been issued. Queue limit: 8 items, 40 KB per item.

`--message` is one-shot mode; `--json` returns metadata and the final response to stdout.
That explicit stdout response can contain business content; do not confuse it with the
metadata-only on-disk ledger.
