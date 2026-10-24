# Security

This alpha release runs explicitly selected local project code in the same Python
process. A plugin is trusted code with the user's filesystem and network permissions;
`Tool(side_effect=False)` is a declaration, not a sandbox or static proof of read-only behavior.
Only load plugins and tools you trust. No shell tool is enabled by default.

Each declared side-effect tool requires a synchronous project authorization callback.
That callback must verify application authorization and relevant business state on every
invocation. A conversation, restored summary or model statement never grants approval.
Unknown writes are not automatically retried; verify external state through your project.

Metadata logs omit raw prompts, outputs, tool inputs/results and exception bodies.
Explicit `/save` generates a best-effort redacted summary; inspect the suitability of
business facts for persistence. Redaction is not a complete data-loss-prevention system.

To report vulnerabilities, use the repository's private security advisory channel if
available or contact its maintainer privately through an established channel. Do not
post active credentials or confidential reproduction data in public issues.
Supported security fixes initially target the current 0.1.x release only.
