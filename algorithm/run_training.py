"""
模型训练与评估运行脚本（优化版）
功能：训练所有模型、评估性能、生成对比报告

优化内容：
1. 修复变量未定义BUG
2. 完善训练流程
3. 添加训练进度和时间统计
4. 增强错误处理
5. 支持命令行参数配置
6. 添加训练配置管理
"""

import sys
import numpy as np
import os
from pathlib import Path
import joblib
import time
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import warnings

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from algorithm.training.isolation_forest import LightweightIsolationForest
from algorithm.training.autoencoder import LightweightAutoEncoder, EnhancedLightweightAutoEncoder
from algorithm.training.baseline_models import BaselineKNN, BaselineSVM
from algorithm.evaluation.evaluator import ModelEvaluator
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / 'algorithm' / 'training.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 忽略一些常见警告
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)


# =============================================================================
# 配置管理
# =============================================================================

@dataclass
class TrainingConfig:
    """训练配置数据类"""
    # 数据配置
    data_path: Path = field(default_factory=lambda: project_root / 'data' / 'processed' / 'train_test_data.npz')
    
    # 孤立森林配置
    if_n_estimators: int = 100
    if_max_depth: int = 10
    if_max_samples: int = 512
    if_contamination: float = 0.2
    
    # 自编码器配置
    ae_hidden_dim: int = 4
    ae_latent_dim: int = 2
    ae_epochs: int = 50
    ae_batch_size: int = 64
    ae_learning_rate: float = 0.001
    ae_early_stopping: bool = True
    ae_patience: int = 10
    
    # 增强自编码器配置
    enhanced_ae_hidden_dim: int = 8
    enhanced_ae_latent_dim: int = 4
    enhanced_ae_epochs: int = 80
    enhanced_ae_batch_size: int = 64
    
    # 基线模型配置
    knn_n_neighbors: int = 5
    svm_kernel: str = 'rbf'
    svm_c: float = 1.0
    
    # 特征选择配置
    feature_selection_method: str = 'mutual_info'
    feature_selection_k: int = 20
    
    # 输出配置
    output_path: Path = field(default_factory=lambda: project_root / 'algorithm' / 'models')
    evaluation_path: Path = field(default_factory=lambda: project_root / 'algorithm' / 'evaluation')
    
    # 训练选项
    train_baseline: bool = True
    train_enhanced: bool = True
    train_ensemble: bool = True
    train_optimized: bool = True
    test_incremental: bool = False  # 默认关闭增量学习测试
    
    def __post_init__(self):
        """初始化后处理"""
        self.output_path = Path(self.output_path)
        self.evaluation_path = Path(self.evaluation_path)
        self.data_path = Path(self.data_path)


