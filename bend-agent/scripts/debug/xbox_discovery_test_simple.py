"""
Xbox 快速发现测试脚本（无日志版本）
====================================

手动测试Xbox发现功能，不依赖日志文件

使用方法：
    cd d:\auto-xbox\team-management\bend-agent
    python -m src.agent.utils.xbox_discovery_test_simple
"""
import asyncio
import socket
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


async def test_ssdp():
    """测试SSDP发现"""
    print("\n1. 测试 SSDP 发现...")
    print("   - 发送 SSDP M-SEARCH 请求到 239.255.255.250:1900")

    SSDP_MULTICAST_ADDR = "239.255.255.250"
    SSDP_PORT = 1900

    XBOX_SEARCH_REQUEST = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: {host}:{port}\r\n"
        "MAN: \"ssdp:discover\"\r\n"
        "MX: 3\r\n"
        "ST: urn:schemas-xbox-com:device:Xbox\r\n"
        "\r\n"
    )

    devices = []

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.settimeout(5)

        request = XBOX_SEARCH_REQUEST.format(host=SSDP_MULTICAST_ADDR, port=SSDP_PORT)
        sock.sendto(request.encode(), (SSDP_MULTICAST_ADDR, SSDP_PORT))
        print(f"   ✓ 已发送 SSDP 请求")

        try:
            data, addr = sock.recvfrom(4096)
            response = data.decode('utf-8', errors='ignore')
            devices.append((addr[0], response))
            print(f"   ✓ 收到来自 {addr[0]} 的响应")
        except socket.timeout:
            print("   ✗ SSDP 未收到任何响应")

        sock.close()

    except Exception as e:
        print(f"   ✗ SSDP 测试失败: {e}")

    return devices


async def test_network_scan():
    """测试网络扫描"""
    print("\n2. 测试网络端口扫描...")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]

        network_prefix = '.'.join(local_ip.split('.')[:3])
        print(f"   - 本机IP: {local_ip}")
        print(f"   - 扫描网段: {network_prefix}.0/24")

        ports = [5050, 3074, 5000]
        found_ips = []

        async def scan_port(ip, port):
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=1
                )
                writer.close()
                await writer.wait_closed()
                return (ip, port, True)
            except:
                return (ip, port, False)

        tasks = []
        for i in range(1, 255):
            ip = f"{network_prefix}.{i}"
            for port in ports:
                tasks.append(scan_port(ip, port))

        print(f"   - 开始扫描 {len(tasks)} 个端口...")
        results = await asyncio.gather(*tasks)

        for ip, port, success in results:
            if success and ip not in found_ips:
                found_ips.append(ip)
                print(f"   ✓ 发现开放端口: {ip}:{port}")

        if not found_ips:
            print("   ✗ 未发现任何开放端口")

        return found_ips

    except Exception as e:
        print(f"   ✗ 网络扫描失败: {e}")
        return []


async def test_direct_connect(ip):
    """测试直接连接"""
    print(f"\n3. 测试直接连接到 {ip}:5050...")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 5050),
            timeout=5
        )
        print(f"   ✓ 成功连接到 {ip}:5050")
        writer.close()
        await writer.wait_closed()
        return True
    except asyncio.TimeoutError:
        print(f"   ✗ 连接超时")
        return False
    except ConnectionRefusedError:
        print(f"   ✗ 连接被拒绝")
        return False
    except Exception as e:
        print(f"   ✗ 连接失败: {e}")
        return False


async def get_local_ip():
    """获取本机IP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return None


async def main():
    print("=" * 70)
    print("Xbox 发现测试工具")
    print("=" * 70)

    local_ip = await get_local_ip()
    if local_ip:
        print(f"\n本机 IP 地址: {local_ip}")
    else:
        print("\n✗ 无法获取本机 IP 地址")
        return

    print("\n开始测试，请耐心等待...\n")

    ssdp_devices = await test_ssdp()
    network_devices = await test_network_scan()

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    print(f"\nSSDP 发现: {len(ssdp_devices)} 个设备")
    for ip, resp in ssdp_devices:
        print(f"  - {ip}")

    print(f"\n网络扫描: {len(network_devices)} 个设备")
    for ip in network_devices:
        print(f"  - {ip}")

    if network_devices:
        print(f"\n测试连接到第一个发现的设备: {network_devices[0]}")
        await test_direct_connect(network_devices[0])

    print("\n" + "=" * 70)

    if not ssdp_devices and not network_devices:
        print("\n❌ 未发现任何 Xbox 设备")
        print("\n故障排除建议:")
        print("  1. 确认 Xbox 已开机并连接到网络")
        print("  2. 检查 Windows 防火墙设置")
        print("  3. 确认 Xbox 和电脑在同一网段")
        print("  4. 检查路由器是否支持 SSDP 多播")
        print("  5. 手动在 Xbox 上查看 IP 地址并测试")

        manual_ip = input("\n请输入 Xbox IP 地址进行直接测试（直接回车跳过）: ").strip()
        if manual_ip:
            await test_direct_connect(manual_ip)
    else:
        print("\n✅ 发现设备！请尝试使用第一个 IP 地址进行任务测试。")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
