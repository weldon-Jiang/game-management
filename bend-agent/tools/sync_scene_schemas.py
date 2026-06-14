#!/usr/bin/env python3
"""
Sync scene schemas and template PNGs to bend-agent.

Sources:
  - streaming/xsrpst.py  — scenes 1–204 (production baseline)
  - ttt/xsrpst.py        — scenes 205–255 (EA 首登 / FC 扩展，ttt 独有)

Template PNG:
  - streaming templates.dat / scene crops — scenes 1–204
  - XStreamingDesktop ttt-reference/template (or ttt/template) — scenes 205+

Usage:
    python tools/sync_scene_schemas.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent

STREAMING_ROOT = REPO_ROOT / "streaming"
if not STREAMING_ROOT.exists():
    STREAMING_ROOT = Path(r"D:\auto-xbox\streaming")

TTT_ROOT = REPO_ROOT / "ttt"
if not TTT_ROOT.exists():
    TTT_ROOT = Path(r"D:\auto-xbox\ttt")

STREAMING_XSRPST = STREAMING_ROOT / "xsrpst.py"
TTT_XSRPST = TTT_ROOT / "xsrpst.py"
SCHEMA_OUT = ROOT / "configs" / "scene_schemas.py"
TEMPLATE_OUT = ROOT / "templates"
SCENE_DIR = STREAMING_ROOT / "scene"

# ttt 扩展场景起始 ID（205–255 仅存在于 ttt/xsrpst.py）
TTT_EXTENSION_MIN_SCENE_ID = 205

TEMPLATES_DAT_CANDIDATES = [
    Path(r"D:\auto-xbox\XStreamingDesktop-main\ttt-reference\templates.dat"),
    STREAMING_ROOT / "data" / "templates.dat",
    Path(r"D:\auto-xbox\xsrp\_internal\data\templates.dat"),
]

# 1–204：优先 streaming 参考图
STREAMING_PNG_DIR_CANDIDATES = [
    Path(r"D:\auto-xbox\XStreamingDesktop-main\ttt-reference\template"),
    TEMPLATE_OUT,
]

# 205+：ttt 扩展模板（ttt-reference 含 205–255 全套 PNG）
TTT_PNG_DIR_CANDIDATES = [
    Path(r"D:\auto-xbox\XStreamingDesktop-main\ttt-reference\template"),
    TTT_ROOT / "template",
    TTT_ROOT / "templates",
]

FC_SCENE_SCHEMA_OVERRIDES: dict[int, list[list[int]]] = {
    203: [
        [203, 960, 540, 1, 24, 404, 94, 476, 1, 22, 402, 96, 478, 90, 3],
        [203, 960, 540, 2, 70, 448, 92, 472, 1, 66, 444, 96, 476, 90, 3],
    ],
    126: [
        [126, 960, 540, 1, 49, 52, 62, 65, 1, 45, 48, 66, 69, 90, 3],
    ],
}


def _extract_schemas_from_xsrpst(path: Path) -> list[list[int]]:
    content = path.read_text(encoding="utf-8")
    start = content.find("def get_templates_schema")
    end = content.find("def get_scenes_diagram", start)
    if start < 0 or end < 0:
        return []
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


def _extract_scene_names_from_xsrpst(path: Path) -> dict[int, str]:
    """从 xsrpst schema 块注释提取场景中文名。"""
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8")
    start = content.find("def get_templates_schema")
    end = content.find("def get_scenes_diagram", start)
    if start < 0 or end < 0:
        return {}
    block = content[start:end]

    names: dict[int, str] = {}
    for match in re.finditer(
        r"schema\s*=\s*\[\s*\n\s*(\d+),\s*#\s*场景编号---【([^】]+)】",
        block,
    ):
        names[int(match.group(1))] = match.group(2).strip()

    for match in re.finditer(r"^\s*#\s*(\d+)\s+(.+?)\s*$", block, re.MULTILINE):
        sid = int(match.group(1))
        title = match.group(2).strip()
        if sid in names:
            continue
        if title.startswith("场景编号") or title.startswith("场景转移"):
            continue
        names[sid] = title
    return names


def _extract_scene_names(existing_text: str) -> dict[int, str]:
    names: dict[int, str] = {}
    scene_names_start = existing_text.find("SCENE_NAMES = {")
    if scene_names_start < 0:
        return names
    scene_names_end = existing_text.find("}\n\nALGORITHM_NAMES", scene_names_start)
    block = existing_text[scene_names_start:scene_names_end]
    for line in block.splitlines():
        match = re.match(r'\s*(\d+):\s*"(.+)",?\s*$', line)
        if match:
            names[int(match.group(1))] = match.group(2)
    return names


def _apply_fc_schema_overrides(schemas: list[list[int]]) -> list[list[int]]:
    if not FC_SCENE_SCHEMA_OVERRIDES:
        return schemas
    filtered = [row for row in schemas if row[0] not in FC_SCENE_SCHEMA_OVERRIDES]
    for scene_id in sorted(FC_SCENE_SCHEMA_OVERRIDES):
        filtered.extend(FC_SCENE_SCHEMA_OVERRIDES[scene_id])
    filtered.sort(key=lambda row: (row[0], row[8], row[3]))
    return filtered


def _merge_streaming_and_ttt_schemas(
    streaming_schemas: list[list[int]],
    ttt_schemas: list[list[int]],
) -> list[list[int]]:
    """streaming 1–204 为主；ttt 仅补充 streaming 中不存在的 scene_id（205–255）。"""
    streaming_ids = {row[0] for row in streaming_schemas}
    extension_rows = [row for row in ttt_schemas if row[0] not in streaming_ids]
    merged = list(streaming_schemas) + extension_rows
    merged.sort(key=lambda row: (row[0], row[8], row[3]))
    return merged


def _write_scene_schemas(schemas: list[list[int]], scene_names: dict[int, str]) -> None:
    header = '''"""
