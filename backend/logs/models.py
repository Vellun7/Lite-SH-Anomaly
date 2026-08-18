"""Persistent alert records created from anomaly detections."""

from django.db import models


class AlertLog(models.Model):
    """Security alert raised for a detection record."""

    class Level(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        DANGER = 'danger', 'Danger'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        RESOLVED = 'resolved', 'Resolved'
        IGNORED = 'ignored', 'Ignored'

    detection_record = models.ForeignKey(
        'detection.DetectionRecord',
        on_delete=models.SET_NULL,
        related_name='alerts',
        null=True,
        blank=True,
        verbose_name='Detection record',
    )
    device_id = models.CharField('Device ID', max_length=64, db_index=True)
    level = models.CharField(
        'Level', max_length=10, choices=Level.choices, default=Level.WARNING, db_index=True
    )
    attack_type = models.CharField('Attack type', max_length=20, db_index=True)
    title = models.CharField('Title', max_length=200)
    message = models.TextField('Message', blank=True)
    confidence = models.FloatField('Confidence', default=0.0)
    status = models.CharField(
        'Status', max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    handling_note = models.TextField('Handling note', blank=True)
    handled_at = models.DateTimeField('Handled at', null=True, blank=True)
    created_at = models.DateTimeField('Created at', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Updated at', auto_now=True)

    class Meta:
        db_table = 'alert_logs'
        verbose_name = 'Alert log'
        verbose_name_plural = 'Alert logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='alert_logs_status__cc1194_idx'),
            models.Index(fields=['device_id', 'created_at'], name='alert_logs_device__103051_idx'),
            models.Index(fields=['level', 'created_at'], name='alert_logs_level_80b005_idx'),
        ]

    def __str__(self):
        return f'{self.device_id} - {self.attack_type} - {self.status}'
