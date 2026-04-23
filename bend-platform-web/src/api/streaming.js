import request from '@/utils/request'

export const streamingApi = {
  list: (params) => request.get('/api/streaming-accounts', { params }),
  getById: (id) => request.get(`/api/streaming-accounts/${id}`),
  create: (data) => request.post('/api/streaming-accounts', data),
  update: (id, data) => request.put(`/api/streaming-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/streaming-accounts/${id}`),
  getXboxHosts: (id) => request.get(`/api/streaming-accounts/${id}/xbox-hosts`)
}
