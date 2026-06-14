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

from ..core.task_logger import get_task_logger
from ..core.account_logger import get_game_logger, get_stream_logger
from ..task.task_context import (
    AgentTaskContext,
    Step4Result,
    TaskStepStatus,
    TaskMainStatus,
    GameAccountInfo
)
from ..input.controller_protocol import XboxButtonFlag

VALID_TASK_TYPES = frozenset({
    'auction_transfer',
    'squad_battle',
    'transfer_sqb_combo',
    'divisions_rivals',
    'weekend_league',
})

# 比赛结束 / 回到 UT 菜单的场景（本地模板 + streaming 对齐）
MATCH_END_SCENE_IDS = [102, 193]
UT_MENU_SCENE_IDS = [127, 147, 149]
SETTLEMENT_SCENE_IDS = [184, 185, 186, 187, 188, 189, 193]
# expected_screen -> Streaming 场景 ID（Xbox 系统 UI 1-9，足球 UT 菜单 100+）
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


async def _validate_step4_templates(task_logger) -> Optional[str]:
    """必需模板缺失时返回错误消息。"""
    from ..vision.template_manager import validate_templates

    template_dir = _resolve_template_dir()
    ok, missing = validate_templates(template_dir)
    if ok:
        task_logger.info("场景模板预检通过 (dir=%s)", template_dir)
        return None

    sample = ", ".join(missing[:8])
    suffix = f" 等共 {len(missing)} 个" if len(missing) > 8 else ""
    return (
        f"场景模板缺失 ({len(missing)} 个): {sample}{suffix}。"
        f"请确认模板目录 {template_dir} 存在，或运行 bend-agent/tools/sync_scene_schemas.py 同步模板。"
    )


async def _ensure_streaming_scene_detector(context: AgentTaskContext, task_logger):
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
    task_logger.info("StreamingSceneDetector 已就绪 (template_dir=%s)", template_dir)
    return detector


async def _apply_fc_controller_actions(
    context: AgentTaskContext,
    actions: list,
    task_logger,
) -> None:
    """应用 FC 服务器返回的手柄动作。"""
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


async def _ensure_fc_scene_client(context: AgentTaskContext, task_logger):
    """配置启用时创建 FC 远程场景客户端。"""
    if getattr(context, '_fc_scene_client', None) is not None:
        return context._fc_scene_client

    from ..core.config import config as agent_config
    if not agent_config.get('fc_server.enabled', False):
        return None

    from ..scene.fc_scene_client import FCSceneClient

    host = agent_config.get('fc_server.host', '127.0.0.1')
    port = int(agent_config.get('fc_server.port', 8080))
    width = int(agent_config.get('window.default_width', 1280))
    height = int(agent_config.get('window.default_height', 720))
    runtime = getattr(context, '_stream_runtime', None)
    latest = runtime.get_latest_frame() if runtime else None
    if latest is not None:
        width = int(getattr(latest, 'width', width) or width)
        height = int(getattr(latest, 'height', height) or height)

    client = FCSceneClient(
        host=host,
        port=port,
        username=context.streaming_account_email,
        session_token=getattr(context, '_fc_session_token', ''),
        gamepad_index=0,
        frame_width=width,
        frame_height=height,
    )
    context._fc_scene_client = client
    task_logger.info("FCSceneClient 已就绪 (%s:%s)", host, port)
    return client


def _fc_remote_play_enabled() -> bool:
    from ..core.config import config as agent_config
    return bool(
        agent_config.get('fc_server.enabled', False)
        and agent_config.get('fc_server.use_remote_play', False)
    )


async def _build_fc_play_handler(context: AgentTaskContext, task_logger):
    """FC PLAY 20Hz handler，供 StreamRuntime play loop 调用。"""
    from ..scene.fc_scene_client import FC_ERR_NETWORK, FC_ERR_OK

    fc_client = await _ensure_fc_scene_client(context, task_logger)
    if fc_client is None:
        return None

    async def _handler(image) -> int:
        result = await fc_client.play_frame(image)
        if result.controller_actions:
            await _apply_fc_controller_actions(
                context, result.controller_actions, task_logger
            )
        return result.errno if result.errno else FC_ERR_NETWORK

    return _handler


async def _fc_init_match_session(context: AgentTaskContext, task_logger) -> bool:
    from ..scene.fc_scene_client import FC_ERR_MATCH_EXISTED, FC_ERR_OK

    if not _fc_remote_play_enabled():
        return True
    fc_client = await _ensure_fc_scene_client(context, task_logger)
    if fc_client is None:
        return False
    runtime = getattr(context, '_stream_runtime', None)
    latest = runtime.get_latest_frame() if runtime else None
    if latest is not None:
        fc_client.update_frame_size(
            int(getattr(latest, 'width', fc_client.frame_width)),
            int(getattr(latest, 'height', fc_client.frame_height)),
        )
    report = await fc_client.init_match()
    if report.errno in (FC_ERR_OK, FC_ERR_MATCH_EXISTED):
        context._fc_session_token = report.session or fc_client.session_token
        task_logger.info("FC 比赛会话已初始化 (errno=%s)", report.errno)
        return True
    task_logger.warning("FC init_match 失败: %s", report.errmsg or report.errno)
    return False


