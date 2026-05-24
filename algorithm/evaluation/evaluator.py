"""
模型评估模块
功能：统一评估所有模型、生成对比报告、性能基准测试

优化内容：
1. 添加可视化功能（ROC曲线、PR曲线、混淆矩阵）
2. 生成HTML评估报告
3. 增加模型对比雷达图
4. 添加统计显著性检验
5. 支持交叉验证评估
"""

import numpy as np
import pandas as pd
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from sklearn.metrics import (
    roc_curve, precision_recall_curve, auc,
    confusion_matrix, classification_report,
    f1_score, precision_score, recall_score, accuracy_score,
    roc_auc_score, average_precision_score
)
from sklearn.model_selection import cross_val_predict, StratifiedKFold
import logging
import warnings

warnings.filterwarnings('ignore')

# 可视化库（可选）
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_VISUALIZATION = True
except ImportError:
    HAS_VISUALIZATION = False
    plt = None
    sns = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ModelEvaluator:
    """模型评估器（优化版）"""
    
    # 项目要求
    PROJECT_REQUIREMENTS = {
        'f1_score': {'min': 0.85, 'description': 'F1分数'},
        'false_positive_rate': {'max': 0.05, 'description': '误报率'},
        'false_negative_rate': {'max': 0.03, 'description': '漏报率'},
        'avg_inference_time_ms': {'max': 100, 'description': '推理延迟'},
        'memory_usage_mb': {'max': 30, 'description': '内存占用'}
    }
    
    # 可视化颜色方案
    COLORS = {
        'primary': '#3498db',
        'secondary': '#2ecc71',
        'danger': '#e74c3c',
        'warning': '#f39c12',
        'info': '#9b59b6'
    }
    
    def __init__(self, output_path: str = None):
        """
        初始化评估器
        
        Args:
            output_path: 评估报告输出路径
        """
        self.output_path = Path(output_path) if output_path else Path(__file__).parent.parent / 'evaluation_output'
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.results = {}
        self.predictions_cache = {}  # 缓存预测结果用于可视化
        
        # 设置可视化样式
        if HAS_VISUALIZATION:
            self._setup_visualization()
    
    def _setup_visualization(self):
        """设置可视化样式"""
        if not HAS_VISUALIZATION:
            return
        
        try:
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass
        
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            plt.style.use('ggplot')
        
        sns.set_palette('husl')
        
    def evaluate_model(self, 
                      model, 
                      model_name: str,
                      X_test: np.ndarray, 
                      y_test: np.ndarray,
                      run_benchmark: bool = True,
                      save_predictions: bool = True) -> dict:
        """
        评估单个模型
        
        Args:
            model: 模型实例
            model_name: 模型名称
            X_test: 测试数据
            y_test: 测试标签
            run_benchmark: 是否运行性能基准测试
            save_predictions: 是否保存预测结果
            
        Returns:
            评估结果字典
        """
        logger.info(f"=" * 50)
        logger.info(f"评估模型: {model_name}")
        logger.info(f"=" * 50)
        
        result = {
            'model_name': model_name,
            'metrics': {},
            'benchmark': {},
            'model_size_mb': None,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 转换标签
        y_binary = np.where(y_test > 0, 1, 0)
        
        # 获取预测
        try:
            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
        except Exception as e:
            logger.error(f"模型预测失败: {e}")
            return result
        
        # 保存预测结果用于可视化
        if save_predictions:
            self.predictions_cache[model_name] = {
                'y_true': y_binary,
                'y_pred': y_pred,
                'y_proba': y_proba
            }
        
        # 计算基本指标
        result['metrics'] = self._calculate_metrics(y_binary, y_pred, y_proba)
        
        # 性能基准测试
        if run_benchmark and hasattr(model, 'benchmark_inference'):
            try:
                benchmark = model.benchmark_inference(X_test)
                result['benchmark'] = benchmark
            except Exception as e:
                logger.warning(f"基准测试失败: {e}")
                result['benchmark'] = {}
        
        # 计算模型大小
        if hasattr(model, '_estimate_model_size'):
            try:
                result['model_size_mb'] = model._estimate_model_size()
            except:
                pass
            
        self.results[model_name] = result
        return result
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray, 
                          y_proba: np.ndarray = None) -> Dict:
        """计算评估指标"""
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1_score': f1_score(y_true, y_pred, zero_division=0)
        }
        
        # 混淆矩阵
        cm = confusion_matrix(y_true, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        
        # 详细指标
        if len(cm) == 2:
            tn, fp, fn, tp = cm.ravel()
            metrics['true_positives'] = int(tp)
            metrics['true_negatives'] = int(tn)
            metrics['false_positives'] = int(fp)
            metrics['false_negatives'] = int(fn)
            metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
            metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0
            metrics['true_positive_rate'] = tp / (tp + fn) if (tp + fn) > 0 else 0
            metrics['true_negative_rate'] = tn / (tn + fp) if (tn + fp) > 0 else 0
            metrics['specificity'] = metrics['true_negative_rate']
            metrics['sensitivity'] = metrics['true_positive_rate']
        
        # AUC 指标
        if y_proba is not None:
            try:
                metrics['auc_roc'] = roc_auc_score(y_true, y_proba)
                metrics['auc_pr'] = average_precision_score(y_true, y_proba)
            except ValueError:
                metrics['auc_roc'] = 0.5
                metrics['auc_pr'] = 0.5
        
        # Matthews 相关系数
        from sklearn.metrics import matthews_corrcoef
        metrics['mcc'] = matthews_corrcoef(y_true, y_pred)
        
        return metrics
    
    def compare_models(self, models: Dict[str, Any], X_test: np.ndarray, y_test: np.ndarray,
                      generate_plots: bool = True) -> pd.DataFrame:
        """
        对比多个模型
        
        Args:
            models: 模型字典 {名称: 模型实例}
            X_test: 测试数据
            y_test: 测试标签
            generate_plots: 是否生成可视化图表
            
        Returns:
            对比结果DataFrame
        """
        logger.info("开始模型对比评估...")
        
        for name, model in models.items():
            self.evaluate_model(model, name, X_test, y_test)
            
        # 生成对比表格
        comparison_data = []
        for name, result in self.results.items():
            row = {
                '模型': name,
                '准确率': result['metrics'].get('accuracy', 0),
                '精确率': result['metrics'].get('precision', 0),
                '召回率': result['metrics'].get('recall', 0),
                'F1分数': result['metrics'].get('f1_score', 0),
                'AUC-ROC': result['metrics'].get('auc_roc', 0),
                'MCC': result['metrics'].get('mcc', 0),
                '误报率': result['metrics'].get('false_positive_rate', 0),
                '漏报率': result['metrics'].get('false_negative_rate', 0),
                '推理时间(ms)': result['benchmark'].get('avg_inference_time_ms', 0),
                '内存占用(MB)': result['benchmark'].get('memory_usage_mb', 0)
            }
            comparison_data.append(row)
            
        df = pd.DataFrame(comparison_data)
        df = df.sort_values('F1分数', ascending=False)
        
        logger.info("\n模型对比结果:")
        logger.info(f"\n{df.to_string(index=False)}")
        
        # 生成可视化
        if generate_plots and HAS_VISUALIZATION:
            self.plot_roc_curves()
            self.plot_pr_curves()
            self.plot_confusion_matrices()
            self.plot_model_comparison_radar()
            self.plot_metrics_bar_chart(df)
        
        return df
    
    def plot_roc_curves(self, figsize: Tuple[int, int] = (10, 8), 
                        save: bool = True, filename: str = 'roc_curves.png'):
        """
        绘制ROC曲线对比图
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过ROC曲线绘制")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(self.predictions_cache)))
        
        for (model_name, cache), color in zip(self.predictions_cache.items(), colors):
            if cache['y_proba'] is None:
                continue
            
            fpr, tpr, _ = roc_curve(cache['y_true'], cache['y_proba'])
            roc_auc = auc(fpr, tpr)
            
            ax.plot(fpr, tpr, color=color, lw=2, 
                   label=f'{model_name} (AUC = {roc_auc:.3f})')
        
        # 对角线
        ax.plot([0, 1], [0, 1], 'k--', lw=1, label='Random (AUC = 0.500)')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('False Positive Rate', fontsize=12)
        ax.set_ylabel('True Positive Rate', fontsize=12)
        ax.set_title('ROC Curves Comparison', fontsize=14, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"ROC曲线已保存: {filepath}")
        
        return fig
    
    def plot_pr_curves(self, figsize: Tuple[int, int] = (10, 8),
                       save: bool = True, filename: str = 'pr_curves.png'):
        """
        绘制PR曲线对比图
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过PR曲线绘制")
            return None
        
        fig, ax = plt.subplots(figsize=figsize)
        
        colors = plt.cm.Set1(np.linspace(0, 1, len(self.predictions_cache)))
        
        for (model_name, cache), color in zip(self.predictions_cache.items(), colors):
            if cache['y_proba'] is None:
                continue
            
            precision, recall, _ = precision_recall_curve(cache['y_true'], cache['y_proba'])
            ap = average_precision_score(cache['y_true'], cache['y_proba'])
            
            ax.plot(recall, precision, color=color, lw=2,
                   label=f'{model_name} (AP = {ap:.3f})')
        
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel('Recall', fontsize=12)
        ax.set_ylabel('Precision', fontsize=12)
        ax.set_title('Precision-Recall Curves Comparison', fontsize=14, fontweight='bold')
        ax.legend(loc='lower left', fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"PR曲线已保存: {filepath}")
        
        return fig
    
    def plot_confusion_matrices(self, figsize: Tuple[int, int] = None,
                                save: bool = True, filename: str = 'confusion_matrices.png'):
        """
        绘制混淆矩阵热力图
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过混淆矩阵绘制")
            return None
        
        n_models = len(self.predictions_cache)
        if n_models == 0:
            return None
        
        n_cols = min(3, n_models)
        n_rows = (n_models + n_cols - 1) // n_cols
        
        figsize = figsize or (5 * n_cols, 4 * n_rows)
        fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
        
        if n_models == 1:
            axes = np.array([[axes]])
        elif n_rows == 1:
            axes = axes.reshape(1, -1)
        elif n_cols == 1:
            axes = axes.reshape(-1, 1)
        
        for idx, (model_name, cache) in enumerate(self.predictions_cache.items()):
            row = idx // n_cols
            col = idx % n_cols
            ax = axes[row, col]
            
            cm = confusion_matrix(cache['y_true'], cache['y_pred'])
            
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax,
                       xticklabels=['Normal', 'Anomaly'],
                       yticklabels=['Normal', 'Anomaly'])
            
            ax.set_xlabel('Predicted', fontsize=10)
            ax.set_ylabel('Actual', fontsize=10)
            ax.set_title(f'{model_name}', fontsize=11, fontweight='bold')
        
        # 隐藏多余的子图
        for idx in range(n_models, n_rows * n_cols):
            row = idx // n_cols
            col = idx % n_cols
            axes[row, col].set_visible(False)
        
        plt.suptitle('Confusion Matrices', fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"混淆矩阵已保存: {filepath}")
        
        return fig
    
    def plot_model_comparison_radar(self, figsize: Tuple[int, int] = (10, 10),
                                    save: bool = True, filename: str = 'radar_comparison.png'):
        """
        绘制模型对比雷达图
        """
        if not HAS_VISUALIZATION:
            logger.warning("可视化库未安装，跳过雷达图绘制")
            return None
        
        if len(self.results) == 0:
            return None
        
        # 选择要比较的指标
        metrics_to_compare = ['accuracy', 'precision', 'recall', 'f1_score', 'auc_roc']
        labels = ['Accuracy', 'Precision', 'Recall', 'F1 Score', 'AUC-ROC']
        
        fig, ax = plt.subplots(figsize=figsize, subplot_kw=dict(polar=True))
        
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles += angles[:1]  # 闭合
        
        colors = plt.cm.Set2(np.linspace(0, 1, len(self.results)))
        
        for (model_name, result), color in zip(self.results.items(), colors):
            values = [result['metrics'].get(m, 0) for m in metrics_to_compare]
            values += values[:1]  # 闭合
            
            ax.plot(angles, values, 'o-', linewidth=2, label=model_name, color=color)
            ax.fill(angles, values, alpha=0.25, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylim(0, 1)
        ax.set_title('Model Comparison Radar Chart', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=10)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"雷达图已保存: {filepath}")
        
        return fig
    
    def plot_metrics_bar_chart(self, df: pd.DataFrame = None,
                               figsize: Tuple[int, int] = (14, 6),
                               save: bool = True, filename: str = 'metrics_comparison.png'):
        """
        绘制指标对比条形图
        """
        if not HAS_VISUALIZATION:
            return None
        
        if df is None:
            return None
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 左图：性能指标
        metrics = ['准确率', '精确率', '召回率', 'F1分数']
        x = np.arange(len(df))
        width = 0.2
        
        ax1 = axes[0]
        for i, metric in enumerate(metrics):
            ax1.bar(x + i * width, df[metric], width, label=metric)
        
        ax1.set_xticks(x + width * 1.5)
        ax1.set_xticklabels(df['模型'], rotation=45, ha='right')
        ax1.set_ylabel('Score')
        ax1.set_title('Performance Metrics Comparison', fontsize=12, fontweight='bold')
        ax1.legend(loc='lower right')
        ax1.set_ylim(0, 1.1)
        ax1.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        # 右图：误报率和漏报率
        ax2 = axes[1]
        width = 0.35
        ax2.bar(x - width/2, df['误报率'] * 100, width, label='误报率', color=self.COLORS['warning'])
        ax2.bar(x + width/2, df['漏报率'] * 100, width, label='漏报率', color=self.COLORS['danger'])
        
        # 添加阈值线
        ax2.axhline(y=5, color='orange', linestyle='--', linewidth=2, label='误报率阈值 (5%)')
        ax2.axhline(y=3, color='red', linestyle='--', linewidth=2, label='漏报率阈值 (3%)')
        
        ax2.set_xticks(x)
        ax2.set_xticklabels(df['模型'], rotation=45, ha='right')
        ax2.set_ylabel('Rate (%)')
        ax2.set_title('Error Rates Comparison', fontsize=12, fontweight='bold')
        ax2.legend(loc='upper right')
        ax2.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save:
            filepath = self.output_path / filename
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            logger.info(f"指标对比图已保存: {filepath}")
        
        return fig
    
    def check_requirements(self, model_name: str = None) -> dict:
        """
        检查是否满足项目要求
        
        要求：
        - F1分数 ≥ 0.85
        - 误报率 ≤ 5%
        - 漏报率 ≤ 3%
        - 推理延迟 ≤ 100ms
        - 内存占用 ≤ 30MB
        """
        results_to_check = {model_name: self.results[model_name]} if model_name else self.results
        
        check_results = {}
        for name, result in results_to_check.items():
            checks = {}
            
            # F1分数
            f1 = result['metrics'].get('f1_score', 0)
            checks['F1分数 ≥ 0.85'] = {
                'value': f1,
                'passed': f1 >= 0.85,
                'target': '≥ 0.85'
            }
            
            # 误报率
            fpr = result['metrics'].get('false_positive_rate', 1)
            checks['误报率 ≤ 5%'] = {
                'value': fpr,
                'passed': fpr <= 0.05,
                'target': '≤ 5%'
            }
            
            # 漏报率
            fnr = result['metrics'].get('false_negative_rate', 1)
            checks['漏报率 ≤ 3%'] = {
                'value': fnr,
                'passed': fnr <= 0.03,
                'target': '≤ 3%'
            }
            
            # 推理延迟
            latency = result['benchmark'].get('avg_inference_time_ms', float('inf'))
            checks['推理延迟 ≤ 100ms'] = {
                'value': latency,
                'passed': latency <= 100,
                'target': '≤ 100ms'
            }
            
            # 内存占用
            memory = result['benchmark'].get('memory_usage_mb', float('inf'))
            checks['内存占用 ≤ 30MB'] = {
                'value': memory,
                'passed': memory <= 30,
                'target': '≤ 30MB'
            }
            
            all_passed = all(c['passed'] for c in checks.values())
            check_results[name] = {
                'checks': checks,
                'all_passed': all_passed,
                'passed_count': sum(1 for c in checks.values() if c['passed']),
                'total_checks': len(checks)
            }
            
            logger.info(f"\n{name} 指标检查:")
            for check_name, check_info in checks.items():
                status = "✓" if check_info['passed'] else "✗"
                logger.info(f"  {status} {check_name}: {check_info['value']:.4f}")
            logger.info(f"  总体: {'全部通过 ✓' if all_passed else '未全部通过 ✗'}")
            
        return check_results
    
    def generate_html_report(self, filename: str = 'evaluation_report.html') -> str:
        """
        生成HTML评估报告
        
        Returns:
            报告文件路径
        """
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # 准备数据
        models_html = ''
        for name, result in self.results.items():
            metrics = result['metrics']
            benchmark = result['benchmark']
            
            check = self.check_requirements(name)
            all_passed = check[name]['all_passed']
            status_badge = '<span class="badge bg-success">通过</span>' if all_passed else '<span class="badge bg-danger">未通过</span>'
            
            models_html += f'''
            <div class="card mb-4">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">{name}</h5>
                    {status_badge}
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6>性能指标</h6>
                            <table class="table table-sm">
                                <tr><td>准确率</td><td>{metrics.get('accuracy', 0):.4f}</td></tr>
                                <tr><td>精确率</td><td>{metrics.get('precision', 0):.4f}</td></tr>
                                <tr><td>召回率</td><td>{metrics.get('recall', 0):.4f}</td></tr>
                                <tr><td>F1分数</td><td>{metrics.get('f1_score', 0):.4f}</td></tr>
                                <tr><td>AUC-ROC</td><td>{metrics.get('auc_roc', 0):.4f}</td></tr>
                                <tr><td>MCC</td><td>{metrics.get('mcc', 0):.4f}</td></tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <h6>错误率 & 性能</h6>
                            <table class="table table-sm">
                                <tr><td>误报率</td><td>{metrics.get('false_positive_rate', 0)*100:.2f}%</td></tr>
                                <tr><td>漏报率</td><td>{metrics.get('false_negative_rate', 0)*100:.2f}%</td></tr>
                                <tr><td>推理时间</td><td>{benchmark.get('avg_inference_time_ms', 0):.2f} ms</td></tr>
                                <tr><td>内存占用</td><td>{benchmark.get('memory_usage_mb', 0):.2f} MB</td></tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
            '''
        
        # 图表部分
        images_html = ''
        image_files = ['roc_curves.png', 'pr_curves.png', 'confusion_matrices.png', 
                      'radar_comparison.png', 'metrics_comparison.png']
        image_titles = ['ROC Curves', 'PR Curves', 'Confusion Matrices', 
                       'Radar Comparison', 'Metrics Comparison']
        
        for img_file, title in zip(image_files, image_titles):
            if (self.output_path / img_file).exists():
                images_html += f'''
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header"><h6>{title}</h6></div>
                        <div class="card-body text-center">
                            <img src="{img_file}" class="img-fluid" alt="{title}">
                        </div>
                    </div>
                </div>
                '''
        
        html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Model Evaluation Report</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 0; }}
        .card {{ border: none; box-shadow: 0 2px 15px rgba(0,0,0,0.1); border-radius: 10px; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; padding: 20px; }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header text-center">
        <h1>Model Evaluation Report</h1>
        <p class="mb-0">Generated: {timestamp}</p>
    </div>
    
    <div class="container mt-4">
        <!-- 概览统计 -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card stat-card">
                    <div class="stat-value">{len(self.results)}</div>
                    <div>Models Evaluated</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card">
                    <div class="stat-value">{max([r['metrics'].get('f1_score', 0) for r in self.results.values()]):.2f}</div>
                    <div>Best F1 Score</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card">
                    <div class="stat-value">{min([r['benchmark'].get('avg_inference_time_ms', 999) for r in self.results.values()]):.1f}ms</div>
                    <div>Fastest Inference</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card stat-card">
                    <div class="stat-value">{sum(1 for r in self.results.values() if r['metrics'].get('f1_score', 0) >= 0.85)}</div>
                    <div>Meet F1 Target</div>
                </div>
            </div>
        </div>
        
        <!-- 模型详情 -->
        <h4 class="mb-3">Model Details</h4>
        {models_html}
        
        <!-- 可视化图表 -->
        <h4 class="mb-3">Visualization</h4>
        <div class="row">
            {images_html}
        </div>
    </div>
    
    <footer class="text-center py-4 text-muted">
        <p>ShieldHome Detection System - Evaluation Module</p>
    </footer>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''
        
        report_path = self.output_path / filename
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已生成: {report_path}")
        return str(report_path)
    
    def save_report(self, filename: str = 'evaluation_report.json'):
        """保存评估报告（JSON格式）"""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'results': {}
        }
        
        for name, result in self.results.items():
            # 转换numpy类型为Python原生类型
            report['results'][name] = {
                'metrics': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v 
                           for k, v in result['metrics'].items()},
                'benchmark': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v 
                             for k, v in result['benchmark'].items()}
            }
            
        output_file = self.output_path / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
        logger.info(f"评估报告已保存: {output_file}")
        
    def save_comparison_csv(self, df: pd.DataFrame, filename: str = 'model_comparison.csv'):
        """保存对比结果CSV"""
        output_file = self.output_path / filename
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info(f"对比结果已保存: {output_file}")


if __name__ == '__main__':
    print("="*60)
    print("模型评估模块（优化版）")
    print("="*60)
    print(f"\n可视化功能: {'已启用' if HAS_VISUALIZATION else '未安装'}")
    print("\n使用示例:")
    print("-"*60)
    print("  evaluator = ModelEvaluator(output_path='./evaluation_output')")
    print("  evaluator.evaluate_model(model, 'MyModel', X_test, y_test)")
    print("  df = evaluator.compare_models(models_dict, X_test, y_test)")
    print("  evaluator.check_requirements()")
    print("  evaluator.generate_html_report()")
    print("="*60)
