/**
 * 设备相关API
 */
import request from './request'

// 设备信息
export interface Device {
  id: number
  device_id: string
  name: string
  device_type: string
  device_type_display: string
  ip_address: string
  mac_address: string | null
  location: string | null
  status: 'online' | 'offline' | 'warning'
  status_display: string
  is_trusted: boolean
  security_score: number
  security_level: 'high' | 'medium' | 'low'
  last_score_update: string | null
  groups: string[]       // 分组名称列表（用于展示）
  group_ids: number[]    // 分组ID列表（用于过滤匹配）
  last_seen: string | null
  created_at: string
  updated_at: string
}

// 设备概览
export interface DeviceOverview {
  total: number
  online: number
  offline: number
  warning: number
  type_distribution: Array<{ device_type: string; count: number }>
}

// 获取设备列表
export function getDevices(params?: {
  device_type?: string
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: Device[]
  }>('/devices/', { params })
}

// 获取设备详情
export function getDevice(deviceId: string) {
  return request.get<Device>(`/devices/${deviceId}/`)
}

// 获取设备概览统计
export function getDeviceOverview() {
  return request.get<DeviceOverview>('/devices/overview/')
}

// 创建设备
export function createDevice(data: Partial<Device>) {
  return request.post<Device>('/devices/', data)
}

// 更新设备
export function updateDevice(deviceId: string, data: Partial<Device>) {
  return request.put<Device>(`/devices/${deviceId}/`, data)
}

// 设备分组
export interface DeviceGroup {
  id: number
  name: string
  description: string
  icon: string
  color: string
  parent: number | null
  parent_name: string | null
  device_count: number
  created_at: string
  updated_at: string
  children?: DeviceGroup[]
}

// 安全评分历史
export interface SecurityScoreHistory {
  date: string
  security_score: number
  anomaly_count: number
  avg_confidence: number
}

// 安全概览
export interface SecurityOverview {
  total_devices: number
  avg_score: number
  high_security: number
  medium_security: number
  low_security: number
  score_distribution: Array<{ range: string; count: number }>
}

// 删除设备
export function deleteDevice(deviceId: string) {
  return request.delete(`/devices/${deviceId}/`)
}

// 批量设置设备检测状态
export function batchSetMonitoring(deviceIds: string[], enabled: boolean) {
  return request.post('/devices/batch_set_monitoring/', {
    device_ids: deviceIds,
    enabled
  })
}

// ========== 设备分组相关API ==========

// 获取设备分组列表
export function getDeviceGroups(params?: {
  tree?: boolean
  parent_id?: number
}) {
  return request.get<DeviceGroup[]>('/devices/groups/', { params })
}

// 获取分组详情
export function getDeviceGroup(groupId: number) {
  return request.get<DeviceGroup>(`/devices/groups/${groupId}/`)
}

// 创建设备分组
export function createDeviceGroup(data: {
  name: string
  description?: string
  icon?: string
  color?: string
  parent?: number
}) {
  return request.post<DeviceGroup>('/devices/groups/', data)
}

// 更新设备分组
export function updateDeviceGroup(groupId: number, data: Partial<DeviceGroup>) {
  return request.put<DeviceGroup>(`/devices/groups/${groupId}/`, data)
}

// 删除设备分组
export function deleteDeviceGroup(groupId: number) {
  return request.delete(`/devices/groups/${groupId}/`)
}

// 获取分组下的设备
export function getGroupDevices(groupId: number, params?: {
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: Device[]
  }>(`/devices/groups/${groupId}/devices/`, { params })
}

// 添加设备到分组
export function addDevicesToGroup(groupId: number, deviceIds: string[]) {
  return request.post(`/devices/groups/${groupId}/add_devices/`, {
    device_ids: deviceIds
  })
}

// 从分组移除设备
export function removeDevicesFromGroup(groupId: number, deviceIds: string[]) {
  return request.post(`/devices/groups/${groupId}/remove_devices/`, {
    device_ids: deviceIds
  })
}

// 批量分配设备分组
export function batchAssignGroups(deviceIds: string[], groupIds: number[]) {
  return request.post('/devices/groups/batch_assign/', {
    device_ids: deviceIds,
    group_ids: groupIds
  })
}

// 获取未分组设备
export function getUngroupedDevices(params?: {
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: Device[]
  }>('/devices/groups/ungrouped_devices/', { params })
}

// ========== 设备安全评分相关API ==========

// 获取设备安全评分
export function getDeviceSecurityScore(deviceId: string) {
  return request.get<{
    device_id: string
    security_score: number
    security_level: string
  }>('/devices/security/score/', {
    params: { device_id: deviceId }
  })
}

// 更新设备安全评分
export function updateDeviceSecurityScore(deviceId: string) {
  return request.post('/devices/security/update_score/', {
    device_id: deviceId
  })
}

// 批量更新安全评分
export function batchUpdateSecurityScores(deviceIds?: string[]) {
  return request.post('/devices/security/batch_update_scores/', {
    device_ids: deviceIds
  })
}

// 获取安全评分历史
export function getSecurityScoreHistory(deviceId: string, days: number = 30) {
  return request.get<{
    device_id: string
    days: number
    history: SecurityScoreHistory[]
  }>('/devices/security/score_history/', {
    params: { device_id: deviceId, days }
  })
}

// 获取安全概览
export function getSecurityOverview() {
  return request.get<SecurityOverview>('/devices/security/overview/')
}
