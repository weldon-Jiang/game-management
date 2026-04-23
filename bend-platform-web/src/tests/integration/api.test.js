import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { server } from '../mocks/server.js'
import { http, HttpResponse } from 'msw'

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' })
})

afterAll(() => {
  server.close()
})

afterEach(() => {
  server.resetHandlers()
})

describe('Agent API 模块', () => {
  const { agentApi } = await import('@/api/agent')

  it('应该成功获取 Agent 列表', async () => {
    const res = await agentApi.list({ pageNum: 1, pageSize: 10 })
    expect(res.code).toBe(200)
    expect(res.data).toHaveProperty('records')
    expect(Array.isArray(res.data.records)).toBe(true)
    expect(res.data.records.length).toBeGreaterThan(0)
  })

  it('Agent 记录应该包含必要字段', async () => {
    const res = await agentApi.list({ pageNum: 1, pageSize: 10 })
    const agent = res.data.records[0]

    expect(agent).toHaveProperty('agentId')
    expect(agent).toHaveProperty('status')
    expect(agent).toHaveProperty('host')
    expect(agent).toHaveProperty('port')
    expect(agent).toHaveProperty('version')
  })

  it('应该支持状态筛选', async () => {
    const res = await agentApi.list({ pageNum: 1, pageSize: 10, status: 'online' })
    expect(res.code).toBe(200)
    res.data.records.forEach(agent => {
      expect(agent.status).toBe('online')
    })
  })
})

describe('Task API 模块', () => {
  const { taskApi } = await import('@/api/task')

  it('应该成功获取任务列表', async () => {
    const res = await taskApi.list({ pageNum: 1, pageSize: 10 })
    expect(res.code).toBe(200)
    expect(res.data).toHaveProperty('records')
    expect(Array.isArray(res.data.records)).toBe(true)
  })

  it('任务记录应该包含必要字段', async () => {
    const res = await taskApi.list({ pageNum: 1, pageSize: 10 })
    const task = res.data.records[0]

    expect(task).toHaveProperty('id')
    expect(task).toHaveProperty('name')
    expect(task).toHaveProperty('type')
    expect(task).toHaveProperty('status')
    expect(task).toHaveProperty('createdTime')
  })

  it('应该支持按 Agent ID 筛选任务', async () => {
    const res = await taskApi.listByAgent('agent-001')
    expect(res.code).toBe(200)
    expect(Array.isArray(res.data.records)).toBe(true)
  })

  it('应该支持获取待处理任务', async () => {
    const res = await taskApi.listPendingByAgent('agent-001')
    expect(res.code).toBe(200)
    expect(Array.isArray(res.data.records)).toBe(true)
  })
})

describe('Auth API 模块', () => {
  const { authApi } = await import('@/api/auth')

  it('应该成功登录', async () => {
    const res = await authApi.login({
      username: 'admin',
      password: 'password'
    })
    expect(res.code).toBe(200)
    expect(res.data).toHaveProperty('token')
    expect(res.data).toHaveProperty('user')
  })

  it('错误的凭据应该返回 401', async () => {
    const res = await authApi.login({
      username: 'wrong',
      password: 'wrong'
    })
    expect(res.code).toBe(401)
  })

  it('应该成功获取当前用户信息', async () => {
    const res = await authApi.getCurrentUser()
    expect(res.code).toBe(200)
    expect(res.data).toHaveProperty('username')
    expect(res.data).toHaveProperty('role')
  })
})
