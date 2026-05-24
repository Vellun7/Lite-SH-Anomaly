import { ref, computed, onUnmounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { detectSingle, getContinuousStatus, toggleContinuousDetection } from '@/api/detection'
import { getDevices, type Device } from '@/api/device'

/**
 * 检测功能组合式函数
 * 可在 HomeView.vue 和 DetectionView.vue 中复用
 */
export function useDetection() {
  const devices = ref<Device[]>([])
  const selectedDevices = ref<string[]>([])
  const isDetecting = ref(false)
  const devicesLoading = ref(false)

  // 持续检测相关
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

  // 异常率
  const anomalyRate = computed(() => {
    if (totalDetections.value === 0) {
      return 0
    }
    return Number(((totalAnomalies.value / totalDetections.value) * 100).toFixed(1))
  })

  // 检测速率
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

  // 格式化更新时间
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

  // 生成模拟流量数据
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

    ElNotification({
      title: '⚠️ 异常告警',
      message: `设备 ${device.name}(${typeName}) 检测到异常：${attackText}，置信度 ${(confidence * 100).toFixed(0)}%`,
      type: 'warning',
      duration: 10000,
      position: 'top-right'
    })

    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('智能家居异常告警', {
        body: `设备 ${device.name} 检测到 ${attackText}`,
        icon: '/favicon.ico',
        tag: `anomaly-${device.device_id}-${Date.now()}`
      })
    }

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

      if (!isRunning) {
        isDetecting.value = false
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

  // 启动状态轮询
  const startStatusPolling = () => {
    stopStatusPolling()
    stopLightStatusPolling()
    statusPoller = setInterval(async () => {
      await loadContinuousStatus()
    }, 3000)
  }

  // 停止状态轮询
  const stopStatusPolling = () => {
    if (statusPoller) {
      clearInterval(statusPoller)
      statusPoller = null
    }
  }

  // 启动轻量状态轮询
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

  // 切换持续检测模式
  const toggleContinuousMode = async () => {
    try {
      const targetDeviceIds = selectedDevices.value.length > 0
        ? selectedDevices.value
        : []

      const res = await toggleContinuousDetection({
        enabled: continuousMode.value,
        interval: detectionInterval.value,
        target_devices: targetDeviceIds
      })
      const data = (res.data as any).data || res.data

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
        isDetecting.value = false
        stopStatusPolling()
        stopDurationTimer()
        startLightStatusPolling()
        ElMessage.info(`持续检测已停止，共检测 ${totalDetections.value} 次，发现 ${totalAnomalies.value} 个异常`)
      }
    } catch (error) {
      console.error('切换持续检测失败:', error)
      ElMessage.error('操作失败，请重试')
      continuousMode.value = !continuousMode.value
    }
  }

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

  // 获取结果类型
  const getResultType = (isAnomaly: boolean) => {
    return isAnomaly ? 'danger' : 'success'
  }

  // 获取攻击类型文本
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

  // 初始化检测功能
  const initDetection = async () => {
    await loadDevices()
    await loadContinuousStatus()

    startLightStatusPolling()
  }

  // 清理检测功能
  const cleanupDetection = () => {
    stopStatusPolling()
    stopLightStatusPolling()
    stopDurationTimer()
  }

  // 组件卸载时清理
  onUnmounted(() => {
    cleanupDetection()
  })

  return {
    // 状态
    devices,
    selectedDevices,
    isDetecting,
    devicesLoading,
    continuousMode,
    detectionInterval,
    totalDetections,
    totalAnomalies,
    startedAt,
    lastUpdatedAt,
    runningSeconds,

    // 计算属性
    formattedRunningTime,
    anomalyRate,
    detectionRate,
    formattedUpdatedAt,

    // 方法
    loadDevices,
    toggleDeviceSelection,
    getDeviceTagType,
    startDetection,
    toggleContinuousMode,
    loadContinuousStatus,
    initDetection,
    cleanupDetection,

    // 工具方法
    getResultType,
    getAttackTypeText,
    deviceTypeIcons,
    deviceTypeNames
  }
}
