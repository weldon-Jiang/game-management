/**
 * 分控安装注册码 API：总控签发、列表查询与作废（仅总控可用）。
 */
import request from '@/utils/request'

export const registrationCodeApi = {
  generateInstall: (data) => request.post('/api/registration-codes/generate-install', data),
  list: (params) => request.get('/api/registration-codes/list', { params }),
  validate: (code) => request.get(`/api/registration-codes/validate/${code}`),
  check: (code) => request.get(`/api/registration-codes/check/${code}`),
  delete: (ids) => request.delete('/api/registration-codes', { data: ids })
}
