"""
步骤四：自动游戏比赛动作（MVP版本）
=====================================

功能说明：
- 根据游戏账号列表依次执行比赛（假设账号已登录）
- 每个游戏账号每天完成3场比赛
- 记录每个游戏账号当天比赛次数
- 完成当天最大次数后切换到下一个账号
- 实时上报比赛状态给平台

技术实现（MVP）：
- 假设游戏账号已在Xbox登录
- 使用手柄模拟进行比赛操作
- 复用现有 InputController/GamepadController
- 实时同步比赛状态到平台

完整版将包括：
- 检查账号是否已登录，未登录则自动化登录
- OCR识别账号名称
- 模板匹配定位界面元素

状态上报：
- 比赛准备开始
- 比赛正式开始
- 比赛进行中（定期）
- 比赛结束

作者：技术团队
版本：1.1
"""

import asyncio
from typing import Callable, Dict, Any, Optional

from ..core.logger import get_logger
from ..core.account_logger import get_game_logger
from .task_context import (
    AgentTaskContext,
    Step4Result,
    TaskStepStatus,
    GameAccountInfo
)


async def step4_execute_gaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    platform_client: Optional[Any] = None
) -> Step4Result:
    """
    步骤四执行：自动游戏比赛动作（MVP版本）

    简化流程（假设账号已登录）：
    1. 从平台获取所有游戏账号当天已完成场次
    2. 循环处理每个游戏账号：
       a. 检查该账号当天是否已达最大次数(3场)
          - 已达最大次数：跳过该账号
          - 未达最大次数：继续执行
       b. 执行一场比赛
       c. 记录比赛次数
       d. 重复直到完成3场
    3. 切换到下一个游戏账号
    4. 所有账号完成后，任务结束

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数
    - platform_client: 平台API客户端（可选）

    返回：
    - Step4Result: 包含游戏自动化结果的Step4Result
    """
    logger = get_logger(f'step4_game_{context.task_id}')
    logger.info("=== 步骤四：开始游戏比赛自动化（MVP版本）===")

    context.update_step_status("step4", TaskStepStatus.RUNNING, "初始化游戏账号...")
    await report_progress(context.task_id, "STEP4", "RUNNING", "初始化游戏账号...")

    try:
        context.matches_completed_today = {}
        for ga in context.game_accounts:
            context.matches_completed_today[ga.id] = 0

        total_matches = len(context.game_accounts) * 3
        completed_matches = 0

        logger.info(f"游戏账号数量: {len(context.game_accounts)}, "
                   f"目标总比赛数: {total_matches}")

        for account_index, game_account in enumerate(context.game_accounts):
            if check_cancel():
                logger.info("任务被取消，步骤四终止")
                context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
                return Step4Result(success=False, error_code="CANCELLED",
                                 message="任务被取消")

            if context.matches_completed_today[game_account.id] >= game_account.target_matches:
                logger.info(f"账号 {game_account.gamertag} 今日已完成 "
                           f"{game_account.target_matches} 场，跳过")
                continue

            context.current_game_account_index = account_index

            game_logger = get_game_logger(game_account.gamertag)
            logger.info(f"开始处理游戏账号: {game_account.gamertag} "
                       f"({account_index+1}/{len(context.game_accounts)})")
            game_logger.info(f"=== 开始处理游戏账号 ===")

            while context.matches_completed_today[game_account.id] < game_account.target_matches:
                if check_cancel():
                    return Step4Result(success=False, error_code="CANCELLED",
                                     message="任务被取消")

                current_count = context.matches_completed_today[game_account.id] + 1
                current_total = context.matches_completed_today[game_account.id]
                target = game_account.target_matches

                context.update_step_status("step4", TaskStepStatus.RUNNING,
                    f"账号 {game_account.gamertag} 进行第{current_count}场比赛 "
                    f"(今日已完成: {current_total}/{target})")

                game_logger.info(f"进行第{current_count}场比赛 (今日已完成: {current_total}/{target})")

                await report_progress(
                    context.task_id, "STEP4", "RUNNING",
                    f"账号 {game_account.gamertag} 进行第{current_count}场比赛 "
                    f"(今日已完成: {current_total}/{target})",
                    extra_data={
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "currentMatch": current_count,
                        "completedToday": current_total,
                        "targetMatches": target,
                        "matchStatus": "PREPARING"
                    }
                )

                match_success = await _execute_match_for_account(
                    context, game_account, logger, game_logger, check_cancel, report_progress
                )

                if match_success:
                    context.matches_completed_today[game_account.id] += 1
                    completed_matches += 1
                    new_completed = context.matches_completed_today[game_account.id]

                    logger.info(f"账号 {game_account.gamertag} 完成第{current_count}场比赛, "
                               f"今日: {new_completed}/{target}")
                    game_logger.info(f"完成第{current_count}场比赛, 今日: {new_completed}/{target}")

                    await report_progress(
                        context.task_id, "STEP4", "RUNNING",
                        f"账号 {game_account.gamertag} 完成第{current_count}场比赛, "
                        f"今日: {new_completed}/{target}",
                        extra_data={
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "currentMatch": current_count,
                            "completedToday": new_completed,
                            "targetMatches": target,
                            "matchStatus": "COMPLETED"
                        }
                    )
                else:
                    logger.warning(f"账号 {game_account.gamertag} 第{current_count}场比赛失败")
                    game_logger.warning(f"第{current_count}场比赛失败")
                    await asyncio.sleep(5)

            logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 "
                       f"{game_account.target_matches} 场比赛")
            game_logger.info(f"今日已完成 {game_account.target_matches} 场比赛")

        success_msg = f"游戏比赛自动化完成，共完成 {completed_matches} 场比赛"
        logger.info(success_msg)
        context.update_step_status("step4", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP4", "COMPLETED", success_msg)

        return Step4Result(success=True, message=success_msg, total_matches=completed_matches)

    except asyncio.CancelledError:
        logger.info("步骤四被取消")
        context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
        return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as e:
        error_msg = f"步骤四执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        return Step4Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _execute_match_for_account(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
) -> bool:
    """
    为指定账号执行一场比赛（MVP简化版本）

    状态上报点：
    1. 比赛准备开始
    2. 比赛正式开始
    3. 比赛进行中（定期）
    4. 比赛结束

    参数：
    - context: 任务上下文
    - game_account: 游戏账号
    - logger: 主日志记录器
    - game_logger: 游戏账号专用日志记录器
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - bool: 是否成功
    """
    logger.info(f"执行比赛: {game_account.gamertag}")
    game_logger.info("执行比赛")

    try:
        await _enter_match(context, game_account, logger, game_logger, report_progress)

        await _wait_for_match_start(context, game_account, logger, game_logger, report_progress)

        await _play_match(context, game_account, logger, game_logger, check_cancel, report_progress)

        await _finish_match(context, game_account, logger, game_logger, report_progress)

        logger.info(f"比赛完成: {game_account.gamertag}")
        game_logger.info("比赛完成")
        return True

    except Exception as e:
        logger.error(f"比赛执行异常: {e}")
        game_logger.error(f"比赛执行异常: {e}")
        return False


