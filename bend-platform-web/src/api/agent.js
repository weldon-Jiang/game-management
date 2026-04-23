import request from '@/utils/request'

export const agentApi = {
  list: (params) => request.get('/api/agents/list', { params }),
  listPage: (params) => request.get('/api/agents/list', { params }),
  getById: (agentId) => request.get(`/api/agents/${agentId}`),
  updateStatus: (id, status) => request.put(`/api/agent-instances/${id}/status`, null, { params: { status } })
}
