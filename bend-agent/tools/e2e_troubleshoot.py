#!/usr/bin/env python3
"""
P0 E2E 排查助手：基础设施 → Agent 就绪 → 日志/调试帧分析。

用法:
  cd bend-agent && python tools/e2e_troubleshoot.py
  cd bend-agent && python tools/e2e_troubleshoot.py --analyze-logs
  cd bend-agent && python tools/e2e_troubleshoot.py --task-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOGS_DIR = ROOT / "logs"
GATEWAY_DEFAULT = "http://localhost:8060"
FRONTEND_DEFAULT = "http://localhost:3090"

# 按 E2E 阶段归类的高频错误关键词 → 排查建议
STAGE_HINTS: Dict[str, Tuple[str, str]] = {
    r"STEP1|xblive|MSAL|device.?code|登录失败": (
        "Step1 串流账号登录",
        "检查 xblive token / MSAL 设备码是否完成；见 logs/stream_log/stream_*.log",
    ),
    r"STEP2|GSSV|WebRTC|xsrp|串流连接": (
        "Step2 xsrp 串流",
        "确认 Xbox 云主机可用、GSSV 握手成功；见 task_log 中 STEP2 段落",
    ),
    r"STEP3|SDL|frame_capture|画面捕获|GPU": (
        "Step3 窗口/解码",
        "确认 SDL 窗口已创建、frame_capture 非空；Windows 需 GPU 驱动或降 CPU 解码",
    ),
    r"MISSING_TEMPLATES|模板缺失|_validate_step4": (
        "Step4 模板预检",
        "运行 python tools/verify_p0_readiness.py；缺图则 python tools/sync_scene_schemas.py",
    ),
    r"ManualInterventionRequired|人工处理|暂停": (
        "Step4 需人工介入",
        "前端任务详情点「恢复」；手动把画面调到 Xbox 主页 FC 磁贴或 UT 菜单后重试",
    ),
    r"EA 引导|ea_onboarding|scene.?230|首登": (
        "EA/FC 首登引导",
        "确认 gameAccounts[].email 已填；查 logs/debug_scene230_*.png；242 无模板时会双 A 兜底",
    ),
    r"SQB|scene189|导航失败|debug_scene": (
        "SQB 导航链",
        "查 logs/debug_scene*.png 与 game_log；确认已在 UT 主菜单 127/147/149",
    ),
    r"DataChannel|input.*不可用|_ensure_input_ready": (
        "手柄输入通道",
        "Step3 WebRTC DataChannel 未就绪；任务控制栏点「重连串流」或 WS reconnect_stream",
    ),
    r"401|403|X-Agent-Secret|注册码|register": (
        "Agent 认证/注册",
        "X-Agent-Secret 须 Base64；重新激活注册码；Gateway :8060 可达",
    ),
    r"WebSocket|ws/agent|disconnect|reconnect": (
        "Agent WS 连接",
        "确认 agent.yaml ws_url=ws://localhost:8060/ws/agent；Gateway 与 Agent 同网",
    ),
}


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str = ""
    fix: str = ""


@dataclass
class Report:
    items: List[CheckItem] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", fix: str = "") -> None:
        self.items.append(CheckItem(name, ok, detail, fix))

    @property
    def all_ok(self) -> bool:
        return all(i.ok for i in self.items)


def _http_get(url: str, timeout: float = 5.0) -> Tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(512).decode("utf-8", errors="replace")
            return resp.status == 200, f"{resp.status} {body[:200]}"
    except urllib.error.URLError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, str]:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} open"
    except OSError as exc:
        return False, str(exc)


def _docker_ok() -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=True,
        )
        return True, (r.stdout or "").splitlines()[0] if r.stdout else "OK"
    except FileNotFoundError:
        return False, "docker CLI 未安装"
    except subprocess.CalledProcessError as exc:
        msg = (exc.stderr or exc.stdout or str(exc)).strip().splitlines()
        return False, msg[-1] if msg else str(exc)
    except subprocess.TimeoutExpired:
        return False, "docker info 超时"


def _docker_ps() -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            ["docker", "compose", "-f", str(ROOT.parent / "docker" / "docker-compose.yml"), "ps", "--format", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            cwd=str(ROOT.parent / "docker"),
        )
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "compose ps failed").strip()[:300]
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        up = sum(1 for ln in lines if '"running"' in ln.lower() or '"Running"' in ln)
        return up >= 4, f"{up} 容器 running（期望 mysql/redis/backend/gateway/frontend ≥4）"
    except Exception as exc:
        return False, str(exc)


def check_infrastructure(gateway: str, frontend: str) -> Report:
    rep = Report()
    ok, detail = _docker_ok()
    rep.add(
        "Docker daemon",
        ok,
        detail,
        fix="启动 Docker Desktop，等待引擎就绪后: .\\docker\\start-dev.ps1",
    )
    if ok:
        ps_ok, ps_detail = _docker_ps()
        rep.add(
            "Compose 服务",
            ps_ok,
            ps_detail,
            fix="在项目根: .\\docker\\start-dev.ps1  然后 docker compose -f docker/docker-compose.yml ps",
        )
    gw_ok, gw_detail = _http_get(f"{gateway.rstrip('/')}/actuator/health")
    rep.add(
        "Gateway :8060",
        gw_ok and "UP" in gw_detail.upper(),
        gw_detail,
        fix="Docker 栈启动后 curl http://localhost:8060/actuator/health 应含 UP",
    )
    fe_ok, fe_detail = _http_get(frontend)
    rep.add(
        "Frontend :3090",
        fe_ok,
        fe_detail[:120],
        fix="full profile 含 frontend；浏览器打开 http://localhost:3090",
    )
    mysql_ok, mysql_detail = _tcp_open("127.0.0.1", 3307)
    rep.add(
        "MySQL :3307 (dev)",
        mysql_ok,
        mysql_detail,
        fix="data/full profile 启动 mysql；dev 映射 127.0.0.1:3307",
    )
    redis_ok, redis_detail = _tcp_open("127.0.0.1", 6380)
    rep.add(
        "Redis :6380 (dev)",
        redis_ok,
        redis_detail,
        fix="data/full profile 启动 redis；dev 映射 127.0.0.1:6380",
    )
    return rep


def check_agent_ready() -> Report:
    rep = Report()
    cfg = ROOT / "configs" / "agent.yaml"
    rep.add("agent.yaml", cfg.is_file(), str(cfg), fix="copy configs/agent.yaml.example → configs/agent.yaml")
    tpl_count = len(list((ROOT / "templates").glob("*.png")))
    rep.add(
        "templates/",
        tpl_count >= 300,
        f"{tpl_count} PNG",
        fix="cd bend-agent && python tools/sync_scene_schemas.py",
    )
    tokens = ROOT / "tokens"
    rep.add(
        "tokens/ (Agent 激活)",
        tokens.is_dir() and any(tokens.iterdir()) if tokens.is_dir() else False,
        "已激活" if tokens.is_dir() and any(tokens.iterdir()) else "未找到或未激活",
        fix="python src/main.py --code AGENT-XXXX  完成首次注册",
    )
    return rep


def _read_tail(path: Path, max_lines: int = 400) -> List[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.splitlines()
    return lines[-max_lines:]


def _scan_lines_for_stages(lines: List[str]) -> List[Tuple[str, str, str]]:
    hits: List[Tuple[str, str, str]] = []
    joined = "\n".join(lines)
    for pattern, (stage, hint) in STAGE_HINTS.items():
        if re.search(pattern, joined, re.I):
            sample = next((ln for ln in lines if re.search(pattern, ln, re.I)), "")
            hits.append((stage, hint, sample[:160]))
    return hits


def analyze_logs(task_id: Optional[str] = None) -> Report:
    rep = Report()
    if not LOGS_DIR.is_dir():
        rep.add("logs/ 目录", False, "不存在", fix="先运行 Agent 并完成至少一次任务下发")
        return rep

    rep.add("logs/ 目录", True, str(LOGS_DIR))

    agent_log = LOGS_DIR / "agent.log"
    agent_lines = _read_tail(agent_log)
    err_lines = [ln for ln in agent_lines if re.search(r"\b(ERROR|CRITICAL|FAILED|Exception)\b", ln, re.I)]
    rep.add(
        "agent.log 近期错误",
        len(err_lines) == 0,
        f"{len(err_lines)} 条" if err_lines else "无 ERROR/FAILED",
        fix="查看 logs/agent.log 最后 100 行",
    )

    task_logs = sorted((LOGS_DIR / "task_log").glob("task_*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if (LOGS_DIR / "task_log").is_dir() else []
    target: Optional[Path] = None
    if task_id:
        safe = re.sub(r"[^\w\-]", "_", task_id)[:64]
        candidate = LOGS_DIR / "task_log" / f"task_{safe}.log"
        if candidate.is_file():
            target = candidate
        else:
            rep.add(f"task_log task_{safe}.log", False, "未找到", fix="确认 taskId 或先跑任务")
    elif task_logs:
        target = task_logs[0]

    if target:
        lines = _read_tail(target, 800)
        rep.add("最新任务日志", True, target.name)
        for marker in ("STEP1", "STEP2", "STEP3", "STEP4", "EA 引导", "SQB", "FAILED", "COMPLETED"):
            found = any(marker in ln for ln in lines)
            rep.add(f"  含 [{marker}]", found, "是" if found else "否")
        stage_hits = _scan_lines_for_stages(lines)
        if stage_hits:
            rep.add("任务日志阶段提示", True, f"{len(stage_hits)} 条匹配")
            for stage, hint, sample in stage_hits[:6]:
                rep.add(f"  → {stage}", True, hint, fix=sample or hint)
    else:
        rep.add("task_log/", False, "无任务日志", fix="平台下发串流任务后会产生 logs/task_log/task_*.log")

    debug_frames = sorted(LOGS_DIR.glob("debug_scene*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    rep.add(
        "debug_scene 截图",
        True,
        f"{len(debug_frames)} 张" + (f"，最新: {debug_frames[0].name}" if debug_frames else ""),
        fix="场景识别失败时 account_switcher 自动保存；用 tools/crop_template_from_screenshot.py 补模板",
    )

    stream_logs = sorted((LOGS_DIR / "stream_log").glob("stream_*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if (LOGS_DIR / "stream_log").is_dir() else []
    if stream_logs:
        slines = _read_tail(stream_logs[0], 200)
        s_err = [ln for ln in slines if re.search(r"\b(ERROR|FAILED)\b", ln, re.I)]
        rep.add(
            f"stream_log/{stream_logs[0].name}",
            len(s_err) == 0,
            f"{len(s_err)} 条错误" if s_err else "近期无 ERROR",
        )

    return rep


def print_report(title: str, rep: Report) -> None:
    print(f"\n=== {title} ===")
    for item in rep.items:
        mark = "OK" if item.ok else "!!"
        print(f"  [{mark}] {item.name}: {item.detail}")
        if not item.ok and item.fix:
            print(f"       → {item.fix}")


def print_e2e_runbook() -> None:
    print(
        """
