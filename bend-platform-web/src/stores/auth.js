import { defineStore } from 'pinia'
import { authApi } from '@/api'

const TOKEN_EXPIRY_KEY = 'token_expiry'
// 后端 Token 默认按 24 小时保存，前端提前 1 小时刷新，减少用户操作中途 401 的概率。
const REFRESH_BEFORE_SECONDS = 3600

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    tokenExpiry: parseInt(localStorage.getItem(TOKEN_EXPIRY_KEY) || '0'),
    isRefreshing: false
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    // 三个角色 getter 是前端菜单、按钮和查询范围的统一权限入口。
    isPlatformAdmin: (state) => state.user?.role === 'platform_admin',
    isMerchantOwner: (state) => state.user?.role === 'merchant_owner',
    isOperator: (state) => state.user?.role === 'operator',
    hasManagementPermission: (state) => state.user?.role === 'platform_admin' || state.user?.role === 'merchant_owner',
    merchantId: (state) => state.user?.merchantId,
    userId: (state) => state.user?.userId,
    username: (state) => state.user?.username,
    role: (state) => state.user?.role,
    needsRefresh: (state) => {
      if (!state.tokenExpiry) return false
      const remaining = state.tokenExpiry - Date.now() / 1000
      return remaining < REFRESH_BEFORE_SECONDS
    }
  },

  actions: {
    setToken(token, user) {
      this.token = token
      this.user = user
      this.tokenExpiry = Date.now() / 1000 + 86400
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
      localStorage.setItem(TOKEN_EXPIRY_KEY, this.tokenExpiry.toString())
    },

    async refreshToken() {
      if (this.isRefreshing) return false
      if (!this.token) return false

      this.isRefreshing = true
      try {
        // 刷新成功后重写本地用户快照，保证角色/merchantId 与最新 Token 一致。
        const res = await authApi.refresh()
        if (res.code === 0 || res.code === 200) {
          this.setToken(res.data.token, {
            userId: res.data.userId,
            username: res.data.username,
            merchantId: res.data.merchantId,
            role: res.data.role
          })
          return true
        }
        return false
      } catch (error) {
        console.error('Token refresh failed:', error)
        // 刷新失败说明当前会话不再可信，必须清理本地认证状态。
        this.logout()
        return false
      } finally {
        this.isRefreshing = false
      }
    },

    async login(loginKey, password) {
      try {
        const res = await authApi.login({ loginKey, password })
        this.setToken(res.data.token, {
          userId: res.data.userId,
          username: res.data.username,
          merchantId: res.data.merchantId,
          role: res.data.role
        })
        return true
      } catch (error) {
        this.logout()
        throw error
      }
    },

    async register(data) {
      try {
        const res = await authApi.register(data)
        this.setToken(res.data.token, {
          userId: res.data.userId,
          username: res.data.username,
          merchantId: res.data.merchantId,
          role: res.data.role
        })
        return true
      } catch (error) {
        throw error
      }
    },

    logout() {
      this.token = ''
      this.user = null
      this.tokenExpiry = 0
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      localStorage.removeItem(TOKEN_EXPIRY_KEY)
    }
  }
})