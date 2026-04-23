import request from '@/utils/request'

export const userApi = {
  list: (params) => request.get('/api/users', { params }),
  getById: (id) => request.get(`/api/users/${id}`),
  create: (data) => request.post('/api/users', data),
  update: (id, data) => request.put(`/api/users/${id}`, null, { params: data }),
  resetPassword: (id, newPassword) => request.put(`/api/users/${id}/password`, null, { params: { newPassword } }),
  delete: (id) => request.delete(`/api/users/${id}`)
}
