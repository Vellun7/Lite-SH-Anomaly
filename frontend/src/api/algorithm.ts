/**
 * 算法模型管理 API
 * 提供算法模型、训练任务、评估结果、特征重要性相关的 API 调用
 */
import request from '@/utils/request'

// 算法模型相关 API
export const getAlgorithmModels = (params?: any) => {
  return request.get('/algorithm/models/', { params })
}

export const getAlgorithmModelDetail = (id: string) => {
  return request.get(`/algorithm/models/${id}/`)
}

export const createAlgorithmModel = (data: any) => {
  return request.post('/algorithm/models/', data)
}

export const updateAlgorithmModel = (id: string, data: any) => {
  return request.put(`/algorithm/models/${id}/`, data)
}

export const deleteAlgorithmModel = (id: string) => {
  return request.delete(`/algorithm/models/${id}/`)
}

export const activateAlgorithmModel = (id: string) => {
  return request.post(`/algorithm/models/${id}/activate/`)
}

export const getActiveAlgorithmModel = () => {
  return request.get('/algorithm/models/active/')
}

// 模型文件相关 API
export const listModelFiles = () => {
  return request.get('/algorithm/model-files/')
}

export const downloadModelFile = (fileName: string) => {
  // 使用 window.open 直接触发文件下载（绕过 axios 拦截器）
  const url = `/api/v1/algorithm/model-files/${encodeURIComponent(fileName)}/download/`
  window.open(url, '_self')
}

// 训练任务相关 API
export const getTrainingTasks = (params?: any) => {
  return request.get('/algorithm/training/', { params })
}

export const createTrainingTask = (data: any) => {
  return request.post('/algorithm/training/', data)
}

export const getTrainingTaskDetail = (id: string) => {
  return request.get(`/algorithm/training/${id}/`)
}

export const startTrainingTask = (id: string) => {
  return request.post(`/algorithm/training/${id}/start/`)
}

export const cancelTrainingTask = (id: string) => {
  return request.post(`/algorithm/training/${id}/cancel/`)
}

// 评估结果相关 API
export const getEvaluationResults = (params?: any) => {
  return request.get('/algorithm/evaluation/', { params })
}

export const getEvaluationResultDetail = (id: string) => {
  return request.get(`/algorithm/evaluation/${id}/`)
}

export const compareModels = (modelIds: string[]) => {
  return request.post('/algorithm/evaluation/compare/', { model_ids: modelIds })
}

// 特征重要性相关 API
export const getFeatureImportances = (params?: any) => {
  return request.get('/algorithm/features/', { params })
}

export const getFeatureImportanceDetail = (id: string) => {
  return request.get(`/algorithm/features/${id}/`)
}
