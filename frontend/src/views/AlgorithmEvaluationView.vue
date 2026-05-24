<script setup lang="ts">
/**
 * 模型评估页面
 * 功能：评估结果、模型对比
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 评估结果列表
const evaluationResults = ref([
  {
    id: 1,
    model_name: '轻量化孤立森林',
    task_id: 'task_001',
    metrics: {
      accuracy: 0.92,
      precision: 0.91,
      recall: 0.87,
      f1_score: 0.89,
      auc_roc: 0.94,
      false_positive_rate: 0.03,
      false_negative_rate: 0.02
    },
    evaluation_dataset: 'test_data.npz',
    evaluation_samples: 2000,
    created_at: '2024-01-15T11:00:00'
  },
  {
    id: 2,
    model_name: '轻量化自编码器',
    task_id: 'task_002',
    metrics: {
      accuracy: 0.90,
      precision: 0.88,
      recall: 0.82,
      f1_score: 0.85,
      auc_roc: 0.91,
      false_positive_rate: 0.04,
      false_negative_rate: 0.03
    },
    evaluation_dataset: 'test_data.npz',
    evaluation_samples: 2000,
    created_at: '2024-01-16T11:30:00'
  }
])

// 模型对比数据
const comparisonData = ref([
  { 模型: '轻量化孤立森林', F1分数: 0.89, 精确率: 0.91, 召回率: 0.87, 'AUC-ROC': 0.94, 误报率: 0.03, 漏报率: 0.02 },
  { 模型: '轻量化自编码器', F1分数: 0.85, 精确率: 0.88, 召回率: 0.82, 'AUC-ROC': 0.91, 误报率: 0.04, 漏报率: 0.03 },
  { 模型: 'K近邻基线模型', F1分数: 0.78, 精确率: 0.80, 召回率: 0.76, 'AUC-ROC': 0.87, 误报率: 0.05, 漏报率: 0.04 }
])

// 加载状态
const loading = ref(false)

// 查看评估详情
const viewEvaluationDetail = (result: any) => {
  ElMessage.info(`查看评估详情: ${result.model_name}`)
  // TODO: 打开详情对话框
}

// 对比模型
const compareModels = () => {
  ElMessage.info('开始模型对比')
  // TODO: 打开对比对话框
}

// 导出评估报告
const exportReport = () => {
  ElMessage.info('导出评估报告')
  // TODO: 导出HTML报告
}

// 页面加载时获取数据
onMounted(() => {
  loading.value = true
  // 模拟API调用
  setTimeout(() => {
    loading.value = false
  }, 500)
})
</script>

<template>
  <div class="algorithm-evaluation-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">模型评估</h2>
        <span class="page-subtitle">查看评估结果，对比模型性能</span>
      </div>
      <div class="header-right">
        <el-button @click="compareModels">
          <el-icon><DataAnalysis /></el-icon>
          模型对比
        </el-button>
        <el-button type="primary" @click="exportReport">
          <el-icon><Download /></el-icon>
          导出报告
        </el-button>
      </div>
    </div>

    <!-- 模型对比表格 -->
    <div class="comparison-section">
      <h3 class="section-title">模型对比</h3>
      <div class="comparison-table">
        <el-table :data="comparisonData" border style="width: 100%">
          <el-table-column prop="模型" label="模型" min-width="150" />
          <el-table-column prop="F1分数" label="F1分数" min-width="100">
            <template #default="{ row }">
              <span :class="{ 'is-good': row['F1分数'] >= 0.85 }">
                {{ (row['F1分数'] * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="精确率" label="精确率" min-width="100">
            <template #default="{ row }">
              {{ (row['精确率'] * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="召回率" label="召回率" min-width="100">
            <template #default="{ row }">
              {{ (row['召回率'] * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="AUC-ROC" label="AUC-ROC" min-width="100">
            <template #default="{ row }">
              {{ (row['AUC-ROC'] * 100).toFixed(1) }}%
            </template>
          </el-table-column>
          <el-table-column prop="误报率" label="误报率" min-width="100">
            <template #default="{ row }">
              <span :class="{ 'is-bad': row['误报率'] > 0.05 }">
                {{ (row['误报率'] * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="漏报率" label="漏报率" min-width="100">
            <template #default="{ row }">
              <span :class="{ 'is-bad': row['漏报率'] > 0.03 }">
                {{ (row['漏报率'] * 100).toFixed(1) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 评估结果列表 -->
    <div class="results-section">
      <h3 class="section-title">评估结果列表</h3>
      <div class="results-list">
        <div
          v-for="result in evaluationResults"
          :key="result.id"
          class="result-card"
        >
          <div class="result-header">
            <div class="result-info">
              <h4 class="result-model-name">{{ result.model_name }}</h4>
              <el-tag size="small" type="info">{{ result.evaluation_dataset }}</el-tag>
            </div>
            <div class="result-actions">
              <el-button text size="small" @click="viewEvaluationDetail(result)">
                <el-icon><View /></el-icon>
                详情
              </el-button>
            </div>
          </div>
          
          <div class="result-metrics">
            <div class="metric-item">
              <span class="metric-label">F1分数</span>
              <span class="metric-value">{{ (result.metrics.f1_score * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">精确率</span>
              <span class="metric-value">{{ (result.metrics.precision * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">召回率</span>
              <span class="metric-value">{{ (result.metrics.recall * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">AUC-ROC</span>
              <span class="metric-value">{{ (result.metrics.auc_roc * 100).toFixed(1) }}%</span>
            </div>
          </div>
          
          <div class="result-footer">
            <span class="result-samples">样本数: {{ result.evaluation_samples }}</span>
            <span class="result-time">{{ new Date(result.created_at).toLocaleString() }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.algorithm-evaluation-view {
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
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
  
  .comparison-section {
    margin-bottom: 32px;
    
    .section-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 16px;
    }
    
    .comparison-table {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      
      .is-good {
        color: var(--success-color);
        font-weight: 600;
      }
      
      .is-bad {
        color: var(--danger-color);
        font-weight: 600;
      }
    }
  }
  
  .results-section {
    .section-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 16px;
    }
    
    .results-list {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
      
      .result-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        transition: all 0.3s ease;
        
        &:hover {
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
          transform: translateY(-2px);
        }
        
        .result-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
          
          .result-info {
            .result-model-name {
              font-size: 16px;
              font-weight: 600;
              color: var(--text-primary);
              margin: 0 0 4px 0;
            }
          }
        }
        
        .result-metrics {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 16px;
          
          .metric-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            
            .metric-label {
              font-size: 12px;
              color: var(--text-muted);
            }
            
            .metric-value {
              font-size: 14px;
              font-weight: 600;
              color: var(--text-primary);
            }
          }
        }
        
        .result-footer {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: var(--text-muted);
        }
      }
    }
  }
}
</style>