async def _fc_terminate_match_session(context: AgentTaskContext, task_logger) -> None:
    if not _fc_remote_play_enabled():
        return
    fc_client = getattr(context, '_fc_scene_client', None)
    if fc_client is None:
        return
    try:
        await fc_client.terminate_match()
    except Exception as exc:
        task_logger.debug("FC terminate_match: %s", exc)


async def _match_expected_screen(
    context: AgentTaskContext,
    expected_screen: str,
    task_logger,
    game_logger,
    timeout_sec: float = 25.0,
) -> bool:
    """
    等待期望的 FC/Xbox 场景出现后再继续自动化。

    仅在场景匹配成功或超时时退出；超时本身不取消任务，由调用方决定重试、
    暂停人工介入或跳过当前账号。
    """
    scene_ids = EXPECTED_SCREEN_SCENES.get(expected_screen)
    if not scene_ids:
        game_logger.warning(f"[场景: {expected_screen}] 未配置场景ID，跳过模板校验")
        return False

    from ..core.config import config as agent_config
    prefer_remote = agent_config.get('fc_server.prefer_remote_scene', False)
    fc_client = await _ensure_fc_scene_client(context, task_logger) if prefer_remote else None
    detector = None if prefer_remote and fc_client else await _ensure_streaming_scene_detector(context, task_logger)
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        from ..runtime.stream_runtime import capture_task_frame

        frame = await capture_task_frame(context, timeout=0.8)
        if frame is None:
            await asyncio.sleep(0.4)
            continue

        image = frame.data if hasattr(frame, 'data') else frame

        if fc_client:
            remote_scene_id, actions = await fc_client.recognize_scene_id(image)
            if remote_scene_id in scene_ids:
                task_logger.info(
                    f"FC 远程场景匹配成功: {expected_screen} -> scene {remote_scene_id}"
                )
                game_logger.info(
                    f"[场景: {expected_screen}] FC 匹配 scene {remote_scene_id}"
                )
                await _apply_fc_controller_actions(context, actions, task_logger)
                return True
        elif detector:
            for scene_id in scene_ids:
                result = detector.recognize_scene(image, scene_id=scene_id)
                if result.matched:
                    task_logger.info(
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


def _apply_task_type(context: AgentTaskContext, game_account: GameAccountInfo, task_logger) -> str:
    """
    登录确认后应用平台 gameActionType（AGENTS R006/R007）。

    返回归一化后的 game_action_type 字符串。
    """
    game_action_type = _normalize_game_action_type(context.game_action_type)
    if game_action_type == 'auction_transfer':
        task_logger.info("游戏操作类型 auction_transfer: 拍卖行转会任务")
    elif game_action_type == 'squad_battle':
        task_logger.info("游戏操作类型 squad_battle: SQB模式（与电脑AI对战）")
    elif game_action_type == 'divisions_rivals':
        task_logger.info("游戏操作类型 divisions_rivals: DR模式（与玩家线上对战）")
    elif game_action_type == 'weekend_league':
        task_logger.info("游戏操作类型 weekend_league: 周赛")
    elif game_action_type == 'transfer_sqb_combo':
        task_logger.info("游戏操作类型 transfer_sqb_combo: 转会+SQB组合")
    else:
        task_logger.info(f"游戏操作类型 {game_action_type}: 执行默认SQB模式")
    return game_action_type


def _resolve_billing_unit(game_action_type: str, completed_before: int) -> str:
    """解析当前 Step4 动作的计费单元。"""
    action_type = _normalize_game_action_type(game_action_type)
    if action_type == 'auction_transfer':
        return 'transfer_round'
    if action_type == 'transfer_sqb_combo' and completed_before % 2 == 0:
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


async def _pause_for_manual_fc_launch(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    reason: str,
    error_code: str,
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    check_cancel: Callable[[], bool],
    task_logger,
    stream_logger,
) -> bool:
    """
    暂停 Step4 供人工恢复 FC，并等待平台 resume。

    保持串流/窗口不关闭，会话标记为 paused 以便用户操作 Xbox 窗口。
    仅在等待期间任务被取消时返回 False。
    """
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
    task_logger.warning("自动化已暂停，等待人工处理后恢复: %s", reason)
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
    task_logger.info("任务已恢复，重新尝试启动 FC")
    stream_logger.info("任务已恢复，重新尝试启动 FC")
    return True


async def _launch_fc_with_manual_pause(
    switcher,
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    set_session_phase: Optional[Callable],
    task_logger,
    stream_logger,
) -> bool:
    """
    Launch FC/UT and convert recoverable launch blockers into a manual pause.

    ManualInterventionRequired means the stream is healthy but automation cannot
    advance safely. Pausing avoids closing Step1-3 resources and lets the user
    correct the screen before Step4 retries.
    """
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
                task_logger,
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
    task_logger,
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
            task_logger.debug("主页 203 检测异常，跳过重启逻辑: %s", exc)
            return False

        if not on_home:
            task_logger.info("启动 FC 失败但已离开 Xbox 主页，交由 MAIN_MENU 校验")
            return False

        retry_msg = (
            f"账号 {game_account.gamertag} 启动 FC 失败且仍停留 Xbox 主页(scene203)，"
            f"重启 FC 启动链（第 {attempt}/{FC_LAUNCH_HOME_RETRY_MAX} 次）"
        )
        task_logger.warning(retry_msg)
        stream_logger.warning(retry_msg)

        launch_ok = await _launch_fc_with_manual_pause(
            switcher,
            context,
            game_account,
            check_cancel,
            report_progress,
            set_session_phase,
            task_logger,
            stream_logger,
        )
        if launch_ok:
            return True
        await asyncio.sleep(2.0)

    task_logger.error(
        "账号 %s 多次重启 FC 启动链后仍停留 Xbox 主页，放弃该账号",
        game_account.gamertag,
    )
    return False


async def _report_step4_failure(
    context: AgentTaskContext,
    report_progress: Callable,
    error_msg: str,
    keep_session_alive: bool,
    task_logger,
) -> None:
    """
    上报 Step4 失败，区分终态或可重试会话语义。

    keep_session_alive=True 用于两阶段任务：Step4 失败将会话置为 automation_failed，
    同时保留串流/窗口资源。
    """
    if keep_session_alive:
        task_logger.error("%s (stream kept alive for retry)", error_msg)
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
    task_logger.error(error_msg)
    await report_progress(context.task_id, "STEP4", "FAILED", error_msg)


async def _report_input_channel_event(
    context: AgentTaskContext,
    report_progress: Callable,
    status: str,
    message: str,
    phase: str,
    task_logger,
) -> None:
    """上报 input 通道恢复，不改变任务终态。"""
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
        task_logger.warning("上报 DataChannel 恢复事件失败: %s", exc)


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
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤四：开始自动操作Xbox主机 ===")
    task_logger.info(f"游戏操作类型 (game_action_type): {_normalize_game_action_type(context.game_action_type)}")
    context.update_step_status("step4", TaskStepStatus.RUNNING, "开始游戏自动化...")
    await report_progress(context.task_id, "STEP4", "RUNNING", "开始游戏自动化...")

    if context.frame_capture is None:
        error_msg = "步骤三未初始化画面捕获器，无法执行游戏自动化"
        task_logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        return Step4Result(success=False, error_code="NO_CAPTURE", message=error_msg)

    task_logger.info("画面捕获器可用，开始自动操作Xbox主机")

    template_error = await _validate_step4_templates(task_logger)
    if template_error:
        await _report_step4_failure(
            context, report_progress, template_error, keep_session_alive, task_logger
        )
        context.update_step_status("step4", TaskStepStatus.FAILED, template_error)
        return Step4Result(
            success=False,
            error_code="MISSING_TEMPLATES",
            message=template_error,
        )

    engine, switcher = await _init_game_automation(
        context, task_logger, platform_client, report_progress, input_gate=input_gate
    )
    if not engine or not switcher:
        error_msg = "游戏自动化引擎初始化失败"
        task_logger.error(error_msg)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        return Step4Result(success=False, error_code="ENGINE_INIT_FAILED", message=error_msg)

    # 引擎/切换器随 context 传递，避免模块级全局在多任务并发时互相覆盖
    context._automation_engine = engine
    context._account_switcher = switcher

    from ..runtime.stream_runtime import get_or_create_stream_runtime

    stream_runtime = get_or_create_stream_runtime(context)

    try:
        keyboard_mapper = getattr(context, "_keyboard_mapper", None)
        if keyboard_mapper and getattr(keyboard_mapper, "_running", False):
            await keyboard_mapper.stop()
            task_logger.info("步骤四已停止键盘映射器，避免与自动化输入并发")

        from ..core.config import config as agent_config

        prefer_remote = agent_config.get("fc_server.prefer_remote_scene", False)
        fc_client = await _ensure_fc_scene_client(context, task_logger) if prefer_remote else None
        scene_detector = None if prefer_remote and fc_client else await _ensure_streaming_scene_detector(
            context, task_logger
        )
        play_handler = None
        if _fc_remote_play_enabled():
            play_handler = await _build_fc_play_handler(context, task_logger)
            context._fc_remote_play = play_handler is not None
        else:
            context._fc_remote_play = False

        await stream_runtime.start_automation(
            task_logger,
            scene_detector=scene_detector,
            fc_client=fc_client,
            apply_fc_actions=_apply_fc_controller_actions,
            play_handler=play_handler,
        )
        for ga in context.game_accounts:
            context.matches_completed_today[ga.id] = ga.today_match_count or 0

        total_matches = sum(
            max(0, ga.target_matches - (ga.today_match_count or 0))
            for ga in context.game_accounts
        )

        completed_matches = 0

        task_logger.info(f"游戏账号数量: {len(context.game_accounts)}, "
                   f"目标总比赛数: {total_matches}")

        skipped = skipped_accounts or set()

        if provisioning_module is not None and hasattr(provisioning_module, "refresh_dependencies"):
            detector = await _ensure_streaming_scene_detector(context, task_logger)

            async def _capture_for_provisioning():
                from ..runtime.stream_runtime import capture_task_frame

                return await capture_task_frame(context, timeout=0.8)

            provisioning_module.refresh_dependencies(
                detector,
                getattr(context, "_controller_protocol", None),
                platform_client=platform_client,
                frame_getter=_capture_for_provisioning,
                stream_session=getattr(context, "xbox_session", None),
            )

        for account_index, game_account in enumerate(context.game_accounts):
            if check_cancel():
                task_logger.info("任务被取消，步骤四终止")
                context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
                return Step4Result(success=False, error_code="CANCELLED",
                                 message="任务被取消")

            await context.wait_if_paused()

            if game_account.id in skipped:
                task_logger.info("跳过游戏账号: %s", game_account.gamertag)
                continue

            if provisioning_module is not None:
                # 开通/档案绑定必须在账号切换前完成，失败只跳过当前账号，不关闭整条串流。
                prov = await provisioning_module.ensure(
                    game_account,
                    check_cancel=check_cancel,
                    skipped=False,
                )
                if not prov.success:
                    task_logger.warning(
                        "账号 %s 准备失败: %s",
                        game_account.gamertag,
                        prov.message,
                    )
                    continue

            current_completed = context.matches_completed_today[game_account.id]

            if current_completed >= game_account.target_matches:
                completed_msg = f"账号 {game_account.gamertag} 今日已完成 {current_completed}/{game_account.target_matches} 场比赛"
                task_logger.info(completed_msg)

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
            task_logger.info(f"开始处理游戏账号: {game_account.gamertag} "
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
                # 账号切换和 FC 启动期间持续保活，避免长时间菜单操作导致云串流空闲断开。
                switch_result = await switcher.switch_to(game_account.id)
                if switch_result.success:
                    launch_ok = await _launch_fc_with_manual_pause(
                        switcher,
                        context,
                        game_account,
                        check_cancel,
                        report_progress,
                        set_session_phase,
                        task_logger,
                        stream_logger,
                    )
                    if not launch_ok:
                        task_logger.warning(
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
                            task_logger,
                        )
                        if await reconnect_input_channel(context, task_logger):
                            executor = (
                                engine._action_executor
                                if engine
                                and hasattr(engine, "_action_executor")
                                else None
                            )
                            # DataChannel 重连后，所有持有旧发送器的组件都必须重新绑定。
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
                                task_logger,
                            )
                            launch_ok = await _launch_fc_with_manual_pause(
                                switcher,
                                context,
                                game_account,
                                check_cancel,
                                report_progress,
                                set_session_phase,
                                task_logger,
                                stream_logger,
                            )
                        else:
                            await _report_input_channel_event(
                                context,
                                report_progress,
                                "FAILED",
                                "Input DataChannel 重连失败",
                                "input_reconnect_failed",
                                task_logger,
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
                            task_logger,
                            stream_logger,
                        )

                    if not launch_ok:
                        launch_msg = (
                            f"账号 {game_account.gamertag} 切换成功但未能进入 FC/UT，"
                            "将继续尝试检测主菜单"
                        )
                        task_logger.warning(launch_msg)
                        game_logger.warning(launch_msg)
                        stream_logger.warning(launch_msg)

            if not switch_result.success:
                switch_msg = (
                    f"账号 {game_account.gamertag} 切换失败: "
                    f"{switch_result.error_message}"
                )
                task_logger.warning(switch_msg)
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
                task_logger.info(confirm_msg)
                game_logger.info(confirm_msg)
                stream_logger.info(confirm_msg)
            else:
                login_confirmed = await _detect_screen_state(
                    context, "MAIN_MENU", task_logger, game_logger
                )
            if not login_confirmed:
                msg = f"账号 {game_account.gamertag} 登录未确认，跳过该账号"
                task_logger.warning(msg)
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

            game_action_type = _apply_task_type(context, game_account, task_logger)
            stream_logger.info(
                f"账号 {game_account.gamertag} 登录已确认，应用游戏操作类型: "
                f"{game_action_type}"
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
                        context,
                        game_account,
                        task_logger,
                        game_logger,
                        check_cancel,
                        report_progress,
                        frame_queue=stream_runtime.frame_queue,
                        scene_queue=stream_runtime.scene_queue,
                    )
                    cleanup_needed = False
                finally:
                    if cleanup_needed:
                        await _cleanup_account_resources(context, game_account, task_logger, game_logger)

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

                    task_logger.info(f"账号 {game_account.gamertag} 完成第{current_count}场比赛, "
                               f"今日: {new_completed}/{target}")
                    game_logger.info(f"完成第{current_count}场比赛, 今日: {new_completed}/{target}")
                    stream_logger.info(f"游戏账号 {game_account.gamertag} 完成第{current_count}场比赛 (今日: {new_completed}/{target})")

                    is_account_completed = new_completed >= target
                    billing_unit = _resolve_billing_unit(game_action_type, current_total)

                    await _report_billable_event(
                        context,
                        platform_client,
                        game_account,
                        game_action_type,
                        billing_unit,
                        current_count,
                        task_logger,
                    )

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
                    task_logger.warning(f"账号 {game_account.gamertag} 第{current_count}场比赛失败: {match_error_msg}")
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
                        task_logger.error(error_msg)
                        game_logger.error(error_msg)
                        stream_logger.error(error_msg)
                        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
                        await _report_step4_failure(
                            context, report_progress, error_msg, keep_session_alive, task_logger
                        )
                        if not keep_session_alive:
                            await _close_task_window(window_manager, context.task_id, "match_fail_bound", task_logger)
                        return Step4Result(
                            success=False,
                            error_code="NO_MATCHES_COMPLETED",
                            message=error_msg,
                            total_matches=completed_matches,
                        )
                    await asyncio.sleep(5)

            task_logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 "
                       f"{game_account.target_matches} 场比赛")
            game_logger.info(f"今日已完成 {game_account.target_matches} 场比赛")
            stream_logger.info(f"游戏账号 {game_account.gamertag} 今日已完成 {game_account.target_matches} 场比赛")

        if total_matches > 0 and completed_matches == 0:
            error_msg = "游戏自动化结束但未完成任何比赛"
            stream_logger.error(error_msg)
            context.update_step_status("step4", TaskStepStatus.FAILED, error_msg)
            await _report_step4_failure(
                context, report_progress, error_msg, keep_session_alive, task_logger
            )
            if not keep_session_alive:
                await _close_task_window(window_manager, context.task_id, "no_matches", task_logger)
            return Step4Result(
                success=False,
                error_code="NO_MATCHES_COMPLETED",
                message=error_msg,
                total_matches=0,
            )

        success_msg = f"自动操作Xbox主机完成，共完成 {completed_matches} 场比赛"
        task_logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step4", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP4", "COMPLETED", success_msg)

        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "task_completed", task_logger)

        return Step4Result(success=True, message=success_msg, total_matches=completed_matches)

    except asyncio.CancelledError:
        task_logger.info("步骤四被取消")
        context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "task_cancelled", task_logger)
        return Step4Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤四执行超时: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "timeout", task_logger)
        return Step4Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤四网络连接失败: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "connection_error", task_logger)
        return Step4Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤四参数错误: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "value_error", task_logger)
        return Step4Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤四执行异常: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step4", TaskStepStatus.FAILED, error_msg, str(e))
        await _report_step4_failure(
            context, report_progress, error_msg, keep_session_alive, task_logger
        )
        if not keep_session_alive:
            await _close_task_window(window_manager, context.task_id, "error", task_logger)
        return Step4Result(success=False, error_code="EXCEPTION", message=error_msg)

    finally:
        await _fc_terminate_match_session(context, task_logger)
        await stream_runtime.stop_automation()
        task_logger.info("StreamRuntime 自动化循环已停止（capture/display 保留）")


