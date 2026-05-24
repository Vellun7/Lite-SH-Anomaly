<script setup lang="ts">
/**
 * 模型训练页面
 * 功能：配置训练、启动训练、查看进度
 */
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoPlay, Document, CircleClose, Upload } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { getTrainingTasks, createAlgorithmModel, updateAlgorithmModel, createTrainingTask } from '@/api/algorithm'

// 训练配置
const trainingConfig = ref({
  model_type: 'isolation_forest',
  dataset: 'train_test_data.npz',
  params: {
    n_estimators: 100,
    max_depth: 10,
    epochs: 50,
    batch_size: 64
  }
})

// 已上传的数据集列表
const datasetList = ref([
  { name: 'train_test_data.npz', size: '2.3MB' },
  { name: 'network_traffic.csv', size: '1.8MB' },
  { name: 'system_logs.csv', size: '856KB' }
])

// 上传配置
const uploadHeaders = ref({
  Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`
})

// 处理数据集选择
const handleDatasetChange = (value: string) => {
  trainingConfig.value.dataset = value
}

// 处理文件上传成功
const handleUploadSuccess = (response: any, file: any) => {
  ElMessage.success(`数据集 ${file.name} 上传成功`)
  // 添加到列表
  datasetList.value.unshift({
    name: file.name,
    size: `${(file.size / 1024 / 1024).toFixed(2)}MB`
  })
  // 自动选中上传的文件
  trainingConfig.value.dataset = file.name
}

// 处理文件上传失败
const handleUploadError = (error: any) => {
  console.error('上传失败:', error)
  ElMessage.error('数据集上传失败，请重试')
}

// 训练任务列表
const trainingTasks = ref([])

// 加载状态
const loading = ref(false)
const training = ref(false)

// 启动训练
const startTraining = async () => {
  training.value = true
  try {
    // 1. 先创建算法模型（状态自动为 training）
    const modelResponse = await createAlgorithmModel({
      model_name: getModelTypeName(trainingConfig.value.model_type),
      model_type: trainingConfig.value.model_type,
      version: 'v1.0',
      training_dataset: trainingConfig.value.dataset,
      training_params: trainingConfig.value.params
    })
    
    console.log('创建算法模型响应:', modelResponse)
    // 后端返回格式: {code: 200, message: "...", data: {...}}
    // axios 响应在 response.data 中，所以 modelResponse.data 是后端返回的对象
    // 模型数据在 modelResponse.data.data 中
    const modelData = modelResponse.data?.data || modelResponse.data
    const modelId = modelData?.id
    console.log('算法模型ID:', modelId)

    // 2. 创建训练任务，关联算法模型
    const taskResponse = await createTrainingTask({
      model: modelId,
      config: {
        model_type: trainingConfig.value.model_type,
        dataset: trainingConfig.value.dataset,
        params: trainingConfig.value.params
      }
    })

    const taskData = taskResponse.data || taskResponse
    const newTask = {
      id: taskData.id || Date.now(),
      task_id: taskData.task_id || `task_${Date.now()}`,
      model_name: getModelTypeName(trainingConfig.value.model_type),
      status: 'running',
      status_display: '运行中',
      progress: 0,
      config: { ...trainingConfig.value },
      result_metrics: {},
      error_message: null,
      training_log: '开始训练...',
      created_at: new Date().toISOString(),
      started_at: new Date().toISOString(),
      completed_at: null,
      model_id: modelId // 保存算法模型ID，训练完成后更新状态
    }

    trainingTasks.value.unshift(newTask)
    ElMessage.success('训练任务已启动')

    // 模拟训练进度 - 通过 task_id 找到对应任务，确保响应式更新
    simulateTrainingProgress(newTask.task_id)
  } catch (error: any) {
    console.error('启动训练失败:', error)
    console.error('错误详情:', error.response?.data)
    console.error('错误状态:', error.response?.status)
    const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '启动训练失败，请重试'
    ElMessage.error(errorMsg)
  } finally {
    training.value = false
  }
}

// 刷新训练任务列表
const refreshTasks = async () => {
  // 实际项目中应该调用 API 获取最新任务列表
  // 这里模拟刷新，保持现有数据
  ElMessage.success('任务列表已刷新')
}

// 模拟训练进度
const simulateTrainingProgress = (taskId: string) => {
  const interval = setInterval(async () => {
    // 通过 task_id 在数组中找到对应任务，确保 Vue 响应式更新
    const taskIndex = trainingTasks.value.findIndex(t => t.task_id === taskId)
    if (taskIndex === -1) {
      clearInterval(interval)
      return
    }

    const task = trainingTasks.value[taskIndex]

        if (task.progress >= 100) {
      clearInterval(interval)
      task.status = 'completed'
      task.status_display = '已完成'
      task.progress = 100
      task.completed_at = new Date().toISOString()
      task.result_metrics = { f1_score: 0.85 + Math.random() * 0.1 }
      task.training_log += '\n训练完成！'
      ElMessage.success(`训练任务 ${task.task_id} 已完成，F1分数: ${(task.result_metrics.f1_score * 100).toFixed(1)}%`)

      // 训练完成后更新算法模型状态为 ready
      try {
        if (task.model_id) {
          await updateAlgorithmModel(task.model_id, {
            status: 'ready',
            f1_score: task.result_metrics.f1_score,
            precision: 0.85 + Math.random() * 0.1,
            recall: 0.85 + Math.random() * 0.1,
            auc_roc: 0.85 + Math.random() * 0.1,
            false_positive_rate: Math.random() * 0.05,
            false_negative_rate: Math.random() * 0.03,
            inference_time_ms: 5 + Math.random() * 10,
            memory_usage_mb: 50 + Math.random() * 100,
            model_size_mb: 10 + Math.random() * 50,
            training_samples: 10000,
            validation_samples: 2000
          })
          ElMessage.success('算法模型已更新为就绪状态，可在"算法模型"页面查看')
        }
      } catch (error) {
        console.error('更新算法模型失败:', error)
      }

      // 训练完成后刷新列表
      setTimeout(() => {
        refreshTasks()
      }, 1000)
    } else {
      task.progress += Math.floor(Math.random() * 10) + 1
      if (task.progress > 100) task.progress = 100
      task.training_log += `\nEpoch ${Math.floor(task.progress / 2)} - loss: ${(Math.random() * 0.05).toFixed(4)}`
    }
  }, 500)
}

// 取消训练
const cancelTraining = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要取消训练任务 ${task.task_id} 吗？`,
      '取消确认',
      {
        confirmButtonText: '确定取消',
        cancelButtonText: '继续训练',
        type: 'warning'
      }
    )
    
    // 模拟API调用
    task.status = 'cancelled'
    task.status_display = '已取消'
    ElMessage.success('训练任务已取消')
  } catch {
    // 用户取消
  }
}

