"""
Windows / PowerShell UTF-8 bootstrap for console and redirected logs.

Call ensure_utf8_stdio() as early as possible in any entry script (main.py,
run_live_task.py, etc.) so Chinese log messages render correctly in the
terminal and when output is redirected to a file.
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
    Force UTF-8 on stdout/stderr and align the Windows console code page.

    Safe to call multiple times; subsequent calls are no-ops unless force=True.
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
