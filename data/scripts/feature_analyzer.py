"""
特征分析模块
功能：特征相关性分析、特征重要性评估、特征可视化

优化说明：
1. 添加完整的可视化输出功能（热力图、条形图、分布图、降维图）
2. 支持生成 HTML 交互式报告
3. 增加异常检测专用特征分析
4. 支持特征分布对比和异常值检测
5. 增加统计显著性检验
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.feature_selection import mutual_info_classif, SelectKBest, f_classif
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
from scipy import stats
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple, Any
import warnings
import json
from datetime import datetime

# 可视化库（可选依赖）
try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    import seaborn as sns
    from matplotlib.colors import LinearSegmentedColormap
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False
    plt = None
    sns = None
    
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FeatureAnalyzer:
    """特征分析器（增强版，支持可视化）"""
    
    # 可视化颜色方案 - 异常检测专用配色
    COLORS = {
        'benign': '#2ecc71',       # 绿色 - 正常流量
        'normal': '#2ecc71',       # 绿色 - 正常流量（别名）
        'ddos': '#e74c3c',         # 红色 - DDoS攻击
        'scan': '#f39c12',         # 橙色 - 端口扫描
        'mirai': '#9b59b6',        # 紫色 - Mirai僵尸网络
        'botnet': '#9b59b6',       # 紫色 - 僵尸网络（别名）
        'unauthorized': '#3498db', # 蓝色 - 未授权访问
        'unknown': '#95a5a6',      # 灰色 - 未知类型
        'anomaly': '#e74c3c',      # 红色 - 通用异常
    }
    
    # 特征类别颜色（用于分组展示）
    FEATURE_CATEGORY_COLORS = {
        'flow': '#3498db',         # 流量特征 - 蓝色
        'time': '#2ecc71',         # 时间特征 - 绿色
        'packet': '#e74c3c',       # 包特征 - 红色
        'byte': '#f39c12',         # 字节特征 - 橙色
        'protocol': '#9b59b6',     # 协议特征 - 紫色
    }
    
    # 图表默认配置
    FIGURE_CONFIG = {
        'figsize_large': (14, 10),
        'figsize_medium': (12, 8),
        'figsize_small': (10, 6),
        'dpi': 150,
        'title_fontsize': 14,
        'label_fontsize': 11,
        'tick_fontsize': 9,
    }
    
    def __init__(self, df: pd.DataFrame = None, output_path: str = None):
        """
        初始化分析器
        
        Args:
            df: 数据集DataFrame
            output_path: 可视化输出路径
        """
        self.df = df
        self.feature_importance = None
        self.correlation_matrix = None
        self.pca_result = None
        self.tsne_result = None
        self.analysis_results = {}  # 存储所有分析结果
        self.output_path = Path(output_path) if output_path else Path(__file__).parent.parent / 'analysis_output'
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # 设置可视化样式
        if HAS_VISUALIZATION:
            self._setup_visualization_style()
    
    def _setup_visualization_style(self):
        """设置统一的可视化样式"""
        if not HAS_VISUALIZATION:
            return
            
        # 尝试使用中文字体
        try:
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            pass
        
        # 设置样式
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except OSError:
            plt.style.use('ggplot')
        
        sns.set_palette('husl')
        
        # 设置全局字体大小
        plt.rcParams.update({
            'figure.figsize': self.FIGURE_CONFIG['figsize_medium'],
            'figure.dpi': self.FIGURE_CONFIG['dpi'],
            'axes.titlesize': self.FIGURE_CONFIG['title_fontsize'],
            'axes.labelsize': self.FIGURE_CONFIG['label_fontsize'],
            'xtick.labelsize': self.FIGURE_CONFIG['tick_fontsize'],
            'ytick.labelsize': self.FIGURE_CONFIG['tick_fontsize'],
        })
        
    def load_data(self, file_path: str) -> pd.DataFrame:
        """加载数据"""
        self.df = pd.read_csv(file_path)
        logger.info(f"数据加载完成，共 {len(self.df)} 条记录，{len(self.df.columns)} 个特征")
        return self.df
    
    def calculate_correlation(self, numeric_features: list = None) -> pd.DataFrame:
        """
        计算特征相关性矩阵
        
        Args:
            numeric_features: 数值型特征列表
            
        Returns:
            相关性矩阵
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        if numeric_features is None:
            numeric_features = self.df.select_dtypes(include=[np.number]).columns.tolist()
            
        self.correlation_matrix = self.df[numeric_features].corr()
        logger.info(f"相关性矩阵计算完成，特征数: {len(numeric_features)}")
        
        return self.correlation_matrix
    
    def get_high_correlation_pairs(self, threshold: float = 0.8) -> list:
        """
        获取高相关性特征对
        
        Args:
            threshold: 相关性阈值
            
        Returns:
            高相关性特征对列表
        """
        if self.correlation_matrix is None:
            self.calculate_correlation()
            
        high_corr_pairs = []
        cols = self.correlation_matrix.columns
        
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                corr_value = abs(self.correlation_matrix.iloc[i, j])
                if corr_value >= threshold:
                    high_corr_pairs.append({
                        'feature_1': cols[i],
                        'feature_2': cols[j],
                        'correlation': round(corr_value, 4)
                    })
                    
        logger.info(f"发现 {len(high_corr_pairs)} 对高相关性特征（阈值: {threshold}）")
        return high_corr_pairs
    
    def calculate_feature_importance(self, 
                                    feature_columns: list,
                                    label_column: str = 'label_encoded',
                                    method: str = 'random_forest') -> pd.DataFrame:
        """
        计算特征重要性
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            method: 计算方法 ('random_forest', 'mutual_info', 'f_classif')
            
        Returns:
            特征重要性DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        X = self.df[feature_columns].values
        y = self.df[label_column].values
        
        if method == 'random_forest':
            rf = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42, n_jobs=-1)
            rf.fit(X, y)
            importance = rf.feature_importances_
            
        elif method == 'mutual_info':
            importance = mutual_info_classif(X, y, random_state=42)
            
        elif method == 'f_classif':
            selector = SelectKBest(f_classif, k='all')
            selector.fit(X, y)
            importance = selector.scores_
            importance = importance / importance.max()  # 归一化
            
        else:
            raise ValueError(f"不支持的方法: {method}")
            
        self.feature_importance = pd.DataFrame({
            'feature': feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)
        
        logger.info(f"特征重要性计算完成（方法: {method}）")
        logger.info(f"Top 5 特征:\n{self.feature_importance.head()}")
        
        return self.feature_importance
    
    def select_top_features(self, n_features: int = 6, min_importance: float = 0.1) -> list:
        """
        选择Top特征
        
        Args:
            n_features: 选择特征数量
            min_importance: 最小重要性阈值
            
        Returns:
            选中的特征列表
        """
        if self.feature_importance is None:
            raise ValueError("请先计算特征重要性")
            
        # 筛选重要性大于阈值的特征
        filtered = self.feature_importance[self.feature_importance['importance'] >= min_importance]
        
        # 取前n个
        selected = filtered.head(n_features)['feature'].tolist()
        
        logger.info(f"选择 {len(selected)} 个特征: {selected}")
        return selected
    
    def remove_redundant_features(self, 
                                  feature_columns: list,
                                  correlation_threshold: float = 0.9) -> list:
        """
        移除冗余特征（高相关性）
        
        Args:
            feature_columns: 特征列
            correlation_threshold: 相关性阈值
            
        Returns:
            去除冗余后的特征列表
        """
        if self.correlation_matrix is None:
            self.calculate_correlation(feature_columns)
            
        # 找出需要移除的特征
        features_to_remove = set()
        
        for i in range(len(feature_columns)):
            if feature_columns[i] in features_to_remove:
                continue
            for j in range(i + 1, len(feature_columns)):
                if feature_columns[j] in features_to_remove:
                    continue
                if abs(self.correlation_matrix.loc[feature_columns[i], feature_columns[j]]) > correlation_threshold:
                    # 移除重要性较低的特征
                    if self.feature_importance is not None:
                        imp_i = self.feature_importance[self.feature_importance['feature'] == feature_columns[i]]['importance'].values
                        imp_j = self.feature_importance[self.feature_importance['feature'] == feature_columns[j]]['importance'].values
                        if len(imp_i) > 0 and len(imp_j) > 0:
                            if imp_i[0] < imp_j[0]:
                                features_to_remove.add(feature_columns[i])
                            else:
                                features_to_remove.add(feature_columns[j])
                    else:
                        features_to_remove.add(feature_columns[j])
                        
        selected_features = [f for f in feature_columns if f not in features_to_remove]
        logger.info(f"移除 {len(features_to_remove)} 个冗余特征，保留 {len(selected_features)} 个")
        
        return selected_features
    
    def get_feature_statistics(self, feature_columns: list = None) -> pd.DataFrame:
        """
        获取特征统计信息
        
        Args:
            feature_columns: 特征列
            
        Returns:
            统计信息DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        if feature_columns is None:
            feature_columns = self.df.select_dtypes(include=[np.number]).columns.tolist()
            
        stats = self.df[feature_columns].describe().T
        stats['missing'] = self.df[feature_columns].isnull().sum()
        stats['missing_ratio'] = stats['missing'] / len(self.df)
        
        return stats
    
    def analyze_by_label(self, feature_columns: list, label_column: str = 'label') -> dict:
        """
        按标签分组分析特征
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            
        Returns:
            各标签的特征统计
        """
        if self.df is None:
            raise ValueError("请先加载数据")
            
        result = {}
        for label in self.df[label_column].unique():
            subset = self.df[self.df[label_column] == label]
            result[label] = subset[feature_columns].describe().T
            
        return result
    
    def save_analysis_report(self, output_path: str = None):
        """保存分析报告"""
        if output_path is None:
            output_path = Path(__file__).parent.parent / 'processed'
            
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)
        
        if self.feature_importance is not None:
            self.feature_importance.to_csv(output_path / 'feature_importance.csv', index=False)
            
        if self.correlation_matrix is not None:
            self.correlation_matrix.to_csv(output_path / 'correlation_matrix.csv')
            
        logger.info(f"分析报告已保存至: {output_path}")

    # ==================== 可视化方法 ====================
    
    def plot_correlation_heatmap(self, 
                                  features: List[str] = None,
                                  figsize: Tuple[int, int] = None,
                                  save: bool = True,
                                  filename: str = 'correlation_heatmap.png') -> Optional[plt.Figure]:
        """
        绘制特征相关性热力图
        
        Args:
            features: 要分析的特征列表，None则使用所有数值特征
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过热力图绘制")
            return None
            
        if self.correlation_matrix is None:
            self.calculate_correlation(features)
        
        corr_matrix = self.correlation_matrix
        if features is not None:
            available_features = [f for f in features if f in corr_matrix.columns]
            corr_matrix = corr_matrix.loc[available_features, available_features]
        
        figsize = figsize or self.FIGURE_CONFIG['figsize_large']
        fig, ax = plt.subplots(figsize=figsize)
        
        # 创建自定义颜色映射
        cmap = sns.diverging_palette(220, 10, as_cmap=True)
        
        # 生成掩码（只显示下三角）
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
        
        # 绘制热力图
        sns.heatmap(corr_matrix, 
                   mask=mask,
                   cmap=cmap,
                   vmax=1, vmin=-1,
                   center=0,
                   square=True,
                   linewidths=0.5,
                   cbar_kws={"shrink": 0.8, "label": "Correlation"},
                   annot=True if len(corr_matrix) <= 12 else False,
                   fmt='.2f' if len(corr_matrix) <= 12 else None,
                   annot_kws={"size": 8},
                   ax=ax)
        
        ax.set_title('Feature Correlation Heatmap', fontsize=self.FIGURE_CONFIG['title_fontsize'], fontweight='bold')
        plt.xticks(rotation=45, ha='right')
        plt.yticks(rotation=0)
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"相关性热力图已保存: {filepath}")
        
        return fig
    
    def plot_feature_importance(self,
                                top_n: int = 15,
                                figsize: Tuple[int, int] = None,
                                save: bool = True,
                                filename: str = 'feature_importance.png') -> Optional[plt.Figure]:
        """
        绘制特征重要性条形图
        
        Args:
            top_n: 显示前N个特征
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过特征重要性图绘制")
            return None
            
        if self.feature_importance is None:
            raise ValueError("请先调用 calculate_feature_importance 计算特征重要性")
        
        # 获取Top特征
        top_features = self.feature_importance.head(top_n).copy()
        top_features = top_features.iloc[::-1]  # 反转顺序，最重要的在上面
        
        figsize = figsize or self.FIGURE_CONFIG['figsize_medium']
        fig, ax = plt.subplots(figsize=figsize)
        
        # 创建渐变颜色
        colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(top_features)))[::-1]
        
        # 绘制水平条形图
        bars = ax.barh(range(len(top_features)), 
                       top_features['importance'].values,
                       color=colors,
                       edgecolor='white',
                       linewidth=0.5)
        
        # 添加数值标签
        for i, (bar, value) in enumerate(zip(bars, top_features['importance'].values)):
            ax.text(value + 0.01, bar.get_y() + bar.get_height()/2,
                   f'{value:.4f}',
                   va='center', ha='left',
                   fontsize=9)
        
        ax.set_yticks(range(len(top_features)))
        ax.set_yticklabels(top_features['feature'].values)
        ax.set_xlabel('Importance Score')
        ax.set_title(f'Top {top_n} Feature Importance', fontsize=self.FIGURE_CONFIG['title_fontsize'], fontweight='bold')
        ax.set_xlim(0, max(top_features['importance']) * 1.15)
        
        # 添加网格线
        ax.xaxis.grid(True, linestyle='--', alpha=0.7)
        ax.set_axisbelow(True)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"特征重要性图已保存: {filepath}")
        
        return fig
    
    def plot_feature_distribution(self,
                                   features: List[str],
                                   label_column: str = 'label',
                                   figsize: Tuple[int, int] = None,
                                   save: bool = True,
                                   filename: str = 'feature_distribution.png') -> Optional[plt.Figure]:
        """
        绘制特征分布对比图（按标签分组）
        
        Args:
            features: 要分析的特征列表
            label_column: 标签列名
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过分布图绘制")
            return None
            
        if self.df is None:
            raise ValueError("请先加载数据")
        
        n_features = len(features)
        n_cols = min(3, n_features)
        n_rows = (n_features + n_cols - 1) // n_cols
        
        figsize = figsize or (n_cols * 5, n_rows * 4)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        if n_features == 1:
            axes = np.array([[axes]])
        elif n_rows == 1:
            axes = axes.reshape(1, -1)
        elif n_cols == 1:
            axes = axes.reshape(-1, 1)
        
        labels = self.df[label_column].unique()
        
        for idx, feature in enumerate(features):
            row = idx // n_cols
            col = idx % n_cols
            ax = axes[row, col]
            
            for label in labels:
                label_lower = str(label).lower()
                color = self.COLORS.get(label_lower, self.COLORS['unknown'])
                
                data = self.df[self.df[label_column] == label][feature].dropna()
                
                # 绘制KDE分布
                if len(data) > 1:
                    sns.kdeplot(data=data, ax=ax, label=str(label), 
                               color=color, fill=True, alpha=0.3, linewidth=2)
            
            ax.set_xlabel(feature)
            ax.set_ylabel('Density')
            ax.set_title(f'{feature} Distribution', fontsize=10, fontweight='bold')
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, linestyle='--', alpha=0.5)
        
        # 隐藏多余的子图
        for idx in range(n_features, n_rows * n_cols):
            row = idx // n_cols
            col = idx % n_cols
            axes[row, col].set_visible(False)
        
        plt.suptitle('Feature Distribution by Label', fontsize=self.FIGURE_CONFIG['title_fontsize'], 
                     fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"特征分布图已保存: {filepath}")
        
        return fig
    
    def plot_pca_visualization(self,
                               feature_columns: List[str],
                               label_column: str = 'label',
                               n_components: int = 2,
                               figsize: Tuple[int, int] = None,
                               save: bool = True,
                               filename: str = 'pca_visualization.png') -> Optional[plt.Figure]:
        """
        PCA降维可视化
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            n_components: PCA维度
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过PCA可视化")
            return None
            
        if self.df is None:
            raise ValueError("请先加载数据")
        
        # 标准化数据
        X = self.df[feature_columns].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # PCA降维
        pca = PCA(n_components=n_components)
        X_pca = pca.fit_transform(X_scaled)
        self.pca_result = X_pca
        
        figsize = figsize or self.FIGURE_CONFIG['figsize_medium']
        fig, ax = plt.subplots(figsize=figsize)
        
        labels = self.df[label_column].values
        unique_labels = np.unique(labels)
        
        for label in unique_labels:
            label_lower = str(label).lower()
            color = self.COLORS.get(label_lower, self.COLORS['unknown'])
            mask = labels == label
            
            ax.scatter(X_pca[mask, 0], X_pca[mask, 1],
                      c=color, label=str(label),
                      alpha=0.6, s=30, edgecolors='white', linewidth=0.5)
        
        ax.set_xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)')
        ax.set_ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)')
        ax.set_title('PCA Visualization of Features', fontsize=self.FIGURE_CONFIG['title_fontsize'], fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        # 添加总方差解释比例
        total_var = sum(pca.explained_variance_ratio_[:n_components])
        ax.text(0.02, 0.98, f'Total variance explained: {total_var:.1%}',
               transform=ax.transAxes, fontsize=9, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"PCA可视化图已保存: {filepath}")
        
        # 保存PCA组件信息
        self.analysis_results['pca'] = {
            'explained_variance_ratio': pca.explained_variance_ratio_.tolist(),
            'components': pca.components_.tolist(),
            'feature_names': feature_columns
        }
        
        return fig
    
    def plot_tsne_visualization(self,
                                feature_columns: List[str],
                                label_column: str = 'label',
                                perplexity: int = 30,
                                n_samples: int = 2000,
                                figsize: Tuple[int, int] = None,
                                save: bool = True,
                                filename: str = 'tsne_visualization.png') -> Optional[plt.Figure]:
        """
        t-SNE降维可视化
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            perplexity: t-SNE困惑度参数
            n_samples: 采样数量（t-SNE计算较慢）
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过t-SNE可视化")
            return None
            
        if self.df is None:
            raise ValueError("请先加载数据")
        
        # 采样以加速t-SNE
        df_sample = self.df if len(self.df) <= n_samples else self.df.sample(n=n_samples, random_state=42)
        
        X = df_sample[feature_columns].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # t-SNE降维
        logger.info(f"正在进行t-SNE降维（样本数: {len(df_sample)}）...")
        tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, n_iter=1000)
        X_tsne = tsne.fit_transform(X_scaled)
        self.tsne_result = X_tsne
        
        figsize = figsize or self.FIGURE_CONFIG['figsize_medium']
        fig, ax = plt.subplots(figsize=figsize)
        
        labels = df_sample[label_column].values
        unique_labels = np.unique(labels)
        
        for label in unique_labels:
            label_lower = str(label).lower()
            color = self.COLORS.get(label_lower, self.COLORS['unknown'])
            mask = labels == label
            
            ax.scatter(X_tsne[mask, 0], X_tsne[mask, 1],
                      c=color, label=str(label),
                      alpha=0.6, s=30, edgecolors='white', linewidth=0.5)
        
        ax.set_xlabel('t-SNE Dimension 1')
        ax.set_ylabel('t-SNE Dimension 2')
        ax.set_title('t-SNE Visualization of Features', fontsize=self.FIGURE_CONFIG['title_fontsize'], fontweight='bold')
        ax.legend(loc='best', fontsize=9)
        ax.grid(True, linestyle='--', alpha=0.5)
        
        # 添加参数信息
        ax.text(0.02, 0.98, f'Perplexity: {perplexity}, Samples: {len(df_sample)}',
               transform=ax.transAxes, fontsize=9, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"t-SNE可视化图已保存: {filepath}")
        
        return fig
    
    def plot_anomaly_scores(self,
                            feature_columns: List[str],
                            label_column: str = 'label',
                            contamination: float = 0.1,
                            figsize: Tuple[int, int] = None,
                            save: bool = True,
                            filename: str = 'anomaly_scores.png') -> Optional[plt.Figure]:
        """
        使用IsolationForest计算并可视化异常分数
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            contamination: 预期异常比例
            figsize: 图像大小
            save: 是否保存图像
            filename: 保存文件名
            
        Returns:
            matplotlib Figure对象
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过异常分数可视化")
            return None
            
        if self.df is None:
            raise ValueError("请先加载数据")
        
        X = self.df[feature_columns].values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # 训练IsolationForest
        iso_forest = IsolationForest(contamination=contamination, random_state=42, n_jobs=-1)
        iso_forest.fit(X_scaled)
        
        # 计算异常分数
        anomaly_scores = -iso_forest.decision_function(X_scaled)  # 越高越异常
        
        figsize = figsize or (14, 5)
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 左图：异常分数分布
        ax1 = axes[0]
        labels = self.df[label_column].values
        unique_labels = np.unique(labels)
        
        for label in unique_labels:
            label_lower = str(label).lower()
            color = self.COLORS.get(label_lower, self.COLORS['unknown'])
            mask = labels == label
            
            sns.kdeplot(data=anomaly_scores[mask], ax=ax1, label=str(label),
                       color=color, fill=True, alpha=0.3, linewidth=2)
        
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Threshold')
        ax1.set_xlabel('Anomaly Score')
        ax1.set_ylabel('Density')
        ax1.set_title('Anomaly Score Distribution by Label', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=9)
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # 右图：异常分数箱线图
        ax2 = axes[1]
        df_plot = pd.DataFrame({
            'Anomaly Score': anomaly_scores,
            'Label': labels
        })
        
        # 自定义颜色列表
        palette = [self.COLORS.get(str(l).lower(), self.COLORS['unknown']) for l in unique_labels]
        
        sns.boxplot(x='Label', y='Anomaly Score', data=df_plot, ax=ax2, palette=palette)
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=2)
        ax2.set_title('Anomaly Score by Label (Box Plot)', fontsize=12, fontweight='bold')
        ax2.grid(True, linestyle='--', alpha=0.5, axis='y')
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=self.FIGURE_CONFIG['dpi'], bbox_inches='tight')
            logger.info(f"异常分数图已保存: {filepath}")
        
        # 保存异常分数到结果
        self.analysis_results['anomaly_scores'] = {
            'mean_by_label': {str(l): float(anomaly_scores[labels == l].mean()) for l in unique_labels},
            'std_by_label': {str(l): float(anomaly_scores[labels == l].std()) for l in unique_labels}
        }
        
        return fig
    
    def perform_statistical_tests(self,
                                   feature_columns: List[str],
                                   label_column: str = 'label',
                                   normal_label: str = 'benign') -> pd.DataFrame:
        """
        执行统计显著性检验（比较正常与异常样本的特征差异）
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            normal_label: 正常样本的标签值
            
        Returns:
            统计检验结果DataFrame
        """
        if self.df is None:
            raise ValueError("请先加载数据")
        
        results = []
        
        normal_mask = self.df[label_column] == normal_label
        normal_data = self.df[normal_mask]
        abnormal_data = self.df[~normal_mask]
        
        for feature in feature_columns:
            normal_values = normal_data[feature].dropna().values
            abnormal_values = abnormal_data[feature].dropna().values
            
            if len(normal_values) < 3 or len(abnormal_values) < 3:
                continue
            
            # Mann-Whitney U检验（非参数检验）
            try:
                statistic, p_value = stats.mannwhitneyu(normal_values, abnormal_values, alternative='two-sided')
            except ValueError:
                statistic, p_value = np.nan, np.nan
            
            # Cohen's d 效应量
            pooled_std = np.sqrt(((len(normal_values) - 1) * np.std(normal_values)**2 + 
                                  (len(abnormal_values) - 1) * np.std(abnormal_values)**2) / 
                                 (len(normal_values) + len(abnormal_values) - 2))
            cohens_d = (np.mean(abnormal_values) - np.mean(normal_values)) / pooled_std if pooled_std > 0 else 0
            
            # 判断显著性
            significance = ''
            if p_value < 0.001:
                significance = '***'
            elif p_value < 0.01:
                significance = '**'
            elif p_value < 0.05:
                significance = '*'
            
            results.append({
                'feature': feature,
                'normal_mean': np.mean(normal_values),
                'normal_std': np.std(normal_values),
                'abnormal_mean': np.mean(abnormal_values),
                'abnormal_std': np.std(abnormal_values),
                'mann_whitney_u': statistic,
                'p_value': p_value,
                'cohens_d': cohens_d,
                'significance': significance,
                'effect_size': 'large' if abs(cohens_d) >= 0.8 else ('medium' if abs(cohens_d) >= 0.5 else 'small')
            })
        
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('p_value')
        
        # 保存到分析结果
        self.analysis_results['statistical_tests'] = results_df.to_dict('records')
        
        logger.info(f"统计检验完成，{len(results_df[results_df['p_value'] < 0.05])} 个特征具有显著差异 (p < 0.05)")
        
        return results_df
    
    def generate_html_report(self,
                             feature_columns: List[str],
                             label_column: str = 'label',
                             report_title: str = 'Feature Analysis Report') -> str:
        """
        生成完整的HTML交互式报告
        
        Args:
            feature_columns: 特征列
            label_column: 标签列
            report_title: 报告标题
            
        Returns:
            报告文件路径
        """
        if self.df is None:
            raise ValueError("请先加载数据")
        
        # 确保已计算必要的分析
        if self.correlation_matrix is None:
            self.calculate_correlation(feature_columns)
        
        # 生成所有可视化
        logger.info("正在生成分析报告...")
        
        image_files = {}
        
        # 1. 相关性热力图
        if HAS_VISUALIZATION:
            self.plot_correlation_heatmap(feature_columns, save=True)
            image_files['correlation'] = 'correlation_heatmap.png'
        
        # 2. 特征重要性图
        if self.feature_importance is not None and HAS_VISUALIZATION:
            self.plot_feature_importance(save=True)
            image_files['importance'] = 'feature_importance.png'
        
        # 3. 特征分布图
        if HAS_VISUALIZATION and len(feature_columns) > 0:
            top_features = feature_columns[:6] if self.feature_importance is None else \
                          self.feature_importance.head(6)['feature'].tolist()
            self.plot_feature_distribution(top_features, label_column, save=True)
            image_files['distribution'] = 'feature_distribution.png'
        
        # 4. PCA可视化
        if HAS_VISUALIZATION:
            self.plot_pca_visualization(feature_columns, label_column, save=True)
            image_files['pca'] = 'pca_visualization.png'
        
        # 5. 异常分数可视化
        if HAS_VISUALIZATION:
            self.plot_anomaly_scores(feature_columns, label_column, save=True)
            image_files['anomaly'] = 'anomaly_scores.png'
        
        # 6. 统计检验
        stat_results = self.perform_statistical_tests(feature_columns, label_column)
        
        # 生成统计摘要
        stats_summary = self.get_feature_statistics(feature_columns)
        label_counts = self.df[label_column].value_counts().to_dict()
        
        # 构建HTML报告
        html_content = self._build_html_report(
            report_title=report_title,
            image_files=image_files,
            stats_summary=stats_summary,
            label_counts=label_counts,
            stat_results=stat_results,
            feature_columns=feature_columns
        )
        
        # 保存HTML报告
        report_path = self.output_path / 'analysis_report.html'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已生成: {report_path}")
        
        # 保存JSON格式的分析结果
        json_path = self.output_path / 'analysis_results.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            # 转换不可序列化的对象
            serializable_results = {}
            for key, value in self.analysis_results.items():
                if isinstance(value, pd.DataFrame):
                    serializable_results[key] = value.to_dict('records')
                else:
                    serializable_results[key] = value
            json.dump(serializable_results, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"分析结果JSON已保存: {json_path}")
        
        return str(report_path)
    
    def _build_html_report(self,
                           report_title: str,
                           image_files: Dict[str, str],
                           stats_summary: pd.DataFrame,
                           label_counts: Dict,
                           stat_results: pd.DataFrame,
                           feature_columns: List[str]) -> str:
        """构建HTML报告内容"""
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 转换统计表格为HTML
        stats_html = stats_summary.to_html(classes='table table-striped table-hover', float_format='%.4f')
        
        # 转换统计检验结果为HTML
        stat_results_display = stat_results[['feature', 'normal_mean', 'abnormal_mean', 'p_value', 'cohens_d', 'significance', 'effect_size']].head(15)
        stat_results_html = stat_results_display.to_html(classes='table table-striped table-hover', float_format='%.4f', index=False)
        
        # 标签分布
        label_html = ''.join([f'<span class="badge bg-secondary mx-1">{k}: {v}</span>' for k, v in label_counts.items()])
        
        # 图像部分
        images_html = ''
        for key, filename in image_files.items():
            section_title = {
                'correlation': 'Feature Correlation Heatmap',
                'importance': 'Feature Importance',
                'distribution': 'Feature Distribution by Label',
                'pca': 'PCA Visualization',
                'anomaly': 'Anomaly Score Analysis'
            }.get(key, key.title())
            
            images_html += f'''
            <div class="card mb-4">
                <div class="card-header"><h5>{section_title}</h5></div>
                <div class="card-body text-center">
                    <img src="{filename}" class="img-fluid" alt="{section_title}" style="max-width: 100%;">
                </div>
            </div>
            '''
        
        html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 0; }}
        .card {{ border: none; box-shadow: 0 2px 15px rgba(0,0,0,0.1); border-radius: 10px; }}
        .card-header {{ background-color: #f8f9fa; border-bottom: 1px solid #e9ecef; font-weight: 600; }}
        .table {{ font-size: 0.9rem; }}
        .badge {{ font-size: 0.85rem; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header text-center">
        <h1>{report_title}</h1>
        <p class="mb-0">Generated at: {timestamp}</p>
    </div>
    
    <div class="container mt-4">
        <!-- 数据概览 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card stat-card text-center p-3">
                    <div class="stat-value">{len(self.df):,}</div>
                    <div>Total Samples</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card text-center p-3">
                    <div class="stat-value">{len(feature_columns)}</div>
                    <div>Features Analyzed</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card text-center p-3">
                    <div class="stat-value">{len(label_counts)}</div>
                    <div>Label Classes</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card text-center p-3">
                    <div class="stat-value">{len(stat_results[stat_results['p_value'] < 0.05])}</div>
                    <div>Significant Features</div>
                </div>
            </div>
        </div>
        
        <!-- 标签分布 -->
        <div class="card mb-4">
            <div class="card-header"><h5>Label Distribution</h5></div>
            <div class="card-body">{label_html}</div>
        </div>
        
        <!-- 可视化图表 -->
        {images_html}
        
        <!-- 统计检验结果 -->
        <div class="card mb-4">
            <div class="card-header"><h5>Statistical Test Results (Top Features)</h5></div>
            <div class="card-body">
                <p class="text-muted">Mann-Whitney U test comparing normal vs abnormal samples. 
                   Significance: *** p&lt;0.001, ** p&lt;0.01, * p&lt;0.05</p>
                <div class="table-responsive">{stat_results_html}</div>
            </div>
        </div>
        
        <!-- 特征统计摘要 -->
        <div class="card mb-4">
            <div class="card-header"><h5>Feature Statistics Summary</h5></div>
            <div class="card-body">
                <div class="table-responsive">{stats_html}</div>
            </div>
        </div>
    </div>
    
    <footer class="text-center py-4 text-muted">
        <p>ShieldHome Detection System - Feature Analysis Module</p>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''
        
        return html_template
    
    def run_full_analysis(self,
                          feature_columns: List[str],
                          label_column: str = 'label',
                          label_encoded_column: str = 'label_encoded') -> Dict[str, Any]:
        """
        运行完整的特征分析流程
        
        Args:
            feature_columns: 特征列
            label_column: 标签列名
            label_encoded_column: 编码后的标签列名
            
        Returns:
            完整的分析结果字典
        """
        logger.info("="*50)
        logger.info("开始完整特征分析流程")
        logger.info("="*50)
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'n_samples': len(self.df),
            'n_features': len(feature_columns),
            'features': feature_columns
        }
        
        # 1. 计算相关性
        logger.info("\n[1/6] 计算特征相关性...")
        self.calculate_correlation(feature_columns)
        high_corr = self.get_high_correlation_pairs(threshold=0.8)
        results['high_correlation_pairs'] = high_corr
        
        # 2. 计算特征重要性
        logger.info("\n[2/6] 计算特征重要性...")
        if label_encoded_column in self.df.columns:
            self.calculate_feature_importance(feature_columns, label_encoded_column)
            results['top_features'] = self.select_top_features(n_features=10)
        
        # 3. 统计检验
        logger.info("\n[3/6] 执行统计显著性检验...")
        stat_results = self.perform_statistical_tests(feature_columns, label_column)
        results['significant_features'] = stat_results[stat_results['p_value'] < 0.05]['feature'].tolist()
        
        # 4. 移除冗余特征
        logger.info("\n[4/6] 识别冗余特征...")
        non_redundant = self.remove_redundant_features(feature_columns)
        results['non_redundant_features'] = non_redundant
        
        # 5. 生成可视化
        logger.info("\n[5/6] 生成可视化图表...")
        if HAS_VISUALIZATION:
            self.plot_correlation_heatmap(feature_columns)
            if self.feature_importance is not None:
                self.plot_feature_importance()
            top_viz_features = feature_columns[:6]
            self.plot_feature_distribution(top_viz_features, label_column)
            self.plot_pca_visualization(feature_columns, label_column)
            self.plot_anomaly_scores(feature_columns, label_column)
        
        # 6. 生成报告
        logger.info("\n[6/6] 生成分析报告...")
        report_path = self.generate_html_report(feature_columns, label_column)
        results['report_path'] = report_path
        
        # 保存分析报告
        self.save_analysis_report()
        
        logger.info("="*50)
        logger.info("特征分析完成！")
        logger.info(f"报告位置: {report_path}")
        logger.info("="*50)
        
        return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='特征分析工具')
    parser.add_argument('--input', '-i', type=str, help='输入数据文件路径')
    parser.add_argument('--output', '-o', type=str, help='输出目录路径')
    parser.add_argument('--features', '-f', type=str, nargs='+', help='要分析的特征列')
    parser.add_argument('--label', '-l', type=str, default='label', help='标签列名')
    parser.add_argument('--full', action='store_true', help='运行完整分析流程')
    
    args = parser.parse_args()
    
    print("="*60)
    print("特征分析模块 (Feature Analyzer)")
    print("="*60)
    
    if args.input:
        # 命令行模式
        analyzer = FeatureAnalyzer(output_path=args.output)
        analyzer.load_data(args.input)
        
        if args.features:
            features = args.features
        else:
            features = analyzer.df.select_dtypes(include=[np.number]).columns.tolist()
            # 移除标签列
            features = [f for f in features if f not in [args.label, 'label_encoded']]
        
        if args.full:
            results = analyzer.run_full_analysis(features, args.label)
            print(f"\n分析完成！报告位置: {results['report_path']}")
        else:
            # 基础分析
            analyzer.calculate_correlation(features)
            if 'label_encoded' in analyzer.df.columns:
                analyzer.calculate_feature_importance(features, 'label_encoded')
            analyzer.save_analysis_report()
    else:
        # 交互模式提示
        print("\n使用方法:")
        print("-"*60)
        print("1. 命令行模式:")
        print("   python feature_analyzer.py -i data.csv -o ./output --full")
        print()
        print("2. 代码调用:")
        print("   from feature_analyzer import FeatureAnalyzer")
        print("   analyzer = FeatureAnalyzer(output_path='./analysis_output')")
        print("   analyzer.load_data('processed_data.csv')")
        print("   ")
        print("   # 计算特征重要性")
        print("   features = ['duration', 'src_bytes', 'dst_bytes', ...]")
        print("   importance = analyzer.calculate_feature_importance(features, 'label_encoded')")
        print("   ")
        print("   # 运行完整分析")
        print("   results = analyzer.run_full_analysis(features, 'label')")
        print()
        print("3. 可视化方法:")
        print("   - plot_correlation_heatmap()  : 相关性热力图")
        print("   - plot_feature_importance()   : 特征重要性条形图")
        print("   - plot_feature_distribution() : 特征分布对比图")
        print("   - plot_pca_visualization()    : PCA降维可视化")
        print("   - plot_tsne_visualization()   : t-SNE降维可视化")
        print("   - plot_anomaly_scores()       : 异常分数分布图")
        print("   - generate_html_report()      : 生成HTML交互报告")
        print()
        print(f"可视化功能状态: {'已启用' if HAS_VISUALIZATION else '未安装（需要matplotlib和seaborn）'}")
        print("="*60)
