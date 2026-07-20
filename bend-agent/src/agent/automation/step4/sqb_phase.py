"""
Step4 SQB 阶段
============
从原 step4_game_automation.py 提取。职责:
- 单账号 SQB 比赛阶段编排
"""
import asyncio
from typing import Optional

from ..task.task_context import AgentTaskContext, GameAccountInfo
from .task_routing import _normalize_game_action_type, _requires_sqb_phase, _account_exit_fc_reason

# 7️⃣ SQB 阶段  (→ step4/sqb_phase.py 候选)
# ========================================================================

async def _run_sqb_phase_for_account(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    game_action_type: str,
    task_logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    platform_client: Optional[Any],
    stream_runtime,
    pause_after_match: Optional[Callable[[], bool]],
    keep_session_alive: bool,
    window_manager,
    completed_matches: int,
) -> tuple:
    """
    SQB 比赛阶段：进入 FC/UT 后执行（组合模式在转会阶段之后自动进入）。

    返回 (fatal Step4Result 或 None, 本轮新完成的比赛数)
    """
    consecutive_failures = 0
    max_match_failures = 3
    delta = 0
    target = game_account.target_matches

    task_logger.info(
        "[SQB阶段] 账号 %s 目标 %s 场 (mode=%s)",
        game_account.gamertag,
        target,
        game_action_type,
    )
    game_logger.info(f"[SQB阶段] 目标 {target} 场")

    while context.matches_completed_today[game_account.id] < target:
        if check_cancel():
            return (
                Step4Result(
                    success=False,
                    error_code="CANCELLED",
                    message="任务被取消",
                ),
                delta,
            )

        await context.wait_if_paused()
        from ..runtime.pause_input_control import raise_if_resume_reanchor

        raise_if_resume_reanchor(context)

        current_count = context.matches_completed_today[game_account.id] + 1
        current_total = context.matches_completed_today[game_account.id]

        await report_progress(
            context.task_id,
            "STEP4",
            "RUNNING",
            f"账号 {game_account.gamertag} 准备 SQB 第 {current_count} 场 "
            f"(今日 {current_total}/{target})",
            {
                "gameAccountId": game_account.id,
                "gameAccountName": game_account.gamertag,
                "currentMatch": current_count,
                "todayCompleted": current_total,
                "dailyLimit": target,
                "matchStatus": "PREPARING",
                "gameActionType": game_action_type,
            },
        )
        game_logger.info(
            f"SQB 第 {current_count} 场 (今日 {current_total}/{target})"
        )

        match_success = False
        cleanup_needed = True
        try:
            match_success, match_error_code, match_error_msg = (
                await _execute_match_for_account(
                    context,
                    game_account,
                    task_logger,
                    game_logger,
                    check_cancel,
                    report_progress,
                    frame_queue=stream_runtime.frame_queue,
                    scene_queue=stream_runtime.scene_queue,
                )
            )
            cleanup_needed = False
        finally:
            if cleanup_needed:
                await _cleanup_account_resources(
                    context, game_account, task_logger, game_logger
                )

        if pause_after_match and pause_after_match():
            from ..runtime.pause_input_control import release_automation_input

            await release_automation_input(context, task_logger)
            context.pause()
            await report_progress(
                context.task_id,
                "STEP4",
                "RUNNING",
                "本场完成后暂停",
                {"matchStatus": "PAUSE_AFTER_MATCH"},
            )
            await context.wait_if_paused()
            from ..runtime.pause_input_control import raise_if_resume_reanchor

            raise_if_resume_reanchor(context)

        if match_success:
            consecutive_failures = 0
            context.matches_completed_today[game_account.id] += 1
            delta += 1
            new_completed = context.matches_completed_today[game_account.id]

            task_logger.info(
                "账号 %s 完成 SQB 第 %s 场, 今日 %s/%s",
                game_account.gamertag,
                current_count,
                new_completed,
                target,
            )
            game_logger.info(
                f"完成 SQB 第 {current_count} 场, 今日 {new_completed}/{target}"
            )

            is_account_completed = new_completed >= target
            await _report_billable_event(
                context,
                platform_client,
                game_account,
                game_action_type,
                _resolve_billing_unit(game_action_type, phase="match"),
                current_count,
                task_logger,
            )
            await report_progress(
                context.task_id,
                "STEP4",
                "COMPLETED" if is_account_completed else "RUNNING",
                f"账号 {game_account.gamertag} 完成 SQB 第 {current_count} 场, "
                f"今日 {new_completed}/{target}",
                {
                    "gameAccountId": game_account.id,
                    "gameAccountName": game_account.gamertag,
                    "currentMatch": current_count,
                    "todayCompleted": new_completed,
                    "dailyLimit": target,
                    "matchStatus": "COMPLETED",
                    "accountCompleted": is_account_completed,
                },
            )
        else:
            consecutive_failures += 1
            task_logger.warning(
                "账号 %s SQB 第 %s 场失败: %s",
                game_account.gamertag,
                current_count,
                match_error_msg,
            )
            game_logger.warning(
                f"SQB 第 {current_count} 场失败: {match_error_msg}"
            )
            await report_progress(
                context.task_id,
                "STEP4",
                "RUNNING",
                f"账号 {game_account.gamertag} SQB 第 {current_count} 场失败，将继续",
                {
                    "gameAccountId": game_account.id,
                    "gameAccountName": game_account.gamertag,
                    "currentMatch": current_count,
                    "todayCompleted": current_total,
                    "dailyLimit": target,
                    "matchStatus": "FAILED",
                    "matchErrorCode": match_error_code,
                    "matchErrorMessage": match_error_msg,
                },
            )
            if consecutive_failures >= max_match_failures:
                error_msg = (
                    f"账号 {game_account.gamertag} 连续 {consecutive_failures} "
                    "次 SQB 失败，停止该轮自动化以保留串流供重试"
                )
                task_logger.error(error_msg)
                game_logger.error(error_msg)
                context.update_step_status(
                    "step4", TaskStepStatus.FAILED, error_msg
                )
                await _report_step4_failure(
                    context,
                    report_progress,
                    error_msg,
                    keep_session_alive,
                    task_logger,
                )
                if not keep_session_alive:
                    await _close_task_window(
                        window_manager,
                        context.task_id,
                        "match_fail_bound",
                        task_logger,
                    )
                return (
                    Step4Result(
                        success=False,
                        error_code="NO_MATCHES_COMPLETED",
                        message=error_msg,
                        total_matches=completed_matches + delta,
                    ),
                    delta,
                )
            await asyncio.sleep(5)

    return None, delta


# ========================================================================
