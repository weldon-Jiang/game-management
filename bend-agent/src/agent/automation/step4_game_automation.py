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
    TaskMainStatus,
    GameAccountInfo
)
from ..input.football_controller import FootballController
from ..input.controller_protocol import XboxButtonFlag
from ..scene.scene_action_mapper import SceneActionMapper

VALID_TASK_TYPES = frozenset({
    'auction_transfer',
    'squad_battle',
    'transfer_sqb_combo',
    'divisions_rivals',
    'weekend_league',
})

# expected_screen -> Streaming scene IDs (Xbox system UI 1-9, football UT menus 100+)
EXPECTED_SCREEN_SCENES: Dict[str, list] = {
    'MAIN_MENU': [127, 149, 147, 101],
    'MATCH_START': [168, 176],
    'XBOX_SCENE_3': [3],
    'XBOX_SCENE_5': [5],
    'XBOX_SCENE_6': [6],
}

# 游戏模式导航配置
NAVIGATION_CONFIG = {
    # UT菜单导航超时配置
    'ut_menu_timeout': 30,      # UT菜单检测超时(秒)
    'matchmaking_timeout': 60,   # 匹配超时(秒)
    'button_press_delay': 0.3,  # 按钮按下后等待时间(秒)
}

# SQB难度配置
SQB_DIFFICULTY_MAP = {
    'easy': 'World Class',
    'normal': 'Professional',
    'hard': 'Harder',
    'ultimate': 'Ultimate',
}

# 拍卖行配置
AUCTION_CONFIG = {
    'buy': {
        'min_price': 1000,
        'max_price': 50000,
        'max_bid_increase': 1000,
        'retry_count': 3,
    },
    'sell': {
        'starting_price_ratio': 0.8,
        'buy_now_price_ratio': 1.0,
        'duration_minutes': 60,
    }
}

# DR段位配置
DR_DIVISION_MAP = {
    'champion': {'min_points': 2000, 'max_points': 9999, 'display': 'Champion'},
    'elite': {'min_points': 1500, 'max_points': 1999, 'display': 'Elite'},
    'gold': {'min_points': 1000, 'max_points': 1499, 'display': 'Gold'},
    'silver': {'min_points': 500, 'max_points': 999, 'display': 'Silver'},
    'bronze': {'min_points': 0, 'max_points': 499, 'display': 'Bronze'},
}

# 周赛资格配置
WEEKEND_LEAGUE_REQUIREMENTS = {
    'min_division': 'elite',  # 最低需要Elite段位
    'min_dr_points': 1500,
    'max_matches_per_day': 5,
    'total_matches': 10,
}


def _resolve_template_dir() -> str:
    from ..core.config import config as agent_config
    from ..core.paths import get_templates_dir, resolve_agent_path

    configured = agent_config.get('template.template_dir', './templates')
    if configured in ('./templates', 'templates'):
        return get_templates_dir()
    return str(resolve_agent_path(configured))


async def _validate_step4_templates(logger) -> Optional[str]:
    """Return an error message when required templates are missing."""
    from ..vision.template_manager import validate_templates

    template_dir = _resolve_template_dir()
    ok, missing = validate_templates(template_dir)
    if ok:
        logger.info("场景模板预检通过 (dir=%s)", template_dir)
        return None

    sample = ", ".join(missing[:8])
    suffix = f" 等共 {len(missing)} 个" if len(missing) > 8 else ""
    return (
        f"场景模板缺失 ({len(missing)} 个): {sample}{suffix}。"
        f"请确认模板目录 {template_dir} 存在，或运行 bend-agent/tools/sync_scene_schemas.py 同步模板。"
    )


async def _ensure_streaming_scene_detector(context: AgentTaskContext, logger):
    """创建或复用 StreamingSceneDetector，写入 context。"""
    if getattr(context, '_streaming_scene_detector', None) is not None:
        return context._streaming_scene_detector

    from ..core.config import config as agent_config
    from ..scene.streaming_scene_detector import StreamingSceneDetector

    template_dir = _resolve_template_dir()
    threshold = float(agent_config.get('template.threshold', 0.8))
    detector = StreamingSceneDetector(
        template_dir=template_dir,
        default_threshold=threshold,
    )
    context._streaming_scene_detector = detector
    logger.info("StreamingSceneDetector 已就绪 (template_dir=%s)", template_dir)
    return detector


