"""
轻量化自编码器模型
网络结构：输入→隐藏层→潜在空间→隐藏层→输出
目标：参数量<100，适配低算力设备

优化内容：
1. 学习率调度器（ReduceLROnPlateau, CosineAnnealing）
2. 改进损失函数（MSE + 对比学习损失可选）
3. 梯度裁剪防止梯度爆炸
4. 完善早停机制
5. 温度参数控制概率分布
6. 模型量化支持（INT8）
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau, CosineAnnealingLR, CosineAnnealingWarmRestarts
from torch.utils.data import DataLoader, TensorDataset
import joblib
import time
import psutil
import os
import copy
from pathlib import Path
from sklearn.metrics import (
    f1_score, precision_score, recall_score, 
    accuracy_score, confusion_matrix, roc_auc_score
)
from typing import Optional, Dict, Tuple, List, Union
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleAutoEncoder(nn.Module):
    """简化自编码器网络结构（优化版）"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 4, latent_dim: int = 2, 
                 use_batch_norm: bool = False, activation: str = 'relu'):
        """
        初始化自编码器
        
        Args:
            input_dim: 输入维度
            hidden_dim: 隐藏层维度（默认4）
            latent_dim: 潜在空间维度（默认2）
            use_batch_norm: 是否使用批归一化
            activation: 激活函数类型 ('relu', 'leaky_relu', 'elu')
        """
        super(SimpleAutoEncoder, self).__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        
        # 选择激活函数
        activation_fn = self._get_activation(activation)
        
        # 编码器
        encoder_layers = [nn.Linear(input_dim, hidden_dim)]
        if use_batch_norm:
            encoder_layers.append(nn.BatchNorm1d(hidden_dim))
        encoder_layers.extend([
            activation_fn,
            nn.Linear(hidden_dim, latent_dim),
            activation_fn
        ])
        self.encoder = nn.Sequential(*encoder_layers)
        
        # 解码器
        decoder_layers = [nn.Linear(latent_dim, hidden_dim)]
        if use_batch_norm:
            decoder_layers.append(nn.BatchNorm1d(hidden_dim))
        decoder_layers.extend([
            activation_fn,
            nn.Linear(hidden_dim, input_dim)
        ])
        self.decoder = nn.Sequential(*decoder_layers)
        
        # 初始化权重
        self._initialize_weights()
        
    def _get_activation(self, activation: str) -> nn.Module:
        """获取激活函数"""
        activations = {
            'relu': nn.ReLU(),
            'leaky_relu': nn.LeakyReLU(0.1),
            'elu': nn.ELU(),
            'selu': nn.SELU(),
            'gelu': nn.GELU()
        }
        return activations.get(activation, nn.ReLU())
    
    def _initialize_weights(self):
        """Xavier/Kaiming 权重初始化"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)
    
    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self.decoder(z)


class EnhancedAutoEncoder(nn.Module):
    """增强版自编码器网络结构，引入残差连接和改进的注意力机制"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 8, latent_dim: int = 4,
                 dropout_rate: float = 0.1, use_residual: bool = True):
        """
        初始化增强版自编码器
        
        Args:
            input_dim: 输入维度
            hidden_dim: 隐藏层维度（增强为8）
            latent_dim: 潜在空间维度（增强为4）
            dropout_rate: Dropout比例
            use_residual: 是否使用残差连接
        """
        super(EnhancedAutoEncoder, self).__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.use_residual = use_residual
        
        # 编码器
        self.encoder_fc1 = nn.Linear(input_dim, hidden_dim)
        self.encoder_bn1 = nn.BatchNorm1d(hidden_dim)
        self.encoder_fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.encoder_fc3 = nn.Linear(hidden_dim // 2, latent_dim)
        
        # 解码器
        self.decoder_fc1 = nn.Linear(latent_dim, hidden_dim // 2)
        self.decoder_fc2 = nn.Linear(hidden_dim // 2, hidden_dim)
        self.decoder_bn2 = nn.BatchNorm1d(hidden_dim)
        self.decoder_fc3 = nn.Linear(hidden_dim, input_dim)
        
        # 残差连接的投影层（如果维度不匹配）
        if use_residual and input_dim != hidden_dim:
            self.residual_proj = nn.Linear(input_dim, hidden_dim)
        else:
            self.residual_proj = None
        
        # 注意力机制（改进版：多特征注意力）
        self.feature_attention = nn.Sequential(
            nn.Linear(latent_dim, latent_dim),
            nn.Tanh(),
            nn.Linear(latent_dim, latent_dim),
            nn.Sigmoid()
        )
        
        self.dropout = nn.Dropout(dropout_rate)
        self.activation = nn.LeakyReLU(0.1)
        
        # 初始化权重
        self._initialize_weights()
        
    def _initialize_weights(self):
        """权重初始化"""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='leaky_relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 编码
        encoded = self._encode(x)
        # 应用注意力权重
        attention_weights = self.feature_attention(encoded)
        encoded_weighted = encoded * attention_weights
        # 解码
        decoded = self._decode(encoded_weighted)
        return decoded
    
    def _encode(self, x: torch.Tensor) -> torch.Tensor:
        """编码过程"""
        h1 = self.activation(self.encoder_bn1(self.encoder_fc1(x)))
        h1 = self.dropout(h1)
        h2 = self.activation(self.encoder_fc2(h1))
        latent = torch.tanh(self.encoder_fc3(h2))  # 使用tanh稳定潜在空间
        return latent
    
    def _decode(self, z: torch.Tensor) -> torch.Tensor:
        """解码过程"""
        h1 = self.activation(self.decoder_fc1(z))
        h2 = self.activation(self.decoder_bn2(self.decoder_fc2(h1)))
        h2 = self.dropout(h2)
        output = self.decoder_fc3(h2)
        return output
    
    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self._encode(x)
    
    def decode(self, z: torch.Tensor) -> torch.Tensor:
        return self._decode(z)
    
    def get_attention_weights(self, x: torch.Tensor) -> torch.Tensor:
        """获取注意力权重（用于解释性）"""
        with torch.no_grad():
            encoded = self._encode(x)
            return self.feature_attention(encoded)


class LightweightAutoEncoder:
    """轻量化自编码器异常检测模型（优化版）"""
    
    # 支持的学习率调度策略
    LR_SCHEDULERS = ['reduce_on_plateau', 'cosine', 'cosine_warm_restart', 'none']
    
    # 支持的损失函数
    LOSS_FUNCTIONS = ['mse', 'mae', 'huber', 'combined']
    
    def __init__(self,
                 input_dim: int = 14,
                 hidden_dim: int = 4,
                 latent_dim: int = 2,
                 learning_rate: float = 0.001,
                 epochs: int = 50,
                 batch_size: int = 64,
                 threshold_percentile: float = 95,
                 # 新增优化参数
                 lr_scheduler: str = 'reduce_on_plateau',
                 loss_function: str = 'mse',
                 weight_decay: float = 1e-5,
                 grad_clip_norm: float = 1.0,
                 temperature: float = 1.0,
                 use_batch_norm: bool = False,
                 activation: str = 'relu'):
        """
        初始化轻量化自编码器
        
        Args:
            input_dim: 输入特征维度
            hidden_dim: 隐藏层神经元数（默认4，轻量化）
            latent_dim: 潜在空间维度（默认2，极简压缩）
            learning_rate: 学习率
            epochs: 训练轮数
            batch_size: 批次大小
            threshold_percentile: 异常阈值百分位数
            lr_scheduler: 学习率调度策略 ('reduce_on_plateau', 'cosine', 'cosine_warm_restart', 'none')
            loss_function: 损失函数类型 ('mse', 'mae', 'huber', 'combined')
            weight_decay: 权重衰减（L2正则化）
            grad_clip_norm: 梯度裁剪范数
            temperature: 概率预测的温度参数（越小分布越尖锐）
            use_batch_norm: 是否使用批归一化
            activation: 激活函数类型
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.threshold_percentile = threshold_percentile
        self.lr_scheduler_type = lr_scheduler
        self.loss_function_type = loss_function
        self.weight_decay = weight_decay
        self.grad_clip_norm = grad_clip_norm
        self.temperature = temperature
        
        self.device = torch.device('cpu')  # 边缘设备使用CPU
        self.model = SimpleAutoEncoder(
            input_dim, hidden_dim, latent_dim, 
            use_batch_norm=use_batch_norm, 
            activation=activation
        ).to(self.device)
        
        # 设置损失函数
        self.criterion = self._get_loss_function(loss_function)
        
        # 设置优化器
        self.optimizer = optim.Adam(
            self.model.parameters(), 
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # 设置学习率调度器
        self.scheduler = self._get_lr_scheduler(lr_scheduler)
        
        self.threshold = None
        self.threshold_std = None  # 阈值的标准差（用于自适应）
        self.is_trained = False
        self.training_time = 0
        self.feature_names = None
        self.train_losses = []
        self.val_losses = []
        self.lr_history = []
        self.best_model_state = None
        
        # 计算参数量
        self.param_count = sum(p.numel() for p in self.model.parameters())
        logger.info(f"模型参数量: {self.param_count}")
        
    def _get_loss_function(self, loss_type: str) -> nn.Module:
        """获取损失函数"""
        if loss_type == 'mse':
            return nn.MSELoss()
        elif loss_type == 'mae':
            return nn.L1Loss()
        elif loss_type == 'huber':
            return nn.SmoothL1Loss()
        elif loss_type == 'combined':
            # 组合损失：MSE + MAE
            return CombinedLoss(mse_weight=0.7, mae_weight=0.3)
        else:
            logger.warning(f"未知损失函数 {loss_type}，使用MSE")
            return nn.MSELoss()
    
    def _get_lr_scheduler(self, scheduler_type: str):
        """获取学习率调度器"""
        if scheduler_type == 'reduce_on_plateau':
            return ReduceLROnPlateau(
                self.optimizer, mode='min', factor=0.5, 
                patience=5, min_lr=1e-6, verbose=True
            )
        elif scheduler_type == 'cosine':
            return CosineAnnealingLR(
                self.optimizer, T_max=self.epochs, eta_min=1e-6
            )
        elif scheduler_type == 'cosine_warm_restart':
            return CosineAnnealingWarmRestarts(
                self.optimizer, T_0=10, T_mult=2, eta_min=1e-6
            )
        else:
            return None
        
    def train(self, X_train: np.ndarray, X_val: np.ndarray = None, 
              feature_names: list = None, early_stopping: bool = True,
              patience: int = 10, min_delta: float = 1e-6) -> Dict:
        """
        训练模型（优化版，支持早停和学习率调度）
        
        Args:
            X_train: 训练数据（正常样本）
            X_val: 验证数据
            feature_names: 特征名称
            early_stopping: 是否启用早停
            patience: 早停耐心值
            min_delta: 最小改进阈值
            
        Returns:
            训练历史字典
        """
        logger.info(f"开始训练自编码器模型...")
        logger.info(f"网络结构: {self.input_dim}→{self.hidden_dim}→{self.latent_dim}→{self.hidden_dim}→{self.input_dim}")
        logger.info(f"参数量: {self.param_count}, 损失函数: {self.loss_function_type}, 调度器: {self.lr_scheduler_type}")
        
        self.feature_names = feature_names
        
        # 准备数据
        X_tensor = torch.FloatTensor(X_train).to(self.device)
        dataset = TensorDataset(X_tensor, X_tensor)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True, drop_last=False)
        
        # 准备验证数据
        val_dataloader = None
        if X_val is not None:
            X_val_tensor = torch.FloatTensor(X_val).to(self.device)
            val_dataset = TensorDataset(X_val_tensor, X_val_tensor)
            val_dataloader = DataLoader(val_dataset, batch_size=self.batch_size)
        
        start_time = time.time()
        
        best_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(self.epochs):
            # 训练阶段
            self.model.train()
            epoch_loss = 0
            
            for batch_x, _ in dataloader:
                self.optimizer.zero_grad()
                output = self.model(batch_x)
                loss = self.criterion(output, batch_x)
                loss.backward()
                
                # 梯度裁剪
                if self.grad_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip_norm)
                
                self.optimizer.step()
                epoch_loss += loss.item()
            
            avg_train_loss = epoch_loss / len(dataloader)
            self.train_losses.append(avg_train_loss)
            
            # 记录学习率
            current_lr = self.optimizer.param_groups[0]['lr']
            self.lr_history.append(current_lr)
            
            # 验证阶段
            avg_val_loss = avg_train_loss
            if val_dataloader:
                avg_val_loss = self._validate(val_dataloader)
                self.val_losses.append(avg_val_loss)
            
            # 更新学习率调度器
            if self.scheduler is not None:
                if isinstance(self.scheduler, ReduceLROnPlateau):
                    self.scheduler.step(avg_val_loss if val_dataloader else avg_train_loss)
                else:
                    self.scheduler.step()
            
            # 早停检查
            monitor_loss = avg_val_loss if val_dataloader else avg_train_loss
            if early_stopping:
                if monitor_loss < best_loss - min_delta:
                    best_loss = monitor_loss
                    patience_counter = 0
                    # 保存最佳模型
                    self.best_model_state = copy.deepcopy(self.model.state_dict())
                else:
                    patience_counter += 1
                    
                if patience_counter >= patience:
                    logger.info(f"早停触发于 Epoch {epoch+1}，最佳损失: {best_loss:.6f}")
                    if self.best_model_state is not None:
                        self.model.load_state_dict(self.best_model_state)
                    break
            
            if (epoch + 1) % 10 == 0:
                val_info = f", 验证损失: {avg_val_loss:.6f}" if val_dataloader else ""
                logger.info(f"Epoch [{epoch+1}/{self.epochs}], 训练损失: {avg_train_loss:.6f}{val_info}, LR: {current_lr:.6f}")
        
        self.training_time = time.time() - start_time
        
        # 计算异常阈值
        self._calculate_threshold(X_train)
        
        self.is_trained = True
        logger.info(f"训练完成，耗时: {self.training_time:.3f}s")
        logger.info(f"异常阈值: {self.threshold:.6f} (±{self.threshold_std:.6f})")
        
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'lr_history': self.lr_history,
            'best_loss': best_loss,
            'training_time': self.training_time,
            'final_epoch': len(self.train_losses)
        }
        
    def _validate(self, val_dataloader: DataLoader) -> float:
        """验证模型"""
        self.model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch_x, _ in val_dataloader:
                output = self.model(batch_x)
                loss = self.criterion(output, batch_x)
                val_loss += loss.item()
        return val_loss / len(val_dataloader)
    
    def _calculate_threshold(self, X: np.ndarray):
        """计算异常检测阈值（增强版：考虑分布）"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            errors = mse.cpu().numpy()
            
            self.threshold = np.percentile(errors, self.threshold_percentile)
            self.threshold_std = np.std(errors)
            
            # 保存误差分布信息（用于自适应阈值）
            self._error_distribution = {
                'mean': np.mean(errors),
                'std': np.std(errors),
                'median': np.median(errors),
                'q1': np.percentile(errors, 25),
                'q3': np.percentile(errors, 75)
            }
    
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
            
        reconstruction_errors = self._get_reconstruction_error(X)
        return np.where(reconstruction_errors > self.threshold, 1, 0)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        预测异常概率（使用温度参数控制分布）
        
        Args:
            X: 待预测数据
            
        Returns:
            异常概率（0-1）
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        reconstruction_errors = self._get_reconstruction_error(X)
        
        # 使用温度参数的sigmoid转换
        # 温度越低，分布越尖锐（更确信）
        scaled_diff = (reconstruction_errors - self.threshold) / (self.threshold * self.temperature)
        proba = 1 / (1 + np.exp(-scaled_diff))
        
        return np.clip(proba, 0, 1)
    
    def predict_with_details(self, X: np.ndarray) -> Dict:
        """
        预测并返回详细信息
        
        Returns:
            包含预测、概率、重构误差、置信度的字典
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        reconstruction_errors = self._get_reconstruction_error(X)
        predictions = np.where(reconstruction_errors > self.threshold, 1, 0)
        probabilities = self.predict_proba(X)
        
        # 计算置信度（基于与阈值的相对距离）
        confidence = np.abs(reconstruction_errors - self.threshold) / self.threshold
        confidence = np.clip(confidence, 0, 1)
        
        return {
            'predictions': predictions,
            'probabilities': probabilities,
            'reconstruction_errors': reconstruction_errors,
            'confidence': confidence,
            'threshold': self.threshold
        }
    
    def _get_reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """计算重构误差"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            return mse.cpu().numpy()
    
    def get_reconstruction(self, X: np.ndarray) -> np.ndarray:
        """获取重构结果（用于分析）"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            return reconstructed.cpu().numpy()
    
    def get_latent_representation(self, X: np.ndarray) -> np.ndarray:
        """获取潜在空间表示（用于可视化和聚类）"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            latent = self.model.encode(X_tensor)
            return latent.cpu().numpy()
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> dict:
        """
        评估模型性能
        
        Args:
            X_test: 测试数据
            y_test: 真实标签
            
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
            'confusion_matrix': confusion_matrix(y_binary, y_pred).tolist(),
            'param_count': self.param_count
        }
        
        # 计算AUC-ROC
        try:
            metrics['auc_roc'] = roc_auc_score(y_binary, y_proba)
        except ValueError:
            metrics['auc_roc'] = 0.5
        
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
        """推理性能基准测试"""
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        single_sample = X_sample[0:1]
        times = []
        
        self.model.eval()
        
        # 预热
        for _ in range(10):
            self.predict(single_sample)
        
        # 正式测试
        for _ in range(n_iterations):
            start = time.time()
            self.predict(single_sample)
            times.append((time.time() - start) * 1000)
            
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # 计算模型大小
        model_size_mb = self._estimate_model_size()
        
        benchmark = {
            'avg_inference_time_ms': np.mean(times),
            'max_inference_time_ms': np.max(times),
            'min_inference_time_ms': np.min(times),
            'std_inference_time_ms': np.std(times),
            'p95_inference_time_ms': np.percentile(times, 95),
            'p99_inference_time_ms': np.percentile(times, 99),
            'memory_usage_mb': memory_mb,
            'model_size_mb': model_size_mb,
            'param_count': self.param_count
        }
        
        logger.info(f"推理性能基准测试:")
        logger.info(f"  平均推理时间: {benchmark['avg_inference_time_ms']:.3f}ms")
        logger.info(f"  P95推理时间: {benchmark['p95_inference_time_ms']:.3f}ms")
        logger.info(f"  内存占用: {benchmark['memory_usage_mb']:.2f}MB")
        logger.info(f"  模型大小: {benchmark['model_size_mb']:.4f}MB")
        logger.info(f"  参数量: {benchmark['param_count']}")
        
        return benchmark
    
    def _estimate_model_size(self) -> float:
        """估算模型大小（MB）"""
        param_size = sum(p.numel() * p.element_size() for p in self.model.parameters())
        buffer_size = sum(b.numel() * b.element_size() for b in self.model.buffers())
        return (param_size + buffer_size) / 1024 / 1024
    
    def quantize_model(self, method: str = 'dynamic') -> 'LightweightAutoEncoder':
        """
        模型量化（INT8）用于边缘设备部署
        
        Args:
            method: 量化方法 ('dynamic', 'static')
            
        Returns:
            量化后的模型实例
        """
        if method == 'dynamic':
            # 动态量化
            quantized_model = torch.quantization.quantize_dynamic(
                self.model, {nn.Linear}, dtype=torch.qint8
            )
            self.model = quantized_model
            logger.info("模型已进行动态INT8量化")
        else:
            logger.warning(f"暂不支持 {method} 量化方法")
        
        return self
    
    def save_model(self, filepath: str):
        """保存模型"""
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        model_data = {
            'state_dict': self.model.state_dict(),
            'params': {
                'input_dim': self.input_dim,
                'hidden_dim': self.hidden_dim,
                'latent_dim': self.latent_dim,
                'threshold': self.threshold,
                'threshold_std': self.threshold_std,
                'threshold_percentile': self.threshold_percentile,
                'temperature': self.temperature
            },
            'feature_names': self.feature_names,
            'training_time': self.training_time,
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'lr_history': self.lr_history,
            'error_distribution': getattr(self, '_error_distribution', None),
            'config': {
                'loss_function': self.loss_function_type,
                'lr_scheduler': self.lr_scheduler_type,
                'weight_decay': self.weight_decay,
                'grad_clip_norm': self.grad_clip_norm
            }
        }
        
        torch.save(model_data, filepath)
        
        file_size_mb = os.path.getsize(filepath) / 1024 / 1024
        logger.info(f"模型已保存: {filepath}")
        logger.info(f"模型文件大小: {file_size_mb:.4f}MB")
        
        return file_size_mb
    
    @classmethod
    def load_model(cls, filepath: str) -> 'LightweightAutoEncoder':
        """加载模型"""
        model_data = torch.load(filepath, map_location='cpu', weights_only=False)
        
        params = model_data['params']
        config = model_data.get('config', {})
        
        instance = cls(
            input_dim=params['input_dim'],
            hidden_dim=params['hidden_dim'],
            latent_dim=params['latent_dim'],
            threshold_percentile=params['threshold_percentile'],
            temperature=params.get('temperature', 1.0),
            loss_function=config.get('loss_function', 'mse'),
            lr_scheduler=config.get('lr_scheduler', 'none'),
            weight_decay=config.get('weight_decay', 1e-5),
            grad_clip_norm=config.get('grad_clip_norm', 1.0)
        )
        
        instance.model.load_state_dict(model_data['state_dict'])
        instance.threshold = params['threshold']
        instance.threshold_std = params.get('threshold_std', 0)
        instance.feature_names = model_data['feature_names']
        instance.training_time = model_data['training_time']
        instance.train_losses = model_data.get('train_losses', [])
        instance.val_losses = model_data.get('val_losses', [])
        instance.lr_history = model_data.get('lr_history', [])
        instance._error_distribution = model_data.get('error_distribution', None)
        instance.is_trained = True
        
        logger.info(f"模型已加载: {filepath}")
        return instance


class CombinedLoss(nn.Module):
    """组合损失函数：MSE + MAE"""
    
    def __init__(self, mse_weight: float = 0.7, mae_weight: float = 0.3):
        super().__init__()
        self.mse_weight = mse_weight
        self.mae_weight = mae_weight
        self.mse = nn.MSELoss()
        self.mae = nn.L1Loss()
        
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return self.mse_weight * self.mse(pred, target) + self.mae_weight * self.mae(pred, target)


class EnhancedLightweightAutoEncoder:
    """增强版轻量化自编码器异常检测模型（完整优化版）"""
    
    def __init__(self,
                 input_dim: int = 14,
                 hidden_dim: int = 8,
                 latent_dim: int = 4,
                 learning_rate: float = 0.001,
                 epochs: int = 80,
                 batch_size: int = 64,
                 threshold_percentile: float = 95,
                 use_early_stopping: bool = True,
                 patience: int = 10,
                 # 新增参数
                 lr_scheduler: str = 'cosine_warm_restart',
                 loss_function: str = 'combined',
                 weight_decay: float = 1e-5,
                 grad_clip_norm: float = 1.0,
                 dropout_rate: float = 0.1,
                 temperature: float = 0.8,
                 use_contrastive_loss: bool = False,
                 contrastive_weight: float = 0.1):
        """
        初始化增强版自编码器
        
        Args:
            input_dim: 输入特征维度
            hidden_dim: 隐藏层神经元数（增强为8）
            latent_dim: 潜在空间维度（增强为4）
            learning_rate: 学习率
            epochs: 训练轮数
            batch_size: 批次大小
            threshold_percentile: 异常阈值百分位数
            use_early_stopping: 是否使用早停
            patience: 早停耐心值
            lr_scheduler: 学习率调度策略
            loss_function: 损失函数类型
            weight_decay: 权重衰减
            grad_clip_norm: 梯度裁剪范数
            dropout_rate: Dropout比例
            temperature: 概率预测温度参数
            use_contrastive_loss: 是否使用对比学习损失
            contrastive_weight: 对比损失权重
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.threshold_percentile = threshold_percentile
        self.use_early_stopping = use_early_stopping
        self.patience = patience
        self.lr_scheduler_type = lr_scheduler
        self.loss_function_type = loss_function
        self.weight_decay = weight_decay
        self.grad_clip_norm = grad_clip_norm
        self.dropout_rate = dropout_rate
        self.temperature = temperature
        self.use_contrastive_loss = use_contrastive_loss
        self.contrastive_weight = contrastive_weight
        
        self.device = torch.device('cpu')
        self.model = EnhancedAutoEncoder(
            input_dim, hidden_dim, latent_dim, 
            dropout_rate=dropout_rate
        ).to(self.device)
        
        # 设置损失函数
        self.criterion = self._get_loss_function(loss_function)
        
        # 设置优化器（使用AdamW）
        self.optimizer = optim.AdamW(
            self.model.parameters(), 
            lr=learning_rate, 
            weight_decay=weight_decay,
            betas=(0.9, 0.999)
        )
        
        # 设置学习率调度器
        self.scheduler = self._get_lr_scheduler(lr_scheduler)
        
        self.threshold = None
        self.threshold_std = None
        self.is_trained = False
        self.training_time = 0
        self.feature_names = None
        self.train_losses = []
        self.val_losses = []
        self.lr_history = []
        self.best_model_state = None
        self.best_val_loss = float('inf')
        
        # 计算参数量
        self.param_count = sum(p.numel() for p in self.model.parameters())
        logger.info(f"增强版模型参数量: {self.param_count}")
    
    def _get_loss_function(self, loss_type: str) -> nn.Module:
        """获取损失函数"""
        if loss_type == 'mse':
            return nn.MSELoss()
        elif loss_type == 'mae':
            return nn.L1Loss()
        elif loss_type == 'huber':
            return nn.SmoothL1Loss()
        elif loss_type == 'combined':
            return CombinedLoss(mse_weight=0.7, mae_weight=0.3)
        else:
            return nn.MSELoss()
    
    def _get_lr_scheduler(self, scheduler_type: str):
        """获取学习率调度器"""
        if scheduler_type == 'reduce_on_plateau':
            return ReduceLROnPlateau(
                self.optimizer, mode='min', factor=0.5, 
                patience=5, min_lr=1e-6
            )
        elif scheduler_type == 'cosine':
            return CosineAnnealingLR(self.optimizer, T_max=self.epochs, eta_min=1e-6)
        elif scheduler_type == 'cosine_warm_restart':
            return CosineAnnealingWarmRestarts(self.optimizer, T_0=10, T_mult=2, eta_min=1e-6)
        else:
            return None
        
    def train(self, X_train: np.ndarray, X_val: np.ndarray = None, 
              feature_names: list = None, min_delta: float = 1e-6) -> Dict:
        """
        训练增强版模型（支持早停、学习率调度和可选的对比学习）
        
        Args:
            X_train: 训练数据
            X_val: 验证数据
            feature_names: 特征名称
            min_delta: 最小改进阈值
            
        Returns:
            训练历史字典
        """
        logger.info(f"开始训练增强版自编码器模型...")
        logger.info(f"网络结构: {self.input_dim}→{self.hidden_dim}→{self.latent_dim}→{self.input_dim}")
        logger.info(f"参数量: {self.param_count}, 调度器: {self.lr_scheduler_type}")
        
        self.feature_names = feature_names
        
        # 准备训练数据
        X_tensor = torch.FloatTensor(X_train).to(self.device)
        dataset = TensorDataset(X_tensor, X_tensor)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True, drop_last=True)
        
        # 准备验证数据
        val_dataloader = None
        if X_val is not None:
            X_val_tensor = torch.FloatTensor(X_val).to(self.device)
            val_dataset = TensorDataset(X_val_tensor, X_val_tensor)
            val_dataloader = DataLoader(val_dataset, batch_size=self.batch_size)
        
        start_time = time.time()
        patience_counter = 0
        
        for epoch in range(self.epochs):
            # 训练阶段
            self.model.train()
            epoch_loss = 0
            epoch_contrastive_loss = 0
            
            for batch_x, _ in dataloader:
                self.optimizer.zero_grad()
                
                # 前向传播
                output = self.model(batch_x)
                recon_loss = self.criterion(output, batch_x)
                
                total_loss = recon_loss
                
                # 可选：对比学习损失
                if self.use_contrastive_loss and batch_x.size(0) > 1:
                    contrastive_loss = self._compute_contrastive_loss(batch_x)
                    total_loss = recon_loss + self.contrastive_weight * contrastive_loss
                    epoch_contrastive_loss += contrastive_loss.item()
                
                total_loss.backward()
                
                # 梯度裁剪
                if self.grad_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.grad_clip_norm)
                
                self.optimizer.step()
                epoch_loss += recon_loss.item()
            
            avg_train_loss = epoch_loss / len(dataloader)
            self.train_losses.append(avg_train_loss)
            
            # 记录学习率
            current_lr = self.optimizer.param_groups[0]['lr']
            self.lr_history.append(current_lr)
            
            # 验证阶段
            avg_val_loss = avg_train_loss
            if val_dataloader:
                avg_val_loss = self._validate(val_dataloader)
                self.val_losses.append(avg_val_loss)
            
            # 更新学习率调度器
            if self.scheduler is not None:
                if isinstance(self.scheduler, ReduceLROnPlateau):
                    self.scheduler.step(avg_val_loss if val_dataloader else avg_train_loss)
                else:
                    self.scheduler.step()
            
            # 早停检查
            monitor_loss = avg_val_loss if val_dataloader else avg_train_loss
            if self.use_early_stopping:
                if monitor_loss < self.best_val_loss - min_delta:
                    self.best_val_loss = monitor_loss
                    patience_counter = 0
                    self.best_model_state = copy.deepcopy(self.model.state_dict())
                else:
                    patience_counter += 1
                    
                if patience_counter >= self.patience:
                    logger.info(f"早停触发于 Epoch {epoch+1}，最佳损失: {self.best_val_loss:.6f}")
                    if self.best_model_state is not None:
                        self.model.load_state_dict(self.best_model_state)
                    break
            
            if (epoch + 1) % 10 == 0:
                val_info = f", 验证损失: {avg_val_loss:.6f}" if val_dataloader else ""
                contrastive_info = f", 对比损失: {epoch_contrastive_loss/len(dataloader):.6f}" if self.use_contrastive_loss else ""
                logger.info(f"Epoch [{epoch+1}/{self.epochs}], 重构损失: {avg_train_loss:.6f}{val_info}{contrastive_info}, LR: {current_lr:.6f}")
        
        self.training_time = time.time() - start_time
        
        # 计算异常阈值
        self._calculate_threshold(X_train)
        
        self.is_trained = True
        logger.info(f"训练完成，耗时: {self.training_time:.3f}s")
        logger.info(f"异常阈值: {self.threshold:.6f}")
        
        return {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'lr_history': self.lr_history,
            'best_loss': self.best_val_loss,
            'training_time': self.training_time,
            'final_epoch': len(self.train_losses)
        }
    
    def _compute_contrastive_loss(self, batch_x: torch.Tensor, margin: float = 1.0) -> torch.Tensor:
        """
        计算对比学习损失（InfoNCE风格）
        鼓励相似样本在潜在空间中更接近
        """
        # 获取潜在表示
        latent = self.model.encode(batch_x)
        
        # 添加轻微噪声生成正样本对
        noise = torch.randn_like(batch_x) * 0.01
        latent_aug = self.model.encode(batch_x + noise)
        
        # 计算正样本对的距离（应该小）
        positive_dist = torch.mean((latent - latent_aug) ** 2, dim=1)
        
        # 计算负样本对的距离（随机配对，应该大）
        batch_size = latent.size(0)
        perm = torch.randperm(batch_size)
        negative_dist = torch.mean((latent - latent[perm]) ** 2, dim=1)
        
        # 对比损失：希望正样本距离小，负样本距离大
        loss = torch.mean(positive_dist) + torch.mean(torch.relu(margin - negative_dist))
        
        return loss
    
    def _validate(self, val_dataloader: DataLoader) -> float:
        """验证模型"""
        self.model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch_x, _ in val_dataloader:
                output = self.model(batch_x)
                loss = self.criterion(output, batch_x)
                val_loss += loss.item()
        return val_loss / len(val_dataloader)
    
    def get_feature_importance(self, X_sample: np.ndarray, method: str = 'perturbation') -> np.ndarray:
        """
        获取特征重要性
        
        Args:
            X_sample: 样本数据
            method: 计算方法 ('perturbation', 'gradient', 'attention')
            
        Returns:
            特征重要性分数
        """
        if not self.is_trained:
            raise ValueError("模型未训练")
        
        if method == 'attention':
            return self._get_attention_importance(X_sample)
        elif method == 'gradient':
            return self._get_gradient_importance(X_sample)
        else:
            return self._get_perturbation_importance(X_sample)
    
    def _get_perturbation_importance(self, X_sample: np.ndarray) -> np.ndarray:
        """基于扰动的特征重要性"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_sample).to(self.device)
            
            # 计算原始重构误差
            reconstructed = self.model(X_tensor)
            base_error = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            
            # 对每个特征进行扰动
            feature_importance = np.zeros(X_sample.shape[1])
            
            for i in range(X_sample.shape[1]):
                X_perturbed = X_tensor.clone()
                noise = torch.randn_like(X_perturbed[:, i]) * 0.1
                X_perturbed[:, i] += noise
                
                reconstructed_perturbed = self.model(X_perturbed)
                perturbed_error = torch.mean((X_perturbed - reconstructed_perturbed) ** 2, dim=1)
                
                importance = torch.mean(torch.abs(perturbed_error - base_error))
                feature_importance[i] = importance.item()
            
            # 归一化
            if np.sum(feature_importance) > 0:
                feature_importance = feature_importance / np.sum(feature_importance)
            
            return feature_importance
    
    def _get_attention_importance(self, X_sample: np.ndarray) -> np.ndarray:
        """基于注意力权重的特征重要性"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_sample).to(self.device)
            attention_weights = self.model.get_attention_weights(X_tensor)
            
            # 平均注意力权重
            avg_attention = torch.mean(attention_weights, dim=0).cpu().numpy()
            
            # 由于注意力在潜在空间，需要映射回特征空间
            # 简化：返回潜在空间的重要性，或使用编码器权重
            return avg_attention
    
    def _get_gradient_importance(self, X_sample: np.ndarray) -> np.ndarray:
        """基于梯度的特征重要性"""
        self.model.train()  # 需要梯度
        X_tensor = torch.FloatTensor(X_sample).to(self.device)
        X_tensor.requires_grad = True
        
        # 前向传播
        output = self.model(X_tensor)
        loss = self.criterion(output, X_tensor)
        
        # 反向传播
        loss.backward()
        
        # 梯度的绝对值表示重要性
        gradients = X_tensor.grad.abs().mean(dim=0).cpu().numpy()
        
        # 归一化
        if np.sum(gradients) > 0:
            gradients = gradients / np.sum(gradients)
        
        self.model.eval()
        return gradients
    
    def _calculate_threshold(self, X: np.ndarray):
        """计算自适应异常阈值"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            reconstruction_errors = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            errors = reconstruction_errors.cpu().numpy()
            
            self.threshold = np.percentile(errors, self.threshold_percentile)
            self.threshold_std = np.std(errors)
            
            # 保存误差分布
            self._error_distribution = {
                'mean': np.mean(errors),
                'std': np.std(errors),
                'median': np.median(errors),
                'q1': np.percentile(errors, 25),
                'q3': np.percentile(errors, 75),
                'iqr': np.percentile(errors, 75) - np.percentile(errors, 25)
            }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测异常"""
        if not self.is_trained:
            raise ValueError("模型未训练")
        reconstruction_errors = self._get_reconstruction_error(X)
        return np.where(reconstruction_errors > self.threshold, 1, 0)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """预测异常概率"""
        if not self.is_trained:
            raise ValueError("模型未训练")
        reconstruction_errors = self._get_reconstruction_error(X)
        scaled_diff = (reconstruction_errors - self.threshold) / (self.threshold * self.temperature)
        proba = 1 / (1 + np.exp(-scaled_diff))
        return np.clip(proba, 0, 1)
    
    def predict_with_confidence(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测异常并返回置信度
        
        Returns:
            (predictions, confidence_scores)
        """
        reconstruction_errors = self._get_reconstruction_error(X)
        predictions = np.where(reconstruction_errors > self.threshold, 1, 0)
        
        # 计算置信度（基于与阈值的距离和误差分布）
        if hasattr(self, '_error_distribution'):
            # 使用z-score计算置信度
            z_scores = np.abs(reconstruction_errors - self._error_distribution['mean']) / self._error_distribution['std']
            confidence = 1 - np.exp(-z_scores / 2)  # 转换为0-1
        else:
            confidence = np.abs(reconstruction_errors - self.threshold) / self.threshold
        
        confidence = np.clip(confidence, 0, 1)
        
        return predictions, confidence
    
    def _get_reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """计算重构误差"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            mse = torch.mean((X_tensor - reconstructed) ** 2, dim=1)
            return mse.cpu().numpy()
    
    def get_latent_representation(self, X: np.ndarray) -> np.ndarray:
        """获取潜在空间表示"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            latent = self.model.encode(X_tensor)
            return latent.cpu().numpy()
    
    def get_reconstruction(self, X: np.ndarray) -> np.ndarray:
        """获取重构结果"""
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X).to(self.device)
            reconstructed = self.model(X_tensor)
            return reconstructed.cpu().numpy()
    
    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> dict:
        """增强版评估方法"""
        y_binary = np.where(y_test > 0, 1, 0)
        y_pred = self.predict(X_test)
        y_proba = self.predict_proba(X_test)
        
        metrics = {
            'accuracy': accuracy_score(y_binary, y_pred),
            'precision': precision_score(y_binary, y_pred, zero_division=0),
            'recall': recall_score(y_binary, y_pred, zero_division=0),
            'f1_score': f1_score(y_binary, y_pred, zero_division=0),
            'confusion_matrix': confusion_matrix(y_binary, y_pred).tolist(),
            'param_count': self.param_count
        }
        
        # 计算AUC-ROC
        try:
            metrics['auc_roc'] = roc_auc_score(y_binary, y_proba)
        except ValueError:
            metrics['auc_roc'] = 0.5
        
        # 计算AUC-PR
        from sklearn.metrics import average_precision_score
        try:
            metrics['auc_pr'] = average_precision_score(y_binary, y_proba)
        except ValueError:
            metrics['auc_pr'] = 0.5
        
        tn, fp, fn, tp = confusion_matrix(y_binary, y_pred).ravel()
        metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
        metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0
        metrics['true_positive_rate'] = tp / (tp + fn) if (tp + fn) > 0 else 0
        metrics['true_negative_rate'] = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        # 计算 Matthews 相关系数
        from sklearn.metrics import matthews_corrcoef
        metrics['mcc'] = matthews_corrcoef(y_binary, y_pred)
        
        logger.info(f"增强版模型评估结果:")
        logger.info(f"  准确率: {metrics['accuracy']:.4f}")
        logger.info(f"  精确率: {metrics['precision']:.4f}")
        logger.info(f"  召回率: {metrics['recall']:.4f}")
        logger.info(f"  F1分数: {metrics['f1_score']:.4f}")
        logger.info(f"  AUC-ROC: {metrics['auc_roc']:.4f}")
        logger.info(f"  AUC-PR: {metrics['auc_pr']:.4f}")
        logger.info(f"  MCC: {metrics['mcc']:.4f}")
        
        return metrics
    
    def benchmark_inference(self, X_sample: np.ndarray, n_iterations: int = 100) -> dict:
        """增强版性能基准测试"""
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        single_sample = X_sample[0:1]
        batch_sample = X_sample[:min(32, len(X_sample))]
        
        # 预热
        for _ in range(10):
            self.predict(single_sample)
        
        # 单样本推理
        single_times = []
        self.model.eval()
        for _ in range(n_iterations):
            start = time.time()
            self.predict(single_sample)
            single_times.append((time.time() - start) * 1000)
        
        # 批量推理
        batch_times = []
        for _ in range(n_iterations // 10):
            start = time.time()
            self.predict(batch_sample)
            batch_times.append((time.time() - start) * 1000)
        
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        # 计算模型大小
        model_size_mb = self._estimate_model_size()
        
        benchmark = {
            'avg_single_inference_time_ms': np.mean(single_times),
            'avg_batch_inference_time_ms': np.mean(batch_times),
            'max_inference_time_ms': np.max(single_times),
            'min_inference_time_ms': np.min(single_times),
            'std_inference_time_ms': np.std(single_times),
            'p95_inference_time_ms': np.percentile(single_times, 95),
            'p99_inference_time_ms': np.percentile(single_times, 99),
            'memory_usage_mb': memory_mb,
            'model_size_mb': model_size_mb,
            'param_count': self.param_count,
            'throughput_samples_per_sec': 1000 / np.mean(batch_times) * len(batch_sample)
        }
        
        logger.info(f"增强版推理性能:")
        logger.info(f"  单样本推理: {benchmark['avg_single_inference_time_ms']:.3f}ms")
        logger.info(f"  批量推理: {benchmark['avg_batch_inference_time_ms']:.3f}ms")
        logger.info(f"  吞吐量: {benchmark['throughput_samples_per_sec']:.1f}样本/秒")
        logger.info(f"  内存占用: {benchmark['memory_usage_mb']:.2f}MB")
        logger.info(f"  模型大小: {benchmark['model_size_mb']:.4f}MB")
        
        return benchmark
    
    def _estimate_model_size(self) -> float:
        """估算模型大小（MB）"""
        param_size = sum(p.numel() * p.element_size() for p in self.model.parameters())
        buffer_size = sum(b.numel() * b.element_size() for b in self.model.buffers())
        return (param_size + buffer_size) / 1024 / 1024
    
    def save_model(self, filepath: str):
        """保存增强版模型"""
        if not self.is_trained:
            raise ValueError("模型未训练")
            
        model_data = {
            'state_dict': self.model.state_dict(),
            'params': {
                'input_dim': self.input_dim,
                'hidden_dim': self.hidden_dim,
                'latent_dim': self.latent_dim,
                'threshold': self.threshold,
                'threshold_std': self.threshold_std,
                'threshold_percentile': self.threshold_percentile,
                'dropout_rate': self.dropout_rate,
                'temperature': self.temperature
            },
            'feature_names': self.feature_names,
            'training_time': self.training_time,
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'lr_history': self.lr_history,
            'param_count': self.param_count,
            'error_distribution': getattr(self, '_error_distribution', None),
            'config': {
                'loss_function': self.loss_function_type,
                'lr_scheduler': self.lr_scheduler_type,
                'weight_decay': self.weight_decay,
                'grad_clip_norm': self.grad_clip_norm,
                'use_contrastive_loss': self.use_contrastive_loss,
                'contrastive_weight': self.contrastive_weight
            }
        }
        
        torch.save(model_data, filepath)
        
        file_size_mb = os.path.getsize(filepath) / 1024 / 1024
        logger.info(f"增强版模型已保存: {filepath}")
        logger.info(f"模型文件大小: {file_size_mb:.4f}MB")
        
        return file_size_mb
    
    @classmethod
    def load_model(cls, filepath: str) -> 'EnhancedLightweightAutoEncoder':
        """加载增强版模型"""
        model_data = torch.load(filepath, map_location='cpu', weights_only=False)
        
        params = model_data['params']
        config = model_data.get('config', {})
        
        instance = cls(
            input_dim=params['input_dim'],
            hidden_dim=params['hidden_dim'],
            latent_dim=params['latent_dim'],
            threshold_percentile=params['threshold_percentile'],
            dropout_rate=params.get('dropout_rate', 0.1),
            temperature=params.get('temperature', 0.8),
            loss_function=config.get('loss_function', 'combined'),
            lr_scheduler=config.get('lr_scheduler', 'cosine_warm_restart'),
            weight_decay=config.get('weight_decay', 1e-5),
            grad_clip_norm=config.get('grad_clip_norm', 1.0),
            use_contrastive_loss=config.get('use_contrastive_loss', False),
            contrastive_weight=config.get('contrastive_weight', 0.1)
        )
        
        instance.model.load_state_dict(model_data['state_dict'])
        instance.threshold = params['threshold']
        instance.threshold_std = params.get('threshold_std', 0)
        instance.feature_names = model_data['feature_names']
        instance.training_time = model_data['training_time']
        instance.train_losses = model_data.get('train_losses', [])
        instance.val_losses = model_data.get('val_losses', [])
        instance.lr_history = model_data.get('lr_history', [])
        instance.param_count = model_data.get('param_count', instance.param_count)
        instance._error_distribution = model_data.get('error_distribution', None)
        instance.is_trained = True
        
        logger.info(f"增强版模型已加载: {filepath}")
        return instance


if __name__ == '__main__':
    print("轻量化自编码器模型模块已就绪")
    print("使用方法:")
    print("  model = LightweightAutoEncoder(input_dim=14)")
    print("  model.train(X_train_normal)")
    print("  predictions = model.predict(X_test)")