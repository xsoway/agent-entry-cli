# 项目入口

## ADDED Requirements

### Requirement: 独立安装
CLI SHALL 能够在源码检出目录之外，从 wheel 运行，且无需 agent_eval_harness。
#### Scenario: 无关工作目录
- WHEN 已安装的 wheel 在全新目录中启动
- THEN help、init 和一次 SDK 对话轮次均可在不依赖旧仓库的情况下运行。

### Requirement: 项目集成
可信异步工具 SHALL 显式注册；没有逐次调用的项目策略时，副作用 SHALL 被拒绝。配置 SHALL NOT 隐式执行 Python。
#### Scenario: 只读项目
- WHEN 知识项目注册检索工具
- THEN 真实 SDK 调用该工具，且示例强制执行作用域和大小限制。

### Requirement: 对话生命周期
CLI SHALL 支持流式输出、停止、有界后续输入、窗口准入、原子摘要、显式且安全的作用域绑定恢复，以及已知与未知的累计用量。
#### Scenario: 中断流式输出
- WHEN 用户停止一个延迟响应
- THEN 运行时等待清理，记录 cancelled 或 interrupted，并暂停后续输入。

### Requirement: 开源仓库
仓库 SHALL 包含许可证、署名、可复现的锁文件、贡献与安全文档、CI、示例和可执行测试。仓库 SHALL NOT 包含凭据，也不得声称远程发布已存在。
#### Scenario: 仓库检查
- WHEN 执行确定性检查、隔离环境 wheel 验收和真实 PTY 验收
- THEN 证据记录观察到的结果及确切未执行的验收项。
