import request from '@/utils/request'

export const vipApi = {
  list: () => request.get('/api/vip-configs'),
  listPage: (params) => request.get('/api/vip-configs/page', { params }),
  getById: (id) => request.get(`/api/vip-configs/${id}`),
  create: (data) => request.post('/api/vip-configs', data),
  update: (id, data) => request.put(`/api/vip-configs/${id}`, data),
  updateStatus: (id, status) => request.put(`/api/vip-configs/${id}/status`, null, { params: { status } }),
  delete: (id) => request.delete(`/api/vip-configs/${id}`)
}
