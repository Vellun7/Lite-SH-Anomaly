// Mock数据 - 后续对接后端API时替换

// 设备列表
export const mockDevices = [
  { id: 'DEV001', name: '客厅摄像头', type: 'camera', location: '客厅', status: 'online', ip: '192.168.1.101', lastActive: '2025-12-12 16:30:00' },
  { id: 'DEV002', name: '智能门锁', type: 'lock', location: '大门', status: 'online', ip: '192.168.1.102', lastActive: '2025-12-12 16:28:00' },
  { id: 'DEV003', name: '温湿度传感器', type: 'sensor', location: '卧室', status: 'online', ip: '192.168.1.103', lastActive: '2025-12-12 16:25:00' },
  { id: 'DEV004', name: '智能插座', type: 'switch', location: '书房', status: 'offline', ip: '192.168.1.104', lastActive: '2025-12-12 10:00:00' },
  { id: 'DEV005', name: '烟雾报警器', type: 'alarm', location: '厨房', status: 'online', ip: '192.168.1.105', lastActive: '2025-12-12 16:29:00' },
  { id: 'DEV006', name: '智能灯泡', type: 'light', location: '客厅', status: 'online', ip: '192.168.1.106', lastActive: '2025-12-12 16:20:00' },
]

// 设备类型图标映射
export const deviceTypeIcons: Record<string, string> = {
  camera: '📹',
  lock: '🔐',
  sensor: '🌡️',
  switch: '🔌',
  alarm: '🚨',
  light: '💡',
}

// 统计概览数据
export const mockStats = {
  totalDevices: 6,
  onlineDevices: 5,
  offlineDevices: 1,
  todayDetections: 1247,
  todayAnomalies: 3,
  anomalyRate: 0.24,
  avgLatency: 45,
}

// 威胁类型分布
export const mockThreatTypes = [
  { name: 'DDoS攻击', value: 12, color: '#F44336' },
  { name: '越权访问', value: 8, color: '#FF9800' },
  { name: '异常流量', value: 5, color: '#2196F3' },
  { name: '指令注入', value: 3, color: '#9C27B0' },
]

// 最近告警
export const mockAlerts = [
  { id: 1, device: '客厅摄像头', type: 'DDoS攻击', level: 'high', time: '2025-12-12 16:25:33', status: 'pending', confidence: 0.92 },
  { id: 2, device: '智能门锁', type: '越权访问', level: 'medium', time: '2025-12-12 15:42:18', status: 'handled', confidence: 0.87 },
  { id: 3, device: '温湿度传感器', type: '异常流量', level: 'low', time: '2025-12-12 14:15:00', status: 'pending', confidence: 0.75 },
]

// 检测趋势数据（24小时）
export const mockDetectionTrend = {
  times: ['00:00', '02:00', '04:00', '06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'],
  normal: [45, 32, 28, 35, 120, 180, 210, 195, 220, 185, 150, 95],
  anomaly: [0, 0, 1, 0, 2, 1, 3, 2, 1, 0, 1, 0],
}

// 性能指标
export const mockPerformance = {
  accuracy: 0.94,
  precision: 0.91,
  recall: 0.89,
  f1Score: 0.90,
  avgLatency: 45,
  maxLatency: 98,
  memoryUsage: 24.5,
  cpuUsage: 12.3,
}

// 实时检测记录
export const mockDetectionRecords = [
  { id: 1, device: 'DEV001', timestamp: '2025-12-12 16:30:15', result: 'normal', confidence: 0.98, latency: 42 },
  { id: 2, device: 'DEV002', timestamp: '2025-12-12 16:30:12', result: 'normal', confidence: 0.95, latency: 38 },
  { id: 3, device: 'DEV003', timestamp: '2025-12-12 16:30:10', result: 'anomaly', confidence: 0.87, latency: 55, attackType: 'DDoS攻击' },
  { id: 4, device: 'DEV005', timestamp: '2025-12-12 16:30:08', result: 'normal', confidence: 0.99, latency: 35 },
  { id: 5, device: 'DEV006', timestamp: '2025-12-12 16:30:05', result: 'normal', confidence: 0.96, latency: 41 },
]

// 用户操作日志
export const mockUserLogs = [
  { id: 1, username: 'admin', action: 'login', description: '用户登录系统', ip: '192.168.1.100', time: '2025-12-12 16:30:00', status: 'success' },
  { id: 2, username: 'admin', action: 'view', description: '查看设备列表', ip: '192.168.1.100', time: '2025-12-12 16:28:15', status: 'success' },
  { id: 3, username: 'admin', action: 'handle_alert', description: '处理告警 #1024', ip: '192.168.1.100', time: '2025-12-12 16:25:30', status: 'success' },
  { id: 4, username: 'operator', action: 'login', description: '用户登录系统', ip: '192.168.1.105', time: '2025-12-12 15:42:00', status: 'success' },
  { id: 5, username: 'operator', action: 'export', description: '导出检测报告', ip: '192.168.1.105', time: '2025-12-12 15:38:20', status: 'success' },
  { id: 6, username: 'guest', action: 'login', description: '用户登录失败', ip: '192.168.1.200', time: '2025-12-12 14:20:00', status: 'failed' },
  { id: 7, username: 'admin', action: 'update', description: '更新系统配置', ip: '192.168.1.100', time: '2025-12-12 14:10:00', status: 'success' },
  { id: 8, username: 'admin', action: 'logout', description: '用户退出系统', ip: '192.168.1.100', time: '2025-12-12 12:00:00', status: 'success' },
]

// 用户操作类型图标映射
export const userActionIcons: Record<string, string> = {
  login: '🔑',
  logout: '🚪',
  view: '👁️',
  handle_alert: '🔔',
  export: '📤',
  update: '⚙️',
  create: '➕',
  delete: '🗑️',
}
