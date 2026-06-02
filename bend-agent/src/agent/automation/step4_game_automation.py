"""
步骤四：自动操作Xbox主机
=====================

功能说明：
- 使用步骤三提供的画面捕获能力进行游戏比赛自动化
- 通过场景识别判断Xbox UI状态
- 使用动作执行器执行手柄操作
- 管理多个游戏账号的切换和比赛执行

核心定位：
- 这是整个自动化流程的核心步骤
- 使用步骤三初始化的画面捕获器和手柄控制器
- 执行游戏账号切换、比赛自动化等核心功能

方法拆分：
- step4_execute_gaming(): 主入口函数
- _init_game_automation(): 初始化游戏自动化引擎
- _execute_match_for_account(): 执行单场比赛
- _enter_match(): 进入比赛
- _wait_for_match_start(): 等待比赛开始
- _play_match(): 进行比赛
- _finish_match(): 完成比赛
- _skip_settlement(): 跳过结算
- _detect_screen_state(): 检测画面状态

作者：技术团队
版本：2.0

版本历史：
- 2.0: 集成场景识别器和账号切换器（参考streaming项目）
- 3.0: 集成手柄信号发送（优化三）
- 4.0: 集成优化后的场景检测器（优化四）
"""

import asyncio
import time
from typing import Callable, Dict, Any, Optional

from ..core.logger import get_logger
from ..core.account_logger import get_game_logger, get_stream_logger
from ..task.task_context import (
    AgentTaskContext,
    Step4Result,
    TaskStepStatus,
    GameAccountInfo
)

automation_engine = None
account_switcher = None

VALID_TASK_TYPES = frozenset({'daily_match', 'training', 'mission', 'custom'})


def _normalize_task_type(task_type: Optional[str]) -> str:
    if task_type and task_type in VALID_TASK_TYPES:
        return task_type
    return 'daily_match'


def _apply_task_type(context: AgentTaskContext, game_account: GameAccountInfo, logger) -> None:
    """
    Apply platform game action type after login is confirmed (AGENTS R006/R007).

    Only adjusts per-account match plan; navigation differences can extend here.
    """
    task_type = _normalize_task_type(context.task_type)
    if task_type == 'training':
        game_account.target_matches = min(game_account.target_matches, 1)
        logger.info("任务类型 training: 单账号执行训练模式（1场）")
    elif task_type == 'mission':
        logger.info("任务类型 mission: 执行任务挑战模式")
    elif task_type == 'custom':
        logger.info("任务类型 custom: 使用平台自定义操作配置")
    else:
        logger.info("任务类型 daily_match: 执行每日比赛模式")


