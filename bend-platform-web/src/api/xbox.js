import request from '@/utils/request'

export const xboxApi = {
  list: () => request.get('/api/xbox-hosts'),
  listPage: (params) => request.get('/api/xbox-hosts/page', { params }),
  getById: (id) => request.get(`/api/xbox-hosts/${id}`),
  create: (data) => request.post('/api/xbox-hosts', data),
  update: (id, data) => request.put(`/api/xbox-hosts/${id}`, data),
  delete: (id) => request.delete(`/api/xbox-hosts/${id}`),
  bind: (id, streamingAccountId, gamertag) => request.put(`/api/xbox-hosts/${id}/bind`, null, { params: { streamingAccountId, gamertag } }),
  unbind: (id) => request.put(`/api/xbox-hosts/${id}/unbind`),
  getAvailableAccounts: (id) => request.get(`/api/xbox-hosts/${id}/available-streaming-accounts`)
}
