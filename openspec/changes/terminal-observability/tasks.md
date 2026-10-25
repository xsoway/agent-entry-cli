# 终端基本操作与可观测性实施计划

目标：完成 terminal-observability/spec.md 中全部要求。原生顺序执行，保留已有工作，不提交或发布。
技术栈：Python 3.13、已有 SDK、prompt-toolkit、Rich；不新增依赖。
审查重点：重复 Ctrl+C、SIGINT 清理、观察者异常、推理/工具载荷泄漏、摘要最终提交与时间排序、大 schema 自动摘要、取消未知用量及未知写。

## 1. 生命周期和交互
- [x] 1.1 在 tests/test_terminal_basics.py 先补失败回归，再修复 Ctrl+C、Ctrl+D、运行中退出和普通模式异步输入。用真实 PTY 验证两种模式，无孤立线程/traceback。

## 2. 元数据与上下文
- [x] 2.1 在 tests/test_observability.py 补失败回归；Runtime.run 增加 on_event，模型/工具/摘要/清理事件、固定安全错误分类；观察者失败隔离与载荷隐私测试通过。
- [x] 2.2 补大指令/schema 上下文回归；统一诊断和自动摘要判断，保留逐次请求准入和原子摘要提交。

## 3. 中文交互与发现
- [x] 3.1 补测试后实现中文状态/错误/进度，命令与工具发现；运行中查看安全状态、不执行控制命令队列。普通/增强/NO_COLOR 输出通过。
- [x] 3.2 补测试后实现按时间排序的摘要列表、预览与 latest 恢复，保持旧 schema、作用域和权限约定。

## 4. 交付验证
- [x] 4.1 更新中文手册与限制；执行 pytest、ruff、format、pyright、build、distribution、OpenSpec 与真实 PTY；缺陷导向独立审查，修复并复测。
