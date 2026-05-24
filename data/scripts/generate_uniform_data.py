#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成过去90天的均匀检测数据
以今天为基准，过去30天和90天都均匀分布
"""

import os
import sys
import django
import random
from datetime import datetime, timedelta
from django.utils import timezone

# 设置Django环境
sys.path.append('/Users/lukachihanbao/GraduationProject/ShieldHome/backend')
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from detection.models import DetectionRecord
from devices.models import Device


def generate_uniform_data(days=90, records_per_day=300):
    """
    生成过去N天的均匀检测数据

    Args:
        days: 生成过去多少天的数据
        records_per_day: 每天生成的记录数
    """
    print(f"开始生成过去{days}天的均匀数据，每天{records_per_day}条记录...")

    # 获取所有设备ID
    devices = Device.objects.all()
    if not devices.exists():
        print("错误：没有找到设备，请先创建设备")
        return

    device_list = list(devices)
    print(f"找到 {len(device_list)} 个设备")

    # 攻击类型配置
    attack_types = ['normal', 'ddos', 'port_scan', 'unauthorized', 'malformed', 'unknown']
    # 正常流量占70%，异常流量占30%
    attack_weights = [0.70, 0.05, 0.08, 0.04, 0.04, 0.04]

    # 协议
    protocols = ['TCP', 'UDP', 'ICMP']

    # 生成数据
    records = []
    now = timezone.now()
    start_date = now - timedelta(days=days)

    print(f"时间范围: {start_date.date()} 到 {now.date()}")

    for day_offset in range(days):
        # 计算当天的基准时间
        base_date = start_date + timedelta(days=day_offset)
        date_str = base_date.strftime('%Y-%m-%d')

        # 生成当天的记录
        daily_records = []

        for record_idx in range(records_per_day):
            # 随机选择设备
            device = random.choice(device_list)

            # 随机选择攻击类型
            attack_type = random.choices(attack_types, weights=attack_weights)[0]
            is_anomaly = attack_type != 'normal'

            # 随机时间（当天）
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            timestamp = base_date.replace(hour=hour, minute=minute, second=second, microsecond=0)

            # 生成网络流量特征
            record = DetectionRecord(
                device_id=device.device_id,
                timestamp=timestamp,
                src_ip=f'192.168.1.{random.randint(100, 200)}',
                dst_ip=f'192.168.1.{random.randint(1, 50)}',
                src_port=random.randint(1024, 65535),
                dst_port=random.choice([80, 443, 22, 1883, 53, 8080]),
                protocol=random.choice(protocols),
                duration=round(random.uniform(0.001, 30), 3),
                orig_bytes=random.randint(64, 100000),
                resp_bytes=random.randint(64, 50000),
                orig_pkts=random.randint(1, 100),
                resp_pkts=random.randint(1, 50),
                is_anomaly=is_anomaly,
                attack_type=attack_type,
                confidence=round(random.uniform(0.7, 0.99), 4) if is_anomaly else round(random.uniform(0.85, 0.99), 4),
                anomaly_score=round(random.uniform(0.5, 0.95), 4) if is_anomaly else round(random.uniform(0.1, 0.3), 4),
                model_version='v1.0',
                inference_time=round(random.uniform(15, 80), 2)
            )
            daily_records.append(record)

        records.extend(daily_records)

        # 每10天批量插入一次，避免内存占用过大
        if (day_offset + 1) % 10 == 0 or day_offset == days - 1:
            DetectionRecord.objects.bulk_create(records, batch_size=1000)
            print(f"  已生成 {date_str} 及之前的数据，累计 {len(records)} 条记录")
            records = []

    print(f"\n数据生成完成！")
    print(f"总计生成: {days * records_per_day} 条记录")

    # 统计生成的数据
    print("\n=== 数据统计 ===")
    total_count = DetectionRecord.objects.filter(
        timestamp__gte=start_date
    ).count()
    anomaly_count = DetectionRecord.objects.filter(
        timestamp__gte=start_date,
        is_anomaly=True
    ).count()
    normal_count = total_count - anomaly_count

    print(f"过去{days}天统计:")
    print(f"  总记录数: {total_count}")
    print(f"  正常记录: {normal_count}")
    print(f"  异常记录: {anomaly_count}")
    print(f"  异常率: {anomaly_count/total_count*100:.1f}%")

    # 按攻击类型统计
    from django.db.models import Count
    attack_dist = DetectionRecord.objects.filter(
        timestamp__gte=start_date,
        is_anomaly=True
    ).values('attack_type').annotate(count=Count('id')).order_by('-count')

    print(f"\n攻击类型分布:")
    for item in attack_dist:
        print(f"  {item['attack_type']}: {item['count']} 条")


if __name__ == '__main__':
    # 生成过去90天的数据，每天300条
    generate_uniform_data(days=90, records_per_day=300)
