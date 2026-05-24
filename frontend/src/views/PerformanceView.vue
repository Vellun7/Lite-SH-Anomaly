<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import * as echarts from 'echarts'
import { useThemeStore } from '@/stores/theme'
import { ElMessage } from 'element-plus'
import {
  Timer,
  TrendCharts,
  Warning,
  CircleCheck,
  Aim,
  Stopwatch,
  Download,
  DataAnalysis
} from '@element-plus/icons-vue'
import {
  getMonitoringKpi,
  getMonitoringTrend,
  getMonitoringDeviceRisk,
  getMonitoringTrafficFeature,
  type MonitoringKpiData,
  type MonitoringTrendItem,
  type MonitoringDeviceRiskItem,
  type MonitoringTrafficFeatureItem
} from '@/api/detection'

const themeStore = useThemeStore()
const loading = ref(false)

// 时间范围选择
const timeRange = ref<7 | 30 | 90>(7)
const timeRangeOptions = [
  { label: '近7天', value: 7 },
  { label: '近30天', value: 30 },
  { label: '近90天', value: 90 }
]

// 自动刷新（默认5分钟）
const REFRESH_INTERVAL = 300 // 5分钟（秒）
let refreshTimer: ReturnType<typeof setInterval> | null = null

// 上次更新时间
const lastUpdateTime = ref<Date | null>(null)
const lastUpdateTimeStr = computed(() => {
  if (!lastUpdateTime.value) return '--'
  return lastUpdateTime.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

const kpi = ref<MonitoringKpiData>({
  total_detections: 0,
  anomaly_count: 0,
  anomaly_rate: 0,
  avg_confidence: 0,
  avg_anomaly_score: 0,
  avg_inference_time: 0
})

const trendData = ref<MonitoringTrendItem[]>([])
const deviceRiskData = ref<MonitoringDeviceRiskItem[]>([])
const trafficFeatureData = ref<MonitoringTrafficFeatureItem[]>([])

const trendChartRef = ref<HTMLElement>()
const deviceRiskChartRef = ref<HTMLElement>()
const trafficFeatureChartRef = ref<HTMLElement>()

// 图表实例缓存
let trendChart: echarts.ECharts | null = null
let deviceRiskChart: echarts.ECharts | null = null
let trafficFeatureChart: echarts.ECharts | null = null

// 图表配色（根据主题动态变化）
const chartColors = () => {
  const dark = themeStore.isDark()
  return {
    axisLine: dark ? 'rgba(255,255,255,0.08)' : '#e4e7ed',
    axisLabel: dark ? '#636d85' : '#909399',
    splitLine: dark ? 'rgba(255,255,255,0.05)' : '#e4e7ed',
    legend: dark ? '#a0a8bf' : '#606266',
    emptyText: dark ? '#636d85' : '#909399'
  }
}

const buildQueryParams = () => {
  const endTime = new Date()
  const startTime = new Date()
  startTime.setDate(endTime.getDate() - timeRange.value)
  // 根据时间范围选择合适的粒度
  const granularity = timeRange.value <= 7 ? 'day' : timeRange.value <= 30 ? 'day' : 'week'
  return {
    start_time: startTime.toISOString(),
    end_time: endTime.toISOString(),
    granularity: granularity as 'hour' | 'day' | 'week' | 'month'
  }
}

const getResponseData = (response: any) => {
  return (response.data as any).data || response.data
}

const setEmptyChart = (chart: echarts.ECharts, text: string) => {
  chart.setOption({
    title: {
      text,
      left: 'center',
      top: 'center',
      textStyle: { color: chartColors().emptyText, fontSize: 14 }
    }
  })
}

const initTrendChart = () => {
  if (!trendChartRef.value) return
  if (trendChart) {
    trendChart.dispose()
  }
  trendChart = echarts.init(trendChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  trendChart.setOption({ backgroundColor: 'transparent' })

  if (trendData.value.length === 0) {
    setEmptyChart(trendChart, '暂无检测趋势数据')
    return
  }

  const periods = trendData.value.map(item => item.period)
  const total = trendData.value.map(item => item.total)
  const anomaly = trendData.value.map(item => item.anomaly)
  const anomalyRate = trendData.value.map(item => {
    if (item.total === 0) return 0
    return Number(((item.anomaly / item.total) * 100).toFixed(2))
  })

  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: { data: ['检测频率', '异常次数', '异常率'], top: 0, textStyle: { color: chartColors().legend } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
    xAxis: {
      type: 'category',
      data: periods,
      axisLabel: { color: chartColors().axisLabel },
      axisLine: { lineStyle: { color: chartColors().axisLine } }
    },
    yAxis: [
      {
        type: 'value',
        name: '次数',
        nameTextStyle: { color: chartColors().axisLabel },
        axisLabel: { color: chartColors().axisLabel },
        splitLine: { lineStyle: { color: chartColors().splitLine, type: 'dashed' } }
      },
      {
        type: 'value',
        name: '异常率(%)',
        nameTextStyle: { color: chartColors().axisLabel },
        axisLabel: { color: chartColors().axisLabel },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '检测频率',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#5b8def', width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(91, 141, 239, 0.25)' },
            { offset: 1, color: 'rgba(91, 141, 239, 0.02)' }
          ])
        },
        data: total
      },
      {
        name: '异常次数',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: '#e06060', borderRadius: [4, 4, 0, 0] },
        data: anomaly
      },
      {
        name: '异常率',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#5ec49e', width: 2 },
        itemStyle: { color: '#5ec49e' },
        data: anomalyRate
      }
    ]
  })
}

