/**
 * 系统监控 API：概览指标与趋势时序（SystemMonitoring 页）。
 */
import request from '@/utils/request'

export const monitoringApi = {
  getOverview: () => request.get('/api/monitoring/overview'),
  getTrend: (params) => request.get('/api/monitoring/metrics/trend', { params })
}
