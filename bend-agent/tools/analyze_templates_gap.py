#!/usr/bin/env python3
"""Compare templates/ vs scene schemas and automation requirements."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.scene_schemas import SCENE_COLUMNS, SCENE_NAMES, SCENE_SCHEMAS
from configs.scene_transitions import SQB_NAVIGATION_SCENES
from configs.football_scenes import FOOTBALL_SCHEMAS
from src.agent.game.ea_onboarding import EA_ONBOARDING_CANDIDATES
from src.agent.vision.template_manager import STEP4_REQUIRED_SCENE_IDS, required_template_names

TPL_DIR = ROOT / "templates"
STREAMING_XSRPST = Path(r"D:\auto-xbox\streaming\xsrpst.py")


def load_existing() -> set[str]:
    names: set[str] = set()
    if not TPL_DIR.exists():
        return names
    for p in TPL_DIR.rglob("*.png"):
        names.add(p.name)
    return names


def schema_scene_ids() -> set[int]:
    return {int(dict(zip(SCENE_COLUMNS, s))["scene_id"]) for s in SCENE_SCHEMAS}


def analyze_group(label: str, scene_ids, existing: set[str]) -> dict:
    ids = sorted(set(scene_ids))
    req = required_template_names(ids)
    miss = [x for x in req if x not in existing]
    have = [x for x in req if x in existing]
    in_schema = sorted(set(ids) & schema_scene_ids())
    not_in_schema = sorted(set(ids) - schema_scene_ids())
    return {
        "label": label,
        "scene_count": len(ids),
        "required_templates": len(req),
        "have": len(have),
        "missing": miss,
        "not_in_schema": not_in_schema,
        "in_schema": in_schema,
    }


def streaming_scene_ids() -> set[int]:
    if not STREAMING_XSRPST.exists():
        return set()
    txt = STREAMING_XSRPST.read_text(encoding="utf-8")
    start = txt.find("def get_templates_schema")
    end = txt.find("def get_scenes_diagram", start)
    block = txt[start:end]
    scenes: set[int] = set()
    for match in re.finditer(r"schema\s*=\s*\[([\s\S]*?)\]", block):
        vals: list[int] = []
        for line in match.group(1).splitlines():
            line = line.split("#", 1)[0].strip().rstrip(",")
            if not line:
                continue
            try:
                vals.append(int(line))
            except ValueError:
                pass
        if len(vals) == 15:
            scenes.add(vals[0])
    return scenes


def main() -> None:
    existing = load_existing()
    schema_ids = schema_scene_ids()
    names_ids = set(SCENE_NAMES.keys())

    groups = [
        ("STEP4_REQUIRED（Step4 启动预检）", STEP4_REQUIRED_SCENE_IDS),
        ("EA_ONBOARDING（首登引导）", EA_ONBOARDING_CANDIDATES),
        ("SQB_NAVIGATION（SQB 导航链）", SQB_NAVIGATION_SCENES),
        (
            "MATCH_END_SETTLEMENT（赛后/结算）",
            [102, 127, 147, 149, 184, 185, 186, 187, 188, 189, 193],
        ),
    ]

    print("=== templates 目录 ===")
    print(f"路径: {TPL_DIR}")
    print(f"PNG 数量: {len(existing)}")
    if existing:
        sample = sorted(existing)[:15]
        print(f"样例: {', '.join(sample)}")
    else:
        print("(空 — 需运行 python tools/sync_scene_schemas.py 从 streaming 同步)")

    print()
    print("=== scene_schemas.py ===")
    print(f"schema 场景数: {len(schema_ids)} (ID {min(schema_ids)}–{max(schema_ids)})")
    print(f"SCENE_NAMES 条目: {len(names_ids)}")
    only_names = sorted(names_ids - schema_ids)
    only_schema = sorted(schema_ids - names_ids)
    if only_names:
        print(f"SCENE_NAMES 有、schema 无 ({len(only_names)}): {only_names}")
    if only_schema:
        print(f"schema 有、SCENE_NAMES 无 ({len(only_schema)}): {only_schema}")

    print()
    for label, sids in groups:
        r = analyze_group(label, sids, existing)
        print(f"--- {r['label']} ---")
        print(
            f"  场景 {r['scene_count']} 个 | 需模板 {r['required_templates']} | "
            f"已有 {r['have']} | 缺 {len(r['missing'])}"
        )
        if r["not_in_schema"]:
            print(f"  [WARN] schema undefined ({len(r['not_in_schema'])}): {r['not_in_schema']}")
        if r["missing"]:
            print(f"  缺模板 ({len(r['missing'])}):")
            for name in r["missing"][:50]:
                sid = int(name.split(".")[0])
                desc = SCENE_NAMES.get(sid, "(schema 无名称)")
                print(f"    {name}  # {desc}")
            if len(r["missing"]) > 50:
                print(f"    ... 还有 {len(r['missing']) - 50} 个")
        print()

    ea_no_schema = sorted(set(EA_ONBOARDING_CANDIDATES) - schema_ids)
    print("--- EA 引导：schema 完全没有的场景 ---")
    print(f"共 {len(ea_no_schema)} 个: {ea_no_schema}")
    print("(需 sync_scene_schemas.py 从 streaming 补 schema + 模板)")
    print()

    stream_ids = streaming_scene_ids()
    if stream_ids:
        only_stream = sorted(stream_ids - schema_ids)
        print("--- 对比 streaming/xsrpst.py ---")
        print(f"streaming 场景数: {len(stream_ids)}")
        print(f"streaming 有、bend schema 无 ({len(only_stream)}): {only_stream}")

    football = sorted({f"{s[0]}.{s[1]}.png" for s in FOOTBALL_SCHEMAS})
    fb_miss = [t for t in football if t not in existing]
    print()
    print("--- football_scenes（场中，ID 100–109 与 UT 同名不同义）---")
    print(f"需 {len(football)} 个 | 缺 {len(fb_miss)}")
    if fb_miss:
        print("缺:", ", ".join(fb_miss))


if __name__ == "__main__":
    main()
