# 终端交互与可观测性验收 — 2026-10-24

本记录对应 `terminal-observability`，与原始版本的[历史验收记录](acceptance.md)分开保存。

## 交付范围

- 空闲 Ctrl+C / Ctrl+D 退出；运行中第一次取消、再次请求清理后退出；`/quit`、`/exit` 和真实 SIGINT 行为一致。
- 普通模式采用可取消的异步行输入；增强模式保留主题、补全、多行输入，并显示动态状态和耗时。
- 中文帮助与固定安全原因码；`/tools`、`/status`、项目命令发现和斜杠前缀补全。
- 带保存时间与预览的摘要列表、`/resume latest`、旧检查点兼容和项目输入历史隔离。
- 模型／工具／摘要／清理的安全元数据；执行 ID、循环次数、上下文和已知／未知用量。
- 指令与 schema 纳入自动压缩阈值；账本故障阻断后续调用；真实工具任务纳入清理归属。

## 最终门禁

| 命令或场景 | 实测结果 |
|---|---|
| `uv sync --locked --extra dev` | 锁定环境检查通过，未新增依赖 |
| `uv run --locked --extra dev pytest -q` | **86 passed in 66.32s**，无警告 |
| `uv run --locked --extra dev ruff check .` | All checks passed |
| `uv run --locked --extra dev ruff format --check .` | 通过 |
| `uv run --locked --extra dev pyright` | 0 errors，0 warnings |
| `uv build` | 最终 wheel / sdist 构建通过 |
| `uv run --locked --extra dev python scripts/verify_distribution.py` | 独立 wheel 安装、导入、init、diagnostics 通过 |
| `openspec validate terminal-observability --strict` | 通过 |
| 中文文档链接与 Python 示例编译、`git diff --check` | 通过 |

测试包括真实 PTY 的增强／普通、窄屏／宽屏、NO_COLOR、键盘控制与 `os.kill(SIGINT)`，并使用真实 SDK 的确定性模型验证工具循环。PTY 测试改用先 exec 新解释器再取得控制终端的方式，避免 Python 3.13 多线程 fork 警告。

## 真实端点验收

在现有已授权兼容端点上，从模型列表确认 `sglang-deepseek-v4-flash`；只在临时目录选择该模型，不修改项目配置。最终源码通过：

- Chat Completions 流式公开答复，以及固定只读 `check_status` 工具。
- 两次模型调用、工具完成、公开状态标记与清理完成；供应商返回 **714** 个已知 token。
- 有执行 ID 与耗时的固定元数据观察，无原始 SDK 推理或工具载荷字段。
- 真实模型生成结构化摘要、显式保存、同作用域恢复，以及保存时间／预览读取。

工具仅返回固定验收标记，不代表任何业务系统验收。原始答复和凭据未写入本仓库。临时项目及执行记录随测试清理。

## 独立审查与额外回归

[审查记录](../openspec/changes/terminal-observability/review.md)记录了独立发现的四项问题及主线程进一步发现的工具清理归属问题。均以失败回归复现后修复：

1. 阶段事件不得提前刷新分片凭据的脱敏尾串。
2. provider finalizer 未结束时缺失的最终计量保持未知；设置预算时阻止后续请求。
3. PromptSession 不接管会话 SIGINT，增强 prompt 间隙与清理期间的信号仍受控。
4. 项目切换成功清空旧输入历史，失败保留当前会话。
5. SDK 外层取消不等于工具 task 已清理；仅工具清理超时而模型计量完整时，保留已知用量。

另已保留和验证未知写、逐次授权、流所有权、摘要原子提交、账本故障与观察者故障的回归。最终修复差异经缺陷导向复核，无选择延期的 P0/P1/P2。

## 限制与回滚

本次实测为 macOS、Python 3.13.15、当前锁定 SDK 和上述 Chat Completions 端点。未执行托管 Linux CI、Responses 真实端点或其他供应商验收；未发布或部署。

可信插件仍需配合取消；CLI 不能强制终止任意本地 Python 代码。摘要仅显式保存，计量上限不是账户预付保证。实时阶段不展示私有思考链。

回滚只需撤销本变更的源文件、测试与手册增量，保留先前中文翻译和 terminal-style 样式工作；没有数据迁移或配置格式迁移，也没有外部业务写入需要回滚。
