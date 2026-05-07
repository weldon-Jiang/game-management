import request from '@/utils/request'

export const subscriptionApi = {
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } }),
  previewActivation: (code) => request.get('/api/merchant-subscription/preview', { params: { code } }),
  getStatus: () => request.get('/api/merchant-subscription/status'),
  getActivatedInfo: () => request.get('/api/merchant-subscription/activated')
}
