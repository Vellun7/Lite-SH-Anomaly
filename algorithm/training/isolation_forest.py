"""
轻量化孤立森林模型
核心参数：决策树数量=50、树深度≤8、采样量=256
目标：推理延迟≤100ms、内存占用≤30MB、F1≥0.85

优化内容：
1. 修复 max_depth 参数传递问题
2. 添加异常分数校准（Platt Scaling, Isotonic Regression）
3. 增加特征重要性计算
4. 支持自适应contamination
5. 添加置信区间估计
"""

import numpy as np
import joblib
import time
import psutil
import os
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (
    classification_report, confusion_matrix, f1_score,
    precision_score, recall_score, accuracy_score, roc_auc_score
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from typing import Optional, Dict, Tuple, List, Union
import logging
import warnings

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LightweightIsolationForest:
    """轻量化孤立森林异常检测模型（优化版）"""
    
    # 支持的校准方法
    CALIBRATION_METHODS = ['sigmoid', 'isotonic', 'temperature', 'none']
    
    def __init__(self, 
                 n_estimators: int = 50,
                 max_depth: int = 8,
                 max_samples: int = 256,
                 contamination: float = 0.2,
                 random_state: int = 42,
                 # 新增参数
                 max_features: float = 1.0,
                 bootstrap: bool = False,
                 score_scale: float = 5.0,
                 calibration_method: str = 'temperature',
                 n_jobs: int = 1):
        """
        初始化轻量化孤立森林
        
        Args:
            n_estimators: 决策树数量（默认50，轻量化）
            max_depth: 最大树深度（默认8，限制复杂度）
                      注：sklearn IsolationForest 不直接支持 max_depth，
                      通过 max_samples 间接控制（log2(max_samples) ≈ 树深度）
            max_samples: 采样数量（默认256，对应约8层深度）
            contamination: 异常比例（默认0.2，即20%异常样本）
            random_state: 随机种子
            max_features: 每棵树使用的特征比例
            bootstrap: 是否使用bootstrap采样
            score_scale: 异常分数缩放因子（用于sigmoid转换）
            calibration_method: 分数校准方法 ('sigmoid', 'isotonic', 'temperature', 'none')
            n_jobs: 并行数（边缘设备建议1）
        """
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.max_samples = max_samples
        self.contamination = contamination
        self.random_state = random_state
        self.max_features = max_features
        self.bootstrap = bootstrap
        self.score_scale = score_scale
        self.calibration_method = calibration_method
        self.n_jobs = n_jobs
        
        # 根据 max_depth 调整 max_samples（如果用户指定了 max_depth）
        # IsolationForest 的树深度约等于 ceil(log2(max_samples))
        if max_depth is not None and max_depth > 0:
            recommended_samples = min(2 ** max_depth, max_samples)
            if recommended_samples != max_samples:
                logger.info(f"根据 max_depth={max_depth}，调整 max_samples: {max_samples} -> {recommended_samples}")
                self.max_samples = recommended_samples
        
        self.model = IsolationForest(
            n_estimators=n_estimators,
            max_samples=self.max_samples,
            contamination=contamination,
            max_features=max_features,
            bootstrap=bootstrap,
            random_state=random_state,
            n_jobs=n_jobs,
            warm_start=False
        )
        
        self.is_trained = False
        self.training_time = 0
        self.feature_names = None
        self.calibrator = None  # 分数校准器
        self.temperature = 1.0  # 温度参数
        self._score_stats = None  # 分数统计信息
        self._feature_importance = None  # 特征重要性
        
    def train(self, X_train: np.ndarray, y_train: np.ndarray = None, 
              feature_names: list = None, calibrate: bool = True):
        """
        训练模型
        
        Args:
            X_train: 训练数据
            y_train: 标签（可选，用于校准）
            feature_names: 特征名称列表
            calibrate: 是否校准分数
        """
        logger.info(f"开始训练孤立森林模型...")
        logger.info(f"参数: n_estimators={self.n_estimators}, max_samples={self.max_samples}, contamination={self.contamination}")
        
        self.feature_names = feature_names
        
        start_time = time.time()
        self.model.fit(X_train)
        self.training_time = time.time() - start_time
        
        # 计算分数统计信息
        self._compute_score_statistics(X_train)
        
        # 计算特征重要性
        self._compute_feature_importance(X_train)
        
        # 校准分数（如果提供了标签）
        if calibrate and y_train is not None and self.calibration_method != 'none':
            self._calibrate_scores(X_train, y_train)
        
        self.is_trained = True
        logger.info(f"训练完成，耗时: {self.training_time:.3f}s")
        
    def _compute_score_statistics(self, X: np.ndarray):
        """计算异常分数的统计信息（用于归一化和校准）"""
        raw_scores = self.model.decision_function(X)
        
        self._score_stats = {
            'mean': np.mean(raw_scores),
            'std': np.std(raw_scores),
            'min': np.min(raw_scores),
            'max': np.max(raw_scores),
            'median': np.median(raw_scores),
            'q1': np.percentile(raw_scores, 25),
            'q3': np.percentile(raw_scores, 75)
        }
        
        logger.info(f"异常分数统计: mean={self._score_stats['mean']:.4f}, std={self._score_stats['std']:.4f}")
        
    def _compute_feature_importance(self, X: np.ndarray, n_samples: int = 1000):
        """
        计算特征重要性（基于扰动分析）
        
        孤立森林本身不提供特征重要性，通过扰动分析估算
        """
        if X.shape[0] > n_samples:
            indices = np.random.choice(X.shape[0], n_samples, replace=False)
            X_sample = X[indices]
        else:
            X_sample = X
        
        # 基准分数
        base_scores = self.model.decision_function(X_sample)
        
        importance = np.zeros(X.shape[1])
        
        for i in range(X.shape[1]):
            X_perturbed = X_sample.copy()
            # 打乱第i个特征
            np.random.shuffle(X_perturbed[:, i])
            
            perturbed_scores = self.model.decision_function(X_perturbed)
            
            # 重要性 = 扰动后分数变化的平均值
            importance[i] = np.mean(np.abs(base_scores - perturbed_scores))
        
        # 归一化
        if np.sum(importance) > 0:
            importance = importance / np.sum(importance)
        
        self._feature_importance = importance
        
        if self.feature_names is not None:
            top_features = sorted(
                zip(self.feature_names, importance), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            logger.info(f"Top 5 重要特征: {top_features}")
    
    def _calibrate_scores(self, X: np.ndarray, y: np.ndarray):
        """
        校准异常分数
        
        Args:
            X: 训练数据
            y: 标签（0=正常，>0=异常）
        """
        y_binary = np.where(y > 0, 1, 0)
        raw_scores = -self.model.decision_function(X)  # 取负值使得越大越异常
        
        if self.calibration_method == 'sigmoid':
            # Platt Scaling (Sigmoid校准)
            self.calibrator = LogisticRegression(random_state=self.random_state)
            self.calibrator.fit(raw_scores.reshape(-1, 1), y_binary)
            logger.info("使用 Sigmoid (Platt Scaling) 校准")
            
        elif self.calibration_method == 'isotonic':
            # Isotonic Regression 校准
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(raw_scores, y_binary)
            logger.info("使用 Isotonic Regression 校准")
            
        elif self.calibration_method == 'temperature':
            # 温度缩放（简单有效）
            # 通过交叉熵优化温度参数
            self.temperature = self._optimize_temperature(raw_scores, y_binary)
            logger.info(f"使用 Temperature Scaling，温度参数: {self.temperature:.4f}")
    
    def _optimize_temperature(self, scores: np.ndarray, y: np.ndarray, 
                              lr: float = 0.01, max_iter: int = 100) -> float:
        """
        优化温度参数（最小化交叉熵损失）
        """
        temperature = 1.0
        
        for _ in range(max_iter):
            # 计算概率
            proba = 1 / (1 + np.exp(-scores * self.score_scale / temperature))
            
            # 计算梯度（简化版）
            eps = 1e-7
            proba = np.clip(proba, eps, 1 - eps)
            
            # 交叉熵损失的梯度
            gradient = np.mean(
                (proba - y) * scores * self.score_scale / (temperature ** 2)
            )
            
            # 更新温度
            temperature -= lr * gradient
            temperature = max(0.1, min(10.0, temperature))  # 限制范围
        
        return temperature
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测异常
        
        Args:
            X: 待预测数据
            
        Returns:
            预测结果（0=正常，1=异常）
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        # IsolationForest返回1=正常，-1=异常，需要转换
        predictions = self.model.predict(X)
        # 转换为0=正常，1=异常
        return np.where(predictions == -1, 1, 0)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        预测异常概率（经过校准）
        
        Args:
            X: 待预测数据
            
        Returns:
            异常概率（0-1，越高越可能是异常）
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
        
        # 获取原始异常分数（取负值，越大越异常）
        raw_scores = -self.model.decision_function(X)
        
        if self.calibrator is not None:
            if self.calibration_method == 'sigmoid':
                proba = self.calibrator.predict_proba(raw_scores.reshape(-1, 1))[:, 1]
            elif self.calibration_method == 'isotonic':
                proba = self.calibrator.predict(raw_scores)
            else:
                proba = self._sigmoid_transform(raw_scores)
        else:
            proba = self._sigmoid_transform(raw_scores)
        
        return np.clip(proba, 0, 1)
    
    def _sigmoid_transform(self, scores: np.ndarray) -> np.ndarray:
        """使用温度参数的sigmoid转换"""
        return 1 / (1 + np.exp(-scores * self.score_scale / self.temperature))
    
    def predict_with_confidence(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        预测并返回置信度和异常分数
        
        Returns:
            (predictions, probabilities, raw_scores)
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
        
        predictions = self.predict(X)
        probabilities = self.predict_proba(X)
        raw_scores = -self.model.decision_function(X)
        
        return predictions, probabilities, raw_scores
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性
        
        Returns:
            特征重要性字典
        """
        if self._feature_importance is None:
            raise ValueError("特征重要性尚未计算，请先训练模型")
        
        if self.feature_names is not None:
            return dict(zip(self.feature_names, self._feature_importance))
        else:
            return {f"feature_{i}": v for i, v in enumerate(self._feature_importance)}
    
    def get_anomaly_scores(self, X: np.ndarray, normalize: bool = True) -> np.ndarray:
        """
        获取原始异常分数
        
        Args:
            X: 数据
            normalize: 是否归一化到0-1范围
            
        Returns:
            异常分数（越高越异常）
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
        
        scores = -self.model.decision_function(X)
        
        if normalize and self._score_stats is not None:
            # 使用 z-score 归一化后 sigmoid
            z_scores = (scores - self._score_stats['mean']) / self._score_stats['std']
            scores = 1 / (1 + np.exp(-z_scores))
        
        return scores
    
    def set_contamination(self, contamination: float):
        """
        动态调整contamination参数（需重新训练）
        
        Args:
            contamination: 新的异常比例
        """
        if contamination <= 0 or contamination >= 0.5:
            raise ValueError("contamination 应在 (0, 0.5) 范围内")
        
        self.contamination = contamination
        self.model.set_params(contamination=contamination)
        self.is_trained = False
        logger.info(f"contamination 已更新为 {contamination}，需重新训练")
    
    def auto_tune_contamination(self, X_val: np.ndarray, y_val: np.ndarray, 
                                 search_range: Tuple[float, float] = (0.05, 0.4),
                                 n_steps: int = 10) -> float:
        """
        自动调优contamination参数
        
        Args:
            X_val: 验证数据
            y_val: 验证标签
            search_range: 搜索范围
            n_steps: 搜索步数
            
        Returns:
            最优contamination
        """
        y_binary = np.where(y_val > 0, 1, 0)
        
        best_f1 = 0
        best_contamination = self.contamination
        
        contaminations = np.linspace(search_range[0], search_range[1], n_steps)
        
        for cont in contaminations:
            # 临时设置contamination
            self.model.set_params(contamination=cont)
            self.model.fit(X_val)  # 重新训练
            
            y_pred = self.predict(X_val)
            f1 = f1_score(y_binary, y_pred, zero_division=0)
            
            if f1 > best_f1:
                best_f1 = f1
                best_contamination = cont
        
        # 恢复最优设置
        self.contamination = best_contamination
        self.model.set_params(contamination=best_contamination)
        
        logger.info(f"自动调优完成，最优 contamination={best_contamination:.4f}, F1={best_f1:.4f}")
        
        return best_contamination
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> dict:
        """
        评估模型性能
        
        Args:
            X_test: 测试数据
            y_test: 真实标签（0=正常，非0=异常）
            
        Returns:
            评估指标字典
        """
        y_binary = np.where(y_test > 0, 1, 0)
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_binary, y_pred),
            'precision': precision_score(y_binary, y_pred, zero_division=0),
            'recall': recall_score(y_binary, y_pred, zero_division=0),
            'f1_score': f1_score(y_binary, y_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_binary, y_pred).tolist()
        }
        
        # 计算AUC-ROC
        try:
            metrics['auc_roc'] = roc_auc_score(y_binary, y_proba)
        except ValueError:
            metrics['auc_roc'] = 0.5
        
        # 计算误报率和漏报率
        tn, fp, fn, tp = confusion_matrix(y_binary, y_pred).ravel()
        metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
        metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0
        metrics['true_positive_rate'] = tp / (tp + fn) if (tp + fn) > 0 else 0
        metrics['true_negative_rate'] = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        logger.info(f"评估结果:")
        logger.info(f"  准确率: {metrics['accuracy']:.4f}")
        logger.info(f"  精确率: {metrics['precision']:.4f}")
        logger.info(f"  召回率: {metrics['recall']:.4f}")
        logger.info(f"  F1分数: {metrics['f1_score']:.4f}")
        logger.info(f"  AUC-ROC: {metrics['auc_roc']:.4f}")
        logger.info(f"  误报率: {metrics['false_positive_rate']:.4f}")
        logger.info(f"  漏报率: {metrics['false_negative_rate']:.4f}")
        
        return metrics
    
    def benchmark_inference(self, X_sample: np.ndarray, n_iterations: int = 100) -> dict:
        """
        推理性能基准测试
        
        Args:
            X_sample: 测试样本
            n_iterations: 迭代次数
            
        Returns:
            性能指标
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
        
        single_sample = X_sample[0:1]
        batch_sample = X_sample[:min(32, len(X_sample))]
        times = []
        
        # 预热
        for _ in range(10):
            self.predict(single_sample)
        
        # 单样本测试
        for _ in range(n_iterations):
            start = time.time()
            self.predict(single_sample)
            times.append((time.time() - start) * 1000)
        
        # 批量测试
        batch_times = []
        for _ in range(n_iterations // 10):
            start = time.time()
            self.predict(batch_sample)
            batch_times.append((time.time() - start) * 1000)
            
        # 内存占用
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # 估算模型大小
        model_size_mb = self._estimate_model_size()
        
        benchmark = {
            'avg_inference_time_ms': np.mean(times),
            'max_inference_time_ms': np.max(times),
            'min_inference_time_ms': np.min(times),
            'std_inference_time_ms': np.std(times),
            'p95_inference_time_ms': np.percentile(times, 95),
            'p99_inference_time_ms': np.percentile(times, 99),
            'avg_batch_inference_time_ms': np.mean(batch_times),
            'memory_usage_mb': memory_mb,
            'model_size_mb': model_size_mb,
            'throughput_samples_per_sec': 1000 / np.mean(batch_times) * len(batch_sample) if batch_times else 0
        }
        
        logger.info(f"推理性能基准测试:")
        logger.info(f"  平均推理时间: {benchmark['avg_inference_time_ms']:.3f}ms")
        logger.info(f"  P95推理时间: {benchmark['p95_inference_time_ms']:.3f}ms")
        logger.info(f"  批量推理时间: {benchmark['avg_batch_inference_time_ms']:.3f}ms")
        logger.info(f"  内存占用: {benchmark['memory_usage_mb']:.2f}MB")
        logger.info(f"  模型大小: {benchmark['model_size_mb']:.2f}MB")
        
        return benchmark
    
    def _estimate_model_size(self) -> float:
        """估算模型大小（MB）"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            joblib.dump(self.model, tmp.name, compress=3)
            return os.path.getsize(tmp.name) / 1024 / 1024
    
    def save_model(self, filepath: str):
        """保存模型"""
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        model_data = {
            'model': self.model,
            'params': {
                'n_estimators': self.n_estimators,
                'max_depth': self.max_depth,
                'max_samples': self.max_samples,
                'contamination': self.contamination,
                'max_features': self.max_features,
                'bootstrap': self.bootstrap,
                'score_scale': self.score_scale,
                'temperature': self.temperature,
                'calibration_method': self.calibration_method
            },
            'feature_names': self.feature_names,
            'training_time': self.training_time,
            'calibrator': self.calibrator,
            'score_stats': self._score_stats,
            'feature_importance': self._feature_importance
        }
        
        joblib.dump(model_data, filepath, compress=3)
        
        file_size_mb = os.path.getsize(filepath) / 1024 / 1024
        logger.info(f"模型已保存: {filepath}")
        logger.info(f"模型文件大小: {file_size_mb:.2f}MB")
        
        return file_size_mb
    
    @classmethod
    def load_model(cls, filepath: str) -> 'LightweightIsolationForest':
        """加载模型"""
        model_data = joblib.load(filepath)
        
        params = model_data['params']
        instance = cls(
            n_estimators=params['n_estimators'],
            max_depth=params['max_depth'],
            max_samples=params['max_samples'],
            contamination=params['contamination'],
            max_features=params.get('max_features', 1.0),
            bootstrap=params.get('bootstrap', False),
            score_scale=params.get('score_scale', 5.0),
            calibration_method=params.get('calibration_method', 'temperature')
        )
        
        instance.model = model_data['model']
        instance.feature_names = model_data['feature_names']
        instance.training_time = model_data['training_time']
        instance.calibrator = model_data.get('calibrator')
        instance.temperature = params.get('temperature', 1.0)
        instance._score_stats = model_data.get('score_stats')
        instance._feature_importance = model_data.get('feature_importance')
        instance.is_trained = True
        
        logger.info(f"模型已加载: {filepath}")
        return instance


if __name__ == '__main__':
    print("="*60)
    print("轻量化孤立森林模型模块（优化版）")
    print("="*60)
    print("\n使用方法:")
    print("-"*60)
    print("  # 基础使用")
    print("  model = LightweightIsolationForest()")
    print("  model.train(X_train, y_train)  # 提供标签可校准分数")
    print("  predictions = model.predict(X_test)")
    print("  probabilities = model.predict_proba(X_test)")
    print("  metrics = model.evaluate(X_test, y_test)")
    print()
    print("  # 获取特征重要性")
    print("  importance = model.get_feature_importance()")
    print()
    print("  # 自动调优contamination")
    print("  best_cont = model.auto_tune_contamination(X_val, y_val)")
    print()
    print("  # 使用不同的校准方法")
    print("  model = LightweightIsolationForest(calibration_method='isotonic')")
    print("="*60)
