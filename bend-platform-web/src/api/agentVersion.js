import request from '@/utils/request'

export const agentVersionApi = {
  list: () => request.get('/api/admin/agent-versions'),
  page: (params) => request.get('/api/admin/agent-versions/page', { params }),
  getById: (id) => request.get(`/api/admin/agent-versions/${id}`),
  create: (data) => request.post('/api/admin/agent-versions', data),
  update: (id, data) => request.put(`/api/admin/agent-versions/${id}`, data),
  publish: (id) => request.post(`/api/admin/agent-versions/${id}/publish`),
  unpublish: (id) => request.post(`/api/admin/agent-versions/${id}/unpublish`),
  delete: (id) => request.delete(`/api/admin/agent-versions/${id}`),
  notifyAll: (id) => request.post(`/api/admin/agent-versions/${id}/notify-all`),
  notify: (id, agentId) => request.post(`/api/admin/agent-versions/${id}/notify/${agentId}`),
  getStatistics: () => request.get('/api/admin/agent-versions/statistics')
}
