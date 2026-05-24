/**
 * 首页仪表盘API
 */
import request from './request'

// 首页统计数据
export interface DashboardStats {
  // 设备统计
  totalDevices: number
  onlineDevices: number
  offlineDevices: number
  warningDevices: number
  // 检测统计
  todayDetections: number
  todayAnomalies: number
  anomalyRate: number
  // 性能统计
  avgLatency: number
  accuracy: number
}

// 检测统计详情
export interface DetectionStats {
  total: number
  anomaly: number
  normal: number
  anomaly_rate: number
  attack_distribution: Array<{ attack_type: string; count: number }>
  daily_trend: Array<{ date: string; total: number; anomaly: number }>
  avg_inference_time: number
}

// 获取首页统计数据（聚合多个接口）
export async function getDashboardStats(): Promise<DashboardStats> {
  const [deviceRes, detectionRes] = await Promise.all([
    request.get('/devices/overview/'),
    request.get('/detection/stats/', { params: { days: 1 } })
  ])
  
  const deviceData = (deviceRes.data as any).data || deviceRes.data
  const detectionData = (detectionRes.data as any).data || detectionRes.data
  
  return {
    totalDevices: deviceData.total || 0,
    onlineDevices: deviceData.online || 0,
    offlineDevices: deviceData.offline || 0,
    warningDevices: deviceData.warning || 0,
    todayDetections: detectionData.total || 0,
    todayAnomalies: detectionData.anomaly || 0,
    anomalyRate: detectionData.anomaly_rate || 0,
    avgLatency: detectionData.avg_inference_time || 0,
    accuracy: 94 // 模型准确率（固定值，来自模型评估）
  }
}

// 获取检测统计（用于图表）
export function getDetectionStats(days: number = 7) {
  return request.get<DetectionStats>('/detection/stats/', { params: { days } })
}
