"""
设备视图层 - RESTful API
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from devices.models import Device
from devices.serializers import (
    DeviceSerializer, DeviceCreateSerializer, 
    DeviceUpdateSerializer, DeviceOverviewSerializer
)
from devices.services import DeviceService
from devices.services.device_status_service import DeviceStatusService, DeviceStatusConfig
from devices.services.device_status_scheduler import device_status_scheduler
from common.response import APIResponse
from users.models import AuditLog


@extend_schema_view(
    list=extend_schema(
        tags=['devices'],
        summary='获取设备列表',
        description='获取所有设备列表，支持按类型、状态、关键词筛选',
        parameters=[
            OpenApiParameter(name='device_type', description='设备类型', required=False, type=str),
            OpenApiParameter(name='status', description='设备状态', required=False, type=str),
            OpenApiParameter(name='keyword', description='搜索关键词', required=False, type=str),
        ]
    ),
    create=extend_schema(
        tags=['devices'],
        summary='创建设备',
        description='创建新的智能家居设备',
        request=DeviceCreateSerializer,
    ),
    retrieve=extend_schema(
        tags=['devices'],
        summary='获取设备详情',
        description='根据设备ID获取设备详细信息',
    ),
    update=extend_schema(
        tags=['devices'],
        summary='更新设备',
        description='更新设备信息',
        request=DeviceUpdateSerializer,
    ),
    destroy=extend_schema(
        tags=['devices'],
        summary='删除设备',
        description='删除指定设备',
    ),
)
class DeviceViewSet(viewsets.ViewSet):
    """
    设备管理API
    
    RESTful接口:
    - GET    /api/v1/devices/           获取设备列表
    - POST   /api/v1/devices/           创建设备
    - GET    /api/v1/devices/{id}/      获取设备详情
    - PUT    /api/v1/devices/{id}/      更新设备
    - DELETE /api/v1/devices/{id}/      删除设备
    - GET    /api/v1/devices/overview/  获取设备概览
    """
    
    def list(self, request):
        """获取设备列表"""
        device_type = request.query_params.get('device_type')
        device_status = request.query_params.get('status')
        keyword = request.query_params.get('keyword')
        
        devices = DeviceService.get_device_list(
            device_type=device_type,
            status=device_status,
            keyword=keyword
        )
        
        return APIResponse.paginated(devices, DeviceSerializer, request)
    
    def create(self, request):
        """创建设备"""
        serializer = DeviceCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors
            )
        
        device = DeviceService.create_device(serializer.validated_data)
        
        # 记录审计日志
        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='create',
            resource_type='device',
            resource_id=device.device_id,
            resource_name=device.name,
            description=f'创建设备：{device.name} (ID: {device.device_id}，类型: {device.device_type})',
            request=request,
            result='success',
            new_value={
                'device_id': device.device_id,
                'name': device.name,
                'device_type': device.device_type,
                'manufacturer': device.manufacturer,
                'model': device.model,
            }
        )
        
        return APIResponse.created(
            data=DeviceSerializer(device).data,
            message='设备创建成功'
        )
    
    def retrieve(self, request, pk=None):
        """获取设备详情"""
        try:
            device = DeviceService.get_device_by_id(pk)
            return APIResponse.success(data=DeviceSerializer(device).data)
        except Exception as e:
            return APIResponse.not_found(str(e))
    
    def update(self, request, pk=None):
        """更新设备"""
        serializer = DeviceUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return APIResponse.error(
                message='参数验证失败',
                data=serializer.errors
            )
        
        try:
            # 获取更新前的设备信息
            old_device = DeviceService.get_device_by_id(pk)
            old_data = {
                'name': old_device.name,
                'device_type': old_device.device_type,
                'manufacturer': old_device.manufacturer,
                'model': old_device.model,
                'location': old_device.location,
            }
            
            device = DeviceService.update_device(pk, serializer.validated_data)
            
            new_data = {
                'name': device.name,
                'device_type': device.device_type,
                'manufacturer': device.manufacturer,
                'model': device.model,
                'location': device.location,
            }
            
            # 记录审计日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='update',
                resource_type='device',
                resource_id=device.device_id,
                resource_name=device.name,
                description=f'更新设备：{device.name} (ID: {device.device_id})',
                request=request,
                result='success',
                old_value=old_data,
                new_value=new_data
            )
            
            return APIResponse.success(
                data=DeviceSerializer(device).data,
                message='设备更新成功'
            )
        except Exception as e:
            return APIResponse.not_found(str(e))
    
    def destroy(self, request, pk=None):
        """删除设备"""
        try:
            # 获取设备信息用于日志记录
            device = DeviceService.get_device_by_id(pk)
            device_info = {
                'device_id': device.device_id,
                'name': device.name,
                'device_type': device.device_type,
            }
            device_name = device.name
            device_id = device.device_id
            
            DeviceService.delete_device(pk)
            
            # 记录审计日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='delete',
                resource_type='device',
                resource_id=device_id,
                resource_name=device_name,
                description=f'删除设备：{device_name} (ID: {device_id})',
                request=request,
                result='success',
                old_value=device_info
            )
            
            return APIResponse.success(message='设备删除成功')
        except Exception as e:
            return APIResponse.not_found(str(e))
    
    @extend_schema(
        tags=['devices'],
        summary='获取设备概览',
        description='获取设备统计概览，包括在线/离线/告警数量及类型分布',
    )
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """获取设备概览统计"""
        data = DeviceService.get_device_overview()
        return APIResponse.success(data=data)
    
    @extend_schema(
        tags=['devices'],
        summary='更新设备状态',
        description='更新指定设备的在线状态',
    )
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """更新设备状态"""
        new_status = request.data.get('status')
        if not new_status:
            return APIResponse.error(message='请提供状态参数')
        
        try:
            # 获取更新前的状态
            old_device = DeviceService.get_device_by_id(pk)
            old_status = old_device.status
            
            device = DeviceService.update_device_status(pk, new_status)
            
            # 记录审计日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='update',
                resource_type='device',
                resource_id=device.device_id,
                resource_name=device.name,
                description=f'更新设备状态：{device.name} (ID: {device.device_id})，状态从 {old_status} 变更为 {new_status}',
                request=request,
                result='success',
                old_value={'status': old_status},
                new_value={'status': new_status}
            )
            
            return APIResponse.success(
                data=DeviceSerializer(device).data,
                message='状态更新成功'
            )
        except Exception as e:
            return APIResponse.not_found(str(e))
    
    @extend_schema(
        tags=['devices'],
        summary='批量设置检测状态',
        description='批量启用或禁用设备的异常检测',
    )
    @action(detail=False, methods=['post'])
    def batch_set_monitoring(self, request):
        """批量设置设备检测状态（is_trusted）"""
        device_ids = request.data.get('device_ids', [])
        enabled = request.data.get('enabled', True)  # True=启用检测, False=禁用检测
        
        if not device_ids:
            return APIResponse.error(message='请提供设备ID列表')
        
        try:
            # 批量更新
            updated_count = Device.objects.filter(device_id__in=device_ids).update(is_trusted=enabled)
            
            # 记录审计日志
            action_text = '启用' if enabled else '禁用'
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='update',
                resource_type='device',
                resource_id=','.join(device_ids[:5]) + ('...' if len(device_ids) > 5 else ''),
                resource_name=f'批量{action_text}检测',
                description=f'批量{action_text}检测：{updated_count}个设备',
                request=request,
                result='success',
                new_value={
                    'device_ids': device_ids,
                    'enabled': enabled,
                    'updated_count': updated_count
                }
            )
            
            return APIResponse.success(
                data={'updated_count': updated_count},
                message=f'已{action_text}{updated_count}个设备的检测'
            )
        except Exception as e:
            return APIResponse.error(message=str(e))
    
    @extend_schema(
        tags=['devices'],
        summary='获取设备状态配置',
        description='获取设备状态判断的阈值配置',
    )
    @action(detail=False, methods=['get'])
    def status_config(self, request):
        """获取设备状态判断配置"""
        return APIResponse.success(data={
            'sample_count': DeviceStatusConfig.SAMPLE_COUNT,
            'online_threshold': DeviceStatusConfig.ONLINE_THRESHOLD,
            'warning_threshold': DeviceStatusConfig.WARNING_THRESHOLD,
            'no_record_hours': DeviceStatusConfig.NO_RECORD_HOURS,
            'update_interval': device_status_scheduler.interval,
            'scheduler_running': device_status_scheduler.is_running,
            'description': {
                'sample_count': f'统计最近 {DeviceStatusConfig.SAMPLE_COUNT} 次检测记录',
                'online_threshold': f'正常率 >= {DeviceStatusConfig.ONLINE_THRESHOLD * 100}% 为在线',
                'warning_threshold': f'正常率 >= {DeviceStatusConfig.WARNING_THRESHOLD * 100}% 且 < {DeviceStatusConfig.ONLINE_THRESHOLD * 100}% 为告警',
                'offline': f'正常率 < {DeviceStatusConfig.WARNING_THRESHOLD * 100}% 或无记录为离线'
            }
        })
    
    @extend_schema(
        tags=['devices'],
        summary='手动刷新设备状态',
        description='立即刷新所有设备的状态（基于历史检测记录）',
    )
    @action(detail=False, methods=['post'])
    def refresh_status(self, request):
        """手动刷新所有设备状态"""
        try:
            result = DeviceStatusService.update_all_device_status()
            return APIResponse.success(
                data=result,
                message=f'设备状态已更新，共 {result["total_count"]} 台，更新 {result["updated_count"]} 台'
            )
        except Exception as e:
            return APIResponse.error(message=f'刷新失败: {str(e)}')
    
    @extend_schema(
        tags=['devices'],
        summary='获取设备健康报告',
        description='获取指定设备的详细健康状态报告',
    )
    @action(detail=True, methods=['get'])
    def health_report(self, request, pk=None):
        """获取设备健康报告"""
        report = DeviceStatusService.get_device_health_report(pk)
        if report is None:
            return APIResponse.not_found('设备不存在')
        return APIResponse.success(data=report)