"""
步骤一：串流账号自动登录
========================

功能说明：
- 使用MSAL设备码认证流程登录微软账号
- 首次登录需用户手动输入设备代码，后续自动使用Refresh Token刷新
- 支持多账号Token持久化存储
- 通过Xbox Live认证获取游戏所需令牌

认证流程：
1. 验证账号信息完整性
2. 检查是否有缓存的Refresh Token
3. 如果有，使用Refresh Token刷新获取新Token
4. 如果没有，使用设备码认证，等待用户验证
5. 转换为Xbox Live Token
6. 保存Refresh Token（如获取到）

方法拆分：
- step1_execute_login(): 执行登录主流程
- _validate_account_info(): 验证账号信息
- _get_microsoft_token(): 获取微软访问令牌（优先使用Refresh Token）
- _get_xbox_live_token(): 获取Xbox Live令牌
- _report_progress(): 上报进度到平台

作者：技术团队
版本：3.0
基于MSAL设备码认证方案
"""

import asyncio
from typing import Callable, Optional, Dict, Any

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step1Result, TaskStepStatus


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
        if not validation.get("is_valid", False):
            error_msg = validation.get("error_msg", "未知错误")
            logger.error(f"账号信息验证失败: {error_msg}")
            stream_logger.error(f"账号信息验证失败: {error_msg}")
            context.update_step_status("step1", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
            return Step1Result(success=False, error_code="INVALID_ACCOUNT",
                             message=error_msg)

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

    except asyncio.TimeoutError as e:
        error_msg = f"步骤一执行超时: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤一网络连接失败: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤一参数错误: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="VALUE_ERROR", message=error_msg)

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

    # 打印账号信息供确认
    logger.info(f"账号验证 - 邮箱: {context.streaming_account_email}")
    logger.info(f"账号验证 - 密码: {context.streaming_account_password}")
    stream_logger.info(f"账号验证 - 邮箱: {context.streaming_account_email}")
    stream_logger.info(f"账号验证 - 密码: {context.streaming_account_password}")

    return {"is_valid": True, "error_msg": ""}


async def _get_microsoft_token(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    获取微软访问令牌

    使用MSAL设备码认证流程：
    1. 优先检查缓存的Refresh Token
    2. 如果有Refresh Token，自动刷新获取新Token（无感登录）
    3. 如果没有，使用设备码认证，等待用户手动验证
    4. 自动保存Refresh Token到持久化存储

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号专用日志记录器

    返回：
    - MicrosoftTokens或None
    """
    try:
        from ..auth.microsoft_auth_msal import MicrosoftMsalAuthenticator

        authenticator = MicrosoftMsalAuthenticator()

        logger.info(f"开始微软账号MSAL认证: {context.streaming_account_email}")
        stream_logger.info(f"开始微软账号MSAL认证（设备码流程）")

        # 检查已存储的账号
        stored_accounts = MicrosoftMsalAuthenticator.get_stored_accounts()
        if context.streaming_account_email in stored_accounts:
            logger.info(f"发现已存储的Refresh Token，将自动刷新...")
            stream_logger.info(f"发现已存储的Refresh Token，将自动刷新...")

        # 执行认证（优先使用Refresh Token，失败则回退到设备码认证）
        # 传递密码以启用浏览器自动化登录
        result = await authenticator.login_with_credentials(
            email=context.streaming_account_email,
            password=context.streaming_account_password
        )

        if result.success:
            logger.info(f"微软账号MSAL认证成功")
            stream_logger.info(f"微软账号MSAL认证成功")
            return result.microsoft_tokens
        else:
            logger.error(f"微软账号MSAL认证失败: {result.message}, 错误码: {result.error_code}")
            stream_logger.error(f"微软账号MSAL认证失败: {result.message}")
            return None

    except asyncio.TimeoutError as e:
        logger.error(f"获取Microsoft Token超时: {e}", exc_info=True)
        stream_logger.error(f"获取Microsoft Token超时: {e}", exc_info=True)
        return None

    except ConnectionError as e:
        logger.error(f"获取Microsoft Token网络连接失败: {e}", exc_info=True)
        stream_logger.error(f"获取Microsoft Token网络连接失败: {e}", exc_info=True)
        return None

    except ValueError as e:
        logger.error(f"获取Microsoft Token参数错误: {e}", exc_info=True)
        stream_logger.error(f"获取Microsoft Token参数错误: {e}", exc_info=True)
        return None

    except Exception as e:
        logger.error(f"获取Microsoft Token异常: {e}", exc_info=True)
        stream_logger.error(f"获取Microsoft Token异常: {e}", exc_info=True)
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
        from ..auth.microsoft_auth_msal import XboxLiveClient

        xbox_client = XboxLiveClient()

        logger.info("开始获取Xbox Live Token（包括GSSV Token）")
        stream_logger.info("开始获取Xbox Live Token（包括GSSV Token）")
        
        xbox_tokens = await xbox_client.get_xbox_tokens_with_gssv(microsoft_tokens.access_token)
        
        if xbox_tokens and xbox_tokens.gs_token:
            logger.info(f"Xbox Live Token获取成功（含GSSV Token）, uhs: {xbox_tokens.user_hash}, has_gs_token: True")
            stream_logger.info(f"Xbox Live Token获取成功（含GSSV Token）, uhs: {xbox_tokens.user_hash}, has_gs_token: True")
        elif xbox_tokens:
            logger.warning(f"Xbox Live Token获取成功（无GSSV Token）, uhs: {xbox_tokens.user_hash}, has_gs_token: False")
            stream_logger.warning(f"Xbox Live Token获取成功（无GSSV Token）, uhs: {xbox_tokens.user_hash}, has_gs_token: False")
        else:
            xbox_tokens = await xbox_client.get_xbox_tokens(microsoft_tokens.access_token)
            if xbox_tokens:
                logger.warning("GSSV Token获取失败，使用旧的Xbox Live Token")
                stream_logger.warning("GSSV Token获取失败，使用旧的Xbox Live Token")
                logger.info(f"Xbox Live Token获取成功（旧流程）, uhs: {xbox_tokens.user_hash}, has_gs_token: False")
                stream_logger.info(f"Xbox Live Token获取成功（旧流程）, uhs: {xbox_tokens.user_hash}, has_gs_token: False")
            else:
                logger.error("Xbox Live Token获取失败（包含GSSV Token）")
                stream_logger.error("Xbox Live Token获取失败（包含GSSV Token）")

        return xbox_tokens

    except asyncio.TimeoutError as e:
        logger.error(f"获取Xbox Live Token超时: {e}", exc_info=True)
        stream_logger.error(f"获取Xbox Live Token超时: {e}", exc_info=True)
        return None

    except ConnectionError as e:
        logger.error(f"获取Xbox Live Token网络连接失败: {e}", exc_info=True)
        stream_logger.error(f"获取Xbox Live Token网络连接失败: {e}", exc_info=True)
        return None

    except ValueError as e:
        logger.error(f"获取Xbox Live Token参数错误: {e}", exc_info=True)
        stream_logger.error(f"获取Xbox Live Token参数错误: {e}", exc_info=True)
        return None

    except Exception as e:
        logger.error(f"获取Xbox Live Token异常: {e}", exc_info=True)
        stream_logger.error(f"获取Xbox Live Token异常: {e}", exc_info=True)
        return None
