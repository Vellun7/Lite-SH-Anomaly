/**
 * Axios请求封装
 */
import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 创建axios实例
const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 是否正在刷新token
let isRefreshing = false
// 重试队列
let retryQueue: Array<(token: string) => void> = []

// 请求拦截器
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 401 未授权 - 尝试刷新token
    if (error.response?.status === 401 && !originalRequest._retry) {
      const refreshToken = localStorage.getItem('refresh_token')
      
      if (!refreshToken) {
        // 没有refresh token，跳转登录
        handleLogout()
        return Promise.reject(error)
      }

      if (isRefreshing) {
        // 正在刷新，加入队列等待
        return new Promise((resolve) => {
          retryQueue.push((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(request(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const response = await axios.post('/api/v1/auth/token/refresh/', {
          refresh: refreshToken
        })

        const { access, refresh } = response.data
        localStorage.setItem('access_token', access)
        if (refresh) {
          localStorage.setItem('refresh_token', refresh)
        }

        // 执行队列中的请求
        retryQueue.forEach((callback) => callback(access))
        retryQueue = []

        // 重试原请求
        originalRequest.headers.Authorization = `Bearer ${access}`
        return request(originalRequest)
      } catch (refreshError) {
        // 刷新失败，跳转登录
        handleLogout()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // 其他错误处理
    const message = error.response?.data?.detail 
      || error.response?.data?.message 
      || error.response?.data?.non_field_errors?.[0]
      || '请求失败'
    
    if (error.response?.status !== 401) {
      ElMessage.error(message)
    }

    return Promise.reject(error)
  }
)

// 登出处理
function handleLogout() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_info')
  router.push('/login')
}

export default request
