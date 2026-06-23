#!/usr/bin/env python3
"""
自动化阶段（Step4）：仅调平台 API + 读 agent.log，**不启动 main.py**。

前置：Agent 必须已由串流脚本或手动启动，且全局仅 1 个 main.py 进程。

典型用法：
  # 1) 串流（可启动 Agent）
  python tools/run_streaming_task.py --start-agent

  # 2) 自动化（不再启动 Agent）
  python tools/run_verify_task.py --task-id <taskId>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "agent.log"

DEFAULT_AGENT_ID = "AGENT-37EAD6AC-FB715D0B-6EB5C594"
DEFAULT_BASE = "http://localhost:8060"

sys.path.insert(0, str(ROOT / "tools"))
from agent_process import require_single_agent  # noqa: E402

MARKERS = [
    ("STEP4", r"STEP4|Step4|step4_execute"),
    ("账号门禁", r"账号门禁"),
    ("OCR不匹配", r"OCR 不匹配|不一致，需切换"),
    ("OCR匹配", r"OCR 匹配|跳过切档|skipped_switch"),
    ("场景3", r"场景3|档案和系统"),
    ("场景5失败", r"未进入添加和切换|场景5"),
    ("场景6", r"场景6"),
    ("FC启动", r"launch_fc|启动 FC"),
    ("失败", r"automation_failed|账号门禁失败|切换失败|unknown taskId|FAILED"),
]


async def login(session: aiohttp.ClientSession, base: str, login_key: str, password: str) -> str:
    async with session.post(
        f"{base.rstrip('/')}/api/auth/login",
        json={"loginKey": login_key, "password": password},
    ) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"login failed: {data}")
        return data["data"]["token"]


async def get_task(session: aiohttp.ClientSession, base: str, token: str, task_id: str) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base.rstrip('/')}/api/tasks/{task_id}"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            return {}
        return data.get("data") or {}


async def start_automation(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    task_id: str,
    game_action_type: str,
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    body = {"gameActionType": game_action_type}
    url = f"{base.rstrip('/')}/api/tasks/{task_id}/start-automation"
    async with session.post(url, json=body, headers=headers) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"start-automation failed: {data}")
        print(f"start-automation OK: {data.get('message')}")


def tail_log_since(since_bytes: int) -> tuple[int, str]:
    if not LOG_PATH.is_file():
        return since_bytes, ""
    size = LOG_PATH.stat().st_size
    if size <= since_bytes:
        return since_bytes, ""
    with open(LOG_PATH, "rb") as f:
        f.seek(since_bytes)
        chunk = f.read(size - since_bytes)
    return size, chunk.decode("utf-8", errors="replace")


def scan_markers(text: str) -> List[str]:
    return [label for label, pat in MARKERS if re.search(pat, text, re.IGNORECASE)]


async def wait_ready(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    task_id: str,
    timeout: float,
) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = await get_task(session, base, token, task_id)
        sp = (task.get("sessionPhase") or task.get("session_phase") or "").lower()
        status = (task.get("status") or "").lower()
        print(f"  poll status={status} sessionPhase={sp}")
        if sp == "ready" or "ready" in sp:
            return True
        if status in ("failed", "cancelled"):
            return False
        await asyncio.sleep(5)
    return False


async def main(args: argparse.Namespace) -> int:
    require_single_agent(for_automation=True)

    log_pos = LOG_PATH.stat().st_size if LOG_PATH.is_file() else 0
    seen: set[str] = set()

    async with aiohttp.ClientSession() as session:
        token = await login(session, args.base, args.login_key, args.password)
        print(f"login OK ({args.login_key}) — 本脚本不启动 main.py")

        task_id = args.task_id
        if not task_id:
            raise RuntimeError(
                "请提供 --task-id（串流 READY 后由 run_streaming_task.py 输出）"
            )

        task = await get_task(session, args.base, token, task_id)
        sp = (task.get("sessionPhase") or task.get("session_phase") or "").lower()
        if "ready" not in sp:
            print(f"当前 sessionPhase={sp}，等待 READY...")
            ok = await wait_ready(session, args.base, token, task_id, args.wait_ready_timeout)
            if not ok:
                print("READY 超时")
                return 1

        print("calling start-automation...")
        await start_automation(session, args.base, token, task_id, args.game_action_type)

        deadline = time.time() + args.timeout
        last_report = time.time()
        while time.time() < deadline:
            log_pos, chunk = tail_log_since(log_pos)
            if chunk:
                for line in chunk.splitlines():
                    try:
                        o = json.loads(line)
                        msg = o.get("message", "")
                        name = o.get("name", "")
                        if task_id[:8] in msg or name in (
                            "account_switcher", "step4", "game_automation", "task_control",
                        ):
                            print(f"[log] {o.get('asctime')} {name}: {msg[:200]}")
                    except json.JSONDecodeError:
                        pass
                for h in scan_markers(chunk):
                    if h not in seen:
                        seen.add(h)
                        print(f">>> marker: {h}")

            task = await get_task(session, args.base, token, task_id)
            sp = task.get("sessionPhase") or task.get("session_phase") or ""
            if sp.lower() in ("automation_failed", "failed", "closed"):
                print(f"task ended sessionPhase={sp}")
                break
            if time.time() - last_report > 30:
                print(f"... still running sessionPhase={sp} markers={sorted(seen)}")
                last_report = time.time()
            await asyncio.sleep(3)

    print("\n=== summary ===")
    print(f"task_id: {task_id}")
    print(f"markers: {sorted(seen)}")
    return 0 if seen and "失败" not in seen else (1 if "失败" in seen else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Step4 自动化验证（不启动 main.py，要求 Agent 已单独运行）"
    )
    parser.add_argument("--task-id", required=True, help="串流 READY 后的 taskId")
    parser.add_argument("--timeout", type=float, default=900.0, help="Step4 监控超时秒")
    parser.add_argument("--wait-ready-timeout", type=float, default=600.0)
    parser.add_argument("--game-action-type", default="squad_battle")
    parser.add_argument("--login-key", default="weldon")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--base", default=DEFAULT_BASE)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
