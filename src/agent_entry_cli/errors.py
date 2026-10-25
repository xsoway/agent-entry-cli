#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time     : 2026/10/24 12:50
# @Filename : errors.py
# @Author   : Alan_Hsu
"""固定错误类别与中文恢复提示；不展示外部异常正文。"""

from __future__ import annotations

from agents.exceptions import MaxTurnsExceeded
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

MESSAGES = {
    "completed": "执行完成。",
    "user_cancelled": "已取消；后续输入队列已暂停，使用 /next 继续或 /drop 丢弃。",
    "deadline_exceeded": "执行超时；检查工具状态与 timeout_seconds，再决定下一步。",
    "cleanup_incomplete": "清理尚未完成，暂不能发起新请求；非协作插件可能阻止退出。",
    "previous_cleanup_pending": "前次清理仍在进行，请等待；不要重复发起业务操作。",
    "runtime_still_running": "运行时仍在执行或清理，请等待。",
    "write_result_unknown": "写操作结果未知，请在业务系统核实；不会自动重试或重放。",
    "client_cleanup_failed": "客户端清理失败，请核对外部状态后退出。",
    "metadata_write_failed": "执行元数据写入失败，已停止放行；检查项目目录权限和磁盘空间。",
    "unsafe_event_path": "执行记录目录包含不安全路径；请检查 .agent-entry 目录。",
    "context_window_exceeded": "请求超出上下文窗口；使用 /context 检查，/compact 压缩或 /clear 清空后重试。",
    "context_compaction_required": "上下文需要压缩；使用 /compact 或 /clear，不会静默丢弃历史。",
    "model_call_budget_exceeded": "本轮模型调用已达上限；检查工具循环或 max_model_calls。",
    "token_budget_exceeded": "已达到 token 预算或用量未知；查看 /usage，先核实用量。",
    "session_budget_unavailable": "会话预算已用完或包含未知用量；查看 /usage 并核实，/clear 不会重置用量。",
    "request_invalid": "请求为空或超过 64 KiB；请缩短后发送。",
    "output_too_large": "输出超过 64 KiB；请缩小问题范围。",
    "stream_too_large": "流式输出超过 64 KiB；请缩小问题范围。",
    "model_and_credential_required": "尚未配置模型或凭据；设置模型及对应的密钥环境变量，使用 /model 查看配置。",
    "invalid_project_config": "项目配置无效；检查 agent-entry.toml 的 TOML 语法、字段、类型和窗口预留。",
    "project_directory_required": "项目目录不存在；检查 --project 或 /project 路径。",
    "invalid_project": "项目目录或项目说明无效；检查项目根目录与插件返回值。",
    "project_plugin_rejected": "项目插件加载失败；检查显式 --plugin 路径和 build_project(root) 返回值。",
    "invalid_summary_id": "摘要 ID 无效；使用 /sessions 选择完整 ID，或 /resume latest。",
    "summary_id_required": "需要一个摘要 ID；使用 /resume ID 或 /resume latest。",
    "no_saved_summaries": "没有可恢复的摘要；先通过 /save 显式保存。",
    "invalid_summary": "摘要无效、作用域不匹配或超过当前窗口；使用 /sessions 选择本项目的有效摘要。",
    "unsafe_summary_path": "摘要路径包含符号链接；请检查 .agent-entry/summaries。",
    "summary_required": "当前还没有可保存的摘要；先完成对话，再使用 /save。",
    "summary_too_large": "摘要文件过大；请缩小上下文后重新保存。",
    "conversation_summary_invalid": "模型未返回有效摘要；原上下文保留，可显式再次 /compact。",
    "conversation_summary_boundary_invalid": "摘要边界无效，原上下文保留。",
    "conversation_summary_window_exceeded": "摘要仍超出窗口，原上下文保留；检查窗口配置或 /clear。",
    "conversation_summary_input_too_large": "待摘要材料本身超过窗口；原上下文保留，请调整有效窗口或显式 /clear。",
    "unexpected_command_arguments": "命令不接受这些参数；使用 /help 查看用法。",
    "invalid_model": "模型名称无效；使用 /model 模型名 设置。",
    "project_required": "需要一个项目路径；含空格时请用引号包围。",
    "invalid_command_syntax": "命令引号或参数格式不完整；检查引号后重新输入。",
    "json_requires_message": "--json 需要与 --message 一起使用。",
    "interactive_tty_required": "交互模式需要终端；脚本调用请使用 --message。",
    "file_not_found": "文件不存在；检查插件路径或使用 /sessions 选择摘要。",
    "file_exists": "配置文件已存在，未覆盖；请编辑现有 agent-entry.toml。",
    "filesystem_error": "文件系统操作失败；检查目录权限、磁盘空间和路径。",
    "provider_authentication_failed": "模型服务认证失败；检查密钥环境变量和密钥有效性。",
    "provider_permission_denied": "模型服务拒绝访问；检查账户权限与模型访问范围。",
    "provider_rate_limited": "模型服务限流；稍后按需重新发送，本次不会自动重试。",
    "provider_quota_exceeded": "模型服务额度不足；检查账户余额和用量限制。",
    "provider_timeout": "模型服务请求超时；检查网络及服务状态，不会自动重试。",
    "provider_connection_failed": "无法连接模型服务；检查 base_url、网络、代理及证书。",
    "provider_model_not_found": "模型或服务路径不存在；检查模型名和 base_url。",
    "provider_bad_request": "模型服务不接受请求；检查模型、协议及参数兼容性。",
    "provider_unavailable": "模型服务异常；检查服务状态后再决定是否重新发送。",
    "model_request_failed": "模型请求失败；检查模型、协议、网络和凭据，不会自动重试。",
    "execution_failed": "执行失败；查看 /details 的安全原因码，检查项目工具与配置，不会自动重试。",
}


def safe_reason(error: Exception) -> str:
    """仅信任固定原因码和 SDK 异常类型，丢弃外部正文。"""
    categories = (
        (MaxTurnsExceeded, "model_call_budget_exceeded"),
        (AuthenticationError, "provider_authentication_failed"),
        (PermissionDeniedError, "provider_permission_denied"),
        (RateLimitError, "provider_rate_limited"),
        (APITimeoutError, "provider_timeout"),
        (APIConnectionError, "provider_connection_failed"),
        (NotFoundError, "provider_model_not_found"),
        (BadRequestError, "provider_bad_request"),
        (APIStatusError, "provider_unavailable"),
        (FileNotFoundError, "file_not_found"),
        (FileExistsError, "file_exists"),
        (OSError, "filesystem_error"),
    )
    if isinstance(error, RateLimitError) and error.code in {
        "insufficient_quota",
        "credit_balance_exhausted",
    }:
        return "provider_quota_exceeded"
    for kind, code in categories:
        if isinstance(error, kind):
            return code
    code = str(error) if isinstance(error, ValueError) else "execution_failed"
    return code if code in MESSAGES else "execution_failed"


def explain(code: str) -> str:
    return f"{MESSAGES.get(code, MESSAGES['execution_failed'])} [{code if code in MESSAGES else 'execution_failed'}]"