=== P0 E2E 标准流程 ===
1. 基础设施
   .\\docker\\start-dev.ps1
   curl http://localhost:8060/actuator/health   # 含 UP

2. Agent（bend-agent 目录，另开终端）
   python tools/verify_p0_readiness.py
   python src/main.py --config configs/agent.yaml

3. 平台操作（http://localhost:3090）
   a) 串流账号 + 游戏账号（email = EA 邮箱）+ 绑定 Agent
   b) 「启动串流」→ Step1-3，任务进入 READY / streaming_session
   c) 「开始自动化」→ gameActionType=squad_battle → Step4

4. P0 验收点
   - 新号：FC 启动后自动 EA 引导 → UT (127/147/149)
   - SQB：导航到 scene189 → 进入比赛
   - 失败时查 logs/task_log/ + logs/debug_scene*.png

5. 常用恢复
   - 画面卡住：任务详情 → 暂停 → 手动调屏 → 恢复
   - 串流断：任务控制 → 重连串流 (reconnect_stream)
   - Step4 失败但串流在：automation_failed 可再次「开始自动化」
"""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="P0 E2E troubleshooting")
    parser.add_argument("--gateway-url", default=GATEWAY_DEFAULT)
    parser.add_argument("--frontend-url", default=FRONTEND_DEFAULT)
    parser.add_argument("--analyze-logs", action="store_true", help="分析 logs/ 下任务与错误")
    parser.add_argument("--task-id", default="", help="指定 taskId 分析对应 task_log")
    parser.add_argument("--runbook", action="store_true", help="打印 E2E 标准流程")
    args = parser.parse_args()

    print("P0 E2E Troubleshoot\n")

    infra = check_infrastructure(args.gateway_url, args.frontend_url)
    agent = check_agent_ready()
    print_report("基础设施", infra)
    print_report("Agent 就绪", agent)

    if args.analyze_logs or args.task_id:
        logs = analyze_logs(args.task_id or None)
        print_report("日志 / 调试帧", logs)

    if args.runbook or (not infra.all_ok):
        print_e2e_runbook()

    blockers = [i for i in infra.items + agent.items if not i.ok]
    if blockers:
        print("\nRESULT: BLOCKED — 先解决上述 !! 项再跑 E2E")
        print("下一步: 启动 Docker Desktop → .\\docker\\start-dev.ps1 → 重跑本脚本")
        return 1

    if not (LOGS_DIR / "task_log").exists() or not any((LOGS_DIR / "task_log").glob("task_*.log")):
        print("\nRESULT: READY — 基础设施与 Agent 侧就绪，尚无任务日志")
        print("下一步: 启动 Agent → 前端下发串流任务 → python tools/e2e_troubleshoot.py --analyze-logs")
        return 0

    print("\nRESULT: 有历史任务日志，建议: python tools/e2e_troubleshoot.py --analyze-logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
