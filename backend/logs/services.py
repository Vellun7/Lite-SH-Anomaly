"""Domain services for creating and handling security alerts."""

from logs.models import AlertLog


class AlertService:
    """Keep alert creation deterministic for anomaly detections."""

    @classmethod
    def create_alert_from_detection(cls, record, result):
        """Create one pending alert for an anomalous detection record."""
        if not result.get('is_anomaly'):
            return None

        attack_type = result.get('attack_type', 'unknown')
        confidence = float(result.get('confidence', 0.0))
        alert, _ = AlertLog.objects.get_or_create(
            detection_record=record,
            defaults={
                'device_id': record.device_id,
                'level': cls.get_level(confidence),
                'attack_type': attack_type,
                'title': cls.build_title(attack_type),
                'message': cls.build_message(record, attack_type),
                'confidence': confidence,
            },
        )
        return alert

    @staticmethod
    def get_level(confidence):
        """Map model confidence to a user-facing severity level."""
        if confidence >= 0.9:
            return AlertLog.Level.CRITICAL
        if confidence >= 0.75:
            return AlertLog.Level.DANGER
        if confidence >= 0.5:
            return AlertLog.Level.WARNING
        return AlertLog.Level.INFO

    @staticmethod
    def build_title(attack_type):
        return f'Potential {attack_type.replace("_", " ")} threat detected'

    @staticmethod
    def build_message(record, attack_type):
        return (
            f'Device {record.device_id} triggered a {attack_type} alert '
            f'from {record.src_ip} to {record.dst_ip}.'
        )
