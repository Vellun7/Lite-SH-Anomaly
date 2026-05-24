<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import type { TourInstance } from 'element-plus'

const props = defineProps<{
  /** 是否强制显示（忽略本地存储） */
  force?: boolean
}>()

const emit = defineEmits<{
  (e: 'finish'): void
  (e: 'close'): void
}>()

const tourRef = ref<TourInstance>()
const showTour = ref(false)
const currentStep = ref(0)

// 本地存储 key
const TOUR_COMPLETED_KEY = 'safehome_tour_completed'

// 引导步骤配置
const steps = ref([
  {
    target: '.logo-area',
    title: '👋 欢迎使用 SafeHome',
    description: '这是一个智能家居安全监控系统，帮助您实时检测和防护网络威胁。让我们快速了解一下主要功能！',
    placement: 'right' as const
  },
  {
    target: '.nav-item:nth-child(1)',
    title: '📊 安全概览',
    description: '首页仪表盘展示系统整体安全状态、告警统计、设备状态等核心指标，让您一目了然。',
    placement: 'right' as const
  },
  {
    target: '.nav-item:nth-child(2)',
    title: '🔍 实时检测',
    description: '这里可以对设备流量进行实时异常检测，支持单条检测和持续监控两种模式。',
    placement: 'right' as const
  },
  {
    target: '.nav-item:nth-child(3)',
    title: '📱 设备管理',
    description: '管理您的智能家居设备，包括添加、编辑、删除设备，以及查看设备详情。',
    placement: 'right' as const
  },
  {
    target: '.nav-item:nth-child(4)',
    title: '📋 历史记录',
    description: '查看所有检测记录和告警历史，支持筛选、导出，并可对异常告警进行处理。',
    placement: 'right' as const
  },
  {
    target: '.system-status',
    title: '✅ 系统状态',
    description: '这里显示系统运行状态，绿色表示一切正常，如有异常会变成红色提醒。',
    placement: 'bottom' as const
  },
  {
    target: '.theme-toggle',
    title: '🌓 主题切换',
    description: '点击这里可以在亮色和暗色主题之间切换，保护您的眼睛。',
    placement: 'bottom' as const
  },
  {
    target: '.user-info',
    title: '👤 用户菜单',
    description: '点击头像可以查看个人信息或退出登录。引导结束，开始探索吧！',
    placement: 'bottom' as const
  }
])

// 检查是否需要显示引导
const checkShouldShowTour = () => {
  if (props.force) return true
  const completed = localStorage.getItem(TOUR_COMPLETED_KEY)
  return !completed
}

// 开始引导
const startTour = () => {
  currentStep.value = 0
  showTour.value = true
}

// 引导完成
const handleFinish = () => {
  localStorage.setItem(TOUR_COMPLETED_KEY, 'true')
  showTour.value = false
  emit('finish')
}

// 关闭引导
const handleClose = () => {
  localStorage.setItem(TOUR_COMPLETED_KEY, 'true')
  showTour.value = false
  emit('close')
}

// 重置引导（供外部调用）
const resetTour = () => {
  localStorage.removeItem(TOUR_COMPLETED_KEY)
  nextTick(() => {
    startTour()
  })
}

// 暴露方法
defineExpose({
  startTour,
  resetTour
})

onMounted(() => {
  // 延迟检查，确保 DOM 已渲染
  setTimeout(() => {
    if (checkShouldShowTour()) {
      startTour()
    }
  }, 500)
})

// 监听 force 变化
watch(() => props.force, (val) => {
  if (val) {
    startTour()
  }
})
</script>

<template>
  <el-tour
    ref="tourRef"
    v-model="showTour"
    v-model:current="currentStep"
    :mask="{ style: { boxShadow: 'inset 0 0 15px #333' } }"
    @finish="handleFinish"
    @close="handleClose"
  >
    <el-tour-step
      v-for="(step, index) in steps"
      :key="index"
      :target="step.target"
      :title="step.title"
      :description="step.description"
      :placement="step.placement"
    >
      <template #default>
        <div class="tour-content">
          <p>{{ step.description }}</p>
          <div class="tour-progress">
            <span class="progress-text">{{ index + 1 }} / {{ steps.length }}</span>
            <div class="progress-bar">
              <div 
                class="progress-fill" 
                :style="{ width: `${((index + 1) / steps.length) * 100}%` }"
              ></div>
            </div>
          </div>
        </div>
      </template>
    </el-tour-step>
  </el-tour>
</template>

<style lang="scss" scoped>
.tour-content {
  p {
    margin: 0 0 16px;
    line-height: 1.6;
    color: var(--el-text-color-regular);
  }
}

.tour-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  
  .progress-text {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    white-space: nowrap;
  }
  
  .progress-bar {
    flex: 1;
    height: 4px;
    background: var(--el-fill-color-light);
    border-radius: 2px;
    overflow: hidden;
    
    .progress-fill {
      height: 100%;
      background: var(--el-color-primary);
      border-radius: 2px;
      transition: width 0.3s ease;
    }
  }
}
</style>

<style lang="scss">
/* 全局样式覆盖 Tour 组件 */
.el-tour {
  --el-tour-title-font-size: 16px;
  --el-tour-title-font-weight: 600;
  
  .el-tour__content {
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  }
  
  .el-tour__title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 8px;
  }
  
  .el-tour__body {
    padding: 16px;
  }
  
  .el-tour__footer {
    padding: 12px 16px;
    border-top: 1px solid var(--el-border-color-lighter);
  }
  
  .el-tour__closebtn {
    top: 12px;
    right: 12px;
  }
}
</style>
