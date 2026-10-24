# Optional evaluation framework integration

This adapter calls an **already installed** `agent-eval` executable through PATH.
The independent CLI package does not install or import the evaluation framework.
Pass an existing evaluation workspace as `--project`:

```bash
uv run --locked agent-entry --project /path/to/evaluation-workspace --plugin examples/eval-harness/project.py
```

The only tool is `workflow_status`: fixed argv `agent-eval status <root> --format json`.
There is no shell interpolation, dataset release, approval or evaluation execution.
The old framework's human review and business gates remain authoritative.
The executable and workspace are trusted local dependencies. This example does
not attest a real evaluation Target, Golden release or Judge run.
