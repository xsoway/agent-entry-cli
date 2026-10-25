#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:53
# @Filename : display.py
# @Author   : Alan_Hsu
"""终端的中文安全元数据展示，不接收模型私有推理。"""

from __future__ import annotations

from typing import Any

from .errors import explain

COMMANDS = [
    "/help",
    "/context",
    "/compact",
    "/save",
    "/sessions",
    "/resume",
    "/model",
    "/usage",
    "/clear",
    "/queue",
    "/next",
    "/drop",
    "/project",
    "/details",
    "/tools",
    "/status",
    "/stop",
    "/quit",
    "/exit",
]
HELP = """/help                     查看帮助与项目命令
/context /compact         上下文窗口估算 / 手动压缩
/save /sessions           显式保存摘要 / 按时间列出已保存摘要
/resume ID|latest         恢复指定或最新的同项目摘要
/model [name] /usage      查看或设置模型 / 累计已知与未知用量
/tools /status /details   工具与授权声明 / 当前状态 / 最近执行元数据
/clear                    清空上下文，保留累计用量
/project PATH             切换项目（仅重载显式指定的插件）
/queue /next /drop         查看队列 / 恢复暂停队列 / 丢弃队列
/stop                     取消当前执行，等待清理
/quit /exit               退出；运行中先取消并等待清理
Ctrl+C：空闲退出；运行中首次取消，再次请求清理后退出。Ctrl+D：退出。
增强输入：Enter 发送，Alt+Enter 换行，Tab 补全，上下键查看本次会话输入。
运行中只读控制可直接查看；其他控制命令不排队，普通文字进入下一轮。"""


def format_context(data: dict[str, Any]) -> str:
    return (
        f"上下文窗口：{data['context_window']}；已提交上下文的请求估算：{data['request_estimate']}（不含新输入）\n"
        f"历史与摘要：{data['history_estimate']}；项目指令：{data['instructions_estimate']}；"
        f"工具 schema：{data['tools_estimate']}\n"
        f"输出预留：{data['output_reserve']}；系统预留：{data['system_reserve']}；"
        f"剩余估算：{data['remaining_estimate']}\n"
        f"消息：{data['messages']}；存在摘要：{'是' if data['has_summary'] else '否'}；"
        f"已压缩：{data['compactions']} 次；建议压缩：{'是' if data['needs_compaction'] else '否'}\n"
        "估算依据：UTF-8 字节保守估算，非供应商 tokenizer；每次实际请求仍单独准入。"
    )


def format_usage(usage: dict[str, Any], limit: int | None) -> str:
    return (
        f"累计已知用量：{usage['known_tokens']} token；未知用量执行：{usage['unknown_executions']} 次\n"
        f"累计模型调用：{usage['model_calls']}；执行：{usage['executions']} 次；"
        f"计量完整：{'是' if usage['complete'] else '否'}\n"
        f"会话 token 上限：{limit if limit is not None else '未设置'}；价格不可用。\n"
        "上限在响应后结算，可能超额；未知用量不视为零，/clear 不重置用量。"
    )


def progress_text(event: dict[str, Any], max_calls: int) -> str:
    kind, status = event.get("event"), str(event.get("status", ""))
    if kind == "model":
        if status == "started":
            return f"模型调用 {event['model_calls']}/{max_calls} · 等待响应 · 请求估算 {event['context_estimate']}"
        if status == "reasoning":
            return "模型推理中（仅状态，内部推理不展示）"
        if status == "streaming":
            return "正在输出公开答复"
        return f"模型响应已收尾 · 本轮已知 {event.get('known_tokens', 0)} token"
    if kind == "tool":
        state = {
            "started": "开始",
            "settled": "完成",
            "failed": "失败",
            "denied": "授权拒绝",
            "cancelled": "已取消",
        }.get(status, "状态更新")
        effect = "写操作" if event.get("side_effect") else "只读声明"
        return f"工具 {event['tool_name']} · {effect} · {state}"
    if kind == "compaction":
        return {
            "started": "正在整理上下文摘要",
            "prepared": "摘要已生成，等待清理与提交",
            "completed": "上下文摘要已提交",
        }.get(status, "摘要状态更新")
    if kind == "cleanup":
        return {
            "started": "正在清理模型流与工具",
            "completed": "执行清理完成",
            "pending": "执行清理未完成",
        }.get(status, "清理状态更新")
    return ""


def format_result(row: dict[str, Any], max_calls: int) -> str:
    observed = row["observed_tokens"]
    usage = (
        f"{observed} token"
        if observed is not None
        else f"未知（已知部分 {row['known_tokens']} token）"
    )
    return (
        f"{explain(row['reason'])}\n"
        f"模型循环：{row['model_calls']}/{max_calls}；本轮用量：{usage}\n"
        f"清理完成：{'是' if row['cleanup_complete'] else '否'}；未知写操作：{row['pending_writes']}\n"
        f"执行 ID：{row['execution_id']}\n账本：{row['ledger_path']}"
    )
