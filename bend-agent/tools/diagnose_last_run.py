#!/usr/bin/env python3
"""
分析最近一次自动化运行卡在哪一步，并输出「你要做什么」。

用法:
  cd bend-agent
  python tools/diagnose_last_run.py
  python tools/diagnose_last_run.py --task-id 0642492599bc91b829d1d0a8e0ea8992
  python tools/diagnose_last_run.py --log logs/agent.log
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.scene_schemas import SCENE_NAMES
from tools.automation_checkpoints import AUTOMATION_CHECKPOINTS, FAIL_PATTERNS

LOGS = ROOT / "logs"
SCENE_CAPTURE = LOGS / "scene_capture"


def _latest_task_id() -> Optional[str]:
    if not SCENE_CAPTURE.is_dir():
        return None
    dirs = [p for p in SCENE_CAPTURE.iterdir() if p.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda p: p.stat().st_mtime).name


def _read_log_tail(log_path: Path, max_bytes: int = 800_000) -> str:
    if not log_path.is_file():
        return ""
    data = log_path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def _find_checkpoint(log_text: str) -> Optional[Dict[str, Any]]:
    best: Optional[Dict[str, Any]] = None
    best_pos = -1
    for cp in AUTOMATION_CHECKPOINTS:
        step = cp["step"]
        for pat in FAIL_PATTERNS.get(step, []):
            for m in re.finditer(pat, log_text):
                if m.start() > best_pos:
                    best_pos = m.start()
                    best = {**cp, "matched_line": m.group(0)}
    return best


def _list_debug_files(task_id: Optional[str]) -> List[str]:
    found: List[str] = []
    for p in sorted(LOGS.glob("debug_*.png")):
        found.append(str(p.relative_to(ROOT)))
    if task_id:
        cap = SCENE_CAPTURE / task_id
        if cap.is_dir():
            for p in sorted(cap.iterdir()):
                found.append(str(p.relative_to(ROOT)))
    return found


def _format_scenes(scene_ids: List[int]) -> str:
    if not scene_ids:
        return "-"
    return ", ".join(f"{sid}({SCENE_NAMES.get(sid, '')})" for sid in scene_ids)


def diagnose(task_id: Optional[str], log_path: Path) -> str:
    task_id = task_id or _latest_task_id()
    log_text = _read_log_tail(log_path)
    cp = _find_checkpoint(log_text)
    files = _list_debug_files(task_id)

    lines = [
        "=" * 60,
        "自动化卡点诊断",
        "=" * 60,
        f"task_id: {task_id or '(未找到 scene_capture 目录)'}",
        f"log: {log_path.relative_to(ROOT) if log_path.is_relative_to(ROOT) else log_path}",
        "",
    ]

    if cp:
        lines.extend([
            f"【卡点步骤】 {cp['step']} — {cp['phase']}",
            f"【触发位置】 {cp['trigger']}",
            f"【日志命中】 {cp.get('matched_line', '')}",
            f"【涉及场景】 {_format_scenes(cp.get('scenes', []))}",
            "",
            "【你要做什么】",
            cp["you_do"],
            "",
        ])
        if cp.get("templates"):
            lines.append(f"【相关模板】 {cp['templates']}")
        if cp.get("ocr"):
            lines.append(f"【相关 OCR】 {cp['ocr']}")
        if cp.get("coord_format"):
            lines.append(f"【坐标格式】 {cp['coord_format']}")
        if cp.get("debug_where"):
            lines.append(f"【截图位置】 {cp['debug_where']}")
        lines.append("")
    else:
        lines.extend([
            "【卡点步骤】 未能从日志匹配明确失败点",
            "请搜索 agent.log 中 RuntimeError / 场景校验超时 / debug_scene",
            "",
        ])

    lines.append("【现有调试文件】")
    if files:
        for f in files[:20]:
            lines.append(f"  - {f}")
        if len(files) > 20:
            lines.append(f"  ... 共 {len(files)} 个")
    else:
        lines.append("  (无 debug_*.png，失败时可能未保存截图)")

    if task_id:
        survey = SCENE_CAPTURE / task_id / "entry_survey.json"
        if survey.is_file():
            lines.append("")
            lines.append("【entry_survey 首帧匹配】")
            data = json.loads(survey.read_text(encoding="utf-8"))
            ranked = sorted(
                data.get("scenes", {}).items(),
                key=lambda x: float(x[1].get("confidence", 0) if isinstance(x[1], dict) else 0),
                reverse=True,
            )
            for sid, info in ranked[:8]:
                if not isinstance(info, dict):
                    continue
                mark = "OK" if info.get("matched") else "--"
                lines.append(
                    f"  {mark} scene {sid}: conf={info.get('confidence', 0):.3f} "
                    f"{info.get('name', '')}"
                )

    lines.extend([
        "",
        "【坐标提交格式（发给我即可）】",
        "  场景ID: 6",
        "  模板ID: 1",
        "  template: left=134, top=95, right=177, bottom=110",
        "  search:   left=132, top=93, right=179, bottom=112",
        "  说明: 960×540 整帧上量，原点在左上角",
        "",
        "【探测命令】",
        f"  python tools/probe_frame_scenes.py logs/debug_scene6_xxx.png",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose last automation failure")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--log", default=str(LOGS / "agent.log"))
    args = parser.parse_args()
    print(diagnose(args.task_id, Path(args.log)))


if __name__ == "__main__":
    main()
