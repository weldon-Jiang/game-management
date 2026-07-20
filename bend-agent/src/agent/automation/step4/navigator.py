"""
Step4 游戏模式导航器
=================
从原 step4_game_automation.py 提取。职责:
- 转会市场导航 / SQB导航 / DR导航 / WL导航
- 转会轮次执行
- 手柄按钮发送
"""
import asyncio
from typing import Callable, Optional, Dict

from ..task.task_context import AgentTaskContext, GameAccountInfo
from ..input.controller_protocol import XboxButtonFlag
from .constants import NAVIGATION_CONFIG, UT_MENU_SCENE_IDS
from .post_match import _detect_screen_state

# 9️⃣ 游戏模式导航  (→ step4/navigator.py 候选)
#    转会/SQB/DR/WL 的导航 + 转会轮次执行
# ========================================================================

async def _navigate_to_game_mode(
    context: AgentTaskContext,
    game_action_type: str,
    task_logger,
    game_logger
) -> bool:
    """
    根据 game_action_type 导航到对应的游戏模式

    返回：SQB/组合模式 SQB 段是否导航成功；其他类型暂返回 True。
    """
    task_logger.info(f"开始导航到游戏模式: {game_action_type}")

    if game_action_type == 'auction_transfer':
        return await _navigate_to_auction(context, task_logger, game_logger)
    if game_action_type == 'squad_battle':
        return await _navigate_to_squad_battle(context, task_logger, game_logger)
    if game_action_type == 'divisions_rivals':
        await _navigate_to_dr(context, task_logger, game_logger)
        return True
    if game_action_type == 'weekend_league':
        await _navigate_to_weekend_league(context, task_logger, game_logger)
        return True

    task_logger.warning(f"未知的游戏操作类型: {game_action_type}，默认导航到SQB模式")
    return await _navigate_to_squad_battle(context, task_logger, game_logger)


async def _press_button(context: AgentTaskContext, button: XboxButtonFlag, duration: float = 0.3) -> bool:
    """
    发送手柄按钮信号

    参数：
    - context: 任务上下文
    - button: Xbox按钮 (XboxButtonFlag.A, XboxButtonFlag.B, etc.)
    - duration: 按下持续时间(秒)

    返回：
    - bool: 是否成功
    """
    try:
        if hasattr(context, '_controller_protocol') and context._controller_protocol:
            await context._controller_protocol.press_button(button, duration)
            return True
        else:
            return False
    except Exception as e:
        return False