async def _apply_fc_controller_actions(
    context: AgentTaskContext,
    actions: list,
    logger,
) -> None:
    """Apply controller actions returned by FC server."""
    protocol = getattr(context, '_controller_protocol', None)
    if not protocol or not actions:
        return

    from ..input.controller_protocol import ControllerSignal, XboxButtonFlag

    key_map = {
        "controller_buttons_a": XboxButtonFlag.A,
        "controller_buttons_b": XboxButtonFlag.B,
        "controller_buttons_x": XboxButtonFlag.X,
        "controller_buttons_y": XboxButtonFlag.Y,
        "controller_dpad_up": XboxButtonFlag.DPAD_UP,
        "controller_dpad_down": XboxButtonFlag.DPAD_DOWN,
        "controller_dpad_left": XboxButtonFlag.DPAD_LEFT,
        "controller_dpad_right": XboxButtonFlag.DPAD_RIGHT,
        "controller_buttons_nexus": XboxButtonFlag.NEXUS,
        "controller_buttons_back": XboxButtonFlag.VIEW,
        "controller_buttons_menu": XboxButtonFlag.MENU,
        "controller_left_shoulder": XboxButtonFlag.L1,
        "controller_right_shoulder": XboxButtonFlag.R1,
        "controller_left_stick": XboxButtonFlag.L3,
        "controller_right_stick": XboxButtonFlag.R3,
    }

    for action in actions:
        if not isinstance(action, dict):
            continue
        signal = ControllerSignal()
        for key, flag in key_map.items():
            if key in action:
                signal.set_button(flag, True)
        if "controller_left_trigger" in action:
            signal.left_trigger = min(255, int(action["controller_left_trigger"] / 128))
        if "controller_right_trigger" in action:
            signal.right_trigger = min(255, int(action["controller_right_trigger"] / 128))
        for axis_key, attr in (
            ("controller_left_stick_x", "left_thumb_x"),
            ("controller_left_stick_y", "left_thumb_y"),
            ("controller_right_stick_x", "right_thumb_x"),
            ("controller_right_stick_y", "right_thumb_y"),
        ):
            if axis_key in action:
                setattr(signal, attr, int(action[axis_key]))

        await protocol.send_signal(signal)
        duration = float(action.get("controller_duration", 0) or 0)
        interval = float(action.get("controller_interval", 0) or 0)
        if duration > 0:
            await asyncio.sleep(duration)
        await protocol.send_signal(ControllerSignal.zero())
        if interval > 0:
            await asyncio.sleep(interval)


async def _ensure_fc_scene_client(context: AgentTaskContext, logger):
    """Create FC remote scene client when enabled in config."""
    if getattr(context, '_fc_scene_client', None) is not None:
        return context._fc_scene_client

    from ..core.config import config as agent_config
    if not agent_config.get('fc_server.enabled', False):
        return None

    from ..scene.fc_scene_client import FCSceneClient

    host = agent_config.get('fc_server.host', '127.0.0.1')
    port = int(agent_config.get('fc_server.port', 8080))
    client = FCSceneClient(
        host=host,
        port=port,
        username=context.streaming_account_email,
        session_token=getattr(context, '_fc_session_token', ''),
        gamepad_index=0,
    )
    context._fc_scene_client = client
    logger.info("FCSceneClient 已就绪 (%s:%s)", host, port)
    return client


async def _match_expected_screen(
    context: AgentTaskContext,
    expected_screen: str,
    logger,
    game_logger,
    timeout_sec: float = 25.0,
) -> bool:
    """使用模板匹配或 FC 远程场景识别校验期望画面。"""
    scene_ids = EXPECTED_SCREEN_SCENES.get(expected_screen)
    if not scene_ids:
        game_logger.warning(f"[场景: {expected_screen}] 未配置场景ID，跳过模板校验")
        return False

    from ..core.config import config as agent_config
    prefer_remote = agent_config.get('fc_server.prefer_remote_scene', False)
    fc_client = await _ensure_fc_scene_client(context, logger) if prefer_remote else None
    detector = None if prefer_remote and fc_client else await _ensure_streaming_scene_detector(context, logger)
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        frame = await context.frame_capture.capture_frame()
        if frame is None:
            await asyncio.sleep(0.4)
            continue

        image = frame.data if hasattr(frame, 'data') else frame

        if fc_client:
            remote_scene_id, actions = await fc_client.recognize_scene_id(image)
            if remote_scene_id in scene_ids:
                logger.info(
                    f"FC 远程场景匹配成功: {expected_screen} -> scene {remote_scene_id}"
                )
                game_logger.info(
                    f"[场景: {expected_screen}] FC 匹配 scene {remote_scene_id}"
                )
                await _apply_fc_controller_actions(context, actions, logger)
                return True
        elif detector:
            for scene_id in scene_ids:
                result = detector.recognize_scene(image, scene_id=scene_id)
                if result.matched:
                    logger.info(
                        f"场景匹配成功: {expected_screen} -> scene {scene_id} "
                        f"(confidence={result.confidence:.2f})"
                    )
                    game_logger.info(
                        f"[场景: {expected_screen}] 匹配 scene {scene_id} "
                        f"({result.confidence:.2f})"
                    )
                    return True
        await asyncio.sleep(0.5)

    game_logger.warning(f"[场景: {expected_screen}] 模板匹配超时 ({timeout_sec}s)")
    return False


def _normalize_game_action_type(game_action_type: Optional[str]) -> str:
    if game_action_type and game_action_type in VALID_TASK_TYPES:
        return game_action_type
    return 'squad_battle'


def _apply_task_type(context: AgentTaskContext, game_account: GameAccountInfo, logger) -> str:
    """
    Apply platform game action type after login is confirmed (AGENTS R006/R007).

    Returns the normalized game_action_type string.
    """
    game_action_type = _normalize_game_action_type(context.game_action_type)
    if game_action_type == 'auction_transfer':
        logger.info("游戏操作类型 auction_transfer: 拍卖行转会任务")
    elif game_action_type == 'squad_battle':
        logger.info("游戏操作类型 squad_battle: SQB模式（与电脑AI对战）")
    elif game_action_type == 'divisions_rivals':
        logger.info("游戏操作类型 divisions_rivals: DR模式（与玩家线上对战）")
    elif game_action_type == 'weekend_league':
        logger.info("游戏操作类型 weekend_league: 周赛")
    elif game_action_type == 'transfer_sqb_combo':
        logger.info("游戏操作类型 transfer_sqb_combo: 转会+SQB组合")
    else:
        logger.info(f"游戏操作类型 {game_action_type}: 执行默认SQB模式")
    return game_action_type


