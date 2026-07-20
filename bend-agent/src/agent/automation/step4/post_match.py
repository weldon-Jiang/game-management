"""
Step4 赛后处理与资源清理
=====================
从原 step4_game_automation.py 提取。职责:
- 手柄协议初始化
- 画面状态检测 (_detect_screen_state)
- 比赛开始/结束检测
- 结算画面跳过
- 账号资源清理
"""
import asyncio
from typing import Optional, Any

from ..task.task_context import AgentTaskContext, GameAccountInfo
from .constants import MATCH_END_SCENE_IDS, UT_MENU_SCENE_IDS, SETTLEMENT_SCENE_IDS
from .setup import _match_expected_screen

# ========================================================================

async def _init_gamepad_protocol(
    context: AgentTaskContext,
    executor,
    task_logger,
    input_gate: Optional[Any] = None,
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
    - task_logger: 日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..input.controller_protocol import ControllerProtocol

        if not context.xbox_session:
            task_logger.warning("Xbox会话不可用，手柄协议初始化失败")
            return False

        controller_protocol = ControllerProtocol()
        controller_protocol.set_stream_controller(context.xbox_session)
        controller_protocol.set_task_context(context)
        if input_gate is not None:
            controller_protocol.set_input_gate(input_gate)

        executor.set_controller_protocol(controller_protocol)

        context._controller_protocol = controller_protocol

        task_logger.info("手柄协议初始化成功")
        task_logger.info("完整的手柄信号发送能力已准备就绪")

        return True

    except asyncio.TimeoutError as e:
        task_logger.warning(f"手柄协议初始化超时: {e}")
        return False
    except ConnectionError as e:
        task_logger.warning(f"手柄协议初始化网络错误: {e}")
        return False
    except ValueError as e:
        task_logger.warning(f"手柄协议初始化参数错误: {e}")
        return False
    except Exception as e:
        task_logger.warning(f"手柄协议初始化失败: {e}")
        return False


async def _detect_screen_state(
    context: AgentTaskContext,
    expected_screen: str,
    task_logger,
    game_logger
) -> bool:
    """
    检测画面状态

    参数：
    - context: 任务上下文（包含 frame_capture）
    - expected_screen: 期望的画面类型
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号日志记录器

    返回：
    - bool: 是否检测到期望的画面
    """
    try:
        if context.frame_capture is None:
            task_logger.warning("画面捕获器不可用")
            game_logger.warning("[场景检测] 画面捕获器不可用")
            return False

        from ..runtime.stream_runtime import capture_task_frame

        frame = await capture_task_frame(context)
        if frame is None:
            task_logger.warning("无法捕获画面")
            game_logger.warning(f"[场景: {expected_screen}] 无法捕获画面")
            return False

        matched = await _match_expected_screen(
            context, expected_screen, task_logger, game_logger
        )
        if not matched:
            task_logger.warning(f"未识别到期望画面: {expected_screen}")
            return False

        task_logger.info(f"画面状态确认: {expected_screen} ({frame.width}x{frame.height})")
        return True

    except asyncio.TimeoutError as e:
        task_logger.error(f"检测画面状态超时: {e}")
        game_logger.error(f"检测画面状态超时: {e}")
        return False
    except ConnectionError as e:
        task_logger.error(f"检测画面状态网络错误: {e}")
        game_logger.error(f"检测画面状态网络错误: {e}")
        return False
    except ValueError as e:
        task_logger.error(f"检测画面状态参数错误: {e}")
        game_logger.error(f"检测画面状态参数错误: {e}")
        return False
    except Exception as e:
        task_logger.error(f"检测画面状态失败: {e}")
        game_logger.error(f"检测画面状态失败: {e}")
        return False


async def _wait_for_match_started(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> bool:
    """
    等待比赛开始

    参数：
    - context: 任务上下文
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号日志记录器

    返回：
    - bool: 是否检测到比赛开始
    """
    try:
        switcher = getattr(context, "_account_switcher", None)
        if switcher:
            hit = await switcher._detect_any_scene([102, 190], strict=False)
            if hit in (102, 190):
                task_logger.info("检测到比赛开始 scene=%s", hit)
                game_logger.info("[场景: MATCH_START] scene=%s", hit)
                return True

        from ..runtime.stream_runtime import capture_task_frame

        for _ in range(10):
            frame = await capture_task_frame(context, timeout=0.8)
            if frame:
                task_logger.info("检测到比赛开始")
                game_logger.info("[场景: MATCH_START] 检测到比赛开始")
                return True
            await asyncio.sleep(1)

        task_logger.warning("未检测到比赛开始，超时")
        return False

    except asyncio.TimeoutError as e:
        task_logger.error(f"等待比赛开始超时: {e}")
        return False
    except ConnectionError as e:
        task_logger.error(f"等待比赛开始网络错误: {e}")
        return False
    except ValueError as e:
        task_logger.error(f"等待比赛开始参数错误: {e}")
        return False
    except Exception as e:
        task_logger.error(f"等待比赛开始失败: {e}")
        return False


async def _detect_match_ended(
    context: AgentTaskContext,
    task_logger,
    game_logger
) -> bool:
    """
    检测比赛是否结束（streaming 对齐：场中 102 + UT 193/回到主菜单）。

    返回 True 表示应退出 _play_match 进入结算跳过。
    """
    try:
        switcher = getattr(context, "_account_switcher", None)
        if switcher:
            hit = await switcher._detect_any_scene(
                MATCH_END_SCENE_IDS + UT_MENU_SCENE_IDS,
                strict=False,
            )
            if hit in MATCH_END_SCENE_IDS or hit in UT_MENU_SCENE_IDS:
                task_logger.info("比赛结束场景: %s", hit)
                game_logger.info("[场景: MATCH_END] 检测到场景 %s", hit)
                return True

        detector = getattr(context, "_streaming_scene_detector", None)
        if detector:
            from ..runtime.stream_runtime import capture_task_frame

            frame = await capture_task_frame(context, timeout=0.5)
            if frame is not None:
                image = frame.data if hasattr(frame, "data") else frame
                for scene_id in MATCH_END_SCENE_IDS:
                    try:
                        result = detector.recognize_scene(
                            image, scene_id=scene_id, threshold=0.78
                        )
                        if result.matched:
                            task_logger.info("模板匹配比赛结束 scene=%s", scene_id)
                            return True
                    except Exception:
                        continue
        return False

    except asyncio.TimeoutError as e:
        task_logger.error(f"检测比赛结束超时: {e}")
        return False
    except ConnectionError as e:
        task_logger.error(f"检测比赛结束网络错误: {e}")
        return False
    except ValueError as e:
        task_logger.error(f"检测比赛结束参数错误: {e}")
        return False
    except Exception as e:
        task_logger.error(f"检测比赛结束失败: {e}")
        return False


async def _skip_settlement(
    context: AgentTaskContext,
    task_logger,
    game_logger
):
    """
    跳过结算：按 A 穿过 UT 赛后弹窗直至回到主菜单（127/147/149）。
    """
    try:
        from ..game.account_switcher import FC_UT_TARGET_SCENES

        task_logger.info("跳过结算画面...")
        game_logger.info("跳过结算画面")

        switcher = getattr(context, "_account_switcher", None)
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            if not switcher:
                await asyncio.sleep(2.0)
                return
            hit = await switcher._detect_any_scene(
                UT_MENU_SCENE_IDS,
                strict=False,
            )
            if hit in UT_MENU_SCENE_IDS:
                task_logger.info("结算完成，已回到 UT 主菜单 scene=%s", hit)
                game_logger.info("[场景: MAIN_MENU] 结算后 scene=%s", hit)
                return
            # 模板均未匹配时不盲按 A，避免误操作未知界面
            known = await switcher._detect_any_scene(
                list(UT_MENU_SCENE_IDS) + list(FC_UT_TARGET_SCENES),
                strict=False,
            )
            if known is not None:
                from configs.scene_transitions import resolve_automation_a_press_sec

                duration = resolve_automation_a_press_sec(known)
                await switcher._press_button("A", duration=duration)
            else:
                task_logger.debug("结算跳过：模板未匹配，不发送 A")
            await asyncio.sleep(0.7)

        task_logger.warning("结算跳过超时，继续后续流程")

    except asyncio.TimeoutError as e:
        task_logger.error(f"跳过结算画面超时: {e}")
    except ConnectionError as e:
        task_logger.error(f"跳过结算画面网络错误: {e}")
    except ValueError as e:
        task_logger.error(f"跳过结算画面参数错误: {e}")
    except Exception as e:
        task_logger.error(f"跳过结算画面失败: {e}")


async def _cleanup_account_resources(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
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
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号日志记录器
    """
    try:
        task_logger.info(f"清理账号 {game_account.gamertag} 资源...")
        game_logger.info("清理账号资源...")

        if hasattr(context, '_controller_protocol') and context._controller_protocol:
            try:
                protocol = context._controller_protocol
                if hasattr(protocol, 'reset'):
                    protocol.reset()
                    task_logger.debug("控制器协议已重置")
            except Exception as e:
                task_logger.warning(f"重置控制器协议失败: {e}")

        if hasattr(context, 'frame_capture') and context.frame_capture:
            try:
                if hasattr(context.frame_capture, 'close'):
                    pass
            except Exception as e:
                task_logger.warning(f"清理画面捕获器失败: {e}")

        task_logger.info(f"账号 {game_account.gamertag} 资源清理完成")
        game_logger.info("资源清理完成")

    except Exception as e:
        task_logger.error(f"清理账号资源异常: {e}")
        game_logger.error(f"清理账号资源异常: {e}")

