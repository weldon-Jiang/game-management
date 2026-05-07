import request from '@/utils/request'

export const vipApi = {
  getMyInfo: () => request.get('/api/vip/my-info'),
  getMyLevels: () => request.get('/api/vip/my-levels'),
  getInfo: (merchantId) => request.get(`/api/vip/info/${merchantId}`),
  getLevels: () => request.get('/api/vip/levels')
}
