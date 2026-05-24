"""
算法模型管理 - 序列化器层
提供数据验证和序列化功能
"""

from rest_framework import serializers
from .models import AlgorithmModel, TrainingTask, EvaluationResult, FeatureImportance


class AlgorithmModelSerializer(serializers.ModelSerializer):
    """算法模型序列化器"""
    
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = AlgorithmModel
        fields = [
            'id', 'model_id', 'model_name', 'model_type', 'model_type_display',
            'version', 'status', 'status_display', 'is_active',
            'training_dataset', 'training_params', 'training_samples', 'validation_samples',
            'f1_score', 'precision', 'recall', 'accuracy', 'auc_roc',
            'false_positive_rate', 'false_negative_rate',
            'inference_time_ms', 'memory_usage_mb', 'model_size_mb',
            'model_path', 'created_at', 'updated_at', 'trained_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AlgorithmModelCreateSerializer(serializers.ModelSerializer):
    """算法模型创建序列化器"""
    
    class Meta:
        model = AlgorithmModel
        fields = ['id', 'model_name', 'model_type', 'version', 'training_dataset', 'training_params']
    
    def create(self, validated_data):
        # 生成唯一的 model_id
        import uuid
        validated_data['model_id'] = f"model_{uuid.uuid4().hex[:8]}"
        return super().create(validated_data)


class AlgorithmModelUpdateSerializer(serializers.ModelSerializer):
    """算法模型更新序列化器"""
    
    model_name = serializers.CharField(required=False)  # 更新时可选
    
    class Meta:
        model = AlgorithmModel
        fields = ['model_name', 'version', 'status', 'is_active', 'training_params']
    
    def validate_is_active(self, value):
        """验证激活状态"""
        if value and self.instance and self.instance.status != 'ready':
            raise serializers.ValidationError('只有就绪状态的模型才能激活')
        return value


class TrainingTaskSerializer(serializers.ModelSerializer):
    """训练任务序列化器"""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    model_name = serializers.CharField(source='model.model_name', read_only=True)
    
    class Meta:
        model = TrainingTask
        fields = [
            'id', 'task_id', 'model', 'model_name', 'status', 'status_display',
            'progress', 'config', 'result_metrics', 'error_message',
            'training_log', 'created_at', 'started_at', 'completed_at'
        ]
        read_only_fields = ['id', 'task_id', 'created_at']


class TrainingTaskCreateSerializer(serializers.ModelSerializer):
    """训练任务创建序列化器"""
    
    class Meta:
        model = TrainingTask
        fields = ['model', 'config']
    
    def create(self, validated_data):
        import uuid
        validated_data['task_id'] = f"task_{uuid.uuid4().hex[:8]}"
        validated_data['status'] = 'pending'
        return super().create(validated_data)


class EvaluationResultSerializer(serializers.ModelSerializer):
    """评估结果序列化器"""
    
    model_name = serializers.CharField(source='model.model_name', read_only=True)
    
    class Meta:
        model = EvaluationResult
        fields = ['id', 'model', 'model_name', 'task', 'metrics', 'evaluation_dataset', 'evaluation_samples', 'created_at']
        read_only_fields = ['id', 'created_at']


class FeatureImportanceSerializer(serializers.ModelSerializer):
    """特征重要性序列化器"""
    
    class Meta:
        model = FeatureImportance
        fields = ['id', 'model', 'feature_name', 'importance_score', 'rank']
        read_only_fields = ['id']
