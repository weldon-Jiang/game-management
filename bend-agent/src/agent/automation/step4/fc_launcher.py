"""
Step4 FC 启动与账号切换
=====================
从原 step4_game_automation.py 提取。职责:
- 手动/自动 FC 启动控制
- Xbox 主页检测 + FC 重试启动
- Step4 失败上报 + 输入通道保障
- 账号跳过切换 + 输入通道事件上报
"""
import asyncio
import time
from typing import Callable, Optional

from ..task.task_context import AgentTaskContext, GameAccountInfo, TaskMainStatus

async def _pause_for_manual_fc_launch(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    reason: str,
    error_code: str,
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    check_cancel: Callable[[], bool],
    task_logger,
    stream_logger,
) -> bool:
    """
    暂停 Step4 供人工恢复 FC，并等待平台 resume。

    保持串流/窗口不关闭，会话标记为 paused 以便用户操作 Xbox 窗口。
    仅在等待期间任务被取消时返回 False。
    """
    from ..runtime.phase_fsm import SessionPhase
    from ..runtime.pause_input_control import release_automation_input

    await release_automation_input(context, task_logger)
    context.pause()
    context.update_task_status(TaskMainStatus.PAUSED)

    if set_session_phase:
        await set_session_phase(SessionPhase.PAUSED_IMMEDIATE, reason)
    else:
        await report_progress(
            context.task_id,
            "SESSION",
            "RUNNING",
            reason,
            {
                "scope": "session",
                "phase": SessionPhase.PAUSED_IMMEDIATE.value,
                "pauseMode": "immediate",
            },
        )

    await report_progress(
        context.task_id,
        "STEP4",
        "RUNNING",
        reason,
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "MANUAL_REQUIRED",
            "accountStatus": "paused",
            "errorCode": error_code,
            "errorDetails": reason,
        },
    )
    task_logger.warning("自动化已暂停，等待人工处理后恢复: %s", reason)
    stream_logger.warning(reason)

    while context.is_paused():
        if check_cancel():
            return False
        await asyncio.sleep(0.3)

    from ..runtime.pause_input_control import raise_if_resume_reanchor

    raise_if_resume_reanchor(context)

    context.update_task_status(TaskMainStatus.RUNNING)
    if set_session_phase:
        await set_session_phase(
            SessionPhase.AUTOMATING,
            "人工处理完成，继续尝试启动 FC",
        )
    task_logger.info("任务已恢复，重新尝试启动 FC")
    stream_logger.info("任务已恢复，重新尝试启动 FC")
    return True


async def _launch_fc_with_manual_pause(
    switcher,
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    task_logger,
    stream_logger,
) -> bool:
    """
    Launch FC/UT and convert recoverable launch blockers into a manual pause.

    ManualInterventionRequired means the stream is healthy but automation cannot
    advance safely. Pausing avoids closing Step1-3 resources and lets the user
    correct the screen before Step4 retries.
    """
    from ..game.account_switcher import ManualInterventionRequired
    from ..runtime.pause_input_control import ResumeReanchor

    while True:
        try:
            return await switcher.launch_fc_to_ut_menu()
        except ResumeReanchor:
            raise
        except ManualInterventionRequired as exc:
            reason = f"账号 {game_account.gamertag}：{exc.reason}"
            resumed = await _pause_for_manual_fc_launch(
                context,
                game_account,
                reason,
                exc.error_code,
                report_progress,
                set_session_phase,
                check_cancel,
                task_logger,
                stream_logger,
            )
            if not resumed:
                return False


# 启动 FC 失败但仍停留 Xbox 主页时，重启启动链的最大次数
FC_LAUNCH_HOME_RETRY_MAX = 3


async def _retry_fc_launch_if_on_home(
    switcher,
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    task_logger,
    stream_logger,
) -> bool:
    """
    启动 FC 失败后，若画面仍停留 Xbox 主页(scene203)，重启 FC 启动链而非空等跳过。

    背景：MAIN_MENU 仅匹配 UT 场景 [127,149,147,101]，在 Xbox 主页恒超时（25s），
    导致「切换成功 -> MAIN_MENU 盲等 -> 跳过账号」的死循环。此处在确认仍在主页时
    重启启动链；若多次仍停 203，启动链内部会抛出 ManualInterventionRequired 转入暂停。

    返回：True 表示重启后已进入 FC/UT；False 表示已离开主页（交由 MAIN_MENU 校验）
    或重试耗尽。
    """
    for attempt in range(1, FC_LAUNCH_HOME_RETRY_MAX + 1):
        if check_cancel():
            return False

        try:
            on_home = await switcher._is_home_203_dominant()
        except Exception as exc:
            task_logger.debug("主页 203 检测异常，跳过重启逻辑: %s", exc)
            return False

        if not on_home:
            task_logger.info("启动 FC 失败但已离开 Xbox 主页，交由 MAIN_MENU 校验")
            return False

        retry_msg = (
            f"账号 {game_account.gamertag} 启动 FC 失败且仍停留 Xbox 主页(scene203)，"
            f"重启 FC 启动链（第 {attempt}/{FC_LAUNCH_HOME_RETRY_MAX} 次）"
        )
        task_logger.warning(retry_msg)
        stream_logger.warning(retry_msg)

        launch_ok = await _launch_fc_with_manual_pause(
            switcher,
            context,
            game_account,
            check_cancel,
            report_progress,
            set_session_phase,
            task_logger,
            stream_logger,
        )
        if launch_ok:
            return True
        await asyncio.sleep(2.0)

    task_logger.error(
        "账号 %s 多次重启 FC 启动链后仍停留 Xbox 主页，放弃该账号",
        game_account.gamertag,
    )
    return False


