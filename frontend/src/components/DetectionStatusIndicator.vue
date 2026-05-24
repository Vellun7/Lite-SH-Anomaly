<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getContinuousStatus, toggleContinuousDetection, type ContinuousDetectionStatus } from '@/api/detection'
import { VideoPause, VideoPlay, Warning, CircleCheck } from '@element-plus/icons-vue'

const router = useRouter()

// 检测状态
const isRunning = ref(false)
const totalDetections = ref(0)
const totalAnomalies = ref(0)
const lastUpdatedAt = ref<string | null>(null)
const loading = ref(false)
const toggling = ref(false) // 切换中状态

// 轮询定时器
let statusPoller: ReturnType<typeof setInterval> | null = null

// 运行时长
const runningDuration = ref('')
const startedAt = ref<string | null>(null)
let durationTimer: ReturnType<typeof setInterval> | null = null

// 计算运行时长
const updateDuration = () => {
  if (!startedAt.value || !isRunning.value) {
    runningDuration.value = ''
    return
  }
  const start = new Date(startedAt.value).getTime()
  if (Number.isNaN(start)) {
    runningDuration.value = ''
    return
  }
  const diff = Date.now() - start
  const hours = Math.floor(diff / 3600000)
  const minutes = Math.floor((diff % 3600000) / 60000)
  const seconds = Math.floor((diff % 60000) / 1000)
  
  if (hours > 0) {
    runningDuration.value = `${hours}h ${minutes}m`
  } else if (minutes > 0) {
    runningDuration.value = `${minutes}m ${seconds}s`
  } else {
    runningDuration.value = `${seconds}s`
  }
}

// 加载状态
const loadStatus = async () => {
  try {
    const res = await getContinuousStatus()
    const data = (res.data as any).data || res.data
    isRunning.value = data.enabled && data.is_running
    totalDetections.value = data.total_detections || 0
    totalAnomalies.value = data.total_anomalies || 0
    startedAt.value = data.started_at || null
    lastUpdatedAt.value = data.updated_at || null
    updateDuration()
  } catch (error) {
    console.error('获取检测状态失败:', error)
  }
}

// 切换检测状态
const toggleDetection = async (e: Event) => {
  e.stopPropagation() // 阻止冒泡，不触发跳转
  
  if (toggling.value) return
  toggling.value = true
  
  try {
    const newState = !isRunning.value
    const res = await toggleContinuousDetection({
      enabled: newState,
      interval: 60, // 默认60秒（1分钟）
      target_devices: []
    })
    const data = (res.data as any).data || res.data
    isRunning.value = data.enabled && data.is_running
    totalDetections.value = data.total_detections || 0
    totalAnomalies.value = data.total_anomalies || 0
    
    if (isRunning.value) {
      ElMessage.success('持续检测已启动')
    } else {
      ElMessage.info(`持续检测已停止，共检测 ${totalDetections.value} 次`)
    }
    
    // 刷新状态
    await loadStatus()
  } catch (error) {
    console.error('切换检测状态失败:', error)
    ElMessage.error('操作失败，请重试')
  } finally {
    toggling.value = false
  }
}

// 状态文本
const statusText = computed(() => {
  if (isRunning.value) {
    return '检测运行中'
  }
  return '检测已停止'
})

// 跳转到检测页面
const goToDetection = () => {
  router.push('/detection')
}

// 启动轮询
const startPolling = () => {
  stopPolling()
  statusPoller = setInterval(loadStatus, 5000)
  durationTimer = setInterval(updateDuration, 1000)
}

// 停止轮询
const stopPolling = () => {
  if (statusPoller) {
    clearInterval(statusPoller)
    statusPoller = null
  }
  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }
}