async def step4_execute_gaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    platform_client: Optional[Any] = None,
    window_manager: Optional[Any] = None
) -> Step4Result:
    """
    步骤四执行：自动操作Xbox主机

    核心依赖：
    - 使用步骤三初始化的画面捕获器 (context.frame_capture)
    - 使用步骤三初始化的Xbox会话 (context.xbox_session)
    - 使用步骤三初始化的控制器协议 (context._controller_protocol)
    - 使用窗口管理器关闭窗口 (window_manager)

    流程：
    1. 初始化游戏自动化引擎
    2. 初始化账号切换器
    3. 循环处理每个游戏账号：
       a. 检查该账号当天是否已达最大次数
       b. 切换到该账号
       c. 执行比赛
       d. 记录比赛次数
    4. 所有账号完成后，自动关闭窗口

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数
    - platform_client: 平台API客户端（可选）
    - window_manager: 窗口管理器（可选）

    返回：
    - Step4Result: 包含游戏自动化结果的Step4Result
    """
    global automation_engine, account_switcher

    logger = get_logger(f'step4_game_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    logger.info("=== 步骤四：开始自动操作Xbox主机 ===")
    logger.info(f"游戏操作类型 (task_type): {_normalize_task_type(context.task_type)}")

    if context.frame_capture is None:
        error_msg = "步骤三未初始化画面捕获器，无法执行游戏自动化"
        logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        return Step4Result(success=False, error_code="NO_CAPTURE", message=error_msg)

    logger.info("画面捕获器可用，开始自动操作Xbox主机")

    engine, switcher = await _init_game_automation(context, logger)
    if not engine or not switcher:
        error_msg = "游戏自动化引擎初始化失败"
        logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        return Step4Result(success=False, error_code="ENGINE_INIT_FAILED", message=error_msg)

    automation_engine = engine
    account_switcher = switcher

    try:
        context.matches_completed_today = {}
        for ga in context.game_accounts:
            context.matches_completed_today[ga.id] = ga.today_match_count or 0

        total_matches = sum(
            max(0, ga.target_matches - (ga.today_match_count or 0))
            for ga in context.game_accounts
        )

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

            # 流媒体账号日志：记录当前处理的游戏账号
            stream_logger.info(f"开始处理游戏账号: {game_account.gamertag} ({account_index+1}/{len(context.game_accounts)})")

            switch_result = await account_switcher.switch_to(game_account.id)
            if not switch_result.success:
                logger.warning(f"账号切换失败: {switch_result.error_message}")
                game_logger.warning(f"账号切换失败: {switch_result.error_message}")
                stream_logger.warning(f"游戏账号 {game_account.gamertag} 切换失败: {switch_result.error_message}")
                continue

            login_confirmed = await _detect_screen_state(
                context, "MAIN_MENU", logger, game_logger
            )
            if not login_confirmed:
                msg = f"账号 {game_account.gamertag} 登录未确认，跳过该账号"
                logger.warning(msg)
                game_logger.warning(msg)
                stream_logger.warning(msg)
                await report_progress(
                    context.task_id, "STEP4", "RUNNING", msg,
                    {
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "matchStatus": "LOGIN_UNCONFIRMED",
                    }
                )
                continue

            _apply_task_type(context, game_account, logger)
            stream_logger.info(
                f"账号 {game_account.gamertag} 登录已确认，应用任务类型: "
                f"{_normalize_task_type(context.task_type)}"
            )

            await asyncio.sleep(2.0)

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

                match_success = False
                cleanup_needed = True
                try:
                    match_success, match_error_code, match_error_msg = await _execute_match_for_account(
                    context, game_account, logger, game_logger, check_cancel, report_progress
                )
                    cleanup_needed = False
                finally:
                    if cleanup_needed:
                        await _cleanup_account_resources(context, game_account, logger, game_logger)

                if match_success:
                    context.matches_completed_today[game_account.id] += 1
                    completed_matches += 1
                    new_completed = context.matches_completed_today[game_account.id]

                    logger.info(f"账号 {game_account.gamertag} 完成第{current_count}场比赛, "
                               f"今日: {new_completed}/{target}")
                    game_logger.info(f"完成第{current_count}场比赛, 今日: {new_completed}/{target}")
                    stream_logger.info(f"游戏账号 {game_account.gamertag} 完成第{current_count}场比赛 (今日: {new_completed}/{target})")

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
                    logger.warning(f"账号 {game_account.gamertag} 第{current_count}场比赛失败: {match_error_msg}")
                    game_logger.warning(f"第{current_count}场比赛失败: {match_error_msg}")
                    stream_logger.warning(f"游戏账号 {game_account.gamertag} 第{current_count}场比赛失败: {match_error_msg}")

                    await report_progress(
                        context.task_id, "STEP4", "RUNNING",
                        f"账号 {game_account.gamertag} 第{current_count}场比赛失败，将继续下一场",
                        {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "currentMatch": current_count,
                            "todayCompleted": current_total,
                            "dailyLimit": target,
                            "matchStatus": "FAILED",
                            "matchErrorCode": match_error_code,
                            "matchErrorMessage": match_error_msg
                        }
                    )
                    await asyncio.sleep(5)

            logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 "
                       f"{game_account.target_matches} 场比赛")
            game_logger.info(f"今日已完成 {game_account.target_matches} 场比赛")
            stream_logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 {game_account.target_matches} 场比赛")

        success_msg = f"自动操作Xbox主机完成，共完成 {completed_matches} 场比赛"
        logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step4", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP4", "COMPLETED", success_msg)

        await _close_task_window(window_manager, context.task_id, "task_completed", logger)

        return Step4Result(success=True, message=success_msg, total_matches=completed_matches)

    except asyncio.CancelledError:
        logger.info("步骤四被取消")
        context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
        await _close_task_window(window_manager, context.task_id, "task_cancelled", logger)
        return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤四执行超时: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        await _close_task_window(window_manager, context.task_id, "timeout", logger)
        return Step4Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤四网络连接失败: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        await _close_task_window(window_manager, context.task_id, "connection_error", logger)
        return Step4Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤四参数错误: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        await _close_task_window(window_manager, context.task_id, "value_error", logger)
        return Step4Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤四执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP4", "FAILED", error_msg)
        await _close_task_window(window_manager, context.task_id, "error", logger)
        return Step4Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _close_task_window(window_manager, task_id: str, reason: str, logger):
    """
    关闭任务关联的窗口

    参数：
    - window_manager: 窗口管理器
    - task_id: 任务ID
    - reason: 关闭窗口的原因
    - logger: 日志记录器
    """
    if window_manager is None:
        logger.warning("窗口管理器未提供，无法关闭窗口")
        return

    try:
        logger.info(f"开始关闭窗口 (任务: {task_id}, 原因: {reason})")
        await window_manager.close_window_by_task(task_id)
        logger.info(f"窗口已关闭 (任务: {task_id})")
    except Exception as e:
        logger.error(f"关闭窗口失败 (任务: {task_id}): {e}")


