"""
步骤一：串流账号自动登录（legacy MSAL，已移出生产热路径）
============================================================

⚠️ 生产任务请使用 step1_xblive_login（auth.provider=xblive）。
本模块保留供 scripts/debug 与历史对照，step1_router 不再路由至此。

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
版本：4.0
基于MSAL设备码认证方案

版本历史：
- 3.0: 基于MSAL设备码认证方案
- 4.0: 优化错误上报机制，精确传递错误码和详细信息
"""

import asyncio
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass, field

from ..core.task_logger import get_task_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step1Result, TaskStepStatus


@dataclass
class TokenResult:
    """
    Token获取结果统一返回类型
    
    用于统一 Microsoft Token 和 Xbox Live Token 的获取结果，
    包含详细的错误信息，便于上层准确上报状态和错误原因
    """
    success: bool = False
    microsoft_tokens: Any = None
    xbox_tokens: Any = None
    error_code: str = ""
    error_message: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)


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
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤一：开始串流账号登录 ===")
    stream_logger.info("=== 开始串流账号登录 ===")

    context.update_step_status("step1", TaskStepStatus.RUNNING, "正在登录串流账号...")
    await report_progress(context.task_id, "STEP1", "RUNNING", "正在登录串流账号...")

    try:
        if check_cancel():
            task_logger.info("任务被取消，步骤一终止")
            context.update_step_status("step1", TaskStepStatus.SKIPPED, "任务被取消")
            return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

        validation = await _validate_account_info(context, task_logger, stream_logger)
        if not validation.get("is_valid", False):
            error_msg = validation.get("error_msg", "未知错误")
            task_logger.error(f"账号信息验证失败: {error_msg}")
            stream_logger.error(f"账号信息验证失败: {error_msg}")
            context.update_step_status("step1", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
            return Step1Result(success=False, error_code="INVALID_ACCOUNT",
                             message=error_msg)

        if check_cancel():
            return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step1", TaskStepStatus.RUNNING, "正在获取微软账号Token...")
        stream_logger.info("正在获取微软账号Token...")
        ms_token_result = await _get_microsoft_token(context, task_logger, stream_logger)

        if not ms_token_result.success or not ms_token_result.microsoft_tokens:
            # Microsoft Token 获取失败
            error_code = ms_token_result.error_code or "MICROSOFT_TOKEN_FAILED"
            error_message = ms_token_result.error_message or "获取Microsoft Token失败"
            
            # 构建详细错误消息
            detailed_error_msg = f"[{error_code}] {error_message}"
            if ms_token_result.error_details and "suggestion" in ms_token_result.error_details:
                detailed_error_msg += f"; 解决方案: {ms_token_result.error_details['suggestion']}"
            
            task_logger.error(f"Microsoft Token 获取失败: {detailed_error_msg}")
            stream_logger.error(f"Microsoft Token 获取失败: {error_message}")
            
            # 记录详细信息
            if ms_token_result.error_details:
                task_logger.error("\n详细信息:")
                for key, value in ms_token_result.error_details.items():
                    if key != "suggestion":
                        task_logger.error(f"  {key}: {value}")
                if "suggestion" in ms_token_result.error_details:
                    task_logger.error(f"\n解决方案: {ms_token_result.error_details['suggestion']}")
            
            context.update_step_status("step1", TaskStepStatus.FAILED, detailed_error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", detailed_error_msg)
            return Step1Result(success=False, error_code=error_code, message=detailed_error_msg)

        microsoft_tokens = ms_token_result.microsoft_tokens

        context.update_step_status("step1", TaskStepStatus.RUNNING, "正在获取Xbox Live令牌...")
        stream_logger.info("正在获取Xbox Live令牌...")
        xbox_token_result = await _get_xbox_live_token(microsoft_tokens, context, task_logger, stream_logger)

        if not xbox_token_result.success or not xbox_token_result.xbox_tokens:
            # Xbox Live Token 获取失败
            error_code = xbox_token_result.error_code or "XBOX_TOKEN_FAILED"
            error_message = xbox_token_result.error_message or "获取Xbox Live Token失败"
            
            # 构建详细错误消息
            detailed_error_msg = f"[{error_code}] {error_message}"
            if xbox_token_result.error_details and "suggestion" in xbox_token_result.error_details:
                detailed_error_msg += f"; 解决方案: {xbox_token_result.error_details['suggestion']}"
            
            task_logger.error(f"Xbox Live Token 获取失败: {detailed_error_msg}")
            stream_logger.error(f"Xbox Live Token 获取失败: {error_message}")
            
            # 记录详细信息
            if xbox_token_result.error_details:
                task_logger.error("\n详细信息:")
                for key, value in xbox_token_result.error_details.items():
                    if key != "suggestion":
                        task_logger.error(f"  {key}: {value}")
                if "suggestion" in xbox_token_result.error_details:
                    task_logger.error(f"\n解决方案: {xbox_token_result.error_details['suggestion']}")
            
            context.update_step_status("step1", TaskStepStatus.FAILED, detailed_error_msg)
            await report_progress(context.task_id, "STEP1", "FAILED", detailed_error_msg)
            return Step1Result(success=False, error_code=error_code, message=detailed_error_msg)

        xbox_tokens = xbox_token_result.xbox_tokens

        context.microsoft_tokens = microsoft_tokens
        context.xbox_tokens = xbox_tokens

        success_msg = "串流账号登录成功"
        task_logger.info(f"{success_msg}: {context.streaming_account_email}")
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
        task_logger.info("步骤一被取消")
        stream_logger.info("步骤一被取消")
        context.update_step_status("step1", TaskStepStatus.SKIPPED, "任务被取消")
        return Step1Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤一执行超时: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤一网络连接失败: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤一参数错误: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤一执行异常: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step1", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP1", "FAILED", error_msg)
        return Step1Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _validate_account_info(
    context: AgentTaskContext,
    task_logger,
    stream_logger
) -> Dict[str, Any]:
    """
    验证账号信息完整性

    参数：
    - context: 任务上下文
    - task_logger: 任务日志记录器
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

    # 只记录凭据是否存在，禁止输出明文密码。
    task_logger.info(f"账号验证 - 邮箱: {context.streaming_account_email}")
    task_logger.info(
        "账号验证 - 密码已提供: %s",
        bool(context.streaming_account_password),
    )
    stream_logger.info(f"账号验证 - 邮箱: {context.streaming_account_email}")
    stream_logger.info(
        "账号验证 - 密码已提供: %s",
        bool(context.streaming_account_password),
    )

    return {"is_valid": True, "error_msg": ""}


async def _get_microsoft_token(
    context: AgentTaskContext,
    task_logger,
    stream_logger
) -> TokenResult:
    """
    获取微软访问令牌
    
    使用MSAL设备码认证流程：
    1. 优先检查缓存的Refresh Token
    2. 如果有Refresh Token，自动刷新获取新Token（无感登录）
    3. 如果没有，使用设备码认证，等待用户手动验证
    4. 自动保存Refresh Token到持久化存储
    
    参数：
    - context: 任务上下文
    - task_logger: 任务日志记录器
    - stream_logger: 流媒体账号专用日志记录器
    
    返回：
    - TokenResult: 包含结果或详细错误信息的对象
    """
    try:
        from ..auth.microsoft_auth_msal import MicrosoftMsalAuthenticator

        authenticator = MicrosoftMsalAuthenticator()

        task_logger.info(f"开始微软账号MSAL认证: {context.streaming_account_email}")
        stream_logger.info(f"开始微软账号MSAL认证（设备码流程）")

        # 检查已存储的账号
        stored_accounts = MicrosoftMsalAuthenticator.get_stored_accounts()
        if context.streaming_account_email in stored_accounts:
            task_logger.info(f"发现已存储的Refresh Token，将自动刷新...")
            stream_logger.info(f"发现已存储的Refresh Token，将自动刷新...")

        # 执行认证（优先使用Refresh Token，失败则回退到设备码认证）
        # 传递密码和auto_code以启用浏览器自动化登录和MFA自动验证码生成
        result = await authenticator.login_with_credentials(
            email=context.streaming_account_email,
            password=context.streaming_account_password,
            auto_code=context.streaming_account_auto_code
        )

        if result.success:
            task_logger.info(f"微软账号MSAL认证成功")
            stream_logger.info(f"微软账号MSAL认证成功")
            return TokenResult(
                success=True,
                microsoft_tokens=result.microsoft_tokens
            )
        else:
            # 认证失败，记录详细错误信息并返回
            error_code = result.error_code or "UNKNOWN"
            error_message = result.message or "Microsoft认证失败"
            
            task_logger.error(f"微软账号MSAL认证失败")
            task_logger.error(f"  错误码: {error_code}")
            task_logger.error(f"  错误消息: {error_message}")
            if result.error_details:
                task_logger.error(f"  错误详情: {result.error_details}")
            
            stream_logger.error(f"微软账号MSAL认证失败: {error_message}")
            
            # 根据错误码生成解决方案
            suggestion = _get_auth_error_suggestion(error_code, "Microsoft")
            
            return TokenResult(
                success=False,
                error_code=error_code,
                error_message=error_message,
                error_details={
                    "account": context.streaming_account_email,
                    "error_details": result.error_details,
                    "suggestion": suggestion
                }
            )

    except asyncio.TimeoutError as e:
        error_msg = f"获取Microsoft Token超时: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="TIMEOUT",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "TimeoutError",
                "suggestion": "网络连接超时，请检查网络稳定性"
            }
        )

    except ConnectionError as e:
        error_msg = f"获取Microsoft Token网络连接失败: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="CONNECTION_ERROR",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "ConnectionError",
                "suggestion": "网络连接失败，请检查网络设置和代理配置"
            }
        )

    except ValueError as e:
        error_msg = f"获取Microsoft Token参数错误: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="VALUE_ERROR",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "ValueError",
                "suggestion": "参数错误，请检查账号信息是否正确"
            }
        )

    except Exception as e:
        error_msg = f"获取Microsoft Token异常: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="EXCEPTION",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": type(e).__name__,
                "suggestion": "发生未知错误，请查看日志获取详细信息"
            }
        )


async def _get_xbox_live_token(
    microsoft_tokens: Any,
    context: AgentTaskContext,
    task_logger,
    stream_logger
) -> TokenResult:
    """
    获取Xbox Live令牌
    
    参数：
    - microsoft_tokens: 微软访问令牌
    - context: 任务上下文
    - task_logger: 任务日志记录器
    - stream_logger: 流媒体账号专用日志记录器
    
    返回：
    - TokenResult: 包含结果或详细错误信息的对象
    """
    try:
        from ..auth.microsoft_auth_msal import XboxLiveClient

        xbox_client = XboxLiveClient()

        task_logger.info("开始获取 Xbox Live Token（含 GSSV gsToken，云端设备列表必需）")
        stream_logger.info("开始获取 Xbox Live Token（含 GSSV gsToken）")

        xbox_tokens = await xbox_client.get_xbox_tokens_with_gssv(microsoft_tokens.access_token)

        if xbox_tokens and xbox_tokens.gs_token:
            task_logger.info(
                "Xbox Live Token 成功 uhs=%s has_gs_token=True",
                xbox_tokens.user_hash,
            )
            stream_logger.info(
                f"Xbox Live Token获取成功（含GSSV Token）, uhs: {xbox_tokens.user_hash}"
            )
            return TokenResult(success=True, xbox_tokens=xbox_tokens)

        error_msg = "GSSV gsToken 获取失败，无法拉取云端 Xbox 设备列表"
        task_logger.error(error_msg)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="NO_GS_TOKEN",
            error_message=error_msg,
            error_details={
                "has_gs_token": False,
                "suggestion": "确认流媒体账号已在 Xbox App 授权主机且具备 Xbox Live 权限",
            },
        )

    except asyncio.TimeoutError as e:
        error_msg = f"获取Xbox Live Token超时: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="TIMEOUT",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "TimeoutError",
                "suggestion": "Xbox Live服务响应超时，请稍后重试"
            }
        )

    except ConnectionError as e:
        error_msg = f"获取Xbox Live Token网络连接失败: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="CONNECTION_ERROR",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "ConnectionError",
                "suggestion": "无法连接到Xbox Live服务，请检查网络设置"
            }
        )

    except ValueError as e:
        error_msg = f"获取Xbox Live Token参数错误: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="VALUE_ERROR",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": "ValueError",
                "suggestion": "Token格式错误，请重新登录Microsoft账号"
            }
        )

    except Exception as e:
        error_msg = f"获取Xbox Live Token异常: {str(e)}"
        task_logger.error(error_msg, exc_info=True)
        stream_logger.error(error_msg)
        return TokenResult(
            success=False,
            error_code="EXCEPTION",
            error_message=error_msg,
            error_details={
                "account": context.streaming_account_email,
                "exception_type": type(e).__name__,
                "suggestion": "Xbox Live认证发生未知错误，请查看日志"
            }
        )


def _get_auth_error_suggestion(error_code: str, auth_type: str) -> str:
    """
    根据认证错误码生成解决方案提示
    
    注意：
    - SESSION_EXPIRED 和 REFRESH_TOKEN_INVALID 在 login_with_credentials() 内部
      会被自动处理（自动回退到设备码认证），不会上报到这里
    - 这里的错误码表示：所有自动恢复机制都失败后的最终错误
    
    参数:
        error_code: 错误码
        auth_type: 认证类型 ("Microsoft" 或 "Xbox Live")
        
    返回:
        解决方案提示字符串
    """
    suggestions = {
        # Microsoft 认证错误码（设备码认证失败后的错误）
        "INVALID_CREDENTIALS": "请检查账号密码是否正确，确保账号未被锁定",
        "ACCOUNT_LOCKED": "账号已被锁定，请在Microsoft官网解锁后重试",
        "MFA_REQUIRED": "账号启用了多因素认证，请关闭MFA或使用应用密码",
        "MFA_FAILED": "MFA验证码验证失败，请检查验证码是否正确",
        "MFA_TIMEOUT": "MFA验证码输入超时，请重新登录并在规定时间内输入验证码",
        "MFA_INVALID_CODE": "MFA验证码错误，请检查是否使用了正确的验证码",
        "RATE_LIMITED": "请求频率过高，请稍后重试",
        "PERMISSION_DENIED": "账号权限不足，请确保账号有足够的权限",
        "DEVICE_LIMIT": "设备数量达到上限，请移除不使用的设备",
        "AUTHENTICATION_FAILED": "认证失败，请检查账号密码是否正确",
        "BROWSER_ERROR": "浏览器自动化失败，请确保已安装Chrome或Edge浏览器",
        "CAPTCHA_REQUIRED": "检测到验证码，请稍后重试或使用其他网络",
        
        # 通用错误码
        "DEVICE_CODE_TIMEOUT": "设备码认证超时，请在设备上及时完成验证",
        "DEVICE_CODE_FAILED": "设备码认证失败，请重试",
        "TIMEOUT": "网络连接超时，请检查网络稳定性",
        "CONNECTION_ERROR": "网络连接失败，请检查网络设置和代理配置",
        "UNKNOWN": "未知错误，请查看详细日志获取更多信息"
    }
    
    # Xbox Live 特有的错误码
    xbox_suggestions = {
        "XBOX_TOKEN_FAILED": "Xbox Live Token获取失败，请确保Microsoft账号已绑定Xbox",
        "GSSV_TOKEN_FAILED": "GSSV Token获取失败，账号可能没有Xbox Live权限",
        "XSTS_INVALID": "XSTS Token无效，账号可能没有Xbox Live权限",
        "RESTRICTED_ACCOUNT": "账号被Xbox Live限制，请检查账号状态",
        "USER_TOKEN_FAILED": "Xbox用户令牌获取失败，请重新登录Microsoft账号"
    }
    
    if auth_type == "Xbox Live" and error_code in xbox_suggestions:
        return xbox_suggestions[error_code]
    
    return suggestions.get(error_code, suggestions["UNKNOWN"])
