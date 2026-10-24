# Third-party and source attribution

Project code is MIT; see LICENSE and NOTICE. The conversation/context-summary module
was adapted from the MIT Agent Eval Harness implementation by Alan Hsu. No business
framework code, data or bundled framework help is distributed.

Direct runtime dependencies (not vendored):

| Dependency | Purpose | Upstream license |
|---|---|---|
| openai-agents | Model/tool loop and schemas | MIT |
| prompt-toolkit | Terminal input and completion | BSD-3-Clause |
| Rich | Terminal rendering and safe text output | MIT |

The OpenAI client is a transitive SDK dependency under Apache-2.0. Development tools
include pytest (MIT), Ruff (MIT) and Pyright (MIT). Retain upstream distribution license
metadata. uv.lock records exact resolved packages; dependency inclusion is not a claim
of a completed legal audit of every transitive dependency. No source from Pi, DSH or
Codex is copied or vendored.
