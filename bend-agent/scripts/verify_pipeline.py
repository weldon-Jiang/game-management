#!/usr/bin/env python3
"""
Verify Step1-Step4 pipeline wiring (static + mock context propagation).

Usage:
    set PYTHONPATH=src
    python scripts/verify_pipeline.py
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core.encoding_bootstrap import ensure_utf8_stdio

ensure_utf8_stdio()


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def _check_imports() -> List[CheckResult]:
    results: List[CheckResult] = []
    modules = [
        ("agent.task.automation_task", "AgentAutomationTask"),
        ("agent.automation.step1_stream_account_login", "step1_execute_login"),
        ("agent.automation.step2_xbox_streaming", "step2_execute_streaming"),
        ("agent.automation.step3_streaming_init", "step3_streaming_init"),
        ("agent.automation.step4_game_automation", "step4_execute_gaming"),
        ("agent.xbox.cloud_stream_session", "CloudStreamSession"),
        ("agent.vision.webrtc_frame_controller", "WebRTCFrameController"),
        ("agent.scene.streaming_scene_detector", "StreamingSceneDetector"),
        ("agent.scene.fc_scene_client", "FCSceneClient"),
    ]
    for mod_name, symbol in modules:
        try:
            mod = __import__(mod_name, fromlist=[symbol])
            getattr(mod, symbol)
            results.append(CheckResult(f"import {symbol}", True))
        except Exception as exc:
            results.append(CheckResult(f"import {symbol}", False, str(exc)))
    return results


def _check_automation_task_wiring() -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        from agent.task import automation_task as at

        src = inspect.getsource(at.AgentAutomationTask.execute)
        for token in (
            "step1_execute_login",
            "step2_execute_streaming",
            "step3_streaming_init",
            "step4_execute_gaming",
        ):
            ok = token in src
            results.append(CheckResult(f"automation_task calls {token}", ok))
    except Exception as exc:
        results.append(CheckResult("automation_task wiring", False, str(exc)))
    return results


def _check_step2_cloud_hooks() -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        from agent.automation import step2_xbox_streaming as s2

        src = inspect.getsource(s2._connect_to_xbox)
        for token in (
            "_exchange_sdp",
            "_establish_cloud_media_session",
            "_start_cloud_video_receiver",
            "context.xbox_session",
        ):
            results.append(CheckResult(f"step2 _connect_to_xbox has {token}", token in src))

        for fn_name in ("_establish_cloud_media_session", "_start_cloud_video_receiver"):
            fn = getattr(s2, fn_name, None)
            results.append(CheckResult(f"step2 defines {fn_name}", callable(fn)))
    except Exception as exc:
        results.append(CheckResult("step2 cloud hooks", False, str(exc)))
    return results


def _check_step3_step4_deps() -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        from agent.automation import step3_streaming_init as s3
        from agent.automation import step4_game_automation as s4

        s3_src = inspect.getsource(s3.step3_streaming_init)
        results.append(CheckResult("step3 sets context.frame_capture", "context.frame_capture = capture" in s3_src))
        results.append(CheckResult("step3 binds xbox_session gamepad", "context.xbox_session" in s3_src))
        results.append(CheckResult("step3 webrtc controller hook", "set_webrtc_controller" in inspect.getsource(s3._init_frame_capture)))

        s4_src = inspect.getsource(s4.step4_execute_gaming)
        results.append(CheckResult("step4 requires frame_capture", "context.frame_capture is None" in s4_src))
        results.append(CheckResult("step4 uses xbox_session", "context.xbox_session" in s4_src))
    except Exception as exc:
        results.append(CheckResult("step3/4 deps", False, str(exc)))
    return results


def _check_templates() -> List[CheckResult]:
    results: List[CheckResult] = []
    template_dir = ROOT / "templates"
    png_count = len(list(template_dir.glob("*.png")))
    ok = png_count >= 200
    results.append(CheckResult(
        "template png assets",
        ok,
        f"{png_count} files in {template_dir}" if ok else f"only {png_count} png (run tools/sync_scene_schemas.py)",
    ))
    schema_file = ROOT / "configs" / "scene_schemas.py"
    if schema_file.exists():
        rows = schema_file.read_text(encoding="utf-8").count("\n    [")
        results.append(CheckResult("scene_schemas rows", rows >= 200, f"{rows} schema rows"))
    else:
        results.append(CheckResult("scene_schemas rows", False, "missing scene_schemas.py"))
    return results


def _check_context_field_map() -> List[CheckResult]:
    """Document expected context handoff between steps."""
    mapping = {
        "step1 -> step2": ["microsoft_tokens", "xbox_tokens"],
        "step2 -> step3": [
            "current_xbox",
            "xbox_session",
            "_cloud_stream_session",
            "_webrtc_frame_controller",
            "_video_capture_mode",
            "_webrtc_handler",
        ],
        "step3 -> step4": [
            "frame_capture",
            "xbox_session",
            "_controller_protocol",
            "_gamepad_controller",
            "_streaming_scene_detector",
        ],
    }
    results: List[CheckResult] = []
    from agent.task.task_context import AgentTaskContext

    ctx_fields = set(AgentTaskContext.__dataclass_fields__.keys())
    for edge, fields in mapping.items():
        for f in fields:
            if f.startswith("_"):
                results.append(CheckResult(f"{edge}: dynamic attr {f}", True, "runtime attribute"))
            else:
                ok = f in ctx_fields
                results.append(CheckResult(f"{edge}: {f}", ok, "declared on AgentTaskContext" if ok else "missing"))
    return results


async def _mock_context_propagation() -> CheckResult:
    """
    Simulate post-step2 context and verify step3/step4 preconditions can be satisfied.
    """
    try:
        import numpy as np
        from agent.task.task_context import AgentTaskContext, GameAccountInfo
        from agent.vision.frame_capture import VideoFrameCapture, Frame
        from agent.vision.webrtc_frame_controller import WebRTCFrameController
        from agent.xbox.cloud_stream_session import CloudStreamSession, AIORTC_AVAILABLE

        class _FakeWindow:
            hwnd = None

        class _FakeCloudSession:
            is_connected = True

            async def start_video_receiver(self, **kwargs):
                return True

            async def send_gamepad_state(self, data):
                return True

            async def get_frame(self, timeout=1.0):
                return np.zeros((540, 960, 3), dtype=np.uint8)

            async def disconnect(self):
                return None

            @property
            def video_mode(self):
                return "webrtc"

        context = AgentTaskContext(
            task_id="verify-pipeline-001",
            streaming_account_id="sa-1",
            streaming_account_email="verify@test.local",
            streaming_account_password="",
            streaming_account_encrypted_password="",
            game_accounts=[GameAccountInfo(id="g1", gamertag="TestGamer")],
        )

        # Simulate step1 output
        context.microsoft_tokens = object()
        context.xbox_tokens = type("T", (), {"gs_token": "fake-gs-token"})()

        # Simulate step2 output
        fake_session = _FakeCloudSession()
        context.xbox_session = fake_session
        context._cloud_stream_session = fake_session
        context._video_capture_mode = "webrtc"
        context._webrtc_frame_controller = WebRTCFrameController(fake_session)

        # Simulate step3 frame capture wiring
        capture = VideoFrameCapture(_FakeWindow())
        capture.set_webrtc_controller(context._webrtc_frame_controller)
        capture.set_capture_mode("webrtc")
        context.frame_capture = capture

        # step4 precondition
        if context.frame_capture is None:
            return CheckResult("mock context propagation", False, "frame_capture missing")

        frame = await context.frame_capture.capture_frame()
        if frame is None:
            return CheckResult("mock context propagation", False, "capture_frame returned None")

        from agent.input.controller_protocol import ControllerProtocol, ControllerSignal

        protocol = ControllerProtocol()
        protocol.set_stream_controller(context.xbox_session)
        sent = await protocol.send_signal(ControllerSignal.zero())
        if not sent:
            return CheckResult("mock context propagation", False, "controller send failed")

        from agent.scene.streaming_scene_detector import StreamingSceneDetector

        detector = StreamingSceneDetector(template_dir=str(ROOT / "templates"))
        result = detector.recognize_scene(frame.data, scene_id=1)
        # template may be missing; only verify API path works
        api_ok = hasattr(result, "matched")

        detail = (
            f"frame={frame.width}x{frame.height}, "
            f"controller_sent={sent}, "
            f"scene_api_ok={api_ok}, "
            f"aiortc_installed={AIORTC_AVAILABLE}"
        )
        return CheckResult("mock context propagation", True, detail)
    except Exception as exc:
        return CheckResult("mock context propagation", False, str(exc))


def _print_results(results: List[CheckResult]) -> Tuple[int, int]:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        line = f"[{mark}] {r.name}"
        if r.detail:
            line += f" — {r.detail}"
        print(line)
    return passed, failed


def main() -> int:
    print("=" * 60)
    print("Bend Agent Step1-Step4 Pipeline Verification")
    print("=" * 60)

    all_results: List[CheckResult] = []
    all_results.extend(_check_imports())
    all_results.extend(_check_automation_task_wiring())
    all_results.extend(_check_step2_cloud_hooks())
    all_results.extend(_check_step3_step4_deps())
    all_results.extend(_check_context_field_map())
    all_results.extend(_check_templates())

    print("\n--- Static checks ---")
    p1, f1 = _print_results(all_results)

    print("\n--- Mock context propagation ---")
    mock_result = asyncio.run(_mock_context_propagation())
    p2, f2 = (1, 0) if mock_result.passed else (0, 1)
    _print_results([mock_result])

    print("\n" + "=" * 60)
    total_pass = p1 + p2
    total_fail = f1 + f2
    print(f"Total: {total_pass} passed, {total_fail} failed")

    if total_fail == 0:
        print("Pipeline wiring: OK (code-level)")
        print("Note: Full E2E still requires real MSAL/Xbox cloud credentials and platform task dispatch.")
    else:
        print("Pipeline wiring: ISSUES FOUND")
    print("=" * 60)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
