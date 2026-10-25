# 🧭 Agent Entry CLI

为现有项目提供主 Agent 终端入口。项目提供说明、异步工具和授权策略，CLI 负责对话、流式输出、上下文、取消、队列和用量。

[官方页（本地预览）](index.html) · [完整中文说明](README.md) · [接入说明](docs/integration.md) · [架构与边界](docs/architecture.md)

## 项目定位

开发这个独立 CLI，是为了让多个 Python 业务项目复用终端、上下文和会话控制，同时保留各自的服务实现与授权规则。项目显式提供异步工具，模型／工具循环复用 OpenAI Agents SDK。

Codex、Pi、OpenCode 和 Claude Code 也有 SDK 或扩展入口；选择本库的主要理由是 Python 业务函数接入和项目授权边界贴合需求。完整的开发初衷、逐工具对比、设计取舍、应用场景与选型建议见[完整中文说明中的定位章节](README.md#为什么开发独立的-agent-cli)。

## 当前能力

- 一个 Python 包，支持 `Project`、`Tool`、`run_cli` 和独立 `Runtime`。
- 显式 `--plugin` 接入可信 Python 项目；TOML 只读取数据，不自动执行代码。
- 流式答复、Esc／`/stop` 停止、下一轮补充队列；失败或取消后队列暂停。
- 窗口检查、自动／手动结构化摘要、显式保存与恢复；不默认保存原始聊天。
- 模型诊断、累计已知消费、未知计量和安全执行元数据；没有价格时显示 unavailable。
- 写工具默认拒绝；授权回调逐次核对项目业务权限。同一响应中存在未知写时也阻断后续工具。

## 本地启动

需要 Python 3.13+、uv 和 macOS/Linux。首版使用 OpenAI Agents SDK 0.22.x，支持对应的 Chat Completions／Responses 接口。Windows 尚未支持。

```bash
uv sync --locked --extra dev
export OPENAI_API_KEY='你的供应商密钥'
export OPENAI_DEFAULT_MODEL='你的模型'
# 可选：export OPENAI_BASE_URL='你的兼容接口地址'
uv run --locked agent-entry
```

当前未声明存在远端 GitHub/PyPI 发布。从本地源码安装工具可运行 `uv tool install .`，不会覆盖原有 `ah` 命令。

⚠️ 凭据仅放环境变量，`.env` 和 `.agent-entry/` 已被 Git 忽略。CLI 不自动读取 `.env`。使用 `--init` 后要在 `agent-entry.toml` 中填写模型名；文件模型优先于环境回退，`--model` 优先于文件。

## 接入你的项目

```python
from pathlib import Path
from agent_entry_cli import Project, Tool, run_cli


async def health() -> str:
    """读取业务服务状态。"""
    return "示例结果，请替换为业务服务调用。"


raise SystemExit(
    run_cli(
        Project(
            root=Path.cwd(),
            instructions="你是项目主助手，回答要引用工具证据。",
            tools=(Tool(health),),
        )
    )
)
```

也可以暴露 `build_project(root) -> Project`，显式传 `--plugin`。示例：

```bash
uv run --locked agent-entry --project examples/knowledge --plugin examples/knowledge/project.py
```

询问 notes 中的部署时间，工具会返回文件及行号。评测框架示例仅通过已安装的 `agent-eval` 读取状态，不搬入 Core、不代签审批、不执行评测。

## 常用命令

| 命令 | 功能 |
|---|---|
| `/context`、`/compact` | 窗口估计与手动摘要 |
| `/save`、`/sessions`、`/resume ID` | 显式保存与恢复摘要 |
| `/model [name]`、`/usage` | 模型、协议、累计已知／未知用量 |
| `/clear` | 清空短期上下文，保留累计消费 |
| `/project PATH` | 预检后切换项目，隔离上下文 |
| `/queue`、`/next`、`/drop` | 查看、继续或清空补充队列 |
| `/details` | 执行状态、清理结果与账本路径 |
| `/quit` | 退出 |

运行中普通文字进入下一轮，控制命令不能排队成为授权。增强模式 Esc 停止；plain 模式 `/stop` 加回车停止。`--plain` 和 `NO_COLOR=1` 可调整终端显示。

## 边界

插件和工具是可信本地代码，不是沙箱；声明 read-only 不构成权限隔离。异步工具必须配合取消，不配合的代码可能阻止进程退出。摘要不能授权、不能解除未知写，也不能代替业务检查。

窗口是应用配置，字节估计不是供应商 tokenizer。累计上限在响应后结算，可能超额，不是账户预付费保证。默认只记执行元数据；显式保存的摘要仍需判断业务事实是否适合持久化。

开发检查、目录结构和贡献方式见 [README](README.md)、[CONTRIBUTING](CONTRIBUTING.md)。验收事实见 [docs/acceptance.md](docs/acceptance.md)。许可证为 [MIT](LICENSE)。

终端快捷键、执行阶段、实时上下文与错误处理见[终端操作手册](docs/terminal.md)。

官方页的双语交互、本地验收与待部署状态见[发布说明](docs/releasing.md)。
