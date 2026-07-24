"""
Step4 转会阶段
===========
从原 step4_game_automation.py 提取。职责:
- 单账号转会阶段编排
"""
import asyncio
from typing import Any, Callable, Dict, Optional

from ...task.task_context import AgentTaskContext, GameAccountInfo
from .task_routing import _normalize_game_action_type, _transfer_rounds_target, _account_needs_transfer_phase
from .navigator import _navigate_to_auction, _execute_transfer_round
from .post_match import _detect_screen_state

# 6️⃣ 转会阶段  (→ step4/transfer_phase.py 候选)
# ========================================================================

async def _run_transfer_phase_for_account(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    game_action_type: str,
    task_logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    platform_client: Optional[Any],
    target_rounds: int,
) -> tuple:
    """
    转会阶段：进入 FC/UT 后执行，与 SQB 比赛阶段分离。

    返回 (fatal Step4Result 或 None, 完成的转会轮数)
    """
    if target_rounds <= 0:
        return None, 0

    action = _normalize_game_action_type(game_action_type)
    rounds_done = 0
    consecutive_failures = 0
    max_failures = 3

    task_logger.info(
        "[转会阶段] 账号 %s 目标 %s 轮 (mode=%s)",
        game_account.gamertag,
        target_rounds,
        action,
    )
    game_logger.info(f"[转会阶段] 目标 {target_rounds} 轮")

    while rounds_done < target_rounds:
        if check_cancel():
            return (
                Step4Result(
                    success=False, error_code="CANCELLED", message="任务被取消"
                ),
                rounds_done,
            )

        await context.wait_if_paused()
        from ...runtime.pause_input_control import raise_if_resume_reanchor

        raise_if_resume_reanchor(context)

        round_no = rounds_done + 1
        await report_progress(
            context.task_id,
            "STEP4",
            "RUNNING",
            f"账号 {game_account.gamertag} 转会第 {round_no}/{target_rounds} 轮",
            {
                "gameAccountId": game_account.id,
                "gameAccountName": game_account.gamertag,
                "currentTransferRound": round_no,
                "transferTarget": target_rounds,
                "matchStatus": "TRANSFER_PREPARING",
                "gameActionType": game_action_type,
            },
        )

        success, error_code, error_msg = await _execute_transfer_round(
            context,
            game_account,
            task_logger,
            game_logger,
            report_progress,
        )
        if success:
            consecutive_failures = 0
            rounds_done += 1

            await _report_billable_event(
                context,
                platform_client,
                game_account,
                game_action_type,
                _resolve_billing_unit(game_action_type, phase="transfer"),
                round_no,
                task_logger,
            )
            task_logger.info(
                "账号 %s 完成转会第 %s/%s 轮",
                game_account.gamertag,
                round_no,
                target_rounds,
            )
            game_logger.info(f"[转会阶段] 完成第 {round_no}/{target_rounds} 轮")

            if action == 'transfer_sqb_combo' and round_no >= target_rounds:
                task_logger.info(
                    "账号 %s 转会阶段完成，即将进入 SQB 比赛阶段",
                    game_account.gamertag,
                )
                game_logger.info("[转会阶段] 完成，接 SQB")
        else:
            consecutive_failures += 1
            task_logger.warning(
                "账号 %s 转会第 %s 轮失败: %s",
                game_account.gamertag,
                round_no,
                error_msg,
            )
            game_logger.warning(f"[转会阶段] 第 {round_no} 轮失败: {error_msg}")
            await report_progress(
                context.task_id,
                "STEP4",
                "RUNNING",
                f"账号 {game_account.gamertag} 转会第 {round_no} 轮失败",
                {
                    "gameAccountId": game_account.id,
                    "gameAccountName": game_account.gamertag,
                    "matchStatus": "TRANSFER_FAILED",
                    "matchErrorCode": error_code,
                    "matchErrorMessage": error_msg,
                },
            )
            if consecutive_failures >= max_failures:
                error_msg_full = (
                    f"账号 {game_account.gamertag} 连续 {consecutive_failures} "
                    "次转会失败，停止该轮自动化"
                )
                task_logger.error(error_msg_full)
                context.update_step_status(
                    "step4", TaskStepStatus.FAILED, error_msg_full
                )
                return (
                    Step4Result(
                        success=False,
                        error_code=error_code or "TRANSFER_FAILED",
                        message=error_msg_full,
                    ),
                    rounds_done,
                )
            await asyncio.sleep(5)

    if rounds_done >= target_rounds:
        context._transfer_phase_done_account_ids.add(game_account.id)

    return None, rounds_done


# ========================================================================
