"""
步骤二：Xbox串流连接
====================

功能说明：
- 根据条件匹配Xbox主机
- 建立与Xbox的串流连接
- 回传主机信息到平台并标记防止抢夺

方法拆分：
- step2_execute_streaming(): 执行串流主流程
- _match_xbox_host(): 匹配Xbox主机
- _connect_to_xbox(): 连接到Xbox主机
- _bind_xbox_to_platform(): 绑定Xbox到平台（防止抢夺）
- _report_progress(): 上报进度到平台

作者：技术团队
版本：1.0
"""

import asyncio
import random
from typing import Callable, Optional, Dict, Any, List

from ..core.logger import get_logger
from .task_context import AgentTaskContext, Step2Result, XboxInfo, TaskStepStatus


async def step2_execute_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step2Result:
    """
    步骤二执行：Xbox串流连接

    流程：
    1. 检查是否指定了Xbox主机
       - 已指定：直接使用指定主机
       - 未指定：解析串流账号已登录的Xbox信息，匹配局域网在线Xbox
    2. 如果多个Xbox匹配，随机选择一个
    3. 建立与Xbox的串流连接
    4. 回传主机信息到平台并标记

    参数：
    - context: 任务上下文（包含第一步的认证结果）
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - Step2Result: 包含Xbox连接结果的Step2Result
    """
    logger = get_logger(f'step2_streaming_{context.task_id}')
    logger.info("=== 步骤二：开始Xbox串流连接 ===")

    context.update_step_status("step2", TaskStepStatus.RUNNING, "正在匹配Xbox主机...")
    await report_progress(context.task_id, "STEP2", "RUNNING", "正在匹配Xbox主机...")

    try:
        if check_cancel():
            logger.info("任务被取消，步骤二终止")
            context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        match_result = await _match_xbox_host(context, logger, check_cancel)

        if not match_result.success:
            logger.error(f"Xbox主机匹配失败: {match_result.message}")
            context.update_step_status("step2", TaskStepStatus.FAILED, match_result.message)
            await report_progress(context.task_id, "STEP2", "FAILED", match_result.message)
            return Step2Result(success=False, error_code="XBOX_MATCH_FAILED",
                             message=match_result.message)

        context.current_xbox = match_result.xbox_info
        logger.info(f"Xbox匹配成功: {match_result.xbox_info.name} "
                   f"({match_result.xbox_info.ip_address}), "
                   f"匹配方式: {match_result.match_type}")

        if check_cancel():
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step2", TaskStepStatus.RUNNING,
                                  f"正在连接{context.current_xbox.name}...")

        connect_success = await _connect_to_xbox(context, logger)

        if not connect_success:
            error_msg = f"连接Xbox失败: {context.current_xbox.ip_address}"
            logger.error(error_msg)
            context.update_step_status("step2", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
            return Step2Result(success=False, error_code="XBOX_CONNECT_FAILED",
                             message=error_msg)

        success_msg = f"Xbox串流连接成功: {context.current_xbox.name}"
        logger.info(success_msg)
        context.update_step_status("step2", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP2", "COMPLETED", success_msg)

        return Step2Result(success=True, message=success_msg, xbox_info=context.current_xbox)

    except asyncio.CancelledError:
        logger.info("步骤二被取消")
        context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as e:
        error_msg = f"步骤二执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _match_xbox_host(
    context: AgentTaskContext,
    logger,
    check_cancel: Callable[[], bool]
) -> Dict[str, Any]:
    """
    匹配Xbox主机

    匹配逻辑：
    1. 如果指定了Xbox主机，直接使用
    2. 如果未指定，发现在线Xbox并匹配
    3. 多匹配时随机选择

    参数：
    - context: 任务上下文
    - logger: 日志记录器
    - check_cancel: 取消检查函数

    返回：
    - Dict: {success: bool, xbox_info: XboxInfo, match_type: str, message: str}
    """
    if context.assigned_xbox:
        logger.info(f"使用指定的Xbox主机: {context.assigned_xbox.name} "
                   f"({context.assigned_xbox.ip_address})")

        online = await _test_xbox_connection(context.assigned_xbox.ip_address, logger)
        if online:
            return {
                "success": True,
                "xbox_info": context.assigned_xbox,
                "match_type": "assigned",
                "message": "使用指定的Xbox主机"
            }
        else:
            return {
                "success": False,
                "xbox_info": None,
                "match_type": "assigned",
                "message": f"指定的Xbox主机不在线: {context.assigned_xbox.ip_address}"
            }

    logger.info("未指定Xbox主机，开始自动匹配...")
    discovered_xboxes = await _discover_xbox_devices(logger)

    if not discovered_xboxes:
        return {
            "success": False,
            "xbox_info": None,
            "match_type": "discover",
            "message": "局域网未发现Xbox主机"
        }

    logger.info(f"发现 {len(discovered_xboxes)} 个Xbox主机")

    if len(discovered_xboxes) == 1:
        selected = discovered_xboxes[0]
        logger.info(f"只有一台Xbox，直接选择: {selected.name}")
        return {
            "success": True,
            "xbox_info": selected,
            "match_type": "discovered",
            "message": f"发现Xbox: {selected.name}"
        }

    selected = random.choice(discovered_xboxes)
    logger.info(f"多台Xbox，随机选择: {selected.name} ({selected.ip_address})")
    return {
        "success": True,
        "xbox_info": selected,
        "match_type": "random_selected",
        "message": f"随机选择Xbox: {selected.name}"
    }


async def _discover_xbox_devices(logger) -> List[XboxInfo]:
    """
    发现局域网中的Xbox设备

    参数：
    - logger: 日志记录器

    返回：
    - List[XboxInfo]: Xbox设备列表
    """
    try:
        from ..xbox.xbox_discovery import XboxDiscovery

        discovery = XboxDiscovery()
        devices = await discovery.discover(timeout=5.0)

        xbox_list = []
        for device in devices:
            xbox_info = XboxInfo(
                id=device.get("id", ""),
                name=device.get("name", "Xbox"),
                ip_address=device.get("ip", ""),
                live_id=device.get("live_id", ""),
                mac_address=device.get("mac", "")
            )
            xbox_list.append(xbox_info)

        logger.info(f"Xbox发现完成: {len(xbox_list)} 台")
        return xbox_list

    except Exception as e:
        logger.error(f"Xbox发现异常: {e}")
        return []


async def _test_xbox_connection(ip_address: str, logger) -> bool:
    """
    测试Xbox连接

    参数：
    - ip_address: Xbox IP地址
    - logger: 日志记录器

    返回：
    - bool: 是否在线
    """
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((ip_address, 5050))
        sock.close()

        online = result == 0
        logger.info(f"Xbox {ip_address} 连接测试: {'在线' if online else '离线'}")
        return online

    except Exception as e:
        logger.error(f"Xbox连接测试异常: {e}")
        return False


async def _connect_to_xbox(context: AgentTaskContext, logger) -> bool:
    """
    连接到Xbox主机

    参数：
    - context: 任务上下文
    - logger: 日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..xbox.stream_controller import XboxStreamController, StreamConfig

        xbox_controller = XboxStreamController()
        context.xbox_session = xbox_controller

        xbox_info = context.current_xbox
        xbox_token = context.xbox_tokens.xbox_token
        user_hash = context.xbox_tokens.user_hash

        logger.info(f"开始连接Xbox: {xbox_info.ip_address}")

        success = await xbox_controller.connect_with_token(
            xbox_ip=xbox_info.ip_address,
            xbox_token=xbox_token,
            user_hash=user_hash
        )

        if success:
            logger.info(f"Xbox连接成功: {xbox_info.name}")
            return True
        else:
            logger.error(f"Xbox连接失败: {xbox_info.ip_address}")
            return False

    except Exception as e:
        logger.error(f"连接Xbox异常: {e}")
        return False
