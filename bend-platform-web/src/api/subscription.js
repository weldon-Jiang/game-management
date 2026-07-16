/**
 * 商户订阅 API：激活码兑换、当前订阅、自动化启动前校验。
 */
import request from '@/utils/request'

export const subscriptionApi = {
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } }),
  getStatus: () => request.get('/api/merchant-subscription/status'),
  listSubscriptions: (params) => request.get('/api/merchant-subscription/list', { params }),
  cancelSubscription: (subscriptionId) => request.post(`/api/merchant-subscription/cancel/${subscriptionId}`),
  validateAutomationRequest: (data) => request.post('/api/merchant-subscription/validate-automation', data)
}