async def _report_step4_failure(
    context: AgentTaskContext,
    report_progress: Callable,
    error_msg: str,
    keep_session_alive: bool,
    task_logger,
) -> None:
    """
    上报 Step4 失败，区分终态或可重试会话语义。

    keep_session_alive=True 用于两阶段任务：Step4 失败将会话置为 automation_failed，
    同时保留串流/窗口资源。
    """
    if keep_session_alive:
        task_logger.error("%s (stream kept alive for retry)", error_msg)
        window_state = "visible" if getattr(context, "sdl_window", None) else "hidden"
        await report_progress(
            context.task_id,
            "SESSION",
            "RUNNING",
            error_msg,
            {
                "scope": "session",
                "phase": "automation_failed",
                "windowState": window_state,
            },
        )
        from ..xbox.stream_session_survival import (
            schedule_ensure_stream_subsystems_alive,
        )

        schedule_ensure_stream_subsystems_alive(
            context, reason="automation_failed"
        )
        return
    task_logger.error(error_msg)
    await report_progress(context.task_id, "STEP4", "FAILED", error_msg)


async def _ensure_input_for_step4(context: AgentTaskContext, task_logger) -> bool:
    """
    Step4 自动化前确认 input DataChannel 为 open；closed 时同步触发重连回调。
    """
    from ..xbox.stream_keepalive import is_input_channel_open

    session = getattr(context, "xbox_session", None)
    if session is not None and is_input_channel_open(session):
        return True

    callback = getattr(context, "_input_reconnect_callback", None)
    if callback is None:
        task_logger.error("input DataChannel 已关闭且无重连回调")
        return False

    task_logger.warning("Step4 检测到 input DataChannel 已关闭，开始重连")
    try:
        ok = await callback()
    except Exception as exc:
        task_logger.error("input DataChannel 重连异常: %s", exc)
        return False
    if not ok:
        task_logger.error("input DataChannel 重连失败")
    return ok


async def _switch_to_next_game_account_on_skip(
    context: AgentTaskContext,
    switcher,
    account_index: int,
    task_logger,
) -> bool:
    """
    预检判定当前账号无剩余进度时，若有下一账号则走 Xbox switch_to 切档（不进 FC）。
    """
    next_index = account_index + 1
    if next_index >= len(context.game_accounts):
        return True

    if not await _ensure_input_for_step4(context, task_logger):
        task_logger.warning("预检跳过：切下一账号前 input 不可用")
        return False

    next_ga = context.game_accounts[next_index]
    from ..core.config import config as app_config

    skip_switch = bool(app_config.get("step4.skip_account_switch", False))
    if skip_switch:
        result = await switcher.prepare_without_switch(next_ga.id)
    else:
        result = await switcher.ensure_target_game_account(next_ga.id)

    if result.success:
        task_logger.info(
            "账号 %s 无剩余进度，已切至下一账号 %s",
            context.game_accounts[account_index].gamertag,
            next_ga.gamertag,
        )
    else:
        task_logger.warning(
            "账号 %s 无剩余进度，切至 %s 失败: %s",
            context.game_accounts[account_index].gamertag,
            next_ga.gamertag,
            result.error_message,
        )
    return result.success


async def _report_input_channel_event(
    context: AgentTaskContext,
    report_progress: Callable,
    status: str,
    message: str,
    phase: str,
    task_logger,
) -> None:
    """上报 input 通道恢复，不改变任务终态。"""
    try:
        await report_progress(
            context.task_id,
            "INPUT_CHANNEL",
            status,
            message,
            {
                "scope": "session",
                "module": "input_channel",
                "phase": phase,
            },
        )
    except Exception as exc:
        task_logger.warning("上报 DataChannel 恢复事件失败: %s", exc)


