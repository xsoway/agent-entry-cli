# Read-only knowledge assistant

Run from the repository root after setting model/credential environment variables:

```bash
uv run --locked agent-entry --project examples/knowledge --plugin examples/knowledge/project.py
```

Ask: `Find the deployment window in the notes and cite the file and line.`

`search_notes` reads only direct `notes/*.md` children, skips symlinks and files
larger than 32 KiB, scans at most 100 files, and returns at most 20 matching lines.
It performs no writes. Filesystem checks assume trusted local code and no hostile
concurrent filesystem mutation; they do not establish an OS sandbox.