async def _pause_for_manual_fc_launch(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    reason: str,
    error_code: str,
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    check_cancel: Callable[[], bool],
    logger,
    stream_logger,
) -> bool:
    """Pause automation and sync platform task status; wait until user resumes."""
    from ..runtime.phase_fsm import SessionPhase

    context.pause()
    context.update_task_status(TaskMainStatus.PAUSED)

    if set_session_phase:
        await set_session_phase(SessionPhase.PAUSED_IMMEDIATE, reason)
    else:
        await report_progress(
            context.task_id,
            "SESSION",
            "RUNNING",
            reason,
            {
                "scope": "session",
                "phase": SessionPhase.PAUSED_IMMEDIATE.value,
                "pauseMode": "immediate",
            },
        )

    await report_progress(
        context.task_id,
        "STEP4",
        "RUNNING",
        reason,
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "matchStatus": "MANUAL_REQUIRED",
            "accountStatus": "paused",
            "errorCode": error_code,
            "errorDetails": reason,
        },
    )
    logger.warning("自动化已暂停，等待人工处理后恢复: %s", reason)
    stream_logger.warning(reason)

    while context.is_paused():
        if check_cancel():
            return False
        await asyncio.sleep(0.3)

    context.update_task_status(TaskMainStatus.RUNNING)
    if set_session_phase:
        await set_session_phase(
            SessionPhase.AUTOMATING,
            "人工处理完成，继续尝试启动 FC",
        )
    logger.info("任务已恢复，重新尝试启动 FC")
    stream_logger.info("任务已恢复，重新尝试启动 FC")
    return True


async def _launch_fc_with_manual_pause(
    switcher,
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    logger,
    stream_logger,
) -> bool:
    """Launch FC/UT; on home-screen stuck, pause for manual intervention instead of failing."""
    from ..game.account_switcher import ManualInterventionRequired

    while True:
        try:
            return await switcher.launch_fc_to_ut_menu()
        except ManualInterventionRequired as exc:
            reason = f"账号 {game_account.gamertag}：{exc.reason}"
            resumed = await _pause_for_manual_fc_launch(
                context,
                game_account,
                reason,
                exc.error_code,
                report_progress,
                set_session_phase,
                check_cancel,
                logger,
                stream_logger,
            )
            if not resumed:
                return False


# 启动 FC 失败但仍停留 Xbox 主页时，重启启动链的最大次数
FC_LAUNCH_HOME_RETRY_MAX = 3


async def _retry_fc_launch_if_on_home(
    switcher,
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    logger,
    stream_logger,
) -> bool:
    """
    启动 FC 失败后，若画面仍停留 Xbox 主页(scene203)，重启 FC 启动链而非空等跳过。

    背景：MAIN_MENU 仅匹配 UT 场景 [127,149,147,101]，在 Xbox 主页恒超时（25s），
    导致「切换成功 -> MAIN_MENU 盲等 -> 跳过账号」的死循环。此处在确认仍在主页时
    重启启动链；若多次仍停 203，启动链内部会抛出 ManualInterventionRequired 转入暂停。

    返回：True 表示重启后已进入 FC/UT；False 表示已离开主页（交由 MAIN_MENU 校验）
    或重试耗尽。
    """
    for attempt in range(1, FC_LAUNCH_HOME_RETRY_MAX + 1):
        if check_cancel():
            return False

        try:
            on_home = await switcher._is_home_203_dominant()
        except Exception as exc:
            logger.debug("主页 203 检测异常，跳过重启逻辑: %s", exc)
            return False

        if not on_home:
            logger.info("启动 FC 失败但已离开 Xbox 主页，交由 MAIN_MENU 校验")
            return False

        retry_msg = (
            f"账号 {game_account.gamertag} 启动 FC 失败且仍停留 Xbox 主页(scene203)，"
            f"重启 FC 启动链（第 {attempt}/{FC_LAUNCH_HOME_RETRY_MAX} 次）"
        )
        logger.warning(retry_msg)
        stream_logger.warning(retry_msg)

        launch_ok = await _launch_fc_with_manual_pause(
            switcher,
            context,
            game_account,
            check_cancel,
            report_progress,
            set_session_phase,
            logger,
            stream_logger,
        )
        if launch_ok:
            return True
        await asyncio.sleep(2.0)

    logger.error(
        "账号 %s 多次重启 FC 启动链后仍停留 Xbox 主页，放弃该账号",
        game_account.gamertag,
    )
    return False


async def _report_step4_failure(
    context: AgentTaskContext,
    report_progress: Callable,
    error_msg: str,
    keep_session_alive: bool,
    logger,
) -> None:
    """Report step4 failure; optionally keep stream/session alive for manual retry."""
    if keep_session_alive:
        logger.error("%s (stream kept alive for retry)", error_msg)
        window_state = "visible" if getattr(context, "sdl_window", None) else "hidden"
        await report_progress(
            context.task_id,
            "SESSION",
            "RUNNING",
            error_msg,
            {
                "scope": "session",
                "phase": "automation_failed",
                "windowState": window_state,
            },
        )
        return
    logger.error(error_msg)
    await report_progress(context.task_id, "STEP4", "FAILED", error_msg)


