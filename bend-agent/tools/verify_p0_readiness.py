#!/usr/bin/env python3
"""
P0 就绪检查：模板 + 模块 + Docker 网关（可选）。

用法:
  cd bend-agent && python tools/verify_p0_readiness.py
  cd bend-agent && python tools/verify_p0_readiness.py --check-docker
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.scene_transitions import SQB_NAVIGATION_SCENES
from src.agent.game.ea_onboarding import EA_ONBOARDING_CANDIDATES
from src.agent.vision.template_manager import STEP4_REQUIRED_SCENE_IDS, validate_templates

TEMPLATE_DIR = ROOT / "templates"
OPTIONAL_MISSING = {"242.1.png", "97.2.png"}


def _check_templates() -> bool:
    ok_step4, miss_step4 = validate_templates(str(TEMPLATE_DIR), STEP4_REQUIRED_SCENE_IDS)
    ok_ea, miss_ea = validate_templates(str(TEMPLATE_DIR), EA_ONBOARDING_CANDIDATES)
    ok_sqb, miss_sqb = validate_templates(str(TEMPLATE_DIR), SQB_NAVIGATION_SCENES)

    hard_ea = [m for m in miss_ea if m not in OPTIONAL_MISSING]
    soft_ea = [m for m in miss_ea if m in OPTIONAL_MISSING]

    print("--- 模板 ---")
    print(f"  STEP4_REQUIRED: {'PASS' if ok_step4 else 'FAIL'} missing={miss_step4}")
    print(
        f"  EA_ONBOARDING:  {'PASS' if not hard_ea else 'FAIL'} "
        f"hard_missing={hard_ea} optional_missing={soft_ea}"
    )
    print(f"  SQB_NAVIGATION: {'PASS' if ok_sqb else 'FAIL'} missing={miss_sqb}")
    print(f"  templates PNG count: {len(list(TEMPLATE_DIR.glob('*.png')))}")

    return ok_step4 and not hard_ea and ok_sqb


def _check_imports() -> bool:
    print("--- 模块 ---")
    modules = [
        "src.agent.game.ea_onboarding",
        "src.agent.game.fc_on_screen_keyboard",
        "src.agent.automation.step4_game_automation",
    ]
    failed = []
    for name in modules:
        try:
            __import__(name)
            print(f"  import {name}: OK")
        except Exception as exc:
            print(f"  import {name}: FAIL ({exc})")
            failed.append(name)
    return not failed


def _check_docker(gateway_url: str) -> bool:
    print("--- Docker / Gateway ---")
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"  Docker daemon: UNAVAILABLE ({exc})")
        print("  请启动 Docker Desktop 后执行: .\\docker\\start-dev.ps1")
        return False

    print("  Docker daemon: OK")
    try:
        with urllib.request.urlopen(f"{gateway_url.rstrip('/')}/actuator/health", timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(f"  Gateway health ({gateway_url}): {resp.status} {body[:120]}")
            return resp.status == 200 and "UP" in body.upper()
    except urllib.error.URLError as exc:
        print(f"  Gateway health: FAIL ({exc})")
        print("  请先: .\\docker\\start-dev.ps1  然后重试 --check-docker")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="P0 readiness verification")
    parser.add_argument(
        "--check-docker",
        action="store_true",
        help="额外检查 Docker 与 Gateway :8060 健康",
    )
    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8060",
        help="Gateway 地址，默认 http://localhost:8060",
    )
    args = parser.parse_args()

    print("P0 readiness check (EA onboarding + SQB + Step4 templates)\n")
    tpl_ok = _check_templates()
    imp_ok = _check_imports()
    docker_ok = True
    if args.check_docker:
        docker_ok = _check_docker(args.gateway_url)

    print()
    if tpl_ok and imp_ok and docker_ok:
        print("RESULT: PASS")
        return 0
    print("RESULT: FAIL (see above)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
