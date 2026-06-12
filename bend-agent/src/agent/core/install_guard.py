"""
Agent 单机安装校验。

每台电脑只允许存在一个 Agent 安装目录；换目录重装需先卸载并清理注册表。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .logger import get_logger
from .machine_identity import machine_identity
from .paths import get_agent_root

logger = get_logger("install_guard")

WINDOWS_SERVICE_NAME = "BendAgent"
SKIP_ENV_VAR = "BEND_AGENT_SKIP_INSTALL_GUARD"


class InstallGuardError(Exception):
    """本机已存在 Agent 安装或残留注册表时抛出。"""


def normalize_install_path(path: os.PathLike[str] | str) -> str:
    """统一安装路径格式，便于跨盘符/大小写比较。"""
    try:
        return str(Path(path).resolve()).rstrip("\\/").casefold()
    except OSError:
        return str(path).rstrip("\\/").casefold()


def get_current_install_root() -> Path:
    """当前 Agent 安装根目录（exe 或 bend-agent 项目根）。"""
    return get_agent_root()


def should_skip_install_guard() -> bool:
    """测试或排障时可设置 BEND_AGENT_SKIP_INSTALL_GUARD=1 跳过校验。"""
    return os.environ.get(SKIP_ENV_VAR) == "1"


def check_existing_installation(current_root: Optional[Path] = None) -> Optional[str]:
    """
    检查本机是否已有其他路径的 Agent 安装。

    返回:
        None 表示允许继续；否则为面向用户的错误说明。
    """
    if should_skip_install_guard():
        return None

    root = current_root or get_current_install_root()
    current_norm = normalize_install_path(root)
    registered = machine_identity.get_install_path()
    if not registered:
        return _check_conflicting_windows_service(current_norm)

    registered_norm = normalize_install_path(registered)
    if current_norm == registered_norm:
        return None

    registered_path = Path(registered)
    if not registered_path.exists():
        return (
            "检测到本机存在 Agent 安装记录，但原安装目录已不存在：\n"
            f"  {registered}\n\n"
            "请先运行 uninstall_agent.ps1（或 BendAgent.exe --uninstall）清理后再安装。"
        )

    return (
        "本机已安装 Bend Agent，每台电脑只能安装一个实例。\n"
        f"现有安装路径：{registered}\n\n"
        "如需换目录重装，请先运行 uninstall_agent.ps1（或 BendAgent.exe --uninstall）完成卸载。"
    )


def assert_single_install(current_root: Optional[Path] = None) -> None:
    """校验通过则静默返回；否则抛出 InstallGuardError。"""
    message = check_existing_installation(current_root)
    if message:
        logger.error("Install guard rejected startup: %s", message.replace("\n", " "))
        raise InstallGuardError(message)


def migrate_install_marker_if_needed(has_credentials: bool) -> None:
    """
    兼容旧版本：已激活但未写入 InstallPath 时，补写当前目录标记。
    """
    if not has_credentials or machine_identity.get_install_path():
        return
    install_root = str(get_current_install_root())
    if machine_identity.mark_installed(install_root):
        logger.info("Migrated install marker to %s", install_root)


def _check_conflicting_windows_service(current_norm: str) -> Optional[str]:
    """无注册表记录时，检查是否已有指向其他目录的 Windows 服务。"""
    if sys.platform != "win32":
        return None

    try:
        import subprocess

        result = subprocess.run(
            ["sc.exe", "qc", WINDOWS_SERVICE_NAME],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return None

        service_dir = _parse_service_app_directory(result.stdout)
        if not service_dir:
            return None

        service_norm = normalize_install_path(service_dir)
        if service_norm == current_norm:
            return None

        return (
            "本机已安装 Bend Agent Windows 服务，每台电脑只能安装一个实例。\n"
            f"服务安装目录：{service_dir}\n\n"
            "如需换目录重装，请先运行 uninstall_agent.ps1 完成卸载。"
        )
    except Exception as exc:
        logger.warning("Failed to inspect BendAgent Windows service: %s", exc)
        return None


def _parse_service_app_directory(sc_qc_output: str) -> Optional[str]:
    """从 sc qc 输出解析 BINARY_PATH_NAME 所在目录。"""
    binary_path = None
    for line in sc_qc_output.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("BINARY_PATH_NAME"):
            parts = stripped.split(":", 1)
            if len(parts) == 2:
                binary_path = parts[1].strip().strip('"')
                break

    if not binary_path:
        return None

    # NSSM 等服务包装器：取最后一个参数中的脚本/exe 路径
    tokens = binary_path.split()
    candidate = tokens[-1] if tokens else binary_path
    if candidate.lower().endswith(".exe") or candidate.lower().endswith(".py"):
        return str(Path(candidate).parent)
    return str(Path(candidate).parent)
