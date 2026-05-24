"""
检测模块URL配置
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from detection.views import DetectionViewSet

router = DefaultRouter()
router.register('', DetectionViewSet, basename='detection')

# 手动添加stats路由，确保与前端请求匹配
urlpatterns = [
    path('', include(router.urls)),
    path('stats/', DetectionViewSet.as_view({'get': 'stats'}), name='detection-stats'),
    path('continuous/', DetectionViewSet.as_view({'get': 'continuous', 'post': 'continuous'}), name='detection-continuous'),
]
