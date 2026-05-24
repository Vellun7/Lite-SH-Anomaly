/**
 * 检测相关API
 */
import request from './request'

// 检测输入参数
export interface DetectionInput {
  device_id: string
  src_ip?: string
  dst_ip?: string
  src_port?: number
  dst_port?: number
  protocol?: string
  duration?: number
  orig_bytes?: number
  resp_bytes?: number
  orig_pkts?: number
  resp_pkts?: number
}

// 检测结果
export interface DetectionResult {
  device_id: string
  timestamp: string
  is_anomaly: boolean
  attack_type: string
  confidence: number
  anomaly_score: number
  inference_time: number
  model_version: string
}

// 检测记录
export interface DetectionRecord {
  id: number
  device_id: string
  timestamp: string
  src_ip: string
  dst_ip: string
  src_port: number
  dst_port: number
  protocol: string
  duration: number
  orig_bytes: number
  resp_bytes: number
  orig_pkts: number
  resp_pkts: number
  is_anomaly: boolean
  attack_type: string
  confidence: number
  anomaly_score: number
  inference_time: number
  model_version: string
}

// 单条检测
export function detectSingle(data: DetectionInput) {
  return request.post<DetectionResult>('/detection/detect/', data)
}

// 批量检测
export function detectBatch(dataList: DetectionInput[]) {
  return request.post<DetectionResult[]>('/detection/batch/', { data: dataList })
}

// 获取检测记录列表
export function getDetectionRecords(params?: {
  device_id?: string
  attack_type?: string
  is_anomaly?: boolean
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}) {
  return request.get<{
    count: number
    results: DetectionRecord[]
  }>('/detection/records/', { params })
}

// 获取检测统计
export function getDetectionStats() {
  return request.get('/detection/stats/')
}

// 获取模型信息
export function getModelInfo() {
  return request.get('/detection/model-info/')
}

// ========== 监控相关 ==========

export interface MonitoringQueryParams {
  start_time?: string
  end_time?: string
  device_id?: string
  attack_type?: string
  protocol?: string
  is_anomaly?: boolean
  granularity?: 'hour' | 'day' | 'week' | 'month'
}

export interface MonitoringKpiData {
  total_detections: number
  anomaly_count: number
  anomaly_rate: number
  avg_confidence: number
  avg_anomaly_score: number
  avg_inference_time: number
}

export interface MonitoringTrendItem {
  period: string
  total: number
  anomaly: number
}

export interface MonitoringDeviceRiskItem {
  device_id: string
  total: number
  anomaly: number
  anomaly_rate: number
}

export interface MonitoringScoreConfidenceItem {
  anomaly_score: number
  confidence: number
  is_anomaly: boolean
}

export interface MonitoringTrafficFeatureItem {
  bucket: string
  total: number
  anomaly: number
  anomaly_rate: number
}

export function getMonitoringKpi(params?: MonitoringQueryParams) {
  return request.get<MonitoringKpiData>('/detection/monitoring/kpi/', { params })
}

export function getMonitoringTrend(params?: MonitoringQueryParams) {
  return request.get<MonitoringTrendItem[]>('/detection/monitoring/trend/', { params })
}

export function getMonitoringDeviceRisk(params?: MonitoringQueryParams) {
  return request.get<MonitoringDeviceRiskItem[]>('/detection/monitoring/device-risk/', { params })
}

export function getMonitoringScoreConfidence(params?: MonitoringQueryParams) {
  return request.get<MonitoringScoreConfidenceItem[]>('/detection/monitoring/score-confidence/', { params })
}

export function getMonitoringTrafficFeature(params?: MonitoringQueryParams) {
  return request.get<MonitoringTrafficFeatureItem[]>('/detection/monitoring/traffic-feature/', { params })
}

// ========== 持续检测相关 ==========

// 持续检测配置
export interface ContinuousDetectionConfig {
  enabled: boolean
  interval: number
  target_devices: string[]
}

// 持续检测状态
export interface ContinuousDetectionStatus {
  enabled: boolean
  interval: number
  target_devices: string[]
  total_detections: number
  total_anomalies: number
  started_at: string | null
  updated_at: string | null
  is_running: boolean
}

// 获取持续检测状态
export function getContinuousStatus() {
  return request.get<ContinuousDetectionStatus>('/detection/continuous/')
}

// 开启/关闭持续检测
export function toggleContinuousDetection(data: ContinuousDetectionConfig) {
  return request.post<ContinuousDetectionStatus>('/detection/continuous/', data)
}
