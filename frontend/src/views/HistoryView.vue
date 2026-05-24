<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, TrendCharts, Warning, CircleCheck, Timer } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getDetectionRecords, getMonitoringKpi, getMonitoringTrend, type DetectionRecord, type MonitoringKpiData, type MonitoringTrendItem } from '@/api/detection'
import { getDevices, type Device } from '@/api/device'
import AlertHandleDrawer from '@/components/AlertHandleDrawer.vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

const records = ref<DetectionRecord[]>([])
const devices = ref<Device[]>([])
const loading = ref(false)

// 统计数据
const kpiData = ref<MonitoringKpiData | null>(null)
const trendData = ref<MonitoringTrendItem[]>([])
const statsLoading = ref(false)

// 图表相关
const trendChartRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
const chartTimeRange = ref<'7d' | '30d' | '90d'>('7d')

// 告警处理抽屉
const handleDrawerVisible = ref(false)
const currentRecord = ref<DetectionRecord | null>(null)
const currentDevice = ref<Device | null>(null)



// 分页
const pagination = ref({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

// 加载设备列表（用于显示设备名称）
const loadDevices = async () => {
  try {
    const res = await getDevices({ page_size: 100 })
    const data = (res.data as any).data || res.data
    devices.value = data.results || []
  } catch (error) {
    console.error('加载设备列表失败:', error)
  }
}

// 加载统计数据
const loadKpiData = async () => {
  statsLoading.value = true
  try {
    const days = chartTimeRange.value === '7d' ? 7 : chartTimeRange.value === '30d' ? 30 : 90
    const startTime = new Date()
    startTime.setDate(startTime.getDate() - days)
    
    const res = await getMonitoringKpi({
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString()
    })
    kpiData.value = (res.data as any).data || res.data
  } catch (error) {
    console.error('加载统计数据失败:', error)
  } finally {
    statsLoading.value = false
  }
}

// 加载趋势数据
const loadTrendData = async () => {
  try {
    const days = chartTimeRange.value === '7d' ? 7 : chartTimeRange.value === '30d' ? 30 : 90
    const startTime = new Date()
    startTime.setDate(startTime.getDate() - days)
    
    const res = await getMonitoringTrend({
      start_time: startTime.toISOString(),
      end_time: new Date().toISOString(),
      granularity: chartTimeRange.value === '7d' ? 'day' : chartTimeRange.value === '30d' ? 'day' : 'week'
    })
    trendData.value = (res.data as any).data || res.data || []
    updateTrendChart()
  } catch (error) {
    console.error('加载趋势数据失败:', error)
  }
}

// 初始化趋势图表
const initTrendChart = () => {
  if (!trendChartRef.value) return
  
  trendChart = echarts.init(trendChartRef.value)
  updateTrendChart()
  
  // 响应窗口大小变化
  window.addEventListener('resize', handleResize)
}

// 更新趋势图表
const updateTrendChart = () => {
  if (!trendChart) return
  
  const isDark = themeStore.mode === 'dark'
  const textColor = isDark ? 'rgba(255, 255, 255, 0.65)' : 'rgba(0, 0, 0, 0.65)'
  const borderColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
  
  const option: echarts.EChartsOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark ? 'rgba(30, 30, 35, 0.95)' : 'rgba(255, 255, 255, 0.95)',
      borderColor: borderColor,
      textStyle: {
        color: textColor
      },
      axisPointer: {
        type: 'cross',
        crossStyle: {
          color: textColor
        }
      }
    },
    legend: {
      data: ['总检测数', '异常数'],
      textStyle: {
        color: textColor
      },
      top: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '40px',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: trendData.value.map(item => {
        // 格式化日期显示
        const date = new Date(item.period)
        return `${date.getMonth() + 1}/${date.getDate()}`
      }),
      axisLine: {
        lineStyle: {
          color: borderColor
        }
      },
      axisLabel: {
        color: textColor
      }
    },
    yAxis: [
      {
        type: 'value',
        name: '检测数',
        axisLine: {
          lineStyle: {
            color: borderColor
          }
        },
        axisLabel: {
          color: textColor
        },
        splitLine: {
          lineStyle: {
            color: borderColor
          }
        }
      }
    ],
    series: [
      {
        name: '总检测数',
        type: 'bar',
        data: trendData.value.map(item => item.total),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(91, 141, 239, 0.8)' },
            { offset: 1, color: 'rgba(91, 141, 239, 0.3)' }
          ]),
          borderRadius: [4, 4, 0, 0]
        },
        barMaxWidth: 30
      },
      {
        name: '异常数',
        type: 'line',
        data: trendData.value.map(item => item.anomaly),
        smooth: true,
        lineStyle: {
          color: '#e0a854',
          width: 2
        },
        itemStyle: {
          color: '#e0a854'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(224, 168, 84, 0.3)' },
            { offset: 1, color: 'rgba(224, 168, 84, 0.05)' }
          ])
        }
      }
    ]
  }
  
  trendChart.setOption(option)
}

