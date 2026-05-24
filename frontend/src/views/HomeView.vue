<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import { deviceTypeIcons } from '@/mock/data'
import { getDashboardStats, getDetectionStats, type DashboardStats } from '@/api/dashboard'
import { getDevices, type Device } from '@/api/device'
import { getAlerts, updateAlertStatus, type Alert } from '@/api/log'
import { detectSingle, getContinuousStatus, toggleContinuousDetection } from '@/api/detection'
import { ElMessage, ElNotification } from 'element-plus'
import { Warning, Clock, Timer } from '@element-plus/icons-vue'

const router = useRouter()
const themeStore = useThemeStore()

// ==========================================
// 统计数据
// ==========================================
const stats = ref<DashboardStats>({
  totalDevices: 0,
  onlineDevices: 0,
  offlineDevices: 0,
  warningDevices: 0,
  todayDetections: 0,
  todayAnomalies: 0,
  anomalyRate: 0,
  avgLatency: 0,
  accuracy: 94
})

// 设备列表
const devices = ref<Device[]>([])

// 告警列表
const alerts = ref<Alert[]>([])

// 加载状态
const loading = ref(false)

// 图表引用
const threatChartRef = ref<HTMLElement>()
const trendChartRef = ref<HTMLElement>()
const overviewChartRef = ref<HTMLElement>()

// 威胁类型分布数据
const threatTypes = ref<Array<{ name: string; value: number; color: string }>>([])

// 检测趋势数据
const detectionTrend = ref<{ times: string[]; normal: number[]; anomaly: number[] }>({
  times: [],
  normal: [],
  anomaly: []
})

// 今日检测概览数据
const todayOverview = ref({
  total: 0,
  normal: 0,
  anomaly: 0,
  anomalyRate: 0
})

// ==========================================
// 检测控制相关（从 DetectionView 合并）
// ==========================================
const selectedDevices = ref<string[]>([])
const isDetecting = ref(false)
const devicesLoading = ref(false)
const continuousMode = ref(false)
const detectionInterval = ref(60)
const totalDetections = ref(0)
const totalAnomalies = ref(0)
const startedAt = ref<string | null>(null)
const lastUpdatedAt = ref<string | null>(null)
const runningSeconds = ref(0)

let statusPoller: ReturnType<typeof setInterval> | null = null
let lightStatusPoller: ReturnType<typeof setInterval> | null = null
let durationTimer: ReturnType<typeof setInterval> | null = null
let deviceStatusPoller: ReturnType<typeof setInterval> | null = null

// 设备类型图标
const detectionDeviceIcons: Record<string, string> = {
  camera: '📷',
  door_lock: '🔐',
  sensor: '🌡️',
  gateway: '📶',
  other: '📱'
}

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

// ==========================================
// 图表配色（根据主题动态变化）
// ==========================================
const chartColors = () => {
  const dark = themeStore.isDark()
  return {
    axisLine: dark ? 'rgba(255,255,255,0.08)' : '#e4e7ed',
    axisLabel: dark ? '#636d85' : '#909399',
    splitLine: dark ? 'rgba(255,255,255,0.05)' : '#e4e7ed',
    legend: dark ? '#a0a8bf' : '#606266',
    emptyText: dark ? '#636d85' : '#909399',
    pieBorder: dark ? '#1c2030' : '#ffffff'
  }
}

