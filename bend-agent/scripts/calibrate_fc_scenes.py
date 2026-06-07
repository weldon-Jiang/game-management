#!/usr/bin/env python3
"""
FC 场景模板校准（对齐 streaming/xsrpst.py generate_templates 流程）

用法：
  # 从调试帧裁剪模板 PNG（scene 帧 -> templates/{scene}.{tpl}.png）
  python scripts/calibrate_fc_scenes.py generate --scene 203 --frame logs/debug_scene203_*.png

  # 校验现有模板在调试帧上的匹配情况
  python scripts/calibrate_fc_scenes.py verify
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Iterable, List, Optional

import cv2

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT))

from agent.game.account_switcher import (  # noqa: E402
    FC_UT_TARGET_SCENES,
    XBOX_HOME_SCENES,
    AccountSwitcher,
)
from agent.scene.streaming_scene_detector import StreamingSceneDetector  # noqa: E402
from configs.scene_schemas import SCENE_COLUMNS, SCENE_SCHEMAS  # noqa: E402

FC_CALIBRATION_SCENES = (203, 101, 126)
CHECK_SCENES = sorted(XBOX_HOME_SCENES | FC_UT_TARGET_SCENES | {2, 3})


def _schema_rows_for_scene(scene_id: int) -> List[dict]:
    rows = []
    for schema in SCENE_SCHEMAS:
        row = dict(zip(SCENE_COLUMNS, schema))
        if int(row["scene_id"]) == scene_id:
            rows.append(row)
    return rows


def generate_templates_from_frame(
    scene_id: int,
    frame_path: Path,
    *,
    template_dir: Path,
    overwrite: bool = True,
) -> int:
    """
    按 streaming generate_templates() 逻辑，从场景截图裁剪模板 PNG。
    """
    image = cv2.imread(str(frame_path))
    if image is None:
        raise FileNotFoundError(f"unreadable frame: {frame_path}")

    rows = _schema_rows_for_scene(scene_id)
    if not rows:
        raise ValueError(f"no schema for scene {scene_id}")

    target_w = int(rows[0]["scene_width"])
    target_h = int(rows[0]["scene_height"])
    h, w = image.shape[:2]
    if w != target_w or h != target_h:
        image = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)

    template_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: set[str] = set()

    for row in rows:
        token = f"{scene_id}.{int(row['template_id'])}"
        if token in seen:
            continue
        seen.add(token)

        crop = image[
            int(row["template_top"]) : int(row["template_bottom"]),
            int(row["template_left"]) : int(row["template_right"]),
        ]
        if crop.size == 0:
            print(f"[SKIP] empty crop for {token}")
            continue

        out = template_dir / f"{token}.png"
        if out.exists() and not overwrite:
            print(f"[SKIP] exists {out}")
            continue
        cv2.imwrite(str(out), crop)
        print(f"[OK] {out.name} <- {frame_path.name} crop {crop.shape[1]}x{crop.shape[0]}")
        written += 1

    return written


def verify_frames(images: Iterable[str]) -> int:
    switcher = AccountSwitcher()
    switcher.set_scene_detector(StreamingSceneDetector(str(ROOT / "templates")))

    for path_str in images:
        path = Path(path_str)
        if not path.exists():
            print(f"[SKIP] not found: {path}")
            continue
        img = cv2.imread(str(path))
        if img is None:
            print(f"[SKIP] unreadable: {path}")
            continue

        class _Frame:
            data = img

        async def _getter(frame=_Frame()):
            return frame

        switcher.set_frame_getter(_getter)

        async def _run():
            print(f"\n=== {path.name} ({img.shape[1]}x{img.shape[0]}) ===")
            for sid in CHECK_SCENES:
                thr = switcher._scene_match_threshold(sid)
                result = switcher._scene_detector.recognize_scene(
                    img, scene_id=sid, threshold=thr
                )
                if result.matched:
                    print(f"  scene {sid:3d}  conf={result.confidence:.3f}  thr={thr}")
            home = await switcher._detect_any_scene(list(XBOX_HOME_SCENES), strict=False)
            ut = await switcher._detect_any_scene(list(FC_UT_TARGET_SCENES), strict=False)
            print(f"  -> home={home}  ut={ut}")

        asyncio.run(_run())

    return 0


def _resolve_frame_arg(frame_arg: str) -> Path:
    path = Path(frame_arg)
    if path.exists():
        return path
    matches = sorted(ROOT.glob(frame_arg))
    if not matches:
        raise FileNotFoundError(f"frame not found: {frame_arg}")
    return matches[-1]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="FC scene template calibration (streaming-style)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate", help="Crop template PNGs from a scene frame")
    gen.add_argument("--scene", type=int, required=True, choices=FC_CALIBRATION_SCENES)
    gen.add_argument("--frame", type=str, required=True, help="Path or glob to scene frame")
    gen.add_argument("--template-dir", type=str, default=str(ROOT / "templates"))
    gen.add_argument("--no-overwrite", action="store_true")

    verify = sub.add_parser("verify", help="Verify templates against debug PNGs")
    verify.add_argument(
        "images",
        nargs="*",
        default=sorted(str(p) for p in (ROOT / "logs").glob("debug_scene*.png")),
    )

    args = parser.parse_args(argv)

    if args.cmd == "generate":
        frame = _resolve_frame_arg(args.frame)
        count = generate_templates_from_frame(
            args.scene,
            frame,
            template_dir=Path(args.template_dir),
            overwrite=not args.no_overwrite,
        )
        print(f"Generated {count} template(s) for scene {args.scene}")
        return 0

    return verify_frames(args.images)


if __name__ == "__main__":
    raise SystemExit(main())
