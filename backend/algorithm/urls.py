"""
算法模型管理 - URL路由配置
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlgorithmModelViewSet, TrainingTaskViewSet, EvaluationResultViewSet, FeatureImportanceViewSet,
    upload_dataset, list_datasets, list_model_files, download_model_file
)

app_name = 'algorithm'

router = DefaultRouter()
router.register(r'models', AlgorithmModelViewSet, basename='algorithm-model')
router.register(r'training', TrainingTaskViewSet, basename='algorithm-training')
router.register(r'evaluation', EvaluationResultViewSet, basename='algorithm-evaluation')
router.register(r'features', FeatureImportanceViewSet, basename='algorithm-features')

urlpatterns = [
    path('', include(router.urls)),
    path('datasets/upload/', upload_dataset, name='upload-dataset'),
    path('datasets/list/', list_datasets, name='list-datasets'),
    path('model-files/', list_model_files, name='list-model-files'),
    path('model-files/<str:file_name>/download/', download_model_file, name='download-model-file'),
]
