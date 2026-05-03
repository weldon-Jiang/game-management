import { defineStore } from 'pinia'
import { authApi } from '@/api'

const TOKEN_EXPIRY_KEY = 'token_expiry'
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

    async fetchCurrentUser() {
      try {
        const res = await authApi.getCurrentUser()
        this.user = res.data
        localStorage.setItem('user', JSON.stringify(this.user))
      } catch (error) {
        this.logout()
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