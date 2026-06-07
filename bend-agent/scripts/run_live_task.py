#!/usr/bin/env python3
"""
Real-task integration helper for Bend Agent.

Preflight checks (templates, deps, platform, credentials) and optional
local execution of stream_control without going through WebSocket.

Usage:
    set PYTHONPATH=src
    python scripts/run_live_task.py --preflight
    python scripts/run_live_task.py --task-id <taskId>
    python scripts/run_live_task.py --streaming-id <id>          # default: StreamingAccountTask
    python scripts/run_live_task.py --streaming-id <id> --legacy-steps --max-step 2
    python scripts/run_live_task.py --email jwdong1991@outlook.com --max-step 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core.encoding_bootstrap import ensure_utf8_stdio

ensure_utf8_stdio()

CREDENTIALS_DIR = ROOT / "credentials"
CREDENTIALS_FILE = CREDENTIALS_DIR / "agent_credentials.json"
TEMPLATE_DIR = ROOT / "templates"
SCHEMA_FILE = ROOT / "configs" / "scene_schemas.py"


def _ensure_credentials() -> Tuple[Optional[str], Optional[str]]:
    agent_id = os.environ.get("BEND_AGENT_ID")
    agent_secret = os.environ.get("BEND_AGENT_SECRET")
    if agent_id and agent_secret:
        return agent_id, agent_secret

    if CREDENTIALS_FILE.exists():
        data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
        return data.get("agentId"), data.get("agentSecret")

    return None, None


def _write_credentials(agent_id: str, agent_secret: str, merchant_id: str = "") -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "agentId": agent_id,
        "agentSecret": agent_secret,
        "merchantId": merchant_id,
    }
    CREDENTIALS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def _check_platform(base_url: str) -> Tuple[bool, str]:
    import aiohttp

    url = f"{base_url.rstrip('/')}/actuator/health"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    return True, f"platform OK ({url})"
                return False, f"platform HTTP {resp.status} ({url})"
    except Exception as exc:
        return False, f"platform unreachable: {exc}"


def _check_templates() -> Tuple[bool, str]:
    png_count = len(list(TEMPLATE_DIR.glob("*.png")))
    if png_count < 200:
        return False, f"templates missing or incomplete ({png_count} png, need >=200)"
    return True, f"templates OK ({png_count} png)"


def _check_schemas() -> Tuple[bool, str]:
    if not SCHEMA_FILE.exists():
        return False, "scene_schemas.py missing"
    text = SCHEMA_FILE.read_text(encoding="utf-8")
    row_count = text.count("\n    [")
    if row_count < 200:
        return False, f"scene schemas too few ({row_count})"
    return True, f"scene schemas OK ({row_count} rows)"


def _check_deps() -> Tuple[bool, str]:
    try:
        from agent.xbox.cloud_stream_session import AIORTC_AVAILABLE
    except Exception as exc:
        return False, f"cloud_stream_session import failed: {exc}"

    if not AIORTC_AVAILABLE:
        return False, "aiortc not installed"
    return True, "aiortc available"


async def run_preflight() -> int:
    from agent.core.config import load_config

    load_config(str(ROOT / "configs" / "agent.yaml"))
    base_url = os.environ.get("BEND_BACKEND_URL", "http://localhost:8060")

    checks: List[Tuple[str, bool, str]] = []
    ok, detail = _check_templates()
    checks.append(("templates", ok, detail))
    ok, detail = _check_schemas()
    checks.append(("schemas", ok, detail))
    ok, detail = _check_deps()
    checks.append(("deps", ok, detail))

    agent_id, agent_secret = _ensure_credentials()
    cred_ok = bool(agent_id and agent_secret)
    checks.append((
        "credentials",
        cred_ok,
        f"agentId={'set' if agent_id else 'missing'}, secret={'set' if agent_secret else 'missing'}",
    ))

    plat_ok, plat_detail = await _check_platform(base_url)
    checks.append(("platform", plat_ok, plat_detail))

    print("=" * 60)
    print("Bend Agent Live Task Preflight")
    print("=" * 60)
    failed = 0
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        print(f"[{mark}] {name}: {detail}")
        if not passed:
            failed += 1
    print("=" * 60)
    if failed:
        print(f"Preflight failed ({failed} checks).")
        if not cred_ok:
            print("Hint: set BEND_AGENT_ID/BEND_AGENT_SECRET or create credentials/agent_credentials.json")
        if not checks[0][1]:
            print("Hint: run `python tools/sync_scene_schemas.py` to export templates")
        return 1
    print("Preflight passed. Ready for live stream_control.")
    return 0


def _safe_decrypt_password(value: str) -> str:
    if not value or value.startswith("DISABLED:"):
        return ""
    try:
        from agent.utils.crypto_util import decrypt_password
        return decrypt_password(value) or ""
    except Exception:
        return ""


def _mysql_query(sql: str) -> List[List[str]]:
    """Run a read-only query against local docker mysql (dev integration helper)."""
    mysql_password = os.environ.get("BEND_MYSQL_ROOT_PASSWORD", "D@GAMECeKfidb")
    container = os.environ.get("BEND_MYSQL_CONTAINER", "bend-xbox-mysql")
    cmd = [
        "docker", "exec", container,
        "mysql", "-uroot", f"-p{mysql_password}", "bend_platform",
        "-N", "-B", "-e", sql,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "mysql query failed")
    rows: List[List[str]] = []
    for line in proc.stdout.splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _build_params_from_streaming_id(streaming_id: str) -> Dict[str, Any]:
    rows = _mysql_query(
        "SELECT id, email, password_encrypted, auth_code, platform "
        f"FROM streaming_account WHERE id='{streaming_id}' AND deleted=0 LIMIT 1"
    )
    if not rows:
        raise RuntimeError(f"streaming_account not found: {streaming_id}")

    account_id, email, password_encrypted, auth_code, platform = rows[0]
    game_rows = _mysql_query(
        "SELECT id, game_name, email, password_encrypted, is_primary, daily_match_limit, "
        "COALESCE(position_index, -1), COALESCE(profile_bound, 0) "
        f"FROM game_account WHERE streaming_id='{streaming_id}' AND deleted=0 "
        "ORDER BY COALESCE(position_index, 999), priority, game_name"
    )
    game_accounts = []
    for idx, row in enumerate(game_rows):
        raw_pos = int(row[6]) if len(row) > 6 and row[6] not in ("", "NULL", None) else -1
        profile_bound = len(row) > 7 and row[7] in ("1", "true", "True")
        game_accounts.append({
            "id": row[0],
            "gameName": row[1],
            "email": row[2] or "",
            "passwordToken": row[3] or "",
            "isPrimary": row[4] == "1",
            "dailyMatchLimit": int(row[5]) if row[5] else 3,
            "positionIndex": raw_pos if raw_pos >= 0 else idx,
            "profileBound": profile_bound,
        })

    return {
        "taskId": f"live-{uuid.uuid4().hex[:12]}",
        "streamingAccount": {
            "id": account_id,
            "email": email,
            "passwordToken": password_encrypted or "",
            "authCode": auth_code or "",
            "platform": platform or "xbox",
        },
        "gameAccounts": game_accounts,
        "autoMatchHost": True,
        "platform": platform or "xbox",
        "gameActionType": "squad_battle",
    }


async def _fetch_task_payload(task_id: str, agent_id: str, agent_secret: str) -> Dict[str, Any]:
    from agent.api.platform_api_client import PlatformApiClient

    client = PlatformApiClient(agent_id=agent_id, agent_secret=agent_secret)
    try:
        data = await client.get_task_info(task_id)
        if not data:
            raise RuntimeError(f"get_task_info returned empty for task {task_id}")
        return {
            "taskId": data.get("taskId", task_id),
            "streamingAccount": data.get("streamingAccount", {}),
            "gameAccounts": data.get("gameAccounts", []),
            "gameActionType": data.get("gameActionType", "squad_battle"),
            "platform": data.get("platform", "xbox"),
            "autoMatchHost": data.get("autoMatchHost", True),
            "host": data.get("host") or data.get("xboxInfo"),
        }
    finally:
        await client.close()


async def _run_steps_direct(
    params: Dict[str, Any],
    max_step: int,
    check_cancel: Callable[[], bool],
) -> Dict[str, Any]:
    from agent.task.task_context import AgentTaskContext, GameAccountInfo, XboxInfo, TaskStepStatus
    from agent.automation.step1_stream_account_login import step1_execute_login
    from agent.automation.step2_xbox_streaming import step2_execute_streaming
    from agent.automation.step3_streaming_init import step3_streaming_init
    from agent.automation.step4_game_automation import step4_execute_gaming

    streaming = params.get("streamingAccount", {})
    game_accounts_raw = params.get("gameAccounts", [])
    task_id = params.get("taskId", f"live-{uuid.uuid4().hex[:12]}")

    stream_password = _safe_decrypt_password(
        streaming.get("passwordToken", streaming.get("password", ""))
    )

    game_accounts = []
    for idx, ga in enumerate(game_accounts_raw):
        raw_pos = ga.get("positionIndex", ga.get("position_index", -1))
        position_index = raw_pos if isinstance(raw_pos, int) and raw_pos >= 0 else idx
        game_accounts.append(
            GameAccountInfo(
                id=ga.get("id", ""),
                gamertag=ga.get("gameName", ga.get("gamertag", "")),
                email=ga.get("email", ""),
                password=_safe_decrypt_password(ga.get("passwordToken", ga.get("password", ""))),
                position_index=position_index,
                is_new_user=bool(ga.get("isNewUser", ga.get("is_new_user", False))),
                profile_bound=bool(ga.get("profileBound", ga.get("profile_bound", False))),
                is_primary=ga.get("isPrimary", False),
                target_matches=ga.get("dailyMatchLimit", ga.get("targetMatches", 3)),
            )
        )

    context = AgentTaskContext(
        task_id=task_id,
        streaming_account_id=streaming.get("id", ""),
        streaming_account_email=streaming.get("email", ""),
        streaming_account_password=stream_password,
        streaming_account_auto_code=streaming.get("authCode", ""),
        game_accounts=game_accounts,
        game_action_type=params.get("gameActionType", "squad_battle"),
        account_platform=params.get("platform", streaming.get("platform", "xbox")),
        auto_match_host=params.get("autoMatchHost", True),
    )

    host = params.get("host") or params.get("xboxInfo")
    if host:
        context.assigned_xbox = XboxInfo(
            id=host.get("id", ""),
            name=host.get("name", "Xbox"),
            ip_address=host.get("ipAddress", ""),
            live_id=host.get("liveId", ""),
            mac_address=host.get("macAddress", ""),
        )

    async def report_progress(
        _task_id: str,
        step: str,
        status: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        suffix = ""
        if extra_data:
            suffix = f" {extra_data}"
        elif kwargs:
            suffix = f" {kwargs}"
        print(f"[progress] {step} {status}: {message}{suffix}")

    steps = [
        (1, "STEP1", step1_execute_login),
        (2, "STEP2", step2_execute_streaming),
        (3, "STEP3", step3_streaming_init),
        (4, "STEP4", step4_execute_gaming),
    ]

    for step_no, step_name, fn in steps:
        if step_no > max_step:
            break
        print(f"\n>>> Running {step_name} ...")
        result = await fn(context, check_cancel, report_progress)
        ok = getattr(result, "success", False)
        msg = getattr(result, "message", "")
        print(f"<<< {step_name} success={ok} message={msg}")
        if not ok:
            return {
                "success": False,
                "failedStep": step_name,
                "message": msg,
                "errorCode": getattr(result, "error_code", "STEP_FAILED"),
            }

    return {"success": True, "message": f"completed through step {max_step}"}


async def _run_via_scheduler(params: Dict[str, Any], agent_id: str, agent_secret: str) -> Dict[str, Any]:
    from agent.task.automation_scheduler import AutomationScheduler

    streaming = params.get("streamingAccount", {})
    scheduler = AutomationScheduler(agent_id=agent_id, agent_secret=agent_secret)
    task_id = params.get("taskId", "")
    host = params.get("host") or params.get("xboxInfo")

    started = await scheduler.start_task(
        task_id=task_id,
        streaming_account_id=streaming.get("id", ""),
        streaming_account_email=streaming.get("email", ""),
        streaming_account_password=streaming.get("passwordToken", streaming.get("password", "")),
        streaming_account_auto_code=streaming.get("authCode", ""),
        game_accounts=params.get("gameAccounts", []),
        assigned_xbox=host,
        game_action_type=params.get("gameActionType", "squad_battle"),
        account_platform=params.get("platform", streaming.get("platform", "xbox")),
        auto_match_host=params.get("autoMatchHost", True),
    )
    if not started:
        return {"success": False, "message": "scheduler.start_task failed"}

    timeout = 3600
    start = time.time()
    while time.time() - start < timeout:
        result = scheduler.get_task_result(task_id)
        if result is not None:
            return {
                "success": result.success,
                "message": result.message,
                "errorCode": getattr(result, "error_code", None),
                "failedStep": getattr(result, "failed_step", None),
            }
        await asyncio.sleep(1)

    await scheduler.stop_task(task_id)
    return {"success": False, "message": "task timeout"}


async def run_live_task(
    task_id: Optional[str],
    streaming_id: Optional[str],
    email: Optional[str],
    max_step: int,
    use_handler: bool,
    legacy_steps: bool,
) -> int:
    from agent.core.config import load_config

    load_config(str(ROOT / "configs" / "agent.yaml"))

    preflight_code = await run_preflight()
    if preflight_code != 0:
        return preflight_code

    agent_id, agent_secret = _ensure_credentials()
    if not agent_id or not agent_secret:
        print("Missing agent credentials.")
        return 1

    if streaming_id:
        print(f"Building payload from DB streaming_account {streaming_id} ...")
        params = _build_params_from_streaming_id(streaming_id)
    elif task_id:
        print(f"Fetching task payload for {task_id} ...")
        params = await _fetch_task_payload(task_id, agent_id, agent_secret)
    elif email:
        params = {
            "taskId": f"live-{uuid.uuid4().hex[:12]}",
            "streamingAccount": {
                "id": "",
                "email": email,
                "passwordToken": "",
                "authCode": "",
            },
            "gameAccounts": [],
            "autoMatchHost": True,
            "platform": "xbox",
        }
        print(f"Warning: --email mode without platform task; step1 needs passwordToken or cached refresh token.")
    else:
        print("Provide --task-id, --streaming-id, or --email")
        return 1

    cancelled = False

    def check_cancel() -> bool:
        return cancelled

    use_scheduler = (
        not legacy_steps
        and not use_handler
        and max_step >= 4
        and (task_id or streaming_id)
    )

    started = time.time()
    try:
        if use_handler:
            from agent.task.task_executor import handle_stream_control
            result = await handle_stream_control(params, check_cancel)
        elif use_scheduler:
            print("Using StreamingAccountTask scheduler (new orchestration path)")
            result = await _run_via_scheduler(params, agent_id, agent_secret)
        else:
            if (streaming_id or task_id) and not legacy_steps and max_step < 4:
                print(f"Using direct step runner (max-step={max_step} < 4)")
            elif legacy_steps:
                print("Using direct step runner (--legacy-steps)")
            result = await _run_steps_direct(params, max_step=max_step, check_cancel=check_cancel)
    except asyncio.CancelledError:
        print("Task cancelled")
        return 130
    except Exception as exc:
        print(f"Task failed: {exc}")
        return 1

    elapsed = time.time() - started
    print("\n" + "=" * 60)
    print(f"Live task finished in {elapsed:.1f}s")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("=" * 60)
    return 0 if result.get("success") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Bend Agent live task integration")
    parser.add_argument("--preflight", action="store_true", help="Run environment checks only")
    parser.add_argument("--task-id", help="Platform task id; fetches payload via agent callback API")
    parser.add_argument("--streaming-id", help="Local dev: build payload from docker mysql streaming_account id")
    parser.add_argument("--email", help="Streaming account email (minimal local mode)")
    parser.add_argument("--max-step", type=int, default=4, choices=[1, 2, 3, 4],
                        help="Stop after step N when using direct step runner")
    parser.add_argument("--legacy-steps", action="store_true",
                        help="Force legacy step1-4 direct runner instead of StreamingAccountTask")
    parser.add_argument("--handler", action="store_true",
                        help="Use task_executor.handle_stream_control (requires decrypted passwords)")
    parser.add_argument("--bootstrap-credentials", nargs=2, metavar=("AGENT_ID", "AGENT_SECRET"),
                        help="Write credentials/agent_credentials.json and exit")
    args = parser.parse_args()

    if args.bootstrap_credentials:
        _write_credentials(args.bootstrap_credentials[0], args.bootstrap_credentials[1])
        print(f"Wrote {CREDENTIALS_FILE}")
        return 0

    if args.preflight:
        return asyncio.run(run_preflight())

    return asyncio.run(run_live_task(
        task_id=args.task_id,
        streaming_id=args.streaming_id,
        email=args.email,
        max_step=args.max_step,
        use_handler=args.handler,
        legacy_steps=args.legacy_steps,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
