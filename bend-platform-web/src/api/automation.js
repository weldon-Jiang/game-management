import request from '@/utils/request'

export const automationApi = {
  start: (data) => request.post('/api/automation/start', data),
  stop: (streamingAccountId) => request.post(`/api/automation/stop/${streamingAccountId}`),
  getStatus: (streamingAccountId) => request.get(`/api/automation/status/${streamingAccountId}`)
}