const initDeviceRiskChart = () => {
  if (!deviceRiskChartRef.value) return
  if (deviceRiskChart) {
    deviceRiskChart.dispose()
  }
  deviceRiskChart = echarts.init(deviceRiskChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  deviceRiskChart.setOption({ backgroundColor: 'transparent' })

  if (deviceRiskData.value.length === 0) {
    setEmptyChart(deviceRiskChart, '暂无设备风险数据')
    return
  }

  const devices = deviceRiskData.value.map(item => item.device_id)
  const total = deviceRiskData.value.map(item => item.total)
  const anomaly = deviceRiskData.value.map(item => item.anomaly)

  deviceRiskChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: { data: ['检测次数', '异常次数'], top: 0, textStyle: { color: chartColors().legend } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: chartColors().axisLabel },
      splitLine: { lineStyle: { color: chartColors().splitLine, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: devices,
      axisLabel: { color: chartColors().legend }
    },
    series: [
      {
        name: '检测次数',
        type: 'bar',
        barWidth: 12,
        itemStyle: { color: '#5b8def', borderRadius: [0, 4, 4, 0] },
        data: total
      },
      {
        name: '异常次数',
        type: 'bar',
        barWidth: 12,
        itemStyle: { color: '#e06060', borderRadius: [0, 4, 4, 0] },
        data: anomaly
      }
    ]
  })
}



const initTrafficFeatureChart = () => {
  if (!trafficFeatureChartRef.value) return
  if (trafficFeatureChart) {
    trafficFeatureChart.dispose()
  }
  trafficFeatureChart = echarts.init(trafficFeatureChartRef.value, themeStore.isDark() ? 'dark' : undefined)
  trafficFeatureChart.setOption({ backgroundColor: 'transparent' })

  if (trafficFeatureData.value.length === 0) {
    setEmptyChart(trafficFeatureChart, '暂无流量特征数据')
    return
  }

  const buckets = trafficFeatureData.value.map(item => item.bucket)
  const total = trafficFeatureData.value.map(item => item.total)
  const anomaly = trafficFeatureData.value.map(item => item.anomaly)
  const anomalyRate = trafficFeatureData.value.map(item => Number((item.anomaly_rate * 100).toFixed(2)))

  trafficFeatureChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' }
    },
    legend: { data: ['检测总量', '异常数量', '异常率'], top: 0, textStyle: { color: chartColors().legend } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '18%', containLabel: true },
    xAxis: {
      type: 'category',
      data: buckets,
      axisLabel: { color: chartColors().axisLabel },
      axisLine: { lineStyle: { color: chartColors().axisLine } }
    },
    yAxis: [
      {
        type: 'value',
        name: '数量',
        nameTextStyle: { color: chartColors().axisLabel },
        axisLabel: { color: chartColors().axisLabel },
        splitLine: { lineStyle: { color: chartColors().splitLine, type: 'dashed' } }
      },
      {
        type: 'value',
        name: '异常率(%)',
        nameTextStyle: { color: chartColors().axisLabel },
        axisLabel: { color: chartColors().axisLabel },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '检测总量',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: '#5b8def', borderRadius: [4, 4, 0, 0] },
        data: total
      },
      {
        name: '异常数量',
        type: 'bar',
        barWidth: 16,
        itemStyle: { color: '#e06060', borderRadius: [4, 4, 0, 0] },
        data: anomaly
      },
      {
        name: '异常率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#e0a854', width: 2 },
        itemStyle: { color: '#e0a854' },
        data: anomalyRate
      }
    ]
  })
}

