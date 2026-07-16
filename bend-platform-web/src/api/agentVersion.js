/**
 * Agent 版本 API：发布/下架、notifyAll 推送 version_update。
 */
import request from '@/utils/request'

export const agentVersionApi = {
  list: () => request.get('/api/admin/agent-versions'),
  create: (data) => request.post('/api/admin/agent-versions', data),
  update: (id, data) => request.put(`/api/admin/agent-versions/${id}`, data),
  publish: (id) => request.post(`/api/admin/agent-versions/${id}/publish`),
  unpublish: (id) => request.post(`/api/admin/agent-versions/${id}/unpublish`),
  delete: (id) => request.delete(`/api/admin/agent-versions/${id}`),
  notifyAll: (id) => request.post(`/api/admin/agent-versions/${id}/notify-all`)
}