Scene Template Schemas - Streaming + ttt 场景模板配置
=====================================================

本配置文件由 tools/sync_scene_schemas.py 同步生成：
  - scenes 1–204：streaming/xsrpst.py（含 bend FC 203/126 坐标 override）
  - scenes 205–255：ttt/xsrpst.py（EA 首登 / FC 扩展）

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
    for scene_id in sorted({row[0] for row in schemas}):
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
        if row[0] >= TTT_EXTENSION_MIN_SCENE_ID:
            continue
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


def _export_templates_from_png_dirs(
    schemas: list[list[int]],
    candidates: list[Path],
    *,
    min_scene_id: int = 1,
    max_scene_id: int = 9999,
    only_missing: bool = False,
) -> int:
    source_dir = None
    for candidate in candidates:
        if candidate.exists() and any(candidate.glob("*.png")):
            source_dir = candidate
            break
    if source_dir is None:
        return 0

    TEMPLATE_OUT.mkdir(parents=True, exist_ok=True)
    exported = 0
    for row in schemas:
        scene_id, template_id = row[0], row[3]
        if scene_id < min_scene_id or scene_id > max_scene_id:
            continue
        name = f"{scene_id}.{template_id}.png"
        src = source_dir / name
        if not src.exists():
            continue
        dst = TEMPLATE_OUT / name
        if only_missing and dst.exists():
            exported += 1
            continue
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            exported += 1
            continue
        dst.write_bytes(src.read_bytes())
        exported += 1
    print(
        f"  png dir source: {source_dir} "
        f"(scene {min_scene_id}-{max_scene_id}, only_missing={only_missing})"
    )
    return exported


def _export_templates_from_scene(schemas: list[list[int]]) -> int:
    if not SCENE_DIR.exists():
        return 0

    TEMPLATE_OUT.mkdir(parents=True, exist_ok=True)
    exported = 0
    for row in schemas:
        if row[0] >= TTT_EXTENSION_MIN_SCENE_ID:
            continue
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


