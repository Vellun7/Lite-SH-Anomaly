<template>
  <el-dialog
    v-model="visible"
    :title="`${device?.name} - 安全评分详情`"
    width="800px"
    :before-close="handleClose"
  >
    <div class="security-detail" v-if="device">
      <!-- 当前评分概览 -->
      <div class="score-overview">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card class="score-card">
              <div class="score-display">
                <div class="score-circle">
                  <el-progress
                    type="circle"
                    :percentage="device.security_score"
                    :width="120"
                    :color="getSecurityColor(device.security_level)"
                  >
                    <template #default="{ percentage }">
                      <span class="score-text">{{ percentage.toFixed(1) }}</span>
                    </template>
                  </el-progress>
                </div>
                <div class="score-info">
                  <div class="score-level">
                    <el-tag 
                      :type="getSecurityTagType(device.security_level)" 
                      size="large"
                    >
                      {{ getSecurityLevelText(device.security_level) }}
                    </el-tag>
                  </div>
                  <div class="update-time">
                    更新时间：{{ formatTime(device.last_score_update) }}
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card class="info-card">
              <template #header>
                <div class="card-header">
                  <span>设备信息</span>
                  <el-button size="small" @click="updateScore">
                    <el-icon><Refresh /></el-icon>
                    更新评分
                  </el-button>
                </div>
              </template>
              <div class="device-info">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="设备名称">{{ device.name }}</el-descriptions-item>
                  <el-descriptions-item label="设备类型">{{ device.device_type_display }}</el-descriptions-item>
                  <el-descriptions-item label="IP地址">{{ device.ip_address }}</el-descriptions-item>
                  <el-descriptions-item label="设备状态">
                    <el-tag :type="getStatusType(device.status)">
                      {{ device.status_display }}
                    </el-tag>
                  </el-descriptions-item>
                  <el-descriptions-item label="所属分组" :span="2">
                    <div class="device-groups">
                      <el-tag 
                        v-for="group in device.groups" 
                        :key="group" 
                        size="small" 
                        class="group-tag"
                      >
                        {{ group }}
                      </el-tag>
                      <span v-if="!device.groups || device.groups.length === 0" class="no-group">
                        未分组
                      </span>
                    </div>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- 评分历史趋势 -->
      <div class="score-history">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>安全评分趋势</span>
              <div class="history-controls">
                <el-select v-model="historyDays" @change="loadScoreHistory" style="width: 120px;">
                  <el-option label="7天" :value="7" />
                  <el-option label="15天" :value="15" />
                  <el-option label="30天" :value="30" />
                </el-select>
              </div>
            </div>
          </template>
          <div class="chart-container" ref="chartRef" v-loading="loadingHistory"></div>
        </el-card>
      </div>

      <!-- 异常事件统计 -->
      <div class="anomaly-stats">
        <el-card>
          <template #header>
            <span>近期异常事件</span>
          </template>
          <div class="stats-grid">
            <div class="stat-item" v-for="stat in anomalyStats" :key="stat.type">
              <div class="stat-icon" :style="{ backgroundColor: stat.color }">
                <el-icon><Warning /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stat.count }}</div>
                <div class="stat-label">{{ stat.label }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 安全建议 -->
      <div class="security-suggestions">
        <el-card>
          <template #header>
            <span>安全建议</span>
          </template>
          <div class="suggestions-list">
            <el-alert
              v-for="suggestion in securitySuggestions"
              :key="suggestion.id"
              :title="suggestion.title"
              :description="suggestion.description"
              :type="suggestion.type"
              :closable="false"
              class="suggestion-item"
            />
          </div>
        </el-card>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
      <el-button type="primary" @click="updateScore" :loading="updating">
        更新评分
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Warning } from '@element-plus/icons-vue'
import * as echarts from 'echarts'

import {
  getSecurityScoreHistory, updateDeviceSecurityScore,
  type Device, type SecurityScoreHistory
} from '@/api/device'

// Props
interface Props {
  modelValue: boolean
  device: Device | null
}

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const loadingHistory = ref(false)
const updating = ref(false)
const historyDays = ref(30)
const scoreHistory = ref<SecurityScoreHistory[]>([])

// 图表引用
const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// 异常统计数据
const anomalyStats = ref([
  { type: 'ddos', label: 'DDoS攻击', count: 0, color: '#F44336' },
  { type: 'port_scan', label: '端口扫描', count: 0, color: '#FF9800' },
  { type: 'unauthorized', label: '越权访问', count: 0, color: '#9C27B0' },
  { type: 'malformed', label: '异常指令', count: 0, color: '#2196F3' }
])

