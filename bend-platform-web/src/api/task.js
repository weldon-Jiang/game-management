import request from '@/utils/request'

export const taskApi = {
  list: (params) => request.get('/api/tasks/page', { params }),
  getById: (id) => request.get(`/api/tasks/${id}`),
  create: (data) => request.post('/api/tasks', data),
  assign: (taskId, agentId) => request.post(`/api/tasks/${taskId}/assign/${agentId}`),
  start: (taskId) => request.post(`/api/tasks/${taskId}/start`),
  complete: (taskId, result) => request.post(`/api/tasks/${taskId}/complete`, { result }),
  fail: (taskId, errorMessage) => request.post(`/api/tasks/${taskId}/fail`, { errorMessage }),
  cancel: (taskId) => request.post(`/api/tasks/${taskId}/cancel`),
  retry: (taskId) => request.post(`/api/tasks/${taskId}/retry`),
  delete: (id) => request.delete(`/api/tasks/${id}`),
  getTypes: () => request.get('/api/tasks/types'),
  getStatuses: () => request.get('/api/tasks/statuses'),
  listByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}`),
  listPendingByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}/pending`)
}
