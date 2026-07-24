"""
Step4 任务类型路由与计费
=====================
从原 step4_game_automation.py 提取。职责:
- 任务类型规范化/校验
- 阶段路由判断(转会/SQB)
- 计费事件上报
"""
from typing import Optional, Dict, Any

from ...task.task_context import AgentTaskContext, GameAccountInfo
from .constants import VALID_TASK_TYPES


def _normalize_game_action_type(game_action_type: Optional[str]) -> str:
    if game_action_type and game_action_type in VALID_TASK_TYPES:
        return game_action_type
    return 'squad_battle'


def _apply_task_type(context: AgentTaskContext, game_account: GameAccountInfo, task_logger) -> str:
    """
    进入 FC/UT 主菜单后应用平台 gameActionType（AGENTS R006/R007）。

    此后按类型分两阶段（可只执行其一）：
    - auction_transfer：仅转会，完成后退出 FC（不进 SQB）
    - squad_battle：仅 SQB 比赛
    - transfer_sqb_combo：先 1 轮转会，再 SQB 打满 target_matches，全部完成后退出 FC

    返回归一化后的 game_action_type 字符串。
    """
    game_action_type = _normalize_game_action_type(context.game_action_type)
    if game_action_type == 'auction_transfer':
        task_logger.info(
            "游戏操作类型 auction_transfer: 进入 FC 后执行转会任务（本会话 1 轮）"
        )
    elif game_action_type == 'squad_battle':
        task_logger.info("游戏操作类型 squad_battle: 进入 FC 后直接 SQB 比赛")
    elif game_action_type == 'divisions_rivals':
        task_logger.info("游戏操作类型 divisions_rivals: DR模式（与玩家线上对战）")
    elif game_action_type == 'weekend_league':
        task_logger.info("游戏操作类型 weekend_league: 周赛")
    elif game_action_type == 'transfer_sqb_combo':
        task_logger.info(
            "游戏操作类型 transfer_sqb_combo: 进入 FC 后先转会 1 轮，再 SQB %s 场",
            game_account.target_matches,
        )
    else:
        task_logger.info(f"游戏操作类型 {game_action_type}: 执行默认SQB模式")
    return game_action_type


def _requires_transfer_phase(game_action_type: str) -> bool:
    """进入 FC 后是否需要执行转会阶段。"""
    return _normalize_game_action_type(game_action_type) in (
        'auction_transfer',
        'transfer_sqb_combo',
    )


def _requires_sqb_phase(game_action_type: str) -> bool:
    """进入 FC 后是否需要执行 SQB 比赛阶段。"""
    return _normalize_game_action_type(game_action_type) in (
        'squad_battle',
        'transfer_sqb_combo',
    )


def _transfer_rounds_target(game_action_type: str, game_account: GameAccountInfo) -> int:
    """
    单账号转会阶段目标轮数。
    - auction_transfer：固定 1 轮（不占 SQB 今日上限）
    - transfer_sqb_combo：固定 1 轮，完成后自动接 SQB
    """
    action = _normalize_game_action_type(game_action_type)
    if action in ('auction_transfer', 'transfer_sqb_combo'):
        return 1
    return 0


def _account_exit_fc_reason(game_action_type: str) -> str:
    """单账号 FC 内任务全部完成后，退出回 Xbox 主页的日志说明。"""
    action = _normalize_game_action_type(game_action_type)
    if action == 'auction_transfer':
        return '转会任务已完成（未进入 SQB）'
    if action == 'transfer_sqb_combo':
        return '转会 + SQB 已全部完成'
    if action == 'squad_battle':
        return 'SQB 比赛已全部完成'
    return '账号自动化已完成'


def _account_needs_transfer_phase(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    game_action_type: str,
) -> bool:
    """
    当前账号是否仍需转会阶段（本会话每账号 1 轮；恢复重锚后跳过已完成）。
    """
    action = _normalize_game_action_type(game_action_type)
    if action in ("auction_transfer", "transfer_sqb_combo"):
        done_ids = getattr(context, "_transfer_phase_done_account_ids", set())
        return game_account.id not in done_ids
    return False


def _resolve_billing_unit(game_action_type: str, *, phase: str) -> str:
    """
    解析计费单元。

    phase: 'transfer' | 'match'
    """
    if phase == 'transfer':
        return 'transfer_round'
    return 'match_completed'


async def _report_billable_event(
    context: AgentTaskContext,
    platform_client: Optional[Any],
    game_account: GameAccountInfo,
    game_action_type: str,
    billing_unit: str,
    unit_index: int,
    task_logger,
) -> None:
    """上报计费事件；回调失败不阻塞 Step4 执行。"""
    if platform_client is None:
        return
    reporter = getattr(platform_client, 'report_billing_event', None)
    if reporter is None:
        return
    try:
        result = await reporter(
            context.task_id,
            game_account.id,
            game_action_type,
            billing_unit,
            unit_index,
            session_id=getattr(context, 'session_id', None),
            metadata={
                "gameAccountName": game_account.gamertag,
            },
        )
        if result.get("success") is False:
            task_logger.warning(
                "计费事件上报失败 - task=%s account=%s unit=%s index=%s error=%s",
                context.task_id,
                game_account.id,
                billing_unit,
                unit_index,
                result.get("error"),
            )
    except Exception as exc:
        task_logger.warning(
            "计费事件上报异常 - task=%s account=%s unit=%s index=%s error=%s",
            context.task_id,
            game_account.id,
            billing_unit,
            unit_index,
            exc,
        )
