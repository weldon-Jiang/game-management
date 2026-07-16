/**
 * 激活码 API：生成、定价预览、兑换（activate 走 merchant-subscription）。
 */
import request from '@/utils/request'

export const activationApi = {
  createCode: (data) => request.post('/api/activation-codes', data),
  listCodes: (params) => request.get('/api/activation-codes/list', { params }),
  getPrices: (params) => request.get('/api/activation-codes/prices', { params }),
  delete: (id) => request.delete(`/api/activation-codes/${id}`),
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } })
}
