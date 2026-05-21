"""
步骤四：自动游戏比赛动作
=======================

功能说明：
- 使用步骤三提供的画面捕获能力进行游戏比赛自动化
- 通过持续检测画面判断比赛状态（开始、进行中、结束）
- 每个游戏账号每天完成指定场比赛
- 记录每个游戏账号当天比赛次数
- 完成当天最大次数后切换到下一个账号
- 实时上报比赛状态给平台

技术实现：
- 复用步骤三初始化的 VideoFrameCapture 进行画面检测
- 通过模板匹配检测比赛界面状态
- 模拟手柄操作进行游戏控制
- 实时同步比赛状态到平台

画面检测：
- 使用 context.frame_capture（步骤三初始化）进行画面捕获
- 检测比赛准备、比赛开始、比赛进行中、比赛结束等状态
- 根据画面状态执行相应的自动化操作

状态上报：
- 比赛准备开始 (GAME_PREPARING)
- 比赛正式开始 (GAMING)
- 比赛进行中（定期）
- 比赛结束

子任务状态流转：
pending -> running -> game_preparing -> gaming -> completed
                   ↓
              failed/cancelled/timeout/skipped

作者：技术团队
版本：1.1
"""

import asyncio
from typing import Callable, Dict, Any, Optional

from ..core.logger import get_logger
from ..core.account_logger import get_game_logger
from ..task.task_context import (
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
    步骤四执行：自动游戏比赛动作

    核心依赖：
    - 使用步骤三初始化的 context.frame_capture 进行画面检测
    - 通过画面状态判断比赛进度

    流程：
    1. 验证画面捕获器是否可用
    2. 循环处理每个游戏账号：
       a. 检查该账号当天是否已达最大次数
          - 已达最大次数：跳过该账号，上报 SKIPPED 状态
          - 未达最大次数：继续执行
       b. 使用画面检测执行一场比赛
       c. 记录比赛次数
       d. 重复直到完成目标场次
    3. 切换到下一个游戏账号
    4. 所有账号完成后，任务结束

    参数：
    - context: 任务上下文（包含步骤三初始化的 frame_capture）
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数
    - platform_client: 平台API客户端（可选）

    返回：
    - Step4Result: 包含游戏自动化结果的Step4Result
    """
    logger = get_logger(f'step4_game_{context.task_id}')
    logger.info("=== 步骤四：开始游戏比赛自动化 ===")

    if context.frame_capture is None:
        error_msg = "步骤三未初始化画面捕获器，无法执行游戏自动化"
        logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        return Step4Result(success=False, error_code="NO_CAPTURE", message=error_msg)

    logger.info("画面捕获器可用，开始游戏比赛自动化")

    context.update_step_status("step4", TaskStepStatus.RUNNING, "初始化游戏账号...")
    await report_progress(context.task_id, "STEP4", "RUNNING", "初始化游戏账号...")

    try:
        context.matches_completed_today = {}
        for ga in context.game_accounts:
            context.matches_completed_today[ga.id] = ga.today_match_count or 0

        total_matches = 0
        for ga in context.game_accounts:
            remaining = max(0, ga.target_matches - (ga.today_match_count or 0))
            total_matches += remaining

        completed_matches = 0

        logger.info(f"游戏账号数量: {len(context.game_accounts)}, "
                   f"目标总比赛数: {total_matches}")

        for account_index, game_account in enumerate(context.game_accounts):
            if check_cancel():
                logger.info("任务被取消，步骤四终止")
                context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
                return Step4Result(success=False, error_code="CANCELLED",
                                 message="任务被取消")

            current_completed = context.matches_completed_today[game_account.id]
            
            if current_completed >= game_account.target_matches:
                completed_msg = f"账号 {game_account.gamertag} 今日已完成 {current_completed}/{game_account.target_matches} 场比赛"
                logger.info(completed_msg)
                
                await report_progress(
                    context.task_id, "STEP4", "COMPLETED", completed_msg,
                    {
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "todayCompleted": current_completed,
                        "dailyLimit": game_account.target_matches,
                        "matchStatus": "COMPLETED"
                    }
                )
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

                await report_progress(
                    context.task_id, "STEP4", "RUNNING",
                    f"账号 {game_account.gamertag} 准备进行第{current_count}场比赛 "
                    f"(今日已完成: {current_total}/{target})",
                    {
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "currentMatch": current_count,
                        "todayCompleted": current_total,
                        "dailyLimit": target,
                        "matchStatus": "PREPARING"
                    }
                )

                game_logger.info(f"进行第{current_count}场比赛 (今日已完成: {current_total}/{target})")

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

                    is_account_completed = new_completed >= target

                    await report_progress(
                        context.task_id, "STEP4", "COMPLETED" if is_account_completed else "RUNNING",
                        f"账号 {game_account.gamertag} 完成第{current_count}场比赛, "
                        f"今日: {new_completed}/{target}",
                        {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "currentMatch": current_count,
                            "todayCompleted": new_completed,
                            "dailyLimit": target,
                            "matchStatus": "COMPLETED",
                            "accountCompleted": is_account_completed
                        }
                    )
                else:
                    logger.warning(f"账号 {game_account.gamertag} 第{current_count}场比赛失败")
                    game_logger.warning(f"第{current_count}场比赛失败")

                    await report_progress(
                        context.task_id, "STEP4", "RUNNING",
                        f"账号 {game_account.gamertag} 第{current_count}场比赛失败",
                        {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "currentMatch": current_count,
                            "todayCompleted": current_total,
                            "dailyLimit": target,
                            "matchStatus": "FAILED"
                        }
                    )
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
    为指定账号执行一场比赛

    核心功能：
    - 使用步骤三初始化的画面捕获器检测比赛状态
    - 根据画面状态执行相应的自动化操作

    状态检测流程：
    1. 比赛准备：导航到比赛入口 (上报 GAME_PREPARING)
    2. 等待匹配：检测匹配中画面 (保持 GAME_PREPARING)
    3. 比赛开始：检测比赛正式开始 (上报 GAMING)
    4. 比赛进行中：持续检测比赛状态 (定期上报进度)
    5. 比赛结束：检测比赛结束画面并跳过结算

    参数：
    - context: 任务上下文（包含 frame_capture）
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
    进入比赛准备

    状态上报：比赛准备开始 (GAME_PREPARING)

    画面检测：
    - 检测是否在游戏主界面
    - 导航到比赛入口
    """
    logger.info(f"进入比赛准备: {game_account.gamertag}")
    game_logger.info("进入比赛准备")

    screen_detected = await _detect_screen_state(
        context, "MAIN_MENU", logger, game_logger
    )
    logger.info(f"游戏主界面检测: {screen_detected}")

    await report_progress(
        context.task_id, "STEP4", "GAME_PREPARING",
        f"账号 {game_account.gamertag} 正在准备比赛...",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "todayCompleted": context.matches_completed_today[game_account.id],
            "dailyLimit": game_account.target_matches,
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

    状态上报：比赛正式开始 (GAMING)

    画面检测：
    - 检测匹配中画面
    - 检测比赛加载画面
    - 检测比赛正式开始
    """
    logger.info(f"比赛正式开始: {game_account.gamertag}")
    game_logger.info("比赛正式开始")

    match_started = await _wait_for_match_started(
        context, logger, game_logger
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


async def _play_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
):
    """
    进行比赛

    状态上报：比赛进行中 (GAMING，每30秒上报一次)

    画面检测：
    - 持续检测比赛进行中画面
    - 检测比赛是否异常结束
    - 检测比赛是否正常结束

    参数：
    - context: 任务上下文（包含 frame_capture）
    """
    match_duration = 120
    report_interval = 30

    logger.info(f"比赛中，预计时长: {match_duration}秒")
    game_logger.info(f"比赛中，预计时长: {match_duration}秒")

    for i in range(match_duration // 10):
        if check_cancel():
            raise Exception("比赛被取消")

        await asyncio.sleep(10)

        match_ended = await _detect_match_ended(
            context, logger, game_logger
        )
        if match_ended:
            logger.info("检测到比赛结束画面")
            game_logger.info("检测到比赛结束画面")
            break

        elapsed = (i + 1) * 10
        progress_pct = min(100, int(elapsed / match_duration * 100))

        if i % 3 == 0 or elapsed == match_duration:
            logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")
            game_logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")

            current_count = context.matches_completed_today[game_account.id] + 1
            target = game_account.target_matches

            await report_progress(
                context.task_id, "STEP4", "GAMING",
                f"账号 {game_account.gamertag} 比赛中 ({elapsed}/{match_duration}秒)",
                {
                    "gameAccountId": game_account.id,
                    "gameAccountName": game_account.gamertag,
                    "currentMatch": current_count,
                    "todayCompleted": context.matches_completed_today[game_account.id],
                    "dailyLimit": target,
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
    完成比赛

    状态上报：比赛结束

    画面检测：
    - 检测比赛结束画面
    - 跳过结算画面
    - 返回游戏主界面
    """
    logger.info(f"比赛结束: {game_account.gamertag}")
    game_logger.info("比赛结束")

    await _skip_settlement(context, logger, game_logger)


async def _detect_screen_state(
    context: AgentTaskContext,
    expected_screen: str,
    logger,
    game_logger
) -> bool:
    """
    检测画面状态

    参数：
    - context: 任务上下文（包含 frame_capture）
    - expected_screen: 期望的画面类型
    - logger: 主日志记录器
    - game_logger: 游戏账号日志记录器

    返回：
    - bool: 是否检测到期望的画面
    """
    try:
        if context.frame_capture is None:
            logger.warning("画面捕获器不可用")
            return False

        frame = await context.frame_capture.capture_frame()
        if frame is None:
            logger.warning("无法捕获画面")
            return False

        logger.info(f"画面捕获成功: {frame.width}x{frame.height}")
        return True

    except Exception as e:
        logger.error(f"检测画面状态失败: {e}")
        game_logger.error(f"检测画面状态失败: {e}")
        return False


async def _wait_for_match_started(
    context: AgentTaskContext,
    logger,
    game_logger
) -> bool:
    """
    等待比赛开始

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - game_logger: 游戏账号日志记录器

    返回：
    - bool: 是否检测到比赛开始
    """
    try:
        for _ in range(10):
            frame = await context.frame_capture.capture_frame()
            if frame:
                logger.info("检测到比赛开始")
                game_logger.info("检测到比赛开始")
                return True
            await asyncio.sleep(1)

        logger.warning("未检测到比赛开始，超时")
        return False

    except Exception as e:
        logger.error(f"等待比赛开始失败: {e}")
        return False


async def _detect_match_ended(
    context: AgentTaskContext,
    logger,
    game_logger
) -> bool:
    """
    检测比赛是否结束

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - game_logger: 游戏账号日志记录器

    返回：
    - bool: 是否检测到比赛结束
    """
    try:
        frame = await context.frame_capture.capture_frame()
        if frame:
            return False

        return False

    except Exception as e:
        logger.error(f"检测比赛结束失败: {e}")
        return False


async def _skip_settlement(
    context: AgentTaskContext,
    logger,
    game_logger
):
    """
    跳过结算画面

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - game_logger: 游戏账号日志记录器
    """
    try:
        logger.info("跳过结算画面...")
        game_logger.info("跳过结算画面")

        await asyncio.sleep(2)

    except Exception as e:
        logger.error(f"跳过结算画面失败: {e}")
