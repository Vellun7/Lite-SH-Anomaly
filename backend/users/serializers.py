"""
用户序列化器
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, LoginLog, AuditLog


class UserRegisterSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    
    password = serializers.CharField(
        write_only=True, 
        min_length=6, 
        max_length=128,
        help_text='密码，6-128位'
    )
    confirm_password = serializers.CharField(
        write_only=True,
        help_text='确认密码'
    )
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'password', 'confirm_password']
        extra_kwargs = {
            'username': {'help_text': '用户名，3-30位字母数字下划线'},
            'email': {'required': False, 'help_text': '邮箱地址'},
            'phone': {'required': False, 'help_text': '手机号'},
        }
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('用户名已存在')
        if len(value) < 3:
            raise serializers.ValidationError('用户名至少3个字符')
        return value
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': '两次密码不一致'})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserLoginSerializer(serializers.Serializer):
    """用户登录序列化器"""
    
    username = serializers.CharField(help_text='用户名')
    password = serializers.CharField(write_only=True, help_text='密码')
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('用户名或密码错误')
            if not user.is_active:
                raise serializers.ValidationError('用户已被禁用')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('请输入用户名和密码')
        
        return attrs


class UserInfoSerializer(serializers.ModelSerializer):
    """用户信息序列化器"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'avatar', 'role', 
                  'is_active', 'date_joined', 'last_login', 'created_at']
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined', 
                           'last_login', 'created_at']


class UserUpdateSerializer(serializers.ModelSerializer):
    """用户信息更新序列化器"""
    
    class Meta:
        model = User
        fields = ['email', 'phone', 'avatar']
        extra_kwargs = {
            'email': {'required': False},
            'phone': {'required': False},
            'avatar': {'required': False},
        }


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码序列化器"""
    
    old_password = serializers.CharField(write_only=True, help_text='原密码')
    new_password = serializers.CharField(write_only=True, min_length=6, help_text='新密码，至少6位')
    confirm_password = serializers.CharField(write_only=True, help_text='确认新密码')
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('原密码错误')
        return value
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': '两次密码不一致'})
        return attrs


class LoginLogSerializer(serializers.ModelSerializer):
    """登录日志序列化器"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = LoginLog
        fields = ['id', 'username', 'ip_address', 'user_agent', 'login_time', 'status', 'fail_reason']


class TokenResponseSerializer(serializers.Serializer):
    """Token响应序列化器（用于文档）"""
    
    access = serializers.CharField(help_text='访问令牌')
    refresh = serializers.CharField(help_text='刷新令牌')
    user = UserInfoSerializer(help_text='用户信息')


class AuditLogSerializer(serializers.ModelSerializer):
    """审计日志序列化器"""
    
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    resource_type_display = serializers.CharField(source='get_resource_type_display', read_only=True)
    result_display = serializers.CharField(source='get_result_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id',
            'username',
            'action',
            'action_display',
            'resource_type',
            'resource_type_display',
            'resource_id',
            'resource_name',
            'description',
            'request_path',
            'request_method',
            'result',
            'result_display',
            'error_message',
            'ip_address',
            'user_agent',
            'created_at',
            'old_value',
            'new_value',
        ]
        read_only_fields = fields


class AuditLogDetailSerializer(AuditLogSerializer):
    """审计日志详情序列化器（包含完整数据）"""
    
    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + ['request_data', 'session_id']