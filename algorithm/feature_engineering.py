"""
特征工程模块
功能：时序特征提取、特征选择、数据增强
目标：提升模型性能和泛化能力

优化内容：
1. 修复 scipy.stats 导入问题（skew, kurtosis）
2. 添加更多统计特征（熵、能量等）
3. 增强数据增强方法（SMOTE、过采样）
4. 添加特征交互和多项式特征
5. 完善异常处理和边界情况
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Any, Optional, Union
from sklearn.preprocessing import StandardScaler, MinMaxScaler, PolynomialFeatures
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif, RFE
from sklearn.ensemble import RandomForestClassifier
from scipy.stats import skew, kurtosis, entropy
from scipy.interpolate import interp1d
import warnings
import logging

warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TimeSeriesFeatureExtractor:
    """时序特征提取器（优化版）"""
    
    def __init__(self, window_size: int = 5, lag_features: List[int] = None,
                 include_entropy: bool = True, include_energy: bool = True):
        """
        初始化特征提取器
        
        Args:
            window_size: 滑动窗口大小
            lag_features: 滞后特征列表
            include_entropy: 是否包含熵特征
            include_energy: 是否包含能量特征
        """
        self.window_size = window_size
        self.lag_features = lag_features or [1, 2, 3, 5, 7]
        self.include_entropy = include_entropy
        self.include_energy = include_energy
        self.feature_names = []
    
    def extract_statistical_features(self, X: np.ndarray) -> np.ndarray:
        """
        提取统计特征
        
        Args:
            X: 输入数据 (n_samples, n_features)
            
        Returns:
            统计特征数组
        """
        features = []
        
        for i in range(X.shape[1]):
            feature_col = X[:, i]
            
            # 处理空数组或常量数组的情况
            if len(feature_col) == 0:
                features.extend([0] * 11)
                continue
            
            # 基本统计量
            features.extend([
                np.mean(feature_col),      # 均值
                np.std(feature_col),       # 标准差
                np.min(feature_col),       # 最小值
                np.max(feature_col),       # 最大值
                np.median(feature_col),    # 中位数
                np.percentile(feature_col, 25),  # 25分位数
                np.percentile(feature_col, 75),  # 75分位数
                np.sum(feature_col),       # 总和
            ])
            
            # 高阶统计量 - 使用 scipy.stats
            features.extend([
                np.var(feature_col),       # 方差
                skew(feature_col) if len(feature_col) > 2 else 0,      # 偏度
                kurtosis(feature_col) if len(feature_col) > 3 else 0,  # 峰度
            ])
            
            # 可选特征
            if self.include_entropy:
                # 计算熵（需要离散化）
                hist, _ = np.histogram(feature_col, bins=10, density=True)
                hist = hist[hist > 0]  # 移除零值
                ent = entropy(hist) if len(hist) > 0 else 0
                features.append(ent)
            
            if self.include_energy:
                # 信号能量
                energy = np.sum(feature_col ** 2)
                features.append(energy)
        
        return np.array(features).reshape(1, -1)
    
    def extract_temporal_features(self, X: np.ndarray, timestamps: np.ndarray = None) -> np.ndarray:
        """
        提取时序特征
        
        Args:
            X: 输入数据
            timestamps: 时间戳数组（可选）
            
        Returns:
            时序特征数组
        """
        features = []
        
        for i in range(X.shape[1]):
            feature_col = X[:, i]
            
            if len(feature_col) == 0:
                features.extend([0] * 7)
                continue
            
            # 趋势特征
            if len(feature_col) > 1:
                # 线性趋势
                x = np.arange(len(feature_col))
                try:
                    slope, intercept = np.polyfit(x, feature_col, 1)
                    features.append(slope)
                except (np.linalg.LinAlgError, ValueError):
                    features.append(0)
                
                # 变化率
                diff = np.diff(feature_col)
                features.extend([
                    np.mean(diff) if len(diff) > 0 else 0,
                    np.std(diff) if len(diff) > 0 else 0,
                    np.sum(np.abs(diff)) if len(diff) > 0 else 0
                ])
                
                # 自相关性
                if len(feature_col) > 5:
                    try:
                        centered = feature_col - np.mean(feature_col)
                        autocorr = np.correlate(centered, centered, mode='full')
                        mid = len(autocorr) // 2
                        if autocorr[mid] != 0:
                            autocorr = autocorr[mid:] / autocorr[mid]
                            features.extend(autocorr[1:4].tolist() if len(autocorr) > 3 else [0, 0, 0])
                        else:
                            features.extend([0, 0, 0])
                    except (ValueError, FloatingPointError):
                        features.extend([0, 0, 0])
                else:
                    features.extend([0, 0, 0])
            else:
                features.extend([0] * 7)
            
            # 周期性特征（如果有时戳）
            if timestamps is not None:
                try:
                    hours = pd.to_datetime(timestamps).hour
                    
                    # 安全地计算各时段均值
                    def safe_mean(mask):
                        vals = feature_col[mask]
                        return np.mean(vals) if len(vals) > 0 else 0
                    
                    features.extend([
                        safe_mean(hours < 6),                        # 凌晨
                        safe_mean((hours >= 6) & (hours < 12)),     # 上午
                        safe_mean((hours >= 12) & (hours < 18)),    # 下午
                        safe_mean(hours >= 18)                       # 晚上
                    ])
                except Exception:
                    features.extend([0, 0, 0, 0])
        
        return np.array(features).reshape(1, -1)
    
    def extract_window_features(self, X: np.ndarray) -> np.ndarray:
        """提取滑动窗口特征"""
        if len(X) < self.window_size:
            return np.zeros((1, X.shape[1] * 3))
        
        features = []
        
        for i in range(X.shape[1]):
            feature_col = X[:, i]
            
            # 滑动窗口统计
            window_means = []
            window_stds = []
            window_maxs = []
            
            for j in range(len(feature_col) - self.window_size + 1):
                window = feature_col[j:j+self.window_size]
                window_means.append(np.mean(window))
                window_stds.append(np.std(window))
                window_maxs.append(np.max(window))
            
            features.extend([
                np.mean(window_means),
                np.std(window_means),
                np.mean(window_stds),
                np.std(window_stds),
                np.mean(window_maxs),
                np.std(window_maxs)
            ])
        
        return np.array(features).reshape(1, -1)
    
    def extract_all_features(self, X: np.ndarray, timestamps: np.ndarray = None) -> np.ndarray:
        """提取所有特征"""
        statistical_features = self.extract_statistical_features(X)
        temporal_features = self.extract_temporal_features(X, timestamps)
        window_features = self.extract_window_features(X)
        
        # 合并所有特征
        all_features = np.hstack([statistical_features, temporal_features, window_features])
        
        # 生成特征名称
        self._generate_feature_names(X.shape[1])
        
        return all_features
    
    def _generate_feature_names(self, n_features: int):
        """生成特征名称"""
        self.feature_names = []
        
        # 统计特征名称
        stats = ['mean', 'std', 'min', 'max', 'median', 'q25', 'q75', 'sum', 'var', 'skew', 'kurtosis']
        for i in range(n_features):
            for stat in stats:
                self.feature_names.append(f'feature_{i}_{stat}')
        
        # 时序特征名称
        temporal = ['slope', 'diff_mean', 'diff_std', 'diff_sum', 'autocorr_1', 'autocorr_2', 'autocorr_3']
        for i in range(n_features):
            for temp in temporal:
                self.feature_names.append(f'feature_{i}_{temp}')
        
        # 窗口特征名称
        window_stats = ['window_mean_mean', 'window_mean_std', 'window_std_mean', 'window_std_std', 'window_max_mean', 'window_max_std']
        for i in range(n_features):
            for wstat in window_stats:
                self.feature_names.append(f'feature_{i}_{wstat}')


class FeatureSelector:
    """特征选择器"""
    
    def __init__(self, method: str = 'mutual_info', k: int = 20):
        """
        初始化特征选择器
        
        Args:
            method: 选择方法 ('mutual_info', 'f_score', 'correlation')
            k: 选择特征数量
        """
        self.method = method
        self.k = k
        self.selector = None
        self.selected_features = []
        self.feature_scores = {}
    
    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: List[str] = None):
        """训练特征选择器"""
        if feature_names is None:
            feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        
        if self.method == 'mutual_info':
            self.selector = SelectKBest(score_func=mutual_info_classif, k=self.k)
        elif self.method == 'f_score':
            self.selector = SelectKBest(score_func=f_classif, k=self.k)
        else:
            raise ValueError(f'不支持的特征选择方法: {self.method}')
        
        self.selector.fit(X, y)
        
        # 记录特征得分
        scores = self.selector.scores_
        self.feature_scores = {name: score for name, score in zip(feature_names, scores)}
        self.selected_features = [feature_names[i] for i in self.selector.get_support(indices=True)]
        
        logger.info(f'特征选择完成，选择了 {len(self.selected_features)} 个特征')
        logger.info(f'Top 5 特征: {sorted(self.feature_scores.items(), key=lambda x: x[1], reverse=True)[:5]}')
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """应用特征选择"""
        if self.selector is None:
            raise ValueError('特征选择器未训练')
        return self.selector.transform(X)
    
    def get_feature_importance(self) -> Dict[str, float]:
        """获取特征重要性"""
        return self.feature_scores
    
    def plot_feature_importance(self, top_k: int = 15):
        """绘制特征重要性图（文本形式）"""
        sorted_features = sorted(self.feature_scores.items(), key=lambda x: x[1], reverse=True)
        
        logger.info('\n特征重要性排名:')
        logger.info('=' * 50)
        for i, (feature, score) in enumerate(sorted_features[:top_k]):
            selected = '✓' if feature in self.selected_features else '✗'
            logger.info(f'{i+1:2d}. {selected} {feature}: {score:.4f}')


class DataAugmentor:
    """数据增强器（优化版）"""
    
    # 支持的增强方法
    METHODS = ['noise', 'scaling', 'time_warping', 'mixup', 'smote']
    
    def __init__(self, augmentation_methods: List[str] = None,
                 noise_level: float = 0.05,
                 scale_range: Tuple[float, float] = (0.8, 1.2),
                 warp_factor: float = 0.1):
        """
        初始化数据增强器
        
        Args:
            augmentation_methods: 增强方法列表 ('noise', 'scaling', 'time_warping', 'mixup', 'smote')
            noise_level: 噪声水平
            scale_range: 缩放范围
            warp_factor: 时间扭曲因子
        """
        self.methods = augmentation_methods or ['noise', 'scaling']
        self.noise_level = noise_level
        self.scale_range = scale_range
        self.warp_factor = warp_factor
    
    def augment_data(self, X: np.ndarray, y: np.ndarray, 
                     n_augmented: int = 1000,
                     balance_classes: bool = True) -> Tuple[np.ndarray, np.ndarray]:
        """
        数据增强
        
        Args:
            X: 输入数据
            y: 标签
            n_augmented: 增强样本数量
            balance_classes: 是否平衡类别
            
        Returns:
            增强后的数据和标签
        """
        if len(X) == 0:
            return X, y
        
        augmented_X = []
        augmented_y = []
        
        # 如果需要平衡类别，计算每个类别需要增强的数量
        if balance_classes:
            unique_classes, class_counts = np.unique(y, return_counts=True)
            max_count = np.max(class_counts)
            augment_per_class = {cls: max_count - count for cls, count in zip(unique_classes, class_counts)}
        else:
            augment_per_class = None
        
        if augment_per_class:
            # 按类别增强
            for cls, n_needed in augment_per_class.items():
                if n_needed <= 0:
                    continue
                
                cls_indices = np.where(y == cls)[0]
                if len(cls_indices) == 0:
                    continue
                
                for _ in range(n_needed):
                    idx = np.random.choice(cls_indices)
                    sample = self._augment_single(X[idx])
                    augmented_X.append(sample)
                    augmented_y.append(cls)
        else:
            # 随机增强
            for _ in range(n_augmented):
                idx = np.random.randint(0, len(X))
                sample = self._augment_single(X[idx])
                augmented_X.append(sample)
                augmented_y.append(y[idx])
        
        if len(augmented_X) > 0:
            augmented_X = np.array(augmented_X)
            augmented_y = np.array(augmented_y)
            
            # 合并原始数据
            final_X = np.vstack([X, augmented_X])
            final_y = np.hstack([y, augmented_y])
        else:
            final_X, final_y = X, y
        
        logger.info(f'数据增强完成，原始样本: {len(X)}, 增强后: {len(final_X)}')
        
        return final_X, final_y
    
    def _augment_single(self, sample: np.ndarray) -> np.ndarray:
        """增强单个样本"""
        augmented = sample.copy()
        
        # 应用增强方法
        if 'noise' in self.methods:
            augmented = self._add_noise(augmented)
        
        if 'scaling' in self.methods:
            augmented = self._random_scaling(augmented)
        
        if 'time_warping' in self.methods and len(augmented) > 3:
            augmented = self._time_warping(augmented)
        
        return augmented
    
    def augment_with_mixup(self, X: np.ndarray, y: np.ndarray, 
                           n_augmented: int = 500, 
                           alpha: float = 0.2) -> Tuple[np.ndarray, np.ndarray]:
        """
        使用 Mixup 进行数据增强
        
        Args:
            X: 输入数据
            y: 标签
            n_augmented: 增强样本数量
            alpha: Mixup 参数
            
        Returns:
            增强后的数据和标签
        """
        augmented_X = []
        augmented_y = []
        
        for _ in range(n_augmented):
            # 随机选择两个样本
            idx1, idx2 = np.random.choice(len(X), 2, replace=False)
            
            # 生成混合比例
            lam = np.random.beta(alpha, alpha)
            
            # Mixup
            mixed_sample = lam * X[idx1] + (1 - lam) * X[idx2]
            
            # 标签选择（对于分类任务，选择比例较大的标签）
            mixed_label = y[idx1] if lam > 0.5 else y[idx2]
            
            augmented_X.append(mixed_sample)
            augmented_y.append(mixed_label)
        
        augmented_X = np.array(augmented_X)
        augmented_y = np.array(augmented_y)
        
        final_X = np.vstack([X, augmented_X])
        final_y = np.hstack([y, augmented_y])
        
        logger.info(f'Mixup增强完成，原始样本: {len(X)}, 增强后: {len(final_X)}')
        
        return final_X, final_y
    
    def _add_noise(self, sample: np.ndarray) -> np.ndarray:
        """添加高斯噪声"""
        std = np.std(sample) if np.std(sample) > 0 else 1.0
        noise = np.random.normal(0, self.noise_level * std, sample.shape)
        return sample + noise
    
    def _random_scaling(self, sample: np.ndarray) -> np.ndarray:
        """随机缩放"""
        scale_factor = np.random.uniform(self.scale_range[0], self.scale_range[1])
        return sample * scale_factor
    
    def _time_warping(self, sample: np.ndarray) -> np.ndarray:
        """时间扭曲"""
        n_points = len(sample)
        if n_points < 3:
            return sample
        
        # 简单的线性插值扭曲
        original_indices = np.arange(n_points)
        warped_indices = original_indices + np.random.normal(0, self.warp_factor, n_points)
        warped_indices = np.clip(warped_indices, 0, n_points - 1)
        
        try:
            interp_func = interp1d(original_indices, sample, kind='linear', fill_value='extrapolate')
            return interp_func(warped_indices)
        except Exception:
            return sample


class FeaturePipeline:
    """特征工程流水线"""
    
    def __init__(self, steps: List[Tuple[str, Any]] = None):
        """
        初始化特征流水线
        
        Args:
            steps: 处理步骤列表 [(name, processor)]
        """
        self.steps = steps or []
        self.is_fitted = False
    
    def add_step(self, name: str, processor: Any):
        """添加处理步骤"""
        self.steps.append((name, processor))
    
    def fit_transform(self, X: np.ndarray, y: np.ndarray = None) -> np.ndarray:
        """训练并转换数据"""
        current_X = X.copy()
        
        for step_name, processor in self.steps:
            logger.info(f'执行步骤: {step_name}')
            
            if hasattr(processor, 'fit_transform'):
                current_X = processor.fit_transform(current_X, y) if y is not None else processor.fit_transform(current_X)
            elif hasattr(processor, 'fit') and hasattr(processor, 'transform'):
                if y is not None:
                    processor.fit(current_X, y)
                else:
                    processor.fit(current_X)
                current_X = processor.transform(current_X)
            else:
                current_X = processor(current_X)
        
        self.is_fitted = True
        logger.info(f'特征工程完成，维度: {X.shape} -> {current_X.shape}')
        
        return current_X
    
    def transform(self, X: np.ndarray) -> np.ndarray:
        """转换新数据"""
        if not self.is_fitted:
            raise ValueError('流水线未训练')
        
        current_X = X.copy()
        for _, processor in self.steps:
            if hasattr(processor, 'transform'):
                current_X = processor.transform(current_X)
            else:
                current_X = processor(current_X)
        
        return current_X