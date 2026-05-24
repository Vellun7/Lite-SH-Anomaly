<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Warning, Clock, Timer } from '@element-plus/icons-vue'
import {
  detectSingle,
  getContinuousStatus, toggleContinuousDetection,
  type ContinuousDetectionStatus
} from '@/api/detection'
import { getDevices, type Device } from '@/api/device'

// 设备类型图标
const deviceTypeIcons: Record<string, string> = {
  camera: '📷',
  door_lock: '🔐',
  sensor: '🌡️',
  gateway: '📶',
  other: '📱'
}

// 设备类型名称
const deviceTypeNames: Record<string, string> = {
  camera: '摄像头',
  door_lock: '门锁',
  sensor: '传感器',
  gateway: '网关',
  other: '设备'
}

const devices = ref<Device[]>([])
const selectedDevices = ref<string[]>([])
const isDetecting = ref(false)
const loading = ref(false)
const devicesLoading = ref(false)

// 持续检测相关
const continuousMode = ref(false)
const detectionInterval = ref(60) // 检测间隔（秒），默认60秒
const totalDetections = ref(0)
const totalAnomalies = ref(0)
const startedAt = ref<string | null>(null)
const lastUpdatedAt = ref<string | null>(null)
let statusPoller: ReturnType<typeof setInterval> | null = null // 状态轮询定时器
let lightStatusPoller: ReturnType<typeof setInterval> | null = null // 轻量状态轮询定时器
let durationTimer: ReturnType<typeof setInterval> | null = null // 运行时长更新定时器
let deviceStatusPoller: ReturnType<typeof setInterval> | null = null // 设备状态轮询定时器（后端每10分钟更新，前端30秒同步一次）
// 设备选择相关（已移除折叠面板，改用 Tag 标签形式）
const runningSeconds = ref(0) // 用于计算运行时长

// 格式化运行时长
const formattedRunningTime = computed(() => {
  if (!startedAt.value || !continuousMode.value) return '0秒'
  const hours = Math.floor(runningSeconds.value / 3600)
  const minutes = Math.floor((runningSeconds.value % 3600) / 60)
  const seconds = runningSeconds.value % 60
  if (hours > 0) {
    return `${hours}小时 ${minutes}分钟`
  } else if (minutes > 0) {
    return `${minutes}分钟 ${seconds}秒`
  }
  return `${seconds}秒`
})

// 更新运行时长
const updateRunningTime = () => {
  if (!startedAt.value || !continuousMode.value) {
    runningSeconds.value = 0
    return
  }
  const start = new Date(startedAt.value).getTime()
  if (Number.isNaN(start)) {
    runningSeconds.value = 0
    return
  }
  runningSeconds.value = Math.floor((Date.now() - start) / 1000)
}

// 启动运行时长计时器
const startDurationTimer = () => {
  stopDurationTimer()
  updateRunningTime()
  durationTimer = setInterval(updateRunningTime, 1000)
}

// 停止运行时长计时器
const stopDurationTimer = () => {
  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }
}

const anomalyRate = computed(() => {
  if (totalDetections.value === 0) {
    return 0
  }
  return Number(((totalAnomalies.value / totalDetections.value) * 100).toFixed(1))
})

const detectionRate = computed(() => {
  if (!startedAt.value || totalDetections.value === 0) {
    return 0
  }
  const started = new Date(startedAt.value).getTime()
  if (Number.isNaN(started)) {
    return 0
  }
  const diffSeconds = Math.max(1, (Date.now() - started) / 1000)
  const perMinute = (totalDetections.value / diffSeconds) * 60
  return Number(perMinute.toFixed(1))
})

const formattedUpdatedAt = computed(() => {
  if (!lastUpdatedAt.value) {
    return '暂无'
  }
  const date = new Date(lastUpdatedAt.value)
  if (Number.isNaN(date.getTime())) {
    return '暂无'
  }
  return date.toLocaleString()
})