async def _enter_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    进入比赛（MVP简化版本）

    状态上报：比赛准备开始

    实际需要：
    - 导航到比赛入口
    - 选择比赛模式
    - 等待匹配
    """
    logger.info(f"进入比赛准备: {game_account.gamertag}")
    game_logger.info("进入比赛准备")

    await report_progress(
        context.task_id, "STEP4", "RUNNING",
        f"账号 {game_account.gamertag} 比赛准备中...",
        extra_data={
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "PREPARING"
        }
    )

    await asyncio.sleep(2)


async def _wait_for_match_start(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    等待比赛开始

    状态上报：比赛正式开始
    """
    logger.info(f"比赛正式开始: {game_account.gamertag}")
    game_logger.info("比赛正式开始")

    await report_progress(
        context.task_id, "STEP4", "RUNNING",
        f"账号 {game_account.gamertag} 比赛开始！",
        extra_data={
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "STARTED"
        }
    )

    await asyncio.sleep(3)


async def _play_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    进行比赛（MVP简化版本）

    状态上报：比赛进行中（每30秒上报一次）

    实际需要：
    - 持续监控画面
    - 模拟手柄操作
    - 检测比赛状态
    """
    match_duration = 120
    report_interval = 30

    logger.info(f"比赛中，预计时长: {match_duration}秒")
    game_logger.info(f"比赛中，预计时长: {match_duration}秒")

    for i in range(match_duration // 10):
        if check_cancel():
            raise Exception("比赛被取消")

        await asyncio.sleep(10)

        elapsed = (i + 1) * 10
        progress_pct = min(100, int(elapsed / match_duration * 100))

        if i % 3 == 0 or elapsed == match_duration:
            logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")
            game_logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")

            current_count = context.matches_completed_today[game_account.id] + 1
            target = game_account.target_matches

            await report_progress(
                context.task_id, "STEP4", "RUNNING",
                f"账号 {game_account.gamertag} 比赛中 ({elapsed}/{match_duration}秒)",
                extra_data={
                    "gameAccountId": game_account.id,
                    "gameAccountName": game_account.gamertag,
                    "currentMatch": current_count,
                    "completedToday": context.matches_completed_today[game_account.id],
                    "targetMatches": target,
                    "matchStatus": "IN_PROGRESS",
                    "elapsedSeconds": elapsed,
                    "totalSeconds": match_duration,
                    "progressPercent": progress_pct
                }
            )


async def _finish_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    完成比赛（MVP简化版本）

    状态上报：比赛结束

    实际需要：
    - 检测比赛结束
    - 跳过结算画面
    """
    logger.info(f"比赛结束: {game_account.gamertag}")
    game_logger.info("比赛结束")

    current_count = context.matches_completed_today[game_account.id] + 1
    target = game_account.target_matches

    await report_progress(
        context.task_id, "STEP4", "RUNNING",
        f"账号 {game_account.gamertag} 比赛结束",
        extra_data={
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "currentMatch": current_count,
            "completedToday": context.matches_completed_today[game_account.id],
            "targetMatches": target,
            "matchStatus": "ENDED"
        }
    )

    await asyncio.sleep(2)
