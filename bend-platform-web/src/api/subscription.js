import request from '@/utils/request'

export const subscriptionApi = {
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } }),
  getStatus: () => request.get('/api/merchant-subscription/status'),
  getVipConfigs: () => request.get('/api/merchant-subscription/vip-configs'),
  getActivatedVips: () => request.get('/api/merchant-subscription/activated')
}
