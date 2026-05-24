<template>
  <el-dialog
    v-model="visible"
    :title="device ? '编辑设备' : '创建设备'"
    width="500px"
    :before-close="handleClose"
  >
    <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
      <el-form-item label="设备ID" prop="device_id" v-if="!device">
        <el-input v-model="form.device_id" placeholder="请输入设备ID" />
      </el-form-item>
      <el-form-item label="设备名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入设备名称" />
      </el-form-item>
      <el-form-item label="设备类型" prop="device_type">
        <el-select v-model="form.device_type" placeholder="选择设备类型" style="width: 100%;">
          <el-option label="智能摄像头" value="camera" />
          <el-option label="智能门锁" value="door_lock" />
          <el-option label="传感器" value="sensor" />
          <el-option label="网关" value="gateway" />
          <el-option label="其他" value="other" />
        </el-select>
      </el-form-item>
      <el-form-item label="IP地址" prop="ip_address">
        <el-input v-model="form.ip_address" placeholder="请输入IP地址" />
      </el-form-item>
      <el-form-item label="MAC地址" prop="mac_address">
        <el-input v-model="form.mac_address" placeholder="请输入MAC地址（可选）" />
      </el-form-item>
      <el-form-item label="设备位置" prop="location">
        <el-input v-model="form.location" placeholder="请输入设备位置（可选）" />
      </el-form-item>
      <el-form-item label="是否可信" prop="is_trusted" v-if="device">
        <el-switch v-model="form.is_trusted" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="submitting">
        {{ device ? '更新' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createDevice, updateDevice, addDevicesToGroup, type Device } from '@/api/device'

// Props
interface Props {
  modelValue: boolean
  device: Device | null
  defaultGroupId?: number | null
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
const formRef = ref<FormInstance>()

// 表单数据
const form = ref({
  device_id: '',
  name: '',
  device_type: '',
  ip_address: '',
  mac_address: '',
  location: '',
  is_trusted: true
})

// 表单验证规则
const rules: FormRules = {
  device_id: [
    { required: true, message: '请输入设备ID', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入设备名称', trigger: 'blur' }
  ],
  device_type: [
    { required: true, message: '请选择设备类型', trigger: 'change' }
  ],
  ip_address: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    { 
      pattern: /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/,
      message: '请输入有效的IP地址',
      trigger: 'blur'
    }
  ]
}

// 计算属性
const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// 重置表单
const resetForm = () => {
  form.value = {
    device_id: '',
    name: '',
    device_type: '',
    ip_address: '',
    mac_address: '',
    location: '',
    is_trusted: true
  }
  formRef.value?.resetFields()
}

// 填充表单数据
const fillForm = (device: Device) => {
  form.value = {
    device_id: device.device_id,
    name: device.name,
    device_type: device.device_type,
    ip_address: device.ip_address,
    mac_address: device.mac_address || '',
    location: device.location || '',
    is_trusted: device.is_trusted
  }
}

// 处理提交
const handleSubmit = async () => {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
    submitting.value = true
    
    if (props.device) {
      // 更新设备
      await updateDevice(props.device.device_id, form.value)
      ElMessage.success('设备更新成功')
    } else {
      // 创建设备
      await createDevice(form.value)
      // 如果指定了默认分组，自动将设备加入该分组
      if (props.defaultGroupId) {
        await addDevicesToGroup(props.defaultGroupId, [form.value.device_id])
      }
      ElMessage.success('设备创建成功')
    }

    emit('refresh')
    handleClose()
  } catch (error) {
    console.error('操作设备失败:', error)
    ElMessage.error('操作设备失败')
  } finally {
    submitting.value = false
  }
}

// 处理对话框关闭
const handleClose = () => {
  resetForm()
  visible.value = false
}

// 监听设备变化
watch(() => props.device, (newDevice) => {
  if (newDevice) {
    fillForm(newDevice)
  } else {
    resetForm()
  }
}, { immediate: true })
</script>

<style scoped>
/* 样式可以根据需要添加 */
</style>