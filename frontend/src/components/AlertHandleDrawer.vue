<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { DetectionRecord } from '@/api/detection'
import type { Device } from '@/api/device'

const props = defineProps<{
  visible: boolean
  record: DetectionRecord | null
  device: Device | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'handled', record: DetectionRecord, note: string): void
}>()

// 处理步骤
const currentStep = ref(0)
const handleNote = ref('')
const selectedAction = ref('')

// 处理措施选项
const actionOptions = [
  { value: 'block_ip', label: '封禁源IP', icon: 'Lock', desc: '阻止该IP地址的后续访问' },
  { value: 'isolate_device', label: '隔离设备', icon: 'Warning', desc: '将设备从网络中临时隔离' },
  { value: 'reset_connection', label: '重置连接', icon: 'Refresh', desc: '断开并重新建立设备连接' },
  { value: 'ignore', label: '标记为误报', icon: 'Check', desc: '确认为正常行为，忽略此告警' },
  { value: 'monitor', label: '持续观察', icon: 'View', desc: '暂不处理，加入重点监控列表' }
]

// 步骤配置
const steps = [
  { title: '查看详情', description: '了解告警信息' },
  { title: '分析原因', description: '判断威胁类型' },
  { title: '采取措施', description: '选择处理方式' },
  { title: '确认完成', description: '填写处理备注' }
]

// 攻击类型说明
const attackTypeInfo = computed(() => {
  if (!props.record) return null
  const infoMap: Record<string, { title: string; desc: string; suggestion: string }> = {
    ddos: {
      title: 'DDoS 分布式拒绝服务攻击',
      desc: '攻击者通过大量请求占用系统资源，导致正常服务无法响应。',
      suggestion: '建议：封禁源IP或启用流量限制'
    },
    port_scan: {
      title: '端口扫描',
      desc: '攻击者尝试探测开放的端口，寻找系统漏洞。',
      suggestion: '建议：检查防火墙规则，关闭不必要的端口'
    },
    unauthorized: {
      title: '越权访问',
      desc: '未经授权的访问尝试，可能是凭证泄露或暴力破解。',
      suggestion: '建议：重置设备密码，检查访问日志'
    },
    malformed: {
      title: '异常指令',
      desc: '设备接收到格式异常或恶意构造的指令。',
      suggestion: '建议：检查设备固件，隔离设备进行排查'
    },
    unknown: {
      title: '未知异常',
      desc: '检测到异常行为模式，但无法归类到已知攻击类型。',
      suggestion: '建议：持续观察，收集更多信息进行分析'
    }
  }
  return infoMap[props.record.attack_type] || {
    title: '未知类型',
    desc: '暂无该类型的详细说明',
    suggestion: '建议：联系安全专家进行分析'
  }
})

// 威胁等级
const threatLevel = computed(() => {
  if (!props.record) return 'low'
  if (props.record.confidence >= 0.8) return 'high'
  if (props.record.confidence >= 0.5) return 'medium'
  return 'low'
})

const threatLevelText = computed(() => {
  const map = { high: '高危', medium: '中危', low: '低危' }
  return map[threatLevel.value]
})

const threatLevelType = computed(() => {
  const map = { high: 'danger', medium: 'warning', low: 'success' }
  return map[threatLevel.value] as 'danger' | 'warning' | 'success'
})

// 下一步
const nextStep = () => {
  if (currentStep.value < steps.length - 1) {
    currentStep.value++
  }
}

// 上一步
const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

// 确认处理
const confirmHandle = () => {
  if (!selectedAction.value) {
    ElMessage.warning('请选择处理措施')
    return
  }
  
  const actionLabel = actionOptions.find(a => a.value === selectedAction.value)?.label || ''
  const fullNote = `[${actionLabel}] ${handleNote.value}`.trim()
  
  emit('handled', props.record!, fullNote)
  emit('update:visible', false)
  
  ElMessage.success('告警已处理')
  
  // 重置状态
  currentStep.value = 0
  handleNote.value = ''
  selectedAction.value = ''
}

