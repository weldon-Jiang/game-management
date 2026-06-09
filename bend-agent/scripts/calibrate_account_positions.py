#!/usr/bin/env python3
"""
校准 Xbox「您是谁」列表位置与平台 gameName 的对应关系。

用法（需先能 Step1-3 串流）：
    set PYTHONPATH=src
    python scripts/calibrate_account_positions.py --streaming-id <id> --slots 5

流程：进入场景6 → 从顶部起逐格 DOWN → 每格保存截图到 logs/account_slots/
对照截图核对 gamertag 与 gameName 是否一致；切换时 Agent 会 OCR 自动定位，无需手填 position_index。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

from agent.core.encoding_bootstrap import ensure_utf8_stdio

ensure_utf8_stdio()

OUTPUT_DIR = ROOT / "logs" / "account_slots"


async def _run(streaming_id: str, slots: int, max_step: int) -> int:
    from agent.core.config import load_config

    sys.path.insert(0, str(ROOT / "scripts"))
    from run_live_task import _build_params_from_streaming_id, _run_steps_direct, _safe_decrypt_password

    load_config(str(ROOT / "configs" / "agent.yaml"))
    params = _build_params_from_streaming_id(streaming_id)

    print("Running Step1-3 for stream session...")
    result = await _run_steps_direct(params, max_step=min(max_step, 3), check_cancel=lambda: False)
    if not result.get("success") and max_step >= 3:
        print(f"Step1-3 may have issues: {result}")
        return 1

    from agent.automation.step4_game_automation import _init_game_automation
    from agent.task.task_context import AgentTaskContext, TaskStepStatus

    streaming = params["streamingAccount"]
    context = AgentTaskContext(
        task_id=params["taskId"],
        streaming_account_id=streaming["id"],
        streaming_account_email=streaming["email"],
        streaming_account_password=_safe_decrypt_password(streaming.get("passwordToken", "")),
        streaming_account_auto_code=streaming.get("authCode", ""),
        game_accounts=[],
        game_action_type=params.get("gameActionType", "squad_battle"),
    )
    context.update_step_status("step3", TaskStepStatus.COMPLETED, "calibration")

    from agent.automation.step3_streaming_init import step3_streaming_init
    from agent.automation.step2_router import step2_execute_streaming
    from agent.automation.step1_stream_account_login import step1_execute_login

    async def noop_progress(*_a, **_k):
        pass

    if context.frame_capture is None:
        for fn in (step1_execute_login, step2_execute_streaming, step3_streaming_init):
            r = await fn(context, lambda: False, noop_progress)
            if not r.success:
                print(f"Setup failed at {fn.__name__}: {r.message}")
                return 1

    from agent.core.logger import get_logger
    logger = get_logger("calibrate_positions")
    engine, switcher = await _init_game_automation(context, logger)
    if not switcher:
        print("AccountSwitcher init failed")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Navigating to scene 6, capturing {slots} slots -> {OUTPUT_DIR}")

    await switcher._press_guide_button()
    await switcher._wait_for_scene(2, timeout=8.0)
    await switcher._navigate_to_accounts_system()
    if not await switcher._wait_for_scene(3):
        print("Failed to reach scene 3")
        return 1
    await switcher._select_add_switch()
    if not await switcher._wait_for_scene(5):
        print("Failed to reach scene 5")
        return 1
    await switcher._enter_account_selection()
    if not await switcher._wait_for_scene(6):
        print("Failed to reach scene 6")
        return 1

    import cv2

    for i in range(slots):
        frame = await context.frame_capture.capture_frame()
        if frame is not None:
            image = frame.data if hasattr(frame, "data") else frame
            path = OUTPUT_DIR / f"slot_{i:02d}.png"
            cv2.imwrite(str(path), image)
            print(f"  slot {i}: saved {path.name}")
        if i < slots - 1:
            await switcher._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.5)

    print("\n对照截图核对 gamertag 是否与平台 gameName 一致（Agent 切换时 OCR 自动定位）")
    for ga in params.get("gameAccounts", []):
        print(f"  - {ga.get('gameName')} (id={ga.get('id')})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate Xbox account list positions")
    parser.add_argument("--streaming-id", required=True)
    parser.add_argument("--slots", type=int, default=5, help="Max profiles to capture")
    parser.add_argument("--max-step", type=int, default=3)
    args = parser.parse_args()
    return asyncio.run(_run(args.streaming_id, args.slots, args.max_step))


if __name__ == "__main__":
    raise SystemExit(main())
