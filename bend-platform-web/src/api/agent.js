/**
 * Agent 实例 API：分页、在线状态、重命名与清理/批量删除。
 */
import request from '@/utils/request'

export const agentApi = {
  list: (params) => request.get('/api/agents/page', { params }),
  listPage: (params) => request.get('/api/agents/page', { params }),
  listOnline: () => request.get('/api/agents/online'),
  getById: (agentId) => request.get(`/api/agents/${agentId}`),
  updateName: (agentId, data) => request.put(`/api/agents/${agentId}/name`, data),
  updateStatus: (id, status) => request.put(`/api/agent-instances/${id}/status`, null, { params: { status } }),
  delete: (agentId) => request.delete(`/api/agents/${agentId}`),
  batchDelete: (agentIds) => request.delete('/api/agents/batch', { data: agentIds }),
  cleanupUninstalled: () => request.delete('/api/agents/cleanup/uninstalled'),
  cleanupOffline: (offlineMinutes) => request.delete('/api/agents/cleanup/offline', { params: { offlineMinutes } })
}
