"""Pytest configuration for automation unit tests."""

import sys
from pathlib import Path

# Ensure `src` is on sys.path so `agent.*` imports resolve when running from bend-agent/.
_SRC_ROOT = Path(__file__).resolve().parents[3]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))
