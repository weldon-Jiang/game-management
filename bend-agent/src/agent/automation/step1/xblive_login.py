"""
步骤一（xblive 路线）：SISU + Device Token 认证。

产出与 xblive handle_return 一致：gsToken、serverId、playPath、gamerTag。
生产 Step1 入口；legacy MSAL 见 step1_stream_account_login（仅 debug）。
"""

from __future__ import annotations

import asyncio
from typing import Callable

from ...core.task_logger import get_task_logger
from ...core.account_logger import get_stream_logger
from ...task.task_context import AgentTaskContext, Step1Result, TaskStepStatus
from ...auth.xblive import authenticate_account, error_code_name, ERRXS_OK
from ...auth.xblive.models import XbliveCompatXboxTokens


async def step1_execute_login(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None],
) -> Step1Result:
    """xblive 风格 Step1：全链路认证并预查唯一 Xbox 主机。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤一（xblive）：开始串流账号认证 ===")
    stream_logger.info("=== 步骤一（xblive）：开始串流账号认证 ===")

    context.update_step_status("step1", TaskStepStatus.RUNNING, "正在 xblive 认证...")
    await report_progress(context.task_id, "STEP1", "RUNNING", "正在 xblive 认证...")

    if not context.streaming_account_email or not context.streaming_account_password:
        msg = "串流账号邮箱或密码为空"
        context.update_step_status("step1", TaskStepStatus.FAILED, msg)
        await report_progress(context.task_id, "STEP1", "FAILED", msg)
        return Step1Result(success=False, error_code="INVALID_ACCOUNT", message=msg)

    if check_cancel():
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    try:
        from ...core.config import get_config

        cfg = get_config()
        web_headless = bool(getattr(cfg.auth, "XBLIVE_WEB_HEADLESS", True))

        errno, auth_result = await authenticate_account(
            context.streaming_account_email,
            context.streaming_account_password,
            context.streaming_account_auto_code or "",
            streaming_account_id=context.streaming_account_id or "",
            task_id=context.task_id or "",
            web_headless=web_headless,
        )

        if check_cancel():
            return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

        if errno != ERRXS_OK or not auth_result:
            code = error_code_name(errno)
            msg = f"[{code}] xblive 认证失败 (errno={errno})"
            task_logger.error(msg)
            stream_logger.error(msg)
            context.update_step_status("step1", TaskStepStatus.FAILED, msg)
            await report_progress(context.task_id, "STEP1", "FAILED", msg)
            return Step1Result(success=False, error_code=code, message=msg)

        context.xblive_auth = auth_result
        compat = XbliveCompatXboxTokens(
            gs_token=auth_result.gs_token,
            gssv_base_uri=auth_result.gssv_base_uri,
            server_id=auth_result.server_id,
            play_path=auth_result.play_path,
            gamer_tag=auth_result.gamer_tag,
            xhome_token_response=auth_result.xhome_token,
            user_hash=(
                _user_hash_from_bundle(auth_result.token_bundle) or ""
            ),
            xsts_token=(auth_result.token_bundle.get("xsts_token") or {}).get("Token", "")
            if isinstance(auth_result.token_bundle.get("xsts_token"), dict)
            else "",
        )
        context.xbox_tokens = compat
        from ...xbox.streaming_credentials import attach_streaming_credentials

        attach_streaming_credentials(context)

        success_msg = (
            f"xblive 认证成功 gamerTag={auth_result.gamer_tag} "
            f"serverId={auth_result.server_id} playPath={auth_result.play_path}"
        )
        task_logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step1", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP1", "COMPLETED", success_msg)

        return Step1Result(success=True, message=success_msg, xbox_tokens=compat)

    except asyncio.CancelledError:
        context.update_step_status("step1", TaskStepStatus.SKIPPED, "任务被取消")
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as exc:
        msg = f"步骤一（xblive）异常: {exc}"
        task_logger.error(msg, exc_info=True)
        stream_logger.error(msg)
        context.update_step_status("step1", TaskStepStatus.FAILED, msg, str(exc))
        await report_progress(context.task_id, "STEP1", "FAILED", msg)
        return Step1Result(success=False, error_code="EXCEPTION", message=msg)


def _user_hash_from_bundle(bundle: dict) -> str:
    sisu = bundle.get("sisu_token") if isinstance(bundle, dict) else None
    if not isinstance(sisu, dict):
        return ""
    try:
        xui = (
            sisu.get("AuthorizationToken", {})
            .get("DisplayClaims", {})
            .get("xui", [])
        )
        if xui:
            return str(xui[0].get("uhs", "") or "")
    except Exception:
        pass
    return ""
