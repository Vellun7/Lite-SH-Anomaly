"""
设备分组管理视图
"""

from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from devices.models import Device, DeviceGroup
from devices.serializers import (
    DeviceGroupSerializer, DeviceGroupCreateSerializer, DeviceGroupUpdateSerializer,
    BatchGroupAssignSerializer, GroupDeviceOperationSerializer, DeviceSerializer
)
from devices.services.group_service import DeviceGroupService
from common.response import APIResponse
from users.models import AuditLog


@extend_schema_view(
    list=extend_schema(
        summary="获取设备分组列表",
        description="获取所有设备分组，支持树形结构",
        parameters=[
            OpenApiParameter(name='tree', type=bool, description='是否返回树形结构'),
            OpenApiParameter(name='parent_id', type=int, description='父分组ID'),
        ]
    ),
    create=extend_schema(
        summary="创建设备分组",
        description="创建新的设备分组"
    ),
    retrieve=extend_schema(
        summary="获取分组详情",
        description="获取指定分组的详细信息"
    ),
    update=extend_schema(
        summary="更新设备分组",
        description="更新设备分组信息"
    ),
    destroy=extend_schema(
        summary="删除设备分组",
        description="删除设备分组（会将设备移到未分组）"
    )
)
class DeviceGroupViewSet(viewsets.ModelViewSet):
    """设备分组管理视图集"""
    
    queryset = DeviceGroup.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DeviceGroupCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DeviceGroupUpdateSerializer
        return DeviceGroupSerializer
    
    def list(self, request):
        """获取设备分组列表"""
        try:
            tree = request.query_params.get('tree', 'false').lower() == 'true'
            parent_id = request.query_params.get('parent_id')
            
            if tree:
                groups = DeviceGroupService.get_group_tree()
                return APIResponse.success(data=groups, message="获取分组树成功")
            else:
                queryset = self.get_queryset()
                if parent_id:
                    queryset = queryset.filter(parent_id=parent_id)
                
                # 按设备数量降序排序，有设备的分组优先展示
                queryset = queryset.annotate(
                    devices_count=models.Count('devices')
                ).order_by('-devices_count', 'name')
                
                serializer = self.get_serializer(queryset, many=True)
                return APIResponse.success(data=serializer.data, message="获取分组列表成功")
                
        except Exception as e:
            return APIResponse.error(message=f"获取分组列表失败: {str(e)}")
    
    def create(self, request):
        """创建设备分组"""
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                group = serializer.save()
                
                # 记录审计日志
                AuditLog.log(
                    user=request.user if request.user.is_authenticated else None,
                    action='create',
                    resource_type='device_group',
                    resource_id=group.id,
                    resource_name=group.name,
                    description=f'创建设备分组：{group.name}',
                    request=request,
                    result='success',
                    new_value={
                        'id': group.id,
                        'name': group.name,
                        'description': group.description,
                        'parent_id': group.parent_id,
                    }
                )
                
                return APIResponse.success(
                    data=DeviceGroupSerializer(group).data,
                    message="创建分组成功"
                )
            return APIResponse.error(message="数据验证失败", data=serializer.errors)
            
        except Exception as e:
            return APIResponse.error(message=f"创建分组失败: {str(e)}")
    
    def update(self, request, pk=None):
        """更新设备分组"""
        try:
            group = self.get_object()
            
            # 记录更新前的数据
            old_data = {
                'name': group.name,
                'description': group.description,
                'parent_id': group.parent_id,
            }
            
            serializer = self.get_serializer(group, data=request.data)
            if serializer.is_valid():
                group = serializer.save()
                
                new_data = {
                    'name': group.name,
                    'description': group.description,
                    'parent_id': group.parent_id,
                }
                
                # 记录审计日志
                AuditLog.log(
                    user=request.user if request.user.is_authenticated else None,
                    action='update',
                    resource_type='device_group',
                    resource_id=group.id,
                    resource_name=group.name,
                    description=f'更新设备分组：{group.name}',
                    request=request,
                    result='success',
                    old_value=old_data,
                    new_value=new_data
                )
                
                return APIResponse.success(
                    data=DeviceGroupSerializer(group).data,
                    message="更新分组成功"
                )
            return APIResponse.error(message="数据验证失败", data=serializer.errors)
            
        except Exception as e:
            return APIResponse.error(message=f"更新分组失败: {str(e)}")
    
    def destroy(self, request, pk=None):
        """删除设备分组"""
        try:
            group = self.get_object()
            group_name = group.name
            group_id = group.id
            
            # 记录分组信息用于日志
            group_info = {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'device_count': group.devices.count(),
            }
            
            # 将分组下的设备移到未分组
            devices = group.devices.all()
            device_ids = list(devices.values_list('device_id', flat=True))
            for device in devices:
                device.groups.remove(group)
            
            group.delete()
            
            # 记录审计日志
            AuditLog.log(
                user=request.user if request.user.is_authenticated else None,
                action='delete',
                resource_type='device_group',
                resource_id=group_id,
                resource_name=group_name,
                description=f'删除设备分组：{group_name}，涉及 {len(device_ids)} 个设备',
                request=request,
                result='success',
                old_value=group_info
            )
            
            return APIResponse.success(message=f"删除分组 '{group_name}' 成功")
            
        except Exception as e:
            return APIResponse.error(message=f"删除分组失败: {str(e)}")
    
    @extend_schema(
        summary="获取分组下的设备",
        description="获取指定分组下的所有设备",
        parameters=[
            OpenApiParameter(name='page', type=int, description='页码'),
            OpenApiParameter(name='page_size', type=int, description='每页数量'),
        ]
    )
    @action(detail=True, methods=['get'])
    def devices(self, request, pk=None):
        """获取分组下的设备"""
        try:
            group = self.get_object()
            devices = group.devices.all()
            
            # 分页处理
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            
            start = (page - 1) * page_size
            end = start + page_size
            
            total = devices.count()
            devices_page = devices[start:end]
            
            serializer = DeviceSerializer(devices_page, many=True)
            
            return APIResponse.success(data={
                'count': total,
                'results': serializer.data
            }, message="获取分组设备成功")
            
        except Exception as e:
            return APIResponse.error(message=f"获取分组设备失败: {str(e)}")
    
    @extend_schema(
        summary="添加设备到分组",
        description="将指定设备添加到分组中",
        request=GroupDeviceOperationSerializer
    )
    @action(detail=True, methods=['post'])
    def add_devices(self, request, pk=None):
        """添加设备到分组"""
        try:
            group = self.get_object()
            serializer = GroupDeviceOperationSerializer(data=request.data)
            
            if serializer.is_valid():
                device_ids = serializer.validated_data['device_ids']
                
                success_count = 0
                added_devices = []
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        device.groups.add(group)
                        success_count += 1
                        added_devices.append({'device_id': device_id, 'name': device.name})
                    except Device.DoesNotExist:
                        continue
                
                # 记录审计日志
                AuditLog.log(
                    user=request.user if request.user.is_authenticated else None,
                    action='update',
                    resource_type='device_group',
                    resource_id=group.id,
                    resource_name=group.name,
                    description=f'向分组 {group.name} 添加 {success_count} 个设备',
                    request=request,
                    result='success',
                    new_value={'added_devices': added_devices}
                )
                
                return APIResponse.success(
                    data={'success_count': success_count},
                    message=f"成功添加 {success_count} 个设备到分组"
                )
            
            return APIResponse.error(message="数据验证失败", data=serializer.errors)
            
        except Exception as e:
            return APIResponse.error(message=f"添加设备到分组失败: {str(e)}")
    
    @extend_schema(
        summary="从分组移除设备",
        description="将指定设备从分组中移除",
        request=GroupDeviceOperationSerializer
    )
    @action(detail=True, methods=['post'])
    def remove_devices(self, request, pk=None):
        """从分组移除设备"""
        try:
            group = self.get_object()
            serializer = GroupDeviceOperationSerializer(data=request.data)
            
            if serializer.is_valid():
                device_ids = serializer.validated_data['device_ids']
                
                success_count = 0
                removed_devices = []
                for device_id in device_ids:
                    try:
                        device = Device.objects.get(device_id=device_id)
                        device.groups.remove(group)
                        success_count += 1
                        removed_devices.append({'device_id': device_id, 'name': device.name})
                    except Device.DoesNotExist:
                        continue
                
                # 记录审计日志
                AuditLog.log(
                    user=request.user if request.user.is_authenticated else None,
                    action='update',
                    resource_type='device_group',
                    resource_id=group.id,
                    resource_name=group.name,
                    description=f'从分组 {group.name} 移除 {success_count} 个设备',
                    request=request,
                    result='success',
                    old_value={'removed_devices': removed_devices}
                )
                
                return APIResponse.success(
                    data={'success_count': success_count},
                    message=f"成功从分组移除 {success_count} 个设备"
                )
            
            return APIResponse.error(message="数据验证失败", data=serializer.errors)
            
        except Exception as e:
            return APIResponse.error(message=f"从分组移除设备失败: {str(e)}")
    
    @extend_schema(
        summary="批量分配设备分组",
        description="批量为设备分配分组",
        request=BatchGroupAssignSerializer
    )
    @action(detail=False, methods=['post'])
    def batch_assign(self, request):
        """批量分配设备分组"""
        try:
            serializer = BatchGroupAssignSerializer(data=request.data)
            
            if serializer.is_valid():
                device_ids = serializer.validated_data['device_ids']
                group_ids = serializer.validated_data['group_ids']
                
                result = DeviceGroupService.batch_assign_groups(device_ids, group_ids)
                
                # 记录审计日志
                AuditLog.log(
                    user=request.user if request.user.is_authenticated else None,
                    action='update',
                    resource_type='device_group',
                    resource_name='批量分配',
                    description=f'批量分配 {len(device_ids)} 个设备到 {len(group_ids)} 个分组',
                    request=request,
                    result='success',
                    new_value={
                        'device_ids': device_ids,
                        'group_ids': group_ids,
                        'success_count': result['success_count']
                    }
                )
                
                return APIResponse.success(
                    data=result,
                    message=f"批量分配完成，成功处理 {result['success_count']} 个设备"
                )
            
            return APIResponse.error(message="数据验证失败", data=serializer.errors)
            
        except Exception as e:
            return APIResponse.error(message=f"批量分配失败: {str(e)}")
    
    @extend_schema(
        summary="获取未分组设备",
        description="获取所有未分组的设备",
        parameters=[
            OpenApiParameter(name='page', type=int, description='页码'),
            OpenApiParameter(name='page_size', type=int, description='每页数量'),
        ]
    )
    @action(detail=False, methods=['get'])
    def ungrouped_devices(self, request):
        """获取未分组设备"""
        try:
            devices = DeviceGroupService.get_ungrouped_devices()
            
            # 分页处理
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            
            start = (page - 1) * page_size
            end = start + page_size
            
            total = devices.count()
            devices_page = devices[start:end]
            
            serializer = DeviceSerializer(devices_page, many=True)
            
            return APIResponse.success(data={
                'count': total,
                'results': serializer.data
            }, message="获取未分组设备成功")
            
        except Exception as e:
            return APIResponse.error(message=f"获取未分组设备失败: {str(e)}")