# Acceptance — 2026-10-24

Local implementation acceptance passed on macOS with Python 3.13.15.
The repository is an alpha source release prepared locally; no remote release is implied.

## Deterministic gates

| Gate | Observed result |
|---|---|
| `uv sync --locked --extra dev` | Independent project environment created; no copied/shared venv |
| `uv run --locked --extra dev pytest -q` | **39 passed in 3.64s** |
| `uv run --locked --extra dev ruff check .` | All checks passed |
| `uv run --locked --extra dev ruff format --check .` | 37 files already formatted, including Markdown examples |
| `uv run --locked --extra dev pyright` | 0 errors, 0 warnings |
| `uv build` | Wheel and source distribution built |
| `uv run --locked --extra dev python scripts/verify_distribution.py` | Independent wheel installation/import, init and diagnostics passed |
| OpenSpec initial-cli strict validation | Valid |
| Workspace agent inheritance audit | Passed; standalone checkout does not require absent parent workspace files |

Tests use the real SDK with deterministic model providers. They verify contracts and
failure behavior; they are not live-provider or business-evaluation evidence.

## Runtime acceptance

A wheel was installed into a separate uv environment outside the source checkout.
Its Python imports resolve from that environment and cannot import the old evaluation
framework. With the existing authorized model environment, the installed wheel passed:

- Real `sglang-deepseek-v4-flash` Chat Completions streaming and positive provider usage.
- Real registered `search_notes` tool reading sample notes and returning file:line references.
- Explicit summary save, clear, restore and recall of the sample code/language constraint.
- Restart into a new process, restore the same scoped summary and recall the constraint.
- Plain PTY `/stop`, next-turn input queue, pause on cancellation and explicit queue clearing.
- Enhanced PTY command completion and Esc cancellation; NO_COLOR completion/diagnostics.
- Metadata readback: no sample chat markers, settled cleanup, no pending writes, real known
  consumption retained and missing cancellation usage kept unknown.

One provider summary attempt did not satisfy the fixed schema. It was rejected without
mutating history; a later explicit save succeeded. No tool or write was retried as a result.
Early PTY harness assertions were corrected for output segmentation and prompt-control
sequences, then the final scenarios passed. They were not reported as product success.

The optional evaluation adapter was checked against the current installed `agent-eval
status <workspace> --format json` command on an isolated existing sample workspace. It
returned real Core status and left the project definition unchanged. No approvals,
Golden release, Target, Judge or evaluation runs were requested.

## Defect-focused review

An independent read-only review identified budget settlement, same-response unknown-write
blocking, startup model override and per-turn event-loop lifetime issues. Regression tests
first failed and then passed after fixes. A dispatch lock now serializes tool calls and
checks unknown writes and token budget before each invocation. The terminal retains one
loop and refuses new model turns while previous cleanup is pending.

The implementation pass additionally verified headless control-sequence filtering,
iterator finalizers, safe fixed failure reasons, the actual evaluation CLI contract and
subprocess startup cancellation. Each reproducible defect has a regression. The final
focused source pass found no unresolved release-blocking P0/P1/P2 in the delivered scope.

## Limits and unexecuted gates

- GitHub repository creation, hosted Actions and PyPI publication were not executed.
- Linux CI is configured, but this local acceptance ran on macOS. Windows is unsupported.
- The real provider test used Chat Completions; Responses and other vendors need their own
  real endpoint acceptance before claiming compatibility.
- Plugins are trusted local async code, not a sandbox. Non-cooperative code can still
  prevent process shutdown. A cleanup timeout is not proof that external work was undone.
- Summary redaction is best effort. Checkpoints restore historical usage snapshots,
  not provider-account billing state. No price or prepaid spending guarantee is claimed.
- The old `ah` command is unchanged. The independent command is `agent-entry`; migration
  of the old terminal to depend on this package is a separate change.

Raw local PTY evidence and execution receipts remain in the workspace's archived task
record, outside this public repository. They are intentionally not bundled in distributions.
