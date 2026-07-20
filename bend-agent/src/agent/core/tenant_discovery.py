"""
局域网分控发现(UDP 广播监听)

功能:
- 监听 UDP 47820,接收分控广播的 BENDTENANT|ip|port|... 数据
- Agent 启动时若 backend.base_url 为占位/连不上,调用 discover() 等待分控广播
- 拿到分控 IP 后返回 http://ip:port,由调用方回写 agent.yaml 并刷新 config
"""
import socket
import json
import os
from typing import Optional, Tuple

BROADCAST_PORT = 47820
PROTOCOL_HEADER = "BENDTENANT"


def discover(timeout: float = 8.0) -> Optional[Tuple[str, int]]:
    """
    监听 UDP 广播,等待分控出现。
    返回 (分控IP, 端口) 或 None(超时未发现)。
    """
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        sock.bind(("0.0.0.0", BROADCAST_PORT))
        sock.settimeout(timeout)
        # 最多等 timeout 秒,期间收到第一个 BENDTENANT 包即返回
        deadline_remaining = timeout
        import time
        start = time.monotonic()
        while True:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                return None
            text = data.decode("utf-8", errors="ignore")
            parts = text.split("|")
            if len(parts) >= 3 and parts[0] == PROTOCOL_HEADER:
                ip = parts[1]
                try:
                    port = int(parts[2])
                except ValueError:
                    port = 8060
                return (ip, port)
            # 收到非协议包,继续等剩余时间
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                return None
    except Exception:
        return None
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass


def is_backend_url_placeholder(url: str) -> bool:
    """判断 backend_url 是否为占位(需走发现流程)"""
    if not url:
        return True
    lower = url.lower()
    # 占位关键字:打包未填充 / 明显无效
    placeholders = ["本机分控地址", "your-server", "your-master", "example.com", "todo", "0.0.0.0"]
    return any(p in lower for p in placeholders)


def write_discovered_url(config_path: str, ip: str, port: int) -> str:
    """
    把发现的分控地址回写到 agent.yaml 的 backend.base_url / ws_url。
    简易实现:按行替换,避免引入 yaml 依赖。
    返回新的 base_url。
    """
    base_url = f"http://{ip}:{port}"
    ws_url = f"ws://{ip}:{port}/ws/agent"
    if not os.path.exists(config_path):
        return base_url
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("base_url:"):
                out.append(f'  base_url: "{base_url}"\n')
            elif stripped.startswith("ws_url:"):
                out.append(f'  ws_url: "{ws_url}"\n')
            else:
                out.append(line)
        with open(config_path, "w", encoding="utf-8") as f:
            f.writelines(out)
    except Exception:
        pass
    return base_url


def rediscover(timeout: float = 8.0) -> Optional[str]:
    """
    分控 IP 变动后,强制重新发现分控地址:
    1. UDP 监听发现分控新 IP
    2. 更新内存全局配置(立即生效,WS/HTTP 下次读取用新地址)
    3. 回写 agent.yaml(进程重启仍用新地址)
    返回新的 base_url,未发现返回 None。
    """
    found = discover(timeout=timeout)
    if not found:
        return None
    ip, port = found
    # 延迟导入避免循环依赖
    from agent.core.config import update_tenant_url_in_memory, get_loaded_config_path
    update_tenant_url_in_memory(ip, port)
    path = get_loaded_config_path()
    if path:
        write_discovered_url(path, ip, port)
    return f"http://{ip}:{port}"
