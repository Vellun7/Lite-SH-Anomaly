"""
算法模型管理 - 视图层
提供RESTful API接口
"""

import os
import re
import json
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import AlgorithmModel, TrainingTask, EvaluationResult, FeatureImportance
from .serializers import (
    AlgorithmModelSerializer, AlgorithmModelCreateSerializer, AlgorithmModelUpdateSerializer,
    TrainingTaskSerializer, TrainingTaskCreateSerializer,
    EvaluationResultSerializer, FeatureImportanceSerializer
)
from common.response import APIResponse


@extend_schema_view(
    list=extend_schema(summary='算法模型列表', description='获取算法模型列表，支持按类型和状态筛选'),
    create=extend_schema(summary='创建算法模型', description='创建新的算法模型记录'),
    retrieve=extend_schema(summary='算法模型详情', description='获取单个算法模型详情'),
    update=extend_schema(summary='更新算法模型', description='更新算法模型信息'),
    partial_update=extend_schema(summary='部分更新算法模型', description='部分更新算法模型信息'),
    destroy=extend_schema(summary='删除算法模型', description='删除算法模型记录'),
)
class AlgorithmModelViewSet(viewsets.ModelViewSet):
    """算法模型管理API"""
    
    queryset = AlgorithmModel.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AlgorithmModelCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AlgorithmModelUpdateSerializer
        return AlgorithmModelSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        model_type = self.request.query_params.get('model_type')
        status = self.request.query_params.get('status')
        is_active = self.request.query_params.get('is_active')
        
        if model_type:
            queryset = queryset.filter(model_type=model_type)
        if status:
            queryset = queryset.filter(status=status)
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            queryset = queryset.filter(is_active=is_active_bool)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """创建算法模型，如果已存在相同配置的模型则更新版本号"""
        # 获取请求数据
        model_type = request.data.get('model_type')
        training_dataset = request.data.get('training_dataset')
        training_params = request.data.get('training_params', {})
        
        # 查询是否已存在相同配置的模型
        existing_model = AlgorithmModel.objects.filter(
            model_type=model_type,
            training_dataset=training_dataset,
            training_params=training_params
        ).first()
        
        if existing_model:
            # 存在相同配置的模型，递增版本号
            new_version = self._increment_version(existing_model.version)
            existing_model.version = new_version
            existing_model.updated_at = timezone.now()
            existing_model.save()
            
            # 返回更新后的模型
            serializer = AlgorithmModelSerializer(existing_model)
            return APIResponse.success(
                data=serializer.data,
                message=f'已存在相同配置的模型，版本已更新为 {new_version}'
            )
        else:
            # 不存在相同配置的模型，创建新模型
            return super().create(request, *args, **kwargs)
    
    def _increment_version(self, version_str):
        """递增版本号，如 v1.0 -> v1.1"""
        # 匹配版本号格式 vX.Y
        match = re.match(r'v(\d+)\.(\d+)', version_str)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2))
            # 递增小版本号
            minor += 1
            return f'v{major}.{minor}'
        else:
            # 如果版本号格式不匹配，返回原版本号加 _updated
            return f'{version_str}_updated'
    
    @extend_schema(summary='激活模型', description='将指定模型设为当前激活模型')
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活模型"""
        model = self.get_object()
        if model.status != 'ready':
            return APIResponse.error(message='只有就绪状态的模型才能激活')
        
        model.is_active = True
        model.save()
        return APIResponse.success(data=AlgorithmModelSerializer(model).data, message='模型已激活')
    
    @extend_schema(summary='获取当前激活模型', description='获取当前激活的算法模型')
    @action(detail=False, methods=['get'])
    def active(self, request):
        """获取当前激活模型"""
        model = AlgorithmModel.objects.filter(is_active=True).first()
        if not model:
            return APIResponse.error(message='没有激活的模型')
        return APIResponse.success(data=AlgorithmModelSerializer(model).data)


@extend_schema_view(
    list=extend_schema(summary='训练任务列表', description='获取训练任务列表'),
    create=extend_schema(summary='创建训练任务', description='创建新的训练任务'),
    retrieve=extend_schema(summary='训练任务详情', description='获取训练任务详情'),
)
class TrainingTaskViewSet(viewsets.ModelViewSet):
    """训练任务管理API"""
    
    queryset = TrainingTask.objects.all()
    serializer_class = TrainingTaskSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TrainingTaskCreateSerializer
        return TrainingTaskSerializer
    
    def perform_create(self, serializer):
        """创建训练任务时，关联已存在的 AlgorithmModel 记录"""
        import logging
        logger = logging.getLogger(__name__)
        
        # 记录接收到的数据
        logger.info(f"创建训练任务 - 接收数据: {self.request.data}")
        
        # 获取请求数据中的 model ID
        model_id = self.request.data.get('model')
        
        if not model_id:
            logger.error(f"创建训练任务失败 - 缺少model字段. 接收的数据: {self.request.data}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'model': '该字段是必填项。'})
        
        # 查找对应的 AlgorithmModel 记录
        from .models import AlgorithmModel
        try:
            algorithm_model = AlgorithmModel.objects.get(id=model_id)
        except AlgorithmModel.DoesNotExist:
            logger.error(f"创建训练任务失败 - 算法模型不存在. model_id={model_id}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'model': f'算法模型 ID {model_id} 不存在。'})
        
        # 保存训练任务，关联 algorithm_model
        logger.info(f"创建训练任务成功 - model_id={model_id}, algorithm_model={algorithm_model}")
        serializer.save(model=algorithm_model)
    
    @extend_schema(summary='启动训练', description='启动指定的训练任务')
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """启动训练"""
        task = self.get_object()
        if task.status != 'pending':
            return APIResponse.error(message='只有等待中的任务才能启动')
        
        # 实际启动训练逻辑（后台线程）
        task.status = 'running'
        from django.utils import timezone
        task.started_at = timezone.now()
        task.save()
        
        # TODO: 实际调用 algorithm/run_training.py 启动训练
        # 这里可以启动 Celery 任务或后台线程
        
        return APIResponse.success(data=TrainingTaskSerializer(task).data, message='训练任务已启动')
    
    @extend_schema(summary='取消训练', description='取消指定的训练任务')
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消训练"""
        task = self.get_object()
        if task.status != 'running':
            return APIResponse.error(message='只有运行中的任务才能取消')
        
        task.status = 'cancelled'
        task.save()
        
        return APIResponse.success(data=TrainingTaskSerializer(task).data, message='训练任务已取消')