async def _navigate_to_auction(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> bool:
    """
    导航到 UT 转会 Tab（scene 152）

    路径：127/147/149 → LB → 152（`AUCTION_UT_CHAIN` + `trim_auction_navigation_chain`）

    返回：是否到达转会 Tab（152）。
    """
    from configs.scene_transitions import (
        AUCTION_COMPLETE_SCENES,
        AUCTION_NAVIGATION_SCENES,
        trim_auction_navigation_chain,
    )

    task_logger.info("导航到转会 Tab (scene_transitions 链)")
    game_logger.info("[转会] 开始导航 (scene_transitions 链)")

    switcher = getattr(context, '_account_switcher', None)

    try:
        if not switcher:
            task_logger.error("[转会] account_switcher 未初始化")
            game_logger.error("[转会] account_switcher 未初始化")
            return False

        current = await switcher._detect_any_scene(
            AUCTION_NAVIGATION_SCENES, strict=False
        )
        chain = trim_auction_navigation_chain(current)
        if not chain:
            task_logger.info("[转会] 已在转会 Tab (scene152)，跳过导航")
            game_logger.info("[转会] 已在 scene152")
            return True

        task_logger.info(f"[转会] 当前 scene={current}，执行链: {chain}")
        game_logger.info(f"[转会] 链: {chain}")

        ok = await switcher.run_scene_transition_chain(
            chain,
            label="AUCTION",
            complete_scenes=AUCTION_COMPLETE_SCENES,
        )
        if ok:
            task_logger.info("[转会] 场景转移链完成")
            game_logger.info("[转会] 导航完成")
            return True

        task_logger.error("[转会] 场景转移链未完成")
        game_logger.error("[转会] 导航失败，请检查 logs/debug_scene*.png")
        return False

    except Exception as e:
        task_logger.error(f"[转会] 导航异常: {e}")
        game_logger.error(f"[转会] 导航异常: {e}")
        return False


async def _execute_transfer_round(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
) -> tuple:
    """
    执行一轮转会任务（最小闭环）：导航到 152 → 进入转会中心 → 返回 UT 主菜单。

    返回：(success, error_code, error_message)
    """
    from configs.scene_transitions import (
        AUCTION_ENTRY_DWELL_SEC,
        AUCTION_EXIT_DISMISS_TIMEOUT,
        AUCTION_NAVIGATION_SCENES,
    )

    task_logger.info(f"执行转会轮次: {game_account.gamertag}")
    game_logger.info("[转会] 开始 transfer_round")

    switcher = getattr(context, "_account_switcher", None)
    if not switcher:
        return False, "TRANSFER_SWITCHER_MISSING", "account_switcher 未初始化"

    on_menu = await _detect_screen_state(
        context, "MAIN_MENU", task_logger, game_logger
    )
    if not on_menu:
        task_logger.warning("[转会] 未确认 UT 主菜单，仍尝试导航")

    nav_ok = await _navigate_to_auction(context, task_logger, game_logger)
    if not nav_ok:
        await report_progress(
            context.task_id, "STEP4", "RUNNING",
            f"账号 {game_account.gamertag} 转会导航失败",
            {
                "gameAccountId": game_account.id,
                "gameAccountName": game_account.gamertag,
                "matchStatus": "TRANSFER_NAV_FAILED",
                "errorCode": "TRANSFER_NAV_FAILED",
            },
        )
        return False, "TRANSFER_NAV_FAILED", "转会场景导航失败"

    await report_progress(
        context.task_id, "STEP4", "RUNNING",
        f"账号 {game_account.gamertag} 已进入转会 Tab",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "TRANSFER_TAB",
        },
    )

    task_logger.info("[转会] 按 A 进入转会中心（占位）")
    game_logger.info("[转会] 进入转会中心")
    await switcher._press_button("A", duration=0.15)
    await asyncio.sleep(AUCTION_ENTRY_DWELL_SEC)

    task_logger.info("[转会] 返回 UT 主菜单")
    exit_ok = await switcher.dismiss_until_scenes(
        UT_MENU_SCENE_IDS,
        timeout=AUCTION_EXIT_DISMISS_TIMEOUT,
        label="TRANSFER-EXIT",
        probe_scene_ids=AUCTION_NAVIGATION_SCENES,
    )
    if not exit_ok:
        task_logger.warning("[转会] 返回 UT 主菜单超时，仍计为本轮完成")
        for _ in range(8):
            await switcher._press_button("B", duration=0.1)
            await asyncio.sleep(0.45)
            hit = await switcher._detect_any_scene(UT_MENU_SCENE_IDS, strict=False)
            if hit in UT_MENU_SCENE_IDS:
                exit_ok = True
                break

    await report_progress(
        context.task_id, "STEP4", "RUNNING",
        f"账号 {game_account.gamertag} 转会轮次完成",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "TRANSFER_ROUND_COMPLETE",
            "returnedToMenu": exit_ok,
        },
    )
    game_logger.info("[转会] transfer_round 完成")
    return True, None, None


