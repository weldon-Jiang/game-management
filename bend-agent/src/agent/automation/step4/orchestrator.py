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
from typing import Callable, Any, Optional

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

# 常量提取至 step4/constants.py，保持向后兼容
from .constants import (
    VALID_TASK_TYPES,
    MATCH_END_SCENE_IDS, UT_MENU_SCENE_IDS, SETTLEMENT_SCENE_IDS,
    EXPECTED_SCREEN_SCENES,
    NAVIGATION_CONFIG,
    SQB_DIFFICULTY_MAP,
    AUCTION_CONFIG,
    DR_DIVISION_MAP,
    WEEKEND_LEAGUE_REQUIREMENTS,
)



# 1️⃣ 模板校验与 FC 控制器初始化 → step4/setup.py
from .setup import (
    _resolve_template_dir,
    _validate_step4_templates,
    _ensure_streaming_scene_detector,
    _apply_fc_controller_actions,
    _ensure_fc_scene_client,
    _fc_remote_play_enabled,
    _build_fc_play_handler,
    _fc_init_match_session,
    _fc_terminate_match_session,
    _match_expected_screen,
)

# 2️⃣ 任务类型路由与计费 → step4/task_routing.py
from .task_routing import (
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

# 3️⃣ FC 启动 / 账号切换 / 失败上报 → step4/fc_launcher.py
from .fc_launcher import (
    _pause_for_manual_fc_launch,
    _launch_fc_with_manual_pause,
    _retry_fc_launch_if_on_home,
    _report_step4_failure,
    _ensure_input_for_step4,
    _switch_to_next_game_account_on_skip,
    _report_input_channel_event,
)


# ========================================================================
# 4️⃣ 主编排器 — 自动化主入口  (→ step4/orchestrator.py 候选)
# ========================================================================

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
        from ..core.config import config as agent_config

        keyboard_mapper = getattr(context, "_keyboard_mapper", None)
        keep_keyboard = bool(agent_config.get("debug.manual_input_enabled", True))
        if keyboard_mapper and getattr(keyboard_mapper, "_running", False):
            if keep_keyboard:
                from ..debug.manual_debug_controls import attach_manual_debug_controls

                attach_manual_debug_controls(context, keyboard_mapper, task_logger)
                task_logger.info(
                    "步骤四保留键盘映射（F8 人工接管 / F9 截图 / F10 帮助）"
                )
            else:
                await keyboard_mapper.stop()
                task_logger.info("步骤四已停止键盘映射器，避免与自动化输入并发")

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

        if not hasattr(context, "_transfer_phase_done_account_ids"):
            context._transfer_phase_done_account_ids = set()

        precheck_action = _normalize_game_action_type(context.game_action_type)
        if precheck_action == 'auction_transfer':
            total_matches = sum(
                1 for ga in context.game_accounts if ga.id not in (skipped_accounts or set())
            )
        else:
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
                reconnect_callback=getattr(context, "_input_reconnect_callback", None),
                task_context=context,
            )

        from ..runtime.pause_input_control import (
            ResumeReanchor,
            account_has_remaining_work,
            checkpoint_resume_reanchor,
            raise_if_resume_reanchor,
            resume_reanchor_pending,
        )

        account_index = 0
        while account_index < len(context.game_accounts):
            restart_idx = await checkpoint_resume_reanchor(
                context, switcher, task_logger, skipped
            )
            if restart_idx is not None:
                account_index = restart_idx
                if account_index >= len(context.game_accounts):
                    break
                continue

            game_account = context.game_accounts[account_index]
            try:
                if check_cancel():
                    task_logger.info("任务被取消，步骤四终止")
                    context.update_step_status("step4", TaskStepStatus.SKIPPED, "任务被取消")
                    return Step4Result(success=False, error_code="CANCELLED",
                                     message="任务被取消")

                await context.wait_if_paused()
                raise_if_resume_reanchor(context)

                if game_account.id in skipped:
                    task_logger.info("跳过游戏账号: %s", game_account.gamertag)
                    account_index += 1
                    continue

                if account_index > 0:
                    home_scene = await switcher._detect_any_scene(
                        [203, 1, 24], strict=False
                    )
                    if home_scene not in (203, 1, 24):
                        task_logger.info(
                            "切换下一账号前未在 Xbox 主页 (scene=%s)，尝试退出 FC",
                            home_scene,
                        )
                        await switcher.exit_fc_to_xbox_home()

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
                        account_index += 1
                        continue

                current_completed = context.matches_completed_today[game_account.id]
                precheck_action = _normalize_game_action_type(context.game_action_type)

                if not account_has_remaining_work(context, game_account, skipped):
                    if precheck_action == 'auction_transfer':
                        completed_msg = (
                            f"账号 {game_account.gamertag} 本会话转会已完成，跳过"
                        )
                        progress_payload = {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "matchStatus": "COMPLETED",
                            "transferSessionDone": True,
                        }
                    else:
                        completed_msg = (
                            f"账号 {game_account.gamertag} 今日 SQB 已完成 "
                            f"{current_completed}/{game_account.target_matches} 场"
                        )
                        progress_payload = {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "todayCompleted": current_completed,
                            "dailyLimit": game_account.target_matches,
                            "matchStatus": "COMPLETED",
                        }
                    task_logger.info(completed_msg)
                    await report_progress(
                        context.task_id, "STEP4", "COMPLETED", completed_msg,
                        progress_payload,
                    )
                    await _switch_to_next_game_account_on_skip(
                        context, switcher, account_index, task_logger
                    )
                    account_index += 1
                    continue

                context.current_game_account_index = account_index
                # 供 F8 / Input 等 session 时间线事件附带当前游戏账号
                context._timeline_game_account_id = game_account.id
                context._timeline_game_account_name = game_account.gamertag

                game_logger = get_game_logger(game_account.gamertag)
                task_logger.info(f"开始处理游戏账号: {game_account.gamertag} "
                           f"({account_index+1}/{len(context.game_accounts)})")
                game_logger.info(f"=== 开始处理游戏账号 ===")

                # 流媒体账号日志：记录当前处理的游戏账号
                stream_logger.info(f"开始处理游戏账号: {game_account.gamertag} ({account_index+1}/{len(context.game_accounts)})")

                if not await _ensure_input_for_step4(context, task_logger):
                    task_logger.warning(
                        "账号 %s 跳过：input DataChannel 不可用且重连失败",
                        game_account.gamertag,
                    )
                    account_index += 1
                    continue

                launch_ok = False
                from ..core.config import config as app_config

                # Step4 账号门禁：先回 Xbox 主页，再 OCR 判断是否已是目标游戏账号
                skip_switch = bool(app_config.get("step4.skip_account_switch", False))
                if skip_switch:
                    switch_result = await switcher.prepare_without_switch(game_account.id)
                else:
                    switch_result = await switcher.ensure_target_game_account(
                        game_account.id
                    )
                if switch_result.success and not skip_switch:
                    if switch_result.skipped_switch:
                        gate_msg = (
                            f"账号门禁：主页已是目标游戏账号 {game_account.gamertag}，"
                            "跳过切档"
                        )
                    else:
                        gate_msg = (
                            f"账号门禁：已切换至目标游戏账号 {game_account.gamertag}"
                        )
                    task_logger.info(gate_msg)
                    stream_logger.info(gate_msg)
                    await report_progress(
                        context.task_id,
                        "STEP4",
                        "RUNNING",
                        gate_msg,
                        {
                            "gameAccountId": game_account.id,
                            "gameAccountName": game_account.gamertag,
                            "accountGate": "matched_skip"
                            if switch_result.skipped_switch
                            else "switched",
                        },
                    )
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
                    account_index += 1
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
                    account_index += 1
                    continue

                game_action_type = _apply_task_type(context, game_account, task_logger)
                stream_logger.info(
                    f"账号 {game_account.gamertag} 登录已确认，应用游戏操作类型: "
                    f"{game_action_type}"
                )

                await asyncio.sleep(2.0)

                if _account_needs_transfer_phase(context, game_account, game_action_type):
                    transfer_fatal, transfer_delta = await _run_transfer_phase_for_account(
                        context,
                        game_account,
                        game_action_type,
                        task_logger,
                        game_logger,
                        check_cancel,
                        report_progress,
                        platform_client,
                        target_rounds=_transfer_rounds_target(
                            game_action_type, game_account
                        ),
                    )
                    completed_matches += transfer_delta
                    if transfer_fatal is not None:
                        return transfer_fatal
                    if check_cancel():
                        return Step4Result(
                            success=False,
                            error_code="CANCELLED",
                            message="任务被取消",
                        )

                if _requires_sqb_phase(game_action_type):
                    sqb_fatal, sqb_completed_delta = await _run_sqb_phase_for_account(
                        context,
                        game_account,
                        game_action_type,
                        task_logger,
                        game_logger,
                        check_cancel,
                        report_progress,
                        platform_client,
                        stream_runtime,
                        pause_after_match,
                        keep_session_alive,
                        window_manager,
                        completed_matches,
                    )
                    completed_matches += sqb_completed_delta
                    if sqb_fatal is not None:
                        return sqb_fatal

                if _requires_sqb_phase(game_action_type):
                    final_sqb = context.matches_completed_today[game_account.id]
                    task_logger.info(
                        "游戏账号 %s 今日 SQB 已完成 %s/%s 场",
                        game_account.gamertag,
                        final_sqb,
                        game_account.target_matches,
                    )
                    game_logger.info(
                        f"今日 SQB 已完成 {final_sqb}/{game_account.target_matches} 场"
                    )
                elif game_action_type == 'auction_transfer':
                    task_logger.info(
                        "游戏账号 %s 本会话转会已完成",
                        game_account.gamertag,
                    )
                    game_logger.info("本会话转会已完成")

                exit_reason = _account_exit_fc_reason(game_action_type)
                task_logger.info(
                    "账号 %s %s，退出 FC 回 Xbox 主页",
                    game_account.gamertag,
                    exit_reason,
                )
                game_logger.info(f"[FC 退出] {exit_reason}")
                stream_logger.info(
                    f"账号 {game_account.gamertag} {exit_reason}，退出 FC"
                )
                exit_ok = await switcher.exit_fc_to_xbox_home()
                if not exit_ok:
                    task_logger.warning(
                        "账号 %s 退出 FC 回主页未确认",
                        game_account.gamertag,
                    )
                    stream_logger.warning(
                        f"账号 {game_account.gamertag} 退出 FC 回主页超时"
                    )

                remaining_accounts = [
                    ga for ga in context.game_accounts[account_index + 1:]
                    if account_has_remaining_work(context, ga, skipped)
                ]
                if remaining_accounts:
                    task_logger.info(
                        "还有 %s 个游戏账号待处理",
                        len(remaining_accounts),
                    )

                account_index += 1
            except ResumeReanchor:
                restart_idx = await checkpoint_resume_reanchor(
                    context, switcher, task_logger, skipped
                )
                if restart_idx is not None:
                    account_index = restart_idx
                    if account_index >= len(context.game_accounts):
                        break
                continue

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
        if keep_session_alive:
            from ..xbox.stream_session_survival import (
                schedule_ensure_stream_subsystems_alive,
            )

            schedule_ensure_stream_subsystems_alive(
                context, reason="step4_finally"
            )