// ==========================================
// 加载首页数据
// ==========================================
const loadDashboardData = async () => {
  loading.value = true
  try {
    // 并行加载所有数据
    const [statsData, devicesRes, alertsRes, detectionStatsRes] = await Promise.all([
      getDashboardStats(),
      getDevices({ page_size: 10 }),
      getAlerts({ page_size: 5, status: 'pending' }),
      getDetectionStats(7)
    ])

    // 统计数据
    stats.value = statsData

    // 设备列表
    const deviceData = (devicesRes.data as any).data || devicesRes.data
    devices.value = deviceData.results || []

    // 告警列表
    const alertData = (alertsRes.data as any).data || alertsRes.data
    alerts.value = alertData.results || []

    // 检测统计（用于图表）
    const detectionStats = (detectionStatsRes.data as any).data || detectionStatsRes.data

    // 处理威胁类型分布
    const attackColors: Record<string, string> = {
      ddos: '#e06060',
      port_scan: '#e0a854',
      unauthorized: '#9b7dcf',
      malformed: '#5b8def',
      unknown: '#636d85',
      normal: '#5ec49e'
    }
    const attackNames: Record<string, string> = {
      ddos: 'DDoS攻击',
      port_scan: '端口扫描',
      unauthorized: '越权访问',
      malformed: '异常流量',
      unknown: '未知威胁',
      normal: '正常'
    }
    threatTypes.value = (detectionStats.attack_distribution || []).map((item: any) => ({
      name: attackNames[item.attack_type] || item.attack_type,
      value: item.count,
      color: attackColors[item.attack_type] || '#607D8B'
    }))

    // 处理检测趋势
    const dailyTrend = detectionStats.daily_trend || []
    detectionTrend.value = {
      times: dailyTrend.map((item: any) => item.date),
      normal: dailyTrend.map((item: any) => item.total - item.anomaly),
      anomaly: dailyTrend.map((item: any) => item.anomaly)
    }

    // 处理今日检测概览
    todayOverview.value = {
      total: detectionStats.total || 0,
      normal: (detectionStats.total || 0) - (detectionStats.anomaly || 0),
      anomaly: detectionStats.anomaly || 0,
      anomalyRate: detectionStats.anomaly_rate || 0
    }

    // 初始化图表
    setTimeout(() => {
      initThreatChart()
      initTrendChart()
      initOverviewChart()
    }, 100)

  } catch (error) {
    console.error('加载首页数据失败:', error)
  } finally {
    loading.value = false
  }
}

// 处理告警
const handleResolveAlert = async (alert: Alert) => {
  try {
    await updateAlertStatus(alert.id, 'resolved')
    ElMessage.success('告警已处理')
    // 刷新告警列表
    await loadDashboardData()
  } catch (error) {
    console.error('处理告警失败:', error)
    ElMessage.error('处理告警失败')
  }
}

// ==========================================
// 加载设备列表（检测用）
// ==========================================
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

// ==========================================
// 设备选择
// ==========================================
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

const getDeviceTagType = (device: Device) => {
  if (device.status === 'offline') return 'info'
  if (device.status === 'warning') return 'warning'
  return selectedDevices.value.includes(device.device_id) ? 'primary' : ''
}

