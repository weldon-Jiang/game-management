import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { isAuthError } from './constants'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000
})

request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    if (config.method === 'post' || config.method === 'put') {
      config.headers['Content-Type'] = 'application/json'
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  response => {
    const res = response.data
    if (res.code !== 200 && res.code !== 0) {
      if (isAuthError(res.code)) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
        return Promise.reject(new Error(res.message || 'Auth error'))
      }
      ElMessage.error(res.message || 'Request failed')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return res
  },
  error => {
    if (error.response) {
      if (error.response.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
      }
      ElMessage.error(error.response.data?.message || 'Network error')
    } else {
      ElMessage.error('Network error')
    }
    return Promise.reject(error)
  }
)

export default request