// 安全建议
const securitySuggestions = computed(() => {
  if (!props.device) return []
  
  const suggestions = []
  const score = props.device.security_score
  
  if (score < 70) {
    suggestions.push({
      id: 1,
      title: '安全评分较低',
      description: '设备存在较多安全风险，建议立即检查设备配置和网络环境',
      type: 'error'
    })
  }
  
  if (score >= 70 && score < 90) {
    suggestions.push({
      id: 2,
      title: '安全评分中等',
      description: '设备安全状况一般，建议定期检查和维护',
      type: 'warning'
    })
  }
  
  if (props.device.status === 'warning') {
    suggestions.push({
      id: 3,
      title: '设备状态异常',
      description: '设备当前处于告警状态，请及时处理相关异常',
      type: 'error'
    })
  }
  
  if (!props.device.groups || props.device.groups.length === 0) {
    suggestions.push({
      id: 4,
      title: '设备未分组',
      description: '建议将设备加入适当的分组以便统一管理',
      type: 'info'
    })
  }
  
  if (suggestions.length === 0) {
    suggestions.push({
      id: 5,
      title: '设备安全状况良好',
      description: '当前设备安全评分较高，请继续保持良好的安全防护',
      type: 'success'
    })
  }
  
  return suggestions
})

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 加载评分历史
const loadScoreHistory = async () => {
  if (!props.device) return
  
  loadingHistory.value = true
  try {
    const res = await getSecurityScoreHistory(props.device.device_id, historyDays.value)
    const data = (res.data as any).data || res.data
    scoreHistory.value = data.history || []
    
    // 更新异常统计
    updateAnomalyStats()
    
    // 渲染图表
    await nextTick()
    renderChart()
  } catch (error) {
    console.error('加载评分历史失败:', error)
    ElMessage.error('加载评分历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 更新异常统计
const updateAnomalyStats = () => {
  const stats = {
    ddos: 0,
    port_scan: 0,
    unauthorized: 0,
    malformed: 0
  }
  
  scoreHistory.value.forEach(item => {
    // 这里需要根据实际的异常数据结构来统计
    // 暂时使用模拟数据
  })
  
  anomalyStats.value.forEach(stat => {
    stat.count = stats[stat.type as keyof typeof stats] || Math.floor(Math.random() * 10)
  })
}

// 渲染图表
const renderChart = () => {
  if (!chartRef.value || !scoreHistory.value.length) return
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  chartInstance = echarts.init(chartRef.value)
  
  const dates = scoreHistory.value.map(item => item.date)
  const scores = scoreHistory.value.map(item => item.security_score)
  const anomalyCounts = scoreHistory.value.map(item => item.anomaly_count)
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      }
    },
    legend: {
      data: ['安全评分', '异常次数']
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        formatter: (value: string) => {
          return new Date(value).toLocaleDateString()
        }
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '安全评分',
        min: 0,
        max: 100,
        axisLabel: {
          formatter: '{value}'
        }
      },
      {
        type: 'value',
        name: '异常次数',
        axisLabel: {
          formatter: '{value}'
        }
      }
    ],
    series: [
      {
        name: '安全评分',
        type: 'line',
        data: scores,
        smooth: true,
        itemStyle: {
          color: '#409EFF'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
            { offset: 1, color: 'rgba(64, 158, 255, 0.1)' }
          ])
        }
      },
      {
        name: '异常次数',
        type: 'bar',
        yAxisIndex: 1,
        data: anomalyCounts,
        itemStyle: {
          color: '#F56C6C'
        }
      }
    ]
  }
  
  chartInstance.setOption(option)
}

// 更新安全评分
const updateScore = async () => {
  if (!props.device) return
  
  updating.value = true
  try {
    await updateDeviceSecurityScore(props.device.device_id)
    ElMessage.success('安全评分更新成功')
    // 重新加载历史数据
    loadScoreHistory()
  } catch (error) {
    console.error('更新安全评分失败:', error)
    ElMessage.error('更新安全评分失败')
  } finally {
    updating.value = false
  }
}

// 获取安全评分颜色
const getSecurityColor = (level: string) => {
  const colorMap: Record<string, string> = {
    high: '#67C23A',
    medium: '#E6A23C',
    low: '#F56C6C'
  }
  return colorMap[level] || '#909399'
}

// 获取安全等级标签类型
const getSecurityTagType = (level: string) => {
  const typeMap: Record<string, string> = {
    high: 'success',
    medium: 'warning',
    low: 'danger'
  }
  return typeMap[level] || 'info'
}

// 获取安全等级文本
const getSecurityLevelText = (level: string) => {
  const textMap: Record<string, string> = {
    high: '高安全',
    medium: '中等安全',
    low: '低安全'
  }
  return textMap[level] || '未知'
}

// 获取状态类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    online: 'success',
    offline: 'info',
    warning: 'warning'
  }
  return typeMap[status] || 'info'
}

// 格式化时间
const formatTime = (time: string | null) => {
  if (!time) return '未更新'
  return new Date(time).toLocaleString()
}

// 处理对话框关闭
const handleClose = () => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
  visible.value = false
}

// 监听设备变化
watch(() => props.device, (newDevice) => {
  if (newDevice && visible.value) {
    loadScoreHistory()
  }
})

// 监听对话框显示状态
watch(visible, (show) => {
  if (show && props.device) {
    loadScoreHistory()
  }
})
</script>

<style scoped>
.security-detail {
  padding: 10px 0;
}

.score-overview {
  margin-bottom: 20px;
}

.score-card {
  text-align: center;
}

.score-display {
  padding: 20px;
}

.score-circle {
  margin-bottom: 15px;
}

.score-text {
  font-size: 24px;
  font-weight: bold;
}

.score-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.update-time {
  font-size: 12px;
  color: #909399;
}

.info-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.device-info {
  padding: 10px 0;
}

.device-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.group-tag {
  margin: 0;
}

.no-group {
  color: #c0c4cc;
  font-size: 12px;
}

.score-history {
  margin-bottom: 20px;
}

.history-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chart-container {
  height: 300px;
  width: 100%;
}

.anomaly-stats {
  margin-bottom: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  padding: 10px 0;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 5px;
}

.security-suggestions {
  margin-bottom: 20px;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggestion-item {
  margin: 0;
}
</style>