// ==========================================
// 检测逻辑
// ==========================================
const generateTrafficData = (device: Device) => {
  const isNormalTraffic = Math.random() < 0.7

  if (isNormalTraffic) {
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

const requestNotificationPermission = async () => {
  if ('Notification' in window && Notification.permission === 'default') {
    await Notification.requestPermission()
  }
}

const sendAlertNotification = (device: Device, attackType: string, confidence: number) => {
  const attackText = getAttackTypeText(attackType)

  // 页面内通知
  ElNotification({
    title: '⚠️ 异常告警',
    message: `设备 ${device.name} 检测到异常：${attackText}，置信度 ${(confidence * 100).toFixed(0)}%`,
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

// ==========================================
// 持续检测
// ==========================================
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

const startStatusPolling = () => {
  stopStatusPolling()
  stopLightStatusPolling()
  // 每3秒刷新检测状态
  statusPoller = setInterval(async () => {
    await loadContinuousStatus()
  }, 3000)
}

const stopStatusPolling = () => {
  if (statusPoller) {
    clearInterval(statusPoller)
    statusPoller = null
  }
}

const startLightStatusPolling = () => {
  stopLightStatusPolling()
  lightStatusPoller = setInterval(async () => {
    await loadContinuousStatus()
  }, 15000)
}

const stopLightStatusPolling = () => {
  if (lightStatusPoller) {
    clearInterval(lightStatusPoller)
    lightStatusPoller = null
  }
}

const startDeviceStatusPolling = () => {
  stopDeviceStatusPolling()
  deviceStatusPoller = setInterval(async () => {
    await refreshDeviceStatus()
  }, 30000)
}

const stopDeviceStatusPolling = () => {
  if (deviceStatusPoller) {
    clearInterval(deviceStatusPoller)
    deviceStatusPoller = null
  }
}

const toggleContinuousMode = async () => {
  try {
    const res = await toggleContinuousDetection({
      enabled: continuousMode.value,
      interval: detectionInterval.value,
      target_devices: [],
    })
    const data = (res.data as any).data || res.data

    // 根据后端返回的实际状态更新本地状态
    const isRunning = data.enabled && data.is_running
    continuousMode.value = isRunning
    totalDetections.value = data.total_detections || 0
    totalAnomalies.value = data.total_anomalies || 0

    if (isRunning) {
      await requestNotificationPermission()
      ElMessage.success(`检测已启动，每 ${detectionInterval.value} 秒检测全部设备`)
      startStatusPolling()
      startDurationTimer()
    } else {
      // 检测停止时，确保 isDetecting 也重置
      isDetecting.value = false
      stopStatusPolling()
      stopDurationTimer()
      startLightStatusPolling()
      ElMessage.info(`检测已停止，共检测 ${totalDetections.value} 次，发现 ${totalAnomalies.value} 个异常`)
    }
  } catch (error) {
    console.error('切换检测失败:', error)
    ElMessage.error('操作失败，请重试')
    // 恢复开关状态
    continuousMode.value = !continuousMode.value
  }
}

// ==========================================
// 工具函数
// ==========================================
const formatTime = (timestamp: string) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString()
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

const getStatusClass = (status: string) => {
  if (status === 'online') return 'online'
  if (status === 'warning') return 'warning'
  return 'offline'
}

const getAlertLevelClass = (level: string) => {
  const map: Record<string, string> = {
    critical: 'danger',
    danger: 'danger',
    high: 'danger',
    warning: 'warning',
    medium: 'warning',
    info: 'info',
    low: 'info'
  }
  return map[level] || 'info'
}

const getAlertLevelText = (level: string) => {
  const map: Record<string, string> = {
    critical: '严重',
    danger: '高危',
    high: '高危',
    warning: '中危',
    medium: '中危',
    info: '低危',
    low: '低危'
  }
  return map[level] || level
}

const getDeviceIcon = (deviceType: string) => {
  const icons: Record<string, string> = {
    camera: '📷',
    doorlock: '🔐',
    sensor: '🌡️',
    socket: '🔌',
    light: '💡',
    speaker: '🔊',
    thermostat: '🌡️',
    router: '📶',
    ...deviceTypeIcons
  }
  return icons[deviceType] || '📱'
}

// ==========================================
// 图表初始化
// ==========================================
const initThreatChart = () => {
  if (!threatChartRef.value) return
  const chart = echarts.init(threatChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  chart.setOption({ backgroundColor: 'transparent' })

  // 如果没有数据，显示空状态
  if (threatTypes.value.length === 0) {
    chart.setOption({
      title: {
        text: '暂无威胁数据',
        left: 'center',
        top: 'center',
        textStyle: { color: chartColors().emptyText, fontSize: 14 }
      }
    })
    return
  }

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: chartColors().legend }
    },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 8,
        borderColor: chartColors().pieBorder,
        borderWidth: 2
      },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' }
      },
      data: threatTypes.value.map(item => ({
        value: item.value,
        name: item.name,
        itemStyle: { color: item.color }
      }))
    }]
  })
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  const chart = echarts.init(trendChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  chart.setOption({ backgroundColor: 'transparent' })

  // 如果没有数据，显示空状态
  if (detectionTrend.value.times.length === 0) {
    chart.setOption({
      title: {
        text: '暂无检测数据',
        left: 'center',
        top: 'center',
        textStyle: { color: chartColors().emptyText, fontSize: 14 }
      }
    })
    return
  }

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: ['正常检测', '异常检测'],
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: detectionTrend.value.times,
      axisLine: { lineStyle: { color: chartColors().axisLine } },
      axisLabel: {
        color: chartColors().axisLabel,
        interval: 0,
        rotate: 0,
        fontSize: 11
      }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: chartColors().splitLine, type: 'dashed' } },
      axisLabel: { color: chartColors().axisLabel }
    },
    series: [
      {
        name: '正常检测',
        type: 'line',
        smooth: true,
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(94, 196, 158, 0.25)' },
            { offset: 1, color: 'rgba(94, 196, 158, 0.02)' }
          ])
        },
        lineStyle: { color: '#5ec49e', width: 2 },
        data: detectionTrend.value.normal
      },
      {
        name: '异常检测',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#e06060', width: 2 },
        itemStyle: { color: '#e06060' },
        data: detectionTrend.value.anomaly
      }
    ]
  })
}

