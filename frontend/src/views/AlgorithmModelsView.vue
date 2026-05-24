<script setup lang="ts">
/**
 * 算法模型管理页面
 * 功能：查看所有模型、模型详情、下载模型
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  MoreFilled,
  View,
  Download
} from '@element-plus/icons-vue'
import {
  listModelFiles,
  downloadModelFile
} from '@/api/algorithm'

// 算法模型列表（模型文件列表）
const models = ref<any[]>([])

// 加载状态
const loading = ref(false)

// 对话框控制
const showModelDetail = ref(false)
const currentModel = ref<any>(null)

// 查看模型详情
const viewModelDetail = (model: any) => {
  currentModel.value = model
  showModelDetail.value = true
}

// 激活模型（暂时禁用）
const activateModel = async (model: any) => {
  ElMessage.info('模型文件暂不支持激活操作')
}

// 下载模型
const downloadModel = (model: any) => {
  downloadModelFile(model.file_name)
}

// 删除模型（暂时禁用）
const deleteModel = async (model: any) => {
  ElMessage.info('模型文件暂不支持删除操作')
}

// 加载模型数据（从 algorithm/models/ 文件夹读取）
const loadModels = async () => {
  loading.value = true
  try {
    const response = await listModelFiles()
    console.log('API响应:', response)  // 调试信息
    
    // 处理响应数据 - 适配后端返回格式 {code, data, message}
    // response.data 是 Axios 的响应体
    // response.data.data 才是真正的模型列表
    if (response && response.data && response.data.data) {
      // 后端返回格式: {code: 200, data: [...], message: "success"}
      models.value = response.data.data
    } else if (response && Array.isArray(response.data)) {
      // 如果直接返回数组
      models.value = response.data
    } else {
      console.error('未知的响应格式:', response)
      models.value = []
    }
  } catch (error) {
    console.error('加载模型失败:', error)
    ElMessage.error('加载模型列表失败')
    models.value = []
  } finally {
    loading.value = false
  }
}

// 格式化日期
const formatDate = (timestamp: number) => {
  const date = new Date(timestamp * 1000)  // timestamp 是秒，需要转换为毫秒
  const year = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${year}-${month}-${day}`
}

// 获取模型类型显示名称
const getModelTypeName = (modelType: string) => {
  const names: Record<string, string> = {
    'isolation_forest': '孤立森林',
    'autoencoder': '自编码器',
    'knn': 'K近邻',
    'svm': '支持向量机',
    'scaler': '标准化器',
    'unknown': '未知'
  }
  return names[modelType] || modelType
}

// 判断是否有标准性能指标（用于控制性能指标区域显示）
const hasStandardMetrics = (performance: any) => {
  if (!performance) return false
  const standardKeys = ['accuracy', 'precision', 'recall', 'f1_score', 'auc', 'reconstruction_error']
  return standardKeys.some(key => performance[key] !== undefined)
}

// 页面加载时获取数据
onMounted(() => {
  loadModels()
})
</script>

<template>
  <div class="algorithm-models-view">
    <!-- 模型列表 -->
    <div class="models-grid">
      <div
        v-for="model in models"
        :key="model.file_name"
        class="model-card"
      >
        <!-- 卡片头部 -->
        <div class="card-header">
          <div class="model-info">
            <h3 class="model-name">{{ getModelTypeName(model.model_type) }}</h3>
            <span class="model-file">{{ model.file_name }}</span>
          </div>
          <el-dropdown trigger="click">
            <el-button text :icon="MoreFilled" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="viewModelDetail(model)">
                  <el-icon><View /></el-icon>
                  查看详情
                </el-dropdown-item>
                <el-dropdown-item @click="downloadModel(model)">
                  <el-icon><Download /></el-icon>
                  下载模型
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <!-- 卡片内容 -->
        <div class="card-body">
          <!-- 模型信息 -->
          <div class="model-info-grid">
            <div class="info-item">
              <span class="info-label">文件大小</span>
              <span class="info-value">{{ model.size }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">修改时间</span>
              <span class="info-value">{{ formatDate(model.modified_at) }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">模型类型</span>
              <span class="info-value">{{ getModelTypeName(model.model_type) }}</span>
            </div>
          </div>
          
          <!-- 性能指标 -->
          <div v-if="hasStandardMetrics(model.performance)" class="performance-section">
            <div class="section-title">性能指标</div>
            <div class="performance-list">
              <div v-if="model.performance.accuracy !== undefined" class="perf-row">
                <span class="perf-name">准确率</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.round(model.performance.accuracy * 100)" 
                    :stroke-width="10"
                    :show-text="false"
                    status="success"
                  />
                </div>
                <span class="perf-value">{{ (model.performance.accuracy * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="model.performance.precision !== undefined" class="perf-row">
                <span class="perf-name">精确率</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.round(model.performance.precision * 100)" 
                    :stroke-width="10"
                    :show-text="false"
                  />
                </div>
                <span class="perf-value">{{ (model.performance.precision * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="model.performance.recall !== undefined" class="perf-row">
                <span class="perf-name">召回率</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.round(model.performance.recall * 100)" 
                    :stroke-width="10"
                    :show-text="false"
                  />
                </div>
                <span class="perf-value">{{ (model.performance.recall * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="model.performance.f1_score !== undefined" class="perf-row">
                <span class="perf-name">F1分数</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.round(model.performance.f1_score * 100)" 
                    :stroke-width="10"
                    :show-text="false"
                  />
                </div>
                <span class="perf-value">{{ (model.performance.f1_score * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="model.performance.auc !== undefined" class="perf-row">
                <span class="perf-name">AUC</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.round(model.performance.auc * 100)" 
                    :stroke-width="10"
                    :show-text="false"
                  />
                </div>
                <span class="perf-value">{{ (model.performance.auc * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="model.performance.reconstruction_error !== undefined" class="perf-row">
                <span class="perf-name">重构误差</span>
                <div class="perf-bar-wrap">
                  <el-progress 
                    :percentage="Math.min(Math.round(model.performance.reconstruction_error * 1000), 100)" 
                    :stroke-width="10"
                    :show-text="false"
                    status="warning"
                  />
                </div>
                <span class="perf-value">{{ model.performance.reconstruction_error.toFixed(4) }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>

    <!-- 模型详情对话框 -->
    <el-dialog
      v-model="showModelDetail"
      title="模型详情"
      width="800px"
    >
      <div v-if="currentModel" class="model-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名">{{ currentModel.file_name }}</el-descriptions-item>
          <el-descriptions-item label="模型类型">{{ getModelTypeName(currentModel.model_type) }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ currentModel.size }}</el-descriptions-item>
          <el-descriptions-item label="修改时间">{{ formatDate(currentModel.modified_at) }}</el-descriptions-item>
          <el-descriptions-item label="文件大小(字节)">{{ currentModel.size_bytes }}</el-descriptions-item>
          <el-descriptions-item label="创建时间" v-if="currentModel.created_at">{{ currentModel.created_at }}</el-descriptions-item>
        </el-descriptions>
        
        <!-- 描述信息 -->
        <div v-if="currentModel.description" class="detail-section">
          <h4>模型描述</h4>
          <p>{{ currentModel.description }}</p>
        </div>
        
        <!-- 性能指标 -->
        <div v-if="currentModel.performance" class="detail-section">
          <h4>性能指标</h4>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="准确率" v-if="currentModel.performance.accuracy !== undefined">
              {{ (currentModel.performance.accuracy * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="精确率" v-if="currentModel.performance.precision !== undefined">
              {{ (currentModel.performance.precision * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="召回率" v-if="currentModel.performance.recall !== undefined">
              {{ (currentModel.performance.recall * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="F1分数" v-if="currentModel.performance.f1_score !== undefined">
              {{ (currentModel.performance.f1_score * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="AUC" v-if="currentModel.performance.auc !== undefined">
              {{ (currentModel.performance.auc * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item label="重构误差" v-if="currentModel.performance.reconstruction_error !== undefined">
              {{ currentModel.performance.reconstruction_error.toFixed(4) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <!-- 训练信息 -->
        <div v-if="currentModel.training_info" class="detail-section">
          <h4>训练信息</h4>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="数据集" v-if="currentModel.training_info.dataset">
              {{ currentModel.training_info.dataset }}
            </el-descriptions-item>
            <el-descriptions-item label="训练比例" v-if="currentModel.training_info.train_ratio !== undefined">
              {{ (currentModel.training_info.train_ratio * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="污染率" v-if="currentModel.training_info.contamination !== undefined">
              {{ (currentModel.training_info.contamination * 100).toFixed(0) }}%
            </el-descriptions-item>
            <el-descriptions-item label="编码器维度" v-if="currentModel.training_info.encoding_dim !== undefined">
              {{ currentModel.training_info.encoding_dim }}
            </el-descriptions-item>
            <el-descriptions-item label="训练轮数" v-if="currentModel.training_info.epochs !== undefined">
              {{ currentModel.training_info.epochs }}
            </el-descriptions-item>
            <el-descriptions-item label="批次大小" v-if="currentModel.training_info.batch_size !== undefined">
              {{ currentModel.training_info.batch_size }}
            </el-descriptions-item>
            <el-descriptions-item label="估计器数量" v-if="currentModel.training_info.n_estimators !== undefined">
              {{ currentModel.training_info.n_estimators }}
            </el-descriptions-item>
            <el-descriptions-item label="采样方式" v-if="currentModel.training_info.max_samples !== undefined">
              {{ currentModel.training_info.max_samples }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.algorithm-models-view {
  .models-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 20px;
  }
  
  .model-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.3s ease;
    
    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
      transform: translateY(-2px);
    }
    
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border-color);
      
      .model-info {
        .model-name {
          font-size: 16px;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 2px 0;
        }
        
        .model-file {
          font-size: 12px;
          color: var(--text-muted);
          font-family: 'Courier New', monospace;
        }
      }
    }
    
    .card-body {
      padding: 20px;
      
      .model-info-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 16px;
        
        .info-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          
          .info-label {
            font-size: 12px;
            color: var(--text-muted);
          }
          
          .info-value {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
          }
        }
      }
      
      .performance-section {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px dashed var(--border-color);
        
        .section-title {
          font-size: 13px;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 10px;
        }
        
        .performance-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          
          .perf-row {
            display: flex;
            align-items: center;
            gap: 8px;
            
            .perf-name {
              font-size: 12px;
              color: var(--text-muted);
              width: 48px;
              flex-shrink: 0;
              text-align: right;
            }
            
            .perf-bar-wrap {
              flex: 1;
              min-width: 0;
            }
            
            .perf-value {
              font-size: 12px;
              font-weight: 600;
              color: var(--text-primary);
              width: 48px;
              flex-shrink: 0;
              text-align: left;
            }
          }
        }
      }
    }
    
  }
  
  .model-detail {
    max-height: 600px;
    overflow-y: auto;
    
    .detail-section {
      margin-top: 20px;
      
      h4 {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--border-color);
      }
      
      p {
        font-size: 14px;
        color: var(--text-secondary);
        line-height: 1.6;
        margin: 0;
      }
    }
  }
}
</style>
