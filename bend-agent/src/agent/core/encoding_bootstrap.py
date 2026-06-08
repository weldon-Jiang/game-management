"""
Windows / PowerShell UTF-8 引导（控制台与重定向日志）。

在入口脚本（main.py、run_live_task.py 等）尽可能早调用 ensure_utf8_stdio()，
确保中文日志在终端及重定向到文件时正确显示。
"""
from __future__ import annotations

import io
import os
import sys


def _configure_windows_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def ensure_utf8_stdio(*, force: bool = False) -> None:
    """
    强制 stdout/stderr 使用 UTF-8，并同步 Windows 控制台代码页。

    可多次调用；除非 force=True，后续调用为 no-op。
    """
    if getattr(ensure_utf8_stdio, "_done", False) and not force:
        return

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    _configure_windows_console()

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "buffer"):
                wrapped = io.TextIOWrapper(
                    stream.buffer,
                    encoding="utf-8",
                    errors="replace",
                    line_buffering=True,
                )
                setattr(sys, stream_name, wrapped)
            elif hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ensure_utf8_stdio._done = True  # type: ignore[attr-defined]
