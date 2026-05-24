<script setup lang="ts">
/**
 * 特征工程页面
 * 功能：特征列表、特征重要性、特征选择
 */
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

// 特征重要性列表
const featureImportances = ref([
  { id: 1, feature_name: 'duration', importance_score: 0.95, rank: 1 },
  { id: 2, feature_name: 'orig_bytes', importance_score: 0.89, rank: 2 },
  { id: 3, feature_name: 'resp_bytes', importance_score: 0.87, rank: 3 },
  { id: 4, feature_name: 'orig_pkts', importance_score: 0.82, rank: 4 },
  { id: 5, feature_name: 'resp_pkts', importance_score: 0.78, rank: 5 },
  { id: 6, feature_name: 'proto_encoded', importance_score: 0.75, rank: 6 },
  { id: 7, feature_name: 'bytes_ratio', importance_score: 0.72, rank: 7 },
  { id: 8, feature_name: 'pkts_ratio', importance_score: 0.68, rank: 8 },
  { id: 9, feature_name: 'service_encoded', importance_score: 0.65, rank: 9 },
  { id: 10, feature_name: 'conn_state_encoded', importance_score: 0.62, rank: 10 }
])

// 特征选择配置
const featureSelectionConfig = ref({
  method: 'mutual_info',
  k: 20
})

// 加载状态
const loading = ref(false)

// 执行特征选择
const runFeatureSelection = async () => {
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1500))
    ElMessage.success('特征选择完成')
  } catch (error) {
    ElMessage.error('特征选择失败')
  }
}

// 查看特征详情
const viewFeatureDetail = (feature: any) => {
  ElMessage.info(`查看特征详情: ${feature.feature_name}`)
  // TODO: 打开详情对话框
}

// 导出特征列表
const exportFeatures = () => {
  ElMessage.info('导出特征列表')
  // TODO: 导出CSV
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
  <div class="algorithm-features-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">特征工程</h2>
        <span class="page-subtitle">查看特征重要性，执行特征选择</span>
      </div>
      <div class="header-right">
        <el-button @click="exportFeatures">
          <el-icon><Download /></el-icon>
          导出特征
        </el-button>
        <el-button type="primary" @click="runFeatureSelection">
          <el-icon><VideoPlay /></el-icon>
          执行特征选择
        </el-button>
      </div>
    </div>

    <!-- 特征选择配置 -->
    <div class="config-section">
      <h3 class="section-title">特征选择配置</h3>
      <div class="config-card">
        <el-form :model="featureSelectionConfig" label-width="120px" class="config-form">
          <el-form-item label="选择方法">
            <el-select v-model="featureSelectionConfig.method" placeholder="选择方法">
              <el-option label="互信息 (Mutual Info)" value="mutual_info" />
              <el-option label="F分数 (F-Score)" value="f_score" />
              <el-option label="相关系数 (Correlation)" value="correlation" />
            </el-select>
          </el-form-item>
          <el-form-item label="选择特征数">
            <el-input-number v-model="featureSelectionConfig.k" :min="5" :max="50" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="runFeatureSelection">
              <el-icon><VideoPlay /></el-icon>
              开始选择
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>

    <!-- 特征重要性列表 -->
    <div class="features-section">
      <h3 class="section-title">特征重要性排名</h3>
      <div class="features-table">
        <el-table :data="featureImportances" border style="width: 100%">
          <el-table-column prop="rank" label="排名" width="80" sortable />
          <el-table-column prop="feature_name" label="特征名称" min-width="150" />
          <el-table-column prop="importance_score" label="重要性分数" min-width="150" sortable>
            <template #default="{ row }">
              <div class="importance-bar">
                <div 
                  class="bar-fill" 
                  :style="{ width: `${row.importance_score * 100}%` }"
                />
                <span class="bar-value">{{ row.importance_score.toFixed(4) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" @click="viewFeatureDetail(row)">
                <el-icon><View /></el-icon>
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.algorithm-features-view {
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
      }
    }
  }
  
  .features-section {
    .section-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 16px;
    }
    
    .features-table {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 16px;
      
      .importance-bar {
        position: relative;
        height: 24px;
        background: var(--bg-base);
        border-radius: 4px;
        overflow: hidden;
        
        .bar-fill {
          height: 100%;
          background: var(--primary-gradient);
          border-radius: 4px;
          transition: width 0.3s ease;
        }
        
        .bar-value {
          position: absolute;
          right: 8px;
          top: 50%;
          transform: translateY(-50%);
          font-size: 12px;
          font-weight: 600;
          color: var(--text-primary);
        }
      }
    }
  }
}
</style>