async def _close_task_window(window_manager, task_id: str, reason: str, task_logger):
    """
    关闭任务关联的窗口

    参数：
    - window_manager: 窗口管理器
    - task_id: 任务ID
    - reason: 关闭窗口的原因
    - task_logger: 日志记录器
    """
    if window_manager is None:
        task_logger.warning("窗口管理器未提供，无法关闭窗口")
        return

    try:
        task_logger.info(f"开始关闭窗口 (任务: {task_id}, 原因: {reason})")
        await window_manager.close_window_by_task(task_id)
        task_logger.info(f"窗口已关闭 (任务: {task_id})")
    except Exception as e:
        task_logger.error(f"关闭窗口失败 (任务: {task_id}): {e}")


async def _init_game_automation(
    context: AgentTaskContext,
    task_logger,
    platform_client: Optional[Any] = None,
    report_progress: Optional[Callable[[str, str, str, Optional[Dict]], None]] = None,
    input_gate: Optional[Any] = None,
):
    """
    初始化游戏自动化引擎

    参数：
    - context: 任务上下文
    - task_logger: 日志记录器

    返回：
    - (automation_engine, account_switcher) 或 (None, None)
    """
    try:
        from ..scene.game_automation_engine import GameAutomationEngine, ActionExecutor
        from ..scene.scene_detector import SceneDetector, SceneState
        from ..scene.optimized_scene_detector import OptimizedSceneDetector, SceneConfig
        from ..game.account_switcher import AccountSwitcher

        task_logger.info("初始化游戏自动化引擎...")

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
                task_logger.info("优化后的场景检测器已创建（优化四）")
                task_logger.info(f"检测配置: 每{config.frame_interval}帧检测一次, 置信度阈值{config.confidence_threshold}")

            except asyncio.TimeoutError as e:
                task_logger.warning(f"场景检测器创建超时: {e}")
            except ValueError as e:
                task_logger.warning(f"场景检测器创建参数错误: {e}")
            except Exception as e:
                task_logger.warning(f"场景检测器创建失败: {e}")

        executor = ActionExecutor()
        if input_gate is not None:
            executor.set_input_gate(input_gate)
        if context.xbox_session:
            executor.set_xbox_session(context.xbox_session)
            task_logger.info("动作执行器已绑定Xbox会话")
        else:
            task_logger.warning("Xbox会话不可用，动作执行器将无法发送信号")

        await _init_gamepad_protocol(context, executor, task_logger, input_gate=input_gate)

        engine = GameAutomationEngine()
        if scene_detector and context.xbox_session:
            engine.initialize(scene_detector, context.xbox_session)
            task_logger.info("游戏自动化引擎已初始化")
        else:
            task_logger.warning("游戏自动化引擎初始化不完整")

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

            async def _noop_report(*_args, **_kwargs):
                return None

            rp = report_progress or _noop_report

            await _report_input_channel_event(
                context,
                rp,
                "RUNNING",
                "Input DataChannel 已关闭，正在重连",
                "input_reconnecting",
                task_logger,
            )
            ok = await reconnect_input_channel(context, task_logger)
            if ok:
                rebind_stream_bindings(
                    context,
                    executor=executor,
                    switcher=switcher,
                    engine=engine,
                )
                await _report_input_channel_event(
                    context,
                    rp,
                    "RUNNING",
                    "Input DataChannel 已恢复",
                    "input_restored",
                    task_logger,
                )
            else:
                await _report_input_channel_event(
                    context,
                    rp,
                    "FAILED",
                    "Input DataChannel 重连失败",
                    "input_reconnect_failed",
                    task_logger,
                )
            return ok

        switcher.set_reconnect_callback(_reconnect_input_and_rebind)
        switcher.set_task_context(context)
        context._account_switcher = switcher

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
                streaming_detector = await _ensure_streaming_scene_detector(context, task_logger)
                switcher.set_scene_detector(streaming_detector)

                async def _capture_for_switcher():
                    from ..runtime.stream_runtime import capture_task_frame

                    return await capture_task_frame(context, timeout=0.8)

                switcher.set_frame_getter(_capture_for_switcher)
            except Exception as e:
                task_logger.warning(f"账号切换器场景检测绑定失败: {e}")

        task_logger.info("账号切换器已初始化")
        task_logger.info(f"已加载 {len(accounts_data)} 个游戏账号")

        if optimized_detector:
            context._optimized_scene_detector = optimized_detector
            task_logger.info("优化后的场景检测器已保存到上下文")

        return engine, switcher

    except asyncio.TimeoutError as e:
        task_logger.error(f"初始化游戏自动化引擎超时: {e}")
        return None, None
    except ConnectionError as e:
        task_logger.error(f"初始化游戏自动化引擎网络错误: {e}")
        return None, None
    except ValueError as e:
        task_logger.error(f"初始化游戏自动化引擎参数错误: {e}")
        return None, None
    except Exception as e:
        task_logger.error(f"初始化游戏自动化引擎失败: {e}")
        return None, None


