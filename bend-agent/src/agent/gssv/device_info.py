"""X-MS-Device-Info header builder (XStreamingDesktop aligned)."""

import json
import platform
from typing import Any, Dict


def build_device_info(
    *,
    app_version: str = "1.0.0",
    os_name: str = "windows",
    device_type: str = "desktop",
) -> str:
    """Return JSON string for X-MS-Device-Info request header."""
    info: Dict[str, Any] = {
        "appInfo": {
            "env": {
                "clientAppId": "000000004C12AE6F",
                "clientAppType": "native",
                "clientAppVersion": app_version,
                "clientSdkVersion": "1.0.0",
            },
        },
        "dev": {
            "deviceType": device_type,
            "osName": os_name,
            "osVersion": platform.version(),
        },
    }
    return json.dumps(info, separators=(",", ":"))