// 加载设备列表
const loadDevices = async () => {
  devicesLoading.value = true
  try {
    const res = await getDevices({ page_size: 50 })
    const data = (res.data as any).data || res.data
    const deviceList = data.results || []
    // 排序：在线设备在前，离线设备在后
    devices.value = deviceList.sort((a: Device, b: Device) => {
      const statusOrder: Record<string, number> = { online: 0, warning: 1, offline: 2 }
      return (statusOrder[a.status] ?? 2) - (statusOrder[b.status] ?? 2)
    })
  } catch (error) {
    console.error('加载设备列表失败:', error)
    devices.value = []
  } finally {
    devicesLoading.value = false
  }
}

// 仅更新设备状态（不重新排序，避免 Tag 位置跳动）
const refreshDeviceStatus = async () => {
  try {
    const res = await getDevices({ page_size: 50 })
    const data = (res.data as any).data || res.data
    const deviceList = data.results || []
    
    // 只更新现有设备的状态
    for (const newDevice of deviceList) {
      const existingDevice = devices.value.find(d => d.device_id === newDevice.device_id)
      if (existingDevice) {
        existingDevice.status = newDevice.status
      }
    }
  } catch (error) {
    console.error('刷新设备状态失败:', error)
  }
}

// 获取设备显示名称（同类型设备加编号区分）
const getDeviceDisplayName = (device: Device) => {
  // 统计同类型设备
  const sameTypeDevices = devices.value.filter(d => d.device_type === device.device_type)
  if (sameTypeDevices.length > 1) {
    // 找到当前设备在同类型中的索引
    const index = sameTypeDevices.findIndex(d => d.device_id === device.device_id)
    const typeName = deviceTypeNames[device.device_type] || device.device_type
    return `${device.name} (${typeName}${index + 1})`
  }
  return device.name
}

// 切换设备选择
const toggleDeviceSelection = (device: Device) => {
  if (device.status === 'offline') {
    ElMessage.warning('离线设备无法选择')
    return
  }
  
  const index = selectedDevices.value.indexOf(device.device_id)
  if (index > -1) {
    selectedDevices.value.splice(index, 1)
  } else {
    selectedDevices.value.push(device.device_id)
  }
}

// 获取设备 Tag 类型
const getDeviceTagType = (device: Device) => {
  if (device.status === 'offline') return 'info'
  if (device.status === 'warning') return 'warning'
  return selectedDevices.value.includes(device.device_id) ? 'primary' : ''
}

// 生成模拟流量数据（约70%正常流量，30%异常流量）
const generateTrafficData = (device: Device) => {
  const isNormalTraffic = Math.random() < 0.7

  if (isNormalTraffic) {
    // 正常流量：参数范围与训练数据分布一致
    // duration: 0.1~30 (均值~15), orig_bytes: 64~2048, resp_bytes: 64~4096
    // orig_pkts: 1~20, resp_pkts: 1~25
    return {
      device_id: device.device_id,
      src_ip: device.ip_address || '192.168.1.100',
      dst_ip: '192.168.1.1',
      src_port: Math.floor(Math.random() * 60000) + 1024,
      dst_port: [80, 443, 8080][Math.floor(Math.random() * 3)],
      protocol: ['tcp', 'udp'][Math.floor(Math.random() * 2)],
      duration: 0.1 + Math.random() * 29.9,
      orig_bytes: 64 + Math.floor(Math.random() * 1984),
      resp_bytes: 64 + Math.floor(Math.random() * 4032),
      orig_pkts: 1 + Math.floor(Math.random() * 19),
      resp_pkts: 1 + Math.floor(Math.random() * 24)
    }
  } else {
    // 异常流量：明显偏离正常分布的特征
    // 短时间大流量、极高字节数/包数等
    return {
      device_id: device.device_id,
      src_ip: device.ip_address || '192.168.1.100',
      dst_ip: '192.168.1.1',
      src_port: Math.floor(Math.random() * 60000) + 1024,
      dst_port: [80, 443, 8080, 22, 3306][Math.floor(Math.random() * 5)],
      protocol: ['tcp', 'udp'][Math.floor(Math.random() * 2)],
      duration: Math.random() * 0.1,
      orig_bytes: 10000 + Math.floor(Math.random() * 40000),
      resp_bytes: Math.floor(Math.random() * 100000),
      orig_pkts: 100 + Math.floor(Math.random() * 200),
      resp_pkts: Math.floor(Math.random() * 150)
    }
  }
}