def _report_missing_templates(schemas: list[list[int]]) -> None:
    required = {f"{row[0]}.{row[3]}.png" for row in schemas}
    existing = {p.name for p in TEMPLATE_OUT.glob("*.png")}
    missing = sorted(required - existing)
    ext_missing = [m for m in missing if int(m.split(".")[0]) >= TTT_EXTENSION_MIN_SCENE_ID]
    print(f"  missing templates total: {len(missing)} (205+: {len(ext_missing)})")
    if ext_missing[:20]:
        print(f"  sample 205+ missing: {ext_missing[:20]}")
    if missing:
        print(
            "  tip: python tools/crop_template_from_screenshot.py "
            "--scene <id> --image <960x540.png>"
        )


def main() -> int:
    if not STREAMING_XSRPST.exists():
        print(f"streaming xsrpst.py not found: {STREAMING_XSRPST}")
        return 1

    streaming_schemas = _apply_fc_schema_overrides(
        _extract_schemas_from_xsrpst(STREAMING_XSRPST)
    )
    if not streaming_schemas:
        print("No schemas extracted from streaming")
        return 1

    ttt_schemas: list[list[int]] = []
    if TTT_XSRPST.exists():
        ttt_schemas = _extract_schemas_from_xsrpst(TTT_XSRPST)
        print(f"ttt xsrpst: {len(ttt_schemas)} schema rows from {TTT_XSRPST}")
    else:
        print(f"WARN: ttt xsrpst not found: {TTT_XSRPST} (skip 205-255 merge)")

    schemas = _merge_streaming_and_ttt_schemas(streaming_schemas, ttt_schemas)
    scene_ids = sorted({row[0] for row in schemas})
    ext_ids = [sid for sid in scene_ids if sid >= TTT_EXTENSION_MIN_SCENE_ID]
    print(
        f"Merged schemas: {len(schemas)} rows, {len(scene_ids)} scenes "
        f"(streaming<=204 + ttt ext {len(ext_ids)} scenes)"
    )

    scene_names: dict[int, str] = {}
    if SCHEMA_OUT.exists():
        scene_names.update(_extract_scene_names(SCHEMA_OUT.read_text(encoding="utf-8")))
    scene_names.update(_extract_scene_names_from_xsrpst(STREAMING_XSRPST))
    if TTT_XSRPST.exists():
        for sid, name in _extract_scene_names_from_xsrpst(TTT_XSRPST).items():
            if sid >= TTT_EXTENSION_MIN_SCENE_ID or sid not in scene_names:
                scene_names[sid] = name
    scene_names.setdefault(203, "主页横排磁贴---FC24可见")

    _write_scene_schemas(schemas, scene_names)
    print(f"Wrote {SCHEMA_OUT}")

    exported_dat = _export_templates_from_dat(schemas)
    exported_stream_png = _export_templates_from_png_dirs(
        schemas,
        STREAMING_PNG_DIR_CANDIDATES,
        min_scene_id=1,
        max_scene_id=TTT_EXTENSION_MIN_SCENE_ID - 1,
    )
    exported_ttt_png = _export_templates_from_png_dirs(
        schemas,
        TTT_PNG_DIR_CANDIDATES,
        min_scene_id=TTT_EXTENSION_MIN_SCENE_ID,
        max_scene_id=9999,
        only_missing=True,
    )
    exported_scene = _export_templates_from_scene(schemas)
    total_png = len(list(TEMPLATE_OUT.glob("*.png")))
    print(
        f"Exported templates: dat={exported_dat}, stream_png={exported_stream_png}, "
        f"ttt_png={exported_ttt_png}, scene_crop={exported_scene}, total_png={total_png}"
    )
    _report_missing_templates(schemas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