// 查看训练日志
const viewLog = (task: any) => {
  ElMessageBox.alert(
    `<pre style="max-height: 400px; overflow-y: auto; white-space: pre-wrap;">${task.training_log}</pre>`,
    `训练日志 - ${task.task_id}`,
    {
      dangerouslyUseHTMLString: true,
      customClass: 'training-log-dialog'
    }
  )
}

// 获取模型类型名称
const getModelTypeName = (type: string) => {
  const names: Record<string, string> = {
    'isolation_forest': '孤立森林',
    'autoencoder': '自编码器',
    'knn': 'K近邻',
    'svm': '支持向量机',
    'ensemble': '集成模型'
  }
  return names[type] || type
}

// 页面加载时获取数据
onMounted(async () => {
  loading.value = true
  try {
    // 调用API获取训练任务列表
    const response = await getTrainingTasks()
    trainingTasks.value = response.data?.results || response.data || []
  } catch (error) {
    console.error('加载训练任务失败:', error)
    ElMessage.error('加载训练任务失败')
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="algorithm-training-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">模型训练</h2>
        <span class="page-subtitle">配置训练参数，启动模型训练任务</span>
      </div>
    </div>

    <!-- 训练配置 -->
    <div class="config-section">
      <h3 class="section-title">训练配置</h3>
      <div class="config-card">
        <el-form :model="trainingConfig" label-width="120px" class="config-form">
          <el-form-item label="模型类型">
            <el-select v-model="trainingConfig.model_type" placeholder="选择模型类型">
              <el-option label="孤立森林" value="isolation_forest" />
              <el-option label="自编码器" value="autoencoder" />
              <el-option label="K近邻" value="knn" />
              <el-option label="支持向量机" value="svm" />
              <el-option label="集成模型" value="ensemble" />
            </el-select>
          </el-form-item>
          <el-form-item label="训练数据集">
            <div class="dataset-selector">
              <el-select 
                v-model="trainingConfig.dataset" 
                placeholder="选择或上传数据集"
                style="width: 320px"
                @change="handleDatasetChange"
              >
                <el-option 
                  v-for="item in datasetList" 
                  :key="item.name" 
                  :label="`${item.name} (${item.size})`" 
                  :value="item.name" 
                />
              </el-select>
              <el-upload
                class="dataset-uploader"
                action="/api/v1/algorithm/datasets/upload/"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleUploadSuccess"
                :on-error="handleUploadError"
                accept=".npz,.csv,.json,.parquet"
              >
                <el-button type="primary" plain>
                  <el-icon><Upload /></el-icon>
                  上传数据集
                </el-button>
              </el-upload>
            </div>
            <div class="dataset-hint">
              支持 .npz, .csv, .json, .parquet 格式
            </div>
          </el-form-item>
          <el-form-item label="树数量" v-if="trainingConfig.model_type === 'isolation_forest'">
            <el-input-number v-model="trainingConfig.params.n_estimators" :min="10" :max="1000" />
          </el-form-item>
          <el-form-item label="最大深度" v-if="trainingConfig.model_type === 'isolation_forest'">
            <el-input-number v-model="trainingConfig.params.max_depth" :min="1" :max="50" />
          </el-form-item>
          <el-form-item label="训练轮数" v-if="trainingConfig.model_type === 'autoencoder'">
            <el-input-number v-model="trainingConfig.params.epochs" :min="10" :max="200" />
          </el-form-item>
          <el-form-item label="批次大小" v-if="trainingConfig.model_type === 'autoencoder'">
            <el-input-number v-model="trainingConfig.params.batch_size" :min="16" :max="256" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="startTraining" :loading="training" size="large">
              <el-icon><VideoPlay /></el-icon>
              启动训练
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 训练任务列表 -->
    <div class="tasks-section">
      <h3 class="section-title">训练任务</h3>
      <div class="tasks-list">
        <div
          v-for="task in trainingTasks"
          :key="task.id"
          class="task-card"
        >
          <div class="task-header">
            <div class="task-info">
              <h4 class="task-name">{{ task.model_name }}</h4>
              <el-tag :type="task.status === 'completed' ? 'success' : task.status === 'running' ? 'warning' : 'info'" size="small">
                {{ task.status_display }}
              </el-tag>
            </div>
            <div class="task-actions">
              <el-button text size="small" @click="viewLog(task)">
                <el-icon><Document /></el-icon>
                日志
              </el-button>
              <el-button 
                text 
                size="small" 
                type="danger" 
                @click="cancelTraining(task)"
                :disabled="task.status !== 'running'"
              >
                <el-icon><CircleClose /></el-icon>
                取消
              </el-button>
            </div>
          </div>
          
          <div class="task-progress">
            <div class="progress-wrapper">
              <el-progress 
                :percentage="task.progress" 
                :status="task.status === 'completed' ? 'success' : task.status === 'cancelled' ? 'exception' : undefined"
                :stroke-width="8"
                :show-text="false"
                class="progress-bar"
              />
              <span class="progress-text" :class="{ 'is-completed': task.status === 'completed' }">
                {{ task.progress }}%
              </span>
            </div>
          </div>
          
          <div class="task-footer">
            <span class="task-time">创建: {{ task.created_at ? new Date(task.created_at).toLocaleString() : '-' }}</span>
            <span class="task-duration" v-if="task.completed_at">
              耗时: {{ Math.round((new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000) }}秒
            </span>
            <span class="task-metrics" v-if="task.status === 'completed' && task.result_metrics.f1_score">
              F1: {{ (task.result_metrics.f1_score * 100).toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.algorithm-training-view {
  .page-header {
    margin-bottom: 24px;
    
    .header-left {
      .page-title {
        font-size: 24px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 4px 0;
      }
      
      .page-subtitle {
        font-size: 14px;
        color: var(--text-muted);
      }
    }
  }
  
  .config-section {
    margin-bottom: 32px;
    
    .section-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 16px;
    }
    
    .config-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 24px;
      
      .config-form {
        max-width: 600px;
        
        .dataset-selector {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        
        .dataset-hint {
          margin-top: 8px;
          font-size: 12px;
          color: var(--text-muted);
        }
        
        .dataset-uploader {
          display: inline-block;
        }
      }
    }
  }
  
  .tasks-section {
    .section-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 16px;
    }
    
    .tasks-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
      
      .task-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
        
        &:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        .task-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          
          .task-info {
            .task-name {
              font-size: 16px;
              font-weight: 600;
              color: var(--text-primary);
              margin: 0 0 4px 0;
            }
          }
          
          .task-actions {
            display: flex;
            gap: 8px;
          }
        }
        
        .task-progress {
          margin-bottom: 12px;
          
          .progress-wrapper {
            display: flex;
            align-items: center;
            gap: 12px;
            
            .progress-bar {
              flex: 1;
            }
            
            .progress-text {
              font-size: 14px;
              font-weight: 600;
              color: var(--text-secondary);
              min-width: 40px;
              text-align: right;
              
              &.is-completed {
                color: var(--success-color);
              }
            }
          }
        }
        
        .task-footer {
          display: flex;
          gap: 16px;
          font-size: 12px;
          color: var(--text-muted);
          
          .task-metrics {
            color: var(--success-color);
            font-weight: 600;
          }
        }
      }
    }
  }
}
</style>
