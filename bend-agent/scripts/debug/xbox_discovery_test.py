"""
Xbox 快速发现测试脚本
=====================

手动测试Xbox发现功能

使用方法：
    python -m src.agent.utils.xbox_discovery_test
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agent.xbox.xbox_discovery import XboxDiscovery
from src.agent.core.logger import get_logger


async def main():
    logger = get_logger('xbox_discovery_test')
    logger.info("=" * 60)
    logger.info("Xbox 快速发现测试")
    logger.info("=" * 60)

    discovery = XboxDiscovery()

    print("\n正在搜索局域网中的Xbox设备...")
    print("这可能需要10-30秒，请耐心等待...\n")

    xboxes = await discovery.discover()

    print("\n" + "=" * 60)
    if xboxes:
        print(f"✓ 成功发现 {len(xboxes)} 台Xbox设备:")
        print("=" * 60)
        for idx, xbox in enumerate(xboxes, 1):
            print(f"\n  Xbox #{idx}:")
            print(f"    名称: {xbox.name}")
            print(f"    IP: {xbox.ip_address}")
            print(f"    端口: {xbox.port}")
            print(f"    类型: {xbox.console_type}")
            print(f"    设备ID: {xbox.device_id}")
    else:
        print("✗ 未发现任何Xbox设备")
        print("=" * 60)
        print("\n故障排除建议:")
        print("  1. 确认Xbox已开机并连接到网络")
        print("  2. 检查Windows防火墙设置")
        print("  3. 确认Xbox和电脑在同一网段")
        print("  4. 检查路由器是否支持SSDP多播")
        print("  5. 尝试手动指定Xbox IP地址")

        print("\n运行详细诊断:")
        print("  python -m src.agent.utils.xbox_discovery_diag")

    print("\n" + "=" * 60)

    if xboxes:
        print("\n测试连接到Xbox...")
        first_xbox = xboxes[0]
        connected = await discovery.test_connection(first_xbox.ip_address, first_xbox.port)
        if connected:
            print(f"✓ 成功连接到 {first_xbox.ip_address}:{first_xbox.port}")
        else:
            print(f"✗ 无法连接到 {first_xbox.ip_address}:{first_xbox.port}")


if __name__ == "__main__":
    asyncio.run(main())