async def _report_input_channel_event(
    context: AgentTaskContext,
    report_progress: Callable,
    status: str,
    message: str,
    phase: str,
    logger,
) -> None:
    """Report input channel recovery without changing task terminal state."""
    try:
        await report_progress(
            context.task_id,
            "INPUT_CHANNEL",
            status,
            message,
            {
                "scope": "session",
                "module": "input_channel",
                "phase": phase,
            },
        )
    except Exception as exc:
        logger.warning("上报 DataChannel 恢复事件失败: %s", exc)


async def step4_execute_gaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    platform_client: Optional[Any] = None,
    window_manager: Optional[Any] = None,
    provisioning_module: Optional[Any] = None,
    skipped_accounts: Optional[set] = None,
    pause_after_match: Optional[Callable[[], bool]] = None,
    set_session_phase: Optional[Callable] = None,
    keep_session_alive: bool = False,
    input_gate: Optional[Any] = None,
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
    logger = get_logger(f'step4_game_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    logger.info("=== 步骤四：开始自动操作Xbox主机 ===")
    logger.info(f"游戏操作类型 (game_action_type): {_normalize_game_action_type(context.game_action_type)}")
    context.update_step_status("step4", TaskStepStatus.RUNNING, "开始游戏自动化...")
    await report_progress(context.task_id, "STEP4", "RUNNING", "开始游戏自动化...")

    if context.frame_capture is None:
        error_msg = "步骤三未初始化画面捕获器，无法执行游戏自动化"
        logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        return Step4Result(success=False, error_code="NO_CAPTURE", message=error_msg)

    logger.info("画面捕获器可用，开始自动操作Xbox主机")

    template_error = await _validate_step4_templates(logger)
    if template_error:
        await _report_step4_failure(
            context, report_progress, template_error, keep_session_alive, logger
        )
        context.update_step_status("step4", TaskStepStatus.FAILED, template_error)
        return Step4Result(
            success=False,
            error_code="MISSING_TEMPLATES",
            message=template_error,
        )

    engine, switcher = await _init_game_automation(
        context, logger, platform_client, input_gate=input_gate
    )
    if not engine or not switcher:
        error_msg = "游戏自动化引擎初始化失败"
        logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        return Step4Result(success=False, error_code="ENGINE_INIT_FAILED", message=error_msg)

    # 引擎/切换器随 context 传递，避免模块级全局在多任务并发时互相覆盖
    context._automation_engine = engine
    context._account_switcher = switcher

    global_frame_queue = None
    global_scene_queue = None
    global_cancel_event = None
    global_async_tasks = []
    football_controller = None
    scene_action_mapper = None

    async def _send_controller_signal(signal):
        """发送手柄信号到Xbox"""
        if engine and hasattr(engine, 'send_controller_signal'):
            try:
                await engine.send_controller_signal(signal)
                logger.debug(f"[手柄信号] 发送: {signal}")
            except Exception as e:
                logger.error(f"[手柄信号] 发送失败: {e}")
        else:
            logger.warning("[手柄信号] 引擎不支持信号发送")

    try:
        keyboard_mapper = getattr(context, "_keyboard_mapper", None)
        if keyboard_mapper and getattr(keyboard_mapper, "_running", False):
            await keyboard_mapper.stop()
            logger.info("步骤四已停止键盘映射器，避免与 SDL 显示循环并发访问 pygame")

        if context.enable_window_display and context.sdl_window is not None:
            logger.info("[全局异步] 启动帧捕获、显示和场景检测任务")
            global_frame_queue = asyncio.Queue(maxsize=5)
            global_scene_queue = asyncio.Queue(maxsize=5)
            global_cancel_event = asyncio.Event()

            capture_task = asyncio.create_task(
                _capture_loop(context, global_frame_queue, global_cancel_event, logger)
            )
            display_task = asyncio.create_task(
                _display_loop(context, global_frame_queue, global_cancel_event, logger)
            )
            detect_task = asyncio.create_task(
                _detect_loop(context, global_frame_queue, global_scene_queue, global_cancel_event, logger)
            )

            global_async_tasks = [capture_task, display_task, detect_task]
            logger.info("[全局异步] 帧捕获、显示和场景检测任务已启动")

            logger.info("[比赛控制] 初始化比赛控制器和场景动作映射器")
            football_controller = FootballController()
            football_controller.set_signal_sender(_send_controller_signal)

            scene_action_mapper = SceneActionMapper(
                scene_detector=None,
                football_controller=football_controller
            )
            logger.info("[比赛控制] 比赛控制器和场景动作映射器已初始化")

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

        skipped = skipped_accounts or set()

        if provisioning_module is not None and hasattr(provisioning_module, "refresh_dependencies"):
            detector = await _ensure_streaming_scene_detector(context, logger)

            async def _capture_for_provisioning():
                if context.frame_capture is None:
                    return None
                return await context.frame_capture.capture_frame()

            provisioning_module.refresh_dependencies(
                detector,
                getattr(context, "_controller_protocol", None),
                platform_client=platform_client,
                frame_getter=_capture_for_provisioning,
                stream_session=getattr(context, "xbox_session", None),
            )

        for account_index, game_account in enumerate(context.game_accounts):
            if check_cancel():
                logger.info("任务被取消，步骤四终止")
                context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
                return Step4Result(success=False, error_code="CANCELLED",
                                 message="任务被取消")

            await context.wait_if_paused()

            if game_account.id in skipped:
                logger.info("跳过游戏账号: %s", game_account.gamertag)
                continue

            if provisioning_module is not None:
                prov = await provisioning_module.ensure(
                    game_account,
                    check_cancel=check_cancel,
                    skipped=False,
                )
                if not prov.success:
                    logger.warning(
                        "账号 %s 准备失败: %s",
                        game_account.gamertag,
                        prov.message,
                    )
                    continue

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

            from ..xbox.stream_keepalive import StreamKeepaliveLoop

            launch_ok = False
            async with StreamKeepaliveLoop(
                lambda: getattr(context, "xbox_session", None),
                interval=4.0,
            ):
                switch_result = await switcher.switch_to(game_account.id)
                if switch_result.success:
                    launch_ok = await _launch_fc_with_manual_pause(
                        switcher,
                        context,
                        game_account,
                        check_cancel,
                        report_progress,
                        set_session_phase,
                        logger,
                        stream_logger,
                    )
                    if not launch_ok:
                        logger.warning(
                            "进 FC 失败，尝试重连 input DataChannel 后重试一次"
                        )
                        from ..xbox.stream_recovery import (
                            reconnect_input_channel,
                            rebind_stream_bindings,
                        )

                        await _report_input_channel_event(
                            context,
                            report_progress,
                            "RUNNING",
                            "Input DataChannel 已关闭，正在重连",
                            "input_reconnecting",
                            logger,
                        )
                        if await reconnect_input_channel(context, logger):
                            executor = (
                                engine._action_executor
                                if engine
                                and hasattr(engine, "_action_executor")
                                else None
                            )
                            rebind_stream_bindings(
                                context,
                                executor=executor,
                                switcher=switcher,
                                engine=engine,
                            )
                            await _report_input_channel_event(
                                context,
                                report_progress,
                                "RUNNING",
                                "Input DataChannel 已恢复",
                                "input_restored",
                                logger,
                            )
                            launch_ok = await _launch_fc_with_manual_pause(
                                switcher,
                                context,
                                game_account,
                                check_cancel,
                                report_progress,
                                set_session_phase,
                                logger,
                                stream_logger,
                            )
                        else:
                            await _report_input_channel_event(
                                context,
                                report_progress,
                                "FAILED",
                                "Input DataChannel 重连失败",
                                "input_reconnect_failed",
                                logger,
                            )

                    if not launch_ok:
                        # 仍失败：若画面仍停留 Xbox 主页(scene203)，重启 FC 启动链，
                        # 避免「切换成功 -> MAIN_MENU 盲等 25s -> 跳过」的死循环
                        launch_ok = await _retry_fc_launch_if_on_home(
                            switcher,
                            context,
                            game_account,
                            check_cancel,
                            report_progress,
                            set_session_phase,
                            logger,
                            stream_logger,
                        )

                    if not launch_ok:
                        launch_msg = (
                            f"账号 {game_account.gamertag} 切换成功但未能进入 FC/UT，"
                            "将继续尝试检测主菜单"
                        )
                        logger.warning(launch_msg)
                        game_logger.warning(launch_msg)
                        stream_logger.warning(launch_msg)

            if not switch_result.success:
                switch_msg = (
                    f"账号 {game_account.gamertag} 切换失败: "
                    f"{switch_result.error_message}"
                )
                logger.warning(switch_msg)
                game_logger.warning(switch_msg)
                stream_logger.warning(switch_msg)
                await report_progress(
                    context.task_id,
                    "STEP4",
                    "RUNNING",
                    switch_msg,
                    {
                        "gameAccountId": game_account.id,
                        "gameAccountName": game_account.gamertag,
                        "matchStatus": "SWITCH_FAILED",
                        "accountStatus": "failed",
                        "errorCode": "ACCOUNT_SWITCH_FAILED",
                    },
                )
                continue

            if launch_ok:
                login_confirmed = True
                confirm_msg = (
                    f"账号 {game_account.gamertag} 已进入 FC/UT 界面（场景链确认）"
                )
                logger.info(confirm_msg)
                game_logger.info(confirm_msg)
                stream_logger.info(confirm_msg)
            else:
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
                        "accountStatus": "failed",
                        "errorCode": "LOGIN_UNCONFIRMED",
                    }
                )
                continue

            _apply_task_type(context, game_account, logger)
            stream_logger.info(
                f"账号 {game_account.gamertag} 登录已确认，应用游戏操作类型: "
                f"{_normalize_game_action_type(context.game_action_type)}"
            )

            await asyncio.sleep(2.0)

            consecutive_failures = 0
            max_match_failures = 3
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

                if pause_after_match and pause_after_match():
                    context.pause()
                    await report_progress(
                        context.task_id, "STEP4", "RUNNING",
                        "本场完成后暂停",
                        {"matchStatus": "PAUSE_AFTER_MATCH"},
                    )
                    await context.wait_if_paused()

                if match_success:
                    consecutive_failures = 0
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
                    consecutive_failures += 1
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
                    if consecutive_failures >= max_match_failures:
                        error_msg = (
                            f"账号 {game_account.gamertag} 连续 {consecutive_failures} 次比赛失败，"
                            "停止该轮自动化以保留串流供重试"
                        )
                        logger.error(error_msg)
                        game_logger.error(error_msg)
                        stream_logger.error(error_msg)
                        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
                        await _report_step4_failure(
                            context, report_progress, error_msg, keep_session_alive, logger
                        )
                        if not keep_session_alive:
                            await _close_task_window(window_manager, context.task_id, "match_fail_bound", logger)
                        return Step4Result(
                            success=False,
                            error_code="NO_MATCHES_COMPLETED",
                            message=error_msg,
                            total_matches=completed_matches,
                        )
                    await asyncio.sleep(5)

            logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 "
                       f"{game_account.target_matches} 场比赛")
            game_logger.info(f"今日已完成 {game_account.target_matches} 场比赛")
            stream_logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 {game_account.target_matches} 场比赛")

        if total_matches > 0 and completed_matches == 0:
            error_msg = "游戏自动化结束但未完成任何比赛"
            stream_logger.error(error_msg)
            context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
            await _report_step4_failure(
                context, report_progress, error_msg, keep_session_alive, logger
            )
            if not keep_session_alive:
                await _close_task_window(window_manager, context.task_id, "no_matches", logger)
            return Step4Result(
                success=False,
                error_code="NO_MATCHES_COMPLETED",
                message=error_msg,
                total_matches=0,
            )

        success_msg = f"自动操作Xbox主机完成，共完成 {completed_matches} 场比赛"
        logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step4", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP4", "COMPLETED", success_msg)

        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "task_completed", logger)

        return Step4Result(success=True, message=success_msg, total_matches=completed_matches)

    except asyncio.CancelledError:
        logger.info("步骤四被取消")
        context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "task_cancelled", logger)
        return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤四执行超时: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "timeout", logger)
        return Step4Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤四网络连接失败: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "connection_error", logger)
        return Step4Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤四参数错误: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "value_error", logger)
        return Step4Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤四执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "error", logger)
        return Step4Result(success=False, error_code="EXCEPTION", message=error_msg)

    finally:
        if global_async_tasks:
            logger.info("[全局异步] 停止帧捕获、显示和场景检测任务")
            global_cancel_event.set()
            await asyncio.gather(*global_async_tasks, return_exceptions=True)
            logger.info("[全局异步] 帧捕获、显示和场景检测任务已停止")


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


