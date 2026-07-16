/**
 * Xbox 主机 API：绑定流媒体账号、LAN 发现（discover）、解锁。
 */
import request from '@/utils/request'

export const xboxApi = {
  listPage: (params) => request.get('/api/xbox-hosts/page', { params }),
  create: (data) => request.post('/api/xbox-hosts', data),
  update: (id, data) => request.put(`/api/xbox-hosts/${id}`, data),
  delete: (id) => request.delete(`/api/xbox-hosts/${id}`),
  bind: (id, streamingAccountId, gamertag) => request.put(`/api/xbox-hosts/${id}/bind`, null, { params: { streamingAccountId, gamertag } }),
  unbind: (id) => request.put(`/api/xbox-hosts/${id}/unbind`),
  discover: (agentId) => request.post('/api/xbox-hosts/discover', null, { params: { agentId } }),
  unlock: (id) => request.post(`/api/xbox-hosts/${id}/unlock`),
  dedupe: (params) => request.post('/api/xbox-hosts/dedupe', null, { params })
}
