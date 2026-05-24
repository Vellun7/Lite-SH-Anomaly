"""
算法模型管理 - 数据模型层
定义算法模型、训练任务、评估结果等数据模型
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class AlgorithmModel(models.Model):
    """算法模型模型"""
    
    class ModelType(models.TextChoices):
        ISOLATION_FOREST = 'isolation_forest', '孤立森林'
        AUTOENCODER = 'autoencoder', '自编码器'
        KNN = 'knn', 'K近邻'
        SVM = 'svm', '支持向量机'
        ENSEMBLE = 'ensemble', '集成模型'
        LSTM = 'lstm', 'LSTM'
        GRU = 'gru', 'GRU'
    
    class ModelStatus(models.TextChoices):
        TRAINING = 'training', '训练中'
        READY = 'ready', '就绪'
        DEPLOYED = 'deployed', '已部署'
        ARCHIVED = 'archived', '已归档'
        FAILED = 'failed', '训练失败'
    
    # 基础信息
    model_id = models.CharField('模型ID', max_length=64, unique=True, db_index=True)
    model_name = models.CharField('模型名称', max_length=128)
    model_type = models.CharField('模型类型', max_length=32, choices=ModelType.choices, db_index=True)
    version = models.CharField('版本号', max_length=32, default='v1.0')
    
    # 状态信息
    status = models.CharField('状态', max_length=20, choices=ModelStatus.choices, default=ModelStatus.TRAINING, db_index=True)
    is_active = models.BooleanField('是否当前激活模型', default=False, db_index=True)
    
    # 训练信息
    training_dataset = models.CharField('训练数据集', max_length=256, null=True, blank=True)
    training_params = models.JSONField('训练参数', default=dict, blank=True, help_text='训练参数字典，用于判断是否为相同配置的模型')
    training_samples = models.IntegerField('训练样本数', default=0)
    validation_samples = models.IntegerField('验证样本数', default=0)
    
    # 性能指标
    f1_score = models.FloatField('F1分数', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    precision = models.FloatField('精确率', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    recall = models.FloatField('召回率', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    accuracy = models.FloatField('准确率', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    auc_roc = models.FloatField('AUC-ROC', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # 错误率指标
    false_positive_rate = models.FloatField('误报率', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    false_negative_rate = models.FloatField('漏报率', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    # 性能指标
    inference_time_ms = models.FloatField('推理时间(ms)', default=0.0)
    memory_usage_mb = models.FloatField('内存占用(MB)', default=0.0)
    model_size_mb = models.FloatField('模型大小(MB)', default=0.0)
    
    # 文件路径
    model_path = models.CharField('模型文件路径', max_length=512, null=True, blank=True)
    
    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    trained_at = models.DateTimeField('训练完成时间', null=True, blank=True)
    
    class Meta:
        db_table = 'algorithm_models'
        verbose_name = '算法模型'
        verbose_name_plural = '算法模型'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_type', 'status']),
            models.Index(fields=['is_active', 'status']),
        ]
    
    def __str__(self):
        return f'{self.model_name} ({self.model_id}) - {self.get_status_display()}'
    
    def save(self, *args, **kwargs):
        """保存时确保只有一个激活模型"""
        if self.is_active:
            # 取消其他模型的激活状态
            AlgorithmModel.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class TrainingTask(models.Model):
    """训练任务模型"""
    
    class TaskStatus(models.TextChoices):
        PENDING = 'pending', '等待中'
        RUNNING = 'running', '运行中'
        COMPLETED = 'completed', '已完成'
        FAILED = 'failed', '失败'
        CANCELLED = 'cancelled', '已取消'
    
    task_id = models.CharField('任务ID', max_length=64, unique=True, db_index=True)
    model = models.ForeignKey(AlgorithmModel, on_delete=models.CASCADE, related_name='training_tasks', verbose_name='关联模型')
    
    status = models.CharField('状态', max_length=20, choices=TaskStatus.choices, default=TaskStatus.PENDING, db_index=True)
    progress = models.FloatField('进度(%)', default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    
    # 训练配置
    config = models.JSONField('训练配置', default=dict, blank=True)
    
    # 训练结果
    result_metrics = models.JSONField('结果指标', default=dict, blank=True)
    error_message = models.TextField('错误信息', null=True, blank=True)
    
    # 日志
    training_log = models.TextField('训练日志', null=True, blank=True)
    
    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    started_at = models.DateTimeField('开始时间', null=True, blank=True)
    completed_at = models.DateTimeField('完成时间', null=True, blank=True)
    
    class Meta:
        db_table = 'algorithm_training_tasks'
        verbose_name = '训练任务'
        verbose_name_plural = '训练任务'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f'训练任务 {self.task_id} - {self.get_status_display()}'


class EvaluationResult(models.Model):
    """评估结果模型"""
    
    model = models.ForeignKey(AlgorithmModel, on_delete=models.CASCADE, related_name='evaluations', verbose_name='关联模型')
    task = models.ForeignKey(TrainingTask, on_delete=models.SET_NULL, null=True, blank=True, related_name='evaluations', verbose_name='关联训练任务')
    
    # 评估指标
    metrics = models.JSONField('评估指标', default=dict, blank=True)
    
    # 评估数据集
    evaluation_dataset = models.CharField('评估数据集', max_length=256, null=True, blank=True)
    evaluation_samples = models.IntegerField('评估样本数', default=0)
    
    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    
    class Meta:
        db_table = 'algorithm_evaluation_results'
        verbose_name = '评估结果'
        verbose_name_plural = '评估结果'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.model.model_name} 评估结果 - {self.created_at.strftime("%Y-%m-%d %H:%M")}'


class FeatureImportance(models.Model):
    """特征重要性模型"""
    
    model = models.ForeignKey(AlgorithmModel, on_delete=models.CASCADE, related_name='feature_importances', verbose_name='关联模型')
    
    feature_name = models.CharField('特征名称', max_length=128, db_index=True)
    importance_score = models.FloatField('重要性分数', default=0.0)
    rank = models.IntegerField('排名', db_index=True)
    
    class Meta:
        db_table = 'algorithm_feature_importance'
        verbose_name = '特征重要性'
        verbose_name_plural = '特征重要性'
        ordering = ['model', 'rank']
        unique_together = ['model', 'feature_name']
    
    def __str__(self):
        return f'{self.model.model_name} - {self.feature_name} (排名{self.rank})'