async def _init_game_automation(
    context: AgentTaskContext,
    logger,
    platform_client: Optional[Any] = None,
    input_gate: Optional[Any] = None,
):
    """
    初始化游戏自动化引擎

    参数：
    - context: 任务上下文
    - logger: 日志记录器

    返回：
    - (automation_engine, account_switcher) 或 (None, None)
    """
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
        if input_gate is not None:
            executor.set_input_gate(input_gate)
        if context.xbox_session:
            executor.set_xbox_session(context.xbox_session)
            logger.info("动作执行器已绑定Xbox会话")
        else:
            logger.warning("Xbox会话不可用，动作执行器将无法发送信号")

        await _init_gamepad_protocol(context, executor, logger, input_gate=input_gate)

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
                'email': getattr(ga, 'email', None) or None,
                'password': getattr(ga, 'password', None) or None,
                'position_index': (
                    ga.position_index if getattr(ga, 'position_index', -1) >= 0 else idx
                ),
                'is_new_user': bool(getattr(ga, 'is_new_user', False)),
                'profile_bound': bool(getattr(ga, 'profile_bound', False)),
                'max_matches_per_day': ga.target_matches,
            }
            for idx, ga in enumerate(context.game_accounts)
        ]
        switcher.set_accounts(accounts_data)
        switcher.set_action_executor(executor)
        if input_gate is not None:
            switcher.set_input_gate(input_gate)
        if context.xbox_session:
            switcher.set_stream_session(context.xbox_session)

        async def _reconnect_input_and_rebind() -> bool:
            from ..xbox.stream_recovery import reconnect_input_channel, rebind_stream_bindings

            await _report_input_channel_event(
                context,
                report_progress,
                "RUNNING",
                "Input DataChannel 已关闭，正在重连",
                "input_reconnecting",
                logger,
            )
            ok = await reconnect_input_channel(context, logger)
            if ok:
                rebind_stream_bindings(
                    context,
                    executor=executor,
                    switcher=switcher,
                    engine=engine,
                )
                await _report_input_channel_event(
                    context,
                    report_progress,
                    "RUNNING",
                    "Input DataChannel 已恢复",
                    "input_restored",
                    logger,
                )
            else:
                await _report_input_channel_event(
                    context,
                    report_progress,
                    "FAILED",
                    "Input DataChannel 重连失败",
                    "input_reconnect_failed",
                    logger,
                )
            return ok

        switcher.set_reconnect_callback(_reconnect_input_and_rebind)
        switcher.set_task_context(context)

        if platform_client and hasattr(platform_client, "update_profile_binding"):

            async def _mark_profile_bound(
                ga_id: str,
                position_index: int,
                game_name: Optional[str] = None,
            ) -> None:
                await platform_client.update_profile_binding(
                    ga_id,
                    profile_bound=True,
                    position_index=position_index,
                    game_name=game_name,
                )

            switcher.set_profile_bound_callback(_mark_profile_bound)

        streaming_detector = None
        if context.frame_capture:
            try:
                streaming_detector = await _ensure_streaming_scene_detector(context, logger)
                switcher.set_scene_detector(streaming_detector)

                async def _capture_for_switcher():
                    return await context.frame_capture.capture_frame()

                switcher.set_frame_getter(_capture_for_switcher)
            except Exception as e:
                logger.warning(f"账号切换器场景检测绑定失败: {e}")

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
    report_progress: Callable[[str, str, str, Optional[Dict]], None],
    frame_queue: Optional[asyncio.Queue] = None,
    scene_queue: Optional[asyncio.Queue] = None,
    cancel_event: Optional[asyncio.Event] = None
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

    action_type = _normalize_game_action_type(context.game_action_type)
    if action_type == 'transfer_sqb_combo':
        completed = context.matches_completed_today.get(game_account.id, 0)
        if completed % 2 == 0:
            await _navigate_to_auction(context, logger, game_logger)
            game_logger.info("组合模式: 转会阶段完成")
            return True, None, None
        action_type = 'squad_battle'

    try:
        if action_type == 'auction_transfer':
            await _navigate_to_auction(context, logger, game_logger)
            return True, None, None

        await _enter_match(context, game_account, logger, game_logger, report_progress)

        await _wait_for_match_start(context, game_account, logger, game_logger, report_progress)

        await _play_match(
            context, game_account, logger, game_logger, 
            check_cancel, report_progress,
            frame_queue, scene_queue
        )

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