const loadMonitoringData = async () => {
  loading.value = true
  try {
    const params = buildQueryParams()
    const [kpiRes, trendRes, riskRes, trafficRes] = await Promise.all([
      getMonitoringKpi(params),
      getMonitoringTrend(params),
      getMonitoringDeviceRisk(params),
      getMonitoringTrafficFeature(params)
    ])

    kpi.value = getResponseData(kpiRes)
    trendData.value = getResponseData(trendRes) || []
    deviceRiskData.value = getResponseData(riskRes) || []
    trafficFeatureData.value = getResponseData(trafficRes) || []

    lastUpdateTime.value = new Date()

    await nextTick()
    initTrendChart()
    initDeviceRiskChart()
    initTrafficFeatureChart()
  } catch (error) {
    console.error('加载监控数据失败:', error)
    ElMessage.error('加载监控数据失败')
  } finally {
    loading.value = false
  }
}

// 时间范围变化
const handleTimeRangeChange = () => {
  loadMonitoringData()
}

// 开启自动刷新
const startAutoRefresh = () => {
  stopAutoRefresh()
  refreshTimer = setInterval(() => {
    loadMonitoringData()
  }, REFRESH_INTERVAL * 1000)
}

// 停止自动刷新
const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// 窗口大小变化时重新调整图表
const handleResize = () => {
  trendChart?.resize()
  deviceRiskChart?.resize()
  trafficFeatureChart?.resize()
}

