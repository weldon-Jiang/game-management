/**
 * 商户使用权限（Permission）API：总控续期/停用/恢复/查询。
 */
import request from '@/utils/request'

export const permissionApi = {
  /** 分页查询权限列表 */
  list: (params) => request.get('/api/permissions', { params }),

  /** 创建/激活权限 */
  create: (data) => request.post('/api/permissions', data),

  /** 续期。expireAt 格式: yyyy-MM-dd HH:mm:ss */
  renew: (id, expireAt) => request.put(`/api/permissions/${id}/renew`, null, { params: { expireAt } }),

  /** 停用 */
  suspend: (id) => request.put(`/api/permissions/${id}/suspend`),

  /** 恢复（解除停用） */
  resume: (id) => request.put(`/api/permissions/${id}/resume`),

  /** 查询商户的权限 */
  getByMerchant: (merchantId) => request.get(`/api/permissions/merchant/${merchantId}`),

  /** 查询单个权限 */
  getById: (id) => request.get(`/api/permissions/${id}`)
}