async def _navigate_to_squad_battle(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> bool:
    """
    导航到 SQB 模式（读取 SCENE_TRANSITIONS 链）

    路径：147 → 149 → 155 → 156 → 168 → 177(业余A) → 183 → 189
    对齐 streaming get_scenes_diagram / configs.scene_transitions.SQB_UT_MENU_CHAIN

    返回：是否到达 SQB 赛前界面（189）或链执行成功。
    """
    from configs.scene_transitions import (
        SQB_COMPLETE_SCENES,
        SQB_NAVIGATION_SCENES,
        trim_sqb_navigation_chain,
    )

    task_logger.info("导航到SQB模式 (SCENE_TRANSITIONS 链)")
    game_logger.info("[SQB] 开始导航 (scene_transitions 链)")

    switcher = getattr(context, '_account_switcher', None)

    try:
        if not switcher:
            task_logger.error("[SQB] account_switcher 未初始化，无法执行场景转移链")
            game_logger.error("[SQB] account_switcher 未初始化")
            return False

        current = await switcher._detect_any_scene(
            SQB_NAVIGATION_SCENES, strict=False
        )
        chain = trim_sqb_navigation_chain(current)
        if not chain:
            task_logger.info("[SQB] 已在赛前界面 (scene189)，跳过导航")
            game_logger.info("[SQB] 已在 scene189")
            return True

        task_logger.info(f"[SQB] 当前 scene={current}，执行链: {chain}")
        game_logger.info(f"[SQB] 链: {chain}")

        ok = await switcher.run_scene_transition_chain(
            chain,
            label="SQB",
            complete_scenes=SQB_COMPLETE_SCENES,
        )
        if ok:
            task_logger.info("[SQB] 场景转移链完成，等待匹配")
            game_logger.info("[SQB] 导航完成")
            return True

        task_logger.error("[SQB] 场景转移链未完成")
        game_logger.error("[SQB] 导航失败，请检查 logs/debug_scene*.png")
        return False

    except Exception as e:
        task_logger.error(f"[SQB] 导航异常: {e}")
        game_logger.error(f"[SQB] 导航异常: {e}")
        return False


async def _navigate_to_dr(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> None:
    """
    导航到DR模式 (Division Rivals)

    导航路径：主页 → UT → Division Rivals → Play Champions → 开始匹配

    操作序列：
    1. 从主页按 RB×3 + A 进入 UT 菜单
    2. 按 LB×2 + A 进入 Division Rivals
    3. 按 A 选择 Play Champions
    4. 按 A 开始匹配
    """
    task_logger.info("导航到DR模式")
    game_logger.info("[DR] 开始导航到DR模式")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        task_logger.info("[DR] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Division Rivals：LB×2 + A
        task_logger.info("[DR] 步骤2: 进入Division Rivals (LB×2 + A)")
        for _ in range(2):
            await _press_button(context, XboxButtonFlag.L1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 3. 选择 Play Champions（默认选项，直接A）
        task_logger.info("[DR] 步骤3: 选择Play Champions")
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(1)

        # 4. 开始匹配
        task_logger.info("[DR] 步骤4: 开始匹配")
        await _press_button(context, XboxButtonFlag.A, 0.5)

        task_logger.info("[DR] 导航完成，等待匹配")
        game_logger.info("[DR] 导航完成")

    except Exception as e:
        task_logger.error(f"[DR] 导航异常: {e}")
        game_logger.error(f"[DR] 导航异常: {e}")


async def _navigate_to_weekend_league(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> None:
    """
    导航到周赛模式 (Weekend League)

    导航路径：主页 → UT → Weekend League → 资格检查 → 开始匹配

    操作序列：
    1. 从主页按 RB×3 + A 进入 UT 菜单
    2. 按 LB×3 + A 进入 Weekend League
    3. 检测资格状态
    4. 有资格则按 A 开始匹配，无资格则报错

    注意：需要DR段位达到Elite才能参加周赛
    """
    task_logger.info("导航到周赛模式")
    game_logger.info("[周赛] 开始导航到周赛模式")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        task_logger.info("[周赛] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Weekend League：LB×3 + A
        task_logger.info("[周赛] 步骤2: 进入Weekend League (LB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.L1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 3. 检查资格状态
        # TODO: 通过画面检测判断资格状态
        # 当前简化处理：假设有资格，直接开始匹配
        task_logger.info("[周赛] 步骤3: 检查资格...")

        # 4. 开始匹配（假设有资格）
        task_logger.info("[周赛] 步骤4: 开始匹配")
        await _press_button(context, XboxButtonFlag.A, 0.5)

        task_logger.info("[周赛] 导航完成，等待匹配")
        game_logger.info("[周赛] 导航完成")

    except Exception as e:
        task_logger.error(f"[周赛] 导航异常: {e}")
        game_logger.error(f"[周赛] 导航异常: {e}")


# ========================================================================
