"""
暂停/恢复时的 input 释键、scene 同步与恢复重锚（回 Xbox 主页重走流程）。

暂停（input 层）：不论当前 scene，释放自动化按键并退出 play 模式，再关 InputGate。
恢复（流程层）：Guide 回 Xbox 主页，按 matches_completed_today / 转会阶段标记跳过已完成进度。
"""

from __future__ import annotations

from typing import List, Optional, Set

from ..core.logger import get_logger
from ..input.controller_protocol import ControllerSignal

# 与 step4 VALID_TASK_TYPES 对齐，避免循环 import
_PROGRESS_ACTIONS = frozenset({
    "auction_transfer",
    "squad_battle",
    "transfer_sqb_combo",
    "divisions_rivals",
    "weekend_league",
})


def _normalize_action(raw: Optional[str]) -> str:
    if raw in _PROGRESS_ACTIONS:
        return raw
    return "squad_battle"


def account_has_remaining_work(
    context,
    game_account,
    skipped: Optional[Set[str]] = None,
) -> bool:
    """
    账号在本轮自动化中是否仍有待执行进度。

    - auction_transfer：本会话每账号 1 轮转会（_transfer_phase_done_account_ids）
    - squad_battle：今日 SQB matches_completed_today vs target_matches
    - transfer_sqb_combo：转会未完成，或 SQB 未达今日上限
    """
    skipped = skipped or set()
    if game_account.id in skipped:
        return False

    action = _normalize_action(getattr(context, "game_action_type", None))
    transfer_done = getattr(context, "_transfer_phase_done_account_ids", set())

    if action == "auction_transfer":
        return game_account.id not in transfer_done

    sqb_done = context.matches_completed_today.get(game_account.id, 0)
    sqb_remaining = sqb_done < game_account.target_matches

    if action == "transfer_sqb_combo":
        if game_account.id not in transfer_done:
            return True
        return sqb_remaining

    return sqb_remaining


class ResumeReanchor(Exception):
    """Step4 内层循环因恢复重锚而中断，由账号外层 loop 接管。"""


def request_resume_reanchor(context) -> None:
    """平台 resume 时标记：下次 checkpoint 回 Xbox 主页并重走自动化。"""
    context._resume_reanchor_home = True


def resume_reanchor_pending(context) -> bool:
    return bool(getattr(context, "_resume_reanchor_home", False))


def raise_if_resume_reanchor(context) -> None:
    """内层循环在 wait_if_paused 返回后调用，将重锚交给账号外层 loop。"""
    if resume_reanchor_pending(context):
        raise ResumeReanchor()


def _resume_probe_scene_ids() -> List[int]:
    from configs.scene_transitions import (
        AUCTION_NAVIGATION_SCENES,
        SQB_NAVIGATION_SCENES,
        SQB_PREMATCH_PROBE_SCENES,
    )

    return list(
        dict.fromkeys(
            [1, 24, 203, 101, 126, 102, 190]
            + list(AUCTION_NAVIGATION_SCENES)
            + list(SQB_NAVIGATION_SCENES)
            + list(SQB_PREMATCH_PROBE_SCENES)
        )
    )


async def release_automation_input(context, task_logger=None) -> None:
    """
    释放自动化 input：退出 FC play loop，经 ungated 路径发送 zero（不受 InputGate 拦截）。
    """
    log = task_logger or get_logger("pause_input")

    stream_runtime = getattr(context, "_stream_runtime", None)
    if stream_runtime is not None:
        try:
            stream_runtime.exit_play_mode()
        except Exception as exc:
            log.debug("exit_play_mode 异常: %s", exc)

    protocol = getattr(context, "_controller_protocol", None)
    if protocol is not None:
        try:
            await protocol.send_manual_signal(ControllerSignal.zero())
        except Exception as exc:
            log.debug("发送 zero 释键失败: %s", exc)

    log.info("自动化 input 已释放 (zero + exit play)")


async def sync_scene_on_resume(context, task_logger=None) -> Optional[int]:
    """
    恢复前识别当前 scene（仅日志/诊断）；重锚以 go_to_xbox_home 为准。
    """
    log = task_logger or get_logger("pause_input")
    switcher = getattr(context, "_account_switcher", None)
    if switcher is None:
        log.warning("resume scene sync: account_switcher 未就绪")
        context._resume_scene_id = None
        return None

    probes = _resume_probe_scene_ids()
    scene_id = await switcher._detect_any_scene(probes, strict=False)
    context._resume_scene_id = scene_id
    if scene_id is not None:
        log.info("恢复前 scene 快照: scene=%s（重锚后将回 Xbox 主页）", scene_id)
    else:
        log.warning("恢复前 scene 快照: 未命中探测集")
    return scene_id


def first_incomplete_account_index(
    context,
    skipped: Optional[Set[str]] = None,
) -> int:
    """
    第一个仍有未完成进度的 game_account 下标；全部完成则返回 len(game_accounts)。
    """
    for index, ga in enumerate(context.game_accounts):
        if account_has_remaining_work(context, ga, skipped):
            return index
    return len(context.game_accounts)


async def checkpoint_resume_reanchor(
    context,
    switcher,
    task_logger,
    skipped: Optional[Set[str]] = None,
) -> Optional[int]:
    """
    若平台已 request 恢复重锚：Guide 回 Xbox 主页，返回应重启的 account_index。

    已完成进度由 account_has_remaining_work（SQB 今日计数 / 本会话转会标记）保证不重复。
    """
    if not resume_reanchor_pending(context):
        return None

    log = task_logger or get_logger("pause_input")
    context._resume_reanchor_home = False
    context._resume_scene_id = None

    await release_automation_input(context, log)

    home_ok = False
    if switcher is not None:
        home_ok = await switcher.go_to_xbox_home_for_resume()
    if not home_ok:
        log.warning("恢复重锚：未能确认 Xbox 主页，仍按进度重启账号 loop")

    restart_index = first_incomplete_account_index(context, skipped)
    context._resume_restart_account_index = restart_index

    if restart_index >= len(context.game_accounts):
        log.info("恢复重锚：全部账号今日任务已完成，无需继续")
    else:
        ga = context.game_accounts[restart_index]
        action = _normalize_action(getattr(context, "game_action_type", None))
        if action == "auction_transfer":
            log.info(
                "恢复重锚：从账号 [%s] %s 重启（本会话转会未完成）",
                restart_index,
                ga.gamertag,
            )
        else:
            done = context.matches_completed_today.get(ga.id, 0)
            log.info(
                "恢复重锚：从账号 [%s] %s 重启 (今日 SQB %s/%s)",
                restart_index,
                ga.gamertag,
                done,
                ga.target_matches,
            )
    return restart_index
