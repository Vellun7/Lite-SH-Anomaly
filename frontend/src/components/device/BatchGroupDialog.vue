<template>
  <el-dialog
    v-model="visible"
    title="批量分组管理"
    width="600px"
    :before-close="handleClose"
  >
    <div class="batch-group">
      <!-- 选中设备列表 -->
      <div class="selected-devices">
        <h4>已选择设备 ({{ devices.length }}个)</h4>
        <div class="device-list">
          <el-tag 
            v-for="device in devices" 
            :key="device.device_id"
            closable
            @close="removeDevice(device)"
            class="device-tag"
          >
            {{ device.name }}
          </el-tag>
        </div>
      </div>

      <!-- 分组选择 -->
      <div class="group-selection">
        <h4>选择分组</h4>
        <el-checkbox-group v-model="selectedGroups">
          <el-checkbox 
            v-for="group in groups" 
            :key="group.id" 
            :label="group.id"
            class="group-checkbox"
          >
            <div class="group-item">
              <el-icon :style="{ color: group.color }">
                <Collection v-if="group.icon === 'collection'" />
                <Folder v-else />
              </el-icon>
              <span>{{ group.name }}</span>
              <el-badge :value="group.device_count" class="group-badge" />
            </div>
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <!-- 操作选项 -->
      <div class="operation-options">
        <el-radio-group v-model="operation">
          <el-radio label="replace">替换现有分组</el-radio>
          <el-radio label="add">添加到分组</el-radio>
        </el-radio-group>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button 
        type="primary" 
        @click="handleSubmit" 
        :loading="submitting"
        :disabled="selectedGroups.length === 0"
      >
        确定分配
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Collection, Folder } from '@element-plus/icons-vue'
import { batchAssignGroups, type Device, type DeviceGroup } from '@/api/device'

// Props
interface Props {
  modelValue: boolean
  devices: Device[]
  groups: DeviceGroup[]
}

// Emits
interface Emits {
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// 响应式数据
const submitting = ref(false)
const selectedGroups = ref<number[]>([])
const operation = ref<'replace' | 'add'>('replace')

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 移除设备
const removeDevice = (device: Device) => {
  // 这里需要通过事件通知父组件移除设备
  // 暂时不实现，因为需要修改父组件的选择逻辑
}

// 处理提交
const handleSubmit = async () => {
  if (selectedGroups.value.length === 0) {
    ElMessage.warning('请选择至少一个分组')
    return
  }

  submitting.value = true
  try {
    const deviceIds = props.devices.map(d => d.device_id)
    await batchAssignGroups(deviceIds, selectedGroups.value)
    
    ElMessage.success(`成功将 ${props.devices.length} 个设备分配到 ${selectedGroups.value.length} 个分组`)
    emit('refresh')
    handleClose()
  } catch (error) {
    console.error('批量分组失败:', error)
    ElMessage.error('批量分组失败')
  } finally {
    submitting.value = false
  }
}

// 重置表单
const resetForm = () => {
  selectedGroups.value = []
  operation.value = 'replace'
}

// 处理对话框关闭
const handleClose = () => {
  resetForm()
  visible.value = false
}
</script>

<style scoped>
.batch-group {
  padding: 10px 0;
}

.selected-devices {
  margin-bottom: 20px;
}

.selected-devices h4 {
  margin: 0 0 10px 0;
  color: #303133;
}

.device-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 40px;
  padding: 10px;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  background-color: #fafafa;
}

.device-tag {
  margin: 0;
}

.group-selection {
  margin-bottom: 20px;
}

.group-selection h4 {
  margin: 0 0 15px 0;
  color: #303133;
}

.group-checkbox {
  display: block;
  margin-bottom: 10px;
  width: 100%;
}

.group-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
}

.group-item:hover {
  background-color: #f5f7fa;
}

.group-badge {
  margin-left: auto;
}

.operation-options {
  padding: 15px;
  background-color: #f8f9fa;
  border-radius: 4px;
}
</style>