# ========================================================================
# 5️⃣ 窗口管理与游戏自动化初始化
# ========================================================================

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
        executor.set_task_context(context)
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
                'is_new_user': bool(getattr(ga, 'is_new_user', False)),
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
            from ..xbox.stream_recovery import install_task_input_recovery

            install_task_input_recovery(
                context,
                task_logger,
                executor=executor,
                switcher=switcher,
                engine=engine,
            )

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
            base_cb = getattr(context, "_input_reconnect_base", None)
            ok = await base_cb() if base_cb else False
            if ok:
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
        context._input_reconnect_callback = _reconnect_input_and_rebind

        if platform_client and hasattr(platform_client, "update_profile_binding"):

            async def _sync_gamertag_to_platform(
                ga_id: str,
                game_name: Optional[str] = None,
            ) -> None:
                await platform_client.update_profile_binding(
                    ga_id,
                    game_name=game_name,
                )

            switcher.set_gamertag_sync_callback(_sync_gamertag_to_platform)

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


# ========================================================================

# 6️⃣ 转会阶段 → step4/transfer_phase.py
from .transfer_phase import _run_transfer_phase_for_account

# 7️⃣ SQB 阶段 → step4/sqb_phase.py
from .sqb_phase import _run_sqb_phase_for_account

# 8️⃣ 单场比赛执行
# ========================================================================

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
    task_logger.info(f"执行 SQB 比赛: {game_account.gamertag}")
    game_logger.info("执行 SQB 比赛")

    from ..runtime.pause_input_control import ResumeReanchor

    try:
        if not await _enter_match(
            context, game_account, task_logger, game_logger, report_progress
        ):
            return False, "SQB_NAV_FAILED", "SQB 场景导航失败"

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

    except ResumeReanchor:
        raise
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


# ========================================================================

# 9️⃣ 游戏模式导航 → step4/navigator.py
from .navigator import (
    _navigate_to_game_mode,
    _press_button,
    _navigate_to_auction,
    _execute_transfer_round,
    _navigate_to_squad_battle,
    _navigate_to_dr,
    _navigate_to_weekend_league,
)

# 🔟 比赛生命周期 → step4/match_lifecycle.py
from .match_lifecycle import (
    _enter_match,
    _wait_for_match_start,
    _play_match,
    _finish_match,
)

# 1️⃣1️⃣ 赛后处理与资源清理 → step4/post_match.py
from .post_match import (
    _init_gamepad_protocol,
    _detect_screen_state,
    _wait_for_match_started,
    _detect_match_ended,
    _skip_settlement,
    _cleanup_account_resources,
