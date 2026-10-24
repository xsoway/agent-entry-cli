# Design

Project supplies root, instructions, async tools and an optional per-call authorization callback. Tool metadata marks side effects; default denies side effects. Explicit --plugin loads a trusted local build_project(root) function, otherwise no project code executes. Config is TOML data only.

SDK owns model/tool loop; Runtime owns context admission, timeout, cancellation settlement, per-execution known/unknown usage, and metadata-only records. SDK client disables transport retries; write tools are never retried by this library. Summary requests have no tools and use the same budget. Conversation mutation commits after success and cleanup only.

Terminal owns local controls and a bounded next-turn queue. Streaming and input run in one event loop. Consumer is shielded; SDK alone cancels its run loop; the iterator and SDK tasks settle before a terminal result. Non-cooperative plugin cleanup yields interrupted rather than claiming cancellation succeeded.

Summary files are immutable UUID, schema/scope validated, restrictive permissions and no original messages or grants. Read-only knowledge example constrains paths, sizes and symlinks. Evaluation example invokes only agent-eval status using a fixed argument list; old Core retains business state and approvals.
