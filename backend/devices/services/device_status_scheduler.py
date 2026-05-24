"""
设备状态定时更新任务
每10分钟基于检测历史更新所有设备状态
"""

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class DeviceStatusScheduler:
    """设备状态定时更新调度器"""
    
    _instance: Optional['DeviceStatusScheduler'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = 600  # 10分钟 = 600秒
        self._stop_event = threading.Event()
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def interval(self) -> int:
        return self._interval
    
    def set_interval(self, seconds: int):
        """设置更新间隔（秒）"""
        if seconds < 60:
            seconds = 60  # 最小1分钟
        self._interval = seconds
        logger.info(f"设备状态更新间隔设置为 {seconds} 秒")
    
    def start(self):
        """启动定时更新任务"""
        if self._running:
            logger.warning("设备状态定时更新任务已在运行")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"设备状态定时更新任务已启动，间隔 {self._interval} 秒")
    
    def stop(self):
        """停止定时更新任务"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        logger.info("设备状态定时更新任务已停止")
    
    def _run(self):
        """定时任务主循环"""
        # 启动时先执行一次
        self._update_status()
        
        while self._running:
            # 等待指定间隔或停止信号
            if self._stop_event.wait(timeout=self._interval):
                break  # 收到停止信号
            
            if self._running:
                self._update_status()
    
    def _update_status(self):
        """执行设备状态更新"""
        try:
            from devices.services.device_status_service import DeviceStatusService
            result = DeviceStatusService.update_all_device_status()
            logger.info(
                f"设备状态定时更新完成: "
                f"总计 {result['total_count']} 台, "
                f"更新 {result['updated_count']} 台"
            )
        except Exception as e:
            logger.error(f"设备状态更新失败: {e}")
    
    def update_now(self):
        """立即执行一次状态更新"""
        logger.info("手动触发设备状态更新")
        self._update_status()


# 全局单例
device_status_scheduler = DeviceStatusScheduler()
