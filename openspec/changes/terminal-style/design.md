## Decision
Keep PromptSession and its existing key bindings. Add formatted prompts, toolbar and theme; use Rich panels for startup, user and execution results. Keep streaming incremental, sanitized literal Text. Plain mode bypasses panels. NO_COLOR removes all color styles.

## Verification
Sanitization and dynamic-state tests, existing cancel/queue tests, real PTY at wide/narrow widths and plain/NO_COLOR modes, then project quality gates.
