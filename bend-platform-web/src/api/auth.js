import request from '@/utils/request'

export const authApi = {
  login: (data) => request.post('/api/auth/login', data),
  register: (data) => request.post('/api/auth/register', data),
  getCurrentUser: () => request.get('/api/auth/me'),
  refresh: () => request.post('/api/auth/refresh')
}
