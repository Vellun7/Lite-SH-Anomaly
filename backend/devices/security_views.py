"""
设备安全评分管理视图
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from devices.models import Device
from devices.services.security_service import DeviceSecurityService
from common.response import APIResponse


@extend_schema_view(
    list=extend_schema(
        summary="设备安全评分管理",
        description="设备安全评分相关操作的入口"
    )
)
class DeviceSecurityViewSet(viewsets.ViewSet):
    """设备安全评分管理视图集"""
    
    @extend_schema(
        summary="获取设备安全评分",
        description="获取指定设备的安全评分信息",
        parameters=[
            OpenApiParameter(name='device_id', type=str, description='设备ID', required=True),
        ]
    )
    @action(detail=False, methods=['get'])
    def score(self, request):
        """获取设备安全评分"""
        try:
            device_id = request.query_params.get('device_id')
            if not device_id:
                return APIResponse.error(message="设备ID不能为空")
            
            try:
                device = Device.objects.get(device_id=device_id)
            except Device.DoesNotExist:
                return APIResponse.error(message="设备不存在")
            
            return APIResponse.success(data={
                'device_id': device.device_id,
                'security_score': device.security_score,
                'security_level': device.security_level,
                'last_score_update': device.last_score_update
            }, message="获取安全评分成功")
            
        except Exception as e:
            return APIResponse.error(message=f"获取安全评分失败: {str(e)}")
    
    @extend_schema(
        summary="更新设备安全评分",
        description="重新计算并更新指定设备的安全评分",
        request={
            'type': 'object',
            'properties': {
                'device_id': {'type': 'string', 'description': '设备ID'}
            },
            'required': ['device_id']
        }
    )
    @action(detail=False, methods=['post'])
    def update_score(self, request):
        """更新设备安全评分"""
        try:
            device_id = request.data.get('device_id')
            if not device_id:
                return APIResponse.error(message="设备ID不能为空")
            
            try:
                device = Device.objects.get(device_id=device_id)
            except Device.DoesNotExist:
                return APIResponse.error(message="设备不存在")
            
            # 重新计算安全评分
            new_score = DeviceSecurityService.calculate_device_security_score(device_id)
            
            return APIResponse.success(data={
                'device_id': device_id,
                'old_score': device.security_score,
                'new_score': new_score,
                'security_level': device.security_level
            }, message="安全评分更新成功")
            
        except Exception as e:
            return APIResponse.error(message=f"更新安全评分失败: {str(e)}")
    
    @extend_schema(
        summary="批量更新安全评分",
        description="批量更新多个设备的安全评分",
        request={
            'type': 'object',
            'properties': {
                'device_ids': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '设备ID列表，为空则更新所有设备'
                }
            }
        }
    )
    @action(detail=False, methods=['post'])
    def batch_update_scores(self, request):
        """批量更新安全评分"""
        try:
            device_ids = request.data.get('device_ids', [])
            
            result = DeviceSecurityService.batch_update_security_scores(device_ids)
            
            return APIResponse.success(
                data=result,
                message=f"批量更新完成，成功更新 {result['success_count']} 个设备"
            )
            
        except Exception as e:
            return APIResponse.error(message=f"批量更新安全评分失败: {str(e)}")
    
    @extend_schema(
        summary="获取安全评分历史",
        description="获取指定设备的安全评分历史趋势",
        parameters=[
            OpenApiParameter(name='device_id', type=str, description='设备ID', required=True),
            OpenApiParameter(name='days', type=int, description='查询天数，默认30天'),
        ]
    )
    @action(detail=False, methods=['get'])
    def score_history(self, request):
        """获取安全评分历史"""
        try:
            device_id = request.query_params.get('device_id')
            if not device_id:
                return APIResponse.error(message="设备ID不能为空")
            
            days = int(request.query_params.get('days', 30))
            
            try:
                device = Device.objects.get(device_id=device_id)
            except Device.DoesNotExist:
                return APIResponse.error(message="设备不存在")
            
            history = DeviceSecurityService.get_security_score_history(device_id, days)
            
            return APIResponse.success(data={
                'device_id': device_id,
                'days': days,
                'history': history
            }, message="获取评分历史成功")
            
        except Exception as e:
            return APIResponse.error(message=f"获取评分历史失败: {str(e)}")
    
    @extend_schema(
        summary="获取安全概览",
        description="获取所有设备的安全状况概览统计"
    )
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """获取安全概览"""
        try:
            overview = DeviceSecurityService.get_security_overview()
            
            return APIResponse.success(
                data=overview,
                message="获取安全概览成功"
            )
            
        except Exception as e:
            return APIResponse.error(message=f"获取安全概览失败: {str(e)}")