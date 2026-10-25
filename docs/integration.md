# 集成项目

本页说明如何把现有业务接入终端，以及如何在自有服务中复用运行时。整体流程图与最小插件见 [README](../README.md#接入你的项目)。

## 接入前先准备什么？

- 业务项目使用 Python 3.13+，有独立的 uv 环境；通过 `uv add /absolute/path/to/agent-entry-cli` 安装本地源码包，或安装经过验证的构建产物。当前不假定已有 PyPI 发布版。
- 模型名、API 类型、兼容端点和窗口配置已确认；凭据通过环境变量提供，CLI 不会自动加载 `.env`。
- 先选一个有明确范围的只读服务，确认调用者身份、数据访问权限、超时和取消行为。插件进程内共享宿主权限，不构成沙箱。
- 确认业务库可从运行 CLI 的同一环境导入；不要依赖当前目录自动执行插件。

## 一个显式的本地入口

在自己的项目中创建可信的 `project_agent.py`：

```python
from pathlib import Path
from agent_entry_cli import Project, Tool


def build_project(root: Path) -> Project:
    async def lookup_ticket(ticket_id: str) -> str:
        """从现有服务中读取已获授权的工单。"""
        # 替换为服务的只读 API，并在服务端验证用户访问权限。
        return "尚未配置工单后端。"

    return Project(
        root=root,
        instructions="你是项目的主助手。请引用工具证据。",
        tools=(Tool(lookup_ticket),),
    )
```

```bash
agent-entry --project /path/to/project --plugin /path/to/project/project_agent.py
```

从安装 CLI 的环境中导入业务库。插件不会从当前工作目录或 TOML 中自动导入。
`--plugin` 会执行可信的 Python 代码；配置文件不会授予代码执行权限。
返回的根目录必须与显式选择的项目一致。

## 不加载插件的嵌入方式

```python
from pathlib import Path
from agent_entry_cli import Project, Tool, run_cli


async def health() -> str:
    """读取服务健康检查结果。"""
    return "示例健康检查结果；请替换为自己的服务。"


raise SystemExit(run_cli(Project(Path.cwd(), tools=(Tool(health),))))
```

对于受控写操作，声明 `Tool(fn, side_effect=True)`，并提供 `Project(..., authorize=policy)`。
策略接收 `ToolCall(root, name, arguments, side_effect)`，只有返回值严格为 `True` 才允许调用。
每次调用都必须检查真实的项目授权和业务准入条件。不提供策略时，已声明的读操作可以执行，写操作被拒绝。
策略也可以拒绝读操作。不要在真实应用中使用 `lambda _: True`，也不要把模型的同意视为用户授权。

本地自定义命令通过 `commands={"project-info": callable_returning_text}` 配置。
内置命令保持优先级；本地命令由终端用户调用，模型输出中的命令永远不会进入队列。
插件命令同样属于可信代码。

## 接入受控写操作

`authorize` 必须是同步回调，接收 `ToolCall`；工具必须是具名异步函数。策略只有返回值严格为 `True` 才允许，异常也会拒绝。工具名必须唯一，符合 `[A-Za-z_][A-Za-z0-9_]{0,63}`。

建议按下面的顺序开放写能力：

1. 先保持写工具默认拒绝，验证模型无法自行获得授权。
2. 在项目中实现策略：基于可信的当前用户身份、目标资源、动作与有效的业务审批检查本次调用。`call.arguments` 用于核对目标和参数，不能作为授权来源。
3. 将工具注册为 `Tool(write_function, side_effect=True)`，并在 `Project` 中传入 `authorize=policy`。异步鉴权应放在实际业务服务中执行；不要在同步回调里阻塞等待网络。
4. 在真实写服务中再次执行权限校验，使用项目自己的幂等键，明确超时、取消和结果不确定时的查询方式。
5. 在隔离环境验证“拒绝／允许／过期／重复／取消中写入”场景，再开放实际业务。

策略存在时也会检查读工具，必须明确允许所需的读调用。恢复摘要、模型答复、终端排队消息都不能替代授权；写结果不确定时，先查询外部状态，再由项目决定后续操作。

## 无界面嵌入：复用运行时

以下示例从环境变量获取实际模型设置，不经过终端。它会向模型发出真实请求并把答复输出到标准输出，需要凭据；请先在测试环境运行：

```python
import asyncio
import os
from collections import Counter
from pathlib import Path

from agent_entry_cli import Config, Project, Runtime


def observe(event: dict[str, object]) -> None:
    # 只统计事件类型；导出到外部平台时使用有界队列与独立 worker。
    event_counts[str(event.get("event", "unknown"))] += 1


event_counts: Counter[str] = Counter()


async def main() -> None:
    settings = Config(
        model=os.environ["OPENAI_DEFAULT_MODEL"],
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api="chat_completions",
    )
    runtime = Runtime(Project(root=Path.cwd()), settings)
    result = await runtime.run("简要说明你能做什么。", on_event=observe)
    print(result.status, result.reason, result.execution_id)
    if result.output is not None:
        print(result.output)
    if not result.cleanup_complete or result.pending_writes:
        raise RuntimeError("先完成清理并核实写操作，再接收下一次请求")


if __name__ == "__main__":
    asyncio.run(main())
```

示例只统计事件类型，不保存每条事件。长期服务导出时使用有界队列，避免无限积累。`on_event` 是同步、快速回调；普通回调异常会关闭本轮观察者，不触发业务重试。回调接收安全元数据副本，不提供原始提示、工具参数／结果或私有推理文本。终端只显示推理阶段及可用事件类型。

一个 `Runtime` 对应一个隔离会话，同一实例串行调用；不同用户不要共享其对话对象。宿主收到停止请求时调用 `runtime.cancel()`，随后等待正在执行的 `run()` 返回并检查清理状态。不要在外面再实现一套模型／工具循环。SDK 模型注入接口适合受信任的集成与测试，不代表任意供应商已适配。

## 扩展时需要守住的契约

| 扩展位置 | 使用方式 | 验证重点 |
|---|---|---|
| 业务工具 | 具名 `async def`，清晰类型与 docstring，返回精简且可核对的结果 | 输入边界、越权、异常、结果体积、取消协作；避免把同步阻塞 I/O 直接放进事件循环 |
| 本地命令 | `commands={"project-info": callable_returning_text}`；同步无参数，返回字符串 | 名称符合 `[a-z][a-z0-9_-]{0,31}`；避开 `/status` 等内置命令；命令不是写工具授权入口 |
| 观测导出 | 用执行 ID 关联 `on_event` 与项目自己的业务审计 | 导出失败不阻塞工具；限流、脱敏、队列容量和丢弃策略；接入外部平台需另行实现 |
| 模型服务 | 选择当前支持的 `chat_completions` 或 `responses` | 实际端点的流输出、工具 schema、停止与清理、缺失用量；不能用本地协议测试代替真实端点验收 |
| 上下文 | 配置窗口、输出与系统预留，使用 `/context`、`/compact` | 指令与工具 schema 的占用；估算不是供应商 tokenizer；最新请求不能静默丢弃 |
| 摘要恢复 | 用户显式 `/save`，恢复时校验项目作用域 | 仅保存摘要，不是完整记录；不继承授权、不自动重放写操作 |

需要 MCP 时，可在项目适配层把经过信任与权限校验的远端操作包装成工具，但还需自行实现客户端生命周期、超时、取消、结果限制与错误转换。需要 Skills 或多 Agent 时，应先定义加载信任和调度边界、总预算及取消传播，再增加适配层；这些能力当前均未内置。新后端如需修改库内部，应先补兼容测试，保留 SDK 唯一循环与清理归属，避免绕过现有门禁。

## 如何验收一次接入？

| 阶段 | 执行动作 | 通过依据 |
|---|---|---|
| 本地装配 | `--diagnostics`、`/tools`、`/project-info`、`/context` | 根目录、模型配置、工具和本地命令符合预期；此阶段不能证明模型可用 |
| 真实模型 | 请求调用只读工具并引用结果 | 工具实际被调用，答复可由业务源核对；检查执行状态与已知／未知用量 |
| 生命周期 | 在模型输出与工具执行期间分别停止 | `run()` 收尾完成；无残留请求；新轮次遵守清理状态 |
| 权限与写入 | 隔离环境覆盖拒绝、允许、过期及不确定结果 | 每次调用都检查业务权限，不自动重放，外部状态可核实 |
| 会话与隐私 | 分别切换项目、保存／恢复摘要、检查元数据账本 | 作用域隔离；恢复不授权；默认账本不含业务正文、参数与私有推理 |

先通过项目自身的业务回归，再运行本库的[开发检查](../README.md#开发检查)。两者分别证明业务结果和库的基础行为。真实端点、业务权限及外部平台的验收需记录各自环境与结果，不能由单元测试推断。

## 命令参考

| 命令 | 用途 |
|---|---|
| `/help` | 列出内置及项目命令 |
| `/context`, `/compact` | 查看上下文窗口估算／显式生成摘要 |
| `/save`, `/sessions`, `/resume ID`、`/resume latest` | 显式保存、查看和恢复绑定作用域的摘要检查点 |
| `/model [name]`, `/usage` | 查看生效配置／已知与未知用量 |
| `/clear` | 清空内存上下文，保留累计用量 |
| `/project PATH` | 预检并切换作用域；重新构建同一个显式指定的插件 |
| `/queue`, `/next`, `/drop` | 查看队列、恢复暂停的队列、丢弃后续消息 |
| `/details` | 查看最近一次安全的执行元数据和台账路径 |
| `/tools`, `/status` | 工具与授权声明、当前阶段和耗时 |
| `/stop` | 取消当前执行，等待清理 |
| `/quit`, `/exit` | 退出；运行中先取消并等待清理 |

执行过程中，`/stop` 会取消执行，普通文本则排队等待下一轮。斜杠命令不能作为授权进入队列。
失败或取消会暂停队列。增强模式也支持按 Esc 停止；普通模式使用 `/stop` 加回车。
后续消息不会修改已经发出的工具调用。队列上限为 8 条，每条 40 KB。

`--message` 为单次执行模式；`--json` 会将元数据和最终响应输出到 stdout。
这种显式输出到 stdout 的响应可能包含业务内容，不应与磁盘上仅含元数据的台账混淆。

实时元数据回调 `Runtime.run(..., on_event=callback)`、快捷键及错误处理见[终端操作手册](terminal.md)。
