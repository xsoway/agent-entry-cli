# 第三方依赖与来源说明

项目代码使用 MIT 许可证，参见 LICENSE 和 NOTICE。对话与上下文摘要模块改编自 Alan Hsu
编写的 MIT 许可 Agent Eval Harness 实现。本项目不分发业务框架代码、数据或捆绑的框架帮助内容。

直接运行时依赖（未将其源码内置到本仓库）：

| 依赖 | 用途 | 上游许可证 |
|---|---|---|
| openai-agents | 模型与工具循环及 schema | MIT |
| prompt-toolkit | 终端输入与补全 | BSD-3-Clause |
| Rich | 终端渲染与安全文本输出 | MIT |

OpenAI 客户端是 SDK 的传递依赖，使用 Apache-2.0 许可证。开发工具包括 pytest（MIT）、
Ruff（MIT）和 Pyright（MIT）。应保留上游发行包的许可证元数据。
uv.lock 记录了精确解析的依赖包；纳入依赖并不表示已经完成对所有传递依赖的法律审计。
本项目没有复制或内置 Pi、DSH 或 Codex 的源码。