// 关闭时重置
watch(() => props.visible, (val) => {
  if (!val) {
    currentStep.value = 0
    handleNote.value = ''
    selectedAction.value = ''
  }
})

// 是否可以进入下一步
const canNext = computed(() => {
  if (currentStep.value === 2) {
    return !!selectedAction.value
  }
  return true
})

// 关闭抽屉
const handleClose = () => {
  emit('update:visible', false)
}
</script>

<template>
  <el-drawer
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="告警处理"
    direction="rtl"
    size="500px"
    :before-close="handleClose"
  >
    <div class="handle-drawer" v-if="record">
      <!-- 步骤条 -->
      <el-steps :active="currentStep" finish-status="success" class="steps">
        <el-step
          v-for="(step, index) in steps"
          :key="index"
          :title="step.title"
          :description="step.description"
        />
      </el-steps>

      <!-- 步骤内容 -->
      <div class="step-content">
        <!-- 步骤1：查看详情 -->
        <div v-if="currentStep === 0" class="step-panel">
          <h3>告警详情</h3>
          
          <div class="info-card">
            <div class="info-header">
              <el-tag :type="threatLevelType" size="large">{{ threatLevelText }}</el-tag>
              <span class="confidence">置信度: {{ (record.confidence * 100).toFixed(0) }}%</span>
            </div>
            
            <el-descriptions :column="1" border class="info-desc">
              <el-descriptions-item label="设备名称">
                {{ device?.name || record.device_id }}
              </el-descriptions-item>
              <el-descriptions-item label="设备ID">
                {{ record.device_id }}
              </el-descriptions-item>
              <el-descriptions-item label="发生时间">
                {{ record.timestamp }}
              </el-descriptions-item>
              <el-descriptions-item label="源IP">
                {{ record.src_ip || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="目标IP">
                {{ record.dst_ip || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="协议">
                {{ record.protocol || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="异常分数">
                {{ record.anomaly_score?.toFixed(4) || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <!-- 步骤2：分析原因 -->
        <div v-if="currentStep === 1" class="step-panel">
          <h3>威胁分析</h3>
          
          <div class="analysis-card" v-if="attackTypeInfo">
            <div class="attack-type">
              <el-icon size="24"><WarningFilled /></el-icon>
              <span>{{ attackTypeInfo.title }}</span>
            </div>
            
            <div class="attack-desc">
              <p>{{ attackTypeInfo.desc }}</p>
            </div>
            
            <el-alert
              :title="attackTypeInfo.suggestion"
              type="info"
              :closable="false"
              show-icon
            />
          </div>
          
          <div class="traffic-info">
            <h4>流量特征</h4>
            <div class="traffic-grid">
              <div class="traffic-item">
                <span class="label">发送字节</span>
                <span class="value">{{ record.orig_bytes || 0 }}</span>
              </div>
              <div class="traffic-item">
                <span class="label">接收字节</span>
                <span class="value">{{ record.resp_bytes || 0 }}</span>
              </div>
              <div class="traffic-item">
                <span class="label">发送包数</span>
                <span class="value">{{ record.orig_pkts || 0 }}</span>
              </div>
              <div class="traffic-item">
                <span class="label">接收包数</span>
                <span class="value">{{ record.resp_pkts || 0 }}</span>
              </div>
              <div class="traffic-item">
                <span class="label">持续时间</span>
                <span class="value">{{ record.duration?.toFixed(2) || 0 }}s</span>
              </div>
              <div class="traffic-item">
                <span class="label">推理耗时</span>
                <span class="value">{{ record.inference_time?.toFixed(2) || 0 }}ms</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 步骤3：采取措施 -->
        <div v-if="currentStep === 2" class="step-panel">
          <h3>选择处理措施</h3>
          
          <div class="action-list">
            <div
              v-for="action in actionOptions"
              :key="action.value"
              class="action-item"
              :class="{ active: selectedAction === action.value }"
              @click="selectedAction = action.value"
            >
              <div class="action-icon">
                <el-icon size="20">
                  <component :is="action.icon" />
                </el-icon>
              </div>
              <div class="action-content">
                <div class="action-label">{{ action.label }}</div>
                <div class="action-desc">{{ action.desc }}</div>
              </div>
              <el-icon v-if="selectedAction === action.value" class="action-check">
                <CircleCheckFilled />
              </el-icon>
            </div>
          </div>
        </div>

        <!-- 步骤4：确认完成 -->
        <div v-if="currentStep === 3" class="step-panel">
          <h3>确认处理</h3>
          
          <div class="summary-card">
            <div class="summary-item">
              <span class="label">处理措施</span>
              <el-tag type="primary">
                {{ actionOptions.find(a => a.value === selectedAction)?.label }}
              </el-tag>
            </div>
            <div class="summary-item">
              <span class="label">目标设备</span>
              <span class="value">{{ device?.name || record.device_id }}</span>
            </div>
            <div class="summary-item">
              <span class="label">告警类型</span>
              <span class="value">{{ attackTypeInfo?.title }}</span>
            </div>
          </div>
          
          <div class="note-input">
            <label>处理备注（可选）</label>
            <el-input
              v-model="handleNote"
              type="textarea"
              :rows="3"
              placeholder="请输入处理备注，例如：已确认为测试流量，标记为误报"
            />
          </div>
        </div>
      </div>

      <!-- 底部按钮 -->
      <div class="drawer-footer">
        <el-button v-if="currentStep > 0" @click="prevStep">
          上一步
        </el-button>
        <el-button v-if="currentStep < steps.length - 1" type="primary" @click="nextStep" :disabled="!canNext">
          下一步
        </el-button>
        <el-button v-if="currentStep === steps.length - 1" type="success" @click="confirmHandle">
          确认处理
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<style lang="scss" scoped>
.handle-drawer {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 4px;
}

.steps {
  margin-bottom: 24px;
  
  :deep(.el-step__title) {
    font-size: 13px;
  }
  
  :deep(.el-step__description) {
    font-size: 11px;
  }
}

.step-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 80px;
}

.step-panel {
  h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 16px;
    color: var(--el-text-color-primary);
  }
  
  h4 {
    font-size: 14px;
    font-weight: 500;
    margin: 16px 0 12px;
    color: var(--el-text-color-regular);
  }
}

.info-card {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 16px;
  
  .info-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    
    .confidence {
      font-size: 14px;
      color: var(--el-text-color-secondary);
    }
  }
  
  .info-desc {
    :deep(.el-descriptions__label) {
      width: 80px;
    }
  }
}

.analysis-card {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 16px;
  
  .attack-type {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: var(--el-color-danger);
    margin-bottom: 12px;
  }
  
  .attack-desc {
    color: var(--el-text-color-regular);
    margin-bottom: 12px;
    line-height: 1.6;
  }
}

.traffic-info {
  margin-top: 20px;
}

.traffic-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  
  .traffic-item {
    background: var(--el-fill-color-light);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    
    .label {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
    
    .value {
      font-size: 16px;
      font-weight: 600;
      color: var(--el-text-color-primary);
    }
  }
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--el-fill-color-light);
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: var(--el-fill-color);
  }
  
  &.active {
    border-color: var(--el-color-primary);
    background: var(--el-color-primary-light-9);
  }
  
  .action-icon {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--el-color-primary-light-8);
    border-radius: 8px;
    color: var(--el-color-primary);
  }
  
  .action-content {
    flex: 1;
    
    .action-label {
      font-size: 14px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }
    
    .action-desc {
      font-size: 12px;
      color: var(--el-text-color-secondary);
      margin-top: 2px;
    }
  }
  
  .action-check {
    color: var(--el-color-primary);
  }
}

.summary-card {
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  
  .summary-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    
    &:not(:last-child) {
      border-bottom: 1px solid var(--el-border-color-lighter);
    }
    
    .label {
      font-size: 13px;
      color: var(--el-text-color-secondary);
    }
    
    .value {
      font-size: 13px;
      font-weight: 500;
      color: var(--el-text-color-primary);
    }
  }
}

.note-input {
  label {
    display: block;
    font-size: 13px;
    color: var(--el-text-color-regular);
    margin-bottom: 8px;
  }
}

.drawer-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px 20px;
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
