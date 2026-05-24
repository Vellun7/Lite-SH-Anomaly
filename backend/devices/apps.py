"""
设备应用配置
"""

from django.apps import AppConfig


class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'devices'
    verbose_name = '设备管理'
    
    def ready(self):
        """应用启动时启动设备状态定时更新任务"""
        import logging
        import os
        
        logger = logging.getLogger(__name__)
        
        # 避免在 manage.py migrate 等命令时启动
        # 只在 runserver 时启动
        if os.environ.get('RUN_MAIN') == 'true':
            try:
                from devices.services.device_status_scheduler import device_status_scheduler
                device_status_scheduler.start()
                logger.info('设备状态定时更新任务已启动（每10分钟更新一次）')
            except Exception as e:
                logger.error(f'启动设备状态定时更新任务失败: {e}')
