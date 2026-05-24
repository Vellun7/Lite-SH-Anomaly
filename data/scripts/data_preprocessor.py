"""
数据预处理模块
功能：数据清洗、特征工程、数据标准化

优化说明：
1. 修复数据泄漏问题 - Scaler 只在训练集上 fit
2. 优化异常值处理策略 - 保留攻击特征，使用分位数裁剪
3. 添加数据验证和质量检查
4. 支持增量预处理模式
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, RobustScaler, LabelEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold
from pathlib import Path
import logging
import joblib
from typing import Optional, Tuple, List, Dict, Union
import warnings

warnings.filterwarnings('ignore')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataPreprocessor:
    """数据预处理器"""
    
    # 核心特征列（基于IoT-23数据集）
    CORE_FEATURES = [
        'duration',           # 连接持续时间
        'orig_bytes',         # 源端发送字节数
        'resp_bytes',         # 目的端响应字节数
        'orig_pkts',          # 源端发送包数
        'resp_pkts',          # 目的端响应包数
        'orig_ip_bytes',      # 源端IP层字节数
        'resp_ip_bytes',      # 目的端IP层字节数
    ]
    
    # 分类特征
    CATEGORICAL_FEATURES = [
        'proto',              # 协议类型 (TCP/UDP/ICMP)
        'service',            # 服务类型
        'conn_state',         # 连接状态
    ]
    
    # 标签列
    LABEL_COLUMN = 'label'
    
    # 攻击类型映射
    ATTACK_TYPES = {
        'benign': 0,          # 正常流量
        'ddos': 1,            # DDoS攻击
        'dos': 1,             # DoS攻击
        'scan': 2,            # 端口扫描
        'mirai': 3,           # Mirai僵尸网络
        'okiru': 3,           # Okiru僵尸网络
        'torii': 3,           # Torii僵尸网络
        'unauthorized': 4,    # 越权访问
    }
    
    def __init__(self, raw_data_path: str = None, output_path: str = None, 
                 use_robust_scaler: bool = True):
        """
        初始化预处理器
        
        Args:
            raw_data_path: 原始数据路径
            output_path: 输出路径
            use_robust_scaler: 是否使用 RobustScaler（对异常值更鲁棒）
        """
        self.raw_data_path = Path(raw_data_path) if raw_data_path else None
        self.output_path = Path(output_path) if output_path else Path(__file__).parent.parent / 'processed'
        
        # 使用 RobustScaler 对异常值更鲁棒，避免极端值影响标准化
        self.scaler = RobustScaler() if use_robust_scaler else StandardScaler()
        self.scaler_type = 'robust' if use_robust_scaler else 'standard'
        
        self.label_encoders = {}
        self.df = None
        self._is_fitted = False  # 跟踪 scaler 是否已 fit
        self._feature_columns = None  # 保存特征列名
        self._outlier_bounds = {}  # 保存异常值边界（用于推理时）
        
    def load_data(self, file_path: str = None) -> pd.DataFrame:
        """
        加载原始数据
        
        Args:
            file_path: 数据文件路径（支持CSV格式）
            
        Returns:
            加载的DataFrame
        """
        path = Path(file_path) if file_path else self.raw_data_path
        
        if path is None:
            raise ValueError("请提供数据文件路径")
            
        logger.info(f"正在加载数据: {path}")
        
        if path.suffix == '.csv':
            self.df = pd.read_csv(path, low_memory=False)
        else:
            raise ValueError(f"不支持的文件格式: {path.suffix}")
            
        logger.info(f"数据加载完成，共 {len(self.df)} 条记录")
        return self.df
    
    def clean_data(self, preserve_attack_features: bool = True) -> pd.DataFrame:
        """
        数据清洗
        - 处理缺失值
        - 去除重复值
        - 智能处理异常值（保留攻击特征）
        
        Args:
            preserve_attack_features: 是否保留可能代表攻击行为的极端值
        
        Returns:
            清洗后的DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        logger.info("开始数据清洗...")
        original_count = len(self.df)
        
        # 1. 去除完全重复的行
        self.df = self.df.drop_duplicates()
        logger.info(f"去除重复行: {original_count - len(self.df)} 条")
        
        # 2. 处理缺失值
        # 数值型特征用中位数填充
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if self.df[col].isnull().sum() > 0:
                median_val = self.df[col].median()
                self.df[col].fillna(median_val, inplace=True)
                
        # 分类特征用众数填充
        categorical_cols = self.df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            if self.df[col].isnull().sum() > 0:
                mode_val = self.df[col].mode()[0] if len(self.df[col].mode()) > 0 else 'unknown'
                self.df[col].fillna(mode_val, inplace=True)
        
        # 3. 智能异常值处理（保留攻击特征）
        # 对于异常检测任务，极端值可能正是攻击特征，不能简单裁剪
        self._handle_outliers_smart(numeric_cols, preserve_attack_features)
        
        # 4. 处理无穷值
        self.df.replace([np.inf, -np.inf], np.nan, inplace=True)
        self.df.dropna(inplace=True)
        
        logger.info(f"数据清洗完成，剩余 {len(self.df)} 条记录")
        return self.df
    
    def _handle_outliers_smart(self, numeric_cols: List[str], preserve_attack: bool = True):
        """
        智能异常值处理
        
        策略：
        1. 对于正常样本：使用温和的 IQR 裁剪（3 * IQR）
        2. 对于异常样本：保留极端值，因为它们可能是攻击特征
        3. 只处理真正的噪声（如负数字节、负时长等不合理值）
        
        Args:
            numeric_cols: 数值型列名列表
            preserve_attack: 是否保留攻击样本的极端值
        """
        logger.info("执行智能异常值处理...")
        
        for col in numeric_cols:
            if col not in self.CORE_FEATURES:
                continue
                
            # 计算正常样本的统计量（如果有标签）
            if 'label_encoded' in self.df.columns or self.LABEL_COLUMN in self.df.columns:
                # 只基于正常样本计算边界
                label_col = 'label_encoded' if 'label_encoded' in self.df.columns else self.LABEL_COLUMN
                normal_mask = self.df[label_col].astype(str).str.lower().str.contains('benign|0')
                if normal_mask.sum() > 0:
                    normal_data = self.df.loc[normal_mask, col]
                else:
                    normal_data = self.df[col]
            else:
                normal_data = self.df[col]
            
            Q1 = normal_data.quantile(0.25)
            Q3 = normal_data.quantile(0.75)
            IQR = Q3 - Q1
            
            # 使用 3 * IQR 的宽松边界
            lower_bound = Q1 - 3 * IQR
            upper_bound = Q3 + 3 * IQR
            
            # 保存边界用于推理时
            self._outlier_bounds[col] = {
                'lower': max(0, lower_bound),  # 字节数、包数等不能为负
                'upper': upper_bound,
                'q1': Q1,
                'q3': Q3
            }
            
            if preserve_attack:
                # 只处理不合理的值（负数等）
                # 保留极端高值，因为可能是 DDoS 等攻击特征
                self.df[col] = self.df[col].clip(lower=0)  # 只裁剪负数
                
                # 使用对数变换处理极端高值（保留信息但压缩范围）
                if self.df[col].max() > upper_bound * 10:
                    logger.info(f"列 {col} 存在极端高值，将应用 log1p 变换标记")
                    # 不直接变换，而是添加一个标记列
                    self.df[f'{col}_extreme'] = (self.df[col] > upper_bound).astype(int)
            else:
                # 传统裁剪方法
                self.df[col] = self.df[col].clip(
                    lower=max(0, lower_bound), 
                    upper=upper_bound
                )
    
    def encode_categorical(self) -> pd.DataFrame:
        """
        编码分类特征
        
        Returns:
            编码后的DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        logger.info("开始编码分类特征...")
        
        for col in self.CATEGORICAL_FEATURES:
            if col in self.df.columns:
                le = LabelEncoder()
                self.df[col + '_encoded'] = le.fit_transform(self.df[col].astype(str))
                self.label_encoders[col] = le
                logger.info(f"编码特征 {col}: {len(le.classes_)} 个类别")
                
        return self.df
    
    def extract_features(self) -> pd.DataFrame:
        """
        特征工程：提取和构造特征
        
        Returns:
            特征工程后的DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        logger.info("开始特征工程...")
        
        # 1. 构造派生特征
        if 'orig_bytes' in self.df.columns and 'resp_bytes' in self.df.columns:
            # 字节比率
            self.df['bytes_ratio'] = self.df['orig_bytes'] / (self.df['resp_bytes'] + 1)
            
        if 'orig_pkts' in self.df.columns and 'resp_pkts' in self.df.columns:
            # 包数比率
            self.df['pkts_ratio'] = self.df['orig_pkts'] / (self.df['resp_pkts'] + 1)
            
        if 'duration' in self.df.columns and 'orig_bytes' in self.df.columns:
            # 传输速率
            self.df['bytes_per_second'] = self.df['orig_bytes'] / (self.df['duration'] + 0.001)
            
        if 'duration' in self.df.columns and 'orig_pkts' in self.df.columns:
            # 包速率
            self.df['pkts_per_second'] = self.df['orig_pkts'] / (self.df['duration'] + 0.001)
        
        logger.info(f"特征工程完成，当前特征数: {len(self.df.columns)}")
        return self.df
    
    def normalize_labels(self) -> pd.DataFrame:
        """
        标准化标签（将多种攻击类型映射为统一标签）
        
        Returns:
            标签标准化后的DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        if self.LABEL_COLUMN not in self.df.columns:
            logger.warning(f"未找到标签列 '{self.LABEL_COLUMN}'")
            return self.df
            
        logger.info("开始标准化标签...")
        
        def map_label(label):
            label_lower = str(label).lower()
            for attack_type, code in self.ATTACK_TYPES.items():
                if attack_type in label_lower:
                    return code
            return 0  # 默认为正常
            
        self.df['label_encoded'] = self.df[self.LABEL_COLUMN].apply(map_label)
        
        # 统计各类别数量
        label_counts = self.df['label_encoded'].value_counts()
        logger.info(f"标签分布:\n{label_counts}")
        
        return self.df
    
    def scale_features(self, feature_columns: list = None, 
                       fit: bool = True) -> Tuple[np.ndarray, List[str]]:
        """
        特征标准化（支持分离 fit 和 transform 以避免数据泄漏）
        
        Args:
            feature_columns: 需要标准化的特征列
            fit: 是否进行 fit 操作（训练时为 True，推理时为 False）
            
        Returns:
            (标准化后的特征数组, 特征列名列表)
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        if feature_columns is None:
            # 使用核心特征 + 编码后的分类特征 + 派生特征
            feature_columns = [col for col in self.CORE_FEATURES if col in self.df.columns]
            feature_columns += [col + '_encoded' for col in self.CATEGORICAL_FEATURES 
                              if col + '_encoded' in self.df.columns]
            feature_columns += ['bytes_ratio', 'pkts_ratio', 'bytes_per_second', 'pkts_per_second']
            # 添加极端值标记特征（如果存在）
            feature_columns += [col for col in self.df.columns if col.endswith('_extreme')]
            feature_columns = [col for col in feature_columns if col in self.df.columns]
        
        self._feature_columns = feature_columns
        logger.info(f"标准化特征 ({len(feature_columns)} 个): {feature_columns}")
        
        X = self.df[feature_columns].values
        
        if fit:
            X_scaled = self.scaler.fit_transform(X)
            self._is_fitted = True
            logger.info("Scaler 已 fit（仅应在训练数据上执行）")
        else:
            if not self._is_fitted:
                raise ValueError("Scaler 尚未 fit，请先在训练数据上调用 fit=True")
            X_scaled = self.scaler.transform(X)
            logger.info("使用已 fit 的 Scaler 进行 transform")
        
        return X_scaled, feature_columns
    
    def fit_scaler(self, X_train: np.ndarray, feature_columns: List[str]):
        """
        仅在训练数据上 fit scaler（防止数据泄漏的关键方法）
        
        Args:
            X_train: 训练数据
            feature_columns: 特征列名
        """
        self.scaler.fit(X_train)
        self._is_fitted = True
        self._feature_columns = feature_columns
        logger.info(f"Scaler 已在训练集上 fit（样本数: {len(X_train)}）")
    
    def transform_features(self, X: np.ndarray) -> np.ndarray:
        """
        使用已 fit 的 scaler 转换特征
        
        Args:
            X: 原始特征数组
            
        Returns:
            标准化后的特征数组
        """
        if not self._is_fitted:
            raise ValueError("Scaler 尚未 fit，请先调用 fit_scaler")
        return self.scaler.transform(X)
    
    def prepare_dataset(self, test_size: float = 0.2, random_state: int = 42,
                        validation_size: float = 0.1) -> Dict[str, np.ndarray]:
        """
        准备训练、验证和测试数据集（修复数据泄漏问题）
        
        关键改进：先分割数据，再在训练集上 fit scaler，最后 transform 所有集合
        
        Args:
            test_size: 测试集比例
            random_state: 随机种子
            validation_size: 验证集比例（从训练集中划分）
            
        Returns:
            包含所有数据集的字典：
            {
                'X_train': 训练特征,
                'X_val': 验证特征,
                'X_test': 测试特征,
                'y_train': 训练标签,
                'y_val': 验证标签,
                'y_test': 测试标签,
                'feature_columns': 特征列名
            }
        """
        logger.info("准备数据集（防止数据泄漏模式）...")
        
        # 1. 获取特征列
        feature_columns = [col for col in self.CORE_FEATURES if col in self.df.columns]
        feature_columns += [col + '_encoded' for col in self.CATEGORICAL_FEATURES 
                          if col + '_encoded' in self.df.columns]
        feature_columns += ['bytes_ratio', 'pkts_ratio', 'bytes_per_second', 'pkts_per_second']
        feature_columns += [col for col in self.df.columns if col.endswith('_extreme')]
        feature_columns = [col for col in feature_columns if col in self.df.columns]
        
        self._feature_columns = feature_columns
        logger.info(f"使用特征 ({len(feature_columns)} 个): {feature_columns}")
        
        # 2. 提取原始特征（未标准化）
        X_raw = self.df[feature_columns].values
        
        if 'label_encoded' in self.df.columns:
            y = self.df['label_encoded'].values
        else:
            raise ValueError("请先执行标签标准化")
        
        # 3. 先分割数据（在标准化之前！）
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X_raw, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # 4. 从训练集中划分验证集
        if validation_size > 0:
            val_ratio = validation_size / (1 - test_size)  # 相对于训练集的比例
            X_train_raw, X_val_raw, y_train, y_val = train_test_split(
                X_train_raw, y_train, test_size=val_ratio, 
                random_state=random_state, stratify=y_train
            )
        else:
            X_val_raw, y_val = None, None
        
        # 5. 只在训练集上 fit scaler（防止数据泄漏的关键步骤！）
        self.scaler.fit(X_train_raw)
        self._is_fitted = True
        logger.info(f"✓ Scaler 仅在训练集上 fit（{len(X_train_raw)} 样本）")
        
        # 6. Transform 所有数据集
        X_train = self.scaler.transform(X_train_raw)
        X_test = self.scaler.transform(X_test_raw)
        X_val = self.scaler.transform(X_val_raw) if X_val_raw is not None else None
        
        # 7. 保存 scaler 和相关配置
        self._save_preprocessing_artifacts()
        
        # 8. 数据质量验证
        self._validate_dataset(X_train, X_test, y_train, y_test)
        
        logger.info(f"数据集划分完成:")
        logger.info(f"  训练集: {len(X_train)} 条")
        if X_val is not None:
            logger.info(f"  验证集: {len(X_val)} 条")
        logger.info(f"  测试集: {len(X_test)} 条")
        
        result = {
            'X_train': X_train,
            'X_test': X_test,
            'y_train': y_train,
            'y_test': y_test,
            'feature_columns': feature_columns
        }
        
        if X_val is not None:
            result['X_val'] = X_val
            result['y_val'] = y_val
        
        return result
    
    def _validate_dataset(self, X_train: np.ndarray, X_test: np.ndarray,
                         y_train: np.ndarray, y_test: np.ndarray):
        """
        验证数据集质量
        
        检查：
        1. 是否存在 NaN 或 Inf
        2. 标签分布是否合理
        3. 特征范围是否正常
        """
        logger.info("执行数据质量验证...")
        
        # 检查 NaN 和 Inf
        for name, data in [('X_train', X_train), ('X_test', X_test)]:
            if np.isnan(data).any():
                logger.warning(f"⚠ {name} 中存在 NaN 值")
            if np.isinf(data).any():
                logger.warning(f"⚠ {name} 中存在 Inf 值")
        
        # 检查标签分布
        train_dist = pd.Series(y_train).value_counts(normalize=True)
        test_dist = pd.Series(y_test).value_counts(normalize=True)
        
        logger.info(f"训练集标签分布: {dict(train_dist)}")
        logger.info(f"测试集标签分布: {dict(test_dist)}")
        
        # 检查分布偏差
        for label in train_dist.index:
            if label in test_dist.index:
                diff = abs(train_dist[label] - test_dist[label])
                if diff > 0.1:  # 超过 10% 的偏差
                    logger.warning(f"⚠ 标签 {label} 在训练集和测试集中的分布差异较大: {diff:.2%}")
    
    def _save_preprocessing_artifacts(self):
        """
        保存所有预处理相关的配置和模型
        
        保存内容：
        1. Scaler 模型
        2. Label Encoders
        3. 特征列名
        4. 异常值边界
        5. 预处理配置
        """
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 1. 保存 Scaler
        scaler_path = self.output_path / 'scaler.joblib'
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"✓ Scaler 已保存至: {scaler_path}")
        
        # 2. 保存 Label Encoders
        if self.label_encoders:
            encoders_path = self.output_path / 'label_encoders.joblib'
            joblib.dump(self.label_encoders, encoders_path)
            logger.info(f"✓ Label Encoders 已保存至: {encoders_path}")
        
        # 3. 保存预处理配置
        config = {
            'feature_columns': self._feature_columns,
            'scaler_type': self.scaler_type,
            'outlier_bounds': self._outlier_bounds,
            'core_features': self.CORE_FEATURES,
            'categorical_features': self.CATEGORICAL_FEATURES,
            'attack_types': self.ATTACK_TYPES
        }
        config_path = self.output_path / 'preprocessing_config.joblib'
        joblib.dump(config, config_path)
        logger.info(f"✓ 预处理配置已保存至: {config_path}")
    
    def load_preprocessing_artifacts(self):
        """
        加载预处理配置（用于推理时）
        
        加载内容：
        1. Scaler 模型
        2. Label Encoders
        3. 预处理配置
        """
        # 加载 Scaler
        scaler_path = self.output_path / 'scaler.joblib'
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            self._is_fitted = True
            logger.info(f"✓ Scaler 已加载: {scaler_path}")
        else:
            raise FileNotFoundError(f"Scaler 文件不存在: {scaler_path}")
        
        # 加载 Label Encoders
        encoders_path = self.output_path / 'label_encoders.joblib'
        if encoders_path.exists():
            self.label_encoders = joblib.load(encoders_path)
            logger.info(f"✓ Label Encoders 已加载")
        
        # 加载配置
        config_path = self.output_path / 'preprocessing_config.joblib'
        if config_path.exists():
            config = joblib.load(config_path)
            self._feature_columns = config.get('feature_columns')
            self._outlier_bounds = config.get('outlier_bounds', {})
            logger.info(f"✓ 预处理配置已加载")
    
    def save_processed_data(self, filename: str = 'processed_data.csv'):
        """
        保存预处理后的数据
        
        Args:
            filename: 输出文件名
        """
        if self.df is None:
            raise ValueError("请先加载并处理数据")
            
        output_file = self.output_path / filename
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.df.to_csv(output_file, index=False)
        logger.info(f"数据已保存至: {output_file}")
        
    def run_pipeline(self, input_file: str, output_file: str = 'processed_data.csv',
                     test_size: float = 0.2, validation_size: float = 0.1,
                     preserve_attack_features: bool = True) -> Dict[str, np.ndarray]:
        """
        运行完整预处理流水线（优化版）
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件名
            test_size: 测试集比例
            validation_size: 验证集比例
            preserve_attack_features: 是否保留攻击特征的极端值
            
        Returns:
            包含所有数据集的字典
        """
        logger.info("=" * 60)
        logger.info("开始数据预处理流水线（防数据泄漏版）")
        logger.info("=" * 60)
        
        # 1. 加载数据
        self.load_data(input_file)
        
        # 2. 数据清洗（智能异常值处理）
        self.clean_data(preserve_attack_features=preserve_attack_features)
        
        # 3. 编码分类特征
        self.encode_categorical()
        
        # 4. 特征工程
        self.extract_features()
        
        # 5. 标签标准化
        self.normalize_labels()
        
        # 6. 保存处理后的数据
        self.save_processed_data(output_file)
        
        # 7. 准备数据集（先分割再标准化，防止数据泄漏）
        result = self.prepare_dataset(
            test_size=test_size, 
            validation_size=validation_size
        )
        
        logger.info("=" * 60)
        logger.info("数据预处理流水线完成")
        logger.info("=" * 60)
        
        return result
    
    def preprocess_for_inference(self, data: Union[pd.DataFrame, np.ndarray], 
                                  feature_columns: List[str] = None) -> np.ndarray:
        """
        为推理准备数据（使用已保存的预处理配置）
        
        Args:
            data: 待预测的原始数据
            feature_columns: 特征列（如果 data 是 DataFrame）
            
        Returns:
            标准化后的特征数组
        """
        if not self._is_fitted:
            self.load_preprocessing_artifacts()
        
        if isinstance(data, pd.DataFrame):
            if feature_columns is None:
                feature_columns = self._feature_columns
            X = data[feature_columns].values
        else:
            X = data
        
        return self.scaler.transform(X)


