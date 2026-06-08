/**
 * 认证 API：登录、注册、当前用户与 JWT 刷新。
 */
import request from '@/utils/request'

export const authApi = {
  login: (data) => request.post('/api/auth/login', data),
  register: (data) => request.post('/api/auth/register', data),
  getCurrentUser: () => request.get('/api/auth/me'),
  refresh: () => request.post('/api/auth/refresh')
}
