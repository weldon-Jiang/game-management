import request from '@/utils/request'

export const authApi = {
  login: (data) => request.post('/api/auth/login', data),
  register: (data) => request.post('/api/auth/register', data),
  getCurrentUser: () => request.get('/api/auth/me')
}

export const merchantApi = {
  list: (params) => request.get('/api/merchants', { params }),
  listAll: () => request.get('/api/merchants/all'),
  getById: (id) => request.get(`/api/merchants/${id}`),
  create: (data) => request.post('/api/merchants', null, { params: data }),
  updateStatus: (id, status) => request.put(`/api/merchants/${id}/status`, null, { params: { status } }),
  delete: (id) => request.delete(`/api/merchants/${id}`)
}

export const userApi = {
  list: (params) => request.get('/api/users', { params }),
  getById: (id) => request.get(`/api/users/${id}`),
  create: (data) => request.post('/api/users', data),
  update: (id, data) => request.put(`/api/users/${id}`, null, { params: data }),
  resetPassword: (id, newPassword) => request.put(`/api/users/${id}/password`, null, { params: { newPassword } }),
  delete: (id) => request.delete(`/api/users/${id}`)
}

export const streamingApi = {
  list: (params) => request.get('/api/streaming-accounts', { params }),
  getById: (id) => request.get(`/api/streaming-accounts/${id}`),
  create: (data) => request.post('/api/streaming-accounts', data),
  update: (id, data) => request.put(`/api/streaming-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/streaming-accounts/${id}`),
  getXboxHosts: (id) => request.get(`/api/streaming-accounts/${id}/xbox-hosts`)
}

export const automationApi = {
  start: (data) => request.post('/api/automation/start', data),
  stop: (streamingAccountId) => request.post(`/api/automation/stop/${streamingAccountId}`),
  getStatus: (streamingAccountId) => request.get(`/api/automation/status/${streamingAccountId}`)
}

export const xboxApi = {
  list: () => request.get('/api/xbox-hosts'),
  listPage: (params) => request.get('/api/xbox-hosts/page', { params }),
  getById: (id) => request.get(`/api/xbox-hosts/${id}`),
  create: (data) => request.post('/api/xbox-hosts', data),
  update: (id, data) => request.put(`/api/xbox-hosts/${id}`, data),
  delete: (id) => request.delete(`/api/xbox-hosts/${id}`),
  bind: (id, streamingAccountId, gamertag) => request.put(`/api/xbox-hosts/${id}/bind`, null, { params: { streamingAccountId, gamertag } }),
  unbind: (id) => request.put(`/api/xbox-hosts/${id}/unbind`),
  getAvailableAccounts: (id) => request.get(`/api/xbox-hosts/${id}/available-streaming-accounts`)
}

export const vipApi = {
  list: () => request.get('/api/vip-configs'),
  listPage: (params) => request.get('/api/vip-configs/page', { params }),
  getById: (id) => request.get(`/api/vip-configs/${id}`),
  create: (data) => request.post('/api/vip-configs', data),
  update: (id, data) => request.put(`/api/vip-configs/${id}`, data),
  updateStatus: (id, status) => request.put(`/api/vip-configs/${id}/status`, null, { params: { status } }),
  delete: (id) => request.delete(`/api/vip-configs/${id}`)
}

export const activationApi = {
  generateSingle: (data) => request.post('/api/activation-codes/single', data),
  listCodes: (params) => request.get('/api/activation-codes/list', { params }),
  generateBatch: (data) => request.post('/api/activation-codes/batch', data),
  listBatches: () => request.get('/api/activation-codes/batches'),
  listBatchesPage: (params) => request.get('/api/activation-codes/batches/page', { params }),
  getBatch: (batchId) => request.get(`/api/activation-codes/batch/${batchId}`),
  getCodes: (batchId, params) => request.get(`/api/activation-codes/batch/${batchId}/codes`, { params }),
  use: (code) => request.post('/api/activation-codes/use', null, { params: { code } }),
  deleteBatch: (ids) => request.delete('/api/activation-codes', { data: ids })
}

export const subscriptionApi = {
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } }),
  getStatus: () => request.get('/api/merchant-subscription/status'),
  getVipConfigs: () => request.get('/api/merchant-subscription/vip-configs'),
  getActivatedVips: () => request.get('/api/merchant-subscription/activated')
}

export const agentApi = {
  list: (params) => request.get('/api/agents/list', { params }),
  listPage: (params) => request.get('/api/agents/list', { params }),
  getById: (agentId) => request.get(`/api/agents/${agentId}`),
  updateStatus: (id, status) => request.put(`/api/agent-instances/${id}/status`, null, { params: { status } })
}

export const agentVersionApi = {
  list: () => request.get('/api/admin/agent-versions'),
  page: (params) => request.get('/api/admin/agent-versions/page', { params }),
  getById: (id) => request.get(`/api/admin/agent-versions/${id}`),
  create: (data) => request.post('/api/admin/agent-versions', data),
  update: (id, data) => request.put(`/api/admin/agent-versions/${id}`, data),
  publish: (id) => request.post(`/api/admin/agent-versions/${id}/publish`),
  unpublish: (id) => request.post(`/api/admin/agent-versions/${id}/unpublish`),
  delete: (id) => request.delete(`/api/admin/agent-versions/${id}`),
  notifyAll: (id) => request.post(`/api/admin/agent-versions/${id}/notify-all`),
  notify: (id, agentId) => request.post(`/api/admin/agent-versions/${id}/notify/${agentId}`),
  getStatistics: () => request.get('/api/admin/agent-versions/statistics')
}

export const registrationCodeApi = {
  generate: (data) => request.post('/api/registration-codes/generate', data),
  list: (params) => request.get('/api/registration-codes/list', { params }),
  validate: (code) => request.get(`/api/registration-codes/validate/${code}`),
  check: (code) => request.get(`/api/registration-codes/check/${code}`),
  delete: (ids) => request.delete('/api/registration-codes', { data: ids })
}

export const gameAccountApi = {
  list: (params) => request.get('/api/game-accounts', { params }),
  getById: (id) => request.get(`/api/game-accounts/${id}`),
  create: (data) => request.post('/api/game-accounts', data),
  update: (id, data) => request.put(`/api/game-accounts/${id}`, data),
  delete: (id) => request.delete(`/api/game-accounts/${id}`)
}

export const taskApi = {
  list: (params) => request.get('/api/tasks/page', { params }),
  getById: (id) => request.get(`/api/tasks/${id}`),
  create: (data) => request.post('/api/tasks', data),
  assign: (taskId, agentId) => request.post(`/api/tasks/${taskId}/assign/${agentId}`),
  start: (taskId) => request.post(`/api/tasks/${taskId}/start`),
  complete: (taskId, result) => request.post(`/api/tasks/${taskId}/complete`, { result }),
  fail: (taskId, errorMessage) => request.post(`/api/tasks/${taskId}/fail`, { errorMessage }),
  cancel: (taskId) => request.post(`/api/tasks/${taskId}/cancel`),
  retry: (taskId) => request.post(`/api/tasks/${taskId}/retry`),
  delete: (id) => request.delete(`/api/tasks/${id}`),
  getTypes: () => request.get('/api/tasks/types'),
  getStatuses: () => request.get('/api/tasks/statuses'),
  listByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}`),
  listPendingByAgent: (agentId) => request.get(`/api/tasks/agent/${agentId}/pending`)
}