"""Serializers for security alert APIs."""

from rest_framework import serializers

from logs.models import AlertLog


class AlertLogSerializer(serializers.ModelSerializer):
    """Expose alert details without querying devices per row."""

    device_name = serializers.SerializerMethodField()
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AlertLog
        fields = [
            'id', 'detection_record', 'device_id', 'device_name',
            'level', 'level_display', 'attack_type', 'title', 'message',
            'confidence', 'status', 'status_display', 'handling_note',
            'handled_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'detection_record', 'device_id', 'level', 'attack_type',
            'title', 'message', 'confidence', 'handled_at', 'created_at', 'updated_at',
        ]

    def get_device_name(self, obj):
        return self.context.get('device_names', {}).get(obj.device_id)


class AlertStatusUpdateSerializer(serializers.Serializer):
    """Validate an alert handling action."""

    status = serializers.ChoiceField(choices=AlertLog.Status.choices)
    handling_note = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_status(self, value):
        if value == AlertLog.Status.PENDING:
            raise serializers.ValidationError('An alert cannot be moved back to pending.')
        return value


class AlertBatchStatusUpdateSerializer(AlertStatusUpdateSerializer):
    """Validate a shared status update for several alerts."""

    alert_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=100,
    )


class AlertStatsSerializer(serializers.Serializer):
    """Document the alert statistics response."""

    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    resolved = serializers.IntegerField()
    level_distribution = serializers.ListField()
    daily_trend = serializers.ListField()
