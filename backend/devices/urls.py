"""
设备模块URL配置

注意：DeviceViewSet 注册在根路径 ''，它会将 /devices/<pk>/ 匹配所有子路径，
因此 groups 和 security 必须通过独立的 Router 先注册到 urlpatterns 中，
保证 Django URL 解析时优先匹配到它们，而不是被当作 DeviceViewSet 的 pk 参数。
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from devices.group_views import DeviceGroupViewSet
from devices.main_views import DeviceViewSet
from devices.security_views import DeviceSecurityViewSet

# groups 和 security 使用独立的 router，避免与根路径 DeviceViewSet 冲突
group_router = DefaultRouter()
group_router.register('', DeviceGroupViewSet, basename='device-group')

security_router = DefaultRouter()
security_router.register('', DeviceSecurityViewSet, basename='device-security')

# 根路径 DeviceViewSet
device_router = DefaultRouter()
device_router.register('', DeviceViewSet, basename='device')

urlpatterns = [
    # 显式前缀路径优先匹配
    path('groups/', include(group_router.urls)),
    path('security/', include(security_router.urls)),
    # 根路径最后匹配
    path('', include(device_router.urls)),
]
