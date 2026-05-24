/**
 * 日志相关API
 */
import request from './request'

// 告警信息
export interface Alert {
  id: number
  device_id: string
  device_name: string | null
  level: 'info' | 'warning' | 'danger' | 'critical'
  attack_type: string
  message: string
  confidence: number
  status: 'pending' | 'confirmed' | 'resolved' | 'ignored'
  created_at: string
  updated_at: string
}

// 告警统计
export interface AlertStats {
  total: number
  pending: number
  resolved: number
  level_distribution: Array<{ level: string; count: number }>
  daily_trend: Array<{ date: string; count: number }>
}

// 登录日志
export interface LoginLog {
  id: number
  user: number
  ip_address: string
  user_agent: string
  status: 'success' | 'failed'
  fail_reason: string | null
  created_at: string
}

// 获取告警列表
export function getAlerts(params?: {
  level?: string
  status?: string
  device_id?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: Alert[]
  }>('/logs/alerts/', { params })
}

// 更新告警状态
export function updateAlertStatus(alertId: number, status: string) {
  return request.patch(`/logs/alerts/${alertId}/`, { status })
}

// 批量更新告警状态
export function batchUpdateAlerts(alertIds: number[], status: string) {
  return request.post('/logs/alerts/batch-update/', { alert_ids: alertIds, status })
}

// 获取告警统计
export function getAlertStats(days?: number) {
  return request.get<AlertStats>('/logs/alerts/stats/', { params: { days } })
}

// 获取登录日志
export function getLoginLogs(params?: {
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: LoginLog[]
  }>('/auth/login-logs/', { params })
}
