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
  terminate: (taskId) => request.post(`/api/tasks/${taskId}/terminate`),
  retry: (taskId) => request.post(`/api/tasks/${taskId}/retry`),
  delete: (id) => request.delete(`/api/tasks/${id}`),
  getTypes: () => request.get('/api/tasks/types'),
  getStatuses: () => request.get('/api/tasks/statuses'),
  listByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}`),
  listPendingByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}/pending`),
  pause: (taskId, data) => request.post(`/api/tasks/${taskId}/pause`, data),
  resume: (taskId) => request.post(`/api/tasks/${taskId}/resume`),
  stop: (taskId) => request.post(`/api/tasks/${taskId}/stop`),
  getDetail: (taskId) => request.get(`/api/tasks/${taskId}/detail`),
  getEvents: (taskId, params = {}) =>
    request.get(`/api/tasks/${taskId}/events`, {
      params: { limit: 50, ...params }
    }),
  listSessions: (taskId) => request.get(`/api/tasks/${taskId}/sessions`),
  getGameAccountStatus: (taskId) => request.get(`/api/tasks/${taskId}/game-account-status`),
  showWindow: (taskId) => request.post(`/api/tasks/${taskId}/window/show`),
  hideWindow: (taskId) => request.post(`/api/tasks/${taskId}/window/hide`),
  focusWindow: (taskId) => request.post(`/api/tasks/${taskId}/window/focus`),
  reconnectStream: (taskId) => request.post(`/api/tasks/${taskId}/reconnect-stream`),
  skipGameAccount: (taskId, gameAccountId) =>
    request.post(`/api/tasks/${taskId}/skip-game-account/${gameAccountId}`),
  startAutomation: (taskId, data) => request.post(`/api/tasks/${taskId}/start-automation`, data),
  getActiveByAgent: (agentId) => request.get(`/api/agents/${agentId}/active-tasks`)
}
