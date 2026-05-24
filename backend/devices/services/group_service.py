"""
设备分组管理服务
"""

from typing import Optional, List, Dict, Any
from django.db.models import Count, Q
from django.db import transaction

from devices.models import Device, DeviceGroup
from common.exceptions import DeviceNotFoundException


class DeviceGroupService:
    """设备分组管理服务"""
    
    @staticmethod
    def get_group_list(parent_id: Optional[int] = None) -> List[DeviceGroup]:
        """获取分组列表"""
        queryset = DeviceGroup.objects.all()
        
        if parent_id is not None:
            queryset = queryset.filter(parent_id=parent_id)
        
        return queryset.annotate(device_count=Count('devices'))
    
    @staticmethod
    def get_group_tree() -> List[Dict[str, Any]]:
        """获取分组树形结构"""
        def build_tree(parent_id=None):
            groups = DeviceGroup.objects.filter(parent_id=parent_id).annotate(
                device_count=Count('devices')
            )
            tree = []
            for group in groups:
                node = {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'icon': group.icon,
                    'color': group.color,
                    'device_count': group.device_count,
                    'children': build_tree(group.id)
                }
                tree.append(node)
            return tree
        
        return build_tree()
    
    @staticmethod
    def get_group_by_id(group_id: int) -> DeviceGroup:
        """根据ID获取分组"""
        try:
            return DeviceGroup.objects.get(id=group_id)
        except DeviceGroup.DoesNotExist:
            raise DeviceNotFoundException(f'分组 {group_id} 不存在')
    
    @staticmethod
    def create_group(data: Dict[str, Any]) -> DeviceGroup:
        """创建分组"""
        return DeviceGroup.objects.create(**data)
    
    @staticmethod
    def update_group(group_id: int, data: Dict[str, Any]) -> DeviceGroup:
        """更新分组信息"""
        group = DeviceGroupService.get_group_by_id(group_id)
        for key, value in data.items():
            if hasattr(group, key):
                setattr(group, key, value)
        group.save()
        return group
    
    @staticmethod
    def delete_group(group_id: int) -> bool:
        """删除分组"""
        group = DeviceGroupService.get_group_by_id(group_id)
        
        # 检查是否有子分组
        if group.children.exists():
            raise ValueError('该分组下还有子分组，无法删除')
        
        # 移除设备关联
        group.devices.clear()
        group.delete()
        return True
    
    @staticmethod
    def add_devices_to_group(group_id: int, device_ids: List[str]) -> int:
        """将设备添加到分组"""
        group = DeviceGroupService.get_group_by_id(group_id)
        devices = Device.objects.filter(device_id__in=device_ids)
        
        added_count = 0
        for device in devices:
            if not group.devices.filter(id=device.id).exists():
                group.devices.add(device)
                added_count += 1
        
        return added_count
    
    @staticmethod
    def remove_devices_from_group(group_id: int, device_ids: List[str]) -> int:
        """从分组中移除设备"""
        group = DeviceGroupService.get_group_by_id(group_id)
        devices = Device.objects.filter(device_id__in=device_ids)
        
        removed_count = 0
        for device in devices:
            if group.devices.filter(id=device.id).exists():
                group.devices.remove(device)
                removed_count += 1
        
        return removed_count
    
    @staticmethod
    def get_group_devices(group_id: int) -> List[Device]:
        """获取分组下的设备列表"""
        group = DeviceGroupService.get_group_by_id(group_id)
        return group.devices.all()
    
    @staticmethod
    def get_ungrouped_devices() -> List[Device]:
        """获取未分组的设备"""
        return Device.objects.filter(groups__isnull=True)
    
    @staticmethod
    @transaction.atomic
    def batch_assign_groups(device_ids: List[str], group_ids: List[int]) -> Dict[str, int]:
        """批量分配设备到分组"""
        devices = Device.objects.filter(device_id__in=device_ids)
        groups = DeviceGroup.objects.filter(id__in=group_ids)
        
        success_count = 0
        for device in devices:
            # 清除现有分组关联
            device.groups.clear()
            # 添加新的分组关联
            device.groups.set(groups)
            success_count += 1
        
        return {
            'success_count': success_count,
            'total_devices': len(device_ids),
            'total_groups': len(group_ids)
        }