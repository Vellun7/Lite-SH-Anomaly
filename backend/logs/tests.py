from django.test import TestCase
from django.utils import timezone

from detection.models import DetectionRecord
from logs.models import AlertLog
from logs.services import AlertService


class AlertServiceTests(TestCase):
    def create_record(self):
        return DetectionRecord.objects.create(
            device_id='camera-001',
            timestamp=timezone.now(),
            src_ip='192.168.1.10',
            dst_ip='192.168.1.20',
            is_anomaly=True,
            attack_type=DetectionRecord.AttackType.DDOS,
            confidence=0.95,
            anomaly_score=0.8,
        )

    def test_creates_one_critical_alert_for_anomalous_record(self):
        record = self.create_record()
        result = {
            'is_anomaly': True,
            'attack_type': 'ddos',
            'confidence': 0.95,
        }

        alert = AlertService.create_alert_from_detection(record, result)

        self.assertEqual(alert.device_id, record.device_id)
        self.assertEqual(alert.level, AlertLog.Level.CRITICAL)
        self.assertEqual(alert.status, AlertLog.Status.PENDING)
        self.assertEqual(AlertLog.objects.count(), 1)

    def test_reuses_existing_alert_for_the_same_detection_record(self):
        record = self.create_record()
        result = {
            'is_anomaly': True,
            'attack_type': 'ddos',
            'confidence': 0.7,
        }

        first_alert = AlertService.create_alert_from_detection(record, result)
        second_alert = AlertService.create_alert_from_detection(record, result)

        self.assertEqual(first_alert.id, second_alert.id)
        self.assertEqual(AlertLog.objects.count(), 1)

    def test_skips_alert_creation_for_normal_detection(self):
        record = self.create_record()

        alert = AlertService.create_alert_from_detection(
            record,
            {'is_anomaly': False, 'attack_type': 'normal', 'confidence': 0.0},
        )

        self.assertIsNone(alert)
        self.assertFalse(AlertLog.objects.exists())
