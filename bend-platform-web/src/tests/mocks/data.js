export const mockAgent = {
  id: 'agent-001',
  agentId: 'agent-001',
  merchantId: 'merchant-001',
  merchantName: '测试商户',
  host: '192.168.1.100',
  port: 8888,
  version: '1.0.0',
  status: 'online',
  lastHeartbeat: new Date().toISOString()
}

export const mockAgentList = [
  mockAgent,
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
]

export const mockTask = {
  id: 'task-001',
  name: '测试任务',
  type: 'template_match',
  status: 'running',
  agentId: 'agent-001',
  streamingAccountId: 'stream-001',
  gameAccountId: 'game-001',
  params: '{}',
  result: null,
  errorMessage: null,
  createdTime: new Date().toISOString(),
  updatedTime: new Date().toISOString(),
  deleted: 0
}

export const mockTaskList = [
  mockTask,
  {
    id: 'task-002',
    name: '已完成任务',
    type: 'input_sequence',
    status: 'completed',
    agentId: 'agent-001',
    streamingAccountId: 'stream-001',
    gameAccountId: 'game-001',
    params: '{}',
    result: '{"success": true}',
    errorMessage: null,
    createdTime: new Date(Date.now() - 7200000).toISOString(),
    updatedTime: new Date(Date.now() - 3600000).toISOString(),
    deleted: 0
  }
]

export const mockUser = {
  id: 'user-001',
  username: 'admin',
  role: 'admin',
  merchantId: 'merchant-001'
}

export const createMockAgent = (overrides = {}) => ({
  ...mockAgent,
  ...overrides
})

export const createMockTask = (overrides = {}) => ({
  ...mockTask,
  ...overrides
})
