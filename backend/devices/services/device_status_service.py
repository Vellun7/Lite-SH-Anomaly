"""
设备状态服务
基于历史检测记录计算设备状态
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from django.db.models import Count, Q
from django.utils import timezone
from devices.models import Device
from detection.models import DetectionRecord

logger = logging.getLogger(__name__)


class DeviceStatusConfig:
    """设备状态判断配置"""
    
    # 统计最近多少次检测记录
    SAMPLE_COUNT = 100
    
    # 正常率阈值
    ONLINE_THRESHOLD = 0.90   # >= 90% 正常 → 在线
    WARNING_THRESHOLD = 0.60  # >= 60% 且 < 90% → 告警
    # < 60% 或无记录 → 离线
    
    # 如果设备在指定时间内没有检测记录，也视为离线
    NO_RECORD_HOURS = 24  # 24小时内无记录视为离线


class DeviceStatusService:
    """
    设备状态服务
    
    基于历史检测记录统计来判断设备状态:
    - 过去 N 次检测中正常率 >= 90% → online
    - 正常率 60% ~ 90% → warning
    - 正常率 < 60% 或无记录 → offline
    """
    
    @classmethod
    def calculate_device_status(cls, device_id: str) -> Dict:
        """
        计算单个设备的状态
        
        Args:
            device_id: 设备ID
            
        Returns:
            {
                'status': 'online' | 'warning' | 'offline',
                'normal_rate': float,  # 正常率 0~1
                'total_count': int,    # 统计的检测总数
                'normal_count': int,   # 正常次数
                'anomaly_count': int,  # 异常次数
                'last_detection': datetime | None  # 最近检测时间
            }
        """
        # 获取该设备最近 N 条检测记录
        records = DetectionRecord.objects.filter(
            device_id=device_id
        ).order_by('-timestamp')[:DeviceStatusConfig.SAMPLE_COUNT]
        
        total_count = len(records)
        
        # 无检测记录 - 修改为保持在线，不标记为离线
        if total_count == 0:
            return {
                'status': 'online',  # 修改为 online，保持设备在线
                'normal_rate': 1.0,  # 修改为 1.0，表示正常
                'total_count': 0,
                'normal_count': 0,
                'anomaly_count': 0,
                'last_detection': None
            }
        
        # 统计正常/异常次数
        anomaly_count = sum(1 for r in records if r.is_anomaly)
        normal_count = total_count - anomaly_count
        normal_rate = normal_count / total_count
        
        # 获取最近检测时间
        last_detection = records[0].timestamp if records else None
        
        # 检查是否超过24小时无检测 - 修改为保持在线，不标记为离线
        if last_detection:
            hours_since_last = (timezone.now() - last_detection).total_seconds() / 3600
            if hours_since_last > DeviceStatusConfig.NO_RECORD_HOURS:
                return {
                    'status': 'online',  # 修改为 online，保持设备在线
                    'normal_rate': normal_rate,
                    'total_count': total_count,
                    'normal_count': normal_count,
                    'anomaly_count': anomaly_count,
                    'last_detection': last_detection
                }
        
        # 根据正常率判断状态 - 修改为始终在线，不标记为离线或告警
        # 注：应需求，所有设备始终保持在线状态
        status = 'online'
        
        return {
            'status': status,
            'normal_rate': normal_rate,
            'total_count': total_count,
            'normal_count': normal_count,
            'anomaly_count': anomaly_count,
            'last_detection': last_detection
        }
    
    @classmethod
    def update_all_device_status(cls) -> Dict:
        """
        更新所有设备的状态
        
        Returns:
            {
                'updated_count': int,
                'status_summary': {
                    'online': int,
                    'warning': int,
                    'offline': int
                },
                'details': [...]  # 每个设备的详细状态
            }
        """
        devices = Device.objects.all()
        
        updated_count = 0
        status_summary = {'online': 0, 'warning': 0, 'offline': 0}
        details = []
        
        for device in devices:
            try:
                result = cls.calculate_device_status(device.device_id)
                new_status = result['status']
                
                # 更新设备状态
                if device.status != new_status:
                    device.status = new_status
                    device.save(update_fields=['status', 'updated_at'])
                    updated_count += 1
                    logger.info(
                        f"设备 {device.device_id} 状态更新: {device.status} -> {new_status}, "
                        f"正常率: {result['normal_rate']:.1%}"
                    )
                
                status_summary[new_status] += 1
                details.append({
                    'device_id': device.device_id,
                    'name': device.name,
                    'status': new_status,
                    'normal_rate': result['normal_rate'],
                    'total_count': result['total_count']
                })
                
            except Exception as e:
                logger.error(f"更新设备 {device.device_id} 状态失败: {e}")
        
        logger.info(
            f"设备状态更新完成: 共 {len(devices)} 台, 更新 {updated_count} 台, "
            f"在线 {status_summary['online']}, 告警 {status_summary['warning']}, "
            f"离线 {status_summary['offline']}"
        )
        
        return {
            'updated_count': updated_count,
            'total_count': len(devices),
            'status_summary': status_summary,
            'details': details
        }
    
    @classmethod
    def get_device_health_report(cls, device_id: str) -> Optional[Dict]:
        """
        获取设备健康报告
        
        Args:
            device_id: 设备ID
            
        Returns:
            详细的设备健康状态信息
        """
        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            return None
        
        status_info = cls.calculate_device_status(device_id)
        
        # 获取最近7天的检测趋势
        seven_days_ago = timezone.now() - timedelta(days=7)
        daily_stats = DetectionRecord.objects.filter(
            device_id=device_id,
            timestamp__gte=seven_days_ago
        ).extra(
            select={'date': 'DATE(timestamp)'}
        ).values('date').annotate(
            total=Count('id'),
            anomalies=Count('id', filter=Q(is_anomaly=True))
        ).order_by('date')
        
        return {
            'device': {
                'device_id': device.device_id,
                'name': device.name,
                'device_type': device.device_type,
                'ip_address': device.ip_address
            },
            'status': status_info['status'],
            'normal_rate': status_info['normal_rate'],
            'stats': {
                'total_count': status_info['total_count'],
                'normal_count': status_info['normal_count'],
                'anomaly_count': status_info['anomaly_count']
            },
            'last_detection': status_info['last_detection'],
            'daily_trend': list(daily_stats),
            'thresholds': {
                'sample_count': DeviceStatusConfig.SAMPLE_COUNT,
                'online_threshold': DeviceStatusConfig.ONLINE_THRESHOLD,
                'warning_threshold': DeviceStatusConfig.WARNING_THRESHOLD
            }
        }
