import request from '@/utils/request'

export const subscriptionApi = {
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } }),
  previewActivation: (code) => request.get('/api/merchant-subscription/preview', { params: { code } }),
  getStatus: () => request.get('/api/merchant-subscription/status'),
  getActivatedInfo: () => request.get('/api/merchant-subscription/activated'),
  getActiveSubscriptions: () => request.get('/api/merchant-subscription/active'),
  listSubscriptions: (params) => request.get('/api/merchant-subscription/list', { params }),
  cancelSubscription: (subscriptionId) => request.post(`/api/merchant-subscription/cancel/${subscriptionId}`),
  getSubscriptionTypes: () => request.get('/api/merchant-subscription/subscription-types'),
  validateAutomationRequest: (data) => request.post('/api/merchant-subscription/validate-automation', data)
}
