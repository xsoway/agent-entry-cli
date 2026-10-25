# 独立 CLI 实施计划

> **面向 Agent 执行者：**使用 executing-plans 在当前会话中实施。步骤采用复选框语法。

**目标：**提供独立、可安装的主 Agent CLI，配备小型项目 API，并使仓库具备托管到 GitHub 的条件。
**架构：**项目/工具 → 共享 SDK 运行时 → 终端。元数据与摘要分开存储。不导入旧框架。
**技术栈：**Python 3.13、uv、OpenAI Agents SDK、prompt-toolkit、Rich、pytest、Ruff、Pyright。
**规范：**openspec/changes/initial-cli/specs/project-entry/spec.md

## 全局约束
Python >=3.13。不记录凭据或原始对话日志。仅显式加载可信插件。默认拒绝有副作用的操作。不向 GitHub 发布。

## 审查重点
- 在模型或工具清理期间取消，不得错误报告清理完成。
- 超大或恶意摘要不得替换当前历史。
- 工作目录变更和已安装的示例不得依赖源码检出目录。
- 插件或策略错误不得泄露任意异常正文，也不得授予写入权限。
- 取消后缺失的用量不得被当作零，也不得随 /clear 重置。

### 任务 1：项目、配置与对话契约
文件：config.py、project.py、privacy.py、conversation.py、storage.py、tests/test_state.py。
接口：Config、Project(root,instructions,tools,authorize)、Tool、Conversation、SummaryStore。
- [x] 编写真实行为测试，运行 RED，实现最小模块，再运行 GREEN。

### 任务 2：SDK 生命周期
文件：runtime.py、events.py、tests/test_runtime.py。
接口：Runtime(project,config,conversation,model=None).run(request,on_text=None)、cancel()、Result。
- [x] 使用脚本化的提供方响应测试真实 SDK：工具与策略、流式输出、预算、摘要、回调错误及延迟清理；RED→GREEN。

### 任务 3：终端与示例
文件：terminal.py、cli.py、examples/、tests/test_cli.py。
接口：run_cli(Project)、build_project(root) 插件、agent-entry 命令。
- [x] 对 init、显式插件、诊断、保存与恢复、队列控制及启动错误执行 RED→GREEN。
- [x] 知识示例和只读评测示例；真实 PTY 与模型验收。

### 任务 4：仓库交付
文件：README、README.zh-CN、docs/、LICENSE、NOTICE、.github/、uv.lock。
- [x] 记录实际行为和限制，提供 CI 与模板。运行全量测试、lint、类型、构建及隔离环境 wheel 验收。
- [x] 重新进行以缺陷为先的审查；修复问题并运行受影响的验收项。仅初始化本地 Git，不推送、不发布。
