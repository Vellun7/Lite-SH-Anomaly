"""
模型服务层
负责加载和调用检测模型，支持增量学习
"""

import os
import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from collections import deque
from datetime import datetime

import numpy as np
import joblib
from django.conf import settings
from django.utils import timezone

from common.exceptions import ModelNotLoadedException

logger = logging.getLogger(__name__)


class ModelService:
    """模型管理服务（单例模式），支持基于反馈的增量学习"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._model = None
        self._scaler = None
        self._model_version = 'v1.0'
        self._is_loaded = False

        # 增量学习状态
        self._feedback_buffer_X: List[np.ndarray] = []
        self._feedback_buffer_y: List[int] = []
        self._update_frequency = 50      # 积累多少条反馈后触发更新
        self._total_samples_learned = 0
        self._last_update_time: Optional[datetime] = None
        self._update_history: List[Dict[str, Any]] = []

    # =========================================================================
    # 模型加载
    # =========================================================================

    def load_model(self, model_path: Optional[str] = None) -> bool:
        if model_path is None:
            model_path = settings.MODEL_DIR / 'isolation_forest.joblib'

        try:
            if os.path.exists(model_path):
                model_data = joblib.load(model_path)
                if isinstance(model_data, dict) and 'model' in model_data:
                    self._model = model_data['model']
                    logger.info(f'从字典中加载模型: {model_path}')
                else:
                    self._model = model_data
                self._is_loaded = True
                self._model_version = 'v1.0'
                logger.info(f'模型加载成功: {model_path}')
                self._load_scaler()
                return True
            else:
                logger.warning(f'模型文件不存在: {model_path}，使用模拟模式')
                self._is_loaded = False
                return False
        except Exception as e:
            logger.error(f'模型加载失败: {e}')
            self._is_loaded = False
            return False

    def _load_scaler(self):
        scaler_path = settings.MODEL_DIR / 'scaler.joblib'
        try:
            if os.path.exists(scaler_path):
                self._scaler = joblib.load(scaler_path)
                logger.info(f'特征标准化器加载成功: {scaler_path}')
            else:
                logger.warning('标准化器文件不存在，预测结果可能不准确')
                self._scaler = None
        except Exception as e:
            logger.error(f'标准化器加载失败: {e}')
            self._scaler = None

    # =========================================================================
    # 预测
    # =========================================================================

    def predict(self, features: np.ndarray) -> Dict[str, Any]:
        start_time = time.time()

        if features.ndim == 1:
            features = features.reshape(1, -1)

        if self._is_loaded and self._model is not None:
            if self._scaler is not None:
                features = self._scaler.transform(features)
            else:
                logger.warning('标准化器未加载，使用原始特征进行预测')

            prediction = self._model.predict(features)[0]
            score = self._model.decision_function(features)[0]
            is_anomaly = prediction == -1
            anomaly_score = -score
        else:
            is_anomaly, anomaly_score = self._simulate_predict(features[0])

        inference_time = (time.time() - start_time) * 1000

        attack_type = self._classify_attack(features[0], anomaly_score) if is_anomaly else 'normal'
        confidence = min(abs(anomaly_score) / 0.5, 1.0) if is_anomaly else 1.0 - min(abs(anomaly_score) / 0.5, 0.5)

        return {
            'is_anomaly': bool(is_anomaly),
            'attack_type': attack_type,
            'confidence': round(float(confidence), 4),
            'anomaly_score': round(float(anomaly_score), 4),
            'inference_time': round(inference_time, 2),
            'model_version': self._model_version
        }

    def predict_batch(self, features_batch: np.ndarray) -> List[Dict[str, Any]]:
        results = []
        for features in features_batch:
            result = self.predict(features)
            results.append(result)
        return results

    # =========================================================================
    # 增量学习：反馈收集与模型更新
    # =========================================================================

    def submit_feedback(self, record_id: int, is_anomaly: bool) -> Dict[str, Any]:
        """
        提交检测结果的用户反馈，用于增量学习

        Args:
            record_id: 检测记录ID
            is_anomaly: 人工确认结果 (True=确实是异常, False=误报/实际正常)

        Returns:
            反馈处理结果
        """
        from detection.models import DetectionRecord

        try:
            record = DetectionRecord.objects.get(id=record_id)
        except DetectionRecord.DoesNotExist:
            return {'success': False, 'message': f'检测记录 {record_id} 不存在'}

        # 更新记录的反馈标签
        record.feedback_label = is_anomaly
        record.feedback_at = timezone.now()
        record.save(update_fields=['feedback_label', 'feedback_at'])

        # 从记录中重建特征向量（用于增量训练）
        features = self._extract_features_from_record(record)
        label = 1 if is_anomaly else 0  # 0=正常, 1=异常

        self._feedback_buffer_X.append(features)
        self._feedback_buffer_y.append(label)

        logger.info(
            f'收到反馈: record={record_id}, '
            f'模型判定={"异常" if record.is_anomaly else "正常"}, '
            f'人工确认={"异常" if is_anomaly else "正常"}, '
            f'缓冲区: {len(self._feedback_buffer_X)}/{self._update_frequency}'
        )

        # 检查是否需要触发增量更新
        update_triggered = self._check_and_update()

        return {
            'success': True,
            'record_id': record_id,
            'feedback_label': '已确认异常' if is_anomaly else '已纠正(误报)',
            'buffer_size': len(self._feedback_buffer_X),
            'update_frequency': self._update_frequency,
            'update_triggered': update_triggered,
        }

    def _extract_features_from_record(self, record) -> np.ndarray:
        """从 DetectionRecord 中提取与训练时一致的特征向量"""
        orig_bytes = float(record.orig_bytes)
        resp_bytes = float(record.resp_bytes)
        orig_pkts = float(record.orig_pkts)
        resp_pkts = float(record.resp_pkts)
        duration = float(record.duration)
        src_port = record.src_port or 0
        dst_port = record.dst_port or 0

        # IP字节数估算
        orig_ip_bytes = orig_bytes * 1.1
        resp_ip_bytes = resp_bytes * 1.1

        # 协议编码
        proto_map = {'tcp': 0, 'udp': 1, 'icmp': 2}
        proto_encoded = proto_map.get(record.protocol.lower(), 0)

        # 服务编码
        service_map = {80: 1, 8080: 1, 443: 2, 1883: 3, 22: 4}
        service_encoded = service_map.get(dst_port, 0)

        # 连接状态编码
        state_map = {'REJ': 0, 'RSTO': 1, 'RSTOS0': 2, 'S0': 3, 'SF': 4, 'SH': 5, 'SHR': 6, 'OTH': 7}
        conn_state_encoded = state_map.get('SF', 4)  # 默认SF

        # 衍生特征
        bytes_ratio = orig_bytes / (resp_bytes + 1)
        pkts_ratio = orig_pkts / (resp_pkts + 1)
        bytes_per_second = orig_bytes / (duration + 0.001)
        pkts_per_second = orig_pkts / (duration + 0.001)

        return np.array([
            duration, orig_bytes, resp_bytes, orig_pkts, resp_pkts,
            orig_ip_bytes, resp_ip_bytes, proto_encoded, service_encoded,
            conn_state_encoded, bytes_ratio, pkts_ratio, bytes_per_second, pkts_per_second
        ], dtype=np.float32)

    def _check_and_update(self) -> bool:
        """检查是否满足增量更新条件，满足则触发重训"""
        if len(self._feedback_buffer_X) < self._update_frequency:
            return False

        self._retrain_model()
        return True

    def _retrain_model(self):
        """
        增量重训模型

        策略说明：
        - 孤立森林是无监督模型，仅用正常样本训练
        - 从反馈缓冲区筛出人工确认为正常的样本（feedback_label=False，即误报纠正）
        - 如果正常样本不足，则不做增量更新，仅清除缓冲区
        - 使用 sklearn IF 的 fit 在新累积的正常样本上训练（相当于用新数据更新分布认知）
        """
        X_buffer = np.array(self._feedback_buffer_X)
        y_buffer = np.array(self._feedback_buffer_y)

        # 仅保留人工确认为正常的样本（y=0）
        normal_mask = y_buffer == 0
        X_normal_new = X_buffer[normal_mask]

        logger.info(
            f'增量更新：缓冲区共 {len(X_buffer)} 条，'
            f'其中正常 {np.sum(normal_mask)} 条，异常 {np.sum(~normal_mask)} 条'
        )

        if len(X_normal_new) < 10:
            logger.warning('新增正常样本不足 10 条，跳过增量更新，清空缓冲区')
            self._feedback_buffer_X.clear()
            self._feedback_buffer_y.clear()
            return

        # 标准化
        if self._scaler is not None:
            X_normal_new = self._scaler.transform(X_normal_new)

        # 在当前模型的基础上继续训练
        # sklearn IsolationForest 不支持 partial_fit，这里使用重新拟合
        # 注意：这会使模型适应当前累积的正常行为分布
        try:
            from sklearn.ensemble import IsolationForest as SklearnIF

            # 获取当前模型参数
            current_params = self._model.get_params()
            # 只保留构造参数中有意义的
            safe_params = {
                'n_estimators': current_params.get('n_estimators', 100),
                'max_samples': current_params.get('max_samples', 256),
                'contamination': current_params.get('contamination', 0.2),
                'max_features': current_params.get('max_features', 1.0),
                'bootstrap': current_params.get('bootstrap', False),
                'random_state': current_params.get('random_state', 42),
                'n_jobs': current_params.get('n_jobs', 1),
            }

            new_model = SklearnIF(**safe_params)
            new_model.fit(X_normal_new)

            # 替换模型
            self._model = new_model

            # 更新版本号
            self._model_version = self._increment_version(self._model_version)
            self._total_samples_learned += len(X_normal_new)
            self._last_update_time = timezone.now()

            self._update_history.append({
                'version': self._model_version,
                'samples_added': len(X_normal_new),
                'buffer_size': len(X_buffer),
                'timestamp': self._last_update_time.isoformat(),
            })

            # 保存更新后的模型到文件
            self._save_updated_model()

            logger.info(
                f'增量更新完成: 版本 {self._model_version}, '
                f'新增正常样本 {len(X_normal_new)} 条, '
                f'已累计学习 {self._total_samples_learned} 条'
            )

        except Exception as e:
            logger.error(f'增量更新失败: {e}')

        # 清空缓冲区
        self._feedback_buffer_X.clear()
        self._feedback_buffer_y.clear()

    def _save_updated_model(self):
        """保存更新后的模型到文件"""
        model_path = settings.MODEL_DIR / 'isolation_forest.joblib'
        try:
            model_data = {
                'model': self._model,
                'params': {
                    'n_estimators': self._model.get_params().get('n_estimators', 100),
                    'contamination': self._model.get_params().get('contamination', 0.2),
                    'max_samples': self._model.get_params().get('max_samples', 256),
                },
                'incremental_info': {
                    'version': self._model_version,
                    'total_samples_learned': self._total_samples_learned,
                    'last_update_time': self._last_update_time.isoformat() if self._last_update_time else None,
                    'update_count': len(self._update_history),
                }
            }
            joblib.dump(model_data, model_path, compress=3)
            logger.info(f'更新后的模型已保存: {model_path}')
        except Exception as e:
            logger.error(f'保存更新模型失败: {e}')

    def _increment_version(self, version_str: str) -> str:
        """递增版本号: v1.0 -> v1.1"""
        match = re.match(r'v(\d+)\.(\d+)', version_str)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            return f'v{major}.{minor + 1}'
        return f'{version_str}_inc1'

    # =========================================================================
    # 增量学习状态查询
    # =========================================================================

    def get_incremental_status(self) -> Dict[str, Any]:
        """获取增量学习当前状态"""
        return {
            'feedback_buffer_size': len(self._feedback_buffer_X),
            'update_frequency': self._update_frequency,
            'total_samples_learned': self._total_samples_learned,
            'model_version': self._model_version,
            'last_update_time': self._last_update_time.isoformat() if self._last_update_time else None,
            'is_ready_to_update': len(self._feedback_buffer_X) >= self._update_frequency,
            'update_history': self._update_history[-10:],  # 最近10条更新记录
        }

    def force_update(self) -> Dict[str, Any]:
        """手动强制触发增量更新"""
        if len(self._feedback_buffer_X) == 0:
            return {'success': False, 'message': '反馈缓冲区为空，无需更新'}

        self._retrain_model()
        return {
            'success': True,
            'new_version': self._model_version,
            'total_samples_learned': self._total_samples_learned,
        }

    # =========================================================================
    # 模拟预测（开发调试用）
    # =========================================================================

    def _simulate_predict(self, features: np.ndarray) -> tuple:
        anomaly_score = 0.0
        if len(features) > 1 and features[1] > 10000:
            anomaly_score += 0.3
        if len(features) > 3 and features[3] > 100:
            anomaly_score += 0.2
        if len(features) > 0 and features[0] < 0.1 and len(features) > 1 and features[1] > 1000:
            anomaly_score += 0.3
        anomaly_score += np.random.uniform(-0.1, 0.1)
        is_anomaly = anomaly_score > 0.3
        return is_anomaly, anomaly_score

    def _classify_attack(self, features: np.ndarray, score: float) -> str:
        if len(features) < 4:
            return 'unknown'
        orig_bytes = features[1] if len(features) > 1 else 0
        orig_pkts = features[3] if len(features) > 3 else 0
        duration = features[0] if len(features) > 0 else 0
        if orig_pkts > 50 and duration < 1:
            return 'ddos'
        if duration < 0.01 and orig_bytes < 100:
            return 'port_scan'
        if len(features) > 2 and features[2] > 50000:
            return 'unauthorized'
        if score > 0.5:
            return 'malformed'
        return 'unknown'

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def model_version(self) -> str:
        return self._model_version


# 全局模型服务实例
model_service = ModelService()
