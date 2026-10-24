# Independent CLI Implementation Plan

> **For agentic workers:** implement inline using executing-plans. Steps use checkbox syntax.

**Goal:** An independent, installable main-agent CLI with a small project API and GitHub-ready repository.
**Architecture:** Project/tools → shared SDK runtime → terminal. Metadata and summary storage are separate. No old framework imports.
**Tech Stack:** Python 3.13, uv, OpenAI Agents SDK, prompt-toolkit, Rich, pytest, Ruff, Pyright.
**Spec:** openspec/changes/initial-cli/specs/project-entry/spec.md

## Global Constraints
Python >=3.13. No credential or raw conversation logs. Explicit trusted plugins only. Side effects default deny. No GitHub publication.

## Review Focus
- Cancellation during model/tool cleanup must not report false cleanup.
- Oversized/malicious summaries must not replace active history.
- Working-directory changes and installed examples must not depend on the source checkout.
- Plugin/policy errors must not leak arbitrary exception bodies or grant writes.
- Missing usage after cancellation must not become zero or reset with /clear.

### Task 1: Project/config/conversation contracts
Files: config.py, project.py, privacy.py, conversation.py, storage.py, tests/test_state.py.
Interfaces: Config, Project(root,instructions,tools,authorize), Tool, Conversation, SummaryStore.
- [x] Write real behavior tests, run RED, implement minimal modules, run GREEN.

### Task 2: SDK lifecycle
Files: runtime.py, events.py, tests/test_runtime.py.
Interfaces: Runtime(project,config,conversation,model=None).run(request,on_text=None), cancel(), Result.
- [x] Test real SDK with scripted provider responses: tools/policy, stream, budgets, summary, callback errors and delayed cleanup; RED→GREEN.

### Task 3: Terminal and examples
Files: terminal.py, cli.py, examples/, tests/test_cli.py.
Interfaces: run_cli(Project), build_project(root) plugin, command agent-entry.
- [x] RED→GREEN for init, explicit plugins, diagnostics, save/restore, queue controls and startup errors.
- [x] Knowledge and read-only eval examples; real PTY and model acceptance.

### Task 4: Repository delivery
Files: README, README.zh-CN, docs/, LICENSE, NOTICE, .github/, uv.lock.
- [x] Document actual behavior and limitations, CI and templates. Run full tests/lint/types/build and isolated wheel acceptance.
- [x] Fresh defect-first review; repair and run affected gates. Initialize local Git only; no push or publication.