// 请求浏览器通知权限
const requestNotificationPermission = async () => {
  if ('Notification' in window && Notification.permission === 'default') {
    await Notification.requestPermission()
  }
}

// 发送告警通知
const sendAlertNotification = (device: Device, attackType: string, confidence: number) => {
  const typeName = deviceTypeNames[device.device_type] || device.device_type
  const attackText = getAttackTypeText(attackType)
  
  // 页面内通知
  ElNotification({
    title: '⚠️ 异常告警',
    message: `设备 ${device.name}(${typeName}) 检测到异常：${attackText}，置信度 ${(confidence * 100).toFixed(0)}%`,
    type: 'warning',
    duration: 10000,
    position: 'top-right'
  })
  
  // 浏览器系统通知
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('智能家居异常告警', {
      body: `设备 ${device.name} 检测到 ${attackText}`,
      icon: '/favicon.ico',
      tag: `anomaly-${device.device_id}-${Date.now()}`
    })
  }
  
  // 播放告警音效（可选）
  try {
    const audio = new Audio('/alert.mp3')
    audio.volume = 0.5
    audio.play().catch(() => {})
  } catch {}
}

// 执行一轮检测
const runDetectionRound = async () => {
  const targetDevices = selectedDevices.value.length > 0 
    ? devices.value.filter(d => selectedDevices.value.includes(d.device_id) && d.status !== 'offline')
    : devices.value.filter(d => d.status !== 'offline')

  if (targetDevices.length === 0) {
    return { success: 0, anomaly: 0 }
  }

  let successCount = 0
  let anomalyCount = 0

  for (const device of targetDevices) {
    const trafficData = generateTrafficData(device)
    
    try {
      const res = await detectSingle(trafficData)
      const result = (res.data as any).data || res.data
      successCount++
      
      // 检测到异常时发送告警通知
      // 注意：设备状态由后端每10分钟基于历史检测统计更新
      if (result.is_anomaly) {
        anomalyCount++
        sendAlertNotification(device, result.attack_type, result.confidence)
      }
    } catch (err) {
      console.error(`设备 ${device.device_id} 检测失败:`, err)
    }
  }

  return { success: successCount, anomaly: anomalyCount }
}

// 开始检测（单次）
const startDetection = async () => {
  const targetDevices = selectedDevices.value.length > 0 
    ? devices.value.filter(d => selectedDevices.value.includes(d.device_id) && d.status !== 'offline')
    : devices.value.filter(d => d.status !== 'offline')

  if (targetDevices.length === 0) {
    ElMessage.warning('没有可检测的设备')
    return
  }

  isDetecting.value = true

  try {
    const { success, anomaly } = await runDetectionRound()
    
    if (success > 0) {
      if (anomaly > 0) {
        ElMessage.warning(`检测完成，发现 ${anomaly} 个异常`)
      } else {
        ElMessage.success(`检测完成，${success} 个设备均正常`)
      }
    }
  } catch (error) {
    ElMessage.error('检测失败，请重试')
  } finally {
    isDetecting.value = false
  }
}

// 从后端获取持续检测状态
const loadContinuousStatus = async () => {
  try {
    const res = await getContinuousStatus()
    const data = (res.data as any).data || res.data
    const wasRunning = continuousMode.value
    const isRunning = data.enabled && data.is_running
    
    continuousMode.value = isRunning
    detectionInterval.value = data.interval || 5
    totalDetections.value = data.total_detections || 0
    totalAnomalies.value = data.total_anomalies || 0
    startedAt.value = data.started_at || null
    lastUpdatedAt.value = data.updated_at || null
    
    // 同步 isDetecting 状态：如果后端检测已停止，前端也要停止
    if (!isRunning) {
      isDetecting.value = false
      // 如果之前在运行，现在停止了，切换轮询模式
      if (wasRunning) {
        stopStatusPolling()
        stopDurationTimer()
        startLightStatusPolling()
      }
    }
  } catch (error) {
    console.error('获取持续检测状态失败:', error)
  }
}

