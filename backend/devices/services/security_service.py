"""
设备安全评分计算服务
"""

import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Q, Avg

from devices.models import Device
from detection.models import DetectionRecord


class DeviceSecurityService:
    """设备安全评分服务"""
    
    # 评分参数配置
    DECAY_LAMBDA = 0.1  # 时间衰减系数
    MAX_SCORE = 100.0   # 最高评分
    MIN_SCORE = 0.0     # 最低评分
    
    # 异常类型严重程度配置（用于加权异常率计算）
    ANOMALY_SEVERITY = {
        'ddos': 1.5,          # DDoS攻击 - 严重
        'port_scan': 1.2,     # 端口扫描 - 中等
        'unauthorized': 1.4,  # 越权访问 - 较严重
        'malformed': 1.1,     # 异常指令 - 轻微
        'unknown': 1.0,       # 未知威胁 - 基准
    }
    
    @staticmethod
    def calculate_device_security_score(device_id: str, days: int = 30) -> float:
        """
        计算设备安全评分
        
        基于异常率的评分算法：
        - 安全评分 = 100 * (1 - 加权异常率)
        - 加权异常率 = 加权异常次数 / 总检测次数
        - 近期异常权重更高（时间衰减）
        
        Args:
            device_id: 设备ID
            days: 计算天数范围
            
        Returns:
            安全评分 (0-100)
        """
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # 获取总检测记录数
        total_records = DetectionRecord.objects.filter(
            device_id=device_id,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).count()
        
        if total_records == 0:
            # 无检测记录，返回默认满分
            return DeviceSecurityService.MAX_SCORE
        
        # 获取异常记录
        anomaly_records = DetectionRecord.objects.filter(
            device_id=device_id,
            is_anomaly=True,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        )
        
        anomaly_count = anomaly_records.count()
        
        if anomaly_count == 0:
            return DeviceSecurityService.MAX_SCORE
        
        # 计算加权异常分数（考虑异常类型严重程度和时间衰减）
        weighted_anomaly_score = 0.0
        
        for record in anomaly_records:
            # 计算时间差（天数）
            days_ago = (end_date - record.timestamp).days
            
            # 时间衰减因子：近期异常权重更高
            # 今天的异常权重为1，30天前的约为0.05
            decay_factor = math.exp(-DeviceSecurityService.DECAY_LAMBDA * days_ago)
            
            # 获取异常类型严重程度
            severity = DeviceSecurityService.ANOMALY_SEVERITY.get(
                record.attack_type, 
                DeviceSecurityService.ANOMALY_SEVERITY['unknown']
            )
            
            # 结合置信度
            confidence = record.confidence if record.confidence > 0 else 0.5
            
            # 累加加权异常分数
            weighted_anomaly_score += decay_factor * severity * confidence
        
        # 计算基准异常率（不考虑权重时的理论最大加权分数）
        # 假设所有记录都是今天的、最严重的异常，最大加权分数约为 total_records * 1.5
        max_possible_weighted_score = total_records * 1.5
        
        # 计算加权异常率（归一化到 0-1）
        weighted_anomaly_rate = min(1.0, weighted_anomaly_score / max_possible_weighted_score)
        
        # 计算最终评分：异常率越高，评分越低
        # 使用平方根函数使评分变化更平缓
        final_score = DeviceSecurityService.MAX_SCORE * (1 - math.sqrt(weighted_anomaly_rate))
        
        # 确保评分在有效范围内
        return max(DeviceSecurityService.MIN_SCORE, 
                  min(DeviceSecurityService.MAX_SCORE, round(final_score, 2)))
    
    @staticmethod
    def update_device_security_score(device_id: str) -> Dict[str, Any]:
        """更新设备安全评分"""
        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            raise ValueError(f'设备 {device_id} 不存在')
        
        # 计算新的安全评分
        new_score = DeviceSecurityService.calculate_device_security_score(device_id)
        old_score = device.security_score
        
        # 更新设备评分
        device.security_score = new_score
        device.last_score_update = timezone.now()
        device.save()
        
        return {
            'device_id': device_id,
            'old_score': old_score,
            'new_score': new_score,
            'score_change': new_score - old_score,
            'security_level': device.security_level,
            'updated_at': device.last_score_update
        }
    
    @staticmethod
    def batch_update_security_scores(device_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """批量更新设备安全评分"""
        if device_ids is None:
            devices = Device.objects.all()
        else:
            devices = Device.objects.filter(device_id__in=device_ids)
        
        success_count = 0
        results = []
        
        for device in devices:
            try:
                result = DeviceSecurityService.update_device_security_score(device.device_id)
                results.append(result)
                success_count += 1
            except Exception as e:
                results.append({
                    'device_id': device.device_id,
                    'error': str(e)
                })
        
        return {
            'total_devices': devices.count(),
            'success_count': success_count,
            'results': results
        }
    
    @staticmethod
    def get_security_score_history(device_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取设备安全评分历史趋势"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # 按天分组统计异常记录
        daily_anomalies = DetectionRecord.objects.filter(
            device_id=device_id,
            is_anomaly=True,
            timestamp__gte=start_date,
            timestamp__lte=end_date
        ).extra(
            select={'day': 'date(timestamp)'}
        ).values('day').annotate(
            anomaly_count=Count('id'),
            avg_confidence=Avg('confidence')
        ).order_by('day')
        
        # 构建每日评分历史
        history = []
        current_date = start_date.date()
        
        # 创建异常记录字典以便快速查找
        anomaly_dict = {item['day']: item for item in daily_anomalies}
        
        while current_date <= end_date.date():
            day_str = current_date.strftime('%Y-%m-%d')
            
            # 计算该日期的累积评分
            daily_records = DetectionRecord.objects.filter(
                device_id=device_id,
                is_anomaly=True,
                timestamp__date__lte=current_date,
                timestamp__gte=start_date
            )
            
            # 简化计算：基于该日期前的所有异常记录计算评分
            score = DeviceSecurityService._calculate_score_for_date(
                device_id, current_date, start_date
            )
            
            anomaly_info = anomaly_dict.get(current_date, {})
            
            history.append({
                'date': day_str,
                'security_score': round(score, 2),
                'anomaly_count': anomaly_info.get('anomaly_count', 0),
                'avg_confidence': round(anomaly_info.get('avg_confidence', 0) or 0, 2)
            })
            
            current_date += timedelta(days=1)
        
        return history
    
    @staticmethod
    def _calculate_score_for_date(device_id: str, target_date: datetime.date, 
                                 start_date: datetime) -> float:
        """计算特定日期的安全评分（用于历史趋势）"""
        target_datetime = timezone.make_aware(
            datetime.combine(target_date, datetime.max.time())
        )
        
        # 获取截至该日期的总检测记录数
        total_records = DetectionRecord.objects.filter(
            device_id=device_id,
            timestamp__gte=start_date,
            timestamp__lte=target_datetime
        ).count()
        
        if total_records == 0:
            return DeviceSecurityService.MAX_SCORE
        
        # 获取异常记录
        anomaly_records = DetectionRecord.objects.filter(
            device_id=device_id,
            is_anomaly=True,
            timestamp__gte=start_date,
            timestamp__lte=target_datetime
        )
        
        if not anomaly_records.exists():
            return DeviceSecurityService.MAX_SCORE
        
        # 计算加权异常分数
        weighted_anomaly_score = 0.0
        
        for record in anomaly_records:
            days_ago = (target_datetime - record.timestamp).days
            decay_factor = math.exp(-DeviceSecurityService.DECAY_LAMBDA * days_ago)
            
            severity = DeviceSecurityService.ANOMALY_SEVERITY.get(
                record.attack_type, 
                DeviceSecurityService.ANOMALY_SEVERITY['unknown']
            )
            
            confidence = record.confidence if record.confidence > 0 else 0.5
            weighted_anomaly_score += decay_factor * severity * confidence
        
        # 计算加权异常率
        max_possible_weighted_score = total_records * 1.5
        weighted_anomaly_rate = min(1.0, weighted_anomaly_score / max_possible_weighted_score)
        
        # 计算最终评分
        final_score = DeviceSecurityService.MAX_SCORE * (1 - math.sqrt(weighted_anomaly_rate))
        
        return max(DeviceSecurityService.MIN_SCORE, 
                  min(DeviceSecurityService.MAX_SCORE, round(final_score, 2)))
    
    @staticmethod
    def get_security_overview() -> Dict[str, Any]:
        """获取安全评分概览统计"""
        devices = Device.objects.all()
        
        if not devices.exists():
            return {
                'total_devices': 0,
                'avg_score': 0,
                'high_security': 0,
                'medium_security': 0,
                'low_security': 0,
                'score_distribution': []
            }
        
        # 统计不同安全等级的设备数量
        high_security = devices.filter(security_score__gte=90).count()
        medium_security = devices.filter(
            security_score__gte=70, 
            security_score__lt=90
        ).count()
        low_security = devices.filter(security_score__lt=70).count()
        
        # 计算平均评分
        avg_score = devices.aggregate(avg=Avg('security_score'))['avg'] or 0
        
        # 评分分布（按10分为一档）
        score_distribution = []
        for i in range(0, 101, 10):
            count = devices.filter(
                security_score__gte=i,
                security_score__lt=i+10 if i < 100 else 101
            ).count()
            score_distribution.append({
                'range': f'{i}-{i+9 if i < 100 else 100}',
                'count': count
            })
        
        return {
            'total_devices': devices.count(),
            'avg_score': round(avg_score, 2),
            'high_security': high_security,
            'medium_security': medium_security,
            'low_security': low_security,
            'score_distribution': score_distribution
        }