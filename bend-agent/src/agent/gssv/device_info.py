"""Xbox xHome client device identity helpers."""

import json
import platform
from typing import Any, Dict


def build_x_ms_device_info(
    width: int = 1920,
    height: int = 1080,
    browser_version: str = "131.0.0.0",
) -> str:
    """Build the X-MS-Device-Info header expected by xHome GSSV APIs."""
    os_version = platform.version() or "10.0"
    payload: Dict[str, Any] = {
        "appInfo": {
            "env": {
                "clientAppId": "www.xbox.com",
                "clientAppType": "browser",
                "clientSdkVersion": "10.3.7",
            }
        },
        "dev": {
            "hw": {
                "make": "Microsoft",
                "model": "unknown",
                "sdktype": "web",
            },
            "os": {
                "name": "windows",
                "ver": os_version,
                "platform": "desktop",
            },
            "displayInfo": {
                "dimensions": {
                    "widthInPixels": width,
                    "heightInPixels": height,
                }
            },
            "browser": {
                "browserName": "chrome",
                "browserVersion": browser_version,
            },
        },
    }
    return json.dumps(payload, separators=(",", ":"))
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
