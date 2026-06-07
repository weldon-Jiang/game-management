import request from '@/utils/request'

export const monitoringApi = {
  getOverview: () => request.get('/api/monitoring/overview'),
  getTrend: (params) => request.get('/api/monitoring/metrics/trend', { params })
}
