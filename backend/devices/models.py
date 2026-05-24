"""
设备模型层
定义智能家居设备相关数据模型
"""

from django.db import models


class Device(models.Model):
    """智能家居设备模型"""
    
    class DeviceType(models.TextChoices):
        CAMERA = 'camera', '智能摄像头'
        DOOR_LOCK = 'door_lock', '智能门锁'
        SENSOR = 'sensor', '传感器'
        GATEWAY = 'gateway', '网关'
        SWITCH = 'switch', '智能开关'
        ROBOT = 'robot', '扫地机器人'
        LOCK = 'lock', '门锁'
        CURTAIN = 'curtain', '窗帘电机'
        LIGHT = 'light', '智能灯泡'
        SPEAKER = 'speaker', '智能音箱'
        AC_COMPANION = 'ac_companion', '空调伴侣'
        PURIFIER = 'purifier', '空气净化器'
        ALARM = 'alarm', '烟雾报警器'
        OTHER = 'other', '其他'
    
    class Status(models.TextChoices):
        ONLINE = 'online', '在线'
        OFFLINE = 'offline', '离线'
        WARNING = 'warning', '告警'
    
    device_id = models.CharField('设备ID', max_length=64, unique=True, db_index=True)
    name = models.CharField('设备名称', max_length=128)
    device_type = models.CharField('设备类型', max_length=20, choices=DeviceType.choices, default=DeviceType.OTHER)
    ip_address = models.GenericIPAddressField('IP地址', null=True, blank=True)
    mac_address = models.CharField('MAC地址', max_length=17, null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=Status.choices, default=Status.ONLINE)
    location = models.CharField('位置', max_length=128, null=True, blank=True)
    is_trusted = models.BooleanField('是否可信', default=True)
    security_score = models.FloatField('安全评分', default=100.0)
    last_score_update = models.DateTimeField('评分更新时间', null=True, blank=True)
    groups = models.ManyToManyField('DeviceGroup', related_name='devices', blank=True, verbose_name='所属分组')
    last_seen = models.DateTimeField('最后在线时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'devices'
        verbose_name = '设备'
        verbose_name_plural = '设备'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f'{self.name} ({self.device_id})'
    
    @property
    def security_level(self):
        """根据安全评分返回安全等级"""
        if self.security_score >= 90:
            return 'high'
        elif self.security_score >= 70:
            return 'medium'
        else:
            return 'low'


class DeviceGroup(models.Model):
    """设备分组模型"""
    
    name = models.CharField('分组名称', max_length=128, unique=True)
    description = models.TextField('分组描述', blank=True)
    icon = models.CharField('图标', max_length=64, blank=True, default='folder')
    color = models.CharField('颜色', max_length=7, default='#1890ff')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    
    class Meta:
        db_table = 'device_groups'
        verbose_name = '设备分组'
        verbose_name_plural = '设备分组'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def device_count(self):
        """获取分组下的设备数量"""
        return self.devices.count()


class DeviceStats(models.Model):
    """设备统计信息（每日汇总）"""
    
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='stats')
    date = models.DateField('统计日期', db_index=True)
    total_requests = models.IntegerField('总请求数', default=0)
    normal_count = models.IntegerField('正常请求数', default=0)
    anomaly_count = models.IntegerField('异常请求数', default=0)
    
    class Meta:
        db_table = 'device_stats'
        verbose_name = '设备统计'
        verbose_name_plural = '设备统计'
        unique_together = ['device', 'date']
        ordering = ['-date']
