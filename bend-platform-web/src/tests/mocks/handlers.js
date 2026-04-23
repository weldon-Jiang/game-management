import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

const handlers = [
  http.get('/api/agents/list', () => {
    return HttpResponse.json({
      code: 200,
      message: 'success',
      data: {
        records: [
          {
            id: 'agent-001',
            agentId: 'agent-001',
            merchantId: 'merchant-001',
            merchantName: '测试商户',
            host: '192.168.1.100',
            port: 8888,
            version: '1.0.0',
            status: 'online',
            lastHeartbeat: new Date().toISOString()
          },
          {
            id: 'agent-002',
            agentId: 'agent-002',
            merchantId: 'merchant-001',
            merchantName: '测试商户',
            host: '192.168.1.101',
            port: 8888,
            version: '1.0.0',
            status: 'offline',
            lastHeartbeat: new Date(Date.now() - 3600000).toISOString()
          }
        ],
        total: 2,
        pageNum: 1,
        pageSize: 10
      }
    })
  }),

  http.get('/api/tasks/page', ({ request }) => {
    const url = new URL(request.url)
    const agentId = url.searchParams.get('agentId')

    const tasks = [
      {
        id: 'task-001',
        name: '测试任务',
        type: 'template_match',
        status: 'running',
        agentId: agentId || 'agent-001',
        streamingAccountId: 'stream-001',
        gameAccountId: 'game-001',
        createdTime: new Date().toISOString(),
        updatedTime: new Date().toISOString()
      },
      {
        id: 'task-002',
        name: '已完成任务',
        type: 'input_sequence',
        status: 'completed',
        agentId: agentId || 'agent-001',
        streamingAccountId: 'stream-001',
        gameAccountId: 'game-001',
        result: '{"success": true}',
        createdTime: new Date(Date.now() - 7200000).toISOString(),
        updatedTime: new Date(Date.now() - 3600000).toISOString()
      }
    ]

    return HttpResponse.json({
      code: 200,
      message: 'success',
      data: {
        records: agentId ? tasks.filter(t => t.agentId === agentId) : tasks,
        total: 2,
        pageNum: 1,
        pageSize: 10
      }
    })
  }),

  http.post('/api/auth/login', async ({ request }) => {
    const body = await request.json()

    if (body.username === 'admin' && body.password === 'password') {
      return HttpResponse.json({
        code: 200,
        message: '登录成功',
        data: {
          token: 'mock-jwt-token',
          user: {
            id: 'user-001',
            username: 'admin',
            role: 'admin'
          }
        }
      })
    }

    return HttpResponse.json({
      code: 401,
      message: '用户名或密码错误'
    }, { status: 401 })
  }),

  http.get('/api/auth/me', () => {
    return HttpResponse.json({
      code: 200,
      message: 'success',
      data: {
        id: 'user-001',
        username: 'admin',
        role: 'admin'
      }
    })
  })
]

export const server = setupServer(...handlers)
