import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { isAuthError } from './constants'

const pendingRequests = new Map()

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000
})

const generateRequestKey = (config) => {
  const { method, url, params, data } = config
  return `${method}_${url}_${JSON.stringify(params)}_${JSON.stringify(data)}`
}

const removePendingRequest = (config) => {
  const key = generateRequestKey(config)
  if (pendingRequests.has(key)) {
    const cancel = pendingRequests.get(key)
    cancel('请求取消：由于发起新请求')
    pendingRequests.delete(key)
  }
}

const addPendingRequest = (config) => {
  removePendingRequest(config)
  const controller = new AbortController()
  config.signal = controller.signal
  pendingRequests.set(generateRequestKey(config), controller.abort.bind(controller))
}

const clearAllPendingRequests = () => {
  pendingRequests.forEach((cancel) => cancel('请求取消：全局清理'))
  pendingRequests.clear()
}

const retryDelay = (retryCount) => Math.min(1000 * Math.pow(2, retryCount), 10000)

let isRefreshing = false
let refreshSubscribers = []

const subscribeTokenRefresh = (callback) => {
  refreshSubscribers.push(callback)
}

const onTokenRefreshed = (newToken) => {
  refreshSubscribers.forEach((callback) => callback(newToken))
  refreshSubscribers = []
}

request.interceptors.request.use(
  (config) => {
    addPendingRequest(config)

    const authStore = useAuthStore()
    if (authStore.token) {
      if (authStore.needsRefresh && !authStore.isRefreshing && !config.url.includes('/auth/refresh')) {
        if (!isRefreshing) {
          isRefreshing = true
          authStore.refreshToken().then((success) => {
            isRefreshing = false
            if (success) {
              onTokenRefreshed(authStore.token)
            }
          })
        }
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken) => {
            config.headers.Authorization = `Bearer ${newToken}`
            resolve(config)
          })
        })
      }
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    if (config.method === 'post' || config.method === 'put') {
      config.headers['Content-Type'] = 'application/json'
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    removePendingRequest(response.config)
    const res = response.data
    if (res.code !== 200 && res.code !== 0) {
      console.log('Response with error code:', res.code, res.message)
      if (isAuthError(res.code)) {
        console.log('Auth error detected in response interceptor, redirecting to login')
        clearAllPendingRequests()
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('token_expiry')
        router.push('/login')
        return Promise.reject(new Error(res.message || 'Auth error'))
      }
      ElMessage.error(res.message || 'Request failed')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res
  },
  async (error) => {
    const authStore = useAuthStore()

    if (error.config && !error.config.__retryCount) {
      error.config.__retryCount = error.config.__retryCount || 0

      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        error.config.__retryCount += 1
        if (error.config.__retryCount <= 3) {
          ElMessage.warning(`请求超时，正在重试 (${error.config.__retryCount}/3)`)
          await new Promise((resolve) => setTimeout(resolve, retryDelay(error.config.__retryCount)))
          return request(error.config)
        }
        ElMessage.error('请求超时，请稍后重试')
      }

      if (error.response?.status >= 500 && error.config.__retryCount < 3) {
        error.config.__retryCount += 1
        ElMessage.warning(`服务器错误，正在重试 (${error.config.__retryCount}/3)`)
        await new Promise((resolve) => setTimeout(resolve, retryDelay(error.config.__retryCount)))
        return request(error.config)
      }
    }

    removePendingRequest(error.config || {})

    if (error.response) {
      console.log('Request error with response:', error.response.status, error.response.data)
      if (error.response.status === 401) {
        if (!error.config.url.includes('/auth/refresh') && !error.config.url.includes('/auth/login')) {
          const refreshed = await authStore.refreshToken()
          if (refreshed) {
            error.config.headers.Authorization = `Bearer ${authStore.token}`
            return request(error.config)
          }
        }
        console.log('401 detected, clearing auth and redirecting to login')
        clearAllPendingRequests()
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('token_expiry')
        try {
          router.push('/login')
          console.log('Navigation to /login initiated')
        } catch (e) {
          console.error('Navigation error:', e)
        }
      }
      ElMessage.error(error.response.data?.message || 'Network error')
    } else if (error.request) {
      ElMessage.error('网络连接失败，请检查网络')
    } else {
      ElMessage.error('Network error')
    }
    return Promise.reject(error)
  }
)

export const createCancelToken = () => new axios.CancelToken()

export const cancelAllRequests = () => clearAllPendingRequests()

export default request
