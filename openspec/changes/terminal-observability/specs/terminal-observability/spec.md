## ADDED Requirements

### Requirement: 安全退出
终端 SHALL 在空闲 Ctrl+C/Ctrl+D 或 /quit、/exit 时退出；运行中第一次 Ctrl+C SHALL 取消，第二次 SHALL 请求清理后退出。/quit 或 /exit SHALL 运行中请求清理后退出。普通模式 SHALL 不遗留阻塞 input 线程。
#### Scenario: 两种终端模式
- **WHEN** 在增强或普通模式的空闲/运行阶段发送中断或退出
- **THEN** 进程按约定结束或回到输入，保留取消/清理/未知写与未知用量事实，无 traceback。

### Requirement: 元数据可观测性
运行时 SHALL 展示模型循环次数/上限、工具执行状态、摘要准备/提交、清理、上下文和用量元数据；等待时 SHALL 显示耗时。观察者异常 SHALL 不修改业务结果。系统 SHALL NOT 转发或记录私有推理、原始消息、工具参数/结果、凭据或异常正文。
#### Scenario: 工具及推理流
- **WHEN** SDK 执行包含推理事件、工具调用和公开答复的循环
- **THEN** 展示安全状态和公开答复，私有推理及工具载荷不进入观察事件、终端或元数据账本。

### Requirement: 上下文与预算
上下文展示和自动摘要判断 SHALL 包含指令、工具 schema、历史及预留空间；工具循环逐次请求仍 SHALL 实际检查窗口与预算。摘要 SHALL 仅在成功收尾后提交；取消后未知用量 SHALL 保持未知。
#### Scenario: 大工具 schema
- **WHEN** 指令/工具使实际上下文提前接近窗口
- **THEN** 显示相应占用，按有效剩余窗口触发摘要或明确拒绝；不静默丢弃对话。

### Requirement: 命令与诊断
终端 SHALL 提供中文帮助和明确原因/下一步；/help 与补全 SHALL 包含项目命令、/stop /tools /exit。/tools SHALL 展示工具名称、读写声明和授权策略是否存在，不声称实际权限已批准。
#### Scenario: 无效摘要 ID 与自定义命令
- **WHEN** 用户查询帮助/工具或恢复错误 ID
- **THEN** 命令可发现，错误指出 ID/作用域等安全原因，不暴露任意异常正文。

### Requirement: 摘要发现
/sessions SHALL 按本地保存时间降序显示时间、ID 和已保存摘要预览；/resume latest SHALL 显式恢复最新有效且同作用域的检查点。旧检查点 SHALL 兼容。
#### Scenario: 多个摘要
- **WHEN** UUID 字典序与保存时间相反
- **THEN** 列表及 latest 按保存时间选择，非法/异作用域摘要不展示，不自动加载。
