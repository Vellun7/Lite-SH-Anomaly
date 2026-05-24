"""
部署和监控模块
功能：模型部署、性能监控、自动更新
目标：实现生产环境下的模型管理和优化
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional, Callable
import logging
import time
from pathlib import Path
import json
import joblib
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ModelDeployer:
    """模型部署器"""
    
    def __init__(self, deployment_dir: str = './deployment'):
        """
        初始化模型部署器
        
        Args:
            deployment_dir: 部署目录
        """
        self.deployment_dir = Path(deployment_dir)
        self.deployment_dir.mkdir(parents=True, exist_ok=True)
        
        self.deployed_models = {}
        self.model_metadata = {}
        self.active_model = None
        
        # 性能监控
        self.performance_stats = defaultdict(lambda: defaultdict(list))
        self.alert_thresholds = {
            'accuracy_drop': 0.1,      # 准确率下降10%
            'latency_increase': 0.5,   # 延迟增加50%
            'memory_increase': 0.2,    # 内存增加20%
            'error_rate': 0.05        # 错误率超过5%
        }
        
        logger.info(f"模型部署器初始化完成，部署目录: {deployment_dir}")
    
    def deploy_model(self, model: Any, model_name: str, version: str = 'v1.0', 
                    metadata: Dict[str, Any] = None) -> bool:
        """
        部署模型
        
        Args:
            model: 要部署的模型
            model_name: 模型名称
            version: 版本号
            metadata: 模型元数据
        
        Returns:
            bool: 部署是否成功
        """
        try:
            # 创建模型文件
            model_filename = f"{model_name}_{version}.joblib"
            model_path = self.deployment_dir / model_filename
            
            # 保存模型
            joblib.dump(model, model_path)
            
            # 保存元数据
            metadata = metadata or {}
            metadata.update({
                'name': model_name,
                'version': version,
                'deployment_time': datetime.now().isoformat(),
                'model_path': str(model_path),
                'performance': {
                    'accuracy': 0.0,
                    'latency': 0.0,
                    'memory_usage': 0.0,
                    'error_rate': 0.0
                }
            })
            
            metadata_path = self.deployment_dir / f"{model_name}_{version}_metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # 注册模型
            self.deployed_models[model_name] = model
            self.model_metadata[model_name] = metadata
            
            # 如果这是第一个模型，设为活动模型
            if self.active_model is None:
                self.active_model = model_name
            
            logger.info(f"模型部署成功: {model_name} (版本: {version})")
            return True
            
        except Exception as e:
            logger.error(f"模型部署失败: {e}")
            return False
    
    def switch_model(self, model_name: str) -> bool:
        """
        切换活动模型
        
        Args:
            model_name: 要切换的模型名称
        
        Returns:
            bool: 切换是否成功
        """
        if model_name not in self.deployed_models:
            logger.error(f"模型未部署: {model_name}")
            return False
        
        self.active_model = model_name
        logger.info(f"切换活动模型: {model_name}")
        return True
    
    def predict(self, X: np.ndarray, model_name: str = None) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        使用模型进行预测
        
        Args:
            X: 输入数据
            model_name: 模型名称（None表示使用活动模型）
        
        Returns:
            Tuple: (预测结果, 性能指标)
        """
        if model_name is None:
            model_name = self.active_model
        
        if model_name not in self.deployed_models:
            raise ValueError(f"模型未部署: {model_name}")
        
        model = self.deployed_models[model_name]
        
        # 记录开始时间
        start_time = time.time()
        
        try:
            # 执行预测
            predictions = model.predict(X)
            
            # 计算性能指标
            latency = (time.time() - start_time) * 1000  # 毫秒
            memory_usage = self._estimate_memory_usage(model)
            
            # 记录性能
            self._record_performance(model_name, latency, memory_usage, len(X))
            
            performance_stats = {
                'latency_ms': latency,
                'memory_mb': memory_usage,
                'batch_size': len(X),
                'timestamp': datetime.now().isoformat()
            }
            
            return predictions, performance_stats
            
        except Exception as e:
            logger.error(f"预测失败: {e}")
            # 记录错误
            self._record_error(model_name, str(e))
            raise
    
    def update_model_performance(self, model_name: str, ground_truth: np.ndarray, 
                               predictions: np.ndarray) -> Dict[str, float]:
        """
        更新模型性能指标
        
        Args:
            model_name: 模型名称
            ground_truth: 真实标签
            predictions: 预测结果
        
        Returns:
            Dict: 性能指标
        """
        if len(ground_truth) != len(predictions):
            raise ValueError("真实标签和预测结果长度不一致")
        
        # 计算性能指标
        accuracy = np.mean(ground_truth == predictions)
        error_rate = 1 - accuracy
        
        # 更新元数据
        if model_name in self.model_metadata:
            self.model_metadata[model_name]['performance'].update({
                'accuracy': accuracy,
                'error_rate': error_rate,
                'last_evaluation': datetime.now().isoformat()
            })
        
        # 检查是否需要告警
        self._check_performance_alerts(model_name, accuracy, error_rate)
        
        return {
            'accuracy': accuracy,
            'error_rate': error_rate,
            'samples_evaluated': len(ground_truth)
        }
    
    def _estimate_memory_usage(self, model: Any) -> float:
        """估算模型内存使用量"""
        try:
            # 简单的内存估算
            import sys
            return sys.getsizeof(model) / 1024 / 1024  # MB
        except:
            return 0.0
    
    def _record_performance(self, model_name: str, latency: float, memory: float, batch_size: int):
        """记录性能指标"""
        self.performance_stats[model_name]['latency'].append(latency)
        self.performance_stats[model_name]['memory'].append(memory)
        self.performance_stats[model_name]['batch_size'].append(batch_size)
        
        # 保持最近1000条记录
        for key in ['latency', 'memory', 'batch_size']:
            if len(self.performance_stats[model_name][key]) > 1000:
                self.performance_stats[model_name][key] = self.performance_stats[model_name][key][-1000:]
    
    def _record_error(self, model_name: str, error_message: str):
        """记录错误信息"""
        self.performance_stats[model_name]['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'message': error_message
        })
    
    def _check_performance_alerts(self, model_name: str, accuracy: float, error_rate: float):
        """检查性能告警"""
        # 获取历史性能
        if len(self.performance_stats[model_name]['accuracy']) > 10:
            recent_acc = np.mean(self.performance_stats[model_name]['accuracy'][-5:])
            historical_acc = np.mean(self.performance_stats[model_name]['accuracy'][:-5])
            
            # 检查准确率下降
            if historical_acc > 0 and (recent_acc / historical_acc - 1) < -self.alert_thresholds['accuracy_drop']:
                logger.warning(f"模型 {model_name} 准确率下降: {historical_acc:.4f} -> {recent_acc:.4f}")
        
        # 检查错误率
        if error_rate > self.alert_thresholds['error_rate']:
            logger.warning(f"模型 {model_name} 错误率过高: {error_rate:.4f}")
    
    def get_model_stats(self, model_name: str) -> Dict[str, Any]:
        """获取模型统计信息"""
        if model_name not in self.deployed_models:
            return {}
        
        stats = self.model_metadata[model_name].copy()
        
        # 添加实时性能统计
        if self.performance_stats[model_name]:
            stats['real_time_stats'] = {
                'avg_latency': np.mean(self.performance_stats[model_name]['latency']),
                'avg_memory': np.mean(self.performance_stats[model_name]['memory']),
                'total_predictions': len(self.performance_stats[model_name]['latency']),
                'error_count': len(self.performance_stats[model_name]['errors'])
            }
        
        return stats
    
    def list_deployed_models(self) -> List[Dict[str, Any]]:
        """列出所有已部署模型"""
        models_info = []
        
        for name, metadata in self.model_metadata.items():
            model_info = metadata.copy()
            model_info['is_active'] = (name == self.active_model)
            models_info.append(model_info)
        
        return models_info


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, check_interval: int = 300):  # 5分钟检查一次
        """
        初始化性能监控器
        
        Args:
            check_interval: 检查间隔（秒）
        """
        self.check_interval = check_interval
        self.monitoring_models = {}
        self.alert_handlers = []
        self.is_monitoring = False
        self.monitor_thread = None
        
        # 性能基准
        self.performance_baselines = {}
        
        logger.info(f"性能监控器初始化完成，检查间隔: {check_interval}秒")
    
    def add_model_to_monitor(self, model_name: str, deployer: ModelDeployer, 
                           baseline_performance: Dict[str, float] = None):
        """
        添加模型到监控列表
        
        Args:
            model_name: 模型名称
            deployer: 模型部署器实例
            baseline_performance: 性能基准
        """
        self.monitoring_models[model_name] = {
            'deployer': deployer,
            'baseline': baseline_performance or {},
            'last_check': None,
            'alert_count': 0
        }
        
        logger.info(f"添加模型到监控: {model_name}")
    
    def add_alert_handler(self, handler: Callable[[str, str, Dict[str, Any]], None]):
        """添加告警处理器"""
        self.alert_handlers.append(handler)
        logger.info("添加告警处理器")
    
    def start_monitoring(self):
        """开始监控"""
        if self.is_monitoring:
            logger.warning("监控已在运行中")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("性能监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        logger.info("性能监控已停止")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                self._check_all_models()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                time.sleep(10)  # 出错后等待10秒再继续
    
    def _check_all_models(self):
        """检查所有模型性能"""
        for model_name, monitor_info in self.monitoring_models.items():
            try:
                self._check_model_performance(model_name, monitor_info)
            except Exception as e:
                logger.error(f"检查模型 {model_name} 性能失败: {e}")
    
    def _check_model_performance(self, model_name: str, monitor_info: Dict[str, Any]):
        """检查单个模型性能"""
        deployer = monitor_info['deployer']
        baseline = monitor_info['baseline']
        
        # 获取模型统计信息
        stats = deployer.get_model_stats(model_name)
        
        if not stats or 'real_time_stats' not in stats:
            return
        
        real_time_stats = stats['real_time_stats']
        performance = stats.get('performance', {})
        
        # 检查性能指标
        alerts = []
        
        # 检查延迟
        if 'latency_ms' in baseline and real_time_stats['avg_latency'] > baseline['latency_ms'] * 1.5:
            alerts.append({
                'type': 'high_latency',
                'message': f"模型 {model_name} 延迟过高: {real_time_stats['avg_latency']:.2f}ms"
            })
        
        # 检查错误率
        if performance.get('error_rate', 0) > 0.1:  # 错误率超过10%
            alerts.append({
                'type': 'high_error_rate',
                'message': f"模型 {model_name} 错误率过高: {performance['error_rate']:.4f}"
            })
        
        # 检查内存使用
        if 'memory_mb' in baseline and real_time_stats['avg_memory'] > baseline['memory_mb'] * 1.2:
            alerts.append({
                'type': 'high_memory',
                'message': f"模型 {model_name} 内存使用过高: {real_time_stats['avg_memory']:.2f}MB"
            })
        
        # 触发告警
        for alert in alerts:
            self._trigger_alert(model_name, alert)
    
    def _trigger_alert(self, model_name: str, alert: Dict[str, Any]):
        """触发告警"""
        logger.warning(f"性能告警 - {alert['message']}")
        
        # 调用告警处理器
        for handler in self.alert_handlers:
            try:
                handler(model_name, alert['type'], alert)
            except Exception as e:
                logger.error(f"告警处理器出错: {e}")


class AutoUpdater:
    """自动更新器"""
    
    def __init__(self, deployer: ModelDeployer, update_strategy: str = 'performance_based'):
        """
        初始化自动更新器
        
        Args:
            deployer: 模型部署器
            update_strategy: 更新策略 ('performance_based', 'scheduled', 'manual')
        """
        self.deployer = deployer
        self.update_strategy = update_strategy
        self.update_history = []
        self.update_triggers = []
        
        logger.info(f"自动更新器初始化完成，策略: {update_strategy}")
    
    def add_update_trigger(self, trigger: Callable[[ModelDeployer], bool]):
        """添加更新触发器"""
        self.update_triggers.append(trigger)
        logger.info("添加更新触发器")
    
    def check_for_updates(self) -> bool:
        """检查是否需要更新"""
        if self.update_strategy == 'manual':
            return False
        
        for trigger in self.update_triggers:
            try:
                if trigger(self.deployer):
                    logger.info("检测到更新条件满足")
                    return True
            except Exception as e:
                logger.error(f"检查更新条件失败: {e}")
        
        return False
    
    def perform_update(self, new_model: Any, model_name: str, version: str) -> bool:
        """执行模型更新"""
        try:
            # 部署新模型
            success = self.deployer.deploy_model(new_model, model_name, version)
            
            if success:
                # 切换到新模型
                self.deployer.switch_model(model_name)
                
                # 记录更新历史
                self.update_history.append({
                    'model_name': model_name,
                    'version': version,
                    'update_time': datetime.now().isoformat(),
                    'strategy': self.update_strategy
                })
                
                logger.info(f"模型更新成功: {model_name} -> {version}")
                return True
            
        except Exception as e:
            logger.error(f"模型更新失败: {e}")
        
        return False
    
    def get_update_history(self) -> List[Dict[str, Any]]:
        """获取更新历史"""
        return self.update_history.copy()


def create_performance_trigger(thresholds: Dict[str, float]) -> Callable[[ModelDeployer], bool]:
    """创建性能触发条件"""
    def performance_trigger(deployer: ModelDeployer) -> bool:
        active_model = deployer.active_model
        if not active_model:
            return False
        
        stats = deployer.get_model_stats(active_model)
        performance = stats.get('performance', {})
        
        # 检查性能阈值
        if performance.get('accuracy', 1.0) < thresholds.get('min_accuracy', 0.8):
            return True
        
        if performance.get('error_rate', 0.0) > thresholds.get('max_error_rate', 0.1):
            return True
        
        return False
    
    return performance_trigger


def create_scheduled_trigger(interval_hours: int) -> Callable[[ModelDeployer], bool]:
    """创建定时触发条件"""
    last_check = datetime.now()
    
    def scheduled_trigger(deployer: ModelDeployer) -> bool:
        nonlocal last_check
        current_time = datetime.now()
        
        if (current_time - last_check).total_seconds() >= interval_hours * 3600:
            last_check = current_time
            return True
        
        return False
    
    return scheduled_trigger