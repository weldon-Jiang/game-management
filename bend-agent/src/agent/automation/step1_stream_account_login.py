"""
步骤一：串流账号自动登录
========================

功能说明：
- 使用账号密码直接获取Microsoft OAuth Token
- 绕过微软设备代码登录窗口（ROPC流程）
- 复用现有 MicrosoftAuthenticator 模块

方法拆分：
- step1_execute_login(): 执行登录主流程
- _validate_account_info(): 验证账号信息
- _get_microsoft_token(): 获取微软访问令牌
- _get_xbox_live_token(): 获取Xbox Live令牌
- _report_progress(): 上报进度到平台

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Callable, Optional, Dict, Any

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from .task_context import AgentTaskContext, Step1Result, TaskStepStatus


async def step1_execute_login(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step1Result:
    """
    步骤一执行：串流账号自动登录

    流程：
    1. 验证账号信息完整性
    2. 使用ROPC流程获取Microsoft Token（绕过设备代码授权）
    3. 使用Microsoft Token获取Xbox Live Token
    4. 上报进度到平台

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - Step1Result: 包含认证结果的Step1Result
    """
    logger = get_logger(f'step1_login_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    logger.info("=== 步骤一：开始串流账号登录 ===")
    stream_logger.info("=== 开始串流账号登录 ===")

    context.update_step_status("step1", TaskStepStatus.RUNNING, "正在登录串流账号...")
    await report_progress(context.task_id, "STEP1", "RUNNING", "正在登录串流账号...")

    try:
        if check_cancel():
            logger.info("任务被取消，步骤一终止")
            context.update_step_status("step1", TaskStepStatus.SKIPPED, "任务被取消")
            return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

        validation = await _validate_account_info(context, logger, stream_logger)
        if not validation.is_valid:
            logger.error(f"账号信息验证失败: {validation.error_msg}")
            stream_logger.error(f"账号信息验证失败: {validation.error_msg}")
            context.update_step_status("step1", TaskStepStatus.FAILED, validation.error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", validation.error_msg)
            return Step1Result(success=False, error_code="INVALID_ACCOUNT",
                             message=validation.error_msg)

        if check_cancel():
            return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step1", TaskStepStatus.RUNNING, "正在获取微软账号Token...")
        stream_logger.info("正在获取微软账号Token...")
        microsoft_tokens = await _get_microsoft_token(context, logger, stream_logger)

        if not microsoft_tokens:
            error_msg = "获取Microsoft Token失败，请检查账号密码"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step1", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
            return Step1Result(success=False, error_code="MICROSOFT_TOKEN_FAILED",
                             message=error_msg)

        context.update_step_status("step1", TaskStepStatus.RUNNING, "正在获取Xbox Live令牌...")
        stream_logger.info("正在获取Xbox Live令牌...")
        xbox_tokens = await _get_xbox_live_token(microsoft_tokens, context, logger, stream_logger)

        if not xbox_tokens:
            error_msg = "获取Xbox Live Token失败"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step1", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
            return Step1Result(success=False, error_code="XBOX_TOKEN_FAILED",
                             message=error_msg)

        context.microsoft_tokens = microsoft_tokens
        context.xbox_tokens = xbox_tokens

        success_msg = "串流账号登录成功"
        logger.info(f"{success_msg}: {context.streaming_account_email}")
        stream_logger.info(f"{success_msg}")
        context.update_step_status("step1", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP1", "COMPLETED", success_msg)

        return Step1Result(
            success=True,
            message=success_msg,
            microsoft_tokens=microsoft_tokens,
            xbox_tokens=xbox_tokens
        )

    except asyncio.CancelledError:
        logger.info("步骤一被取消")
        stream_logger.info("步骤一被取消")
        context.update_step_status("step1", TaskStepStatus.SKIPPED, "任务被取消")
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as e:
        error_msg = f"步骤一执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _validate_account_info(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Dict[str, Any]:
    """
    验证账号信息完整性

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号专用日志记录器

    返回：
    - Dict: {is_valid: bool, error_msg: str}
    """
    if not context.streaming_account_email:
        return {"is_valid": False, "error_msg": "串流账号邮箱为空"}

    if not context.streaming_account_password:
        return {"is_valid": False, "error_msg": "串流账号密码为空"}

    if "@" not in context.streaming_account_email:
        return {"is_valid": False, "error_msg": "串流账号邮箱格式无效"}

    logger.info(f"账号信息验证通过: {context.streaming_account_email}")
    stream_logger.info(f"账号信息验证通过")
    return {"is_valid": True, "error_msg": ""}


async def _get_microsoft_token(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    获取微软访问令牌

    使用ROPC（Resource Owner Password Credentials）流程
    绕过微软设备代码登录窗口

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号专用日志记录器

    返回：
    - MicrosoftTokens或None
    """
    try:
        from ..auth.microsoft_auth import MicrosoftAuthenticator

        authenticator = MicrosoftAuthenticator()

        logger.info(f"开始微软账号认证: {context.streaming_account_email}")
        stream_logger.info(f"开始微软账号认证")

        result = await authenticator.login_with_credentials(
            email=context.streaming_account_email,
            password=context.streaming_account_password
        )

        await authenticator.close()

        if result.success:
            logger.info(f"微软账号认证成功")
            stream_logger.info(f"微软账号认证成功")
            return result.microsoft_tokens
        else:
            logger.error(f"微软账号认证失败: {result.message}")
            stream_logger.error(f"微软账号认证失败: {result.message}")
            return None

    except Exception as e:
        logger.error(f"获取Microsoft Token异常: {e}")
        stream_logger.error(f"获取Microsoft Token异常: {e}")
        return None


async def _get_xbox_live_token(
    microsoft_tokens: Any,
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    获取Xbox Live令牌

    参数：
    - microsoft_tokens: 微软访问令牌
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号专用日志记录器

    返回：
    - XboxLiveTokens或None
    """
    try:
        from ..auth.microsoft_auth import MicrosoftAuthenticator

        authenticator = MicrosoftAuthenticator()
        authenticator._microsoft_tokens = microsoft_tokens

        logger.info("开始获取Xbox Live Token")
        stream_logger.info("开始获取Xbox Live Token")

        xbox_tokens = await authenticator._get_xbox_tokens(microsoft_tokens.access_token)

        if xbox_tokens:
            logger.info(f"Xbox Live Token获取成功, uhs: {xbox_tokens.user_hash}")
            stream_logger.info(f"Xbox Live Token获取成功, uhs: {xbox_tokens.user_hash}")
        else:
            logger.error("Xbox Live Token获取失败")
            stream_logger.error("Xbox Live Token获取失败")

        return xbox_tokens

    except Exception as e:
        logger.error(f"获取Xbox Live Token异常: {e}")
        stream_logger.error(f"获取Xbox Live Token异常: {e}")
        return None
