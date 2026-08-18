from django.contrib import admin

from logs.models import AlertLog


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'device_id', 'attack_type', 'level', 'status', 'confidence', 'created_at')
    list_filter = ('level', 'status', 'attack_type')
    search_fields = ('device_id', 'title', 'message')
    readonly_fields = ('created_at', 'updated_at', 'handled_at')
    ordering = ('-created_at',)
