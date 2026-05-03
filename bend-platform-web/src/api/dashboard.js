import request from '@/utils/request'

export const dashboardApi = {
  getStats: () => request.get('/api/dashboard/stats')
}
