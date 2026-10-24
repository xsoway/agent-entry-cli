# Contributing

Start with an issue describing an observable problem and a small proposed change.
For a bug, add the smallest failing regression before fixing it. Keep runtime and
project code separate; no imports from a specific application's Core in the package.

## Development

Python 3.13+ and uv are required. From the repository root:

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev pyright
uv build
```

Tests use the real SDK with deterministic provider doubles and need no API key.
For real-model testing, use environment credentials and an isolated project directory.
Never commit model keys, raw private conversations or real project business data.
Do not weaken cancellation, usage, scope or unknown-write regressions to pass a gate.

Please include the problem, resulting behavior, relevant test output and compatibility
impact in a pull request. Update docs when changing public APIs or command semantics.
New Python files retain the project header format used in source files.
