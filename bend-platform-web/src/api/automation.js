/**
 * 自动化 API：两阶段入口 startStreaming；旧 stop 保留兼容。
 */
import request from '@/utils/request'

export const automationApi = {
  stop: (streamingAccountId) => request.post(`/api/automation/stop/${streamingAccountId}`),
  startStreaming: (streamingAccountId, data, config = {}) =>
    request.post(
      `/api/streaming-accounts/${streamingAccountId}/tasks/start-streaming`,
      data,
      { skipErrorToast: true, ...config }
    )
}
