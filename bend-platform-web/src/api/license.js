/**
 * License（软件授权凭证）API：总控签发/吊销/查询。
 * 使用权限（到期/续期/配额）请用 @/api/permission.js 的 permissionApi。
 */
import request from '@/utils/request'

export const licenseApi = {
  /** 分页查询 License 列表 */
  list: (params) => request.get('/api/licenses', { params }),

  /** 查询单个 License */
  getById: (id) => request.get(`/api/licenses/${id}`),

  /** 签发 License（软件授权凭证，无到期时间） */
  issue: (data) => request.post('/api/licenses', data),

  /** 吊销 License */
  revoke: (id, reason) => request.put(`/api/licenses/${id}/revoke`, null, { params: { reason } }),

  /** 查询某个商户的所有 License */
  listByMerchant: (merchantId) => request.get(`/api/licenses/merchant/${merchantId}`)
}