// 启动状态轮询（在持续检测运行时定时拉取后端状态）
const startStatusPolling = () => {
  stopStatusPolling()
  stopLightStatusPolling()
  // 每3秒刷新检测状态
  statusPoller = setInterval(async () => {
    await loadContinuousStatus()
  }, 3000)
}

// 启动设备状态轮询（30秒同步一次后端设备状态）
const startDeviceStatusPolling = () => {
  stopDeviceStatusPolling()
  deviceStatusPoller = setInterval(async () => {
    await refreshDeviceStatus()
  }, 30000)
}

// 停止设备状态轮询
const stopDeviceStatusPolling = () => {
  if (deviceStatusPoller) {
    clearInterval(deviceStatusPoller)
    deviceStatusPoller = null
  }
}

// 停止状态轮询
const stopStatusPolling = () => {
  if (statusPoller) {
    clearInterval(statusPoller)
    statusPoller = null
  }
}

// 启动轻量状态轮询（持续检测未运行时，仅拉取状态）
const startLightStatusPolling = () => {
  stopLightStatusPolling()
  lightStatusPoller = setInterval(async () => {
    await loadContinuousStatus()
  }, 15000)
}

// 停止轻量状态轮询
const stopLightStatusPolling = () => {
  if (lightStatusPoller) {
    clearInterval(lightStatusPoller)
    lightStatusPoller = null
  }
}

// 切换持续检测模式（通过后端API控制）
const toggleContinuousMode = async () => {
  try {
    const targetDeviceIds = selectedDevices.value.length > 0
      ? selectedDevices.value
      : []

    const res = await toggleContinuousDetection({
      enabled: continuousMode.value,
      interval: detectionInterval.value,
      target_devices: targetDeviceIds,
    })
    const data = (res.data as any).data || res.data

    // 根据后端返回的实际状态更新本地状态
    const isRunning = data.enabled && data.is_running
    continuousMode.value = isRunning
    totalDetections.value = data.total_detections || 0
    totalAnomalies.value = data.total_anomalies || 0

    if (isRunning) {
      await requestNotificationPermission()
      ElMessage.success(`持续检测已启动，间隔 ${detectionInterval.value} 秒`)
      startStatusPolling()
      startDurationTimer()
    } else {
      // 持续检测停止时，确保 isDetecting 也重置
      isDetecting.value = false
      stopStatusPolling()
      stopDurationTimer()
      startLightStatusPolling()
      ElMessage.info(`持续检测已停止，共检测 ${totalDetections.value} 次，发现 ${totalAnomalies.value} 个异常`)
    }
  } catch (error) {
    console.error('切换持续检测失败:', error)
    ElMessage.error('操作失败，请重试')
    // 恢复开关状态
    continuousMode.value = !continuousMode.value
  }
}

const getResultType = (isAnomaly: boolean) => {
  return isAnomaly ? 'danger' : 'success'
}

const getAttackTypeText = (type: string) => {
  const map: Record<string, string> = {
    normal: '正常',
    ddos: 'DDoS攻击',
    port_scan: '端口扫描',
    unauthorized: '越权访问',
    malformed: '异常指令',
    unknown: '未知异常'
  }
  return map[type] || type
}

onMounted(async () => {
  loadDevices()
  // 预请求通知权限
  requestNotificationPermission()
  // 从后端加载持续检测状态
  await loadContinuousStatus()
  
  // 启动设备状态轮询（30秒同步一次，后端每10分钟更新）
  startDeviceStatusPolling()
  
  // 根据后端状态决定是否启动检测数据轮询
  if (continuousMode.value) {
    // 后端正在运行中，启动状态轮询
    startStatusPolling()
    startDurationTimer()
  } else {
    // 后端未运行，启动轻量轮询（只同步状态）
    startLightStatusPolling()
  }
})

// 组件卸载时清理轮询定时器（不影响后端持续检测）
onUnmounted(() => {
  stopStatusPolling()
  stopLightStatusPolling()
  stopDurationTimer()
  stopDeviceStatusPolling()
})
</script>

