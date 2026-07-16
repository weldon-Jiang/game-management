/**
 * 流媒体账号 API：列表、凭据、批量导入与 Xbox 主机绑定查询。
 */
import request from '@/utils/request'

export const streamingApi = {
  list: (params) => request.get('/api/streaming-accounts', { params }),
  getById: (id) => request.get(`/api/streaming-accounts/${id}`),
  getPasswordById: (id) => request.get(`/api/streaming-accounts/${id}/password`),
  create: (data) => request.post('/api/streaming-accounts', data),
  update: (id, data) => request.put(`/api/streaming-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/streaming-accounts/${id}`),
  getBoundHosts: (id) => request.get(`/api/streaming-accounts/${id}/bound-hosts`),
  bindHost: (accountId, hostId, gamertag) =>
    request.put(`/api/streaming-accounts/${accountId}/bound-hosts/${hostId}`, null, {
      params: gamertag ? { gamertag } : {}
    }),
  unbindHost: (accountId, hostId) =>
    request.delete(`/api/streaming-accounts/${accountId}/bound-hosts/${hostId}`),
  downloadTemplate: () => request.get('/api/streaming-accounts/template'),
  batchImport: (data) => request.post('/api/streaming-accounts/batch', data)
}