const initOverviewChart = () => {
  if (!overviewChartRef.value) return
  const chart = echarts.init(overviewChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  chart.setOption({ backgroundColor: 'transparent' })

  const { total, normal, anomaly, anomalyRate } = todayOverview.value

  // 如果没有数据，显示空状态
  if (total === 0) {
    chart.setOption({
      title: {
        text: '暂无检测数据',
        left: 'center',
        top: 'center',
        textStyle: { color: chartColors().emptyText, fontSize: 14 }
      }
    })
    return
  }

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      textStyle: { color: chartColors().legend }
    },
    series: [
      {
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 8,
          borderColor: chartColors().pieBorder,
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'center',
          formatter: () => `{total|${total}}\n{label|今日检测}`,
          rich: {
            total: {
              fontSize: 28,
              fontWeight: 'bold',
              color: themeStore.isDark() ? '#e0e6f0' : '#2c3e50',
              fontFamily: 'var(--font-mono)'
            },
            label: {
              fontSize: 12,
              color: chartColors().legend,
              padding: [4, 0, 0, 0]
            }
          }
        },
        emphasis: {
          label: { show: true }
        },
        labelLine: { show: false },
        data: [
          {
            value: normal,
            name: '正常',
            itemStyle: { color: '#5ec49e' }
          },
          {
            value: anomaly,
            name: '异常',
            itemStyle: { color: '#e06060' }
          }
        ]
      }
    ]
  })
}

