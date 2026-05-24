/**
 * 认证相关API
 */
import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  password: string
  confirm_password: string
  email?: string
  phone?: string
}

export interface UserInfo {
  id: number
  username: string
  email: string | null
  phone: string | null
  avatar: string | null
  role: 'admin' | 'user' | 'guest'
  is_active: boolean
  date_joined: string
  last_login: string | null
  created_at: string
}

export interface AuthResponse {
  code: number
  message: string
  data: {
    access: string
    refresh: string
    user: UserInfo
  }
}

export interface ChangePasswordParams {
  old_password: string
  new_password: string
  confirm_password: string
}

export interface UpdateProfileParams {
  email?: string
  phone?: string
  avatar?: string
}

// 审计日志接口
export interface AuditLog {
  id: number
  username: string | null
  action: string
  action_display: string
  resource_type: string
  resource_type_display: string
  resource_id: string | null
  resource_name: string | null
  description: string | null
  request_path: string | null
  request_method: string | null
  result: string
  result_display: string
  error_message: string | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
  old_value: string | null
  new_value: string | null
  request_data?: string | null
  session_id?: string | null
}

export interface AuditLogListParams {
  page?: number
  page_size?: number
  action?: string
  resource_type?: string
  result?: string
  username?: string
  start_time?: string
  end_time?: string
  search?: string
  ordering?: string
}

export interface AuditLogListResponse {
  code: number
  message: string
  data: {
    count: number
    next: string | null
    previous: string | null
    results: AuditLog[]
  }
}

export interface AuditLogStatistics {
  total: number
  recent_total: number
  action_stats: Array<{ action: string; count: number }>
  resource_stats: Array<{ resource_type: string; count: number }>
  result_stats: Array<{ result: string; count: number }>
  daily_stats: Array<{ date: string; count: number }>
}

// 用户注册
export const register = (data: RegisterParams) => {
  return request.post<AuthResponse>('/auth/register/', data)
}

// 用户登录
export const login = (data: LoginParams) => {
  return request.post<AuthResponse>('/auth/login/', data)
}

// 用户登出
export const logout = (refresh?: string) => {
  return request.post('/auth/logout/', { refresh })
}

// 获取当前用户信息
export const getMe = () => {
  return request.get<{ code: number; message: string; data: UserInfo }>('/auth/me/')
}

// 更新用户信息
export const updateProfile = (data: UpdateProfileParams) => {
  return request.patch<{ code: number; message: string; data: UserInfo }>('/auth/update_profile/', data)
}

// 修改密码
export const changePassword = (data: ChangePasswordParams) => {
  return request.post<{ code: number; message: string }>('/auth/change_password/', data)
}

// 刷新令牌
export const refreshToken = (refresh: string) => {
  return request.post<{ access: string; refresh: string }>('/auth/token/refresh/', { refresh })
}

// 获取审计日志列表
export const getAuditLogs = (params?: AuditLogListParams) => {
  return request.get<AuditLogListResponse>('/audit-logs/', { params })
}

// 获取审计日志详情
export const getAuditLogDetail = (id: number) => {
  return request.get<{ code: number; message: string; data: AuditLog }>(`/audit-logs/${id}/`)
}

// 获取审计日志统计
export const getAuditLogStatistics = () => {
  return request.get<{ code: number; message: string; data: AuditLogStatistics }>('/audit-logs/statistics/')
}

// 导出审计日志（返回CSV文件下载URL）
export const exportAuditLogs = (params?: AuditLogListParams) => {
  const queryString = params ? new URLSearchParams(
    Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== '')
      .map(([k, v]) => [k, String(v)])
  ).toString() : ''
  
  // 获取基础URL和token
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
  const token = localStorage.getItem('access_token')
  
  // 构建完整URL
  const url = `${baseUrl}/audit-logs/export/${queryString ? '?' + queryString : ''}`
  
  // 使用fetch下载文件
  return fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }).then(response => {
    if (!response.ok) {
      throw new Error('导出失败')
    }
    return response.blob()
  }).then(blob => {
    // 创建下载链接
    const downloadUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `审计日志_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(downloadUrl)
  })
}