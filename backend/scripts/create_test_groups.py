#!/usr/bin/env python
"""
创建测试设备分组数据
"""

import os
import sys
import django

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from devices.models import Device, DeviceGroup
from devices.services.security_service import DeviceSecurityService


def create_test_groups():
    """创建测试设备分组"""
    
    # 创建顶级分组
    living_room = DeviceGroup.objects.create(
        name='客厅设备',
        description='客厅区域的智能设备',
        icon='collection',
        color='#409EFF'
    )
    
    bedroom = DeviceGroup.objects.create(
        name='卧室设备',
        description='卧室区域的智能设备',
        icon='folder',
        color='#67C23A'
    )
    
    security = DeviceGroup.objects.create(
        name='安防设备',
        description='安全防护相关设备',
        icon='collection',
        color='#F56C6C'
    )
    
    # 创建子分组
    cameras = DeviceGroup.objects.create(
        name='摄像头',
        description='监控摄像头设备',
        icon='folder',
        color='#E6A23C',
        parent=security
    )
    
    sensors = DeviceGroup.objects.create(
        name='传感器',
        description='各类传感器设备',
        icon='folder',
        color='#909399',
        parent=security
    )
    
    print("✅ 设备分组创建完成")
    
    # 获取现有设备并分配到分组
    devices = Device.objects.all()
    
    for i, device in enumerate(devices):
        if device.device_type == 'camera':
            device.groups.add(cameras)
            device.groups.add(living_room if i % 2 == 0 else bedroom)
        elif device.device_type == 'sensor':
            device.groups.add(sensors)
        elif device.device_type == 'door_lock':
            device.groups.add(security)
        else:
            device.groups.add(living_room if i % 3 == 0 else bedroom)
    
    print("✅ 设备分组分配完成")
    
    # 更新所有设备的安全评分
    print("🔄 更新设备安全评分...")
    result = DeviceSecurityService.batch_update_security_scores()
    print(f"✅ 安全评分更新完成，共更新 {result['updated_count']} 个设备")
    
    # 显示统计信息
    print("\n📊 分组统计:")
    for group in DeviceGroup.objects.all():
        print(f"  - {group.name}: {group.device_count} 个设备")


if __name__ == '__main__':
    create_test_groups()