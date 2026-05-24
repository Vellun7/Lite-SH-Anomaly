"""
检测序列化器
"""

from rest_framework import serializers
from detection.models import DetectionRecord, DetectionTask


class DetectionRecordSerializer(serializers.ModelSerializer):
    """检测记录序列化器"""

    attack_type_display = serializers.CharField(source='get_attack_type_display', read_only=True)
    feedback_label_display = serializers.SerializerMethodField()

    class Meta:
        model = DetectionRecord
        fields = [
            'id', 'device_id', 'timestamp', 'src_ip', 'dst_ip',
            'src_port', 'dst_port', 'protocol', 'duration',
            'orig_bytes', 'resp_bytes', 'orig_pkts', 'resp_pkts',
            'is_anomaly', 'attack_type', 'attack_type_display',
            'confidence', 'anomaly_score', 'model_version',
            'inference_time', 'created_at',
            'feedback_label', 'feedback_at',
            'feedback_label_display',
        ]

    def get_feedback_label_display(self, obj):
        if obj.feedback_label is None:
            return '未反馈'
        return '已确认异常' if obj.feedback_label else '已纠正(误报)'


class FeedbackInputSerializer(serializers.Serializer):
    """检测反馈输入序列化器"""

    record_id = serializers.IntegerField(help_text='检测记录ID')
    is_anomaly = serializers.BooleanField(
        help_text='人工确认结果: True=确实是异常, False=误报(实际正常)'
    )


class DetectionInputSerializer(serializers.Serializer):
    """检测输入序列化器"""

    device_id = serializers.CharField(max_length=64)
    timestamp = serializers.DateTimeField(required=False)
    src_ip = serializers.IPAddressField()
    dst_ip = serializers.IPAddressField()
    src_port = serializers.IntegerField(required=False, min_value=0, max_value=65535)
    dst_port = serializers.IntegerField(required=False, min_value=0, max_value=65535)
    protocol = serializers.CharField(max_length=10, default='TCP')
    duration = serializers.FloatField(default=0)
    orig_bytes = serializers.IntegerField(default=0)
    resp_bytes = serializers.IntegerField(default=0)
    orig_pkts = serializers.IntegerField(default=0)
    resp_pkts = serializers.IntegerField(default=0)


class DetectionBatchInputSerializer(serializers.Serializer):
    """批量检测输入序列化器"""

    data = DetectionInputSerializer(many=True)


class DetectionResultSerializer(serializers.Serializer):
    """检测结果序列化器"""

    record_id = serializers.IntegerField()
    is_anomaly = serializers.BooleanField()
    attack_type = serializers.CharField()
    confidence = serializers.FloatField()
    anomaly_score = serializers.FloatField()
    inference_time = serializers.FloatField()
    model_version = serializers.CharField()


class DetectionTaskSerializer(serializers.ModelSerializer):
    """检测任务序列化器"""

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = DetectionTask
        fields = [
            'task_id', 'file_name', 'status', 'status_display',
            'total_count', 'processed_count', 'anomaly_count',
            'progress', 'error_message', 'started_at',
            'completed_at', 'created_at'
        ]

    def get_progress(self, obj):
        if obj.total_count > 0:
            return round(obj.processed_count / obj.total_count * 100, 2)
        return 0


class DetectionStatsSerializer(serializers.Serializer):
    """检测统计序列化器"""

    total = serializers.IntegerField()
    anomaly = serializers.IntegerField()
    normal = serializers.IntegerField()
    anomaly_rate = serializers.FloatField()
    attack_distribution = serializers.ListField()
    daily_trend = serializers.ListField()
    avg_inference_time = serializers.FloatField()


class MonitoringKpiSerializer(serializers.Serializer):
    """监控KPI序列化器"""

    total_detections = serializers.IntegerField()
    anomaly_count = serializers.IntegerField()
    anomaly_rate = serializers.FloatField()
    avg_confidence = serializers.FloatField()
    avg_anomaly_score = serializers.FloatField()
    avg_inference_time = serializers.FloatField()


class MonitoringTrendSerializer(serializers.Serializer):
    """异常趋势序列化器"""

    period = serializers.CharField()
    total = serializers.IntegerField()
    anomaly = serializers.IntegerField()


class MonitoringDeviceRiskSerializer(serializers.Serializer):
    """设备风险排行序列化器"""

    device_id = serializers.CharField()
    total = serializers.IntegerField()
    anomaly = serializers.IntegerField()
    anomaly_rate = serializers.FloatField()


class MonitoringScoreConfidenceSerializer(serializers.Serializer):
    """异常分数与置信度序列化器"""

    anomaly_score = serializers.FloatField()
    confidence = serializers.FloatField()
    is_anomaly = serializers.BooleanField()


class MonitoringTrafficFeatureSerializer(serializers.Serializer):
    """流量特征与异常关联序列化器"""

    bucket = serializers.CharField()
    total = serializers.IntegerField()
    anomaly = serializers.IntegerField()
    anomaly_rate = serializers.FloatField()
    attack_distribution = serializers.ListField()
    daily_trend = serializers.ListField()
    avg_inference_time = serializers.FloatField()


class ContinuousDetectionConfigSerializer(serializers.Serializer):
    """持续检测配置序列化器"""

    enabled = serializers.BooleanField(help_text='是否启用')
    interval = serializers.IntegerField(
        help_text='检测间隔(秒)',
        min_value=3,
        max_value=300,
        default=5,
    )
    target_devices = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
        help_text='目标设备ID列表，为空则检测所有非离线设备',
    )


class ContinuousDetectionStatusSerializer(serializers.Serializer):
    """持续检测状态序列化器"""

    enabled = serializers.BooleanField()
    interval = serializers.IntegerField()
    target_devices = serializers.ListField(child=serializers.CharField())
    total_detections = serializers.IntegerField()
    total_anomalies = serializers.IntegerField()
    started_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    is_running = serializers.BooleanField()


class IncrementalLearningSerializer(serializers.Serializer):
    """增量学习状态序列化器"""

    feedback_buffer_size = serializers.IntegerField()
    update_frequency = serializers.IntegerField()
    total_samples_learned = serializers.IntegerField()
    model_version = serializers.CharField()
    last_update_time = serializers.CharField(allow_null=True)
    is_ready_to_update = serializers.BooleanField()
