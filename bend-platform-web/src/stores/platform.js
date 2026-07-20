import { defineStore } from 'pinia'
import { platformApi } from '@/api/platform'

/**
 * 平台部署模式：master=总控 / tenant=分控。
 * 用于控制仅总控可见的菜单（如分控安装注册码管理）。
 */
export const usePlatformStore = defineStore('platform', {
  state: () => ({
    mode: null,
    loaded: false,
    loading: false
  }),

  getters: {
    isMasterMode: (state) => state.mode === 'master',
    isTenantMode: (state) => state.mode === 'tenant'
  },

  actions: {
    async fetchConfig() {
      if (this.loading) return
      this.loading = true
      try {
        const res = await platformApi.getConfig()
        if (res.code === 0 || res.code === 200) {
          this.mode = res.data?.mode === 'tenant' ? 'tenant' : 'master'
        } else {
          this.mode = 'master'
        }
      } catch (error) {
        console.error('Failed to load platform config:', error)
        this.mode = 'master'
      } finally {
        this.loaded = true
        this.loading = false
      }
    }
  }
})