@extend_schema_view(
    list=extend_schema(summary='评估结果列表', description='获取评估结果列表'),
    retrieve=extend_schema(summary='评估结果详情', description='获取评估结果详情'),
)
class EvaluationResultViewSet(viewsets.ModelViewSet):
    """评估结果管理API"""
    
    queryset = EvaluationResult.objects.all()
    serializer_class = EvaluationResultSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(summary='模型对比', description='对比多个模型的评估结果')
    @action(detail=False, methods=['post'])
    def compare(self, request):
        """模型对比"""
        model_ids = request.data.get('model_ids', [])
        if not model_ids:
            return APIResponse.error(message='请提供要对比的模型ID')
        
        results = EvaluationResult.objects.filter(model_id__in=model_ids).order_by('-created_at')
        
        # 取每个模型最新的评估结果
        latest_results = {}
        for result in results:
            if result.model_id not in latest_results:
                latest_results[result.model_id] = result
        
        serializer = EvaluationResultSerializer(latest_results.values(), many=True)
        return APIResponse.success(data=serializer.data)


@extend_schema_view(
    list=extend_schema(summary='特征重要性列表', description='获取特征重要性列表'),
    retrieve=extend_schema(summary='特征重要性详情', description='获取特征重要性详情'),
)
class FeatureImportanceViewSet(viewsets.ModelViewSet):
    """特征重要性管理API"""
    
    queryset = FeatureImportance.objects.all()
    serializer_class = FeatureImportanceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
        return queryset.order_by('rank')