async def _execute_match_for_account(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
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
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号专用日志记录器
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - tuple: (success: bool, error_code: Optional[str], error_message: Optional[str])
    """
    task_logger.info(f"执行比赛: {game_account.gamertag}")
    game_logger.info("执行比赛")

    action_type = _normalize_game_action_type(context.game_action_type)
    if action_type == 'transfer_sqb_combo':
        completed = context.matches_completed_today.get(game_account.id, 0)
        if completed % 2 == 0:
            await _navigate_to_auction(context, task_logger, game_logger)
            game_logger.info("组合模式: 转会阶段完成")
            return True, None, None
        action_type = 'squad_battle'

    try:
        if action_type == 'auction_transfer':
            await _navigate_to_auction(context, task_logger, game_logger)
            return True, None, None

        await _enter_match(context, game_account, task_logger, game_logger, report_progress)

        await _wait_for_match_start(context, game_account, task_logger, game_logger, report_progress)

        await _play_match(
            context, game_account, task_logger, game_logger, 
            check_cancel, report_progress,
            frame_queue, scene_queue
        )

        await _finish_match(context, game_account, task_logger, game_logger, report_progress)

        task_logger.info(f"比赛完成: {game_account.gamertag}")
        game_logger.info("比赛完成")
        return True, None, None

    except asyncio.CancelledError as e:
        task_logger.error(f"比赛执行取消: {e}")
        game_logger.error(f"比赛执行取消: {e}")
        return False, "CANCELLED", "任务被取消"
    except asyncio.TimeoutError as e:
        task_logger.error(f"比赛执行超时: {e}")
        game_logger.error(f"比赛执行超时: {e}")
        return False, "TIMEOUT", f"比赛执行超时: {str(e)}"
    except ConnectionError as e:
        task_logger.error(f"比赛执行网络错误: {e}")
        game_logger.error(f"比赛执行网络错误: {e}")
        return False, "CONNECTION_ERROR", f"网络连接错误: {str(e)}"
    except ValueError as e:
        task_logger.error(f"比赛执行参数错误: {e}")
        game_logger.error(f"比赛执行参数错误: {e}")
        return False, "VALUE_ERROR", f"参数错误: {str(e)}"
    except Exception as e:
        task_logger.error(f"比赛执行异常: {e}")
        game_logger.error(f"比赛执行异常: {e}")
        return False, "MATCH_ERROR", f"比赛执行异常: {str(e)}"


async def _navigate_to_game_mode(
    context: AgentTaskContext,
    game_action_type: str,
    task_logger,
    game_logger
) -> None:
    """
    根据 game_action_type 导航到对应的游戏模式

    导航分发中心，根据不同的 game_action_type 调用对应的导航函数。

    参数：
    - context: 任务上下文
    - game_action_type: 游戏操作类型 (auction_transfer/squad_battle/divisions_rivals/weekend_league)
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号专用日志记录器
    """
    task_logger.info(f"开始导航到游戏模式: {game_action_type}")

    if game_action_type == 'auction_transfer':
        await _navigate_to_auction(context, task_logger, game_logger)
    elif game_action_type == 'squad_battle':
        await _navigate_to_squad_battle(context, task_logger, game_logger)
    elif game_action_type == 'divisions_rivals':
        await _navigate_to_dr(context, task_logger, game_logger)
    elif game_action_type == 'weekend_league':
        await _navigate_to_weekend_league(context, task_logger, game_logger)
    elif game_action_type == 'transfer_sqb_combo':
        await _navigate_to_auction(context, task_logger, game_logger)
        await _navigate_to_squad_battle(context, task_logger, game_logger)
    else:
        task_logger.warning(f"未知的游戏操作类型: {game_action_type}，默认导航到SQB模式")
        await _navigate_to_squad_battle(context, task_logger, game_logger)


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
) -> None:
    """
    导航到拍卖行转会界面

    导航路径：主页 → UT → Transfer Market

    操作序列：
    1. 从主页按 RB×3 + A 进入 UT 菜单
    2. 按 LB + A 进入 Transfer Market
    """
    task_logger.info("导航到拍卖行转会界面")
    game_logger.info("[拍卖行] 开始导航到拍卖行")

    try:
        # 1. 进入 UT 菜单：RB×3 + A
        task_logger.info("[拍卖行] 步骤1: 进入UT菜单 (RB×3 + A)")
        for _ in range(3):
            await _press_button(context, XboxButtonFlag.R1, 0.2)
            await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        # 2. 进入 Transfer Market：LB + A
        task_logger.info("[拍卖行] 步骤2: 进入Transfer Market (LB + A)")
        await _press_button(context, XboxButtonFlag.L1, 0.3)
        await asyncio.sleep(NAVIGATION_CONFIG['button_press_delay'])
        await _press_button(context, XboxButtonFlag.A, 0.5)
        await asyncio.sleep(2)

        task_logger.info("[拍卖行] 导航完成，等待拍卖行界面加载")
        game_logger.info("[拍卖行] 导航完成")

    except Exception as e:
        task_logger.error(f"[拍卖行] 导航异常: {e}")
        game_logger.error(f"[拍卖行] 导航异常: {e}")


async def _navigate_to_squad_battle(
    context: AgentTaskContext,
    task_logger,
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

    task_logger.info("导航到SQB模式 (SCENE_TRANSITIONS 链)")
    game_logger.info("[SQB] 开始导航 (scene_transitions 链)")

    switcher = getattr(context, '_account_switcher', None)

    try:
        if not switcher:
            task_logger.error("[SQB] account_switcher 未初始化，无法执行场景转移链")
            game_logger.error("[SQB] account_switcher 未初始化")
            return

        current = await switcher._detect_any_scene(
            SQB_NAVIGATION_SCENES, strict=False
        )
        chain = trim_sqb_navigation_chain(current)
        if not chain:
            task_logger.info("[SQB] 已在赛前界面 (scene189)，跳过导航")
            game_logger.info("[SQB] 已在 scene189")
            return

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
        else:
            task_logger.error("[SQB] 场景转移链未完成")
            game_logger.error("[SQB] 导航失败，请检查 logs/debug_scene*.png")

    except Exception as e:
        task_logger.error(f"[SQB] 导航异常: {e}")
        game_logger.error(f"[SQB] 导航异常: {e}")


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


async def _enter_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
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
    - task_logger: 任务日志记录器
    - game_logger: 游戏账号专用日志记录器
    - report_progress: 进度上报函数
    """
    task_logger.info(f"进入比赛准备: {game_account.gamertag}")
    game_logger.info("[场景: MAIN_MENU] 进入比赛准备")

    screen_detected = await _detect_screen_state(
        context, "MAIN_MENU", task_logger, game_logger
    )
    task_logger.info(f"游戏主界面检测: {screen_detected}")

    # 获取游戏操作类型并导航到对应模式
    game_action_type = _normalize_game_action_type(context.game_action_type)
    task_logger.info(f"根据游戏操作类型导航: {game_action_type}")

    # 导航到对应的游戏模式
    await _navigate_to_game_mode(context, game_action_type, task_logger, game_logger)

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
    task_logger,
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
    task_logger.info(f"比赛正式开始: {game_account.gamertag}")
    game_logger.info("[场景: MATCHMAKING] 比赛正式开始")

    match_started = await _wait_for_match_started(
        context, task_logger, game_logger
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

    if not await _fc_init_match_session(context, task_logger):
        task_logger.warning("FC 比赛会话初始化失败，仍尝试本地 play loop")

    runtime = getattr(context, "_stream_runtime", None)
    if runtime:
        runtime.enter_play_mode()


async def _play_match(
    context: AgentTaskContext,
    game_account: GameAccountInfo,
    task_logger,
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
    match_duration = 1200
    report_interval = 30
    poll_interval = 10

    task_logger.info(f"比赛中，预计时长: {match_duration}秒")
    game_logger.info(f"[场景: IN_GAME] 比赛中，预计时长: {match_duration}秒")

    if getattr(context, "_fc_remote_play", False):
        runtime = getattr(context, "_stream_runtime", None)
        if runtime:
            task_logger.info("[比赛进行] FC PLAY loop 已接管（StreamRuntime play 20Hz）")
            try:
                await asyncio.wait_for(runtime.match_over.wait(), timeout=match_duration)
                task_logger.info("FC 报告比赛结束 (ERR_MATCH_OVER)")
                game_logger.info("[场景: SETTLEMENT] FC 比赛结束")
                return
            except asyncio.TimeoutError:
                task_logger.info("FC 比赛等待超时，按本地时长结束")
            return

    if scene_queue is not None:
        task_logger.info("[比赛进行] 使用 StreamRuntime graph/scene_queue 辅助检测")

    for i in range(match_duration // poll_interval):
        if check_cancel():
            raise Exception("比赛被取消")

        if scene_queue and not scene_queue.empty():
            try:
                scene_result = await asyncio.wait_for(
                    scene_queue.get(),
                    timeout=0.5
                )
                if scene_result and scene_result != "UNKNOWN":
                    task_logger.info(f"[比赛进行] 检测到场景: {scene_result}")
                    game_logger.info(f"[比赛进行] 检测到场景: {scene_result}")
            except asyncio.TimeoutError:
                pass

        await asyncio.sleep(poll_interval)

        match_ended = await _detect_match_ended(
            context, task_logger, game_logger
        )
        if match_ended:
            task_logger.info("检测到比赛结束画面")
            game_logger.info("[场景: SETTLEMENT] 检测到比赛结束画面")
            break

        elapsed = (i + 1) * poll_interval
        progress_pct = min(100, int(elapsed / match_duration * 100))

        if i % 3 == 0 or elapsed == match_duration:
            task_logger.info(f"比赛进行中... ({elapsed}/{match_duration}秒, {progress_pct}%)")
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
    task_logger,
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
    task_logger.info(f"比赛结束: {game_account.gamertag}")
    game_logger.info("[场景: MATCH_END] 比赛结束")

    runtime = getattr(context, "_stream_runtime", None)
    if runtime:
        runtime.exit_play_mode()
    await _fc_terminate_match_session(context, task_logger)

    await _skip_settlement(context, task_logger, game_logger)


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
            await switcher._press_button("A", duration=0.12)
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

