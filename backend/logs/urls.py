"""URL routes for security alert APIs."""

from django.urls import path

from logs.views import AlertBatchStatusView, AlertDetailView, AlertListView, AlertStatsView


urlpatterns = [
    path('alerts/', AlertListView.as_view(), name='alert-list'),
    path('alerts/stats/', AlertStatsView.as_view(), name='alert-stats'),
    path('alerts/batch-update/', AlertBatchStatusView.as_view(), name='alert-batch-update'),
    path('alerts/<int:alert_id>/', AlertDetailView.as_view(), name='alert-detail'),
]
