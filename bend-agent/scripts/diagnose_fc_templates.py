#!/usr/bin/env python3
"""Per-template diagnostics for FC scenes (streaming-style)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from agent.scene.streaming_scene_detector import StreamingSceneDetector  # noqa: E402


def diagnose(detector: StreamingSceneDetector, image_path: Path, scene_id: int) -> None:
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"[SKIP] unreadable {image_path}")
        return

    frame = detector._normalize_frame(img, scene_id)
    result = detector.recognize_scene(img, scene_id=scene_id, threshold=0.0)
    configs = detector._scene_configs.get(scene_id, [])

    print(f"\n=== {image_path.name} -> scene {scene_id} ({img.shape[1]}x{img.shape[0]} -> {frame.shape[1]}x{frame.shape[0]}) ===")
    print(f"overall matched={result.matched} conf={result.confidence:.3f}")

    for cfg in configs:
        tid = int(cfg["template_id"])
        sid = int(cfg["search_id"])
        tpl = detector._load_template(scene_id, tid)
        if tpl is None:
            print(f"  tpl {tid} search {sid}: MISSING template file")
            continue
        sr = frame[
            int(cfg["search_top"]) : int(cfg["search_bottom"]),
            int(cfg["search_left"]) : int(cfg["search_right"]),
        ]
        need = float(cfg["likeness"]) / 100.0
        ok, sim = detector._match_single_template(sr, tpl, int(cfg["algorithm"]), need)
        print(
            f"  tpl {tid} search {sid}: sim={sim:.3f} need={cfg['likeness']}% ok={ok} "
            f"sr={sr.shape[1]}x{sr.shape[0]} tpl={tpl.shape[1]}x{tpl.shape[0]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=int, required=True)
    parser.add_argument("image", type=str)
    args = parser.parse_args()

    detector = StreamingSceneDetector(str(ROOT / "templates"))
    diagnose(detector, Path(args.image), args.scene)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