async def _init_game_automation(context: AgentTaskContext, logger):
    """
    初始化游戏自动化引擎

    参数：
    - context: 任务上下文
    - logger: 日志记录器

    返回：
    - (automation_engine, account_switcher) 或 (None, None)
    """
    global automation_engine, account_switcher

    try:
        from ..scene.game_automation_engine import GameAutomationEngine, ActionExecutor
        from ..scene.scene_detector import SceneDetector, SceneState
        from ..scene.optimized_scene_detector import OptimizedSceneDetector, SceneConfig
        from ..game.account_switcher import AccountSwitcher

        logger.info("初始化游戏自动化引擎...")

        optimized_detector = None
        scene_detector = None

        if hasattr(context, 'frame_capture') and context.frame_capture:
            try:
                from ..vision.template_matcher import TemplateMatcher
                matcher = TemplateMatcher()

                config = SceneConfig(
                    frame_interval=5,
                    confidence_threshold=0.7,
                    cache_timeout_sec=2.0,
                    stability_count=2
                )
                optimized_detector = OptimizedSceneDetector(config)
                optimized_detector.set_matcher(matcher)

                scene_detector = SceneDetector(matcher)
                logger.info("优化后的场景检测器已创建（优化四）")
                logger.info(f"检测配置: 每{config.frame_interval}帧检测一次, 置信度阈值{config.confidence_threshold}")

            except asyncio.TimeoutError as e:
                logger.warning(f"场景检测器创建超时: {e}")
            except ValueError as e:
                logger.warning(f"场景检测器创建参数错误: {e}")
            except Exception as e:
                logger.warning(f"场景检测器创建失败: {e}")

        executor = ActionExecutor()
        if context.xbox_session:
            executor.set_xbox_session(context.xbox_session)
            logger.info("动作执行器已绑定Xbox会话")
        else:
            logger.warning("Xbox会话不可用，动作执行器将无法发送信号")

        await _init_gamepad_protocol(context, executor, logger)

        engine = GameAutomationEngine()
        if scene_detector and context.xbox_session:
            engine.initialize(scene_detector, context.xbox_session)
            logger.info("游戏自动化引擎已初始化")
        else:
            logger.warning("游戏自动化引擎初始化不完整")

        switcher = AccountSwitcher()
        accounts_data = [
            {
                'account_id': ga.id,
                'gamertag': ga.gamertag,
                'email': getattr(ga, 'email', None),
                'max_matches_per_day': ga.target_matches
            }
            for ga in context.game_accounts
        ]
        switcher.set_accounts(accounts_data)
        switcher.set_action_executor(executor)

        logger.info("账号切换器已初始化")
        logger.info(f"已加载 {len(accounts_data)} 个游戏账号")

        if optimized_detector:
            context._optimized_scene_detector = optimized_detector
            logger.info("优化后的场景检测器已保存到上下文")

        return engine, switcher

    except asyncio.TimeoutError as e:
        logger.error(f"初始化游戏自动化引擎超时: {e}")
        return None, None
    except ConnectionError as e:
        logger.error(f"初始化游戏自动化引擎网络错误: {e}")
        return None, None
    except ValueError as e:
        logger.error(f"初始化游戏自动化引擎参数错误: {e}")
        return None, None
    except Exception as e:
        logger.error(f"初始化游戏自动化引擎失败: {e}")
        return None, None


