"""
检测模型层
定义异常检测相关数据模型
"""

from django.db import models


class DetectionRecord(models.Model):
    """检测记录模型"""
    
    class AttackType(models.TextChoices):
        NORMAL = 'normal', '正常'
        DDOS = 'ddos', 'DDoS攻击'
        PORT_SCAN = 'port_scan', '端口扫描'
        UNAUTHORIZED = 'unauthorized', '越权访问'
        MALFORMED = 'malformed', '异常指令'
        UNKNOWN = 'unknown', '未知威胁'
    
    # 基础信息
    device_id = models.CharField('设备ID', max_length=64, db_index=True)
    timestamp = models.DateTimeField('检测时间', db_index=True)
    
    # 网络特征
    src_ip = models.GenericIPAddressField('源IP')
    dst_ip = models.GenericIPAddressField('目的IP')
    src_port = models.IntegerField('源端口', null=True, blank=True)
    dst_port = models.IntegerField('目的端口', null=True, blank=True)
    protocol = models.CharField('协议', max_length=10, default='TCP')
    
    # 流量特征
    duration = models.FloatField('持续时间', default=0)
    orig_bytes = models.BigIntegerField('发送字节数', default=0)
    resp_bytes = models.BigIntegerField('接收字节数', default=0)
    orig_pkts = models.IntegerField('发送包数', default=0)
    resp_pkts = models.IntegerField('接收包数', default=0)
    
    # 检测结果
    is_anomaly = models.BooleanField('是否异常', default=False, db_index=True)
    attack_type = models.CharField('攻击类型', max_length=20, choices=AttackType.choices, default=AttackType.NORMAL)
    confidence = models.FloatField('置信度', default=0.0)
    anomaly_score = models.FloatField('异常分数', default=0.0)
    
    # 用户反馈（增量学习的数据来源）
    feedback_label = models.BooleanField(
        '用户反馈标签', null=True, blank=True, db_index=True,
        help_text='None=未反馈, True=确认异常, False=纠正为正常(误报)'
    )
    feedback_at = models.DateTimeField('反馈时间', null=True, blank=True)

    # 元数据
    model_version = models.CharField('模型版本', max_length=32, default='v1.0')
    inference_time = models.FloatField('推理耗时(ms)', default=0.0)
    created_at = models.DateTimeField('记录创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'detection_records'
        verbose_name = '检测记录'
        verbose_name_plural = '检测记录'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device_id', 'timestamp']),
            models.Index(fields=['is_anomaly', 'timestamp']),
            models.Index(fields=['attack_type', 'timestamp']),
        ]
    
    def __str__(self):
        status = '异常' if self.is_anomaly else '正常'
        return f'{self.device_id} - {status} - {self.timestamp}'


class DetectionTask(models.Model):
    """批量检测任务模型"""
    
    class TaskStatus(models.TextChoices):
        PENDING = 'pending', '等待中'
        RUNNING = 'running', '运行中'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '失败'
    
    task_id = models.CharField('任务ID', max_length=64, unique=True, db_index=True)
    file_name = models.CharField('文件名', max_length=256)
    status = models.CharField('状态', max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING)
    total_count = models.IntegerField('总记录数', default=0)
    processed_count = models.IntegerField('已处理数', default=0)
    anomaly_count = models.IntegerField('异常数', default=0)
    error_message = models.TextField('错误信息', null=True, blank=True)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'detection_tasks'
        verbose_name = '检测任务'
        verbose_name_plural = '检测任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.task_id} - {self.status}'


class ContinuousDetectionConfig(models.Model):
    """持续检测配置（全局单例模式）"""

    enabled = models.BooleanField('是否启用', default=False)
    interval = models.IntegerField('检测间隔(秒)', default=60)
    target_devices = models.JSONField('目标设备ID列表', default=list, blank=True)
    total_detections = models.IntegerField('累计检测次数', default=0)
    total_anomalies = models.IntegerField('累计异常次数', default=0)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'continuous_detection_config'
        verbose_name = '持续检测配置'
        verbose_name_plural = '持续检测配置'

    def __str__(self):
        status = '启用' if self.enabled else '停用'
        return f'持续检测配置 - {status}'

    @classmethod
    def get_instance(cls):
        """获取单例配置，不存在则创建"""
        instance, __ = cls.objects.get_or_create(pk=1)
        return instance
