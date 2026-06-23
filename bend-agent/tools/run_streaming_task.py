#!/usr/bin/env python3
"""
串流阶段（Step1–3）：可选启动 Agent + 平台 start-streaming，等到 READY。

职责：本脚本可以启动 main.py（--start-agent）；自动化验证请用 run_verify_task.py。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOG_PATH = ROOT / "logs" / "agent.log"

DEFAULT_STREAMING_ID = "93455c1eda884f63e1ecda2438911ab7"
DEFAULT_AGENT_ID = "AGENT-37EAD6AC-FB715D0B-6EB5C594"
DEFAULT_BASE = "http://localhost:8060"

sys.path.insert(0, str(ROOT / "tools"))
from agent_process import count_agent_processes, list_main_py_processes  # noqa: E402


async def login(session: aiohttp.ClientSession, base: str, login_key: str, password: str) -> str:
    async with session.post(
        f"{base.rstrip('/')}/api/auth/login",
        json={"loginKey": login_key, "password": password},
    ) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"login failed: {data}")
        return data["data"]["token"]


async def start_streaming(
    session: aiohttp.ClientSession,
    base: str,
    token: str,
    streaming_id: str,
    agent_id: str,
) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "agentId": agent_id,
        "gameAccountIds": [],
        "description": "run_streaming_task",
    }
    url = f"{base.rstrip('/')}/api/streaming-accounts/{streaming_id}/tasks/start-streaming"
    async with session.post(url, json=body, headers=headers) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"start-streaming failed: {data}")
        task_id = data["data"].get("taskId") or data["data"].get("id")
        print(f"start-streaming OK taskId={task_id}")
        return task_id


async def get_task(session: aiohttp.ClientSession, base: str, token: str, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{base.rstrip('/')}/api/tasks/{task_id}"
    async with session.get(url, headers=headers) as resp:
        data = await resp.json()
        if data.get("code") != 200:
            return {}
        return data.get("data") or {}


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


def start_agent_process() -> subprocess.Popen:
    n = count_agent_processes()
    if n > 0:
        procs = list_main_py_processes()
        print(f"Agent 已在运行 ({n} 个)，跳过启动 main.py: {[p[0] for p in procs]}")
        return None
    print(f"启动 Agent: {SRC / 'main.py'}")
    env = os.environ.copy()
    return subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(SRC),
        env=env,
    )


async def main(args: argparse.Namespace) -> int:
    proc = None
    if args.start_agent:
        proc = start_agent_process()
        if proc is not None:
            print("等待 Agent 注册 (15s)...")
            await asyncio.sleep(15)

    try:
        async with aiohttp.ClientSession() as session:
            token = await login(session, args.base, args.login_key, args.password)
            print(f"login OK ({args.login_key})")
            task_id = await start_streaming(
                session, args.base, token, args.streaming_id, args.agent_id
            )
            print(f"waiting READY (max {args.timeout}s)...")
            ok = await wait_ready(session, args.base, token, task_id, args.timeout)
            if not ok:
                print("READY 超时，请查 logs/agent.log")
                return 1
            print(f"\n串流就绪。下一步（勿再启动 main.py）：")
            print(f"  python tools/run_verify_task.py --task-id {task_id}")
            return 0
    finally:
        # 串流脚本启动的 Agent 保持运行，不随脚本退出而 kill
        if proc is not None and proc.poll() is not None:
            print(f"警告: Agent 进程已退出 code={proc.returncode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="串流 Step1-3（可启动 main.py）")
    parser.add_argument("--start-agent", action="store_true", help="若尚无 Agent 则启动 main.py")
    parser.add_argument("--login-key", default="weldon")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--streaming-id", default=DEFAULT_STREAMING_ID)
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--timeout", type=float, default=600.0)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
