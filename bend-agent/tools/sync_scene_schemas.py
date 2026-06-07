#!/usr/bin/env python3
"""
Sync scene schemas and template PNGs from streaming/xsrpst.py to bend-agent.

Usage:
    python tools/sync_scene_schemas.py
"""

from __future__ import annotations

import ast
import os
import re
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STREAMING_ROOT = ROOT.parent.parent / "streaming"
if not STREAMING_ROOT.exists():
    STREAMING_ROOT = Path(r"D:\auto-xbox\streaming")

XSRPST = STREAMING_ROOT / "xsrpst.py"
SCHEMA_OUT = ROOT / "configs" / "scene_schemas.py"
TEMPLATE_OUT = ROOT / "templates"
SCENE_DIR = STREAMING_ROOT / "scene"

# Fallback template sources (xsrp build / XStreamingDesktop reference)
TEMPLATES_DAT_CANDIDATES = [
    Path(r"D:\auto-xbox\XStreamingDesktop-main\ttt-reference\templates.dat"),
    STREAMING_ROOT / "data" / "templates.dat",
    Path(r"D:\auto-xbox\xsrp\_internal\data\templates.dat"),
]
TEMPLATE_PNG_DIR_CANDIDATES = [
    Path(r"D:\auto-xbox\XStreamingDesktop-main\ttt-reference\template"),
    TEMPLATE_OUT,
]

# bend-agent 横版 Xbox Home / FC 联调校准（sync 后保留，勿被 streaming 旧纵向坐标覆盖）
FC_SCENE_SCHEMA_OVERRIDES: dict[int, list[list[int]]] = {
    203: [
        [203, 960, 540, 1, 24, 404, 94, 476, 1, 22, 402, 96, 478, 90, 3],
        [203, 960, 540, 2, 70, 448, 92, 472, 1, 66, 444, 96, 476, 90, 3],
    ],
    126: [
        [126, 960, 540, 1, 49, 52, 62, 65, 1, 45, 48, 66, 69, 90, 3],
    ],
}


def _extract_schemas_from_xsrpst() -> list[list[int]]:
    content = XSRPST.read_text(encoding="utf-8")
    start = content.find("def get_templates_schema")
    end = content.find("def get_scenes_diagram", start)
    block = content[start:end]

    schemas: list[list[int]] = []
    for match in re.finditer(r"schema\s*=\s*\[([\s\S]*?)\]", block):
        raw = match.group(1)
        values: list[int] = []
        for line in raw.splitlines():
            line = line.split("#", 1)[0].strip().rstrip(",")
            if not line:
                continue
            try:
                values.append(int(line))
            except ValueError:
                continue
        if len(values) == 15:
            schemas.append(values)
    return schemas


def _extract_scene_names(existing_text: str) -> dict[int, str]:
    names: dict[int, str] = {}
    scene_names_start = existing_text.find("SCENE_NAMES = {")
    if scene_names_start < 0:
        return names
    scene_names_end = existing_text.find("}\n\nALGORITHM_NAMES", scene_names_start)
    block = existing_text[scene_names_start:scene_names_end]
    for line in block.splitlines():
        m = re.match(r"\s*(\d+):\s*\"(.+)\",?\s*$", line)
        if m:
            names[int(m.group(1))] = m.group(2)
    return names


def _apply_fc_schema_overrides(schemas: list[list[int]]) -> list[list[int]]:
    if not FC_SCENE_SCHEMA_OVERRIDES:
        return schemas
    filtered = [row for row in schemas if row[0] not in FC_SCENE_SCHEMA_OVERRIDES]
    for scene_id in sorted(FC_SCENE_SCHEMA_OVERRIDES):
        filtered.extend(FC_SCENE_SCHEMA_OVERRIDES[scene_id])
    filtered.sort(key=lambda row: (row[0], row[8], row[3]))
    return filtered


def _write_scene_schemas(schemas: list[list[int]], scene_names: dict[int, str]) -> None:
    header = '''"""
Scene Template Schemas - Streaming项目场景模板配置
=================================================

本配置文件由 tools/sync_scene_schemas.py 从 streaming/xsrpst.py 同步生成。

模板文件命名规则：{场景ID}.{模板ID}.png
"""

SCENE_SCHEMAS = [
'''
    lines = [header]
    current_scene = None
    for row in schemas:
        scene_id = row[0]
        if scene_id != current_scene:
            if current_scene is not None:
                lines.append("\n")
            name = scene_names.get(scene_id, f"场景{scene_id}")
            lines.append(f"    # 场景{scene_id}：{name}\n")
            current_scene = scene_id
        lines.append(f"    {row},\n")
    lines.append("]\n\n")
    lines.append(
        "SCENE_COLUMNS = [\n"
        "    'scene_id',\n"
        "    'scene_width',\n"
        "    'scene_height',\n"
        "    'template_id',\n"
        "    'template_left',\n"
        "    'template_top',\n"
        "    'template_right',\n"
        "    'template_bottom',\n"
        "    'search_id',\n"
        "    'search_left',\n"
        "    'search_top',\n"
        "    'search_right',\n"
        "    'search_bottom',\n"
        "    'likeness',\n"
        "    'algorithm',\n"
        "]\n\n"
    )
    lines.append("SCENE_NAMES = {\n")
    for scene_id in sorted(set(row[0] for row in schemas)):
        name = scene_names.get(scene_id, f"场景{scene_id}")
        lines.append(f'    {scene_id}: "{name}",\n')
    lines.append("}\n\n")
    lines.append(
        "ALGORITHM_NAMES = {\n"
        "    0: \"TM_SQDIFF\",\n"
        "    1: \"TM_SQDIFF_NORMED\",\n"
        "    2: \"TM_CCORR\",\n"
        "    3: \"TM_CCORR_NORMED\",\n"
        "    4: \"TM_CCOEFF\",\n"
        "    5: \"TM_CCOEFF_NORMED\",\n"
        "}\n"
    )
    SCHEMA_OUT.write_text("".join(lines), encoding="utf-8")