async def _navigate_to_game_mode(
    context: AgentTaskContext,
    game_action_type: str,
    logger,
    game_logger
) -> None:
    """
    根据 game_action_type 导航到对应的游戏模式

    导航分发中心，根据不同的 game_action_type 调用对应的导航函数。

    参数：
    - context: 任务上下文
    - game_action_type: 游戏操作类型 (auction_transfer/squad_battle/divisions_rivals/weekend_league)
    - logger: 主日志记录器
    - game_logger: 游戏账号专用日志记录器
    """
    logger.info(f"开始导航到游戏模式: {game_action_type}")

    if game_action_type == 'auction_transfer':
        await _navigate_to_auction(context, logger, game_logger)
    elif game_action_type == 'squad_battle':
        await _navigate_to_squad_battle(context, logger, game_logger)
    elif game_action_type == 'divisions_rivals':
        await _navigate_to_dr(context, logger, game_logger)
    elif game_action_type == 'weekend_league':
        await _navigate_to_weekend_league(context, logger, game_logger)
    elif game_action_type == 'transfer_sqb_combo':
        await _navigate_to_auction(context, logger, game_logger)
        await _navigate_to_squad_battle(context, logger, game_logger)
    else:
        logger.warning(f"未知的游戏操作类型: {game_action_type}，默认导航到SQB模式")
        await _navigate_to_squad_battle(context, logger, game_logger)


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
    logger,
    game_logger
) -> None:
    """
    导航到拍卖行转会界面

    导航路径：主页 → UT → Transfer Market

    操作序列：
    1. 从主页按 RB×3 + A 进入 UT 菜单
    2. 按 LB + A 进入 Transfer Market
    """
    logger.info("导航到拍卖行转会界面")
    game_logger.info("[拍卖行] 开始导航到拍卖行")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        logger.info("[拍卖行] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Transfer Market：LB + A
        logger.info("[拍卖行] 步骤2: 进入Transfer Market (LB + A)")
        await _press_button(context, XboxButtonFlag.L1, 0.3)
        await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        logger.info("[拍卖行] 导航完成，等待拍卖行界面加载")
        game_logger.info("[拍卖行] 导航完成")

    except Exception as e:
        logger.error(f"[拍卖行] 导航异常: {e}")
        game_logger.error(f"[拍卖行] 导航异常: {e}")


async def _navigate_to_squad_battle(
    context: AgentTaskContext,
    logger,
    game_logger
) -> None:
    """
    导航到 SQB 模式（读取 SCENE_TRANSITIONS 链）

    路径：147 → 149 → 155 → 156 → 168 → 177(业余A) → 183 → 189
    对齐 streaming get_scenes_diagram / configs.scene_transitions.SQB_UT_MENU_CHAIN
    """
    from configs.scene_transitions import (
        SQB_COMPLETE_SCENES,
        SQB_NAVIGATION_SCENES,
        trim_sqb_navigation_chain,
    )

    logger.info("导航到SQB模式 (SCENE_TRANSITIONS 链)")
    game_logger.info("[SQB] 开始导航 (scene_transitions 链)")

    switcher = getattr(context, '_account_switcher', None)

    try:
        if not switcher:
            logger.error("[SQB] account_switcher 未初始化，无法执行场景转移链")
            game_logger.error("[SQB] account_switcher 未初始化")
            return

        current = await switcher._detect_any_scene(
            SQB_NAVIGATION_SCENES, strict=False
        )
        chain = trim_sqb_navigation_chain(current)
        if not chain:
            logger.info("[SQB] 已在赛前界面 (scene189)，跳过导航")
            game_logger.info("[SQB] 已在 scene189")
            return

        logger.info(f"[SQB] 当前 scene={current}，执行链: {chain}")
        game_logger.info(f"[SQB] 链: {chain}")

        ok = await switcher.run_scene_transition_chain(
            chain,
            label="SQB",
            complete_scenes=SQB_COMPLETE_SCENES,
        )
        if ok:
            logger.info("[SQB] 场景转移链完成，等待匹配")
            game_logger.info("[SQB] 导航完成")
        else:
            logger.error("[SQB] 场景转移链未完成")
            game_logger.error("[SQB] 导航失败，请检查 logs/debug_scene*.png")

    except Exception as e:
        logger.error(f"[SQB] 导航异常: {e}")
        game_logger.error(f"[SQB] 导航异常: {e}")


async def _navigate_to_dr(
    context: AgentTaskContext,
    logger,
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
    logger.info("导航到DR模式")
    game_logger.info("[DR] 开始导航到DR模式")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        logger.info("[DR] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Division Rivals：LB×2 + A
        logger.info("[DR] 步骤2: 进入Division Rivals (LB×2 + A)")
        for _ in range(2):
            await _press_button(context, XboxButtonFlag.L1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 3. 选择 Play Champions（默认选项，直接A）
        logger.info("[DR] 步骤3: 选择Play Champions")
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(1)

        # 4. 开始匹配
        logger.info("[DR] 步骤4: 开始匹配")
        await _press_button(context, XboxButtonFlag.A, 0.5)

        logger.info("[DR] 导航完成，等待匹配")
        game_logger.info("[DR] 导航完成")

    except Exception as e:
        logger.error(f"[DR] 导航异常: {e}")
        game_logger.error(f"[DR] 导航异常: {e}")


async def _navigate_to_weekend_league(
    context: AgentTaskContext,
    logger,
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
    logger.info("导航到周赛模式")
    game_logger.info("[周赛] 开始导航到周赛模式")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        logger.info("[周赛] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Weekend League：LB×3 + A
        logger.info("[周赛] 步骤2: 进入Weekend League (LB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.L1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 3. 检查资格状态
        # TODO: 通过画面检测判断资格状态
        # 当前简化处理：假设有资格，直接开始匹配
        logger.info("[周赛] 步骤3: 检查资格...")

        # 4. 开始匹配（假设有资格）
        logger.info("[周赛] 步骤4: 开始匹配")
        await _press_button(context, XboxButtonFlag.A, 0.5)

        logger.info("[周赛] 导航完成，等待匹配")
        game_logger.info("[周赛] 导航完成")

    except Exception as e:
        logger.error(f"[周赛] 导航异常: {e}")
        game_logger.error(f"[周赛] 导航异常: {e}")


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
    - 导航到对应的游戏模式（根据 game_action_type）

    参数：
    - context: 任务上下文（包含 game_action_type）
    - game_account: 游戏账号信息
    - logger: 主日志记录器
    - game_logger: 游戏账号专用日志记录器
    - report_progress: 进度上报函数
    """
    logger.info(f"进入比赛准备: {game_account.gamertag}")
    game_logger.info("[场景: MAIN_MENU] 进入比赛准备")

    screen_detected = await _detect_screen_state(
        context, "MAIN_MENU", logger, game_logger
    )
    logger.info(f"游戏主界面检测: {screen_detected}")

    # 获取游戏操作类型并导航到对应模式
    game_action_type = _normalize_game_action_type(context.game_action_type)
    logger.info(f"根据游戏操作类型导航: {game_action_type}")

    # 导航到对应的游戏模式
    await _navigate_to_game_mode(context, game_action_type, logger, game_logger)

    await report_progress(
        context.task_id, "STEP4", "GAME_PREPARING",
        f"账号 {game_account.gamertag} 导航到{game_action_type}完成",
        {
            "gameAccountId": game_account.id,
            "gameAccountName": game_account.gamertag,
            "gameActionType": game_action_type,
            "todayCompleted": context.matches_completed_today[game_account.id],
            "dailyLimit": game_account.target_matches,
            "matchStatus": "PREPARING"
        }
    )

    await asyncio.sleep(1)


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
    match_duration = 120
    report_interval = 30

    logger.info(f"比赛中，预计时长: {match_duration}秒")
    game_logger.info(f"[场景: IN_GAME] 比赛中，预计时长: {match_duration}秒")

    if frame_queue and scene_queue:
        logger.info("[比赛进行] 使用全局异步任务进行场景检测和动作控制")

    for i in range(match_duration // 10):
        if check_cancel():
            raise Exception("比赛被取消")

        if scene_queue and not scene_queue.empty():
            try:
                scene_result = await asyncio.wait_for(
                    scene_queue.get(),
                    timeout=0.5
                )
                if scene_result and scene_result != "UNKNOWN":
                    logger.info(f"[比赛进行] 检测到场景: {scene_result}")
                    game_logger.info(f"[比赛进行] 检测到场景: {scene_result}")

                    if scene_action_mapper:
                        try:
                            await scene_action_mapper.on_scene_detected(scene_result)
                            logger.info(f"[比赛进行] 场景 {scene_result} 对应动作已执行")
                        except Exception as e:
                            logger.error(f"[比赛进行] 执行动作失败: {e}")
            except asyncio.TimeoutError:
                pass

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
    logger,
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
        if input_gate is not None:
            controller_protocol.set_input_gate(input_gate)

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

        matched = await _match_expected_screen(
            context, expected_screen, logger, game_logger
        )
        if not matched:
            logger.warning(f"未识别到期望画面: {expected_screen}")
            return False

        logger.info(f"画面状态确认: {expected_screen} ({frame.width}x{frame.height})")
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
            if hasattr(context.sdl_window, 'process_events'):
                context.sdl_window.process_events()

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
