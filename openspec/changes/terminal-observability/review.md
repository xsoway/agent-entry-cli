# 独立缺陷审查与修复记录

审查范围：本变更的全部 DoD、实现、回归和手册；保留先前中文翻译与 terminal-style 工作。独立只读审查由新的审查上下文完成，不读取凭据、不代替主线程验收。

| 分级 | 问题 | 证据与修复 |
|---|---|---|
| P1 | 状态事件提前刷新跨 chunk 脱敏尾串 | 真实 SDK 流回归先复现凭据分片明文，再修正为阶段事件不刷新尾串，仅文本生命周期结束时刷新 |
| P1 | provider finalizer 超时前未完成计量被记为已知零 | 流式／非流式取消回归先失败；显式跟踪未完成计量调用，结算时保留未知并阻止预算内后续请求 |
| P2 | PromptSession 覆盖会话 SIGINT handler | 真实进程在两个增强 prompt 间发 SIGINT，先复现丢失；设置 handle_sigint=False，由终端统一管理，补真实信号取消／重复信号场景 |
| P2 | 项目切换保留旧 scope 的编辑历史 | 失败切换应保留、成功切换应清空的回归先失败；成功切换后重建内存编辑器 |

四项审查发现均已实现并通过针对性 RED→GREEN 验证，最终完整门禁见 docs/terminal-acceptance.md。没有选择延期的 P0/P1/P2 或 minor。

附加检查：工具清理超时但模型最终用量已知时仍保留已知计量；账本故障阻止同批后续工具／模型请求；观察者异常不重放业务操作；摘要仅成功收尾后提交；SDK 继续拥有唯一内层模型／工具循环。

审查边界：本地 macOS 实测及已授权兼容端点的 Chat Completions 流，不推断 Linux 托管 CI、Responses 或其他供应商验收。

主线程反向验收另发现一项 P1：非流式 SDK 外层 gather 取消后，工具 task 的有界 finally 仍在运行，但只等待外层任务会误报清理完成。补充真实调用任务到 _settling 归属；test_tool_only_cleanup_timeout_retains_known_model_usage 先失败后通过，且两项 provider 未知计量回归同时通过。没有通过把所有清理超时一律记未知来掩盖问题。
