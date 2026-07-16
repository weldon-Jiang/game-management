/**
 * 计费 API：点数余额与 VIP 分组。
 */
import request from '@/utils/request'

export const billingApi = {
  getBalance: () => request.get('/api/billing/balance')
}

export const merchantGroupApi = {
  listAll: () => request.get('/api/merchant-groups'),
  getById: (id) => request.get(`/api/merchant-groups/${id}`),
  getByMerchantId: (merchantId) => request.get(`/api/merchant-groups/by-merchant/${merchantId}`),
  create: (data) => request.post('/api/merchant-groups', data),
  update: (id, data) => request.put(`/api/merchant-groups/${id}`, data),
  delete: (id) => request.delete(`/api/merchant-groups/${id}`)
}
