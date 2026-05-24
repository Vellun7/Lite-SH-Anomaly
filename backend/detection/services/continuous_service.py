# -*- coding: utf-8 -*-
"""
持续检测后台服务

使用后台线程实现持续检测功能，配置持久化到数据库。
支持应用重启后自动恢复持续检测状态。
"""

import logging
import random
import threading
from typing import Dict, Any, List, Optional

from django.utils import timezone
from users.models import AuditLog

logger = logging.getLogger(__name__)


class ContinuousDetectionService:
    """
    持续检测服务（单例模式）

    职责:
    - 管理后台检测线程的启停
    - 从数据库读取/写入配置
    - 按间隔执行检测并更新统计
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        """当前是否正在运行"""
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_config(self) -> Dict[str, Any]:
        """获取当前持续检测配置和状态"""
        from detection.models import ContinuousDetectionConfig

        config = ContinuousDetectionConfig.get_instance()
        return {
            'enabled': config.enabled,
            'interval': config.interval,
            'target_devices': config.target_devices,
            'total_detections': config.total_detections,
            'total_anomalies': config.total_anomalies,
            'started_at': config.started_at.isoformat() if config.started_at else None,
            'updated_at': config.updated_at.isoformat() if config.updated_at else None,
            'is_running': self.is_running,
        }

    def start(self, interval: int = 5, target_devices: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        启动持续检测

        Args:
            interval: 检测间隔(秒)
            target_devices: 目标设备ID列表，为空则检测所有非离线设备

        Returns:
            当前配置状态
        """
        from detection.models import ContinuousDetectionConfig

        # 如果已在运行，先停止
        if self.is_running:
            self._stop_thread()

        # 更新数据库配置
        config = ContinuousDetectionConfig.get_instance()
        config.enabled = True
        config.interval = interval
        config.target_devices = target_devices or []
        config.started_at = timezone.now()
        config.save()

        # 启动后台线程
        self._start_thread(interval, target_devices or [])

        logger.info(f'持续检测已启动，间隔 {interval} 秒，目标设备: {target_devices or "全部"}')
        return self.get_config()

    def stop(self) -> Dict[str, Any]:
        """停止持续检测"""
        from detection.models import ContinuousDetectionConfig

        self._stop_thread()

        # 更新数据库配置
        config = ContinuousDetectionConfig.get_instance()
        config.enabled = False
        config.save()

        logger.info(
            f'持续检测已停止，累计检测 {config.total_detections} 次，'
            f'发现异常 {config.total_anomalies} 次'
        )
        return self.get_config()

    def restore_from_db(self) -> None:
        """
        从数据库恢复持续检测状态

        应用启动时调用，如果数据库中 enabled=True 则自动恢复运行。
        """
        try:
            from detection.models import ContinuousDetectionConfig

            config = ContinuousDetectionConfig.get_instance()
            if config.enabled:
                logger.info(f'从数据库恢复持续检测，间隔 {config.interval} 秒')
                self._start_thread(config.interval, config.target_devices)
            else:
                logger.info('持续检测未启用，跳过恢复')
        except Exception as e:
            logger.error(f'恢复持续检测失败: {e}')

    def _start_thread(self, interval: int, target_devices: List[str]) -> None:
        """启动后台检测线程"""
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._detection_loop,
            args=(interval, target_devices),
            daemon=True,
            name='continuous-detection',
        )
        self._thread.start()

    def _stop_thread(self) -> None:
        """停止后台检测线程"""
        self._stop_event.set()
        self._running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._thread = None

    def _detection_loop(self, interval: int, target_devices: List[str]) -> None:
        """
        后台检测循环

        Args:
            interval: 检测间隔(秒)
            target_devices: 目标设备ID列表
        """
        import django
        django.setup()

        logger.info('持续检测线程启动')

        while not self._stop_event.is_set():
            try:
                self._run_one_round(target_devices)
            except Exception as e:
                logger.error(f'持续检测执行异常: {e}')

            # 等待间隔，但可被中断
            self._stop_event.wait(timeout=interval)

        logger.info('持续检测线程退出')

    def _run_one_round(self, target_devices: List[str]) -> None:
        """执行一轮检测"""
        from devices.models import Device
        from detection.services.detection_service import DetectionService
        from detection.models import ContinuousDetectionConfig

        # 查询目标设备
        if target_devices:
            devices = Device.objects.filter(
                device_id__in=target_devices
            ).exclude(status=Device.Status.OFFLINE)
        else:
            devices = Device.objects.exclude(status=Device.Status.OFFLINE)

        if not devices.exists():
            return

        success_count = 0
        anomaly_count = 0

        for device in devices:
            try:
                # 生成模拟流量数据
                traffic_data = self._generate_traffic_data(device)
                result = DetectionService.detect_single(traffic_data)
                success_count += 1
                if result.get('is_anomaly'):
                    anomaly_count += 1
            except Exception as e:
                logger.warning(f'设备 {device.device_id} 检测失败: {e}')

        # 更新数据库统计
        if success_count > 0:
            from django.db.models import F
            ContinuousDetectionConfig.objects.filter(pk=1).update(
                total_detections=F('total_detections') + success_count,
                total_anomalies=F('total_anomalies') + anomaly_count,
            )

            # 记录审计日志
            device_count = devices.count()
            AuditLog.log(
                user='后台检测',  # 系统自动执行
                action='detect',
                resource_type='detection',
                resource_name='持续检测',
                description=(
                    f'持续检测执行完成：检测设备 {device_count} 台，'
                    f'成功 {success_count} 次，发现异常 {anomaly_count} 次'
                ),
                request=None,
                result='success' if anomaly_count == 0 else 'warning',
                new_value={
                    'device_count': device_count,
                    'success_count': success_count,
                    'anomaly_count': anomaly_count,
                    'target_devices': target_devices or 'all',
                }
            )

    @staticmethod
    def _generate_traffic_data(device) -> Dict[str, Any]:
        """
        生成模拟流量数据（约70%正常，30%异常）

        Args:
            device: Device 实例

        Returns:
            模拟的流量数据字典
        """
        is_normal = random.random() < 0.7
        common = {
            'device_id': device.device_id,
            'src_ip': device.ip_address or '192.168.1.100',
            'dst_ip': '192.168.1.1',
            'src_port': random.randint(1024, 65000),
            'protocol': random.choice(['tcp', 'udp']),
        }

        if is_normal:
            common.update({
                'dst_port': random.choice([80, 443, 8080]),
                'duration': 0.1 + random.random() * 29.9,
                'orig_bytes': 64 + random.randint(0, 1984),
                'resp_bytes': 64 + random.randint(0, 4032),
                'orig_pkts': 1 + random.randint(0, 19),
                'resp_pkts': 1 + random.randint(0, 24),
            })
        else:
            common.update({
                'dst_port': random.choice([80, 443, 8080, 22, 3306]),
                'duration': random.random() * 0.1,
                'orig_bytes': 10000 + random.randint(0, 40000),
                'resp_bytes': random.randint(0, 100000),
                'orig_pkts': 100 + random.randint(0, 200),
                'resp_pkts': random.randint(0, 150),
            })

        return common


# 全局单例
continuous_detection_service = ContinuousDetectionService()
