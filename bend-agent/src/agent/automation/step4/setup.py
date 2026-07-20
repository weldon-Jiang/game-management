"""
Step4 模板校验与 FC 控制器初始化
=============================
从原 step4_game_automation.py 提取。职责:
- 模板目录解析 / 预检
- StreamingSceneDetector 创建/复用
- FC 控制器动作应用 / 场景客户端
- FC 比赛会话管理 (init/terminate)
- 期望画面匹配
"""
import asyncio
from typing import Optional, Dict

from ..task.task_context import AgentTaskContext
from .constants import EXPECTED_SCREEN_SCENES

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


# 2️⃣ 任务类型路由与计费 → step4/task_routing.py
from .step4.task_routing import (
    _normalize_game_action_type,
    _apply_task_type,
    _requires_transfer_phase,
    _requires_sqb_phase,
    _transfer_rounds_target,
    _account_exit_fc_reason,
    _account_needs_transfer_phase,
    _resolve_billing_unit,
    _report_billable_event,
)

