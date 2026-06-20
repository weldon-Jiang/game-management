#!/usr/bin/env python3
"""对单帧截图探测 P0 场景匹配分数。用法: python tools/probe_frame_scenes.py logs/debug_scene6_*.png"""
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from configs.scene_schemas import SCENE_NAMES
from src.agent.scene.streaming_scene_detector import StreamingSceneDetector
from src.agent.vision.template_manager import STEP4_REQUIRED_SCENE_IDS

P0 = sorted(set(STEP4_REQUIRED_SCENE_IDS + [2, 3, 5, 6, 203]))


def main() -> None:
    img_path = Path(sys.argv[1] if len(sys.argv) > 1 else "logs/debug_scene6_1781419269.png")
    img = cv2.imread(str(img_path))
    if img is None:
        raise SystemExit(f"cannot read {img_path}")
    det = StreamingSceneDetector(str(ROOT / "templates"))
    print(f"Frame: {img_path} ({img.shape[1]}x{img.shape[0]})")
    print("\n--- P0 / 账号链 ---")
    for sid in P0:
        r = det.recognize_scene(img, scene_id=sid)
        mark = "OK" if r.matched else "--"
        name = SCENE_NAMES.get(sid, "")
        print(f"  {mark}  scene {sid:3d}  conf={r.confidence:.3f}  {name}")


if __name__ == "__main__":
    main()
