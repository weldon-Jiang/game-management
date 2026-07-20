"""最小三端链路验证脚本(ASCII only, 避免 GBK 控制台编码问题)。"""
import asyncio
import aiohttp
import json
import websockets

TENANT = 'http://localhost:8071'
AGENT_ID = 'mini-test-agent-001'
AGENT_SECRET = 'minitestsecret001xyz'


async def main():
    print('=== 1. auto-register to tenant (no registration code) ===')
    async with aiohttp.ClientSession() as s:
        async with s.post(f'{TENANT}/api/agents/auto-register', json={
            'agentId': AGENT_ID,
            'agentSecret': AGENT_SECRET,
            'osType': 'Windows', 'osVersion': '10',
            'cpuCount': 8, 'maxConcurrentTasks': 5,
            'agentName': 'mini-test',
        }) as r:
            data = await r.json()
            print('  code=', data.get('code'), 'msg=', data.get('message'))
            if data.get('code') != 200:
                print('  [FAIL] auto-register')
                return
            print('  [OK] auto-register, merchantId=', data['data'].get('merchantId'))

    print()
    print('=== 2. WS connect to tenant (heartbeat) ===')
    ws_url = f'ws://localhost:8071/ws/agent/{AGENT_ID}?agentSecret={AGENT_SECRET}'
    try:
        async with websockets.connect(ws_url) as ws:
            print('  [OK] WS connected')
            await ws.send(json.dumps({'type': 'heartbeat', 'agentId': AGENT_ID}))
            print('  sent heartbeat')
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=8)
                print('  [OK] WS recv:', resp[:200])
            except asyncio.TimeoutError:
                print('  (no response in 8s)')
    except Exception as e:
        print(f'  [FAIL] WS: {e}')


asyncio.run(main())
