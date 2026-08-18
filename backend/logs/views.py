"""HTTP endpoints for security alert management."""

from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device
from logs.models import AlertLog
from logs.serializers import AlertLogSerializer


class AlertPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def parse_alert_datetime(value):
    """Parse an ISO-8601 query value accepted by the detection endpoints."""
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is not None:
        return parsed
    if value.endswith('Z'):
        value = value.replace('Z', '+00:00')
    return datetime.fromisoformat(value)


def get_device_names(alerts):
    """Load device names in one query to avoid an alert-list N+1 lookup."""
    device_ids = {alert.device_id for alert in alerts}
    if not device_ids:
        return {}
    return dict(
        Device.objects.filter(device_id__in=device_ids).values_list('device_id', 'name')
    )


class AlertListView(APIView):
    """List security alerts with optional filtering and pagination."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        alerts = AlertLog.objects.all()
        for field in ('level', 'status', 'device_id'):
            value = request.query_params.get(field)
            if value:
                alerts = alerts.filter(**{field: value})

        start_time = parse_alert_datetime(request.query_params.get('start_time'))
        end_time = parse_alert_datetime(request.query_params.get('end_time'))
        if start_time:
            alerts = alerts.filter(created_at__gte=start_time)
        if end_time:
            alerts = alerts.filter(created_at__lte=end_time)

        paginator = AlertPagination()
        page = paginator.paginate_queryset(alerts, request)
        device_names = get_device_names(page)
        serializer = AlertLogSerializer(
            page,
            many=True,
            context={'device_names': device_names},
        )
        return Response({
            'code': status.HTTP_200_OK,
            'message': 'success',
            'data': {
                'count': paginator.page.paginator.count,
                'page': paginator.page.number,
                'page_size': paginator.page_size,
                'total_pages': paginator.page.paginator.num_pages,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
                'results': serializer.data,
            },
        })


class AlertDetailView(APIView):
    """Update one alert's handling status."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, alert_id):
        from logs.serializers import AlertStatusUpdateSerializer
        from users.models import AuditLog

        try:
            alert = AlertLog.objects.get(pk=alert_id)
        except AlertLog.DoesNotExist:
            return Response(
                {'code': status.HTTP_404_NOT_FOUND, 'message': 'Alert not found', 'data': None},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AlertStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = alert.status
        alert.status = serializer.validated_data['status']
        alert.handling_note = serializer.validated_data.get('handling_note', alert.handling_note)
        alert.handled_at = timezone.now()
        alert.save(update_fields=['status', 'handling_note', 'handled_at', 'updated_at'])

        AuditLog.log(
            user=request.user,
            action='update',
            resource_type='detection_result',
            resource_id=alert.id,
            resource_name=alert.title,
            description=f'Updated alert status from {old_status} to {alert.status}',
            request=request,
            old_value={'status': old_status},
            new_value={'status': alert.status, 'handling_note': alert.handling_note},
        )
        return Response({
            'code': status.HTTP_200_OK,
            'message': 'Alert updated',
            'data': AlertLogSerializer(
                alert,
                context={'device_names': get_device_names([alert])},
            ).data,
        })
