"""
IoT-23 真实数据集加载与预处理脚本
数据来源: Kaggle - Network Traffic Dataset from IoT-23 (conn4_log_labeled.csv)
约 15.6 万条真实智能家居网络流量记录，包含正常流量和多种攻击

使用方法:
  # 首先安装 kaggle CLI 并下载数据:
  # pip install kaggle
  # kaggle datasets download ogunmusireseyi/network-traffic-dataset-from-iot23
  # unzip network-traffic-dataset-from-iot23.zip -d data/raw/iot23/

  # 然后运行此脚本:
  python data/scripts/load_iot23_data.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
import logging

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data.scripts.data_preprocessor import DataPreprocessor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 配置 ---
IOT23_CSV = project_root / 'data' / 'raw' / 'iot23' / 'conn4_log_labeled.csv'
OUTPUT_DIR = project_root / 'data' / 'processed'
OUTPUT_FILE = 'iot23_processed.npz'

# IoT-23 Zeek 列名 → 模型需要的列名映射
COLUMN_MAPPING = {
    'duration': 'duration',
    'orig_bytes': 'orig_bytes',
    'resp_bytes': 'resp_bytes',
    'orig_pkts': 'orig_pkts',
    'resp_pkts': 'resp_pkts',
    'orig_ip_bytes': 'orig_ip_bytes',
    'resp_ip_bytes': 'resp_ip_bytes',
    'proto': 'proto',
    'service': 'service',
    'conn_state': 'conn_state',
}

# IoT-23 标签映射 (conn4_log_labeled.csv 用 'malicious' 列标记)
# 也兼容原始 IoT-23 的 'label' 和 'detailed-label' 列
LABEL_MAPPING = {
    # benign
    'benign': 0,
    'normal': 0,
    # DDoS / DoS
    'ddos': 1,
    'dos': 1,
    # Port Scan
    'scan': 2,
    'portscan': 2,
    'port scan': 2,
    # Botnet (Mirai, etc.)
    'mirai': 3,
    'botnet': 3,
    'c&c': 3,
    'okiru': 3,
    'torii': 3,
    'hakai': 3,
    'hajime': 3,
    # Unauthorized
    'unauthorized': 4,
    'bruteforce': 4,
    'brute force': 4,
    'exploit': 4,
}


def check_dataset():
    """检查 IoT-23 数据是否已下载"""
    if not IOT23_CSV.exists():
        logger.error(f"❌ IoT-23 数据文件未找到: {IOT23_CSV}")
        logger.info("\n请按以下步骤下载数据：\n")
        logger.info("  # 方法1: 用 Kaggle CLI 下载 (推荐)")
        logger.info("  pip install kaggle")
        logger.info("  kaggle datasets download ogunmusireseyi/network-traffic-dataset-from-iot23")
        logger.info("  unzip network-traffic-dataset-from-iot23.zip -d data/raw/iot23/\n")
        logger.info("  # 方法2: 手动下载")
        logger.info("  https://www.kaggle.com/datasets/ogunmusireseyi/network-traffic-dataset-from-iot23")
        logger.info("  下载后解压到 data/raw/iot23/ 目录\n")
        return False
    return True


def load_and_prepare():
    """加载 IoT-23 数据并转换为模型可用的格式

    conn4_log_labeled.csv 是 Zeek conn.log 格式。CSV 的列头是 #types 行（数据类型），
    实际字段按 Zeek 标准顺序排列：

    位置 | Zeek字段        | 用途
    -----|-----------------|------
     0   | ts              | 时间戳（忽略）
     1   | uid             | 连接ID（忽略）
     2   | id.orig_h       | 源IP
     3   | id.orig_p       | 源端口
     4   | id.resp_h       | 目的IP
     5   | id.resp_p       | 目的端口
     6   | proto           | 协议 ✓
     7   | service         | 服务 ✓
     8   | duration        | 持续时间 ✓
     9   | orig_bytes      | 源字节数 ✓
    10   | resp_bytes      | 响应字节数 ✓
    11   | conn_state      | 连接状态 ✓
    12-15| 中间字段         | 忽略
    16   | orig_pkts       | 源包数 ✓
    17   | orig_ip_bytes   | 源IP字节数 ✓
    18   | resp_pkts       | 响应包数 ✓
    19   | resp_ip_bytes   | 响应IP字节数 ✓
    20   | tunnel_parents  | 隧道标记
    21   | (empty)         | 空
    22   | label           | 攻击标签 ✓
    23   | detailed-label  | 详细标签
    """
    logger.info(f"📂 加载 IoT-23 数据: {IOT23_CSV}")
    df = pd.read_csv(IOT23_CSV, low_memory=False)
    logger.info(f"  原始记录数: {len(df):,}")

    # 按位置索引提取需要的列（Zeek conn.log 标准顺序）
    cols = df.columns
    col_idx = {
        'proto': 6,
        'service': 7,
        'duration': 8,
        'orig_bytes': 9,
        'resp_bytes': 10,
        'conn_state': 11,
        'orig_pkts': 16,
        'orig_ip_bytes': 17,
        'resp_pkts': 18,
        'resp_ip_bytes': 19,
        'label_raw': 22,
        'detailed_label': 23,
    }

    # 构建新 DataFrame
    result = pd.DataFrame()
    for name, idx in col_idx.items():
        if idx < len(cols):
            result[name] = df.iloc[:, idx]
        else:
            logger.warning(f"  列索引 {idx} ({name}) 超出范围")

    # --- 数值列转换 ---
    numeric_cols = ['duration', 'orig_bytes', 'resp_bytes', 'orig_pkts',
                    'resp_pkts', 'orig_ip_bytes', 'resp_ip_bytes']
    for col in numeric_cols:
        result[col] = pd.to_numeric(result[col], errors='coerce').fillna(0)

    # --- 分类列 ---
    for col in ['proto', 'service', 'conn_state']:
        result[col] = result[col].fillna('-').astype(str)
        # Zeek 用 '-' 表示未设置的值
        result[col] = result[col].replace('-', 'unknown')

    # --- 标签处理 ---
    logger.info(f"  原始标签值: {result['label_raw'].value_counts().to_dict()}")
    logger.info(f"  详细标签样例: {result['detailed_label'].value_counts().head(10).to_dict()}")

    def map_label(row):
        label = str(row['label_raw']).strip()
        detail = str(row['detailed_label']).strip().lower()

        # 先用详细标签匹配
        for keyword, code in LABEL_MAPPING.items():
            if keyword in detail:
                return code

        # 再用主标签匹配
        label_lower = label.lower()
        if 'benign' in label_lower:
            return 0
        for keyword, code in LABEL_MAPPING.items():
            if keyword in label_lower:
                return code

        # 兜底
        if 'malicious' in label_lower or 'attack' in label_lower:
            return 1
        return 0

    result['label'] = result.apply(map_label, axis=1)
    result.drop(columns=['label_raw', 'detailed_label'], inplace=True)

    label_counts = result['label'].value_counts().sort_index()
    label_names = {0: 'Benign', 1: 'DDoS/DoS', 2: 'PortScan', 3: 'Botnet', 4: 'Unauthorized'}
    logger.info(f"  标签分布:")
    for lbl, cnt in label_counts.items():
        pct = cnt / len(result) * 100
        logger.info(f"    {label_names.get(lbl, lbl)}: {cnt:,} ({pct:.1f}%)")

    logger.info(f"  最终记录数: {len(result):,}")
    logger.info(f"  最终列: {list(result.columns)}")

    return result


def preprocess_and_train(df):
    """使用现有的预处理流水线处理数据，然后训练模型"""
    logger.info("\n" + "=" * 60)
    logger.info("🔧 开始预处理 IoT-23 数据")
    logger.info("=" * 60)

    preprocessor = DataPreprocessor(use_robust_scaler=True)
    preprocessor.df = df

    # 注意: IoT-23 数据一般比较干净，跳过部分清洗步骤
    # 但保留分类编码和特征工程
    preprocessor.df = preprocessor.df.drop_duplicates()
    logger.info(f"  去重后: {len(preprocessor.df):,} 条")

    # 处理缺失值
    for col in preprocessor.df.select_dtypes(include=[np.number]).columns:
        if col in preprocessor.CORE_FEATURES:
            preprocessor.df[col].fillna(0, inplace=True)

    # 编码分类特征
    preprocessor.encode_categorical()

    # 特征工程 (计算 ratios)
    preprocessor.extract_features()

    # 标签标准化
    preprocessor.normalize_labels()

    # 准备数据集 (先分割再标准化，防止数据泄漏)
    result = preprocessor.prepare_dataset(test_size=0.2, validation_size=0.1)

    # 保存为训练脚本识别的格式
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 保存 npz (与 run_training.py 兼容的格式)
    npz_path = OUTPUT_DIR / OUTPUT_FILE
    np.savez(
        npz_path,
        X_train=result['X_train'],
        X_test=result['X_test'],
        y_train=result['y_train'],
        y_test=result['y_test'],
    )
    logger.info(f"\n✓ 数据已保存: {npz_path}")

    # 保存特征列名
    feature_path = OUTPUT_DIR / 'feature_columns.txt'
    with open(feature_path, 'w') as f:
        for col in result['feature_columns']:
            f.write(col + '\n')
    logger.info(f"✓ 特征列名已保存: {feature_path}")

    # 打印数据摘要
    logger.info(f"\n📊 数据摘要:")
    logger.info(f"  训练集: {result['X_train'].shape[0]:,} 条, {result['X_train'].shape[1]} 个特征")
    logger.info(f"  测试集: {result['X_test'].shape[0]:,} 条")
    if 'X_val' in result:
        logger.info(f"  验证集: {result['X_val'].shape[0]:,} 条")

    train_unique, train_counts = np.unique(result['y_train'], return_counts=True)
    test_unique, test_counts = np.unique(result['y_test'], return_counts=True)
    label_names = {0: 'Benign', 1: 'DDoS/DoS', 2: 'PortScan', 3: 'Botnet', 4: 'Unauthorized'}

    logger.info(f"\n  训练集分布:")
    for lbl, cnt in zip(train_unique, train_counts):
        logger.info(f"    {label_names.get(lbl, lbl)}: {cnt:,} ({cnt/len(result['y_train'])*100:.1f}%)")

    logger.info(f"\n  测试集分布:")
    for lbl, cnt in zip(test_unique, test_counts):
        logger.info(f"    {label_names.get(lbl, lbl)}: {cnt:,} ({cnt/len(result['y_test'])*100:.1f}%)")

    return npz_path


def main():
    if not check_dataset():
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("🏠 IoT-23 真实数据集 → ShieldHome 模型训练")
    logger.info("=" * 60)

    # 1. 加载 IoT-23 数据
    df = load_and_prepare()

    # 2. 预处理
    npz_path = preprocess_and_train(df)

    # 3. 提示训练
    logger.info("\n" + "=" * 60)
    logger.info("✅ 数据预处理完成！现在可以训练模型：")
    logger.info("=" * 60)
    logger.info(f"\n  python algorithm/run_training.py \\")
    logger.info(f"    --if-n-estimators 100 \\")
    logger.info(f"    --if-max-depth 10 \\")
    logger.info(f"    --ae-epochs 50 \\")
    logger.info(f"    --ae-hidden-dim 4 \\")
    logger.info(f"    --generate-report")
    logger.info(f"\n  # 或者直接使用默认参数:")
    logger.info(f"  python algorithm/run_training.py --generate-report")
    logger.info(f"\n  # 注意: 训练脚本默认读取 data/processed/train_test_data.npz")
    logger.info(f"  # 需要修改为读取 {npz_path}")
    logger.info(f"  # 或者用 --data-path 参数指定")


if __name__ == '__main__':
    main()
