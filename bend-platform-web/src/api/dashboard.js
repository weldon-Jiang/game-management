/**
 * 仪表盘 API：首页统计卡片数据。
 */
import request from '@/utils/request'

export const dashboardApi = {
  getStats: () => request.get('/api/dashboard/stats')
}
