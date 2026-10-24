# Project Entry

## ADDED Requirements

### Requirement: Independent installation
The CLI SHALL run from a wheel outside the source checkout without agent_eval_harness.
#### Scenario: Unrelated working directory
- WHEN installed wheel starts in a fresh directory
- THEN help, init and an SDK turn work without the old repository.

### Requirement: Project integration
Trusted async tools SHALL be registered explicitly and side effects SHALL be denied without a per-call project policy. Config SHALL NOT execute Python implicitly.
#### Scenario: Read-only project
- WHEN a knowledge project registers a search tool
- THEN the real SDK calls it, with scope/size constraints enforced by the example.

### Requirement: Conversation lifecycle
The CLI SHALL support streams, stop, bounded follow-up, window admission, atomic summaries, explicit safe scope-bound restore and known/unknown cumulative usage.
#### Scenario: Interrupted stream
- WHEN the user stops a delayed response
- THEN runtime waits for cleanup, records cancelled or interrupted, and pauses follow-ups.

### Requirement: Open-source repository
The repository SHALL contain license, attribution, reproducible lockfile, contribution/security docs, CI, examples and executable tests. It SHALL NOT include credentials or claim a remote release exists.
#### Scenario: Repository check
- WHEN deterministic gates, isolated wheel and real PTY are exercised
- THEN evidence records observed results and exact unexecuted gates.