// ==========================================
// 生命周期
// ==========================================
onMounted(async () => {
  loadDashboardData()
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

// 监听主题变化，重新初始化图表
watch(() => themeStore.mode, () => {
  // 销毁旧图表
  if (threatChartRef.value) {
    echarts.dispose(threatChartRef.value)
  }
  if (trendChartRef.value) {
    echarts.dispose(trendChartRef.value)
  }
  if (overviewChartRef.value) {
    echarts.dispose(overviewChartRef.value)
  }
  // 重新初始化
  setTimeout(() => {
    initThreatChart()
    initTrendChart()
    initOverviewChart()
  }, 100)
})
</script>

<template>
  <div class="home-view">
    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon devices">
          <el-icon size="24"><Monitor /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-number">{{ stats.totalDevices }}</span>
          <span class="stat-title">设备总数</span>
        </div>
        <div class="stat-extra">
          <span class="online">{{ stats.onlineDevices }} 在线</span>
          <span class="warning" v-if="stats.warningDevices">{{ stats.warningDevices }} 告警</span>
          <span class="offline">{{ stats.offlineDevices }} 离线</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon detections">
          <el-icon size="24"><DataLine /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-number">{{ stats.todayDetections.toLocaleString() }}</span>
          <span class="stat-title">今日检测</span>
        </div>
        <div class="stat-extra">
          <span class="success">实时监控中</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon anomalies">
          <el-icon size="24"><WarningFilled /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-number">{{ stats.todayAnomalies }}</span>
          <span class="stat-title">异常告警</span>
        </div>
        <div class="stat-extra">
          <span class="warning">异常率 {{ stats.anomalyRate }}%</span>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon performance">
          <el-icon size="24"><Timer /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-number">{{ stats.avgLatency }}ms</span>
          <span class="stat-title">平均延迟</span>
        </div>
        <div class="stat-extra">
          <span class="success">性能优秀</span>
        </div>
      </div>
    </div>

    <!-- 实时检测控制区 -->
    <div class="card detection-card" :class="{ 'is-running': continuousMode }">
      <!-- 运行状态指示条 -->
      <div v-if="continuousMode" class="running-indicator">
        <div class="running-bar"></div>
      </div>

      <div class="detection-header">
        <div class="detection-info">
          <div class="detection-title-row">
            <h3>实时检测</h3>
            <div class="status-badge-group">
              <span class="status-badge" :class="{ 'is-active': continuousMode }">
                <span class="badge-dot"></span>
                {{ continuousMode ? '检测运行中' : '检测已停止' }}
              </span>
              <span v-if="continuousMode && totalAnomalies > 0" class="anomaly-badge">
                <el-icon><Warning /></el-icon>
                {{ totalAnomalies }} 个异常待处理
              </span>
            </div>
          </div>
          <p>监控设备流量，实时检测异常行为</p>
          <div class="detection-meta">
            <span class="meta-item">
              <el-icon><Clock /></el-icon>
              最近更新：{{ formattedUpdatedAt }}
            </span>
            <span v-if="continuousMode && startedAt" class="meta-item running-time">
              <el-icon><Timer /></el-icon>
              运行时长：{{ formattedRunningTime }}
            </span>
          </div>
        </div>
        <div class="detection-actions">
          <el-switch
            v-model="continuousMode"
            :active-text="continuousMode ? '开启检测' : '关闭检测'"
            @change="toggleContinuousMode"
          />
        </div>
      </div>

      <!-- 检测指标 -->
      <div class="detection-metrics">
        <div class="metric-item">
          <span class="metric-value">{{ totalDetections }}</span>
          <span class="metric-label">累计检测</span>
        </div>
        <div class="metric-item">
          <span class="metric-value danger">{{ totalAnomalies }}</span>
          <span class="metric-label">累计异常</span>
        </div>
        <div class="metric-item">
          <span class="metric-value">{{ detectionRate }}</span>
          <span class="metric-label">检测速率(次/分)</span>
        </div>
        <div class="metric-item">
          <span class="metric-value">{{ anomalyRate }}%</span>
          <span class="metric-label">异常占比</span>
        </div>
      </div>

      <!-- 检测设备列表 -->
      <div class="device-tags-section">
        <div class="device-tags-header">
          <span class="device-tags-label">检测范围</span>
          <span class="device-tags-hint">全部设备</span>
        </div>
        <div class="device-tags-list" v-loading="devicesLoading">
          <el-tag
            v-for="device in devices"
            :key="device.device_id"
            :type="device.status === 'offline' ? 'info' : device.status === 'warning' ? 'warning' : 'primary'"
            effect="plain"
            :class="{
              'device-tag': true,
              'is-offline': device.status === 'offline',
              'is-warning': device.status === 'warning'
            }"
            size="large"
          >
            <span class="tag-icon">{{ detectionDeviceIcons[device.device_type] || '📱' }}</span>
            <span class="tag-name">{{ device.name }}</span>
            <span class="tag-status" :class="device.status">
              {{ device.status === 'online' ? '●' : device.status === 'warning' ? '◐' : '○' }}
            </span>
          </el-tag>
          <div v-if="devices.length === 0 && !devicesLoading" class="empty-hint">暂无设备</div>
        </div>
      </div>
    </div>

    <!-- 主要内容区 -->
    <div class="main-grid">
      <!-- 设备状态 -->
      <div class="card device-card">
        <div class="card-header">
          <h3>设备状态</h3>
          <el-button text type="primary" @click="router.push('/devices')">查看全部</el-button>
        </div>
        <div class="device-list" v-loading="loading">
          <div v-if="devices.length === 0" class="empty-state">暂无设备数据</div>
          <div
            v-for="device in devices"
            :key="device.device_id"
            class="device-item"
          >
            <div class="device-icon">
              {{ getDeviceIcon(device.device_type) }}
            </div>
            <div class="device-info">
              <span class="device-name">{{ device.name }}</span>
              <span class="device-location">{{ device.location || device.ip_address }}</span>
            </div>
            <div :class="['status-tag', getStatusClass(device.status)]">
              {{ device.status === 'online' ? '在线' : device.status === 'warning' ? '告警' : '离线' }}
            </div>
          </div>
        </div>
      </div>

      <!-- 威胁分布 -->
      <div class="card threat-card">
        <div class="card-header">
          <h3>威胁类型分布</h3>
          <span class="card-subtitle">近7天统计</span>
        </div>
        <div ref="threatChartRef" class="chart-container"></div>
      </div>

      <!-- 检测趋势 -->
      <div class="card trend-card">
        <div class="card-header">
          <h3>检测趋势</h3>
          <span class="card-subtitle">近7天</span>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>

      <!-- 今日检测概览 -->
      <div class="card overview-card">
        <div class="card-header">
          <h3>今日检测概览</h3>
          <span class="card-subtitle">实时</span>
        </div>
        <div class="overview-content">
          <div ref="overviewChartRef" class="overview-chart"></div>
          <div class="overview-stats">
            <div class="stat-row">
              <div class="stat-dot normal"></div>
              <span class="stat-label">正常</span>
              <span class="stat-value">{{ todayOverview.normal }}</span>
            </div>
            <div class="stat-row">
              <div class="stat-dot anomaly"></div>
              <span class="stat-label">异常</span>
              <span class="stat-value">{{ todayOverview.anomaly }}</span>
            </div>
            <div class="stat-row">
              <div class="stat-dot rate"></div>
              <span class="stat-label">异常率</span>
              <span class="stat-value">{{ todayOverview.anomalyRate.toFixed(1) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 最近告警 -->
      <div class="card alert-card">
        <div class="card-header">
          <h3>最近告警</h3>
          <el-button text type="primary" @click="router.push('/history')">查看全部</el-button>
        </div>
        <div class="alert-list" v-loading="loading">
          <div v-if="alerts.length === 0" class="empty-state">暂无告警</div>
          <div
            v-for="alert in alerts"
            :key="alert.id"
            class="alert-item"
          >
            <div :class="['alert-level', getAlertLevelClass(alert.level)]">
              {{ getAlertLevelText(alert.level) }}
            </div>
            <div class="alert-info">
              <div class="alert-title">
                <span class="alert-device">{{ alert.device_name || alert.device_id }}</span>
                <span class="alert-type">{{ getAttackTypeText(alert.attack_type) }}</span>
              </div>
              <div class="alert-meta">
                <span class="alert-time">{{ formatTime(alert.created_at) }}</span>
                <span class="alert-confidence">置信度: {{ (alert.confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
            <el-button
              v-if="alert.status === 'pending'"
              type="primary"
              size="small"
              @click="handleResolveAlert(alert)"
            >
              处理
            </el-button>
            <el-tag v-else type="success" size="small">已处理</el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.home-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

// ==========================================
// 统计卡片
// ==========================================
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: var(--shadow-light);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;

  &:nth-child(1) { animation-delay: 0.05s; }
  &:nth-child(2) { animation-delay: 0.1s; }
  &:nth-child(3) { animation-delay: 0.15s; }
  &:nth-child(4) { animation-delay: 0.2s; }

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-medium);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;

    &.devices {
      background: linear-gradient(135deg, #5b8def, #4171d6);
      box-shadow: 0 4px 12px rgba(91, 141, 239, 0.2);
    }
    &.detections {
      background: linear-gradient(135deg, #5ec49e, #48a882);
      box-shadow: 0 4px 12px rgba(94, 196, 158, 0.2);
    }
    &.anomalies {
      background: linear-gradient(135deg, #e0a854, #c88f3a);
      box-shadow: 0 4px 12px rgba(224, 168, 84, 0.2);
    }
    &.performance {
      background: linear-gradient(135deg, #9b7dcf, #7e5fbf);
      box-shadow: 0 4px 12px rgba(155, 125, 207, 0.2);
    }
  }

  .stat-info {
    flex: 1;

    .stat-number {
      display: block;
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
      font-family: var(--font-mono);
    }

    .stat-title {
      font-size: 13px;
      color: var(--text-muted);
    }
  }

  .stat-extra {
    font-size: 12px;

    .online { color: var(--success-color); }
    .warning { color: var(--danger-color); margin-left: 8px; }
    .offline { color: var(--text-muted); margin-left: 8px; }
    .success { color: var(--success-color); }
  }
}

// ==========================================
// 实时检测控制区
// ==========================================
.detection-card {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);

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
  0% { left: -30%; }
  100% { left: 100%; }
}

.detection-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.detection-info {
  flex: 1;

  .detection-title-row {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }

  h3 {
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

  .detection-meta {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 12px;
    font-size: 13px;
    color: var(--text-muted);
    flex-wrap: wrap;

    .meta-item {
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
}

.status-badge-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
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
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.3); opacity: 0.7; }
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
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.detection-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

// 检测指标
.detection-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);

  .metric-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;

    .metric-value {
      font-size: 22px;
      font-weight: 700;
      color: var(--text-primary);
      font-family: var(--font-mono);

      &.danger {
        color: var(--danger-color);
      }
    }

    .metric-label {
      font-size: 12px;
      color: var(--text-muted);
    }
  }
}

// 设备 Tag 标签选择区域
.device-tags-section {
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
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

  &.is-warning {
    background: rgba(224, 168, 84, 0.15) !important;
    border-color: var(--warning-color) !important;
    color: var(--warning-color) !important;
    animation: pulse-border 2s ease-in-out infinite;

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
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(224, 168, 84, 0.4); }
  50% { box-shadow: 0 0 0 4px rgba(224, 168, 84, 0.1); }
}

// ==========================================
// 主要内容网格
// ==========================================
.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 16px;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
  animation-delay: 0.25s;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .card-subtitle {
      font-size: 12px;
      color: var(--text-muted);
    }

    :deep(.el-button) {
      color: var(--primary-color) !important;
    }
  }

  .empty-state {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-muted);
    font-size: 14px;
  }
}

// ==========================================
// 设备列表
// ==========================================
.device-card {
  .device-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 320px;
    overflow-y: auto;
  }

  .device-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: var(--bg-elevated);
    border: 1px solid transparent;
    border-radius: 10px;
    transition: all 0.2s ease;

    &:hover {
      background: var(--bg-hover);
      border-color: var(--border-color);
    }

    .device-icon {
      font-size: 22px;
      width: 38px;
      height: 38px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-surface);
      border-radius: 9px;
    }

    .device-info {
      flex: 1;

      .device-name {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: var(--text-primary);
      }

      .device-location {
        font-size: 12px;
        color: var(--text-muted);
      }
    }

    // 设备状态标签
    .online, .warning, .offline {
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
    }

    .online {
      color: var(--success-color);
      background: rgba(103, 194, 58, 0.1);
    }

    .warning {
      color: var(--danger-color);
      background: rgba(245, 108, 108, 0.1);
    }

    .offline {
      color: var(--text-muted);
      background: var(--bg-surface);
    }
  }
}

