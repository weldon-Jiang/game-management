/**
 * 流媒体账号 API：列表、凭据、批量导入与 Xbox 主机绑定查询。
 */
import request from '@/utils/request'

export const streamingApi = {
  list: (params) => request.get('/api/streaming-accounts', { params }),
  listAll: () => request.get('/api/streaming-accounts', { params: { pageSize: 10000 } }),
  getById: (id) => request.get(`/api/streaming-accounts/${id}`),
  getPasswordById: (id) => request.get(`/api/streaming-accounts/${id}/password`),
  create: (data) => request.post('/api/streaming-accounts', data),
  update: (id, data) => request.put(`/api/streaming-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/streaming-accounts/${id}`),
  getXboxHosts: (id) => request.get(`/api/streaming-accounts/${id}/xbox-hosts`),
  getBoundHosts: (id) => request.get(`/api/streaming-accounts/${id}/bound-hosts`),
  downloadTemplate: () => request.get('/api/streaming-accounts/template'),
  batchImport: (data) => request.post('/api/streaming-accounts/batch', data)
}
