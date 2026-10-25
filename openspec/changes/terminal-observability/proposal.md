## Why

终端基本操作存在已复现的退出和可发现性缺陷，执行中的模型、工具、上下文收尾状态缺少可见反馈。需要让使用者知道执行到了哪里、为何失败、如何恢复。

## What Changes

- 修复增强与普通模式 Ctrl+C；运行中第一次取消，第二次请求退出并等待已有清理；支持 /quit、/exit 运行中退出。
- 中文化终端帮助、状态和安全错误提示；完善项目命令、/stop、/tools 的发现和补全。
- 展示元数据级模型循环、工具状态、摘要、上下文、预算、耗时、取消与清理；不显示或存储私有推理、工具参数与结果。
- /sessions 按保存时间排列并显示时间与已保存摘要预览，支持 /resume latest。
- 保留现有隐私、授权、未知写、未知用量、流清理归属与 SDK 单一循环契约。

## Capabilities

### New Capabilities
- `terminal-observability`: 安全、可操作的交互式终端与运行时执行元数据展示。

### Modified Capabilities
无。

## Impact

修改 terminal、runtime、events、storage、cli 以及中文文档；新增轻量提示和输入辅助模块及回归测试。不添加依赖，不发布，不自动保存或重试。
