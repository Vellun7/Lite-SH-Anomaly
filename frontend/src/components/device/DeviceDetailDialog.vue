<template>
  <el-dialog
    v-model="visible"
    :title="`设备详情 - ${device?.name}`"
    width="600px"
    :before-close="handleClose"
  >
    <div class="device-detail" v-if="device">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="设备ID">{{ device.device_id }}</el-descriptions-item>
        <el-descriptions-item label="设备名称">{{ device.name }}</el-descriptions-item>
        <el-descriptions-item label="设备类型">{{ device.device_type_display }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ device.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="MAC地址">{{ device.mac_address || '未知' }}</el-descriptions-item>
        <el-descriptions-item label="设备状态">
          <el-tag :type="getStatusType(device.status)">
            {{ device.status_display }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="位置">{{ device.location || '未设置' }}</el-descriptions-item>
        <el-descriptions-item label="是否可信">
          <el-tag :type="device.is_trusted ? 'success' : 'danger'">
            {{ device.is_trusted ? '可信' : '不可信' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="安全评分">
          <div class="security-score">
            <el-progress 
              :percentage="device.security_score" 
              :color="getSecurityColor(device.security_level)"
              :show-text="false"
              :stroke-width="8"
            />
            <span class="score-text">{{ device.security_score.toFixed(1) }}</span>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="安全等级">
          <el-tag :type="getSecurityTagType(device.security_level)">
            {{ getSecurityLevelText(device.security_level) }}
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
        <el-descriptions-item label="最后在线时间" :span="2">
          {{ formatTime(device.last_seen) }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(device.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatTime(device.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <template #footer>
      <el-button @click="handleClose">关闭</el-button>
      <el-button type="primary" @click="editDevice">编辑设备</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '@/api/device'

// Props
interface Props {
  modelValue: boolean
  device: Device | null
}

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
  (e: 'edit', device: Device): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 获取状态类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    online: 'success',
    offline: 'info',
    warning: 'warning'
  }
  return typeMap[status] || 'info'
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

// 格式化时间
const formatTime = (time: string | null) => {
  if (!time) return '未知'
  return new Date(time).toLocaleString()
}

// 编辑设备
const editDevice = () => {
  if (props.device) {
    emit('edit', props.device)
    handleClose()
  }
}

// 处理对话框关闭
const handleClose = () => {
  visible.value = false
}
</script>

<style scoped>
.device-detail {
  padding: 10px 0;
}

.security-score {
  display: flex;
  align-items: center;
  gap: 10px;
}

.score-text {
  font-weight: bold;
  min-width: 35px;
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
</style>