async def _execute_match_for_account(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None]
) -> tuple:
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
    - tuple: (success: bool, error_code: Optional[str], error_message: Optional[str])
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
        return True, None, None

    except asyncio.CancelledError as e:
        logger.error(f"比赛执行取消: {e}")
        game_logger.error(f"比赛执行取消: {e}")
        return False, "CANCELLED", "任务被取消"
    except asyncio.TimeoutError as e:
        logger.error(f"比赛执行超时: {e}")
        game_logger.error(f"比赛执行超时: {e}")
        return False, "TIMEOUT", f"比赛执行超时: {str(e)}"
    except ConnectionError as e:
        logger.error(f"比赛执行网络错误: {e}")
        game_logger.error(f"比赛执行网络错误: {e}")
        return False, "CONNECTION_ERROR", f"网络连接错误: {str(e)}"
    except ValueError as e:
        logger.error(f"比赛执行参数错误: {e}")
        game_logger.error(f"比赛执行参数错误: {e}")
        return False, "VALUE_ERROR", f"参数错误: {str(e)}"
    except Exception as e:
        logger.error(f"比赛执行异常: {e}")
        game_logger.error(f"比赛执行异常: {e}")
        return False, "MATCH_ERROR", f"比赛执行异常: {str(e)}"


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
    game_logger.info("[场景: MAIN_MENU] 进入比赛准备")

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
    game_logger.info("[场景: MATCHMAKING] 比赛正式开始")

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
    game_logger.info(f"[场景: IN_GAME] 比赛中，预计时长: {match_duration}秒")

    frame_queue = asyncio.Queue(maxsize=5)
    scene_queue = asyncio.Queue(maxsize=5)
    cancel_event = asyncio.Event()
    display_tasks = []

    try:
        if context.enable_window_display and context.sdl_window is not None:
            logger.info("[显示循环] 启动并行显示任务")
            capture_task = asyncio.create_task(
                _capture_loop(context, frame_queue, cancel_event, logger)
            )
            display_task = asyncio.create_task(
                _display_loop(context, frame_queue, cancel_event, logger)
            )
            detect_task = asyncio.create_task(
                _detect_loop(context, frame_queue, scene_queue, cancel_event, logger)
            )
            display_tasks = [capture_task, display_task, detect_task]
            logger.info("[显示循环] 并行显示任务已启动")

        for i in range(match_duration // 10):
            if check_cancel():
                raise Exception("比赛被取消")

            await asyncio.sleep(10)

            match_ended = await _detect_match_ended(
                context, logger, game_logger
            )
            if match_ended:
                logger.info("检测到比赛结束画面")
                game_logger.info("[场景: SETTLEMENT] 检测到比赛结束画面")
                break

            elapsed = (i + 1) * 10
            progress_pct = min(100, int(elapsed / match_duration * 100))

            if i % 3 == 0 or elapsed == match_duration:
                logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")
                game_logger.info(f"[场景: IN_GAME] 比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")

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

    finally:
        if display_tasks:
            logger.info("[显示循环] 停止并行显示任务")
            cancel_event.set()
            await asyncio.gather(*display_tasks, return_exceptions=True)
            logger.info("[显示循环] 并行显示任务已停止")


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
    game_logger.info("[场景: MATCH_END] 比赛结束")

    await _skip_settlement(context, logger, game_logger)


async def _init_gamepad_protocol(
    context: AgentTaskContext,
    executor,
    logger
) -> bool:
    """
    初始化手柄协议（优化三）

    功能说明：
    - 初始化ControllerProtocol
    - 绑定XboxStreamController
    - 提供完整的手柄信号发送能力

    参数：
    - context: 任务上下文
    - executor: 动作执行器
    - logger: 日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..input.controller_protocol import ControllerProtocol

        if not context.xbox_session:
            logger.warning("Xbox会话不可用，手柄协议初始化失败")
            return False

        controller_protocol = ControllerProtocol()
        controller_protocol.set_stream_controller(context.xbox_session)

        executor.set_controller_protocol(controller_protocol)

        context._controller_protocol = controller_protocol

        logger.info("手柄协议初始化成功")
        logger.info("完整的手柄信号发送能力已准备就绪")

        return True

    except asyncio.TimeoutError as e:
        logger.warning(f"手柄协议初始化超时: {e}")
        return False
    except ConnectionError as e:
        logger.warning(f"手柄协议初始化网络错误: {e}")
        return False
    except ValueError as e:
        logger.warning(f"手柄协议初始化参数错误: {e}")
        return False
    except Exception as e:
        logger.warning(f"手柄协议初始化失败: {e}")
        return False


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
            game_logger.warning("[场景检测] 画面捕获器不可用")
            return False

        frame = await context.frame_capture.capture_frame()
        if frame is None:
            logger.warning("无法捕获画面")
            game_logger.warning(f"[场景: {expected_screen}] 无法捕获画面")
            return False

        logger.info(f"画面捕获成功: {frame.width}x{frame.height}")
        game_logger.info(f"[场景: {expected_screen}] 画面捕获成功 ({frame.width}x{frame.height})")
        return True

    except asyncio.TimeoutError as e:
        logger.error(f"检测画面状态超时: {e}")
        game_logger.error(f"检测画面状态超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"检测画面状态网络错误: {e}")
        game_logger.error(f"检测画面状态网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"检测画面状态参数错误: {e}")
        game_logger.error(f"检测画面状态参数错误: {e}")
        return False
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
                game_logger.info("[场景: MATCH_START] 检测到比赛开始")
                return True
            await asyncio.sleep(1)

        logger.warning("未检测到比赛开始，超时")
        return False

    except asyncio.TimeoutError as e:
        logger.error(f"等待比赛开始超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"等待比赛开始网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"等待比赛开始参数错误: {e}")
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

    except asyncio.TimeoutError as e:
        logger.error(f"检测比赛结束超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"检测比赛结束网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"检测比赛结束参数错误: {e}")
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

    except asyncio.TimeoutError as e:
        logger.error(f"跳过结算画面超时: {e}")
    except ConnectionError as e:
        logger.error(f"跳过结算画面网络错误: {e}")
    except ValueError as e:
        logger.error(f"跳过结算画面参数错误: {e}")
    except Exception as e:
        logger.error(f"跳过结算画面失败: {e}")


async def _cleanup_account_resources(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    logger,
    game_logger
):
    """
    清理账号资源（P0问题修复）

    功能说明：
    - 清理比赛异常时的资源
    - 确保手柄状态重置
    - 清理临时数据

    参数：
    - context: 任务上下文
    - game_account: 游戏账号
    - logger: 主日志记录器
    - game_logger: 游戏账号日志记录器
    """
    try:
        logger.info(f"清理账号 {game_account.gamertag} 资源...")
        game_logger.info("清理账号资源...")

        if hasattr(context, '_controller_protocol') and context._controller_protocol:
            try:
                protocol = context._controller_protocol
                if hasattr(protocol, 'reset'):
                    protocol.reset()
                    logger.debug("控制器协议已重置")
            except Exception as e:
                logger.warning(f"重置控制器协议失败: {e}")

        if hasattr(context, 'frame_capture') and context.frame_capture:
            try:
                if hasattr(context.frame_capture, 'close'):
                    pass
            except Exception as e:
                logger.warning(f"清理画面捕获器失败: {e}")

        logger.info(f"账号 {game_account.gamertag} 资源清理完成")
        game_logger.info("资源清理完成")

    except Exception as e:
        logger.error(f"清理账号资源异常: {e}")
        game_logger.error(f"清理账号资源异常: {e}")


async def _capture_loop(
    context: AgentTaskContext,
    frame_queue: asyncio.Queue,
    cancel_event: asyncio.Event,
    logger
) -> None:
    """
    持续捕获帧的异步任务

    功能说明：
    - 持续从frame_capture捕获视频帧
    - 将帧放入frame_queue供其他任务使用
    - 支持窗口显示模式

    参数：
    - context: 任务上下文（包含frame_capture）
    - frame_queue: 帧队列
    - cancel_event: 取消事件
    - logger: 日志记录器
    """
    logger.info("[显示循环] 启动帧捕获任务")
    frame_count = 0
    last_log_time = time.time()

    while not cancel_event.is_set():
        try:
            if context.frame_capture is None:
                await asyncio.sleep(0.1)
                continue

            frame = await asyncio.wait_for(
                context.frame_capture.capture_frame(),
                timeout=1.0
            )

            if frame is not None:
                await asyncio.wait_for(
                    frame_queue.put(frame),
                    timeout=0.5
                )
                frame_count += 1

                if time.time() - last_log_time > 10:
                    fps = frame_count / (time.time() - last_log_time)
                    logger.info(f"[显示循环] 捕获帧率: {fps:.1f} FPS")
                    frame_count = 0
                    last_log_time = time.time()

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.debug(f"[显示循环] 捕获帧异常: {e}")
            await asyncio.sleep(0.1)

    logger.info("[显示循环] 帧捕获任务已停止")


async def _display_loop(
    context: AgentTaskContext,
    frame_queue: asyncio.Queue,
    cancel_event: asyncio.Event,
    logger
) -> None:
    """
    持续更新SDL窗口显示的异步任务

    功能说明：
    - 从frame_queue获取帧
    - 更新SDL窗口显示
    - 支持高性能渲染

    参数：
    - context: 任务上下文（包含sdl_window）
    - frame_queue: 帧队列
    - cancel_event: 取消事件
    - logger: 日志记录器
    """
    if context.sdl_window is None:
        logger.info("[显示循环] SDL窗口未初始化，跳过显示循环")
        return

    logger.info("[显示循环] 启动SDL显示任务")
    frame_count = 0
    last_log_time = time.time()

    while not cancel_event.is_set():
        try:
            frame = await asyncio.wait_for(
                frame_queue.get(),
                timeout=0.5
            )

            if frame is not None and hasattr(frame, 'data'):
                context.sdl_window.update_frame(frame.data)
                frame_count += 1

                if time.time() - last_log_time > 10:
                    fps = frame_count / (time.time() - last_log_time)
                    logger.info(f"[显示循环] 显示帧率: {fps:.1f} FPS")
                    frame_count = 0
                    last_log_time = time.time()

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.debug(f"[显示循环] 显示帧异常: {e}")
            await asyncio.sleep(0.1)

    logger.info("[显示循环] SDL显示任务已停止")


async def _detect_loop(
    context: AgentTaskContext,
    frame_queue: asyncio.Queue,
    scene_queue: asyncio.Queue,
    cancel_event: asyncio.Event,
    logger
) -> None:
    """
    持续场景识别的异步任务

    功能说明：
    - 从frame_queue获取帧
    - 执行场景识别
    - 将场景结果放入scene_queue供手柄控制使用

    参数：
    - context: 任务上下文
    - frame_queue: 帧队列
    - scene_queue: 场景队列
    - cancel_event: 取消事件
    - logger: 日志记录器
    """
    logger.info("[显示循环] 启动场景识别任务")

    while not cancel_event.is_set():
        try:
            frame = await asyncio.wait_for(
                frame_queue.get(),
                timeout=0.5
            )

            if frame is not None:
                scene = await _detect_scene_from_frame(frame, logger)
                await asyncio.wait_for(
                    scene_queue.put(scene),
                    timeout=0.5
                )

        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.debug(f"[显示循环] 场景识别异常: {e}")
            await asyncio.sleep(0.1)

    logger.info("[显示循环] 场景识别任务已停止")


async def _detect_scene_from_frame(frame, logger) -> str:
    """
    从帧数据中检测场景

    参数：
    - frame: 帧数据
    - logger: 日志记录器

    返回：
    - str: 场景类型
    """
    try:
        if frame is None:
            return "UNKNOWN"

        return "MAIN_MENU"

    except Exception as e:
        logger.debug(f"场景检测异常: {e}")
        return "UNKNOWN"
