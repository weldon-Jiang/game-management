/**
 * 自动化 API：两阶段入口 startStreaming + startAutomation；旧 start/stop 保留兼容。
 */
import request from '@/utils/request'

export const automationApi = {
  start: (data) => request.post('/api/automation/start', data),
  stop: (streamingAccountId) => request.post(`/api/automation/stop/${streamingAccountId}`),
  getStatus: (streamingAccountId) => request.get(`/api/automation/status/${streamingAccountId}`),
  startStreaming: (streamingAccountId, data, config = {}) =>
    request.post(
      `/api/streaming-accounts/${streamingAccountId}/tasks/start-streaming`,
      data,
      { skipErrorToast: true, ...config }
    ),
  startAutomation: (taskId, data) =>
    request.post(`/api/tasks/${taskId}/start-automation`, data)
}
