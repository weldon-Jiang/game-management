/**
 * 平台部署配置 API：区分总控/分控模式。
 */
import request from '@/utils/request'

export const platformApi = {
  getConfig: () => request.get('/api/platform/config')
}
