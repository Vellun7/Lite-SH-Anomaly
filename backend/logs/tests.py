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


class AlertApiTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        self.user = get_user_model().objects.create_user(
            username='alert-admin',
            password='test-password',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.alert = AlertLog.objects.create(
            device_id='camera-001',
            level=AlertLog.Level.DANGER,
            attack_type='ddos',
            title='DDoS alert',
            confidence=0.8,
        )

    def test_lists_alerts_with_pagination(self):
        response = self.client.get('/api/v1/logs/alerts/?page_size=10')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['count'], 1)
        self.assertEqual(response.data['data']['results'][0]['id'], self.alert.id)

    def test_updates_alert_status(self):
        response = self.client.patch(
            f'/api/v1/logs/alerts/{self.alert.id}/',
            {'status': 'resolved', 'handling_note': 'Blocked source IP'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, AlertLog.Status.RESOLVED)
        self.assertEqual(self.alert.handling_note, 'Blocked source IP')
        self.assertIsNotNone(self.alert.handled_at)

    def test_rejects_batch_update_when_alert_is_missing(self):
        response = self.client.post(
            '/api/v1/logs/alerts/batch-update/',
            {'alert_ids': [self.alert.id, 9999], 'status': 'confirmed'},
            format='json',
        )

        self.assertEqual(response.status_code, 404)
        self.alert.refresh_from_db()
        self.assertEqual(self.alert.status, AlertLog.Status.PENDING)