class Timer:
    """计时器上下文管理器"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.elapsed = 0
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, *args):
        self.end_time = time.time()
        self.elapsed = self.end_time - self.start_time
        if self.name:
            logger.info(f"  ⏱️ {self.name} 耗时: {self.elapsed:.2f}秒")
            
    def format_time(self) -> str:
        """格式化时间"""
        if self.elapsed < 60:
            return f"{self.elapsed:.2f}秒"
        elif self.elapsed < 3600:
            minutes = self.elapsed // 60
            seconds = self.elapsed % 60
            return f"{int(minutes)}分{seconds:.1f}秒"
        else:
            hours = self.elapsed // 3600
            minutes = (self.elapsed % 3600) // 60
            return f"{int(hours)}小时{int(minutes)}分"


class TrainingProgress:
    """训练进度跟踪器"""
    
    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0
        self.step_times: Dict[str, float] = {}
        self.start_time = time.time()
        
    def step(self, name: str, elapsed: float):
        """记录步骤"""
        self.current_step += 1
        self.step_times[name] = elapsed
        progress = self.current_step / self.total_steps * 100
        logger.info(f"📊 进度: [{self.current_step}/{self.total_steps}] {progress:.1f}%")
        
    def summary(self) -> str:
        """生成进度摘要"""
        total_time = time.time() - self.start_time
        summary_lines = [
            "\n" + "=" * 60,
            "训练时间统计",
            "=" * 60,
        ]
        for name, elapsed in self.step_times.items():
            summary_lines.append(f"  {name}: {elapsed:.2f}秒")
        summary_lines.append(f"  总耗时: {total_time:.2f}秒")
        return "\n".join(summary_lines)


# =============================================================================
# 数据加载
# =============================================================================

def load_data(config: TrainingConfig = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """
    加载预处理后的数据
    
    Args:
        config: 训练配置，如果为None则使用默认配置
        
    Returns:
        Tuple[X_train, X_test, y_train, y_test, feature_names]
        
    Raises:
        FileNotFoundError: 数据文件不存在
        ValueError: 数据格式错误
    """
    if config is None:
        config = TrainingConfig()
        
    data_path = config.data_path
    
    if not data_path.exists():
        raise FileNotFoundError(
            f"数据文件不存在: {data_path}\n"
            f"请先运行数据预处理流水线:\n"
            f"  python data/scripts/data_preprocessor.py"
        )
    
    try:
        data = np.load(data_path)
        
        X_train = data['X_train']
        X_test = data['X_test']
        y_train = data['y_train']
        y_test = data['y_test']
        
    except Exception as e:
        raise ValueError(f"数据加载失败: {e}")
    
    # 数据验证
    if len(X_train) == 0 or len(X_test) == 0:
        raise ValueError("训练集或测试集为空")
        
    if X_train.shape[1] != X_test.shape[1]:
        raise ValueError(f"训练集和测试集特征维度不一致: {X_train.shape[1]} vs {X_test.shape[1]}")
    
    logger.info(f"📂 数据加载完成:")
    logger.info(f"  训练集: {X_train.shape} (正常: {np.sum(y_train==0)}, 异常: {np.sum(y_train==1)})")
    logger.info(f"  测试集: {X_test.shape} (正常: {np.sum(y_test==0)}, 异常: {np.sum(y_test==1)})")
    
    # 加载特征名称
    feature_file = project_root / 'data' / 'processed' / 'feature_columns.txt'
    if feature_file.exists():
        with open(feature_file, 'r') as f:
            feature_names = [line.strip() for line in f.readlines()]
        logger.info(f"  特征数: {len(feature_names)}")
    else:
        feature_names = [f'feature_{i}' for i in range(X_train.shape[1])]
        logger.warning(f"  特征名文件不存在，使用默认名称")
        
    return X_train, X_test, y_train, y_test, feature_names


# =============================================================================
# 模型训练函数
# =============================================================================

def train_isolation_forest(
    X_train: np.ndarray, 
    y_train: np.ndarray, 
    feature_names: List[str],
    config: TrainingConfig = None
) -> LightweightIsolationForest:
    """
    训练轻量化孤立森林
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        feature_names: 特征名称列表
        config: 训练配置
        
    Returns:
        训练好的模型
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("🌲 训练轻量化孤立森林")
    logger.info("=" * 60)
    
    # 孤立森林是无监督算法，仅使用正常样本训练效果更好
    normal_mask = y_train == 0
    X_train_normal = X_train[normal_mask]
    
    logger.info(f"  使用正常样本训练: {len(X_train_normal)} 条")
    logger.info(f"  参数: n_estimators={config.if_n_estimators}, max_depth={config.if_max_depth}, "
                f"max_samples={config.if_max_samples}, contamination={config.if_contamination}")
    
    model = LightweightIsolationForest(
        n_estimators=config.if_n_estimators,
        max_depth=config.if_max_depth,
        max_samples=config.if_max_samples,
        contamination=config.if_contamination
    )
    
    with Timer("孤立森林训练"):
        model.train(X_train_normal, feature_names)
        
    return model


