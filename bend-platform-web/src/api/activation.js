import request from '@/utils/request'

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
