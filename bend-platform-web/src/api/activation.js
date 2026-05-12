import request from '@/utils/request'

export const activationApi = {
  createCode: (data) => request.post('/api/activation-codes', data),
  listCodes: (params) => request.get('/api/activation-codes/list', { params }),
  getPrices: (params) => request.get('/api/activation-codes/prices', { params }),
  previewCode: (code) => request.get('/api/activation-codes/preview', { params: { code } }),
  listBatches: (params) => request.get('/api/activation-codes/batch/list', { params }),
  delete: (id) => request.delete(`/api/activation-codes/${id}`),
  activate: (code) => request.post('/api/merchant-subscription/activate', null, { params: { code } })
}
