"""
增量学习模块
功能：在线学习、模型热更新、自适应阈值
目标：支持持续学习和模型优化
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional
from collections import deque
import logging
import time
from pathlib import Path
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class IncrementalLearner:
    """增量学习器"""
    
    def __init__(self, 
                 base_model: Any,
                 update_strategy: str = 'sliding_window',
                 window_size: int = 1000,
                 update_frequency: int = 100,
                 drift_detection: bool = True):
        """
        初始化增量学习器
        
        Args:
            base_model: 基础模型
            update_strategy: 更新策略 ('sliding_window', 'weighted', 'ensemble')
            window_size: 滑动窗口大小
            update_frequency: 更新频率（样本数）
            drift_detection: 是否检测概念漂移
        """
        self.base_model = base_model
        self.update_strategy = update_strategy
        self.window_size = window_size
        self.update_frequency = update_frequency
        self.drift_detection = drift_detection
        
        # 数据缓冲区
        self.data_buffer = deque(maxlen=window_size)
        self.label_buffer = deque(maxlen=window_size)
        self.sample_count = 0
        
        # 概念漂移检测
        self.drift_detector = None
        self.last_update_time = time.time()
        self.concept_drift_detected = False
        
        # 性能监控
        self.performance_history = []
        self.update_history = []
        
        logger.info(f"增量学习器初始化完成，策略: {update_strategy}, 窗口大小: {window_size}")
    
    def add_sample(self, X: np.ndarray, y: np.ndarray, feedback: Optional[np.ndarray] = None):
        """
        添加新样本
        
        Args:
            X: 新样本特征
            y: 新样本标签
            feedback: 用户反馈（可选）
        """
        # 添加到缓冲区
        self.data_buffer.append(X)
        self.label_buffer.append(y)
        self.sample_count += 1
        
        # 检查是否需要更新
        if self.sample_count % self.update_frequency == 0:
            self._check_for_update()
        
        # 概念漂移检测
        if self.drift_detection:
            self._detect_concept_drift(X, y, feedback)
    
    def _check_for_update(self):
        """检查是否需要更新模型"""
        if len(self.data_buffer) < self.update_frequency:
            return
        
        logger.info(f"检查模型更新，缓冲区大小: {len(self.data_buffer)}")
        
        # 检查性能变化
        if self._should_update_model():
            self._update_model()
    
    def _should_update_model(self) -> bool:
        """判断是否需要更新模型"""
        # 简单策略：缓冲区达到一定大小或检测到概念漂移
        if len(self.data_buffer) >= self.update_frequency:
            return True
        
        if self.concept_drift_detected:
            return True
        
        # 检查性能下降
        if len(self.performance_history) > 10:
            recent_performance = np.mean(self.performance_history[-5:])
            historical_performance = np.mean(self.performance_history[:-5])
            
            if recent_performance < historical_performance * 0.9:  # 性能下降10%
                logger.info(f"检测到性能下降，触发模型更新")
                return True
        
        return False
    
    def _update_model(self):
        """更新模型"""
        logger.info("开始增量模型更新...")
        
        # 准备训练数据
        X_train = np.array(self.data_buffer)
        y_train = np.array(self.label_buffer)
        
        if len(X_train) == 0:
            logger.warning("无训练数据，跳过更新")
            return
        
        try:
            # 根据策略更新模型
            if self.update_strategy == 'sliding_window':
                self._update_sliding_window(X_train, y_train)
            elif self.update_strategy == 'weighted':
                self._update_weighted(X_train, y_train)
            elif self.update_strategy == 'ensemble':
                self._update_ensemble(X_train, y_train)
            
            # 记录更新历史
            self.update_history.append({
                'timestamp': time.time(),
                'samples_processed': self.sample_count,
                'buffer_size': len(self.data_buffer),
                'strategy': self.update_strategy
            })
            
            logger.info(f"模型更新完成，已处理样本: {self.sample_count}")
            
        except Exception as e:
            logger.error(f"模型更新失败: {e}")
    
    def _update_sliding_window(self, X: np.ndarray, y: np.ndarray):
        """滑动窗口更新策略"""
        # 使用最新数据重新训练
        if hasattr(self.base_model, 'partial_fit'):
            self.base_model.partial_fit(X, y)
        else:
            # 完全重新训练
            self.base_model.fit(X, y)
    
    def _update_weighted(self, X: np.ndarray, y: np.ndarray):
        """加权更新策略"""
        # 为较新的样本分配更高权重
        n_samples = len(X)
        weights = np.linspace(0.1, 1.0, n_samples)  # 线性权重
        
        if hasattr(self.base_model, 'partial_fit'):
            self.base_model.partial_fit(X, y, sample_weight=weights)
        else:
            # 使用加权训练
            from sklearn.utils.class_weight import compute_sample_weight
            sample_weights = compute_sample_weight('balanced', y) * weights
            self.base_model.fit(X, y, sample_weight=sample_weights)
    
    def _update_ensemble(self, X: np.ndarray, y: np.ndarray):
        """集成更新策略"""
        # 创建新模型并集成
        from sklearn.base import clone
        new_model = clone(self.base_model)
        new_model.fit(X, y)
        
        # 简单的模型平均（可根据需要扩展为更复杂的集成）
        if not hasattr(self, 'ensemble_models'):
            self.ensemble_models = [self.base_model]
        
        self.ensemble_models.append(new_model)
        
        # 限制集成大小
        if len(self.ensemble_models) > 5:
            self.ensemble_models.pop(0)
    
    def _detect_concept_drift(self, X: np.ndarray, y: np.ndarray, feedback: Optional[np.ndarray] = None):
        """检测概念漂移"""
        if len(self.data_buffer) < 100:  # 需要足够的数据
            return
        
        # 简单漂移检测：检查预测准确率变化
        try:
            predictions = self.predict(X)
            accuracy = np.mean(predictions == y)
            
            # 记录性能
            self.performance_history.append(accuracy)
            
            # 检测性能下降
            if len(self.performance_history) > 20:
                recent_acc = np.mean(self.performance_history[-10:])
                historical_acc = np.mean(self.performance_history[:-10])
                
                if recent_acc < historical_acc * 0.8:  # 性能下降20%
                    self.concept_drift_detected = True
                    logger.warning("检测到概念漂移，准备模型更新")
                    
        except Exception as e:
            logger.debug(f"概念漂移检测失败: {e}")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        if hasattr(self, 'ensemble_models') and self.update_strategy == 'ensemble':
            # 集成预测
            predictions = []
            for model in self.ensemble_models:
                pred = model.predict(X)
                predictions.append(pred)
            
            # 多数投票
            predictions = np.array(predictions)
            return np.round(np.mean(predictions, axis=0))
        else:
            return self.base_model.predict(X)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            'total_samples': self.sample_count,
            'buffer_size': len(self.data_buffer),
            'update_count': len(self.update_history),
            'recent_accuracy': np.mean(self.performance_history[-10:]) if self.performance_history else 0,
            'concept_drift_detected': self.concept_drift_detected,
            'last_update_time': self.last_update_time
        }
    
    def save_state(self, filepath: str):
        """保存学习器状态"""
        state = {
            'base_model': self.base_model,
            'data_buffer': list(self.data_buffer),
            'label_buffer': list(self.label_buffer),
            'sample_count': self.sample_count,
            'performance_history': self.performance_history,
            'update_history': self.update_history,
            'concept_drift_detected': self.concept_drift_detected
        }
        
        joblib.dump(state, filepath)
        logger.info(f"增量学习器状态已保存: {filepath}")
    
    @classmethod
    def load_state(cls, filepath: str) -> 'IncrementalLearner':
        """加载学习器状态"""
        state = joblib.load(filepath)
        
        instance = cls(state['base_model'])
        instance.data_buffer = deque(state['data_buffer'], maxlen=instance.window_size)
        instance.label_buffer = deque(state['label_buffer'], maxlen=instance.window_size)
        instance.sample_count = state['sample_count']
        instance.performance_history = state['performance_history']
        instance.update_history = state['update_history']
        instance.concept_drift_detected = state['concept_drift_detected']
        
        logger.info(f"增量学习器状态已加载: {filepath}")
        return instance


class AdaptiveThreshold:
    """自适应阈值调整器"""
    
    def __init__(self, 
                 initial_threshold: float = 0.5,
                 adaptation_rate: float = 0.1,
                 min_threshold: float = 0.1,
                 max_threshold: float = 0.9):
        """
        初始化自适应阈值
        
        Args:
            initial_threshold: 初始阈值
            adaptation_rate: 适应率
            min_threshold: 最小阈值
            max_threshold: 最大阈值
        """
        self.threshold = initial_threshold
        self.adaptation_rate = adaptation_rate
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        
        self.feedback_history = []
        self.performance_history = []
    
    def update_threshold(self, predictions: np.ndarray, ground_truth: np.ndarray):
        """根据反馈更新阈值"""
        if len(predictions) == 0:
            return
        
        # 计算当前性能
        accuracy = np.mean(predictions == ground_truth)
        self.performance_history.append(accuracy)
        
        # 基于性能调整阈值
        if len(self.performance_history) > 10:
            recent_performance = np.mean(self.performance_history[-5:])
            historical_performance = np.mean(self.performance_history[:-5])
            
            # 性能下降时调整阈值
            if recent_performance < historical_performance:
                adjustment = self.adaptation_rate * (historical_performance - recent_performance)
                self.threshold = np.clip(self.threshold + adjustment, self.min_threshold, self.max_threshold)
                
                logger.info(f"阈值调整: {self.threshold:.4f} (性能变化: {recent_performance - historical_performance:.4f})")
    
    def get_threshold(self) -> float:
        """获取当前阈值"""
        return self.threshold
    
    def reset(self):
        """重置阈值"""
        self.threshold = (self.min_threshold + self.max_threshold) / 2
        self.feedback_history.clear()
        self.performance_history.clear()


class OnlineModelManager:
    """在线模型管理器"""
    
    def __init__(self, model_dir: str = './models'):
        """
        初始化模型管理器
        
        Args:
            model_dir: 模型存储目录
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.models = {}
        self.model_versions = {}
        self.active_model = None
        
        logger.info(f"在线模型管理器初始化完成，模型目录: {model_dir}")
    
    def register_model(self, name: str, model: Any, version: str = 'v1.0'):
        """注册模型"""
        self.models[name] = model
        self.model_versions[name] = version
        
        if self.active_model is None:
            self.active_model = name
        
        logger.info(f"模型注册: {name} (版本: {version})")
    
    def switch_model(self, name: str):
        """切换活动模型"""
        if name not in self.models:
            raise ValueError(f"模型未注册: {name}")
        
        self.active_model = name
        logger.info(f"切换活动模型: {name}")
    
    def save_model(self, name: str, filename: str = None):
        """保存模型"""
        if name not in self.models:
            raise ValueError(f"模型未注册: {name}")
        
        if filename is None:
            filename = f"{name}_{self.model_versions[name]}.joblib"
        
        filepath = self.model_dir / filename
        joblib.dump(self.models[name], filepath)
        
        logger.info(f"模型已保存: {filepath}")
    
    def load_model(self, filepath: str, name: str, version: str = 'v1.0'):
        """加载模型"""
        model = joblib.load(filepath)
        self.register_model(name, model, version)
        
        logger.info(f"模型已加载: {filepath}")
    
    def get_active_model(self) -> Any:
        """获取活动模型"""
        if self.active_model is None:
            raise ValueError("没有活动模型")
        
        return self.models[self.active_model]
    
    def list_models(self) -> Dict[str, str]:
        """列出所有模型"""
        return self.model_versions.copy()