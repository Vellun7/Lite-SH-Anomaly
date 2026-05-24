"""
检测视图层 - RESTful API
"""

import os
import uuid
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, JSONParser
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from detection.models import DetectionRecord, DetectionTask
from detection.serializers import (
    DetectionRecordSerializer, DetectionInputSerializer,
    DetectionBatchInputSerializer, DetectionResultSerializer,
    DetectionTaskSerializer, DetectionStatsSerializer,
    ContinuousDetectionConfigSerializer, ContinuousDetectionStatusSerializer,
    MonitoringKpiSerializer, MonitoringTrendSerializer,
    MonitoringDeviceRiskSerializer, MonitoringScoreConfidenceSerializer,
    MonitoringTrafficFeatureSerializer,
    FeedbackInputSerializer, IncrementalLearningSerializer,
)
from detection.services import DetectionService, ModelService
from detection.services.continuous_service import continuous_detection_service
from common.response import APIResponse
from users.models import AuditLog


class DetectionViewSet(viewsets.ViewSet):
    """
    异常检测API
    
    RESTful接口:
    - POST   /api/v1/detection/detect/       单条检测
    - POST   /api/v1/detection/batch/        批量检测
    - POST   /api/v1/detection/upload/       上传CSV检测
    - GET    /api/v1/detection/records/      检测记录列表
    - GET    /api/v1/detection/records/{id}/ 检测记录详情
    - GET    /api/v1/detection/stats/        检测统计
    - GET    /api/v1/detection/tasks/        任务列表
    - GET    /api/v1/detection/model-info/   模型信息
    - GET    /api/v1/detection/continuous/   获取持续检测状态
    - POST   /api/v1/detection/continuous/   开启/关闭持续检测
    """
    
    parser_classes = [JSONParser, MultiPartParser]

    @staticmethod
    def _parse_iso_datetime(value):
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
        if value.endswith('Z'):
            value = value.replace('Z', '+00:00')
        return datetime.fromisoformat(value)

    def _get_monitoring_query_params(self, request):
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        device_id = request.query_params.get('device_id')
        attack_type = request.query_params.get('attack_type')
        protocol = request.query_params.get('protocol')
        is_anomaly = request.query_params.get('is_anomaly')
        granularity = request.query_params.get('granularity')

        if is_anomaly is not None:
            is_anomaly = is_anomaly.lower() == 'true'

        if start_time:
            start_time = self._parse_iso_datetime(start_time)
        if end_time:
            end_time = self._parse_iso_datetime(end_time)

        return {
            'start_time': start_time,
            'end_time': end_time,
            'device_id': device_id,
            'attack_type': attack_type,
            'protocol': protocol,
            'is_anomaly': is_anomaly,
            'granularity': granularity,
        }
    
    @extend_schema(
        tags=['detection'],
        summary='单条数据检测',
        description='对单条网络流量数据进行异常检测，返回检测结果',
        request=DetectionInputSerializer,
        responses={200: DetectionResultSerializer},
    )
    @action(detail=False, methods=['post'])
    def detect(self, request):
        """单条数据检测"""
        serializer = DetectionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors
            )
        
        result = DetectionService.detect_single(serializer.validated_data)
        
        # 记录审计日志
        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='create',
            resource_type='detection_result',
            resource_name='单条检测',
            description=f'执行单条数据异常检测，结果：{"异常" if result.get("is_anomaly") else "正常"}',
            request=request,
            result='success',
            new_value={
                'is_anomaly': result.get('is_anomaly'),
                'anomaly_score': result.get('anomaly_score'),
                'attack_type': result.get('attack_type'),
            }
        )
        
        return APIResponse.success(
            data=result,
            message='检测完成'
        )
    
    @extend_schema(
        tags=['detection'],
        summary='批量数据检测',
        description='对多条网络流量数据进行批量异常检测',
        request=DetectionBatchInputSerializer,
    )
    @action(detail=False, methods=['post'])
    def batch(self, request):
        """批量数据检测"""
        serializer = DetectionBatchInputSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors
            )
        
        result = DetectionService.detect_batch(serializer.validated_data['data'])
        
        # 记录审计日志
        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='create',
            resource_type='detection_result',
            resource_name='批量检测',
            description=f'执行批量数据异常检测，共 {result["total"]} 条，异常 {result.get("anomaly_count", 0)} 条',
            request=request,
            result='success',
            new_value={
                'total': result.get('total'),
                'anomaly_count': result.get('anomaly_count'),
            }
        )
        
        return APIResponse.success(
            data=result,
            message=f'批量检测完成，共{result["total"]}条'
        )
    
    @extend_schema(
        tags=['detection'],
        summary='上传CSV文件检测',
        description='上传CSV格式的流量数据文件进行批量检测',
        request={'multipart/form-data': {'type': 'object', 'properties': {'file': {'type': 'string', 'format': 'binary'}}}},
    )
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser])
    def upload(self, request):
        """上传CSV文件进行检测"""
        file = request.FILES.get('file')
        if not file:
            return APIResponse.error(message='请上传CSV文件')
        
        if not file.name.endswith('.csv'):
            return APIResponse.error(message='仅支持CSV格式文件')
        
        # 保存临时文件
        task_id = str(uuid.uuid4())[:8]
        temp_dir = '/tmp/detection_uploads'
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f'{task_id}_{file.name}')
        
        with open(file_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)
        
        try:
            result = DetectionService.detect_from_csv(file_path, task_id)
            
            # 记录审计日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='import',
                resource_type='detection_result',
                resource_name=file.name,
                description=f'上传CSV文件进行检测：{file.name}，共 {result.get("total", 0)} 条记录',
                request=request,
                result='success',
                new_value={
                    'file_name': file.name,
                    'task_id': task_id,
                    'total': result.get('total'),
                    'anomaly_count': result.get('anomaly_count'),
                }
            )
            
            return APIResponse.success(
                data=result,
                message='CSV检测完成'
            )
        except Exception as e:
            # 记录失败日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='import',
                resource_type='detection_result',
                resource_name=file.name,
                description=f'上传CSV文件检测失败：{file.name}',
                request=request,
                result='failed',
                error_message=str(e)
            )
            return APIResponse.error(message=str(e))
        finally:
            # 清理临时文件
            if os.path.exists(file_path):
                os.remove(file_path)
    
    @extend_schema(
        tags=['detection'],
        summary='获取检测记录列表',
        description='查询历史检测记录，支持按设备、攻击类型、时间范围筛选',
        parameters=[
            OpenApiParameter(name='device_id', description='设备ID', required=False, type=str),
            OpenApiParameter(name='attack_type', description='攻击类型', required=False, type=str),
            OpenApiParameter(name='is_anomaly', description='是否异常', required=False, type=bool),
            OpenApiParameter(name='start_time', description='开始时间(ISO格式)', required=False, type=str),
            OpenApiParameter(name='end_time', description='结束时间(ISO格式)', required=False, type=str),
        ],
        responses={200: DetectionRecordSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def records(self, request):
        """获取检测记录列表"""
        device_id = request.query_params.get('device_id')
        attack_type = request.query_params.get('attack_type')
        is_anomaly = request.query_params.get('is_anomaly')
        start_time = request.query_params.get('start_time')
        end_time = request.query_params.get('end_time')
        
        # 处理布尔参数
        if is_anomaly is not None:
            is_anomaly = is_anomaly.lower() == 'true'
        
        # 处理时间参数
        if start_time:
            start_time = self._parse_iso_datetime(start_time)
        if end_time:
            end_time = self._parse_iso_datetime(end_time)
        
        records = DetectionService.get_detection_records(
            device_id=device_id,
            attack_type=attack_type,
            is_anomaly=is_anomaly,
            start_time=start_time,
            end_time=end_time
        )
        
        return APIResponse.paginated(records, DetectionRecordSerializer, request)
    
    @extend_schema(
        tags=['detection'],
        summary='获取检测记录详情',
        description='根据记录ID获取检测记录详细信息',
        parameters=[
            OpenApiParameter(name='record_id', description='记录ID', required=True, type=int, location=OpenApiParameter.PATH),
        ],
    )
    @action(detail=False, methods=['get'], url_path='records/(?P<record_id>[^/.]+)')
    def record_detail(self, request, record_id=None):
        """获取检测记录详情"""
        try:
            record = DetectionRecord.objects.get(id=record_id)
            return APIResponse.success(data=DetectionRecordSerializer(record).data)
        except DetectionRecord.DoesNotExist:
            return APIResponse.not_found('检测记录不存在')
    
    @extend_schema(
        tags=['detection'],
        summary='获取检测统计数据',
        description='获取指定天数内的检测统计数据，包括异常率、攻击分布、趋势等',
        parameters=[
            OpenApiParameter(name='days', description='统计天数', required=False, type=int, default=7),
        ],
        responses={200: DetectionStatsSerializer},
    )
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取检测统计数据"""
        days = int(request.query_params.get('days', 7))
        stats = DetectionService.get_statistics(days=days)
        return APIResponse.success(data=stats)

    @extend_schema(
        tags=['detection'],
        summary='检测结果概览KPI',
        description='获取检测结果概览的关键指标',
        responses={200: MonitoringKpiSerializer},
    )
    @action(detail=False, methods=['get'], url_path='monitoring/kpi')
    def monitoring_kpi(self, request):
        """检测结果概览KPI"""
        params = self._get_monitoring_query_params(request)
        data = DetectionService.get_monitoring_kpi(**params)
        return APIResponse.success(data=data)

    @extend_schema(
        tags=['detection'],
        summary='异常趋势与检测频率',
        description='获取异常趋势与检测频率数据',
        responses={200: MonitoringTrendSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='monitoring/trend')
    def monitoring_trend(self, request):
        """异常趋势与检测频率"""
        params = self._get_monitoring_query_params(request)
        data = DetectionService.get_anomaly_trend(**params)
        return APIResponse.success(data=data)

    @extend_schema(
        tags=['detection'],
        summary='设备风险排行',
        description='获取设备风险排行数据',
        responses={200: MonitoringDeviceRiskSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='monitoring/device-risk')
    def monitoring_device_risk(self, request):
        """设备风险排行"""
        params = self._get_monitoring_query_params(request)
        data = DetectionService.get_device_risk_ranking(**params)
        return APIResponse.success(data=data)

    @extend_schema(
        tags=['detection'],
        summary='异常分数与置信度分析',
        description='获取异常分数与置信度散点数据',
        responses={200: MonitoringScoreConfidenceSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='monitoring/score-confidence')
    def monitoring_score_confidence(self, request):
        """异常分数与置信度分析"""
        params = self._get_monitoring_query_params(request)
        data = DetectionService.get_score_confidence_analysis(**params)
        return APIResponse.success(data=data)

    @extend_schema(
        tags=['detection'],
        summary='流量特征与异常关联',
        description='获取流量特征与异常关联数据',
        responses={200: MonitoringTrafficFeatureSerializer(many=True)},
    )
    @action(detail=False, methods=['get'], url_path='monitoring/traffic-feature')
    def monitoring_traffic_feature(self, request):
        """流量特征与异常关联"""
        params = self._get_monitoring_query_params(request)
        data = DetectionService.get_traffic_feature_association(**params)
        return APIResponse.success(data=data)
    
    @extend_schema(
        tags=['detection'],
        summary='获取检测任务列表',
        description='获取CSV批量检测任务列表及其状态',
        responses={200: DetectionTaskSerializer(many=True)},
    )
    @action(detail=False, methods=['get'])
    def tasks(self, request):
        """获取检测任务列表"""
        tasks = DetectionTask.objects.all()[:20]
        serializer = DetectionTaskSerializer(tasks, many=True)
        return APIResponse.success(data=serializer.data)
    
    @extend_schema(
        tags=['detection'],
        summary='获取模型信息',
        description='获取当前加载的检测模型信息，包括版本、特征列表、支持的攻击类型',
    )
    @action(detail=False, methods=['get'], url_path='model-info')
    def model_info(self, request):
        """获取模型信息"""
        model_service = ModelService()
        return APIResponse.success(data={
            'is_loaded': model_service.is_loaded,
            'model_version': model_service.model_version,
            'features': [
                'duration', 'orig_bytes', 'resp_bytes', 'orig_pkts',
                'resp_pkts', 'proto_encoded', 'bytes_ratio', 'pkts_ratio'
            ],
            'attack_types': ['normal', 'ddos', 'port_scan', 'unauthorized', 'malformed', 'unknown']
        })

    @extend_schema(
        tags=['detection'],
        summary='持续检测管理',
        description='GET获取持续检测状态，POST开启/关闭持续检测',
        request=ContinuousDetectionConfigSerializer,
        responses={200: ContinuousDetectionStatusSerializer},
    )
    @action(detail=False, methods=['get', 'post'], url_path='continuous')
    def continuous(self, request):
        """
        持续检测管理

        GET: 获取当前配置和运行状态
        POST: 开启或关闭持续检测
        """
        if request.method == 'GET':
            config = continuous_detection_service.get_config()
            return APIResponse.success(data=config)

        # POST
        serializer = ContinuousDetectionConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors,
            )

        enabled = serializer.validated_data['enabled']
        interval = serializer.validated_data.get('interval', 5)
        target_devices = serializer.validated_data.get('target_devices', [])

        if enabled:
            config = continuous_detection_service.start(
                interval=interval,
                target_devices=target_devices,
            )
            
            # 记录审计日志 - 启动持续检测
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='start',
                resource_type='detection_task',
                resource_name='持续检测',
                description=f'启动持续检测，间隔 {interval} 秒，目标设备 {len(target_devices)} 个',
                request=request,
                result='success',
                new_value={
                    'enabled': True,
                    'interval': interval,
                    'target_devices': target_devices,
                }
            )
            
            return APIResponse.success(data=config, message='持续检测已启动')
        else:
            config = continuous_detection_service.stop()
            
            # 记录审计日志 - 停止持续检测
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='stop',
                resource_type='detection_task',
                resource_name='持续检测',
                description='停止持续检测',
                request=request,
                result='success',
                new_value={'enabled': False}
            )
            
            return APIResponse.success(data=config, message='持续检测已停止')

    @extend_schema(
        tags=['detection'],
        summary='提交检测反馈（增量学习）',
        description='对检测结果进行人工确认/纠正，反馈数据将用于模型的增量学习更新',
        request=FeedbackInputSerializer,
    )
    @action(detail=False, methods=['post'], url_path='feedback')
    def submit_feedback(self, request):
        """提交检测结果反馈，用于增量学习"""
        serializer = FeedbackInputSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors
            )

        record_id = serializer.validated_data['record_id']
        is_anomaly = serializer.validated_data['is_anomaly']

        result = model_service.submit_feedback(record_id, is_anomaly)

        if not result['success']:
            return APIResponse.error(message=result['message'])

        # 记录审计日志
        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='update',
            resource_type='detection_feedback',
            resource_name=f'记录{record_id}',
            description=f'提交检测反馈: {result["feedback_label"]}',
            request=request,
            result='success',
            new_value={
                'record_id': record_id,
                'feedback_label': result['feedback_label'],
                'update_triggered': result['update_triggered'],
            }
        )

        return APIResponse.success(data=result, message='反馈已提交')

    @extend_schema(
        tags=['detection'],
        summary='获取增量学习状态',
        description='获取当前增量学习的反馈缓冲区状态、模型版本、更新历史',
        responses={200: IncrementalLearningSerializer},
    )
    @action(detail=False, methods=['get'], url_path='incremental-status')
    def incremental_status(self, request):
        """获取增量学习状态"""
        status_data = model_service.get_incremental_status()
        return APIResponse.success(data=status_data)

    @extend_schema(
        tags=['detection'],
        summary='手动触发增量更新',
        description='强制使用当前反馈缓冲区中的数据立即触发一次模型增量更新',
    )
    @action(detail=False, methods=['post'], url_path='incremental-update')
    def incremental_update(self, request):
        """手动强制触发增量模型更新"""
        result = model_service.force_update()

        if not result['success']:
            return APIResponse.error(message=result['message'])

        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='update',
            resource_type='detection_model',
            resource_name='增量学习',
            description=f'手动触发模型增量更新，新版本: {result["new_version"]}',
            request=request,
            result='success',
            new_value=result,
        )

        return APIResponse.success(data=result, message=f'模型已更新至 {result["new_version"]}')