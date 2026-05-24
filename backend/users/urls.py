"""
用户路由
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AuthViewSet, LoginLogViewSet, AuditLogViewSet

router = DefaultRouter()
router.register('auth', AuthViewSet, basename='auth')
router.register('login-logs', LoginLogViewSet, basename='login-logs')
router.register('audit-logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('', include(router.urls)),
    # JWT刷新令牌
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
