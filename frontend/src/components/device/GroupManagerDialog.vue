<template>
  <el-dialog
    v-model="visible"
    title="设备分组管理"
    width="750px"
    :before-close="handleClose"
    class="group-manager-dialog"
  >
    <div class="group-manager">
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-button type="primary" @click="showCreateGroup = true">
          <el-icon><Plus /></el-icon>
          新建分组
        </el-button>
        <el-button @click="loadGroups">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <!-- 分组列表 -->
      <div class="group-list">
        <el-table :data="groups" v-loading="loading" row-key="id">
          <el-table-column prop="name" label="分组名称" min-width="120">
            <template #default="{ row }">
              <div class="group-name">
                <el-icon :style="{ color: row.color }">
                  <Collection v-if="row.icon === 'collection'" />
                  <Folder v-else />
                </el-icon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
          <el-table-column prop="device_count" label="设备数量" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" type="info" effect="plain" round>
                {{ row.device_count }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="parent_name" label="父分组" width="100">
            <template #default="{ row }">
              <span v-if="row.parent_name">{{ row.parent_name }}</span>
              <span v-else class="no-parent">顶级分组</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <div class="action-links">
                <el-link type="primary" :underline="false" @click="editGroup(row)">
                  编辑
                </el-link>
                <el-divider direction="vertical" />
                <el-link type="primary" :underline="false" @click="viewGroupDevices(row)">
                  设备
                </el-link>
                <el-divider direction="vertical" />
                <el-link 
                  :type="row.device_count > 0 ? 'info' : 'danger'" 
                  :underline="false" 
                  :disabled="row.device_count > 0"
                  @click="deleteGroup(row)"
                >
                  删除
                </el-link>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 创建分组对话框 -->
    <el-dialog
      v-model="showCreateGroup"
      title="创建设备分组"
      width="500px"
      append-to-body
    >
      <el-form :model="groupForm" :rules="groupRules" ref="groupFormRef" label-width="80px">
        <el-form-item label="分组名称" prop="name">
          <el-input v-model="groupForm.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="分组描述" prop="description">
          <el-input 
            v-model="groupForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="请输入分组描述（可选）" 
          />
        </el-form-item>
        <el-form-item label="分组图标" prop="icon">
          <el-select v-model="groupForm.icon" placeholder="选择图标">
            <el-option label="文件夹" value="folder">
              <el-icon><Folder /></el-icon>
              <span style="margin-left: 8px;">文件夹</span>
            </el-option>
            <el-option label="集合" value="collection">
              <el-icon><Collection /></el-icon>
              <span style="margin-left: 8px;">集合</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="分组颜色" prop="color">
          <el-color-picker v-model="groupForm.color" />
        </el-form-item>
        <el-form-item label="父分组" prop="parent">
          <el-select v-model="groupForm.parent" placeholder="选择父分组（可选）" clearable>
            <el-option 
              v-for="group in groups.filter(g => g.id !== editingGroup?.id)" 
              :key="group.id" 
              :label="group.name" 
              :value="group.id" 
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateGroup = false">取消</el-button>
        <el-button type="primary" @click="handleCreateGroup" :loading="submitting">
          {{ editingGroup ? '更新' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 分组设备查看对话框 -->
    <el-dialog
      v-model="showGroupDevices"
      :title="`${currentGroup?.name} - 设备列表`"
      width="700px"
      append-to-body
    >
      <el-table :data="groupDevices" v-loading="loadingDevices">
        <el-table-column prop="name" label="设备名称" />
        <el-table-column prop="device_type_display" label="设备类型" />
        <el-table-column prop="ip_address" label="IP地址" />
        <el-table-column label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="安全评分">
          <template #default="{ row }">
            <el-progress 
              :percentage="row.security_score" 
              :color="getSecurityColor(row.security_level)"
              :show-text="false"
              :stroke-width="6"
            />
            <span style="margin-left: 8px;">{{ row.security_score.toFixed(1) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showGroupDevices = false">关闭</el-button>
      </template>
    </el-dialog>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Collection, Folder } from '@element-plus/icons-vue'

import {
  getDeviceGroups, createDeviceGroup, updateDeviceGroup, deleteDeviceGroup,
  getGroupDevices, type DeviceGroup, type Device
} from '@/api/device'

// Props
interface Props {
  modelValue: boolean
}

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const loading = ref(false)
const submitting = ref(false)
const loadingDevices = ref(false)

const groups = ref<DeviceGroup[]>([])
const groupDevices = ref<Device[]>([])

const showCreateGroup = ref(false)
const showGroupDevices = ref(false)

const editingGroup = ref<DeviceGroup | null>(null)
const currentGroup = ref<DeviceGroup | null>(null)

// 表单数据
const groupForm = ref({
  name: '',
  description: '',
  icon: 'folder',
  color: '#409EFF',
  parent: null as number | null
})

// 表单验证规则
const groupRules: FormRules = {
  name: [
    { required: true, message: '请输入分组名称', trigger: 'blur' },
    { min: 1, max: 50, message: '分组名称长度在 1 到 50 个字符', trigger: 'blur' }
  ]
}

const groupFormRef = ref<FormInstance>()

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 加载分组列表
const loadGroups = async () => {
  loading.value = true
  try {
    const res = await getDeviceGroups()
    const data = (res.data as any).data || res.data
    groups.value = data || []
  } catch (error) {
    console.error('加载分组列表失败:', error)
    ElMessage.error('加载分组列表失败')
  } finally {
    loading.value = false
  }
}

// 编辑分组
const editGroup = (group: DeviceGroup) => {
  editingGroup.value = group
  groupForm.value = {
    name: group.name,
    description: group.description,
    icon: group.icon,
    color: group.color,
    parent: group.parent
  }
  showCreateGroup.value = true
}

// 处理创建/更新分组
const handleCreateGroup = async () => {
  if (!groupFormRef.value) return
  
  try {
    await groupFormRef.value.validate()
    submitting.value = true
    
    if (editingGroup.value) {
      // 更新分组
      await updateDeviceGroup(editingGroup.value.id, groupForm.value)
      ElMessage.success('分组更新成功')
    } else {
      // 创建分组
      await createDeviceGroup(groupForm.value)
      ElMessage.success('分组创建成功')
    }
    
    showCreateGroup.value = false
    resetForm()
    loadGroups()
    emit('refresh')
  } catch (error) {
    console.error('操作分组失败:', error)
    ElMessage.error('操作分组失败')
  } finally {
    submitting.value = false
  }
}

// 删除分组
const deleteGroup = async (group: DeviceGroup) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除分组 "${group.name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await deleteDeviceGroup(group.id)
    ElMessage.success('分组删除成功')
    loadGroups()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除分组失败:', error)
      ElMessage.error('删除分组失败')
    }
  }
}

// 查看分组设备
const viewGroupDevices = async (group: DeviceGroup) => {
  currentGroup.value = group
  loadingDevices.value = true
  showGroupDevices.value = true
  
  try {
    const res = await getGroupDevices(group.id, { page_size: 100 })
    const data = (res.data as any).data || res.data
    groupDevices.value = data.results || []
  } catch (error) {
    console.error('加载分组设备失败:', error)
    ElMessage.error('加载分组设备失败')
  } finally {
    loadingDevices.value = false
  }
}

// 重置表单
const resetForm = () => {
  editingGroup.value = null
  groupForm.value = {
    name: '',
    description: '',
    icon: 'folder',
    color: '#409EFF',
    parent: null
  }
  groupFormRef.value?.resetFields()
}

// 处理对话框关闭
const handleClose = () => {
  resetForm()
  visible.value = false
}

// 格式化时间
const formatTime = (time: string) => {
  return new Date(time).toLocaleString()
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

// 获取安全评分颜色
const getSecurityColor = (level: string) => {
  const colorMap: Record<string, string> = {
    high: '#67C23A',
    medium: '#E6A23C',
    low: '#F56C6C'
  }
  return colorMap[level] || '#909399'
}

// 监听对话框打开，加载分组数据
watch(visible, (newVal) => {
  if (newVal) {
    loadGroups()
  }
})
</script>

<style scoped>
.group-manager-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}

.group-manager {
  padding: 0;
}

.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}

.group-list {
  border-radius: 6px;
  overflow: hidden;
}

.group-list :deep(.el-table) {
  --el-table-border-color: #ebeef5;
}

.group-list :deep(.el-table th) {
  background-color: #fafafa;
  font-weight: 500;
  color: #606266;
}

.group-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-name .el-icon {
  font-size: 16px;
}

.no-parent {
  color: #c0c4cc;
  font-size: 12px;
}

.action-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.action-links .el-link {
  font-size: 13px;
  padding: 0 2px;
}

.action-links .el-divider--vertical {
  margin: 0 4px;
  height: 12px;
}

/* 优化badge样式 */
.group-list :deep(.el-tag--info) {
  background-color: #f0f2f5;
  border-color: #e4e7ed;
  color: #606266;
}
</style>