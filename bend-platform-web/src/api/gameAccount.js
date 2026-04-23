import request from '@/utils/request'

export const gameAccountApi = {
  list: (params) => request.get('/api/game-accounts', { params }),
  getById: (id) => request.get(`/api/game-accounts/${id}`),
  create: (data) => request.post('/api/game-accounts', data),
  update: (id, data) => request.put(`/api/game-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/game-accounts/${id}`)
}
