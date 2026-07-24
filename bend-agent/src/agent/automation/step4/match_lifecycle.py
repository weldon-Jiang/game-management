"""
Step4 比赛生命周期
===============
从原 step4_game_automation.py 提取。职责:
- 进入比赛 (_enter_match)
- 等待比赛开始 (_wait_for_match_start)
- 比赛进行中 (_play_match)
- 完成比赛 (_finish_match)
"""
import asyncio
import time
from typing import Callable, Optional, Dict

from ...task.task_context import AgentTaskContext, GameAccountInfo
from .constants import NAVIGATION_CONFIG
from .task_routing import _normalize_game_action_type
from .setup import _fc_init_match_session, _fc_terminate_match_session
from .post_match import _detect_screen_state, _wait_for_match_started, _detect_match_ended, _skip_settlement
from .navigator import _navigate_to_game_mode

# 🔟 比赛生命周期  (→ step4/match_lifecycle.py 候选)
#    进入比赛 → 等待开始 → 进行中 → 完成
# ========================================================================

async def _enter_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
) -> bool:
    """
    进入比赛准备

    返回：False 表示 SQB 等导航失败，调用方应跳过本场。
    """
    task_logger.info(f"进入比赛准备: {game_account.gamertag}")
    game_logger.info("[场景: MAIN_MENU] 进入比赛准备")

    screen_detected = await _detect_screen_state(
        context, "MAIN_MENU", task_logger, game_logger
    )
    task_logger.info(f"游戏主界面检测: {screen_detected}")

    # 组合模式转会阶段结束后，SQB 导航/比赛固定走 squad_battle 路径
    game_action_type = _normalize_game_action_type(context.game_action_type)
    nav_mode = (
        'squad_battle'
        if game_action_type in ('transfer_sqb_combo', 'squad_battle')
        else game_action_type
    )
    task_logger.info(f"SQB 比赛导航模式: {nav_mode} (task={game_action_type})")

    nav_ok = await _navigate_to_game_mode(
        context, nav_mode, task_logger, game_logger
    )
    if not nav_ok:
        task_logger.error("[SQB] 导航失败，跳过本场比赛")
        game_logger.error("[SQB] 导航失败")
        await report_progress(
            context.task_id, "STEP4", "RUNNING",
            f"账号 {game_account.gamertag} SQB 导航失败",
            {
                "gameAccountId": game_account.id,
                "gameAccountName": game_account.gamertag,
                "matchStatus": "SQB_NAV_FAILED",
                "errorCode": "SQB_NAV_FAILED",
            },
        )
        return False

    await report_progress(
        context.task_id, "STEP4", "GAME_PREPARING",
        f"账号 {game_account.gamertag} 导航到 {nav_mode} 完成",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "gameActionType": game_action_type,
            "navMode": nav_mode,
            "todayCompleted": context.matches_completed_today[game_account.id],
            "dailyLimit": game_account.target_matches,
            "matchStatus": "PREPARING"
        }
    )

    if nav_mode == "squad_battle":
        switcher = getattr(context, "_account_switcher", None)
        if switcher:
            from configs.scene_transitions import (
                SQB_PREMATCH_DISMISS_TIMEOUT,
                SQB_PREMATCH_PROBE_SCENES,
                SQB_PREMATCH_TARGETS,
            )

            task_logger.info("[SQB] 赛前弹窗处理：189 → 开球")
            game_logger.info("[SQB] dismiss_until_scenes 开球前")
            kickoff_ok = await switcher.dismiss_until_scenes(
                SQB_PREMATCH_TARGETS,
                timeout=SQB_PREMATCH_DISMISS_TIMEOUT,
                label="SQB-PREMATCH",
                probe_scene_ids=SQB_PREMATCH_PROBE_SCENES,
            )
            if not kickoff_ok:
                task_logger.error("[SQB] 开球前场景处理超时")
                game_logger.error("[SQB] 开球前超时")
                await report_progress(
                    context.task_id, "STEP4", "RUNNING",
                    f"账号 {game_account.gamertag} SQB 开球前超时",
                    {
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "matchStatus": "SQB_KICKOFF_FAILED",
                        "errorCode": "SQB_KICKOFF_FAILED",
                    },
                )
                return False

    await asyncio.sleep(1)
    return True