// 导出数据
const exportData = () => {
  const data = {
    kpi: kpi.value,
    trend: trendData.value,
    deviceRisk: deviceRiskData.value,
    trafficFeature: trafficFeatureData.value,
    exportTime: new Date().toISOString(),
    timeRange: `近${timeRange.value}天`
  }
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `性能监控数据_${new Date().toLocaleDateString('zh-CN').replace(/\//g, '-')}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('数据导出成功')
}

onMounted(() => {
  loadMonitoringData()
  startAutoRefresh() // 页面加载后自动启动定时刷新
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  stopAutoRefresh()
  window.removeEventListener('resize', handleResize)
  // 销毁图表实例
  trendChart?.dispose()
  deviceRiskChart?.dispose()
  trafficFeatureChart?.dispose()
})

// 监听主题变化，重新初始化所有图表
watch(() => themeStore.mode, () => {
  setTimeout(() => {
    initTrendChart()
    initDeviceRiskChart()
    initTrafficFeatureChart()
  }, 100)
})
</script>

<template>
  <div class="performance-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>
          <el-icon class="title-icon"><DataAnalysis /></el-icon>
          性能监控
        </h2>
        <span class="last-update">
          <el-icon><Timer /></el-icon>
          更新于 {{ lastUpdateTimeStr }}
        </span>
      </div>
      <div class="header-right">
        <!-- 时间范围选择 -->
        <el-button-group class="time-range-group">
          <el-button
            v-for="opt in timeRangeOptions"
            :key="opt.value"
            :type="timeRange === opt.value ? 'primary' : 'default'"
            size="small"
            @click="timeRange = opt.value; handleTimeRangeChange()"
          >
            {{ opt.label }}
          </el-button>
        </el-button-group>

        <!-- 导出数据 -->
        <el-button size="small" type="primary" plain @click="exportData">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
      </div>
    </div>

    <!-- KPI 指标卡片 -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon total">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">检测总量</div>
          <div class="metric-value">{{ kpi.total_detections.toLocaleString() }}</div>
          <div class="metric-desc">近{{ timeRange }}天累计</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon danger">
          <el-icon><Warning /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">异常数量</div>
          <div class="metric-value danger">{{ kpi.anomaly_count.toLocaleString() }}</div>
          <div class="metric-desc">近{{ timeRange }}天累计</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon warning">
          <el-icon><Aim /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">异常率</div>
          <div class="metric-value">{{ (kpi.anomaly_rate * 100).toFixed(1) }}%</div>
          <div class="metric-desc">全局占比</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon success">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">平均置信度</div>
          <div class="metric-value">{{ (kpi.avg_confidence * 100).toFixed(1) }}%</div>
          <div class="metric-desc">模型可信度</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon info">
          <el-icon><DataAnalysis /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">平均异常分数</div>
          <div class="metric-value">{{ kpi.avg_anomaly_score.toFixed(3) }}</div>
          <div class="metric-desc">异常强度</div>
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-icon primary">
          <el-icon><Stopwatch /></el-icon>
        </div>
        <div class="metric-content">
          <div class="metric-label">平均推理耗时</div>
          <div class="metric-value">{{ kpi.avg_inference_time.toFixed(2) }}ms</div>
          <div class="metric-desc">模型耗时</div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-grid" v-loading="loading">
      <div class="card">
        <div class="card-header">
          <h3>异常趋势与检测频率</h3>
          <span class="card-subtitle">近{{ timeRange }}天 · {{ timeRange <= 30 ? '日' : '周' }}粒度</span>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3>设备风险排行</h3>
          <span class="card-subtitle">近{{ timeRange }}天 · {{ timeRange <= 30 ? '日' : '周' }}粒度</span>
        </div>
        <div ref="deviceRiskChartRef" class="chart-container"></div>
      </div>
      <div class="card full-width">
        <div class="card-header">
          <h3>流量特征与异常关联</h3>
          <span class="card-subtitle">近{{ timeRange }}天 · {{ timeRange <= 30 ? '日' : '周' }}粒度</span>
        </div>
        <div ref="trafficFeatureChartRef" class="chart-container"></div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.performance-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

// 页面头部
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;

    h2 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
      margin: 0;

      .title-icon {
        font-size: 24px;
        color: var(--primary-color);
      }
    }

    .last-update {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--text-muted);
      padding: 4px 10px;
      background: var(--bg-secondary);
      border-radius: 12px;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;

    .time-range-group {
      .el-button {
        min-width: 60px;
      }
    }
  }
}

// KPI 卡片网格
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;

  &:nth-child(1) { animation-delay: 0.05s; }
  &:nth-child(2) { animation-delay: 0.1s; }
  &:nth-child(3) { animation-delay: 0.15s; }
  &:nth-child(4) { animation-delay: 0.2s; }
  &:nth-child(5) { animation-delay: 0.25s; }
  &:nth-child(6) { animation-delay: 0.3s; }

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-medium);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .metric-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    flex-shrink: 0;

    &.total {
      background: rgba(91, 141, 239, 0.15);
      color: #5b8def;
    }

    &.danger {
      background: rgba(224, 96, 96, 0.15);
      color: #e06060;
    }

    &.warning {
      background: rgba(224, 168, 84, 0.15);
      color: #e0a854;
    }

    &.success {
      background: rgba(94, 196, 158, 0.15);
      color: #5ec49e;
    }

    &.info {
      background: rgba(144, 147, 153, 0.15);
      color: #909399;
    }

    &.primary {
      background: rgba(64, 158, 255, 0.15);
      color: #409eff;
    }
  }

  .metric-content {
    flex: 1;
    min-width: 0;

    .metric-label {
      font-size: 13px;
      color: var(--text-muted);
      margin-bottom: 4px;
    }

    .metric-value {
      font-size: 26px;
      font-weight: 700;
      color: var(--text-primary);
      font-family: var(--font-mono);
      line-height: 1.2;

      &.danger {
        color: var(--danger-color);
      }
    }

    .metric-desc {
      font-size: 12px;
      color: var(--text-disabled);
      margin-top: 2px;
    }
  }
}

// 图表网格
.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.full-width {
  grid-column: span 2;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;
  animation-delay: 0.3s;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;

    h3 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
    }

    .card-subtitle {
      font-size: 12px;
      color: var(--text-muted);
    }
  }
}

.chart-container {
  height: 300px;
}

// 响应式布局
@media (max-width: 1200px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }

  .full-width {
    grid-column: span 1;
  }
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;

    .header-right {
      width: 100%;
      justify-content: flex-start;
    }
  }

  .metrics-grid {
    grid-template-columns: 1fr;
  }

  .metric-card {
    .metric-icon {
      width: 40px;
      height: 40px;
      font-size: 20px;
    }

    .metric-content {
      .metric-value {
        font-size: 22px;
      }
    }
  }
}

// 动画
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
