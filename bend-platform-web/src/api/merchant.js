/**
 * 商户 API：平台管理员 CRUD 与状态切换。
 */
import request from '@/utils/request'

export const merchantApi = {
  list: (params) => request.get('/api/merchants', { params }),
  listAll: () => request.get('/api/merchants/all'),
  getById: (id) => request.get(`/api/merchants/${id}`),
  create: (data) => request.post('/api/merchants', data),
  update: (id, data) => request.put(`/api/merchants/${id}`, data),
  updateStatus: (id, status) => request.put(`/api/merchants/${id}/status`, null, { params: { status } }),
  delete: (id) => request.delete(`/api/merchants/${id}`)
}