<template>
  <div class="detection-view">
    <div class="metrics-grid">
      <div class="card metric-card">
        <div class="metric-value">{{ totalDetections }}</div>
        <div class="metric-label">累计检测次数</div>
      </div>
      <div class="card metric-card">
        <div class="metric-value danger">{{ totalAnomalies }}</div>
        <div class="metric-label">累计异常次数</div>
      </div>
      <div class="card metric-card">
        <div class="metric-value">{{ detectionRate }}</div>
        <div class="metric-label">当前检测速率（次/分钟）</div>
      </div>
      <div class="card metric-card">
        <div class="metric-value">{{ anomalyRate }}%</div>
        <div class="metric-label">异常占比</div>
      </div>
    </div>

    <div class="card status-section" :class="{ 'is-running': continuousMode }">
      <!-- 运行状态指示条 -->
      <div v-if="continuousMode" class="running-indicator">
        <div class="running-bar"></div>
      </div>

      <div class="status-top">
        <div class="status-info">
          <div class="status-header">
            <h2>实时检测</h2>
            <div class="status-badge-group">
              <span class="status-badge" :class="{ 'is-active': continuousMode }">
                <span class="badge-dot"></span>
                {{ continuousMode ? '持续检测运行中' : '持续检测已停止' }}
              </span>
              <span v-if="continuousMode && totalAnomalies > 0" class="anomaly-badge">
                <el-icon><Warning /></el-icon>
                {{ totalAnomalies }} 个异常待处理
              </span>
            </div>
          </div>
          <p>监控设备流量，实时检测异常行为</p>
          <div class="status-row">
            <span class="status-updated">
              <el-icon><Clock /></el-icon>
              最近更新：{{ formattedUpdatedAt }}
            </span>
            <span v-if="continuousMode && startedAt" class="running-time">
              <el-icon><Timer /></el-icon>
              运行时长：{{ formattedRunningTime }}
            </span>
          </div>
        </div>
        <div class="status-actions">
          <el-button
            type="primary"
            size="default"
            :loading="isDetecting && !continuousMode"
            :disabled="selectedDevices.length === 0"
            @click="startDetection"
          >
            {{ isDetecting && !continuousMode ? '检测中...' : '检测' }}
          </el-button>
        </div>
      </div>

      <!-- 设备选择 - Tag 标签形式 -->
      <div class="device-tags-section">
        <div class="device-tags-header">
          <span class="device-tags-label">检测设备</span>
          <span class="device-tags-hint">
            {{ selectedDevices.length === 0 ? '全部设备' : `已选 ${selectedDevices.length} 个` }}
          </span>
        </div>
        <div class="device-tags-list" v-loading="devicesLoading">
          <el-tag
            v-for="device in devices"
            :key="device.device_id"
            :type="getDeviceTagType(device)"
            :effect="selectedDevices.includes(device.device_id) ? 'dark' : 'plain'"
            :class="{ 
              'device-tag': true, 
              'is-selected': selectedDevices.includes(device.device_id),
              'is-offline': device.status === 'offline',
              'is-warning': device.status === 'warning'
            }"
            size="large"
            @click="toggleDeviceSelection(device)"
          >
            <span class="tag-icon">{{ deviceTypeIcons[device.device_type] || '📱' }}</span>
            <span class="tag-name">{{ device.name }}</span>
            <span class="tag-status" :class="device.status">
              {{ device.status === 'online' ? '●' : device.status === 'warning' ? '◐' : '○' }}
            </span>
          </el-tag>
          <div v-if="devices.length === 0 && !devicesLoading" class="empty-hint">暂无设备</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.detection-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);

  h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 16px;
  }
}

.status-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;

  &.is-running {
    border-color: rgba(94, 196, 158, 0.3);
    background: linear-gradient(135deg, var(--card-bg) 0%, rgba(94, 196, 158, 0.03) 100%);
  }
}

.running-indicator {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--bg-elevated);
  overflow: hidden;

  .running-bar {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    width: 30%;
    background: linear-gradient(90deg, transparent, var(--success-color), transparent);
    animation: runningAnimation 1.5s ease-in-out infinite;
  }
}