// ==========================================
// 图表容器
// ==========================================
.chart-container {
  height: 280px;
}

// ==========================================
// 今日检测概览
// ==========================================
.overview-card {
  .overview-content {
    display: flex;
    align-items: center;
    gap: 16px;
    height: 280px;
  }

  .overview-chart {
    flex: 1;
    height: 100%;
    min-width: 0;
  }

  .overview-stats {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-right: 8px;
    min-width: 100px;

    .stat-row {
      display: flex;
      align-items: center;
      gap: 10px;

      .stat-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;

        &.normal { background: #5ec49e; }
        &.anomaly { background: #e06060; }
        &.rate { background: #e0a854; }
      }

      .stat-label {
        font-size: 13px;
        color: var(--text-secondary);
        flex: 1;
      }

      .stat-value {
        font-size: 15px;
        font-weight: 600;
        color: var(--text-primary);
        font-family: var(--font-mono);
      }
    }
  }
}

// ==========================================
// 告警列表
// ==========================================
.alert-card {
  grid-column: span 2;

  .alert-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .alert-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    background: var(--bg-elevated);
    border: 1px solid transparent;
    border-radius: 10px;
    transition: all 0.2s ease;

    &:hover {
      border-color: var(--border-color);
      background: var(--bg-hover);
    }

    .alert-level {
      padding: 4px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.3px;

      &.danger {
        background: rgba(224, 96, 96, 0.12);
        color: var(--danger-color);
      }

      &.warning {
        background: rgba(224, 168, 84, 0.12);
        color: var(--warning-color);
      }

      &.info {
        background: rgba(107, 143, 199, 0.12);
        color: var(--info-color);
      }
    }

    .alert-info {
      flex: 1;

      .alert-title {
        display: flex;
        gap: 8px;
        margin-bottom: 4px;

        .alert-device {
          font-weight: 500;
          color: var(--text-primary);
          font-size: 13px;
        }

        .alert-type {
          color: var(--text-secondary);
          font-size: 13px;
        }
      }

      .alert-meta {
        font-size: 12px;
        color: var(--text-muted);
        display: flex;
        gap: 16px;
      }
    }
  }
}

// ==========================================
// 响应式
// ==========================================
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .main-grid {
    grid-template-columns: 1fr;
  }

  .alert-card {
    grid-column: span 1;
  }

  .detection-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .detection-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .detection-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .detection-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