async def _wait_for_match_start(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    等待比赛开始

    状态上报：比赛正式开始 (GAMING)

    画面检测：
    - 检测匹配中画面
    - 检测比赛加载画面
    - 检测比赛正式开始
    """
    task_logger.info(f"比赛正式开始: {game_account.gamertag}")
    game_logger.info("[场景: MATCHMAKING] 比赛正式开始")

    match_started = await _wait_for_match_started(
        context, task_logger, game_logger
    )

    await report_progress(
        context.task_id, "STEP4", "GAMING",
        f"账号 {game_account.gamertag} 比赛开始！",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "todayCompleted": context.matches_completed_today[game_account.id],
            "dailyLimit": game_account.target_matches,
            "matchStatus": "STARTED",
            "matchStarted": match_started
        }
    )

    await asyncio.sleep(3)

    if not await _fc_init_match_session(context, task_logger):
        task_logger.warning("FC 比赛会话初始化失败，仍尝试本地 play loop")

    runtime = getattr(context, "_stream_runtime", None)
    if runtime:
        runtime.enter_play_mode()


async def _play_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    frame_queue: Optional[asyncio.Queue] = None,
    scene_queue: Optional[asyncio.Queue] = None
):
    """
    进行比赛

    状态上报：比赛进行中 (GAMING，每30秒上报一次)

    画面检测：
    - 使用全局异步任务检测场景
    - 从全局scene_queue获取检测结果
    - 根据检测到的场景执行对应的足球动作
    - 检测比赛是否异常结束
    - 检测比赛是否正常结束

    参数：
    - context: 任务上下文（包含 frame_capture）
    - frame_queue: 全局帧队列（可选）
    - scene_queue: 全局场景队列（可选）
    """
    match_duration = 1200

    task_logger.info(f"比赛中，预计时长: {match_duration}秒")
    game_logger.info(f"[场景: IN_GAME] 比赛中，预计时长: {match_duration}秒")

    if getattr(context, "_fc_remote_play", False):
        runtime = getattr(context, "_stream_runtime", None)
        if runtime:
            from ...runtime.pause_input_control import raise_if_resume_reanchor

            task_logger.info("[比赛进行] FC PLAY loop 已接管（StreamRuntime play 20Hz）")
            deadline = time.monotonic() + match_duration
            while time.monotonic() < deadline:
                if check_cancel():
                    raise RuntimeError("比赛被取消")
                if context.is_paused():
                    await context.wait_if_paused()
                    raise_if_resume_reanchor(context)
                if runtime.match_over.is_set():
                    task_logger.info("FC 报告比赛结束 (ERR_MATCH_OVER)")
                    game_logger.info("[场景: SETTLEMENT] FC 比赛结束")
                    return
                try:
                    await asyncio.wait_for(runtime.match_over.wait(), timeout=2.0)
                    task_logger.info("FC 报告比赛结束 (ERR_MATCH_OVER)")
                    game_logger.info("[场景: SETTLEMENT] FC 比赛结束")
                    return
                except asyncio.TimeoutError:
                    continue
            task_logger.info("FC 比赛等待超时，按本地时长结束")
            return

    from .in_match_controller import run_local_in_match_loop

    async def _progress(elapsed: int, total: int) -> None:
        progress_pct = min(100, int(elapsed / total * 100)) if total else 0
        current_count = context.matches_completed_today[game_account.id] + 1
        target = game_account.target_matches
        task_logger.info(
            "比赛进行中... (%s/%s秒, %s%%)",
            elapsed, total, progress_pct,
        )
        game_logger.info(
            "[场景: IN_GAME] 比赛进行中... (%s/%s秒)",
            elapsed, total,
        )
        await report_progress(
            context.task_id, "STEP4", "GAMING",
            f"账号 {game_account.gamertag} 比赛中 ({elapsed}/{total}秒)",
            {
                "gameAccountId": game_account.id,
                "gameAccountName": game_account.gamertag,
                "currentMatch": current_count,
                "todayCompleted": context.matches_completed_today[game_account.id],
                "dailyLimit": target,
                "matchStatus": "IN_PROGRESS",
                "elapsedSeconds": elapsed,
                "totalSeconds": total,
                "progressPercent": progress_pct,
            },
        )

    task_logger.info("[比赛进行] 场中自动化（scene 长按 A + 摇杆/面键占位）")
    context._step4_in_match_active = True
    try:
        await run_local_in_match_loop(
            context,
            task_logger,
            check_cancel,
            lambda: _detect_match_ended(context, task_logger, game_logger),
            match_duration=float(match_duration),
            on_progress=_progress,
        )
    finally:
        context._step4_in_match_active = False


async def _finish_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    完成比赛

    状态上报：比赛结束

    画面检测：
    - 检测比赛结束画面
    - 跳过结算画面
    - 返回游戏主界面
    """
    task_logger.info(f"比赛结束: {game_account.gamertag}")
    game_logger.info("[场景: MATCH_END] 比赛结束")

    runtime = getattr(context, "_stream_runtime", None)
    if runtime:
        runtime.exit_play_mode()
    await _fc_terminate_match_session(context, task_logger)

    await _skip_settlement(context, task_logger, game_logger)

