#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django 管理命令：将设备按类型分配到对应分组

使用方法：
    python manage.py assign_devices_to_groups
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from devices.models import Device, DeviceGroup


class Command(BaseCommand):
    help = '将设备按类型（camera/door_lock/sensor/gateway）分配到对应分组'

    # 设备类型到分组配置的映射
    DEVICE_TYPE_CONFIG = {
        'camera': {
            'name': '智能摄像头',
            'description': '所有智能摄像头设备',
            'icon': 'video-camera',
            'color': '#1890ff',
        },
        'door_lock': {
            'name': '智能门锁',
            'description': '所有智能门锁设备',
            'icon': 'lock',
            'color': '#52c41a',
        },
        'sensor': {
            'name': '传感器',
            'description': '所有传感器设备',
            'icon': 'dashboard',
            'color': '#faad14',
        },
        'gateway': {
            'name': '网关',
            'description': '所有网关设备',
            'icon': 'cloud-server',
            'color': '#722ed1',
        },
        'switch': {
            'name': '智能开关',
            'description': '所有智能开关设备',
            'icon': 'power',
            'color': '#13c2c2',
        },
        'robot': {
            'name': '扫地机器人',
            'description': '所有扫地机器人设备',
            'icon': 'robot',
            'color': '#eb2f96',
        },
        'lock': {
            'name': '门锁',
            'description': '所有门锁设备',
            'icon': 'lock',
            'color': '#f5222d',
        },
        'curtain': {
            'name': '窗帘电机',
            'description': '所有窗帘电机设备',
            'icon': 'border-outer',
            'color': '#fa8c16',
        },
        'light': {
            'name': '智能灯泡',
            'description': '所有智能灯泡设备',
            'icon': 'light',
            'color': '#fadb14',
        },
        'speaker': {
            'name': '智能音箱',
            'description': '所有智能音箱设备',
            'icon': 'customer-service',
            'color': '#722ed1',
        },
        'ac_companion': {
            'name': '空调伴侣',
            'description': '所有空调伴侣设备',
            'icon': 'air-conditioner',
            'color': '#1890ff',
        },
        'purifier': {
            'name': '空气净化器',
            'description': '所有空气净化器设备',
            'icon': 'filter',
            'color': '#52c41a',
        },
        'alarm': {
            'name': '烟雾报警器',
            'description': '所有烟雾报警器设备',
            'icon': 'alert',
            'color': '#f5222d',
        },
        'other': {
            'name': '其他设备',
            'description': '其他类型设备',
            'icon': 'appstore',
            'color': '#8c8c8c',
        },
    }

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('开始执行设备分组任务...'))

        # 1. 创建或获取分组
        groups = {}
        for device_type, config in self.DEVICE_TYPE_CONFIG.items():
            group, created = DeviceGroup.objects.get_or_create(
                name=config['name'],
                defaults={
                    'description': config['description'],
                    'icon': config['icon'],
                    'color': config['color'],
                }
            )
            groups[device_type] = group

            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ 创建分组：{config["name"]}'))
            else:
                self.stdout.write(self.style.WARNING(f'  - 分组已存在：{config["name"]}'))

        # 2. 将所有设备分配到对应分组
        devices = Device.objects.all()
        assigned_count = 0

        for device in devices:
            device_type = device.device_type or 'other'
            group = groups.get(device_type)

            if group:
                # 检查设备是否已经在分组中
                if not device.groups.filter(id=group.id).exists():
                    device.groups.add(group)
                    assigned_count += 1
                    self.stdout.write(f'  ✓ 设备 {device.name} ({device.device_id}) → {group.name}')
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠ 未知设备类型：{device_type}，设备：{device.name}'))

        self.stdout.write(self.style.SUCCESS(f'\n任务完成！共分配 {assigned_count} 个设备到对应分组。'))
        self.stdout.write(self.style.SUCCESS(f'分组统计：'))
        for device_type, group in groups.items():
            count = group.devices.count()
            self.stdout.write(f'  - {group.name}：{count} 个设备')
