"""
设备序列化器
"""

from rest_framework import serializers
from devices.models import Device, DeviceStats, DeviceGroup


class DeviceSerializer(serializers.ModelSerializer):
    """设备序列化器"""
    
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    groups = serializers.StringRelatedField(many=True, read_only=True)  # 分组名称列表，用于展示
    group_ids = serializers.SerializerMethodField()  # 分组ID列表，用于前端过滤
    security_level = serializers.ReadOnlyField()
    
    class Meta:
        model = Device
        fields = [
            'id', 'device_id', 'name', 'device_type', 'device_type_display',
            'ip_address', 'mac_address', 'status', 'status_display',
            'location', 'is_trusted', 'security_score', 'security_level', 
            'last_score_update', 'groups', 'group_ids', 'last_seen', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_group_ids(self, obj):
        """获取设备所属分组的ID列表"""
        return list(obj.groups.values_list('id', flat=True))


class DeviceCreateSerializer(serializers.ModelSerializer):
    """设备创建序列化器"""
    
    class Meta:
        model = Device
        fields = ['device_id', 'name', 'device_type', 'ip_address', 'mac_address', 'location']
    
    def validate_device_id(self, value):
        if Device.objects.filter(device_id=value).exists():
            raise serializers.ValidationError('设备ID已存在')
        return value


class DeviceUpdateSerializer(serializers.ModelSerializer):
    """设备更新序列化器"""
    
    class Meta:
        model = Device
        fields = ['name', 'device_type', 'ip_address', 'mac_address', 'location', 'is_trusted']


class DeviceStatsSerializer(serializers.ModelSerializer):
    """设备统计序列化器"""
    
    device_id = serializers.CharField(source='device.device_id', read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True)
    
    class Meta:
        model = DeviceStats
        fields = ['device_id', 'device_name', 'date', 'total_requests', 'normal_count', 'anomaly_count']


class DeviceOverviewSerializer(serializers.Serializer):
    """设备概览序列化器"""
    
    total = serializers.IntegerField()
    online = serializers.IntegerField()
    offline = serializers.IntegerField()
    warning = serializers.IntegerField()
    type_distribution = serializers.ListField()


class DeviceGroupSerializer(serializers.ModelSerializer):
    """设备分组序列化器"""
    
    device_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = DeviceGroup
        fields = [
            'id', 'name', 'description', 'icon', 'color', 
            'parent', 'parent_name', 'device_count', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_device_count(self, obj):
        """获取设备数量，优先使用 annotate 的 devices_count，否则使用 property"""
        return getattr(obj, 'devices_count', obj.device_count)


class DeviceGroupCreateSerializer(serializers.ModelSerializer):
    """设备分组创建序列化器"""
    
    class Meta:
        model = DeviceGroup
        fields = ['name', 'description', 'icon', 'color', 'parent']
    
    def validate_name(self, value):
        if DeviceGroup.objects.filter(name=value).exists():
            raise serializers.ValidationError('分组名称已存在')
        return value


class DeviceGroupUpdateSerializer(serializers.ModelSerializer):
    """设备分组更新序列化器"""
    
    class Meta:
        model = DeviceGroup
        fields = ['name', 'description', 'icon', 'color', 'parent']
    
    def validate_name(self, value):
        # 排除当前对象，检查名称是否重复
        instance = getattr(self, 'instance', None)
        if instance and DeviceGroup.objects.filter(name=value).exclude(id=instance.id).exists():
            raise serializers.ValidationError('分组名称已存在')
        elif not instance and DeviceGroup.objects.filter(name=value).exists():
            raise serializers.ValidationError('分组名称已存在')
        return value


class BatchGroupAssignSerializer(serializers.Serializer):
    """批量分组分配序列化器"""
    
    device_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        min_length=1,
        help_text='设备ID列表'
    )
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text='分组ID列表'
    )


class GroupDeviceOperationSerializer(serializers.Serializer):
    """分组设备操作序列化器"""
    
    device_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        min_length=1,
        help_text='设备ID列表'
    )
