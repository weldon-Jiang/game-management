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

// 同一个 method/url/params/data 只保留最后一次请求，避免列表刷新或重复点击造成旧响应覆盖新状态。
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

/** 同 URL 去重取消或路由切换 abort 时不应弹网络错误 toast。 */
export const isRequestCanceled = (error) => {
  if (!error) return false
  return (
    axios.isCancel(error) ||
    error.code === 'ERR_CANCELED' ||
    error.name === 'CanceledError' ||
    error.message === 'canceled'
  )
}

let isRefreshing = false
let refreshSubscribers = []

// Token 临近过期时只发起一次刷新，其余请求挂起等待新 Token 后继续发出。
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
      // 避免并发请求同时刷新 Token：第一个请求负责刷新，其余请求进入订阅队列。
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
        // 业务响应已判定认证失效时，清理所有挂起请求，避免后续请求继续携带旧 Token。
        console.log('Auth error detected in response interceptor, redirecting to login')
        clearAllPendingRequests()
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('token_expiry')
        router.push('/login')
        return Promise.reject(new Error(res.message || 'Auth error'))
      }
      if (!response.config?.skipErrorToast) {
        ElMessage.error(res.message || 'Request failed')
      }
      const err = new Error(res.message || 'Error')
      err.code = res.code
      err.data = res.data
      return Promise.reject(err)
    }
    return res
  },
  async (error) => {
    const authStore = useAuthStore()

    removePendingRequest(error.config || {})

    if (isRequestCanceled(error)) {
      return Promise.reject(error)
    }

    if (error.response) {
      console.log('Request error with response:', error.response.status, error.response.data)
      if (error.response.status === 401) {
        if (!error.config.url.includes('/auth/refresh') && !error.config.url.includes('/auth/login')) {
          // HTTP 401 允许一次刷新后重放原请求；刷新失败再统一登出。
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
