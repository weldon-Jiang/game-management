"""检测本机 Agent (main.py) 进程数量，避免多实例抢 WebSocket。"""

from __future__ import annotations

import subprocess
import sys
from typing import List, Tuple


def list_main_py_processes() -> List[Tuple[int, str]]:
    """返回 (pid, commandline) 列表；仅 Windows。"""
    if sys.platform != "win32":
        return []
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                "Where-Object { $_.CommandLine -like '*main.py*' } | "
                "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    rows: List[Tuple[int, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        try:
            rows.append((int(parts[0]), parts[1]))
        except ValueError:
            continue
    return rows


def count_agent_processes() -> int:
    return len(list_main_py_processes())


def require_single_agent(*, for_automation: bool = False) -> None:
    """
    自动化脚本前置检查：必须已有且仅有 1 个 Agent 进程。

    for_automation=True 时若未运行则直接报错（不启动 main.py）。
    """
    procs = list_main_py_processes()
    n = len(procs)
    if n == 0:
        if for_automation:
            raise RuntimeError(
                "未检测到 Agent 进程。请先单独启动串流：\n"
                "  cd bend-agent/src && python main.py\n"
                "或: python tools/run_streaming_task.py --start-agent"
            )
        return
    if n > 1:
        pids = ", ".join(str(p[0]) for p in procs)
        raise RuntimeError(
            f"检测到 {n} 个 Agent 进程 (PID: {pids})，会导致 WebSocket 互踢。"
            "请只保留一个 main.py 后再跑自动化脚本。"
        )
