#!/usr/bin/env python3
"""Audit template completeness: bend-agent vs streaming/xsrpst.py schema."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STREAM = Path(r"D:/auto-xbox/streaming")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from configs.scene_schemas import SCENE_COLUMNS, SCENE_SCHEMAS  # noqa: E402


def required_tokens(schemas) -> tuple[set[str], dict[int, set[int]]]:
    tokens: set[str] = set()
    by_scene: dict[int, set[int]] = {}
    for schema in schemas:
        row = dict(zip(SCENE_COLUMNS, schema))
        sid = int(row["scene_id"])
        tid = int(row["template_id"])
        tokens.add(f"{sid}.{tid}")
        by_scene.setdefault(sid, set()).add(tid)
    return tokens, by_scene


def load_streaming_schema():
    sys.path.insert(0, str(STREAM))
    spec_u = importlib.util.spec_from_file_location("xsrputil", STREAM / "xsrputil.py")
    xutil = importlib.util.module_from_spec(spec_u)
    spec_u.loader.exec_module(xutil)

    spec = importlib.util.spec_from_file_location("xsrpst", STREAM / "xsrpst.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    df = mod.get_templates_schema()
    T = xutil.Template
    tokens: set[str] = set()
    by_scene: dict[int, set[int]] = {}
    for _, row in df.iterrows():
        sid = int(row[T.key_scene_id])
        tid = int(row[T.key_template_id])
        tokens.add(f"{sid}.{tid}")
        by_scene.setdefault(sid, set()).add(tid)
    return tokens, by_scene, len(df)


def main() -> int:
    bend_tokens, bend_by_scene = required_tokens(SCENE_SCHEMAS)
    tpl_dir = ROOT / "templates"
    png_tokens = {p.stem for p in tpl_dir.glob("*.png")}

    print("=== BEND-AGENT ===")
    print(f"schema rows: {len(SCENE_SCHEMAS)}")
    print(f"unique templates required: {len(bend_tokens)}")
    print(f"unique scenes: {len(bend_by_scene)}")
    print(f"PNG files on disk: {len(png_tokens)}")

    missing = sorted(bend_tokens - png_tokens)
    print(f"missing PNGs: {len(missing)}")
    if missing:
        print(f"  missing list: {missing}")

    fc_scenes = [101, 126, 127, 147, 149, 203]
    print("\nFC critical scenes:")
    for sid in fc_scenes:
        need = bend_by_scene.get(sid, set())
        have = {int(t.split(".")[1]) for t in png_tokens if t.startswith(f"{sid}.")}
        miss = sorted(need - have)
        print(f"  scene {sid}: need {len(need)} have {len(have)} missing {miss or 'none'}")

    print("\n=== STREAMING REPO ===")
    stream_tpl = STREAM / "template"
    stream_scene = STREAM / "scene"
    stream_dat = STREAM / "data" / "templates.dat"
    print(f"template/ exists: {stream_tpl.exists()}")
    print(f"scene/ exists: {stream_scene.exists()}")
    print(f"data/templates.dat exists: {stream_dat.exists()}")

    stream_png: set[str] = set()
    if stream_tpl.exists():
        stream_png = {p.stem for p in stream_tpl.glob("*.png")}
        print(f"template/*.png count: {len(stream_png)}")

    try:
        stream_tokens, stream_by_scene, stream_rows = load_streaming_schema()
        print(f"xsrpst schema rows: {stream_rows}")
        print(f"xsrpst unique templates: {len(stream_tokens)}")
        print(f"xsrpst unique scenes: {len(stream_by_scene)}")

        only_bend = bend_tokens - stream_tokens
        only_stream = stream_tokens - bend_tokens
        print(f"schema diff: bend-only={len(only_bend)} stream-only={len(only_stream)}")
        if only_bend:
            print(f"  bend-only: {sorted(only_bend)}")
        if only_stream:
            print(f"  stream-only: {sorted(only_stream)}")

        if stream_png:
            smiss = sorted(stream_tokens - stream_png)
            print(f"streaming missing PNG vs xsrpst schema: {len(smiss)}")
            if smiss:
                print(f"  sample: {smiss[:25]}")
        else:
            print("streaming repo has NO template/ PNGs (not committed to git)")

        print("\nFC critical scenes (streaming schema):")
        for sid in fc_scenes:
            need = stream_by_scene.get(sid, set())
            have = {int(t.split(".")[1]) for t in stream_png if t.startswith(f"{sid}.")} if stream_png else set()
            print(f"  scene {sid}: schema needs template ids {sorted(need)}")
            if stream_png:
                print(f"    on disk: {sorted(have) if have else 'NONE'}")

        _audit_external_sources(stream_tokens, fc_scenes)
    except Exception as exc:
        print(f"failed to load streaming schema: {exc}")

    return 0


def _audit_external_sources(stream_tokens: set[str], fc_scenes: list[int]) -> None:
    import compress_pickle

    candidates = [
        ("xsrp/_internal/data/templates.dat", Path(r"D:/auto-xbox/xsrp/_internal/data/templates.dat")),
        ("ttt-reference/templates.dat", Path(r"D:/auto-xbox/XStreamingDesktop-main/ttt-reference/templates.dat")),
        ("ttt-reference/template/*.png", Path(r"D:/auto-xbox/XStreamingDesktop-main/ttt-reference/template")),
    ]
    print("\n=== EXTERNAL TEMPLATE SOURCES (streaming runtime assets) ===")
    for label, path in candidates:
        print(f"\n--- {label} ---")
        if not path.exists():
            print("  MISSING")
            continue
        have: set[str] = set()
        if path.suffix == ".dat":
            with open(path, "rb") as handle:
                data = compress_pickle.load(handle, compression="gzip")
            have = set(data.keys())
            print(f"  entries: {len(have)}")
        else:
            have = {p.stem for p in path.glob("*.png")}
            print(f"  png count: {len(have)}")
        miss = sorted(stream_tokens - have)
        print(f"  missing vs xsrpst schema: {len(miss)}")
        if miss:
            print(f"  missing sample: {miss[:25]}")
        for sid in fc_scenes:
            prefix = f"{sid}."
            need = sorted(t for t in stream_tokens if t.startswith(prefix))
            got = sorted(t for t in have if t.startswith(prefix))
            if need != got:
                print(f"  FC {sid}: need {need} got {got}")
            else:
                print(f"  FC {sid}: OK {got}")


if __name__ == "__main__":
    raise SystemExit(main())
