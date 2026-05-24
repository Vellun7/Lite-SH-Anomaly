"""
检测业务逻辑层
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from django.db.models import Avg, Case, CharField, Count, IntegerField, Q, Value, When
from django.db.models.functions import TruncDay, TruncHour, TruncMonth, TruncWeek
from django.utils import timezone

from detection.models import DetectionRecord, DetectionTask
from detection.services.model_service import model_service
from devices.services import DeviceService
from devices.services.security_service import DeviceSecurityService
from logs.services import AlertService
from common.exceptions import InvalidDataException

logger = logging.getLogger(__name__)


class DetectionService:
    """异常检测服务"""
    
    # 特征字段映射（与模型训练时保持一致）
    FEATURE_COLUMNS = [
        'duration', 'orig_bytes', 'resp_bytes', 'orig_pkts', 'resp_pkts',
        'orig_ip_bytes', 'resp_ip_bytes', 'proto_encoded', 'service_encoded',
        'conn_state_encoded', 'bytes_ratio', 'pkts_ratio', 'bytes_per_second', 'pkts_per_second'
    ]
    
    @staticmethod
    def detect_single(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        单条数据检测
        
        Args:
            data: 包含设备信息和流量特征的字典
        
        Returns:
            检测结果
        """
        # 提取特征
        features = DetectionService._extract_features(data)
        
        # 模型预测
        result = model_service.predict(features)
        
        # 保存检测记录
        record = DetectionService._save_record(data, result)
        
        # 更新设备统计（忽略设备不存在的情况）
        device_id = data.get('device_id', 'unknown')
        try:
            DeviceService.update_device_stats(device_id, result['is_anomaly'])
        except Exception as e:
            logger.warning(f'更新设备统计失败: {e}')
        
        # 根据检测结果更新设备状态
        score_change_info = None
        if result['is_anomaly']:
            try:
                DeviceService.update_device_status(device_id, 'warning')
            except Exception as e:
                logger.warning(f'更新设备状态失败: {e}')
            try:
                AlertService.create_alert_from_detection(record, result)
            except Exception as e:
                logger.warning(f'创建告警失败: {e}')
            
            # 检测到异常时自动更新设备安全评分
            try:
                score_result = DeviceSecurityService.update_device_security_score(device_id)
                score_change_info = {
                    'old_score': round(score_result['old_score'], 1),
                    'new_score': round(score_result['new_score'], 1),
                    'score_change': round(score_result['score_change'], 1),
                    'security_level': score_result['security_level']
                }
                logger.info(f'设备 {device_id} 安全评分已更新: {score_result["old_score"]:.1f} -> {score_result["new_score"]:.1f}')
            except Exception as e:
                logger.warning(f'更新设备安全评分失败: {e}')
        else:
            # 检测正常，恢复设备状态为在线
            try:
                DeviceService.update_device_status(device_id, 'online')
            except Exception as e:
                logger.warning(f'恢复设备状态失败: {e}')
        
        return {
            'record_id': record.id,
            'score_change': score_change_info,
            **result
        }
    
    @staticmethod
    def detect_batch(data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量数据检测"""
        results = []
        anomaly_count = 0
        
        for data in data_list:
            result = DetectionService.detect_single(data)
            results.append(result)
            if result['is_anomaly']:
                anomaly_count += 1
        
        return {
            'total': len(results),
            'anomaly_count': anomaly_count,
            'normal_count': len(results) - anomaly_count,
            'results': results
        }
    
    @staticmethod
    def detect_from_csv(file_path: str, task_id: str = None) -> Dict[str, Any]:
        """从CSV文件批量检测"""
        if task_id is None:
            task_id = str(uuid.uuid4())[:8]
        
        # 创建任务记录
        task = DetectionTask.objects.create(
            task_id=task_id,
            file_name=file_path,
            status=DetectionTask.TaskStatus.RUNNING,
            started_at=timezone.now()
        )
        
        try:
            # 读取CSV
            df = pd.read_csv(file_path)
            task.total_count = len(df)
            task.save()
            
            anomaly_count = 0
            
            for idx, row in df.iterrows():
                data = row.to_dict()
                result = DetectionService.detect_single(data)
                
                if result['is_anomaly']:
                    anomaly_count += 1
                
                task.processed_count = idx + 1
                task.anomaly_count = anomaly_count
                task.save()
            
            task.status = DetectionTask.TaskStatus.COMPLETED
            task.completed_at = timezone.now()
            task.save()
            
            return {
                'task_id': task_id,
                'status': 'completed',
                'total': task.total_count,
                'anomaly_count': anomaly_count
            }
            
        except Exception as e:
            task.status = DetectionTask.TaskStatus.FAILED
            task.error_message = str(e)
            task.save()
            raise InvalidDataException(f'CSV处理失败: {e}')
    
    @staticmethod
    def get_detection_records(
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ):
        """查询检测记录"""
        queryset = DetectionRecord.objects.all()
        
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        if attack_type:
            queryset = queryset.filter(attack_type=attack_type)
        if is_anomaly is not None:
            queryset = queryset.filter(is_anomaly=is_anomaly)
        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)
        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)
        
        return queryset
    
    @staticmethod
    def get_statistics(days: int = 7) -> Dict[str, Any]:
        """获取检测统计数据"""
        end_time = timezone.now()
        # days=7 表示最近7天（今天+前6天），所以start_time = end_time - (days-1)天
        start_time = end_time - timedelta(days=days-1)
        start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        records = DetectionRecord.objects.filter(timestamp__gte=start_time)
        
        total = records.count()
        anomaly = records.filter(is_anomaly=True).count()
        normal = total - anomaly
        
        # 按攻击类型统计
        attack_stats = records.filter(is_anomaly=True).values('attack_type').annotate(
            count=Count('id')
        )
        
        # 按天统计趋势
        daily_stats = records.extra(
            select={'date': 'date(timestamp)'}
        ).values('date').annotate(
            total=Count('id'),
            anomaly=Count('id', filter=Q(is_anomaly=True))
        ).order_by('date')
        
        # 平均推理时间
        avg_inference_time = records.aggregate(avg=Avg('inference_time'))['avg'] or 0
        
        return {
            'total': total,
            'anomaly': anomaly,
            'normal': normal,
            'anomaly_rate': round(anomaly / total * 100, 2) if total > 0 else 0,
            'attack_distribution': list(attack_stats),
            'daily_trend': list(daily_stats),
            'avg_inference_time': round(avg_inference_time, 2)
        }

    @staticmethod
    def _normalize_monitoring_range(
        start_time: Optional[datetime],
        end_time: Optional[datetime]
    ) -> Dict[str, datetime]:
        if end_time is None:
            end_time = timezone.now()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        return {
            'start_time': start_time,
            'end_time': end_time,
        }

    @staticmethod
    def _apply_monitoring_filters(
        queryset,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
    ):
        time_range = DetectionService._normalize_monitoring_range(start_time, end_time)
        queryset = queryset.filter(
            timestamp__gte=time_range['start_time'],
            timestamp__lte=time_range['end_time'],
        )
        if device_id:
            queryset = queryset.filter(device_id=device_id)
        if attack_type:
            queryset = queryset.filter(attack_type=attack_type)
        if protocol:
            queryset = queryset.filter(protocol__iexact=protocol)
        if is_anomaly is not None:
            queryset = queryset.filter(is_anomaly=is_anomaly)
        return queryset

    @staticmethod
    def get_monitoring_kpi(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        records = DetectionService._apply_monitoring_filters(
            DetectionRecord.objects.all(),
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            attack_type=attack_type,
            protocol=protocol,
            is_anomaly=is_anomaly,
        )
        total = records.count()
        anomaly = records.filter(is_anomaly=True).count()
        aggregates = records.aggregate(
            avg_confidence=Avg('confidence'),
            avg_anomaly_score=Avg('anomaly_score'),
            avg_inference_time=Avg('inference_time'),
        )
        return {
            'total_detections': total,
            'anomaly_count': anomaly,
            'anomaly_rate': round(anomaly / total * 100, 2) if total > 0 else 0,
            'avg_confidence': round(aggregates['avg_confidence'] or 0, 4),
            'avg_anomaly_score': round(aggregates['avg_anomaly_score'] or 0, 4),
            'avg_inference_time': round(aggregates['avg_inference_time'] or 0, 2),
        }

    @staticmethod
    def get_anomaly_trend(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        granularity: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        records = DetectionService._apply_monitoring_filters(
            DetectionRecord.objects.all(),
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            attack_type=attack_type,
            protocol=protocol,
            is_anomaly=is_anomaly,
        )

        granularity = granularity or 'day'
        trunc_map = {
            'hour': TruncHour('timestamp'),
            'day': TruncDay('timestamp'),
            'week': TruncWeek('timestamp'),
            'month': TruncMonth('timestamp'),
        }
        trunc = trunc_map.get(granularity, TruncDay('timestamp'))
        period_format = {
            'hour': '%Y-%m-%d %H:00',
            'day': '%Y-%m-%d',
            'week': '%Y-%m-%d',
            'month': '%Y-%m',
        }
        date_format = period_format.get(granularity, '%Y-%m-%d')

        trend = (
            records.annotate(period=trunc)
            .values('period')
            .annotate(
                total=Count('id'),
                anomaly=Count('id', filter=Q(is_anomaly=True))
            )
            .order_by('period')
        )

        return [
            {
                'period': item['period'].strftime(date_format) if item['period'] else '',
                'total': item['total'],
                'anomaly': item['anomaly'],
            }
            for item in trend
        ]

    @staticmethod
    def get_device_risk_ranking(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        records = DetectionService._apply_monitoring_filters(
            DetectionRecord.objects.all(),
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            attack_type=attack_type,
            protocol=protocol,
            is_anomaly=is_anomaly,
        )

        ranking = (
            records.values('device_id')
            .annotate(
                total=Count('id'),
                anomaly=Count('id', filter=Q(is_anomaly=True))
            )
            .order_by('-anomaly', '-total')
        )

        result = []
        for item in ranking:
            total = item['total']
            anomaly = item['anomaly']
            result.append({
                'device_id': item['device_id'],
                'total': total,
                'anomaly': anomaly,
                'anomaly_rate': round(anomaly / total * 100, 2) if total > 0 else 0,
            })
        return result

    @staticmethod
    def get_score_confidence_analysis(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        records = DetectionService._apply_monitoring_filters(
            DetectionRecord.objects.all(),
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            attack_type=attack_type,
            protocol=protocol,
            is_anomaly=is_anomaly,
        )

        points = records.values('anomaly_score', 'confidence', 'is_anomaly').order_by('-timestamp')[:500]
        return [
            {
                'anomaly_score': float(item['anomaly_score'] or 0),
                'confidence': float(item['confidence'] or 0),
                'is_anomaly': item['is_anomaly'],
            }
            for item in points
        ]

    @staticmethod
    def get_traffic_feature_association(
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        device_id: Optional[str] = None,
        attack_type: Optional[str] = None,
        protocol: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        records = DetectionService._apply_monitoring_filters(
            DetectionRecord.objects.all(),
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,
            attack_type=attack_type,
            protocol=protocol,
            is_anomaly=is_anomaly,
        )

        bucket_case = Case(
            When(orig_bytes__lt=1024, then=Value('0-1KB')),
            When(orig_bytes__lt=10240, then=Value('1-10KB')),
            When(orig_bytes__lt=102400, then=Value('10-100KB')),
            default=Value('100KB+'),
            output_field=CharField(),
        )

        stats = (
            records.annotate(bucket=bucket_case)
            .values('bucket')
            .annotate(
                total=Count('id'),
                anomaly=Count('id', filter=Q(is_anomaly=True))
            )
        )

        order_map = {
            '0-1KB': 0,
            '1-10KB': 1,
            '10-100KB': 2,
            '100KB+': 3,
        }

        result = []
        for item in stats:
            total = item['total']
            anomaly = item['anomaly']
            result.append({
                'bucket': item['bucket'],
                'total': total,
                'anomaly': anomaly,
                'anomaly_rate': round(anomaly / total * 100, 2) if total > 0 else 0,
            })

        return sorted(result, key=lambda item: order_map.get(item['bucket'], 99))
    
    @staticmethod
    def _extract_features(data: Dict[str, Any]) -> np.ndarray:
        """从数据中提取特征向量（14个特征，与模型训练一致）"""
        features = []
        
        # 基础特征
        duration = float(data.get('duration', 0))
        orig_bytes = float(data.get('orig_bytes', 0))
        resp_bytes = float(data.get('resp_bytes', 0))
        orig_pkts = float(data.get('orig_pkts', 0))
        resp_pkts = float(data.get('resp_pkts', 0))
        
        features.append(duration)
        features.append(orig_bytes)
        features.append(resp_bytes)
        features.append(orig_pkts)
        features.append(resp_pkts)
        
        # IP字节数（如果没有则用orig_bytes/resp_bytes估算）
        orig_ip_bytes = float(data.get('orig_ip_bytes', orig_bytes * 1.1))
        resp_ip_bytes = float(data.get('resp_ip_bytes', resp_bytes * 1.1))
        features.append(orig_ip_bytes)
        features.append(resp_ip_bytes)
        
        # 协议编码（与训练时 LabelEncoder 一致：tcp=0, udp=1）
        proto = data.get('protocol', 'tcp').lower()
        proto_map = {'tcp': 0, 'udp': 1, 'icmp': 2}
        features.append(proto_map.get(proto, 0))
        
        # 服务编码（与训练时 LabelEncoder 一致：-=0, http=1, https=2, mqtt=3, ssh=4）
        dst_port = int(data.get('dst_port', 0))
        service_map = {80: 1, 8080: 1, 443: 2, 1883: 3, 22: 4}
        features.append(service_map.get(dst_port, 0))
        
        # 连接状态编码（与训练时 LabelEncoder 一致：REJ=0, RSTO=1, RSTOS0=2, S0=3, SF=4）
        conn_state = data.get('conn_state', 'SF')
        state_map = {'REJ': 0, 'RSTO': 1, 'RSTOS0': 2, 'S0': 3, 'SF': 4, 'SH': 5, 'SHR': 6, 'OTH': 7}
        features.append(state_map.get(conn_state, 4))
        
        # 衍生特征（与训练时 DataPreprocessor.extract_features 中的公式保持一致）
        bytes_ratio = orig_bytes / (resp_bytes + 1)
        pkts_ratio = orig_pkts / (resp_pkts + 1)
        bytes_per_second = orig_bytes / (duration + 0.001)
        pkts_per_second = orig_pkts / (duration + 0.001)
        
        features.append(bytes_ratio)
        features.append(pkts_ratio)
        features.append(bytes_per_second)
        features.append(pkts_per_second)
        
        return np.array(features, dtype=np.float32)
    
    @staticmethod
    def _save_record(data: Dict[str, Any], result: Dict[str, Any]) -> DetectionRecord:
        """保存检测记录"""
        record = DetectionRecord.objects.create(
            device_id=data.get('device_id', 'unknown'),
            timestamp=data.get('timestamp', timezone.now()),
            src_ip=data.get('src_ip', '0.0.0.0'),
            dst_ip=data.get('dst_ip', '0.0.0.0'),
            src_port=data.get('src_port'),
            dst_port=data.get('dst_port'),
            protocol=data.get('protocol', 'TCP'),
            duration=data.get('duration', 0),
            orig_bytes=data.get('orig_bytes', 0),
            resp_bytes=data.get('resp_bytes', 0),
            orig_pkts=data.get('orig_pkts', 0),
            resp_pkts=data.get('resp_pkts', 0),
            is_anomaly=result['is_anomaly'],
            attack_type=result['attack_type'],
            confidence=result['confidence'],
            anomaly_score=result['anomaly_score'],
            model_version=result['model_version'],
            inference_time=result['inference_time']
        )
        return record