import request from '@/utils/request'

export const billingApi = {
  getBalance: () => request.get('/api/billing/balance'),

  recharge: (cardNo, cardPwd) => request.post('/api/billing/recharge', null, {
    params: { cardNo, cardPwd }
  }),

  createSubscription: (data) => request.post('/api/billing/subscriptions', null, { params: data }),

  renewSubscription: (id, data) => request.post(`/api/billing/subscriptions/${id}/renew`, null, {
    params: data
  }),

  cancelSubscription: (id) => request.delete(`/api/billing/subscriptions/${id}`),

  listSubscriptions: (params) => request.get('/api/billing/subscriptions', { params }),

  listActiveSubscriptions: () => request.get('/api/billing/subscriptions/active'),

  unbindDevice: (params) => request.post('/api/billing/device/unbind', null, { params }),

  checkDeviceBound: (params) => request.get('/api/billing/device/check', { params })
}

export const rechargeCardApi = {
  createBatch: (data) => request.post('/api/recharge-cards/batches', null, { params: data }),

  listBatches: (params) => request.get('/api/recharge-cards/batches', { params }),

  listCards: (params) => request.get('/api/recharge-cards', { params }),

  getCard: (cardNo) => request.get(`/api/recharge-cards/${cardNo}`),

  exportCards: (batchId) => request.get(`/api/recharge-cards/batches/${batchId}/export`),

  useCard: (cardNo, cardPwd) => request.post('/api/recharge-cards/use', null, {
    params: { cardNo, cardPwd }
  })
}

export const merchantGroupApi = {
  listAll: () => request.get('/api/merchant-groups'),

  getById: (id) => request.get(`/api/merchant-groups/${id}`),

  create: (data) => request.post('/api/merchant-groups', data),

  update: (id, data) => request.put(`/api/merchant-groups/${id}`, data),

  delete: (id) => request.delete(`/api/merchant-groups/${id}`)
}
