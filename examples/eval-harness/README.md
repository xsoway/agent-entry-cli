# 可选的评测框架接入

此适配器通过 PATH 调用**已经安装**的 `agent-eval` 可执行程序。
独立 CLI 包不会安装或导入评测框架。
通过 `--project` 传入已有的评测工作区：

```bash
uv run --locked agent-entry --project /path/to/evaluation-workspace --plugin examples/eval-harness/project.py
```

唯一工具是 `workflow_status`，固定参数为 `agent-eval status <root> --format json`。
不使用 shell 插值，也不发布数据集、代为审批或执行评测。
原框架的人工审核和业务门禁仍然有效，并具有最终约束力。
可执行程序和工作区均属于可信本地依赖。
本示例不证明已完成真实评测 Target、Golden 发布或 Judge 运行。