// 处理窗口大小变化
const handleResize = () => {
  trendChart?.resize()
}

// 切换时间范围
const handleTimeRangeChange = () => {
  loadKpiData()
  loadTrendData()
}

// 加载检测记录（默认只显示异常记录）
const loadRecords = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.value.currentPage,
      page_size: pagination.value.pageSize,
      is_anomaly: true // 默认只显示异常记录
    }
    
    const res = await getDetectionRecords(params)
    const data = (res.data as any).data || res.data
    records.value = data.results || []
    pagination.value.total = data.count || 0
  } catch (error) {
    console.error('加载检测记录失败:', error)
    records.value = []
  } finally {
    loading.value = false
  }
}

// 页码变化
const handlePageChange = (page: number) => {
  pagination.value.currentPage = page
  loadRecords()
}

// 每页条数变化
const handleSizeChange = (size: number) => {
  pagination.value.pageSize = size
  pagination.value.currentPage = 1
  loadRecords()
}

// 获取设备名称
const getDeviceName = (deviceId: string) => {
  const device = devices.value.find(d => d.device_id === deviceId)
  return device ? device.name : deviceId
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

// 获取威胁等级
const getThreatLevel = (record: DetectionRecord) => {
  if (!record.is_anomaly) return 'low'
  if (record.confidence >= 0.8) return 'high'
  if (record.confidence >= 0.5) return 'medium'
  return 'low'
}

// 导出Excel
const handleExport = () => {
  // 构建CSV数据
  const headers = ['设备ID', '设备名称', '攻击类型', '威胁等级', '置信度', '发生时间', '状态']
  const rows = records.value.map(r => [
    r.device_id,
    getDeviceName(r.device_id),
    getAttackTypeText(r.attack_type),
    getThreatLevel(r) === 'high' ? '高危' : getThreatLevel(r) === 'medium' ? '中危' : '低危',
    `${(r.confidence * 100).toFixed(0)}%`,
    r.timestamp,
    r.is_anomaly ? '异常' : '正常'
  ])
  
  const csvContent = [headers, ...rows].map(row => row.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `检测记录_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  
  ElMessage.success('导出成功')
}

// 打开处理抽屉
const openHandleDrawer = (record: DetectionRecord) => {
  currentRecord.value = record
  currentDevice.value = devices.value.find(d => d.device_id === record.device_id) || null
  handleDrawerVisible.value = true
}

// 处理完成回调
const onAlertHandled = (record: DetectionRecord, note: string) => {
  console.log('告警已处理:', record.id, note)
  // TODO: 调用后端API标记告警已处理
  // 这里可以更新本地状态或重新加载数据
  loadRecords()
}

onMounted(() => {
  loadDevices()
  loadRecords()
  loadKpiData()
  loadTrendData()
  
  // 延迟初始化图表，确保 DOM 已渲染
  setTimeout(() => {
    initTrendChart()
  }, 100)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
})

// 监听主题变化更新图表
watch(() => themeStore.mode, () => {
  updateTrendChart()
})
</script>

<template>
  <div class="history-view">
    <div class="page-header">
      <h2>历史记录</h2>
      <el-button type="primary" @click="handleExport">
        <el-icon><Download /></el-icon>
        导出Excel
      </el-button>
    </div>

    <!-- 统计卡片区域 -->
    <div class="stats-section">
      <div class="stats-cards" v-loading="statsLoading">
        <div class="stat-card">
          <div class="stat-icon total">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ kpiData?.total_detections?.toLocaleString() || 0 }}</div>
            <div class="stat-label">总检测数</div>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon anomaly">
            <el-icon><Warning /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value warning">{{ kpiData?.anomaly_count?.toLocaleString() || 0 }}</div>
            <div class="stat-label">异常数量</div>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon rate">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value" :class="{ 'danger': (kpiData?.anomaly_rate || 0) > 10 }">
              {{ ((kpiData?.anomaly_rate || 0)).toFixed(2) }}%
            </div>
            <div class="stat-label">异常率</div>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon time">
            <el-icon><Timer /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ (kpiData?.avg_inference_time || 0).toFixed(1) }}ms</div>
            <div class="stat-label">平均推理时间</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 趋势图表区域 -->
    <div class="chart-section card">
      <div class="chart-header">
        <h3>检测趋势</h3>
        <el-radio-group v-model="chartTimeRange" size="small" @change="handleTimeRangeChange">
          <el-radio-button value="7d">近7天</el-radio-button>
          <el-radio-button value="30d">近30天</el-radio-button>
          <el-radio-button value="90d">近90天</el-radio-button>
        </el-radio-group>
      </div>
      <div ref="trendChartRef" class="trend-chart"></div>
    </div>

    <!-- 数据表格 -->
    <div class="card">
      <el-table :data="records" style="width: 100%" v-loading="loading" empty-text="暂无检测记录">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column label="设备" min-width="150">
          <template #default="{ row }">
            {{ getDeviceName(row.device_id) }}
          </template>
        </el-table-column>
        <el-table-column label="攻击类型" min-width="120">
          <template #default="{ row }">
            {{ getAttackTypeText(row.attack_type) }}
          </template>
        </el-table-column>
        <el-table-column label="威胁等级" min-width="100">
          <template #default="{ row }">
            <el-tag 
              :type="getThreatLevel(row) === 'high' ? 'danger' : getThreatLevel(row) === 'medium' ? 'warning' : 'success'"
            >
              {{ getThreatLevel(row) === 'high' ? '高危' : getThreatLevel(row) === 'medium' ? '中危' : '低危' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" min-width="100">
          <template #default="{ row }">
            {{ (row.confidence * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="发生时间" min-width="180" />
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_anomaly ? 'danger' : 'success'">
              {{ row.is_anomaly ? '异常' : '正常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openHandleDrawer(row)">详情</el-button>
            <el-button 
              v-if="row.is_anomaly" 
              type="warning" 
              link 
              @click="openHandleDrawer(row)"
            >
              处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 告警处理抽屉 -->
    <AlertHandleDrawer
      v-model:visible="handleDrawerVisible"
      :record="currentRecord"
      :device="currentDevice"
      @handled="onAlertHandled"
    />
  </div>
</template>

<style lang="scss" scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
  }
}

// 统计卡片区域
.stats-section {
  .stats-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
}

.stat-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-medium);
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;

    &.total {
      background: rgba(91, 141, 239, 0.12);
      color: var(--primary-color);
    }

    &.anomaly {
      background: rgba(224, 168, 84, 0.12);
      color: var(--warning-color);
    }

    &.rate {
      background: rgba(94, 196, 158, 0.12);
      color: var(--success-color);
    }

    &.time {
      background: rgba(168, 132, 235, 0.12);
      color: #a884eb;
    }
  }

  .stat-content {
    flex: 1;

    .stat-value {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
      font-family: var(--font-mono);

      &.warning {
        color: var(--warning-color);
      }

      &.danger {
        color: var(--danger-color);
      }
    }

    .stat-label {
      font-size: 13px;
      color: var(--text-muted);
      margin-top: 4px;
    }
  }
}

// 图表区域
.chart-section {
  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;

    h3 {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
    }
  }

  .trend-chart {
    height: 300px;
    width: 100%;
  }
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow-light);
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

// 响应式布局
@media (max-width: 1200px) {
  .stats-section .stats-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-section .stats-cards {
    grid-template-columns: 1fr;
  }
}
</style>
