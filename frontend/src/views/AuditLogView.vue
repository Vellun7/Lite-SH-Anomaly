<template>
  <div class="audit-log-view">
      <!-- 页面头部 -->
      <div class="page-header">
        <div class="header-left">
          <h1 class="page-title">
            <el-icon><Notebook /></el-icon>
            操作日志
          </h1>
          <p class="page-desc">查看系统操作日志，支持审计追踪</p>
        </div>
        <div class="header-right">
          <el-button @click="handleRefresh" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="handleExport" :loading="exportLoading">
            <el-icon><Download /></el-icon>
            导出日志
          </el-button>
        </div>
      </div>

      <!-- 日志表格 -->
      <div class="log-table-section">
        <el-table
          :data="logList"
          v-loading="loading"
          stripe
          @row-click="handleRowClick"
          row-class-name="clickable-row"
        >
          <el-table-column prop="created_at" label="操作时间" width="180">
            <template #default="{ row }">
              <span class="time-text">{{ formatTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="username" label="操作用户" width="120">
            <template #default="{ row }">
              <span class="user-text">{{ row.username || '匿名' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="action_display" label="操作类型" width="100">
            <template #default="{ row }">
              <el-tag :type="getActionTagType(row.action)" size="small">
                {{ row.action_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="resource_type_display" label="资源类型" width="110">
            <template #default="{ row }">
              <span class="resource-text">{{ row.resource_type_display }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="resource_name" label="资源名称" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.resource_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="操作描述" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.description || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="ip_address" label="IP地址" width="140">
            <template #default="{ row }">
              <span class="ip-text">{{ row.ip_address || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="result_display" label="结果" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="getResultTagType(row.result)" size="small" effect="plain">
                {{ row.result_display }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click.stop="showDetail(row)">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="pagination.page"
            v-model:page-size="pagination.page_size"
            :total="pagination.total"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <!-- 详情抽屉 -->
      <el-drawer
        v-model="showDetailDrawer"
        title="日志详情"
        direction="rtl"
        size="500px"
      >
        <div class="detail-content" v-if="currentLog">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="日志ID">{{ currentLog.id }}</el-descriptions-item>
            <el-descriptions-item label="操作时间">{{ formatTime(currentLog.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="操作用户">{{ currentLog.username || '匿名' }}</el-descriptions-item>
            <el-descriptions-item label="操作类型">
              <el-tag :type="getActionTagType(currentLog.action)" size="small">
                {{ currentLog.action_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="资源类型">{{ currentLog.resource_type_display }}</el-descriptions-item>
            <el-descriptions-item label="资源ID">{{ currentLog.resource_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="资源名称">{{ currentLog.resource_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作描述">{{ currentLog.description || '-' }}</el-descriptions-item>
            <el-descriptions-item label="请求路径">{{ currentLog.request_path || '-' }}</el-descriptions-item>
            <el-descriptions-item label="请求方法">{{ currentLog.request_method || '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作结果">
              <el-tag :type="getResultTagType(currentLog.result)" size="small">
                {{ currentLog.result_display }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="错误信息" v-if="currentLog.error_message">
              <span class="error-text">{{ currentLog.error_message }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="IP地址">{{ currentLog.ip_address || '-' }}</el-descriptions-item>
            <el-descriptions-item label="User-Agent">
              <span class="ua-text">{{ currentLog.user_agent || '-' }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <!-- 变更数据 -->
          <div class="change-data" v-if="currentLog.old_value || currentLog.new_value">
            <h4>变更数据</h4>
            <div class="change-item" v-if="currentLog.old_value">
              <span class="change-label">变更前:</span>
              <pre class="change-value">{{ formatJson(currentLog.old_value) }}</pre>
            </div>
            <div class="change-item" v-if="currentLog.new_value">
              <span class="change-label">变更后:</span>
              <pre class="change-value">{{ formatJson(currentLog.new_value) }}</pre>
            </div>
          </div>
        </div>
      </el-drawer>
    </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Notebook,
  Refresh,
  Download
} from '@element-plus/icons-vue'
import {
  getAuditLogs,
  exportAuditLogs,
  type AuditLog
} from '@/api/auth'

// 数据状态
const loading = ref(false)
const logList = ref<AuditLog[]>([])
const showDetailDrawer = ref(false)
const currentLog = ref<AuditLog | null>(null)

// 分页
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

// 加载日志列表
const loadLogs = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    
    const res = await getAuditLogs(params)
    const data = (res.data as any).data || res.data
    logList.value = data.results || []
    pagination.total = data.count || 0
  } catch (error) {
    console.error('加载日志失败:', error)
    ElMessage.error('加载日志列表失败')
  } finally {
    loading.value = false
  }
}

// 刷新
const handleRefresh = () => {
  loadLogs()
}

// 分页变化
const handlePageChange = (page: number) => {
  pagination.page = page
  loadLogs()
}

const handleSizeChange = (size: number) => {
  pagination.page_size = size
  pagination.page = 1
  loadLogs()
}

// 行点击
const handleRowClick = (row: AuditLog) => {
  showDetail(row)
}

// 显示详情
const showDetail = (log: AuditLog) => {
  currentLog.value = log
  showDetailDrawer.value = true
}

// 导出日志
const exportLoading = ref(false)
const handleExport = async () => {
  exportLoading.value = true
  try {
    await exportAuditLogs({})
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败，请重试')
  } finally {
    exportLoading.value = false
  }
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 格式化JSON
const formatJson = (jsonStr: string | null) => {
  if (!jsonStr) return '-'
  try {
    const obj = JSON.parse(jsonStr)
    return JSON.stringify(obj, null, 2)
  } catch {
    return jsonStr
  }
}

// 获取操作类型标签颜色
const getActionTagType = (action: string) => {
  const typeMap: Record<string, string> = {
    login: 'success',
    logout: 'info',
    create: 'primary',
    update: 'warning',
    delete: 'danger',
    view: '',
    start: 'success',
    stop: 'warning',
    config: 'primary',
    export: 'info',
    import: 'info'
  }
  return typeMap[action] || ''
}

// 获取结果标签颜色
const getResultTagType = (result: string) => {
  const typeMap: Record<string, string> = {
    success: 'success',
    failed: 'danger',
    partial: 'warning'
  }
  return typeMap[result] || ''
}

// 初始化
onMounted(() => {
  loadLogs()
})
</script>

<style scoped lang="scss">
.audit-log-view {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;

  .header-left {
    .page-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 20px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 8px 0;

      .el-icon {
        color: var(--primary-color);
      }
    }

    .page-desc {
      font-size: 14px;
      color: var(--text-muted);
      margin: 0;
    }
  }

  .header-right {
    display: flex;
    gap: 12px;
  }
}

.log-table-section {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  overflow: hidden;

  :deep(.el-table) {
    --el-table-border-color: var(--border-color);
    --el-table-header-bg-color: var(--bg-elevated);
  }

  :deep(.clickable-row) {
    cursor: pointer;
  }

  .time-text {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .user-text {
    font-weight: 500;
  }

  .resource-text {
    color: var(--text-secondary);
  }

  .ip-text {
    font-family: monospace;
    font-size: 12px;
    color: var(--text-muted);
  }
}

.pagination-wrapper {
  padding: 16px 20px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--border-color);
}

.detail-content {
  padding: 0 4px;

  :deep(.el-descriptions) {
    margin-bottom: 24px;
  }

  .error-text {
    color: #f56c6c;
  }

  .ua-text {
    font-size: 12px;
    color: var(--text-muted);
    word-break: break-all;
  }

  .change-data {
    h4 {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 16px 0;
    }

    .change-item {
      margin-bottom: 16px;

      .change-label {
        display: block;
        font-size: 13px;
        color: var(--text-secondary);
        margin-bottom: 8px;
      }

      .change-value {
        background: var(--bg-elevated);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 12px;
        font-size: 12px;
        font-family: monospace;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-all;
        margin: 0;
      }
    }
  }
}
</style>