def _resolve_templates_dat() -> Path | None:
    for path in TEMPLATES_DAT_CANDIDATES:
        if path.exists():
            return path
    return None


def _export_templates_from_dat(schemas: list[list[int]]) -> int:
    templates_dat = _resolve_templates_dat()
    if templates_dat is None:
        return 0

    try:
        import compress_pickle
    except ImportError:
        print("compress_pickle not installed; skip templates.dat export")
        return 0

    templates = compress_pickle.loads(templates_dat.read_bytes(), compression="gzip")
    TEMPLATE_OUT.mkdir(parents=True, exist_ok=True)
    exported = 0
    for row in schemas:
        scene_id, template_id = row[0], row[3]
        key = f"{scene_id}.{template_id}"
        image = templates.get(key)
        if image is None:
            continue
        out_path = TEMPLATE_OUT / f"{scene_id}.{template_id}.png"
        cv2.imwrite(str(out_path), image)
        exported += 1
    print(f"  templates.dat source: {templates_dat} ({len(templates)} keys)")
    return exported


def _export_templates_from_png_dir(schemas: list[list[int]]) -> int:
    """Copy pre-built PNG templates from reference directories."""
    source_dir = None
    for candidate in TEMPLATE_PNG_DIR_CANDIDATES:
        if candidate.exists() and candidate != TEMPLATE_OUT and any(candidate.glob("*.png")):
            source_dir = candidate
            break
    if source_dir is None:
        return 0

    TEMPLATE_OUT.mkdir(parents=True, exist_ok=True)
    exported = 0
    for row in schemas:
        scene_id, template_id = row[0], row[3]
        name = f"{scene_id}.{template_id}.png"
        src = source_dir / name
        if not src.exists():
            continue
        dst = TEMPLATE_OUT / name
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            exported += 1
            continue
        dst.write_bytes(src.read_bytes())
        exported += 1
    print(f"  png dir source: {source_dir}")
    return exported


def _export_templates_from_scene(schemas: list[list[int]]) -> int:
    if not SCENE_DIR.exists():
        return 0

    TEMPLATE_OUT.mkdir(parents=True, exist_ok=True)
    exported = 0
    for row in schemas:
        scene_id, template_id = row[0], row[3]
        tpl_left, tpl_top, tpl_right, tpl_bottom = row[4], row[5], row[6], row[7]
        scene_path = SCENE_DIR / f"{scene_id}.png"
        if not scene_path.exists():
            continue
        scene_img = cv2.imread(str(scene_path))
        if scene_img is None:
            continue
        crop = scene_img[tpl_top:tpl_bottom, tpl_left:tpl_right]
        if crop.size == 0:
            continue
        out_path = TEMPLATE_OUT / f"{scene_id}.{template_id}.png"
        cv2.imwrite(str(out_path), crop)
        exported += 1
    return exported


def main() -> int:
    if not XSRPST.exists():
        print(f"xsrpst.py not found: {XSRPST}")
        return 1

    schemas = _apply_fc_schema_overrides(_extract_schemas_from_xsrpst())
    if not schemas:
        print("No schemas extracted")
        return 1

    existing_names = {}
    if SCHEMA_OUT.exists():
        existing_names = _extract_scene_names(SCHEMA_OUT.read_text(encoding="utf-8"))
    existing_names.setdefault(203, "主页横排磁贴---FC24可见")

    _write_scene_schemas(schemas, existing_names)
    print(f"Wrote {len(schemas)} schemas to {SCHEMA_OUT}")

    exported_dat = _export_templates_from_dat(schemas)
    exported_png = _export_templates_from_png_dir(schemas)
    exported_scene = _export_templates_from_scene(schemas)
    total_png = len(list(TEMPLATE_OUT.glob("*.png")))
    print(
        f"Exported templates: dat={exported_dat}, png_copy={exported_png}, "
        f"scene_crop={exported_scene}, total_png={total_png} -> {TEMPLATE_OUT}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
