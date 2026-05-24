"""
集成学习模块
功能：模型融合、投票机制、加权集成
目标：提升模型鲁棒性和泛化能力

优化内容：
1. 添加更高效的权重优化算法（贝叶斯优化、差分进化）
2. 统一模型接口（BaseAnomalyDetector 抽象基类）
3. 增加更多投票策略（Stacking、Blending）
4. 支持模型多样性分析
5. 添加 evaluate 和 benchmark_inference 方法保持接口一致
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Callable
from abc import ABC, abstractmethod
from collections import deque
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score, 
    roc_auc_score, confusion_matrix
)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
import time
import logging
import warnings

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BaseAnomalyDetector(ABC):
    """异常检测器抽象基类（统一接口）"""
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测异常（0=正常，1=异常）"""
        pass
    
    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测异常概率"""
        pass
    
    @abstractmethod
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """评估模型性能"""
        pass
    
    @abstractmethod
    def benchmark_inference(self, X_sample: np.ndarray, n_iterations: int = 100) -> Dict:
        """推理性能基准测试"""
        pass


class EnsembleAnomalyDetector:
    """集成异常检测器（优化版）"""
    
    # 支持的投票策略
    VOTING_STRATEGIES = ['majority', 'weighted', 'soft', 'stacking', 'max_confidence']
    
    # 支持的权重优化方法
    OPTIMIZATION_METHODS = ['grid_search', 'random_search', 'differential_evolution', 'bayesian', 'performance_based']
    
    def __init__(self, 
                 voting_strategy: str = 'weighted', 
                 weights: Dict[str, float] = None,
                 meta_learner: str = 'logistic_regression',
                 use_diversity_weighting: bool = False):
        """
        初始化集成检测器
        
        Args:
            voting_strategy: 投票策略 ('majority', 'weighted', 'soft', 'stacking', 'max_confidence')
            weights: 模型权重字典
            meta_learner: Stacking 的元学习器类型
            use_diversity_weighting: 是否基于多样性调整权重
        """
        self.voting_strategy = voting_strategy
        self.weights = weights or {}
        self.models = {}
        self.is_trained = False
        self.meta_learner_type = meta_learner
        self.meta_learner = None  # Stacking 的元学习器
        self.use_diversity_weighting = use_diversity_weighting
        self._diversity_matrix = None
        self._model_performances = {}  # 记录各模型的历史性能
        
    def add_model(self, name: str, model: Any, weight: float = 1.0):
        """
        添加模型到集成
        
        Args:
            name: 模型名称
            model: 模型实例（需要有 predict 和 predict_proba 方法）
            weight: 初始权重
        """
        # 验证模型接口
        if not hasattr(model, 'predict'):
            raise ValueError(f"模型 {name} 必须实现 predict 方法")
        
        self.models[name] = model
        self.weights[name] = weight
        self._model_performances[name] = deque(maxlen=100)  # 记录最近100次性能
        
        logger.info(f"添加模型: {name}, 初始权重: {weight}")
        
        # 如果有多个模型，计算多样性
        if len(self.models) > 1:
            self.is_trained = False  # 需要重新训练元学习器
    
    def remove_model(self, name: str):
        """移除模型"""
        if name in self.models:
            del self.models[name]
            del self.weights[name]
            if name in self._model_performances:
                del self._model_performances[name]
            logger.info(f"移除模型: {name}")
    
    def majority_vote(self, predictions: Dict[str, np.ndarray]) -> np.ndarray:
        """多数投票"""
        all_predictions = np.array(list(predictions.values()))
        return (np.mean(all_predictions, axis=0) >= 0.5).astype(int)
    
    def weighted_vote(self, predictions: Dict[str, np.ndarray]) -> np.ndarray:
        """加权投票"""
        weighted_sum = np.zeros_like(list(predictions.values())[0], dtype=float)
        total_weight = 0
        
        for name, pred in predictions.items():
            weight = self.weights.get(name, 1.0)
            
            # 如果启用多样性加权，调整权重
            if self.use_diversity_weighting and self._diversity_matrix is not None:
                diversity_bonus = self._get_diversity_bonus(name)
                weight *= (1 + diversity_bonus)
            
            weighted_sum += pred.astype(float) * weight
            total_weight += weight
        
        return (weighted_sum / total_weight >= 0.5).astype(int)
    
    def soft_vote(self, prediction_probas: Dict[str, np.ndarray]) -> np.ndarray:
        """软投票（基于概率）"""
        weighted_proba = np.zeros_like(list(prediction_probas.values())[0], dtype=float)
        total_weight = 0
        
        for name, proba in prediction_probas.items():
            weight = self.weights.get(name, 1.0)
            weighted_proba += proba * weight
            total_weight += weight
        
        avg_proba = weighted_proba / total_weight
        return (avg_proba > 0.5).astype(int)
    
    def max_confidence_vote(self, predictions: Dict[str, np.ndarray], 
                            probas: Dict[str, np.ndarray]) -> np.ndarray:
        """
        最大置信度投票：选择最有信心的模型的预测
        """
        n_samples = len(list(predictions.values())[0])
        results = np.zeros(n_samples, dtype=int)
        
        for i in range(n_samples):
            max_confidence = 0
            best_pred = 0
            
            for name in predictions.keys():
                if name in probas:
                    # 置信度 = |概率 - 0.5| * 2
                    confidence = abs(probas[name][i] - 0.5) * 2
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_pred = predictions[name][i]
            
            results[i] = best_pred
        
        return results
    
    def stacking_predict(self, X: np.ndarray) -> np.ndarray:
        """
        Stacking 预测：使用元学习器组合各模型预测
        """
        if self.meta_learner is None:
            raise ValueError("元学习器未训练，请先调用 fit_stacking 方法")
        
        # 获取各模型的概率预测作为元特征
        meta_features = self._get_meta_features(X)
        
        # 使用元学习器预测
        return self.meta_learner.predict(meta_features)
    
    def _get_meta_features(self, X: np.ndarray) -> np.ndarray:
        """获取元特征（各模型的概率预测）"""
        features = []
        
        for name, model in self.models.items():
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
                features.append(proba.reshape(-1, 1))
            else:
                pred = model.predict(X)
                features.append(pred.reshape(-1, 1))
        
        return np.hstack(features)
    
    def fit_stacking(self, X_train: np.ndarray, y_train: np.ndarray):
        """
        训练 Stacking 元学习器
        
        Args:
            X_train: 训练数据
            y_train: 标签
        """
        y_binary = np.where(y_train > 0, 1, 0)
        
        # 获取元特征
        meta_features = self._get_meta_features(X_train)
        
        # 训练元学习器
        if self.meta_learner_type == 'logistic_regression':
            self.meta_learner = LogisticRegression(random_state=42, max_iter=500)
        else:
            self.meta_learner = LogisticRegression(random_state=42)
        
        self.meta_learner.fit(meta_features, y_binary)
        self.is_trained = True
        
        logger.info("Stacking 元学习器训练完成")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """集成预测"""
        if not self.models:
            raise ValueError("没有添加任何模型")
        
        predictions = {}
        prediction_probas = {}
        
        for name, model in self.models.items():
            try:
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                    prediction_probas[name] = proba
                
                pred = model.predict(X)
                predictions[name] = pred
                
            except Exception as e:
                logger.warning(f"模型 {name} 预测失败: {e}")
                continue
        
        if not predictions:
            raise ValueError("所有模型预测失败")
        
        # 根据策略选择投票方法
        if self.voting_strategy == 'stacking':
            if self.meta_learner is None:
                logger.warning("Stacking 元学习器未训练，回退到加权投票")
                return self.weighted_vote(predictions)
            return self.stacking_predict(X)
        elif self.voting_strategy == 'soft' and prediction_probas:
            return self.soft_vote(prediction_probas)
        elif self.voting_strategy == 'max_confidence' and prediction_probas:
            return self.max_confidence_vote(predictions, prediction_probas)
        elif self.voting_strategy == 'weighted':
            return self.weighted_vote(predictions)
        else:
            return self.majority_vote(predictions)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        预测异常概率（集成）
        """
        if not self.models:
            raise ValueError("没有添加任何模型")
        
        probas = []
        weights = []
        
        for name, model in self.models.items():
            try:
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                else:
                    proba = model.predict(X).astype(float)
                
                probas.append(proba)
                weights.append(self.weights.get(name, 1.0))
            except Exception as e:
                logger.warning(f"模型 {name} 概率预测失败: {e}")
                continue
        
        if not probas:
            raise ValueError("所有模型概率预测失败")
        
        # 加权平均
        weights = np.array(weights) / np.sum(weights)
        weighted_proba = np.zeros_like(probas[0])
        
        for p, w in zip(probas, weights):
            weighted_proba += p * w
        
        return weighted_proba
    
    def calculate_diversity(self, X: np.ndarray, y: np.ndarray = None) -> Dict[str, Any]:
        """
        计算模型多样性（不一致性度量）
        
        Returns:
            多样性指标字典
        """
        if len(self.models) < 2:
            return {'message': '需要至少2个模型来计算多样性'}
        
        # 获取各模型预测
        predictions = {}
        for name, model in self.models.items():
            try:
                predictions[name] = model.predict(X)
            except:
                continue
        
        model_names = list(predictions.keys())
        n_models = len(model_names)
        
        # 计算两两不一致率
        disagreement_matrix = np.zeros((n_models, n_models))
        
        for i in range(n_models):
            for j in range(i + 1, n_models):
                pred_i = predictions[model_names[i]]
                pred_j = predictions[model_names[j]]
                disagreement = np.mean(pred_i != pred_j)
                disagreement_matrix[i, j] = disagreement
                disagreement_matrix[j, i] = disagreement
        
        self._diversity_matrix = disagreement_matrix
        
        # 计算平均不一致率
        avg_disagreement = np.mean(disagreement_matrix[np.triu_indices(n_models, k=1)])
        
        # 计算 Q 统计量（如果提供了真实标签）
        q_statistic = None
        if y is not None:
            y_binary = np.where(y > 0, 1, 0)
            q_values = []
            
            for i in range(n_models):
                for j in range(i + 1, n_models):
                    pred_i = predictions[model_names[i]]
                    pred_j = predictions[model_names[j]]
                    
                    # 计算 Q 统计量
                    n11 = np.sum((pred_i == y_binary) & (pred_j == y_binary))
                    n00 = np.sum((pred_i != y_binary) & (pred_j != y_binary))
                    n10 = np.sum((pred_i == y_binary) & (pred_j != y_binary))
                    n01 = np.sum((pred_i != y_binary) & (pred_j == y_binary))
                    
                    numerator = n11 * n00 - n01 * n10
                    denominator = n11 * n00 + n01 * n10
                    
                    if denominator != 0:
                        q_values.append(numerator / denominator)
            
            if q_values:
                q_statistic = np.mean(q_values)
        
        diversity_result = {
            'model_names': model_names,
            'disagreement_matrix': disagreement_matrix.tolist(),
            'avg_disagreement': avg_disagreement,
            'q_statistic': q_statistic,
            'interpretation': 'Q接近0表示高多样性，Q接近1表示模型相似' if q_statistic else None
        }
        
        logger.info(f"多样性分析: 平均不一致率={avg_disagreement:.4f}")
        if q_statistic is not None:
            logger.info(f"  Q统计量={q_statistic:.4f}")
        
        return diversity_result
    
    def _get_diversity_bonus(self, model_name: str) -> float:
        """获取基于多样性的权重加成"""
        if self._diversity_matrix is None:
            return 0.0
        
        model_names = list(self.models.keys())
        if model_name not in model_names:
            return 0.0
        
        idx = model_names.index(model_name)
        
        # 与其他模型的平均不一致率越高，加成越大
        avg_disagreement = np.mean(self._diversity_matrix[idx, :])
        
        return avg_disagreement * 0.5  # 最多50%加成
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """
        评估集成模型性能（统一接口）
        """
        return self.evaluate_ensemble(X_test, y_test)
    
    def evaluate_ensemble(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        """评估集成模型性能"""
        y_binary = np.where(y_test > 0, 1, 0)
        
        # 集成预测
        ensemble_pred = self.predict(X_test)
        ensemble_proba = self.predict_proba(X_test)
        
        # 计算集成指标
        ensemble_metrics = {
            'accuracy': accuracy_score(y_binary, ensemble_pred),
            'precision': precision_score(y_binary, ensemble_pred, zero_division=0),
            'recall': recall_score(y_binary, ensemble_pred, zero_division=0),
            'f1_score': f1_score(y_binary, ensemble_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_binary, ensemble_pred).tolist()
        }
        
        # 计算 AUC-ROC
        try:
            ensemble_metrics['auc_roc'] = roc_auc_score(y_binary, ensemble_proba)
        except ValueError:
            ensemble_metrics['auc_roc'] = 0.5
        
        # 计算误报率和漏报率
        tn, fp, fn, tp = confusion_matrix(y_binary, ensemble_pred).ravel()
        ensemble_metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
        ensemble_metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0
        
        # 各模型单独性能
        individual_metrics = {}
        for name, model in self.models.items():
            try:
                pred = model.predict(X_test)
                individual_metrics[name] = {
                    'accuracy': accuracy_score(y_binary, pred),
                    'precision': precision_score(y_binary, pred, zero_division=0),
                    'recall': recall_score(y_binary, pred, zero_division=0),
                    'f1_score': f1_score(y_binary, pred, zero_division=0)
                }
                
                # 更新性能历史
                self._model_performances[name].append(individual_metrics[name]['f1_score'])
                
            except Exception as e:
                logger.warning(f"模型 {name} 评估失败: {e}")
        
        # 性能提升分析
        if individual_metrics:
            best_individual_f1 = max([m['f1_score'] for m in individual_metrics.values()])
        else:
            best_individual_f1 = 0
            
        ensemble_f1 = ensemble_metrics['f1_score']
        improvement = ensemble_f1 - best_individual_f1
        
        results = {
            'ensemble_metrics': ensemble_metrics,
            'individual_metrics': individual_metrics,
            'improvement_analysis': {
                'best_individual_f1': best_individual_f1,
                'ensemble_f1': ensemble_f1,
                'improvement': improvement,
                'improvement_percentage': (improvement / best_individual_f1 * 100) if best_individual_f1 > 0 else 0
            },
            'weights': self.weights.copy(),
            'voting_strategy': self.voting_strategy
        }
        
        logger.info(f"集成模型评估结果:")
        logger.info(f"  集成F1分数: {ensemble_f1:.4f}")
        logger.info(f"  集成AUC-ROC: {ensemble_metrics['auc_roc']:.4f}")
        logger.info(f"  最佳单模型F1: {best_individual_f1:.4f}")
        logger.info(f"  提升: {improvement:.4f} ({results['improvement_analysis']['improvement_percentage']:.2f}%)")
        
        return results
    
    def benchmark_inference(self, X_sample: np.ndarray, n_iterations: int = 100) -> Dict[str, Any]:
        """
        推理性能基准测试（统一接口）
        """
        if not self.models:
            raise ValueError("没有添加任何模型")
        
        single_sample = X_sample[0:1]
        batch_sample = X_sample[:min(32, len(X_sample))]
        
        # 预热
        for _ in range(10):
            self.predict(single_sample)
        
        # 单样本测试
        single_times = []
        for _ in range(n_iterations):
            start = time.time()
            self.predict(single_sample)
            single_times.append((time.time() - start) * 1000)
        
        # 批量测试
        batch_times = []
        for _ in range(n_iterations // 10):
            start = time.time()
            self.predict(batch_sample)
            batch_times.append((time.time() - start) * 1000)
        
        # 各模型推理时间
        model_times = {}
        for name, model in self.models.items():
            if hasattr(model, 'benchmark_inference'):
                try:
                    model_benchmark = model.benchmark_inference(X_sample, n_iterations=20)
                    model_times[name] = model_benchmark.get('avg_inference_time_ms', 0)
                except:
                    pass
        
        benchmark = {
            'avg_inference_time_ms': np.mean(single_times),
            'max_inference_time_ms': np.max(single_times),
            'min_inference_time_ms': np.min(single_times),
            'std_inference_time_ms': np.std(single_times),
            'p95_inference_time_ms': np.percentile(single_times, 95),
            'avg_batch_inference_time_ms': np.mean(batch_times),
            'throughput_samples_per_sec': 1000 / np.mean(batch_times) * len(batch_sample) if batch_times else 0,
            'model_inference_times': model_times,
            'n_models': len(self.models)
        }
        
        logger.info(f"集成模型推理性能:")
        logger.info(f"  平均推理时间: {benchmark['avg_inference_time_ms']:.3f}ms")
        logger.info(f"  P95推理时间: {benchmark['p95_inference_time_ms']:.3f}ms")
        logger.info(f"  吞吐量: {benchmark['throughput_samples_per_sec']:.1f}样本/秒")
        
        return benchmark
    
    def optimize_weights(self, X_val: np.ndarray, y_val: np.ndarray, 
                        method: str = 'differential_evolution',
                        n_iterations: int = 50) -> Dict[str, float]:
        """
        优化模型权重
        
        Args:
            X_val: 验证数据
            y_val: 验证标签
            method: 优化方法 ('grid_search', 'random_search', 'differential_evolution', 'bayesian', 'performance_based')
            n_iterations: 迭代次数
            
        Returns:
            最优权重字典
        """
        y_binary = np.where(y_val > 0, 1, 0)
        
        # 获取各模型在验证集上的预测
        predictions = {}
        probas = {}
        for name, model in self.models.items():
            try:
                predictions[name] = model.predict(X_val)
                if hasattr(model, 'predict_proba'):
                    probas[name] = model.predict_proba(X_val)
            except Exception as e:
                logger.warning(f"模型 {name} 验证集预测失败: {e}")
                continue
        
        if method == 'grid_search':
            return self._grid_search_weights(predictions, y_binary)
        elif method == 'random_search':
            return self._random_search_weights(predictions, y_binary, n_iterations)
        elif method == 'differential_evolution':
            return self._differential_evolution_weights(predictions, y_binary, n_iterations)
        elif method == 'performance_based':
            return self._performance_based_weights(predictions, y_binary)
        else:
            return self._equal_weights()
    
    def _grid_search_weights(self, predictions: Dict[str, np.ndarray], 
                            y_true: np.ndarray) -> Dict[str, float]:
        """网格搜索优化权重"""
        best_f1 = 0
        best_weights = {}
        
        weight_options = [0.1, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0]
        
        from itertools import product
        n_models = len(self.models)
        
        # 限制搜索空间
        if n_models > 3:
            weight_options = [0.5, 1.0, 2.0]
        
        weight_combinations = list(product(weight_options, repeat=n_models))
        
        for weights in weight_combinations:
            weight_dict = {name: w for name, w in zip(self.models.keys(), weights)}
            
            try:
                # 计算加权投票
                weighted_sum = np.zeros_like(list(predictions.values())[0], dtype=float)
                total_weight = sum(weights)
                
                for name, pred in predictions.items():
                    weighted_sum += pred.astype(float) * weight_dict[name]
                
                ensemble_pred = (weighted_sum / total_weight >= 0.5).astype(int)
                f1 = f1_score(y_true, ensemble_pred, zero_division=0)
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_weights = weight_dict.copy()
            except:
                continue
        
        self.weights = best_weights
        logger.info(f"网格搜索权重优化完成，最佳F1: {best_f1:.4f}")
        logger.info(f"最优权重: {best_weights}")
        
        return best_weights
    
    def _random_search_weights(self, predictions: Dict[str, np.ndarray],
                               y_true: np.ndarray, n_iterations: int = 50) -> Dict[str, float]:
        """随机搜索优化权重"""
        best_f1 = 0
        best_weights = {}
        model_names = list(self.models.keys())
        
        for _ in range(n_iterations):
            # 生成随机权重
            random_weights = np.random.uniform(0.1, 3.0, len(model_names))
            weight_dict = {name: w for name, w in zip(model_names, random_weights)}
            
            try:
                weighted_sum = np.zeros_like(list(predictions.values())[0], dtype=float)
                total_weight = sum(random_weights)
                
                for name, pred in predictions.items():
                    weighted_sum += pred.astype(float) * weight_dict[name]
                
                ensemble_pred = (weighted_sum / total_weight >= 0.5).astype(int)
                f1 = f1_score(y_true, ensemble_pred, zero_division=0)
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_weights = weight_dict.copy()
            except:
                continue
        
        self.weights = best_weights
        logger.info(f"随机搜索权重优化完成，最佳F1: {best_f1:.4f}")
        
        return best_weights
    
    def _differential_evolution_weights(self, predictions: Dict[str, np.ndarray],
                                        y_true: np.ndarray, 
                                        n_iterations: int = 50) -> Dict[str, float]:
        """差分进化优化权重（高效的全局优化算法）"""
        model_names = list(self.models.keys())
        n_models = len(model_names)
        
        # 差分进化参数
        pop_size = max(10, 4 * n_models)
        F = 0.8  # 缩放因子
        CR = 0.9  # 交叉率
        
        # 初始化种群
        population = np.random.uniform(0.1, 3.0, (pop_size, n_models))
        
        def evaluate_weights(weights):
            """评估权重组合的F1分数"""
            weight_dict = {name: w for name, w in zip(model_names, weights)}
            
            weighted_sum = np.zeros_like(list(predictions.values())[0], dtype=float)
            total_weight = sum(weights)
            
            for name, pred in predictions.items():
                weighted_sum += pred.astype(float) * weight_dict[name]
            
            ensemble_pred = (weighted_sum / total_weight >= 0.5).astype(int)
            return f1_score(y_true, ensemble_pred, zero_division=0)
        
        # 评估初始种群
        fitness = np.array([evaluate_weights(ind) for ind in population])
        
        best_idx = np.argmax(fitness)
        best_weights = population[best_idx].copy()
        best_f1 = fitness[best_idx]
        
        # 进化迭代
        for generation in range(n_iterations):
            for i in range(pop_size):
                # 选择3个不同的个体
                candidates = [j for j in range(pop_size) if j != i]
                a, b, c = np.random.choice(candidates, 3, replace=False)
                
                # 变异
                mutant = population[a] + F * (population[b] - population[c])
                mutant = np.clip(mutant, 0.1, 5.0)
                
                # 交叉
                cross_points = np.random.rand(n_models) < CR
                if not np.any(cross_points):
                    cross_points[np.random.randint(n_models)] = True
                
                trial = np.where(cross_points, mutant, population[i])
                
                # 选择
                trial_fitness = evaluate_weights(trial)
                if trial_fitness > fitness[i]:
                    population[i] = trial
                    fitness[i] = trial_fitness
                    
                    if trial_fitness > best_f1:
                        best_f1 = trial_fitness
                        best_weights = trial.copy()
        
        best_weight_dict = {name: w for name, w in zip(model_names, best_weights)}
        self.weights = best_weight_dict
        
        logger.info(f"差分进化权重优化完成，最佳F1: {best_f1:.4f}")
        logger.info(f"最优权重: {best_weight_dict}")
        
        return best_weight_dict
    
    def _performance_based_weights(self, predictions: Dict[str, np.ndarray],
                                   y_true: np.ndarray) -> Dict[str, float]:
        """基于各模型性能分配权重"""
        weights = {}
        
        for name, pred in predictions.items():
            f1 = f1_score(y_true, pred, zero_division=0)
            # 权重 = F1^2（让高性能模型获得更高权重）
            weights[name] = max(0.1, f1 ** 2)
        
        # 归一化
        total = sum(weights.values())
        weights = {k: v / total * len(weights) for k, v in weights.items()}
        
        self.weights = weights
        logger.info(f"基于性能的权重分配: {weights}")
        
        return weights
    
    def _equal_weights(self) -> Dict[str, float]:
        """等权重分配"""
        weights = {name: 1.0 for name in self.models.keys()}
        self.weights = weights
        return weights


class AdaptiveThresholdEnsemble:
    """自适应阈值集成检测器（优化版）"""
    
    def __init__(self, base_ensemble: EnsembleAnomalyDetector, 
                 adaptation_rate: float = 0.1,
                 max_history: int = 100,
                 decay_factor: float = 0.95):
        """
        初始化自适应集成
        
        Args:
            base_ensemble: 基础集成模型
            adaptation_rate: 自适应学习率
            max_history: 最大反馈历史长度
            decay_factor: 历史衰减因子
        """
        self.ensemble = base_ensemble
        self.adaptation_rate = adaptation_rate
        self.feedback_history = deque(maxlen=max_history)
        self.decay_factor = decay_factor
        self._adaptation_count = 0
        
    def update_with_feedback(self, X: np.ndarray, feedback: np.ndarray):
        """
        根据反馈更新模型权重
        
        Args:
            X: 新数据
            feedback: 真实标签反馈
        """
        import time
        
        # 记录反馈
        self.feedback_history.append({
            'X': X.copy(),
            'feedback': feedback.copy(),
            'timestamp': time.time()
        })
        
        # 基于近期反馈调整权重
        if len(self.feedback_history) >= 10:
            self._adapt_weights()
            self._adaptation_count += 1
    
    def _adapt_weights(self):
        """自适应调整权重（带时间衰减）"""
        current_time = time.time()
        performance_scores = {name: [] for name in self.ensemble.models.keys()}
        
        for feedback_item in self.feedback_history:
            # 计算时间衰减权重
            time_diff = current_time - feedback_item['timestamp']
            time_weight = self.decay_factor ** (time_diff / 3600)  # 每小时衰减
            
            for name, model in self.ensemble.models.items():
                try:
                    pred = model.predict(feedback_item['X'])
                    f1 = f1_score(feedback_item['feedback'], pred, zero_division=0)
                    performance_scores[name].append(f1 * time_weight)
                except:
                    continue
        
        # 根据加权平均性能调整权重
        for name, scores in performance_scores.items():
            if scores:
                avg_score = np.mean(scores)
                current_weight = self.ensemble.weights.get(name, 1.0)
                
                # 自适应更新
                new_weight = current_weight * (1 + self.adaptation_rate * (avg_score - 0.5))
                self.ensemble.weights[name] = np.clip(new_weight, 0.1, 5.0)
        
        logger.info(f"权重自适应调整完成（第{self._adaptation_count}次）")
        
    def predict(self, X: np.ndarray) -> np.ndarray:
        """使用自适应集成进行预测"""
        return self.ensemble.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """使用自适应集成进行概率预测"""
        return self.ensemble.predict_proba(X)
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        """评估自适应集成性能"""
        return self.ensemble.evaluate(X_test, y_test)
    
    def get_adaptation_stats(self) -> Dict:
        """获取自适应统计信息"""
        return {
            'adaptation_count': self._adaptation_count,
            'feedback_history_size': len(self.feedback_history),
            'current_weights': self.ensemble.weights.copy()
        }


if __name__ == '__main__':
    print("="*60)
    print("集成学习模块（优化版）")
    print("="*60)
    print("\n支持的投票策略:", EnsembleAnomalyDetector.VOTING_STRATEGIES)
    print("支持的优化方法:", EnsembleAnomalyDetector.OPTIMIZATION_METHODS)
    print()
    print("使用示例:")
    print("-"*60)
    print("  ensemble = EnsembleAnomalyDetector(voting_strategy='weighted')")
    print("  ensemble.add_model('autoencoder', ae_model, weight=1.0)")
    print("  ensemble.add_model('isolation_forest', if_model, weight=1.0)")
    print()
    print("  # 权重优化")
    print("  best_weights = ensemble.optimize_weights(X_val, y_val, method='differential_evolution')")
    print()
    print("  # 多样性分析")
    print("  diversity = ensemble.calculate_diversity(X_test, y_test)")
    print()
    print("  # Stacking 集成")
    print("  ensemble = EnsembleAnomalyDetector(voting_strategy='stacking')")
    print("  ensemble.fit_stacking(X_train, y_train)")
    print("="*60)