def train_autoencoder(
    X_train: np.ndarray, 
    y_train: np.ndarray, 
    feature_names: List[str],
    config: TrainingConfig = None
) -> LightweightAutoEncoder:
    """
    训练轻量化自编码器
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        feature_names: 特征名称列表
        config: 训练配置
        
    Returns:
        训练好的模型
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("🔧 训练轻量化自编码器")
    logger.info("=" * 60)
    
    # 仅使用正常样本训练自编码器
    normal_mask = y_train == 0
    X_train_normal = X_train[normal_mask]
    
    logger.info(f"  使用正常样本训练: {len(X_train_normal)} 条")
    logger.info(f"  参数: hidden_dim={config.ae_hidden_dim}, latent_dim={config.ae_latent_dim}, "
                f"epochs={config.ae_epochs}, batch_size={config.ae_batch_size}")
    
    model = LightweightAutoEncoder(
        input_dim=X_train.shape[1],
        hidden_dim=config.ae_hidden_dim,
        latent_dim=config.ae_latent_dim,
        epochs=config.ae_epochs,
        batch_size=config.ae_batch_size,
        learning_rate=config.ae_learning_rate,
        early_stopping=config.ae_early_stopping,
        patience=config.ae_patience
    )
    
    with Timer("自编码器训练"):
        model.train(X_train_normal, feature_names=feature_names)
        
    return model


def train_enhanced_autoencoder(
    X_train: np.ndarray, 
    y_train: np.ndarray, 
    feature_names: List[str] = None,
    config: TrainingConfig = None
) -> EnhancedLightweightAutoEncoder:
    """
    训练增强版自编码器
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        feature_names: 特征名称列表
        config: 训练配置
        
    Returns:
        训练好的模型
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("🚀 训练增强版自编码器")
    logger.info("=" * 60)
    
    # 仅使用正常样本训练
    normal_mask = y_train == 0
    X_train_normal = X_train[normal_mask]
    
    logger.info(f"  使用正常样本训练: {len(X_train_normal)} 条")
    logger.info(f"  参数: hidden_dim={config.enhanced_ae_hidden_dim}, latent_dim={config.enhanced_ae_latent_dim}, "
                f"epochs={config.enhanced_ae_epochs}")
    
    # 数据分割
    from sklearn.model_selection import train_test_split
    X_train_split, X_val_split = train_test_split(
        X_train_normal, test_size=0.2, random_state=42
    )
    
    logger.info(f"  训练/验证分割: {len(X_train_split)}/{len(X_val_split)}")
    
    model = EnhancedLightweightAutoEncoder(
        input_dim=X_train.shape[1],
        hidden_dim=config.enhanced_ae_hidden_dim,
        latent_dim=config.enhanced_ae_latent_dim,
        epochs=config.enhanced_ae_epochs,
        batch_size=config.enhanced_ae_batch_size,
        use_early_stopping=True,
        patience=config.ae_patience
    )
    
    with Timer("增强自编码器训练"):
        model.train(X_train_split, X_val_split, feature_names)
        
    return model


