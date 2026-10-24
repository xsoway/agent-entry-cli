# Independent project agent CLI

## Why
Provide an independently installable, small main-agent terminal reusable by different projects.

## What Changes
One Python package, a Project/Tool API, explicit trusted plugin loading, a default SDK backend, stream/stop/follow-up, bounded context/summary, explicit scope-safe summary restore, usage diagnostics and metadata events. Include knowledge-search and existing evaluation CLI read-only examples. MIT, CI, contributor/security docs, tests and standalone wheel acceptance.

## Capabilities

### New Capabilities
- `project-entry`: Independent terminal, project tools, context and safe runtime lifecycle.

### Modified Capabilities
None.

## Impact
No dependency on agent_eval_harness, no shell tool by default, no auto-discovered plugin execution, no framework approvals, no remote publication. Existing ah remains unchanged. Python 3.13 and current SDK are deliberate initial compatibility limits.