@keyframes runningAnimation {
  0% {
    left: -30%;
  }
  100% {
    left: 100%;
  }
}

.status-top {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.status-info {
  flex: 1;

  .status-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }

  h2 {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
  }

  p {
    color: var(--text-muted);
    font-size: 14px;
    margin: 0;
  }

  .status-badge-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
}

.anomaly-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(224, 168, 84, 0.12);
  border: 1px solid rgba(224, 168, 84, 0.3);
  color: var(--warning-color);
  font-weight: 500;
  font-size: 12px;
  animation: pulse-warning 2s ease-in-out infinite;

  .el-icon {
    font-size: 12px;
  }
}

@keyframes pulse-warning {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.status-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-muted);
  flex-wrap: wrap;

  .status-updated, .running-time {
    display: flex;
    align-items: center;
    gap: 4px;

    .el-icon {
      font-size: 14px;
    }
  }

  .running-time {
    color: var(--success-color);
    font-family: var(--font-mono);
  }
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  border-radius: 999px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  font-weight: 500;
  font-size: 12px;
  transition: all 0.3s ease;

  .badge-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
    transition: all 0.3s ease;
  }

  &.is-active {
    background: rgba(94, 196, 158, 0.1);
    border-color: rgba(94, 196, 158, 0.2);
    color: var(--success-color);

    .badge-dot {
      background: var(--success-color);
      box-shadow: 0 0 6px var(--success-color);
      animation: badge-pulse 1.5s ease-in-out infinite;
    }
  }
}

@keyframes badge-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.3);
    opacity: 0.7;
  }
}

.status-updated {
  font-size: 12px;
}

.status-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

// 设备 Tag 标签选择区域
.device-tags-section {
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
  margin-top: 4px;
}

.device-tags-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.device-tags-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.device-tags-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.device-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-height: 40px;

  .empty-hint {
    width: 100%;
    text-align: center;
    color: var(--text-muted);
    padding: 12px;
    font-size: 13px;
  }
}

.device-tag {
  cursor: pointer;
  transition: all 0.25s ease;
  border-radius: 20px !important;
  padding: 8px 16px !important;
  height: auto !important;
  display: inline-flex;
  align-items: center;
  gap: 6px;

  .tag-icon {
    font-size: 14px;
  }

  .tag-name {
    font-size: 13px;
  }

  .tag-status {
    font-size: 10px;
    margin-left: 2px;
    
    &.online {
      color: var(--success-color);
    }
    &.warning {
      color: var(--warning-color);
      animation: blink-warning 1s ease-in-out infinite;
    }
    &.offline {
      color: var(--text-muted);
    }
  }

  &:hover:not(.is-offline) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }

  &.is-selected {
    transform: scale(1.02);
    box-shadow: 0 2px 8px rgba(var(--primary-rgb), 0.3);
  }

  &.is-offline {
    cursor: not-allowed;
    opacity: 0.6;
  }

  // 告警设备特殊样式
  &.is-warning {
    background: rgba(224, 168, 84, 0.15) !important;
    border-color: var(--warning-color) !important;
    color: var(--warning-color) !important;
    animation: pulse-border 2s ease-in-out infinite;

    // 告警设备选中状态 - 深色填充
    &.is-selected {
      background: var(--warning-color) !important;
      color: #fff !important;
      animation: none;
      box-shadow: 0 2px 8px rgba(224, 168, 84, 0.4);

      .tag-status.warning {
        color: #fff;
        animation: none;
      }
    }
  }
}

@keyframes blink-warning {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

@keyframes pulse-border {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(224, 168, 84, 0.4);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(224, 168, 84, 0.1);
  }
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-height: 110px;
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;

  &:nth-child(1) { animation-delay: 0.05s; }
  &:nth-child(2) { animation-delay: 0.1s; }
  &:nth-child(3) { animation-delay: 0.15s; }
  &:nth-child(4) { animation-delay: 0.2s; }
}

.metric-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);

  &.danger {
    color: var(--danger-color);
  }
}

.metric-label {
  font-size: 13px;
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .status-top {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}
</style>