/**
 * 任务 API：CRUD、TaskControl 控制面（pause/resume/terminate/window/stream）、详情与事件。
 */
import request from '@/utils/request'

export const taskApi = {
  list: (params) => request.get('/api/tasks/page', { params }),
  getById: (id) => request.get(`/api/tasks/${id}`),
  create: (data) => request.post('/api/tasks', data),
  assign: (taskId, agentId) => request.post(`/api/tasks/${taskId}/assign/${agentId}`),
  cancel: (taskId) => request.post(`/api/tasks/${taskId}/cancel`),
  terminate: (taskId) => request.post(`/api/tasks/${taskId}/terminate`),
  retry: (taskId) => request.post(`/api/tasks/${taskId}/retry`),
  delete: (id) => request.delete(`/api/tasks/${id}`),
  pause: (taskId, data) => request.post(`/api/tasks/${taskId}/pause`, data),
  resume: (taskId) => request.post(`/api/tasks/${taskId}/resume`),
  getDetail: (taskId) => request.get(`/api/tasks/${taskId}/detail`),
  getEvents: (taskId, params = {}) =>
    request.get(`/api/tasks/${taskId}/events`, {
      params: { limit: 50, ...params }
    }),
  listSessions: (taskId) => request.get(`/api/tasks/${taskId}/sessions`),
  showWindow: (taskId) => request.post(`/api/tasks/${taskId}/window/show`),
  reconnectStream: (taskId) => request.post(`/api/tasks/${taskId}/reconnect-stream`),
  skipGameAccount: (taskId, gameAccountId) =>
    request.post(`/api/tasks/${taskId}/skip-game-account/${gameAccountId}`),
  startAutomation: (taskId, data) => request.post(`/api/tasks/${taskId}/start-automation`, data)
}
