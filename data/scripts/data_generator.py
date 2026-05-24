"""
数据模拟生成模块
功能：生成模拟的智能家居网络流量数据（正常流量 + 攻击流量）

优化说明：
1. 基于真实 IoT-23 数据集的统计分布生成数据
2. 添加时间周期性特征（日夜模式、周期性使用模式）
3. 增加设备行为关联性
4. 支持混合式攻击场景生成
5. 添加噪声和漂移模拟真实环境
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from pathlib import Path
import logging
from typing import Dict, List, Optional, Tuple
from scipy import stats

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SmartHomeDataGenerator:
    """智能家居数据生成器（增强版）"""
    
    # 模拟设备配置（包含设备行为特征）
    DEVICES = {
        'camera_01': {
            'type': 'smart_camera', 
            'ip': '192.168.1.101',
            'behavior': {
                'avg_duration': 10.0,      # 平均连接时长
                'avg_bytes': 50000,        # 视频流平均字节数
                'active_hours': (6, 23),   # 活跃时间段
                'packet_rate': 30,         # 平均包速率
                'protocols': ['tcp'],
                'services': ['https', 'rtsp']
            }
        },
        'camera_02': {
            'type': 'smart_camera', 
            'ip': '192.168.1.102',
            'behavior': {
                'avg_duration': 8.0,
                'avg_bytes': 40000,
                'active_hours': (6, 23),
                'packet_rate': 25,
                'protocols': ['tcp'],
                'services': ['https', 'rtsp']
            }
        },
        'doorlock_01': {
            'type': 'smart_doorlock', 
            'ip': '192.168.1.103',
            'behavior': {
                'avg_duration': 0.5,       # 门锁通信很短
                'avg_bytes': 200,          # 字节数很小
                'active_hours': (0, 24),   # 24小时活跃
                'packet_rate': 3,
                'protocols': ['tcp', 'udp'],
                'services': ['mqtt', 'https']
            }
        },
        'doorlock_02': {
            'type': 'smart_doorlock', 
            'ip': '192.168.1.104',
            'behavior': {
                'avg_duration': 0.5,
                'avg_bytes': 200,
                'active_hours': (0, 24),
                'packet_rate': 3,
                'protocols': ['tcp', 'udp'],
                'services': ['mqtt', 'https']
            }
        },
        'thermostat_01': {
            'type': 'smart_thermostat', 
            'ip': '192.168.1.105',
            'behavior': {
                'avg_duration': 2.0,       # 周期性心跳
                'avg_bytes': 500,
                'active_hours': (0, 24),
                'packet_rate': 5,
                'protocols': ['tcp'],
                'services': ['mqtt', 'https']
            }
        },
        'light_01': {
            'type': 'smart_light', 
            'ip': '192.168.1.106',
            'behavior': {
                'avg_duration': 0.3,
                'avg_bytes': 100,
                'active_hours': (6, 24),   # 白天和晚上
                'packet_rate': 2,
                'protocols': ['udp'],
                'services': ['mqtt']
            }
        },
        'light_02': {
            'type': 'smart_light', 
            'ip': '192.168.1.107',
            'behavior': {
                'avg_duration': 0.3,
                'avg_bytes': 100,
                'active_hours': (6, 24),
                'packet_rate': 2,
                'protocols': ['udp'],
                'services': ['mqtt']
            }
        },
        'speaker_01': {
            'type': 'smart_speaker', 
            'ip': '192.168.1.108',
            'behavior': {
                'avg_duration': 5.0,       # 语音交互
                'avg_bytes': 10000,
                'active_hours': (7, 23),
                'packet_rate': 15,
                'protocols': ['tcp', 'udp'],
                'services': ['https', 'dns']
            }
        },
    }
    
    # 基于 IoT-23 数据集的真实统计分布参数
    REAL_DISTRIBUTIONS = {
        'benign': {
            'duration': {'dist': 'lognorm', 'params': (1.5, 0, 2.0)},     # 对数正态分布
            'orig_bytes': {'dist': 'lognorm', 'params': (2.0, 64, 500)},
            'resp_bytes': {'dist': 'lognorm', 'params': (2.2, 64, 800)},
            'orig_pkts': {'dist': 'poisson', 'params': (5,)},
            'resp_pkts': {'dist': 'poisson', 'params': (6,)},
        },
        'ddos': {
            'duration': {'dist': 'expon', 'params': (0, 0.1)},           # 指数分布（短连接）
            'orig_bytes': {'dist': 'norm', 'params': (80, 20)},
            'resp_bytes': {'dist': 'expon', 'params': (0, 30)},
            'orig_pkts': {'dist': 'poisson', 'params': (2,)},
            'resp_pkts': {'dist': 'poisson', 'params': (1,)},
        },
        'scan': {
            'duration': {'dist': 'expon', 'params': (0, 0.05)},
            'orig_bytes': {'dist': 'norm', 'params': (50, 10)},
            'resp_bytes': {'dist': 'expon', 'params': (0, 20)},
            'orig_pkts': {'dist': 'poisson', 'params': (1,)},
            'resp_pkts': {'dist': 'poisson', 'params': (1,)},
        },
        'mirai': {
            'duration': {'dist': 'lognorm', 'params': (1.0, 0.5, 1.5)},
            'orig_bytes': {'dist': 'norm', 'params': (250, 100)},
            'resp_bytes': {'dist': 'norm', 'params': (150, 50)},
            'orig_pkts': {'dist': 'poisson', 'params': (5,)},
            'resp_pkts': {'dist': 'poisson', 'params': (4,)},
        },
        'unauthorized': {
            'duration': {'dist': 'lognorm', 'params': (2.0, 1.0, 10.0)},
            'orig_bytes': {'dist': 'lognorm', 'params': (2.5, 200, 500)},
            'resp_bytes': {'dist': 'lognorm', 'params': (2.0, 100, 300)},
            'orig_pkts': {'dist': 'poisson', 'params': (10,)},
            'resp_pkts': {'dist': 'poisson', 'params': (8,)},
        }
    }
    
    # 网关配置
    GATEWAY_IP = '192.168.1.1'
    
    # 外部IP池（用于模拟攻击）- 更多的 C2 服务器地址
    EXTERNAL_IPS = [
        '203.0.113.1', '203.0.113.2', '198.51.100.1', '198.51.100.2',
        '192.0.2.1', '192.0.2.2', '45.33.32.156', '104.16.123.96',
        '185.220.101.1', '185.220.101.2', '91.121.43.1', '91.121.43.2',
        '178.62.1.1', '178.62.1.2', '159.89.1.1', '159.89.1.2'
    ]
    
    # 协议类型
    PROTOCOLS = ['tcp', 'udp', 'icmp']
    
    # 服务类型
    SERVICES = ['http', 'https', 'mqtt', 'dns', 'ntp', 'ssh', 'rtsp', '-']
    
    # 连接状态及其含义
    CONN_STATES = {
        'SF': 0.7,    # 正常完成
        'S0': 0.1,    # 连接尝试但无响应
        'REJ': 0.05,  # 被拒绝
        'RSTO': 0.05, # 连接被重置
        'RSTOS0': 0.03,
        'SH': 0.03,
        'SHR': 0.02,
        'OTH': 0.02
    }
    
    def __init__(self, output_path: str = None, seed: int = 42):
        """
        初始化生成器
        
        Args:
            output_path: 输出路径
            seed: 随机种子（确保可复现性）
        """
        self.output_path = Path(output_path) if output_path else Path(__file__).parent.parent / 'raw'
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 设置随机种子
        np.random.seed(seed)
        random.seed(seed)
        
        # 设备状态跟踪（用于模拟行为关联性）
        self._device_states = {device_id: {'last_active': None, 'session_count': 0} 
                              for device_id in self.DEVICES}
    
    def _sample_from_distribution(self, dist_config: Dict, size: int = 1) -> np.ndarray:
        """
        从指定的统计分布中采样
        
        Args:
            dist_config: 分布配置 {'dist': 分布类型, 'params': 参数}
            size: 采样数量
            
        Returns:
            采样值数组
        """
        dist_name = dist_config['dist']
        params = dist_config['params']
        
        if dist_name == 'lognorm':
            # 对数正态分布：shape, loc, scale
            samples = stats.lognorm.rvs(params[0], loc=params[1], scale=params[2], size=size)
        elif dist_name == 'expon':
            # 指数分布：loc, scale
            samples = stats.expon.rvs(loc=params[0], scale=params[1], size=size)
        elif dist_name == 'norm':
            # 正态分布：mean, std
            samples = stats.norm.rvs(loc=params[0], scale=params[1], size=size)
        elif dist_name == 'poisson':
            # 泊松分布：lambda
            samples = stats.poisson.rvs(params[0], size=size)
        else:
            # 默认均匀分布
            samples = np.random.uniform(0, 100, size=size)
        
        # 确保非负
        return np.maximum(samples, 0)
    
    def _get_time_factor(self, hour: int, device_behavior: Dict) -> float:
        """
        根据时间计算设备活跃系数
        
        Args:
            hour: 当前小时 (0-23)
            device_behavior: 设备行为配置
            
        Returns:
            活跃系数 (0.1 - 1.0)
        """
        active_start, active_end = device_behavior['active_hours']
        
        if active_start <= hour < active_end:
            # 活跃时段内，基于时间调整
            if 7 <= hour <= 9 or 18 <= hour <= 21:
                # 高峰时段
                return 1.0
            elif 22 <= hour or hour <= 6:
                # 夜间
                return 0.3
            else:
                return 0.7
        else:
            # 非活跃时段
            return 0.1
        
    def _generate_timestamp(self, base_time: datetime, offset_seconds: float) -> str:
        """生成时间戳"""
        return (base_time + timedelta(seconds=offset_seconds)).strftime('%Y-%m-%d %H:%M:%S')
    
    def _generate_normal_traffic(self, num_samples: int, base_time: datetime) -> list:
        """
        生成正常流量数据（增强版）
        
        改进：
        1. 基于设备特定行为生成
        2. 考虑时间周期性
        3. 使用真实统计分布
        4. 添加关联性（设备间、时间序列）
        
        Args:
            num_samples: 样本数量
            base_time: 基准时间
            
        Returns:
            正常流量数据列表
        """
        records = []
        dist_params = self.REAL_DISTRIBUTIONS['benign']
        
        # 预采样以提高效率
        durations = self._sample_from_distribution(dist_params['duration'], num_samples)
        orig_bytes_base = self._sample_from_distribution(dist_params['orig_bytes'], num_samples)
        resp_bytes_base = self._sample_from_distribution(dist_params['resp_bytes'], num_samples)
        orig_pkts = self._sample_from_distribution(dist_params['orig_pkts'], num_samples)
        resp_pkts = self._sample_from_distribution(dist_params['resp_pkts'], num_samples)
        
        current_time = 0
        for i in range(num_samples):
            # 选择设备（基于时间加权）
            hour = (base_time + timedelta(seconds=current_time)).hour
            
            # 根据时间选择活跃设备
            device_weights = []
            device_ids = list(self.DEVICES.keys())
            for device_id in device_ids:
                behavior = self.DEVICES[device_id]['behavior']
                weight = self._get_time_factor(hour, behavior)
                device_weights.append(weight)
            
            # 归一化权重
            total_weight = sum(device_weights)
            device_weights = [w / total_weight for w in device_weights]
            
            device_id = np.random.choice(device_ids, p=device_weights)
            device = self.DEVICES[device_id]
            behavior = device['behavior']
            
            # 基于设备行为调整参数
            time_factor = self._get_time_factor(hour, behavior)
            
            # 应用设备特定的字节数调整
            device_byte_factor = behavior['avg_bytes'] / 1000
            orig_bytes = int(orig_bytes_base[i] * device_byte_factor * time_factor)
            resp_bytes = int(resp_bytes_base[i] * device_byte_factor * time_factor * 1.2)
            
            # 根据设备类型调整连接时长
            duration = durations[i] * (behavior['avg_duration'] / 5.0)
            
            # 选择协议和服务
            proto = random.choice(behavior['protocols'])
            service = random.choice(behavior['services'])
            
            # 连接状态（正常流量主要是 SF）
            conn_state = np.random.choice(
                list(self.CONN_STATES.keys()),
                p=list(self.CONN_STATES.values())
            )
            
            record = {
                'timestamp': self._generate_timestamp(base_time, current_time),
                'device_id': device_id,
                'device_type': device['type'],
                'src_ip': device['ip'],
                'dst_ip': self.GATEWAY_IP,
                'proto': proto,
                'service': service,
                'conn_state': conn_state,
                'duration': round(duration, 3),
                'orig_bytes': max(64, orig_bytes),
                'resp_bytes': max(64, resp_bytes),
                'orig_pkts': max(1, int(orig_pkts[i])),
                'resp_pkts': max(1, int(resp_pkts[i])),
                'orig_ip_bytes': max(100, int(orig_bytes * 1.15)),
                'resp_ip_bytes': max(100, int(resp_bytes * 1.15)),
                'label': 'benign'
            }
            records.append(record)
            
            # 更新时间（添加随机间隔，模拟真实流量）
            interval = random.uniform(0.5, 10) / time_factor  # 活跃时段间隔更短
            current_time += interval
            
        return records
    
    def _generate_ddos_attack(self, num_samples: int, base_time: datetime) -> list:
        """
        生成DDoS攻击流量（增强版）
        
        支持多种 DDoS 类型：
        1. SYN Flood - 大量半开连接
        2. UDP Flood - 大量 UDP 包
        3. HTTP Flood - 应用层攻击
        4. Amplification - 放大攻击
        
        特征：高频率请求、短连接、大量小包
        """
        records = []
        target_device = random.choice(list(self.DEVICES.keys()))
        target_ip = self.DEVICES[target_device]['ip']
        dist_params = self.REAL_DISTRIBUTIONS['ddos']
        
        # 预采样
        durations = self._sample_from_distribution(dist_params['duration'], num_samples)
        orig_bytes = self._sample_from_distribution(dist_params['orig_bytes'], num_samples)
        resp_bytes = self._sample_from_distribution(dist_params['resp_bytes'], num_samples)
        orig_pkts = self._sample_from_distribution(dist_params['orig_pkts'], num_samples)
        resp_pkts = self._sample_from_distribution(dist_params['resp_pkts'], num_samples)
        
        # DDoS 子类型分布
        ddos_types = ['syn_flood', 'udp_flood', 'http_flood', 'amplification']
        ddos_type = random.choice(ddos_types)
        
        # 模拟多个攻击源
        num_attackers = random.randint(5, 15)
        attacker_ips = random.sample(self.EXTERNAL_IPS, min(num_attackers, len(self.EXTERNAL_IPS)))
        
        current_time = 0
        for i in range(num_samples):
            attacker_ip = random.choice(attacker_ips)
            
            if ddos_type == 'syn_flood':
                proto = 'tcp'
                service = '-'
                conn_state = random.choice(['S0', 'REJ', 'RSTOS0'])
                byte_mult = 0.5
            elif ddos_type == 'udp_flood':
                proto = 'udp'
                service = random.choice(['dns', 'ntp', '-'])
                conn_state = 'SF'
                byte_mult = 0.8
            elif ddos_type == 'http_flood':
                proto = 'tcp'
                service = 'http'
                conn_state = random.choice(['SF', 'S0'])
                byte_mult = 2.0
            else:  # amplification
                proto = 'udp'
                service = random.choice(['dns', 'ntp'])
                conn_state = 'SF'
                byte_mult = 0.3  # 请求小，响应大
            
            record = {
                'timestamp': self._generate_timestamp(base_time, current_time),
                'device_id': target_device,
                'device_type': self.DEVICES[target_device]['type'],
                'src_ip': attacker_ip,
                'dst_ip': target_ip,
                'proto': proto,
                'service': service,
                'conn_state': conn_state,
                'duration': round(max(0.001, durations[i]), 3),
                'orig_bytes': max(40, int(orig_bytes[i] * byte_mult)),
                'resp_bytes': max(0, int(resp_bytes[i])),
                'orig_pkts': max(1, int(orig_pkts[i])),
                'resp_pkts': max(0, int(resp_pkts[i])),
                'orig_ip_bytes': max(60, int(orig_bytes[i] * byte_mult * 1.2)),
                'resp_ip_bytes': max(0, int(resp_bytes[i] * 1.2)),
                'label': 'ddos'
            }
            records.append(record)
            
            # DDoS 攻击间隔很短
            current_time += random.uniform(0.001, 0.1)
            
        return records
    
    def _generate_port_scan(self, num_samples: int, base_time: datetime) -> list:
        """
        生成端口扫描流量（增强版）
        
        支持多种扫描类型：
        1. TCP SYN Scan - 半开扫描
        2. TCP Connect Scan - 全连接扫描
        3. UDP Scan - UDP 端口扫描
        4. Stealth Scan - 慢速隐蔽扫描
        
        特征：探测多个端口、短连接、无响应或被拒绝
        """
        records = []
        attacker_ip = random.choice(self.EXTERNAL_IPS)
        dist_params = self.REAL_DISTRIBUTIONS['scan']
        
        # 预采样
        durations = self._sample_from_distribution(dist_params['duration'], num_samples)
        orig_bytes = self._sample_from_distribution(dist_params['orig_bytes'], num_samples)
        resp_bytes = self._sample_from_distribution(dist_params['resp_bytes'], num_samples)
        orig_pkts = self._sample_from_distribution(dist_params['orig_pkts'], num_samples)
        resp_pkts = self._sample_from_distribution(dist_params['resp_pkts'], num_samples)
        
        # 扫描类型
        scan_types = ['syn_scan', 'connect_scan', 'udp_scan', 'stealth_scan']
        scan_type = random.choice(scan_types)
        
        current_time = 0
        for i in range(num_samples):
            target_device = random.choice(list(self.DEVICES.keys()))
            
            if scan_type == 'syn_scan':
                proto = 'tcp'
                conn_state = random.choice(['S0', 'REJ', 'RSTO'])
                interval = random.uniform(0.01, 0.1)
            elif scan_type == 'connect_scan':
                proto = 'tcp'
                conn_state = random.choice(['SF', 'REJ', 'RSTO'])
                interval = random.uniform(0.05, 0.2)
            elif scan_type == 'udp_scan':
                proto = 'udp'
                conn_state = random.choice(['SF', 'S0'])
                interval = random.uniform(0.02, 0.15)
            else:  # stealth_scan - 慢速扫描
                proto = 'tcp'
                conn_state = random.choice(['S0', 'REJ'])
                interval = random.uniform(5, 30)  # 慢速以避免检测
            
            record = {
                'timestamp': self._generate_timestamp(base_time, current_time),
                'device_id': target_device,
                'device_type': self.DEVICES[target_device]['type'],
                'src_ip': attacker_ip,
                'dst_ip': self.DEVICES[target_device]['ip'],
                'proto': proto,
                'service': '-',
                'conn_state': conn_state,
                'duration': round(max(0.001, durations[i]), 3),
                'orig_bytes': max(40, int(orig_bytes[i])),
                'resp_bytes': max(0, int(resp_bytes[i])),
                'orig_pkts': max(1, int(orig_pkts[i])),
                'resp_pkts': max(0, int(resp_pkts[i])),
                'orig_ip_bytes': max(60, int(orig_bytes[i] * 1.2)),
                'resp_ip_bytes': max(0, int(resp_bytes[i] * 1.2)),
                'label': 'scan'
            }
            records.append(record)
            current_time += interval
            
        return records
    
    def _generate_botnet_traffic(self, num_samples: int, base_time: datetime) -> list:
        """
        生成僵尸网络流量（增强版）
        
        模拟多种僵尸网络行为：
        1. C2 心跳通信 - 周期性连接
        2. 指令下发 - 接收攻击指令
        3. 数据外泄 - 发送窃取的数据
        4. 横向传播 - 扫描内网其他设备
        
        特征：设备向外部C2服务器通信、周期性心跳、异常端口
        """
        records = []
        infected_device = random.choice(list(self.DEVICES.keys()))
        c2_servers = random.sample(self.EXTERNAL_IPS, min(3, len(self.EXTERNAL_IPS)))
        dist_params = self.REAL_DISTRIBUTIONS['mirai']
        
        # 预采样
        durations = self._sample_from_distribution(dist_params['duration'], num_samples)
        orig_bytes = self._sample_from_distribution(dist_params['orig_bytes'], num_samples)
        resp_bytes = self._sample_from_distribution(dist_params['resp_bytes'], num_samples)
        orig_pkts = self._sample_from_distribution(dist_params['orig_pkts'], num_samples)
        resp_pkts = self._sample_from_distribution(dist_params['resp_pkts'], num_samples)
        
        # 僵尸网络活动类型
        activities = ['heartbeat', 'command', 'exfiltration', 'propagation']
        activity_weights = [0.5, 0.2, 0.15, 0.15]
        
        current_time = 0
        for i in range(num_samples):
            activity = np.random.choice(activities, p=activity_weights)
            c2_server = random.choice(c2_servers)
            
            if activity == 'heartbeat':
                # 心跳：周期性、小数据量
                interval = random.uniform(30, 120)
                byte_mult = 0.3
                service = '-'
                src_ip = self.DEVICES[infected_device]['ip']
                dst_ip = c2_server
            elif activity == 'command':
                # 指令：C2 服务器发送指令
                interval = random.uniform(60, 300)
                byte_mult = 0.5
                service = '-'
                src_ip = c2_server
                dst_ip = self.DEVICES[infected_device]['ip']
            elif activity == 'exfiltration':
                # 数据外泄：大数据量
                interval = random.uniform(300, 600)
                byte_mult = 3.0
                service = random.choice(['http', 'https', '-'])
                src_ip = self.DEVICES[infected_device]['ip']
                dst_ip = c2_server
            else:  # propagation
                # 横向传播：扫描内网
                interval = random.uniform(5, 30)
                byte_mult = 0.2
                service = '-'
                src_ip = self.DEVICES[infected_device]['ip']
                other_devices = [d for d in self.DEVICES if d != infected_device]
                target = random.choice(other_devices)
                dst_ip = self.DEVICES[target]['ip']
            
            record = {
                'timestamp': self._generate_timestamp(base_time, current_time),
                'device_id': infected_device,
                'device_type': self.DEVICES[infected_device]['type'],
                'src_ip': src_ip,
                'dst_ip': dst_ip,
                'proto': 'tcp',
                'service': service,
                'conn_state': 'SF',
                'duration': round(max(0.1, durations[i]), 3),
                'orig_bytes': max(50, int(orig_bytes[i] * byte_mult)),
                'resp_bytes': max(30, int(resp_bytes[i] * byte_mult * 0.6)),
                'orig_pkts': max(2, int(orig_pkts[i])),
                'resp_pkts': max(1, int(resp_pkts[i])),
                'orig_ip_bytes': max(80, int(orig_bytes[i] * byte_mult * 1.2)),
                'resp_ip_bytes': max(50, int(resp_bytes[i] * byte_mult * 0.7)),
                'label': 'mirai'
            }
            records.append(record)
            current_time += interval
            
        return records
    
    def _generate_unauthorized_access(self, num_samples: int, base_time: datetime) -> list:
        """
        生成越权访问流量（增强版）
        
        模拟多种攻击场景：
        1. 暴力破解 - 多次登录尝试
        2. 凭证填充 - 使用泄露的凭证
        3. 会话劫持 - 尝试复用会话
        4. 权限提升 - 访问高权限接口
        
        特征：尝试访问敏感设备（门锁、摄像头）、异常时间、多次失败尝试
        """
        records = []
        attacker_ip = random.choice(self.EXTERNAL_IPS)
        sensitive_devices = [d for d, info in self.DEVICES.items() 
                           if info['type'] in ['smart_doorlock', 'smart_camera']]
        dist_params = self.REAL_DISTRIBUTIONS['unauthorized']
        
        # 预采样
        durations = self._sample_from_distribution(dist_params['duration'], num_samples)
        orig_bytes = self._sample_from_distribution(dist_params['orig_bytes'], num_samples)
        resp_bytes = self._sample_from_distribution(dist_params['resp_bytes'], num_samples)
        orig_pkts = self._sample_from_distribution(dist_params['orig_pkts'], num_samples)
        resp_pkts = self._sample_from_distribution(dist_params['resp_pkts'], num_samples)
        
        # 攻击场景
        attack_scenarios = ['brute_force', 'credential_stuffing', 'session_hijack', 'privilege_escalation']
        scenario = random.choice(attack_scenarios)
        
        current_time = 0
        consecutive_failures = 0
        max_failures = random.randint(3, 10)
        
        for i in range(num_samples):
            target_device = random.choice(sensitive_devices)
            
            if scenario == 'brute_force':
                # 暴力破解：快速多次尝试，大多失败
                interval = random.uniform(0.5, 3)
                service = 'ssh' if random.random() < 0.3 else 'https'
                # 前几次失败，最后可能成功
                if consecutive_failures < max_failures:
                    conn_state = random.choice(['REJ', 'RSTO', 'SF'])
                    consecutive_failures += 1
                else:
                    conn_state = 'SF'
                    consecutive_failures = 0
                byte_mult = 1.0
                
            elif scenario == 'credential_stuffing':
                # 凭证填充：较慢尝试，避免触发锁定
                interval = random.uniform(5, 30)
                service = 'https'
                conn_state = random.choice(['SF', 'REJ'])
                byte_mult = 1.5
                
            elif scenario == 'session_hijack':
                # 会话劫持：正常连接但行为异常
                interval = random.uniform(1, 10)
                service = 'https'
                conn_state = 'SF'
                byte_mult = 2.0
                
            else:  # privilege_escalation
                # 权限提升：访问敏感接口
                interval = random.uniform(2, 15)
                service = random.choice(['http', 'https'])
                conn_state = random.choice(['SF', 'REJ'])
                byte_mult = 2.5
            
            record = {
                'timestamp': self._generate_timestamp(base_time, current_time),
                'device_id': target_device,
                'device_type': self.DEVICES[target_device]['type'],
                'src_ip': attacker_ip,
                'dst_ip': self.DEVICES[target_device]['ip'],
                'proto': 'tcp',
                'service': service,
                'conn_state': conn_state,
                'duration': round(max(0.5, durations[i]), 3),
                'orig_bytes': max(100, int(orig_bytes[i] * byte_mult)),
                'resp_bytes': max(50, int(resp_bytes[i] * byte_mult * 0.5)),
                'orig_pkts': max(3, int(orig_pkts[i])),
                'resp_pkts': max(2, int(resp_pkts[i])),
                'orig_ip_bytes': max(150, int(orig_bytes[i] * byte_mult * 1.2)),
                'resp_ip_bytes': max(80, int(resp_bytes[i] * byte_mult * 0.6)),
                'label': 'unauthorized'
            }
            records.append(record)
            current_time += interval
            
        return records
    
    def generate_dataset(self, 
                        total_samples: int = 10000,
                        normal_ratio: float = 0.8,
                        attack_distribution: dict = None,
                        add_noise: bool = True,
                        noise_ratio: float = 0.02) -> pd.DataFrame:
        """
        生成完整数据集（增强版）
        
        Args:
            total_samples: 总样本数
            normal_ratio: 正常样本比例
            attack_distribution: 攻击类型分布
            add_noise: 是否添加噪声数据（模拟真实环境中的噪声）
            noise_ratio: 噪声比例
            
        Returns:
            生成的DataFrame
        """
        logger.info(f"开始生成数据集（增强版），总样本数: {total_samples}")
        
        base_time = datetime.now() - timedelta(days=7)
        
        normal_samples = int(total_samples * normal_ratio)
        attack_samples = total_samples - normal_samples
        
        if attack_distribution is None:
            attack_distribution = {
                'ddos': 0.35,
                'scan': 0.25,
                'botnet': 0.20,
                'unauthorized': 0.20
            }
        
        all_records = []
        
        # 生成正常流量
        logger.info(f"生成正常流量: {normal_samples} 条")
        all_records.extend(self._generate_normal_traffic(normal_samples, base_time))
        
        # 生成各类攻击流量
        for attack_type, ratio in attack_distribution.items():
            num = int(attack_samples * ratio)
            logger.info(f"生成 {attack_type} 攻击流量: {num} 条")
            
            if attack_type == 'ddos':
                all_records.extend(self._generate_ddos_attack(num, base_time))
            elif attack_type == 'scan':
                all_records.extend(self._generate_port_scan(num, base_time))
            elif attack_type == 'botnet':
                all_records.extend(self._generate_botnet_traffic(num, base_time))
            elif attack_type == 'unauthorized':
                all_records.extend(self._generate_unauthorized_access(num, base_time))
        
        # 转换为DataFrame
        df = pd.DataFrame(all_records)
        
        # 添加噪声（模拟真实数据中的噪声和异常）
        if add_noise:
            df = self._add_realistic_noise(df, noise_ratio)
        
        # 打乱顺序并按时间排序（模拟真实时间序列）
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        # 数据质量报告
        self._generate_quality_report(df)
        
        logger.info(f"数据集生成完成，共 {len(df)} 条记录")
        
        return df
    
    def _add_realistic_noise(self, df: pd.DataFrame, noise_ratio: float) -> pd.DataFrame:
        """
        添加真实噪声
        
        模拟：
        1. 缺失值
        2. 异常值
        3. 数据漂移
        """
        n_noise = int(len(df) * noise_ratio)
        logger.info(f"添加 {n_noise} 条噪声数据")
        
        # 随机添加一些缺失值
        numeric_cols = ['duration', 'orig_bytes', 'resp_bytes', 'orig_pkts', 'resp_pkts']
        noise_indices = np.random.choice(df.index, size=n_noise, replace=False)
        
        for idx in noise_indices:
            col = random.choice(numeric_cols)
            if random.random() < 0.3:
                # 设为 NaN（之后预处理会处理）
                df.loc[idx, col] = np.nan
            else:
                # 添加随机扰动
                original = df.loc[idx, col]
                noise_factor = random.uniform(0.8, 1.2)
                df.loc[idx, col] = original * noise_factor
        
        return df
    
    def _generate_quality_report(self, df: pd.DataFrame):
        """生成数据质量报告"""
        logger.info("=" * 50)
        logger.info("数据质量报告")
        logger.info("=" * 50)
        
        # 标签分布
        logger.info(f"标签分布:\n{df['label'].value_counts()}")
        
        # 设备分布
        logger.info(f"\n设备分布:\n{df['device_type'].value_counts()}")
        
        # 协议分布
        logger.info(f"\n协议分布:\n{df['proto'].value_counts()}")
        
        # 数值特征统计
        numeric_cols = ['duration', 'orig_bytes', 'resp_bytes', 'orig_pkts', 'resp_pkts']
        logger.info(f"\n数值特征统计:\n{df[numeric_cols].describe()}")
        
        # 缺失值统计
        missing = df.isnull().sum()
        if missing.sum() > 0:
            logger.info(f"\n缺失值统计:\n{missing[missing > 0]}")
    
    def save_dataset(self, df: pd.DataFrame, filename: str = 'simulated_iot_data.csv'):
        """保存数据集"""
        output_file = self.output_path / filename
        df.to_csv(output_file, index=False)
        logger.info(f"数据集已保存至: {output_file}")
        return output_file
    
    def generate_and_save(self, 
                         total_samples: int = 10000,
                         filename: str = 'simulated_iot_data.csv') -> str:
        """生成并保存数据集"""
        df = self.generate_dataset(total_samples)
        return self.save_dataset(df, filename)


if __name__ == '__main__':
    # 生成模拟数据集（增强版）
    generator = SmartHomeDataGenerator(seed=42)
    
    print("=" * 60)
    print("智能家居数据生成器（增强版）")
    print("=" * 60)
    print("\n主要增强：")
    print("  1. ✓ 基于真实 IoT-23 数据集的统计分布")
    print("  2. ✓ 设备特定行为模型")
    print("  3. ✓ 时间周期性特征（日夜模式）")
    print("  4. ✓ 多种攻击子类型支持")
    print("  5. ✓ 可配置的噪声注入")
    print()
    
    output_path = generator.generate_and_save(total_samples=10000)
    print(f"\n数据集已生成: {output_path}")
