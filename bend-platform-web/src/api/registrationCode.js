/**
 * Agent 注册码 API：平台批量生成、校验与作废。
 */
import request from '@/utils/request'

export const registrationCodeApi = {
  generate: (data) => request.post('/api/registration-codes/generate', data),
  list: (params) => request.get('/api/registration-codes/list', { params }),
  validate: (code) => request.get(`/api/registration-codes/validate/${code}`),
  check: (code) => request.get(`/api/registration-codes/check/${code}`),
  delete: (ids) => request.delete('/api/registration-codes', { data: ids })
}