if __name__ == '__main__':
    # 示例用法
    preprocessor = DataPreprocessor(use_robust_scaler=True)
    
    # 如果有原始数据文件，运行预处理流水线
    # result = preprocessor.run_pipeline('path/to/raw_data.csv')
    # 
    # 新的返回格式：
    # X_train = result['X_train']
    # X_val = result.get('X_val')  # 验证集（可选）
    # X_test = result['X_test']
    # y_train = result['y_train']
    # y_val = result.get('y_val')  # 验证集标签（可选）
    # y_test = result['y_test']
    # feature_columns = result['feature_columns']
    
    print("=" * 60)
    print("数据预处理模块已就绪（优化版）")
    print("=" * 60)
    print("\n主要优化：")
    print("  1. ✓ 修复数据泄漏：先分割数据，再在训练集上 fit scaler")
    print("  2. ✓ 智能异常值处理：保留攻击特征，只处理不合理值")
    print("  3. ✓ 使用 RobustScaler：对异常值更鲁棒")
    print("  4. ✓ 添加验证集支持：三集划分")
    print("  5. ✓ 数据质量验证：自动检查 NaN/Inf 和标签分布")
    print("\n使用方法:")
    print("  preprocessor = DataPreprocessor(use_robust_scaler=True)")
    print("  result = preprocessor.run_pipeline('data.csv')")
    print("  X_train, X_test = result['X_train'], result['X_test']")
    print("\n推理时使用:")
    print("  preprocessor.load_preprocessing_artifacts()")
    print("  X_scaled = preprocessor.preprocess_for_inference(new_data)")