@extend_schema(summary='上传数据集', description='上传训练数据集文件')
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_dataset(request):
    """上传数据集文件"""
    if 'file' not in request.FILES:
        return APIResponse.error(message='请提供文件')
    
    file = request.FILES['file']
    file_name = file.name
    
    # 检查文件扩展名
    allowed_extensions = ['.npz', '.csv', '.json', '.parquet']
    file_ext = os.path.splitext(file_name)[1].lower()
    if file_ext not in allowed_extensions:
        return APIResponse.error(message=f'不支持的文件格式，请上传: {", ".join(allowed_extensions)}')
    
    # 保存文件到数据集目录
    dataset_dir = os.path.join(settings.MEDIA_ROOT, 'datasets')
    os.makedirs(dataset_dir, exist_ok=True)
    
    file_path = os.path.join(dataset_dir, file_name)
    
    # 保存文件
    with default_storage.open(file_path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    
    return APIResponse.success(
        data={
            'file_name': file_name,
            'file_path': file_path,
            'file_size': file.size
        },
        message='数据集上传成功'
    )


@extend_schema(summary='数据集列表', description='获取已上传的数据集列表')
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_datasets(request):
    """获取数据集列表"""
    dataset_dir = os.path.join(settings.MEDIA_ROOT, 'datasets')
    datasets = []
    
    if os.path.exists(dataset_dir):
        for file_name in os.listdir(dataset_dir):
            file_path = os.path.join(dataset_dir, file_name)
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f'{file_size}B'
                elif file_size < 1024 * 1024:
                    size_str = f'{file_size / 1024:.1f}KB'
                else:
                    size_str = f'{file_size / 1024 / 1024:.2f}MB'
                
                datasets.append({
                    'name': file_name,
                    'size': size_str,
                    'uploaded_at': os.path.getctime(file_path)
                })
    
    return APIResponse.success(data=datasets)


@extend_schema(summary='模型文件列表', description='获取 algorithm/models/ 文件夹中的模型文件列表')
@api_view(['GET'])
@permission_classes([AllowAny])  # 暂时允许任何人访问以测试
def list_model_files(request):
    """获取模型文件列表"""
    # algorithm/models/ 文件夹路径（相对于项目根目录）
    # 项目根目录是 backend/ 的上一级
    base_dir = settings.BASE_DIR
    models_dir = os.path.join(base_dir, '..', 'algorithm', 'models')
    models_dir = os.path.normpath(models_dir)
    
    model_files = []
    
    # 读取元数据文件
    metadata = {}
    metadata_file = os.path.join(models_dir, 'model_metadata.json')
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
                # 将元数据转换为以 file_name 为键的字典，方便查找
                for item in metadata_list:
                    if 'file_name' in item:
                        metadata[item['file_name']] = item
        except (json.JSONDecodeError, IOError) as e:
            print(f"读取元数据文件失败: {e}")
    
    if os.path.exists(models_dir):
        for file_name in os.listdir(models_dir):
            # 跳过元数据文件
            if file_name == 'model_metadata.json':
                continue
                
            file_path = os.path.join(models_dir, file_name)
            if os.path.isfile(file_path):
                # 过滤掉不需要显示的模型（scaler, knn, svm），只返回孤立森林和自编码器
                if 'scaler' in file_name or 'knn' in file_name or 'svm' in file_name:
                    continue
                    
                file_size = os.path.getsize(file_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f'{file_size}B'
                elif file_size < 1024 * 1024:
                    size_str = f'{file_size / 1024:.1f}KB'
                else:
                    size_str = f'{file_size / 1024 / 1024:.2f}MB'
                
                # 获取文件修改时间
                modified_time = os.path.getmtime(file_path)
                
                # 尝试推断模型类型
                model_type = 'unknown'
                if 'isolation_forest' in file_name:
                    model_type = 'isolation_forest'
                elif 'autoencoder' in file_name:
                    model_type = 'autoencoder'
                elif 'knn' in file_name:
                    model_type = 'knn'
                elif 'svm' in file_name:
                    model_type = 'svm'
                
                # 基础文件信息
                file_info = {
                    'file_name': file_name,
                    'model_type': model_type,
                    'size': size_str,
                    'size_bytes': file_size,
                    'modified_at': modified_time,
                    'modified_at_str': os.path.getmtime(file_path)
                }
                
                # 如果元数据中存在该文件的信息，则合并
                if file_name in metadata:
                    file_metadata = metadata[file_name]
                    # 合并性能数据
                    if 'performance' in file_metadata:
                        file_info['performance'] = file_metadata['performance']
                    # 合并训练信息
                    if 'training_info' in file_metadata:
                        file_info['training_info'] = file_metadata['training_info']
                    # 合并其他信息
                    if 'created_at' in file_metadata:
                        file_info['created_at'] = file_metadata['created_at']
                    if 'description' in file_metadata:
                        file_info['description'] = file_metadata['description']
                
                model_files.append(file_info)
    
    return APIResponse.success(data=model_files)


@extend_schema(summary='下载模型文件', description='从 algorithm/models/ 文件夹下载指定模型文件')
@api_view(['GET'])
@permission_classes([AllowAny])
def download_model_file(request, file_name):
    """下载模型文件"""
    base_dir = settings.BASE_DIR
    models_dir = os.path.join(base_dir, '..', 'algorithm', 'models')
    models_dir = os.path.normpath(models_dir)
    
    file_path = os.path.join(models_dir, file_name)
    
    # 安全检查：防止路径遍历攻击
    if not os.path.abspath(file_path).startswith(os.path.abspath(models_dir)):
        return APIResponse.error(message='非法文件路径')
    
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return APIResponse.error(message='文件不存在')
    
    from django.http import FileResponse
    response = FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=file_name
    )
    return response
