"""简单端口测试"""
import asyncio
import sys
import os

async def test_port(host, port, timeout=2):
    """测试单个端口"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except asyncio.TimeoutError:
        return None
    except ConnectionRefusedError:
        return False
    except Exception as e:
        return False

async def main():
    host = "192.168.0.100"
    ports = [5050, 3074, 5000, 80, 443]

    print(f"测试连接到 {host} 的常用端口...")
    print("=" * 60)

    for port in ports:
        result = await test_port(host, port)
        if result is True:
            status = "✓ 开放"
        elif result is False:
            status = "✗ 被拒绝"
        else:
            status = "✗ 超时"

        print(f"端口 {port:5d}: {status}")

    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