def train_ensemble_model(
    X_train: np.ndarray, 
    y_train: np.ndarray, 
    feature_names: List[str] = None,
    config: TrainingConfig = None
) -> Any:
    """
    训练集成模型
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        feature_names: 特征名称列表
        config: 训练配置
        
    Returns:
        训练好的集成模型
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("🎯 训练集成模型")
    logger.info("=" * 60)
    
    from algorithm.training.ensemble_model import EnsembleAnomalyDetector
    
    # 创建基础模型
    logger.info("  创建并训练基础模型...")
    
    # 训练孤立森林
    logger.info("    - 训练孤立森林...")
    if_model = LightweightIsolationForest(
        n_estimators=config.if_n_estimators,
        max_depth=config.if_max_depth
    )
    if_model.train(X_train[y_train == 0], feature_names)  # 仅正常样本
    
    # 训练自编码器
    logger.info("    - 训练自编码器...")
    ae_model = LightweightAutoEncoder(
        input_dim=X_train.shape[1],
        hidden_dim=config.ae_hidden_dim,
        latent_dim=config.ae_latent_dim,
        epochs=config.ae_epochs // 2  # 集成中使用较少epoch
    )
    ae_model.train(X_train[y_train == 0], feature_names)  # 仅正常样本
    
    # 训练KNN
    logger.info("    - 训练KNN...")
    knn_model = BaselineKNN(n_neighbors=config.knn_n_neighbors)
    knn_model.train(X_train, y_train)
    
    # 训练SVM
    logger.info("    - 训练SVM...")
    svm_model = BaselineSVM(kernel=config.svm_kernel, C=config.svm_c)
    svm_model.train(X_train, y_train)
    
    # 创建集成
    logger.info("  创建集成模型...")
    ensemble = EnsembleAnomalyDetector(voting_strategy='weighted')
    ensemble.add_model('IsolationForest', if_model, weight=1.2)
    ensemble.add_model('AutoEncoder', ae_model, weight=1.0)
    ensemble.add_model('KNN', knn_model, weight=0.8)
    ensemble.add_model('SVM', svm_model, weight=0.9)
    
    logger.info(f"  集成模型包含 {len(ensemble.models)} 个基础模型")
    
    return ensemble


def apply_feature_selection(
    X_train: np.ndarray, 
    X_test: np.ndarray, 
    y_train: np.ndarray, 
    feature_names: List[str] = None,
    config: TrainingConfig = None
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    应用特征选择
    
    Args:
        X_train: 训练特征
        X_test: 测试特征
        y_train: 训练标签
        feature_names: 特征名称列表
        config: 训练配置
        
    Returns:
        Tuple[X_train_selected, X_test_selected, selected_feature_names]
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("🔍 特征选择")
    logger.info("=" * 60)
    
    from algorithm.feature_engineering import FeatureSelector
    
    k = min(config.feature_selection_k, X_train.shape[1])
    logger.info(f"  方法: {config.feature_selection_method}, 选择 {k} 个特征")
    
    selector = FeatureSelector(method=config.feature_selection_method, k=k)
    
    with Timer("特征选择"):
        selector.fit(X_train, y_train, feature_names)
    
    # 获取选择的特征索引和名称
    if hasattr(selector, 'selected_indices_'):
        selected_indices = selector.selected_indices_
        if feature_names:
            selected_feature_names = [feature_names[i] for i in selected_indices]
        else:
            selected_feature_names = [f'feature_{i}' for i in selected_indices]
    else:
        # 回退：使用默认名称
        selected_feature_names = [f'selected_feature_{i}' for i in range(k)]
    
    # 显示特征重要性（如果可用）
    try:
        selector.plot_feature_importance()
    except Exception as e:
        logger.warning(f"  无法绘制特征重要性图: {e}")
    
    # 转换数据
    X_train_selected = selector.transform(X_train)
    X_test_selected = selector.transform(X_test)
    
    logger.info(f"  特征选择完成: {X_train.shape[1]} -> {X_train_selected.shape[1]} 个特征")
    
    # 显示选择的特征
    if len(selected_feature_names) <= 10:
        logger.info(f"  选择的特征: {selected_feature_names}")
    else:
        logger.info(f"  选择的特征 (前10个): {selected_feature_names[:10]}...")
    
    return X_train_selected, X_test_selected, selected_feature_names


def test_incremental_learning(
    X_train: np.ndarray, 
    y_train: np.ndarray, 
    X_test: np.ndarray, 
    y_test: np.ndarray
) -> Optional[Dict[str, Any]]:
    """
    测试增量学习功能
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        X_test: 测试特征
        y_test: 测试标签
        
    Returns:
        增量学习测试结果字典，如果模块不存在则返回None
    """
    logger.info("\n" + "=" * 60)
    logger.info("📈 增量学习测试")
    logger.info("=" * 60)
    
    try:
        from algorithm.incremental_learning import IncrementalLearner
    except ImportError:
        logger.warning("  增量学习模块不可用，跳过测试")
        return None
    
    # 创建基础模型
    logger.info("  创建基础模型...")
    base_model = LightweightIsolationForest()
    
    # 使用部分数据进行初始训练
    initial_size = min(1000, len(X_train) // 2)
    base_model.train(X_train[:initial_size])
    logger.info(f"  初始训练样本数: {initial_size}")
    
    # 创建增量学习器
    incremental_learner = IncrementalLearner(
        base_model=base_model,
        update_strategy='sliding_window',
        window_size=500,
        update_frequency=100
    )
    
    # 模拟增量学习过程
    batch_size = 100
    n_batches = min(20, (len(X_train) - initial_size) // batch_size)
    
    logger.info(f"  开始增量学习: {n_batches} 个批次")
    
    with Timer("增量学习"):
        for i in range(n_batches):
            start_idx = initial_size + i * batch_size
            end_idx = start_idx + batch_size
            batch_X = X_train[start_idx:end_idx]
            batch_y = y_train[start_idx:end_idx]
            
            # 添加样本
            for j in range(len(batch_X)):
                incremental_learner.add_sample(batch_X[j:j+1], batch_y[j:j+1])
    
    # 测试增量学习后的性能
    predictions = incremental_learner.predict(X_test)
    accuracy = np.mean(predictions == y_test)
    
    logger.info(f"  增量学习后测试准确率: {accuracy:.4f}")
    
    # 显示性能统计
    stats = incremental_learner.get_performance_stats()
    logger.info(f"  增量学习统计: {stats}")
    
    return {
        'accuracy': accuracy,
        'stats': stats,
        'n_batches': n_batches
    }


def train_baseline_models(
    X_train: np.ndarray, 
    y_train: np.ndarray,
    config: TrainingConfig = None
) -> Tuple[BaselineKNN, BaselineSVM]:
    """
    训练基准模型
    
    Args:
        X_train: 训练特征
        y_train: 训练标签
        config: 训练配置
        
    Returns:
        Tuple[knn_model, svm_model]
    """
    if config is None:
        config = TrainingConfig()
        
    logger.info("\n" + "=" * 60)
    logger.info("📊 训练基准模型")
    logger.info("=" * 60)
    
    # KNN
    logger.info(f"  训练KNN (n_neighbors={config.knn_n_neighbors})...")
    knn = BaselineKNN(n_neighbors=config.knn_n_neighbors)
    with Timer("KNN训练"):
        knn.train(X_train, y_train)
    
    # SVM
    logger.info(f"  训练SVM (kernel={config.svm_kernel}, C={config.svm_c})...")
    svm = BaselineSVM(kernel=config.svm_kernel, C=config.svm_c)
    with Timer("SVM训练"):
        svm.train(X_train, y_train)
    
    return knn, svm


# =============================================================================
# 模型保存
# =============================================================================

def save_models(models: Dict[str, Any], output_path: Path) -> Dict[str, float]:
    """
    保存所有模型
    
    Args:
        models: 模型字典 {模型名: 模型对象}
        output_path: 输出路径
        
    Returns:
        模型大小字典 {模型名: 大小(MB)}
    """
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info("\n" + "=" * 60)
    logger.info("💾 保存模型")
    logger.info("=" * 60)
    
    model_sizes = {}
    
    # 复制标准化器到模型目录（后端预测时需要）
    scaler_src = project_root / 'data' / 'processed' / 'scaler.joblib'
    scaler_dst = output_path / 'scaler.joblib'
    if scaler_src.exists():
        import shutil
        shutil.copy2(scaler_src, scaler_dst)
        logger.info(f"  ✓ 标准化器已复制到: {scaler_dst}")
    else:
        logger.warning(f"  ⚠ 标准化器文件不存在: {scaler_src}")
    
    # 模型文件名映射
    model_file_mapping = {
        'LightweightIsolationForest': ('isolation_forest.joblib', 'joblib'),
        'LightweightAutoEncoder': ('autoencoder.pt', 'pt'),
        'EnhancedAutoEncoder': ('enhanced_autoencoder.pt', 'pt'),
        'EnsembleModel': ('ensemble_model.joblib', 'joblib'),
        'OptimizedIsolationForest': ('optimized_isolation_forest.joblib', 'joblib'),
        'OptimizedAutoEncoder': ('optimized_autoencoder.pt', 'pt'),
        'KNN': ('knn.joblib', 'joblib'),
        'SVM': ('svm.joblib', 'joblib')
    }
    
    for name, model in models.items():
        if model is None:
            logger.warning(f"  ⚠ 跳过空模型: {name}")
            continue
            
        try:
            if name in model_file_mapping:
                filename, model_type = model_file_mapping[name]
            else:
                # 默认使用joblib保存
                filename = f'{name.lower()}.joblib'
                model_type = 'joblib'
                
            filepath = output_path / filename
            
            # 尝试使用模型自带的保存方法
            if hasattr(model, 'save_model'):
                size = model.save_model(str(filepath))
            elif model_type == 'joblib':
                joblib.dump(model, filepath)
                size = os.path.getsize(filepath) / 1024 / 1024
            else:
                # 对于PyTorch模型
                import torch
                torch.save(model.state_dict() if hasattr(model, 'state_dict') else model, filepath)
                size = os.path.getsize(filepath) / 1024 / 1024
            
            model_sizes[name] = size
            logger.info(f"  ✓ {name}: {filepath.name} ({size:.2f}MB)")
            
        except Exception as e:
            logger.error(f"  ✗ 保存模型 {name} 失败: {e}")
            
    return model_sizes


# =============================================================================
# 命令行参数解析
# =============================================================================

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='智能家居异常检测 - 模型训练与评估',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # 训练选项
    parser.add_argument('--no-baseline', action='store_true', 
                        help='跳过基线模型训练')
    parser.add_argument('--no-enhanced', action='store_true',
                        help='跳过增强模型训练')
    parser.add_argument('--no-ensemble', action='store_true',
                        help='跳过集成模型训练')
    parser.add_argument('--no-optimized', action='store_true',
                        help='跳过特征优化模型训练')
    parser.add_argument('--test-incremental', action='store_true',
                        help='测试增量学习功能')
    
    # 模型参数
    parser.add_argument('--if-n-estimators', type=int, default=100,
                        help='孤立森林树的数量')
    parser.add_argument('--if-max-depth', type=int, default=10,
                        help='孤立森林最大深度')
    parser.add_argument('--ae-epochs', type=int, default=50,
                        help='自编码器训练轮数')
    parser.add_argument('--ae-hidden-dim', type=int, default=4,
                        help='自编码器隐藏层维度')
    
    # 输出选项
    parser.add_argument('--output-dir', type=str, default=None,
                        help='模型输出目录')
    parser.add_argument('--generate-report', action='store_true',
                        help='生成HTML评估报告')
    
    return parser.parse_args()


def create_config_from_args(args: argparse.Namespace) -> TrainingConfig:
    """从命令行参数创建配置"""
    config = TrainingConfig(
        if_n_estimators=args.if_n_estimators,
        if_max_depth=args.if_max_depth,
        ae_epochs=args.ae_epochs,
        ae_hidden_dim=args.ae_hidden_dim,
        train_baseline=not args.no_baseline,
        train_enhanced=not args.no_enhanced,
        train_ensemble=not args.no_ensemble,
        train_optimized=not args.no_optimized,
        test_incremental=args.test_incremental
    )
    
    if args.output_dir:
        config.output_path = Path(args.output_dir)
        
    return config


# =============================================================================
# 主函数
# =============================================================================

def main(config: TrainingConfig = None) -> Tuple[Dict[str, Any], ModelEvaluator]:
    """
    主函数 - 训练所有模型并评估
    
    Args:
        config: 训练配置，如果为None则使用默认配置
        
    Returns:
        Tuple[models_dict, evaluator]
    """
    if config is None:
        config = TrainingConfig()
    
    total_start_time = time.time()
    
    logger.info("=" * 60)
    logger.info("🏠 智能家居异常检测 - 模型训练与评估")
    logger.info("=" * 60)
    logger.info(f"训练配置:")
    logger.info(f"  - 基线模型: {'启用' if config.train_baseline else '禁用'}")
    logger.info(f"  - 增强模型: {'启用' if config.train_enhanced else '禁用'}")
    logger.info(f"  - 集成模型: {'启用' if config.train_ensemble else '禁用'}")
    logger.info(f"  - 特征优化: {'启用' if config.train_optimized else '禁用'}")
    logger.info(f"  - 增量学习: {'启用' if config.test_incremental else '禁用'}")
    
    # 初始化模型字典
    models: Dict[str, Any] = {}
    
    # 计算总步骤数
    total_steps = 1  # 数据加载
    if config.train_baseline:
        total_steps += 3  # IF + AE + 基线模型
    if config.train_enhanced:
        total_steps += 1
    if config.train_ensemble:
        total_steps += 1
    if config.train_optimized:
        total_steps += 2  # 特征选择 + 优化模型
    total_steps += 2  # 评估 + 保存
    
    progress = TrainingProgress(total_steps)
    
    # =========================================================================
    # 1. 加载数据
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("📂 Step 1: 加载数据")
    logger.info("=" * 60)
    
    try:
        with Timer("数据加载") as timer:
            X_train, X_test, y_train, y_test, feature_names = load_data(config)
        progress.step("数据加载", timer.elapsed)
    except Exception as e:
        logger.error(f"数据加载失败: {e}")
        raise
    
    # =========================================================================
    # 2. 训练基础轻量化模型
    # =========================================================================
    if_model = None
    ae_model = None
    knn_model = None
    svm_model = None
    
    if config.train_baseline:
        # 训练孤立森林
        with Timer("") as timer:
            if_model = train_isolation_forest(X_train, y_train, feature_names, config)
        progress.step("孤立森林训练", timer.elapsed)
        models['LightweightIsolationForest'] = if_model
        
        # 训练自编码器
        with Timer("") as timer:
            ae_model = train_autoencoder(X_train, y_train, feature_names, config)
        progress.step("自编码器训练", timer.elapsed)
        models['LightweightAutoEncoder'] = ae_model
        
        # 训练基线模型
        with Timer("") as timer:
            knn_model, svm_model = train_baseline_models(X_train, y_train, config)
        progress.step("基线模型训练", timer.elapsed)
        models['KNN'] = knn_model
        models['SVM'] = svm_model
    
    # =========================================================================
    # 3. 训练增强版模型
    # =========================================================================
    enhanced_ae_model = None
    
    if config.train_enhanced:
        with Timer("") as timer:
            enhanced_ae_model = train_enhanced_autoencoder(X_train, y_train, feature_names, config)
        progress.step("增强自编码器训练", timer.elapsed)
        models['EnhancedAutoEncoder'] = enhanced_ae_model
    
    # =========================================================================
    # 4. 训练集成模型
    # =========================================================================
    ensemble_model = None
    
    if config.train_ensemble:
        with Timer("") as timer:
            ensemble_model = train_ensemble_model(X_train, y_train, feature_names, config)
        progress.step("集成模型训练", timer.elapsed)
        models['EnsembleModel'] = ensemble_model
    
    # =========================================================================
    # 5. 特征工程优化
    # =========================================================================
    optimized_if_model = None
    optimized_ae_model = None
    
    if config.train_optimized:
        # 特征选择
        with Timer("") as timer:
            X_train_optimized, X_test_optimized, selected_feature_names = apply_feature_selection(
                X_train, X_test, y_train, feature_names, config
            )
        progress.step("特征选择", timer.elapsed)
        
        # 使用选择后的特征训练优化模型
        logger.info("\n" + "=" * 60)
        logger.info("⚡ 训练特征优化后的模型")
        logger.info("=" * 60)
        
        with Timer("") as timer:
            # 训练优化后的孤立森林
            optimized_if_model = LightweightIsolationForest(
                n_estimators=config.if_n_estimators,
                max_depth=config.if_max_depth,
                max_samples=config.if_max_samples,
                contamination=config.if_contamination
            )
            optimized_if_model.train(X_train_optimized[y_train == 0], selected_feature_names)
            models['OptimizedIsolationForest'] = optimized_if_model
            
            # 训练优化后的自编码器
            optimized_ae_model = LightweightAutoEncoder(
                input_dim=X_train_optimized.shape[1],
                hidden_dim=config.ae_hidden_dim,
                latent_dim=config.ae_latent_dim,
                epochs=config.ae_epochs,
                batch_size=config.ae_batch_size
            )
            optimized_ae_model.train(X_train_optimized[y_train == 0], feature_names=selected_feature_names)
            models['OptimizedAutoEncoder'] = optimized_ae_model
            
        progress.step("优化模型训练", timer.elapsed)
    else:
        # 如果不进行特征优化，使用原始数据
        X_test_optimized = X_test
    
    # =========================================================================
    # 6. 模型评估与对比
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("📊 Step 6: 模型评估与对比")
    logger.info("=" * 60)
    
    # 过滤掉None的模型
    valid_models = {k: v for k, v in models.items() if v is not None}
    
    if not valid_models:
        logger.warning("没有可评估的模型！")
        return models, None
    
    evaluator = ModelEvaluator(output_path=str(config.evaluation_path))
    
    with Timer("") as timer:
        # 对于优化后的模型，使用优化后的测试集
        models_for_eval = {}
        test_data_for_eval = {}
        
        for name, model in valid_models.items():
            if 'Optimized' in name and config.train_optimized:
                models_for_eval[name] = model
                test_data_for_eval[name] = (X_test_optimized, y_test)
            else:
                models_for_eval[name] = model
                test_data_for_eval[name] = (X_test, y_test)
        
        # 评估每个模型
        for name, model in models_for_eval.items():
            X_eval, y_eval = test_data_for_eval[name]
            try:
                evaluator.evaluate_model(model, name, X_eval, y_eval)
                logger.info(f"  ✓ {name} 评估完成")
            except Exception as e:
                logger.error(f"  ✗ {name} 评估失败: {e}")
        
        # 生成对比报告
        comparison_df = evaluator.compare_models(models_for_eval, X_test, y_test)
        
    progress.step("模型评估", timer.elapsed)
    
    # =========================================================================
    # 7. 增量学习测试（可选）
    # =========================================================================
    if config.test_incremental:
        test_incremental_learning(X_train, y_train, X_test, y_test)
    
    # =========================================================================
    # 8. 检查是否满足要求
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("✅ 指标要求检查")
    logger.info("=" * 60)
    
    try:
        check_results = evaluator.check_requirements()
        for model_name, passed in check_results.items():
            status = "✓ 通过" if passed else "✗ 未通过"
            logger.info(f"  {model_name}: {status}")
    except Exception as e:
        logger.warning(f"  检查指标要求时出错: {e}")
    
    # =========================================================================
    # 9. 保存模型
    # =========================================================================
    with Timer("") as timer:
        model_sizes = save_models(valid_models, config.output_path)
    progress.step("保存模型", timer.elapsed)
    
    # =========================================================================
    # 10. 保存评估报告
    # =========================================================================
    logger.info("\n" + "=" * 60)
    logger.info("📝 保存评估报告")
    logger.info("=" * 60)
    
    try:
        evaluator.save_report('evaluation_report.json')
        logger.info("  ✓ JSON报告已保存")
        
        evaluator.save_comparison_csv(comparison_df, 'model_comparison.csv')
        logger.info("  ✓ CSV对比表已保存")
        
        # 生成HTML报告（如果支持）
        if hasattr(evaluator, 'generate_html_report'):
            evaluator.generate_html_report()
            logger.info("  ✓ HTML报告已生成")
    except Exception as e:
        logger.warning(f"  保存报告时出错: {e}")
    
    # =========================================================================
    # 11. 输出总结
    # =========================================================================
    total_time = time.time() - total_start_time
    
    logger.info("\n" + "=" * 60)
    logger.info("🎉 训练完成总结")
    logger.info("=" * 60)
    
    # 输出时间统计
    logger.info(progress.summary())
    
    # 输出模型性能排名
    if comparison_df is not None and not comparison_df.empty:
        logger.info("\n模型性能排名（按F1分数）:")
        for i, row in comparison_df.iterrows():
            f1_col = 'F1分数' if 'F1分数' in row.index else 'f1_score'
            time_col = '推理时间(ms)' if '推理时间(ms)' in row.index else 'inference_time_ms'
            model_col = '模型' if '模型' in row.index else 'model'
            
            f1 = row.get(f1_col, row.get('f1_score', 0))
            inf_time = row.get(time_col, row.get('inference_time_ms', 0))
            model_name = row.get(model_col, row.get('model', f'Model_{i}'))
            
            logger.info(f"  {i+1}. {model_name}: F1={f1:.4f}, 推理={inf_time:.2f}ms")
    
    # 找出最佳轻量化模型
    lightweight_models = ['LightweightIsolationForest', 'LightweightAutoEncoder', 
                         'EnhancedAutoEncoder', 'OptimizedIsolationForest', 'OptimizedAutoEncoder']
    
    if comparison_df is not None and not comparison_df.empty:
        model_col = '模型' if '模型' in comparison_df.columns else 'model'
        lightweight_df = comparison_df[comparison_df[model_col].isin(lightweight_models)]
        
        if not lightweight_df.empty:
            best_lightweight = lightweight_df.iloc[0]
            
            f1_col = 'F1分数' if 'F1分数' in best_lightweight.index else 'f1_score'
            time_col = '推理时间(ms)' if '推理时间(ms)' in best_lightweight.index else 'inference_time_ms'
            mem_col = '内存占用(MB)' if '内存占用(MB)' in best_lightweight.index else 'memory_mb'
            
            logger.info(f"\n🏆 推荐部署模型: {best_lightweight[model_col]}")
            logger.info(f"  F1分数: {best_lightweight.get(f1_col, 'N/A'):.4f}" if isinstance(best_lightweight.get(f1_col), (int, float)) else f"  F1分数: {best_lightweight.get(f1_col, 'N/A')}")
            logger.info(f"  推理时间: {best_lightweight.get(time_col, 'N/A'):.2f}ms" if isinstance(best_lightweight.get(time_col), (int, float)) else f"  推理时间: {best_lightweight.get(time_col, 'N/A')}")
            logger.info(f"  内存占用: {best_lightweight.get(mem_col, 'N/A'):.2f}MB" if isinstance(best_lightweight.get(mem_col), (int, float)) else f"  内存占用: {best_lightweight.get(mem_col, 'N/A')}")
    
    logger.info(f"\n总耗时: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")
    logger.info("=" * 60)
    
    return models, evaluator


if __name__ == '__main__':
    # 解析命令行参数
    args = parse_args()
    
    # 创建配置
    config = create_config_from_args(args)
    
    try:
        models, evaluator = main(config)
        
        # 生成HTML报告（如果启用）
        if args.generate_report and evaluator is not None:
            if hasattr(evaluator, 'generate_html_report'):
                evaluator.generate_html_report()
                logger.info("HTML报告已生成")
                
    except FileNotFoundError as e:
        logger.error(f"文件未找到: {e}")
        logger.info("请先运行数据预处理: python data/scripts/data_preprocessor.py")
        sys.exit(1)
    except Exception as e:
        logger.error(f"训练过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)