onMounted(() => {
  loadStatus()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

// 暴露刷新方法供外部调用
defineExpose({
  refresh: loadStatus
})
</script>

<template>
  <div 
    class="detection-status-indicator" 
    :class="{ 'is-running': isRunning, 'has-anomaly': totalAnomalies > 0 && isRunning }"
    @click="goToDetection"
    :title="isRunning ? `运行时长: ${runningDuration}\n检测: ${totalDetections} 次\n异常: ${totalAnomalies} 次` : '点击前往检测页面'"
  >
    <!-- 状态指示灯 -->
    <div class="status-light">
      <div class="light-core"></div>
      <div v-if="isRunning" class="light-pulse"></div>
    </div>

    <!-- 状态信息 -->
    <div class="status-info">
      <div class="status-text">{{ statusText }}</div>
      <div v-if="isRunning" class="status-stats">
        <span class="stat-item">
          <el-icon><CircleCheck /></el-icon>
          {{ totalDetections }}
        </span>
        <span v-if="totalAnomalies > 0" class="stat-item anomaly">
          <el-icon><Warning /></el-icon>
          {{ totalAnomalies }}
        </span>
        <span v-if="runningDuration" class="stat-duration">
          {{ runningDuration }}
        </span>
      </div>
    </div>

    <!-- 运行图标 - 点击切换 -->
    <div 
      class="status-icon" 
      :class="{ 'is-toggling': toggling }"
      @click="toggleDetection"
      :title="isRunning ? '点击停止检测' : '点击启动检测'"
    >
      <el-icon v-if="toggling" class="is-loading"><VideoPlay /></el-icon>
      <el-icon v-else-if="isRunning"><VideoPlay /></el-icon>
      <el-icon v-else><VideoPause /></el-icon>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.detection-status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 140px;

  &:hover {
    background: var(--bg-hover);
    border-color: rgba(255, 255, 255, 0.15);
    transform: translateY(-1px);
  }

  &.is-running {
    border-color: rgba(94, 196, 158, 0.3);
    background: rgba(94, 196, 158, 0.08);

    &:hover {
      border-color: rgba(94, 196, 158, 0.5);
      background: rgba(94, 196, 158, 0.12);
    }

    .status-light .light-core {
      background: var(--success-color);
      box-shadow: 0 0 8px rgba(94, 196, 158, 0.6);
    }

    .status-text {
      color: var(--success-color);
    }

    .status-icon {
      color: var(--success-color);
    }
  }

  &.has-anomaly {
    border-color: rgba(224, 168, 84, 0.4);
    background: rgba(224, 168, 84, 0.08);

    &:hover {
      border-color: rgba(224, 168, 84, 0.6);
      background: rgba(224, 168, 84, 0.12);
    }

    .status-light .light-core {
      background: var(--warning-color);
      box-shadow: 0 0 8px rgba(224, 168, 84, 0.6);
    }

    .status-light .light-pulse {
      border-color: rgba(224, 168, 84, 0.6);
    }
  }
}

.status-light {
  position: relative;
  width: 12px;
  height: 12px;
  flex-shrink: 0;

  .light-core {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
    transform: translate(-50%, -50%);
    transition: all 0.3s ease;
  }

  .light-pulse {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    border: 2px solid rgba(94, 196, 158, 0.6);
    transform: translate(-50%, -50%);
    animation: pulse 2s ease-out infinite;
  }
}

@keyframes pulse {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(2.5);
    opacity: 0;
  }
}

.status-info {
  flex: 1;
  min-width: 0;

  .status-text {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    white-space: nowrap;
    transition: color 0.3s ease;
  }

  .status-stats {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 2px;

    .stat-item {
      display: flex;
      align-items: center;
      gap: 2px;
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);

      .el-icon {
        font-size: 10px;
      }

      &.anomaly {
        color: var(--warning-color);
      }
    }

    .stat-duration {
      font-size: 10px;
      color: var(--text-muted);
      padding: 1px 6px;
      background: var(--bg-surface);
      border-radius: 4px;
      font-family: var(--font-mono);
    }
  }
}

.status-icon {
  color: var(--text-muted);
  font-size: 16px;
  transition: all 0.3s ease;
  padding: 6px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: rgba(255, 255, 255, 0.1);
    transform: scale(1.1);
  }

  &:active {
    transform: scale(0.95);
  }

  &.is-toggling {
    opacity: 0.6;
    pointer-events: none;
    
    .is-loading {
      animation: spin 1s linear infinite;
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

// 深色模式下的呼吸动画
.is-running .status-icon:not(:hover) {
  animation: breathe 2s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
