import { defineStore } from 'pinia'
import { authApi } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null')
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    isPlatformAdmin: (state) => state.user?.role === 'platform_admin',
    isOwner: (state) => state.user?.role === 'owner',
    isAdmin: (state) => state.user?.role === 'admin',
    isOperator: (state) => state.user?.role === 'operator',
    merchantId: (state) => state.user?.merchantId,
    userId: (state) => state.user?.userId,
    username: (state) => state.user?.username,
    role: (state) => state.user?.role
  },

  actions: {
    async login(loginKey, password) {
      try {
        const res = await authApi.login({ loginKey, password })
        this.token = res.data.token
        this.user = {
          userId: res.data.userId,
          username: res.data.username,
          merchantId: res.data.merchantId,
          role: res.data.role
        }
        localStorage.setItem('token', this.token)
        localStorage.setItem('user', JSON.stringify(this.user))
        return true
      } catch (error) {
        this.logout()
        throw error
      }
    },

    async register(data) {
      try {
        const res = await authApi.register(data)
        this.token = res.data.token
        this.user = {
          userId: res.data.userId,
          username: res.data.username,
          merchantId: res.data.merchantId,
          role: res.data.role
        }
        localStorage.setItem('token', this.token)
        localStorage.setItem('user', JSON.stringify(this.user))
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
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    }
  }
})