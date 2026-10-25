# Agent Entry CLI 开发约定

<!-- code_project: parent-agents-required -->

在本工作区内，依次读取 `../../../AGENTS.md`、`../../AGENTS.md`，再读取本文件。
独立克隆时遵循以下规则；不要求读取不存在的父级文件。

规划前使用 Karpathy guidelines；实现时使用可用的 engineering-acceptance-harness 和 autonomous-loop。保留已有工作，保持本库独立于 agent-eval-harness。

使用 Python 3.13+、`uv sync --locked --extra dev` 和项目内的 `.venv`。
交付前运行 `uv run --locked --extra dev pytest -q`、`ruff check .`、`pyright` 和 `uv build`。
新建 Python 文件必须包含编码、创建时间、文件名和作者头信息。

项目适配器是可信本地代码，不是沙箱。禁止自动导入项目插件。
默认不记录原始消息、工具参数、工具结果、凭据或私有推理。
仅显式执行 `/save` 才持久化摘要；恢复的摘要不能授予工具调用权限。
有副作用的工具每次调用都必须经过项目授权回调。禁止自动重放写操作。
保留流清理归属、用量不完整和项目作用域隔离的回归测试。
