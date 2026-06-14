#!/usr/bin/env python3
"""
从 960x540 串流截图裁剪单张场景模板 PNG。

用于 reference 目录缺失的模板（如 242.1.png、97.2.png）：

  1. 在对应 UI 出现时保存一帧（960x540，与 scene_schemas 一致）
  2. 运行本脚本按 schema 坐标裁剪并写入 templates/

示例:
  python tools/crop_template_from_screenshot.py --scene 242 --image D:/captures/frame.png
  python tools/crop_template_from_screenshot.py --scene 97 --template 2 --image frame.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.scene_schemas import SCENE_COLUMNS, SCENE_SCHEMAS


def _find_schema_row(scene_id: int, template_id: int) -> list[int] | None:
    for row in SCENE_SCHEMAS:
        parsed = dict(zip(SCENE_COLUMNS, row))
        if int(parsed["scene_id"]) == scene_id and int(parsed["template_id"]) == template_id:
            return row
    return None


def crop_template(
    image_path: Path,
    scene_id: int,
    template_id: int,
    output_dir: Path,
) -> Path:
    row = _find_schema_row(scene_id, template_id)
    if row is None:
        raise SystemExit(f"schema 中未找到 scene={scene_id} template={template_id}")

    parsed = dict(zip(SCENE_COLUMNS, row))
    target_w = int(parsed["scene_width"])
    target_h = int(parsed["scene_height"])
    left = int(parsed["template_left"])
    top = int(parsed["template_top"])
    right = int(parsed["template_right"])
    bottom = int(parsed["template_bottom"])

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"无法读取图片: {image_path}")

    h, w = image.shape[:2]
    if w != target_w or h != target_h:
        image = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)

    crop = image[top:bottom, left:right]
    if crop.size == 0:
        raise SystemExit(f"裁剪区域为空: ({left},{top})-({right},{bottom})")

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{scene_id}.{template_id}.png"
    cv2.imwrite(str(out_path), crop)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop scene template from 960x540 screenshot")
    parser.add_argument("--scene", type=int, required=True, help="场景 ID，如 242")
    parser.add_argument("--template", type=int, default=1, help="模板 ID，默认 1")
    parser.add_argument("--image", type=Path, required=True, help="960x540 截图路径")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "templates",
        help="输出目录，默认 bend-agent/templates",
    )
    args = parser.parse_args()

    if not args.image.exists():
        print(f"文件不存在: {args.image}")
        return 1

    out = crop_template(args.image, args.scene, args.template, args.out_dir)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
