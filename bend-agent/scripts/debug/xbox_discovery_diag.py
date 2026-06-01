"""
Xbox Discovery 诊断工具
====================

用于诊断Xbox发现失败的原因

使用方法：
    python -m src.agent.utils.xbox_discovery_diag
"""
import asyncio
import socket
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agent.core.logger import get_logger


async def diagnose_local_network():
    """诊断本地网络配置"""
    logger = get_logger('xbox_diag')
    logger.info("=== 本地网络诊断 ===")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            logger.info(f"本机IP地址: {local_ip}")

        network_prefix = '.'.join(local_ip.split('.')[:3])
        logger.info(f"扫描网段: {network_prefix}.0/24")

        return local_ip, network_prefix

    except Exception as e:
        logger.error(f"获取本地IP失败: {e}")
        return None, None


async def diagnose_ssdp():
    """诊断SSDP发现"""
    logger = get_logger('xbox_diag')
    logger.info("\n=== SSDP 诊断 ===")

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

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
        sock.settimeout(5)

        request = XBOX_SEARCH_REQUEST.format(host=SSDP_MULTICAST_ADDR, port=SSDP_PORT)
        sock.sendto(request.encode(), (SSDP_MULTICAST_ADDR, SSDP_PORT))
        logger.info(f"已发送SSDP搜索请求到 {SSDP_MULTICAST_ADDR}:{SSDP_PORT}")

        responses = []
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                response = data.decode('utf-8', errors='ignore')
                responses.append((addr[0], response))
                logger.info(f"收到来自 {addr[0]} 的响应:")
                logger.info(f"  {response[:200]}...")
            except socket.timeout:
                break

        sock.close()

        if responses:
            logger.info(f"SSDP发现成功: 收到 {len(responses)} 个响应")
            for ip, resp in responses:
                if 'xbox' in resp.lower() or 'microsoft' in resp.lower():
                    logger.info(f"  ✓ 发现Xbox设备: {ip}")
                else:
                    logger.info(f"  ? 未知设备: {ip}")
        else:
            logger.warning("SSDP未收到任何响应")

        return responses

    except Exception as e:
        logger.error(f"SSDP诊断失败: {e}")
        return []


async def diagnose_ports(network_prefix: str):
    """诊断Xbox常用端口"""
    logger = get_logger('xbox_diag')
    logger.info("\n=== 端口扫描诊断 ===")

    ports_to_test = [
        (5050, "SmartGlass"),
        (3074, "Xbox Live"),
        (5000, "SSDP/UPnP"),
        (53, "DNS"),
        (80, "HTTP"),
        (8080, "HTTP Alt"),
    ]

    async def test_port(ip: str, port: int, desc: str):
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return (ip, port, desc, True, None)
        except asyncio.TimeoutError:
            return (ip, port, desc, False, "timeout")
        except ConnectionRefusedError:
            return (ip, port, desc, False, "refused")
        except Exception as e:
            return (ip, port, desc, False, str(e))

    test_ips = [f"{network_prefix}.1", f"{network_prefix}.254", f"{network_prefix}.100", f"{network_prefix}.200"]

    for ip in test_ips:
        logger.info(f"\n扫描 {ip}...")
        tasks = [test_port(ip, port, desc) for port, desc in ports_to_test]
        results = await asyncio.gather(*tasks)

        for ip_addr, port, desc, success, error in results:
            if success:
                logger.info(f"  ✓ {port}/{desc}: 开放")
            elif port in [5050, 3074, 5000]:
                logger.warning(f"  ✗ {port}/{desc}: {error}")


async def diagnose_direct_connect(ip: str):
    """直接连接测试"""
    logger = get_logger('xbox_diag')
    logger.info(f"\n=== 直接连接测试 {ip} ===")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, 5050),
            timeout=5
        )
        logger.info(f"✓ 成功连接到 {ip}:5050 (SmartGlass)")
        writer.close()
        await writer.wait_closed()
        return True
    except asyncio.TimeoutError:
        logger.warning(f"✗ 连接 {ip}:5050 超时")
    except ConnectionRefusedError:
        logger.warning(f"✗ 连接 {ip}:5050 被拒绝")
    except Exception as e:
        logger.warning(f"✗ 连接 {ip}:5050 失败: {e}")

    return False


async def diagnose_firewall():
    """检查防火墙状态"""
    logger = get_logger('xbox_diag')
    logger.info("\n=== 防火墙检查 ===")

    try:
        import subprocess
        result = subprocess.run(
            ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if 'Block' in result.stdout or 'Enable' in result.stdout:
            logger.info("Windows防火墙状态: 已启用")
            logger.info("建议检查以下端口是否被阻止:")
            logger.info("  - UDP 1900 (SSDP)")
            logger.info("  - TCP 5050 (SmartGlass)")
            logger.info("  - TCP 3074 (Xbox Live)")
        else:
            logger.info("Windows防火墙状态: 已禁用或配置未知")

    except Exception as e:
        logger.warning(f"无法检查防火墙状态: {e}")


async def main():
    logger = get_logger('xbox_diag')
    logger.info("=" * 50)
    logger.info("Xbox Discovery 诊断工具")
    logger.info("=" * 50)

    local_ip, network_prefix = await diagnose_local_network()
    if not local_ip:
        logger.error("无法获取本地网络信息，诊断终止")
        return

    await diagnose_ssdp()
    await diagnose_ports(network_prefix)

    logger.info("\n" + "=" * 50)
    logger.info("诊断建议:")
    logger.info("=" * 50)
    logger.info("1. 如果SSDP无响应但端口开放:")
    logger.info("   - 检查Windows防火墙设置")
    logger.info("   - 检查路由器SSDP多播配置")
    logger.info("")
    logger.info("2. 如果端口未开放:")
    logger.info("   - 确认Xbox IP地址")
    logger.info("   - 检查Xbox网络设置")
    logger.info("   - 确保Xbox和电脑在同一网络")
    logger.info("")
    logger.info("3. 手动指定Xbox IP地址测试:")
    logger.info("   请输入Xbox IP地址进行直接连接测试")

    try:
        test_ip = input("\n输入Xbox IP地址进行测试 (直接回车跳过): ").strip()
        if test_ip:
            await diagnose_direct_connect(test_ip)
    except EOFError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
