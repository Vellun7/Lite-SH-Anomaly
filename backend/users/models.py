"""
用户模型
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """自定义用户模型"""
    
    # 扩展字段
    phone = models.CharField('手机号', max_length=11, blank=True, null=True, unique=True)
    avatar = models.URLField('头像URL', max_length=500, blank=True, null=True)
    role = models.CharField('角色', max_length=20, choices=[
        ('admin', '管理员'),
        ('user', '普通用户'),
        ('guest', '访客'),
    ], default='user')
    
    # 时间戳
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    last_login_ip = models.GenericIPAddressField('最后登录IP', blank=True, null=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = '用户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.username


class LoginLog(models.Model):
    """登录日志"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='login_logs', verbose_name='用户')
    ip_address = models.GenericIPAddressField('IP地址', blank=True, null=True)
    user_agent = models.CharField('User-Agent', max_length=500, blank=True, null=True)
    login_time = models.DateTimeField('登录时间', auto_now_add=True)
    status = models.CharField('状态', max_length=20, choices=[
        ('success', '成功'),
        ('failed', '失败'),
    ], default='success')
    fail_reason = models.CharField('失败原因', max_length=200, blank=True, null=True)

    class Meta:
        db_table = 'login_logs'
        verbose_name = '登录日志'
        verbose_name_plural = verbose_name
        ordering = ['-login_time']

    def __str__(self):
        return f'{self.user.username} - {self.login_time}'


class AuditLog(models.Model):
    """审计日志 - 记录用户所有操作行为，支持安全审计"""
    
    # 操作类型
    ACTION_CHOICES = [
        ('login', '登录'),
        ('logout', '登出'),
        ('create', '创建'),
        ('update', '更新'),
        ('delete', '删除'),
        ('view', '查看'),
        ('export', '导出'),
        ('import', '导入'),
        ('start', '启动'),
        ('stop', '停止'),
        ('config', '配置'),
        ('other', '其他'),
    ]
    
    # 资源类型
    RESOURCE_CHOICES = [
        ('user', '用户'),
        ('device', '设备'),
        ('device_group', '设备分组'),
        ('detection_task', '检测任务'),
        ('detection_result', '检测结果'),
        ('system', '系统'),
        ('other', '其他'),
    ]
    
    # 操作结果
    RESULT_CHOICES = [
        ('success', '成功'),
        ('failed', '失败'),
        ('partial', '部分成功'),
    ]
    
    # 用户信息
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs', 
        verbose_name='操作用户'
    )
    username = models.CharField('用户名', max_length=150, blank=True, null=True)
    
    # 操作信息
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField('资源类型', max_length=30, choices=RESOURCE_CHOICES)
    resource_id = models.CharField('资源ID', max_length=100, blank=True, null=True)
    resource_name = models.CharField('资源名称', max_length=200, blank=True, null=True)
    
    # 操作详情
    description = models.TextField('操作描述', blank=True, null=True)
    request_path = models.CharField('请求路径', max_length=500, blank=True, null=True)
    request_method = models.CharField('请求方法', max_length=10, blank=True, null=True)
    request_data = models.TextField('请求数据', blank=True, null=True)
    response_code = models.IntegerField('响应状态码', blank=True, null=True)
    
    # 变更快照（用于审计追踪）
    old_value = models.TextField('变更前数据', blank=True, null=True)
    new_value = models.TextField('变更后数据', blank=True, null=True)
    
    # 操作结果
    result = models.CharField('操作结果', max_length=20, choices=RESULT_CHOICES, default='success')
    error_message = models.TextField('错误信息', blank=True, null=True)
    
    # 客户端信息
    ip_address = models.GenericIPAddressField('IP地址', blank=True, null=True)
    user_agent = models.CharField('User-Agent', max_length=500, blank=True, null=True)
    
    # 时间戳
    created_at = models.DateTimeField('操作时间', auto_now_add=True, db_index=True)
    
    # 会话追踪
    session_id = models.CharField('会话ID', max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = '审计日志'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['resource_type', 'created_at']),
            models.Index(fields=['result', 'created_at']),
        ]

    def __str__(self):
        return f'{self.username or "匿名"} - {self.get_action_display()} - {self.get_resource_type_display()} - {self.created_at}'
    
    @classmethod
    def log(cls, user=None, action='other', resource_type='other', resource_id=None,
            resource_name=None, description=None, request=None, result='success',
            error_message=None, old_value=None, new_value=None):
        """
        记录审计日志的便捷方法
        
        :param user: 用户对象
        :param action: 操作类型
        :param resource_type: 资源类型
        :param resource_id: 资源ID
        :param resource_name: 资源名称
        :param description: 操作描述
        :param request: HTTP请求对象
        :param result: 操作结果
        :param error_message: 错误信息
        :param old_value: 变更前数据
        :param new_value: 变更后数据
        :return: AuditLog实例
        """
        import json
        
        # 处理user参数：支持用户对象或字符串
        if isinstance(user, str):
            # 如果是字符串，直接作为username使用
            user_obj = None
            username = user
        else:
            user_obj = user
            username = user.username if user else None
        
        log_data = {
            'user': user_obj,
            'username': username,
            'action': action,
            'resource_type': resource_type,
            'resource_id': str(resource_id) if resource_id else None,
            'resource_name': resource_name,
            'description': description,
            'result': result,
            'error_message': error_message,
            'old_value': json.dumps(old_value, ensure_ascii=False, default=str) if old_value else None,
            'new_value': json.dumps(new_value, ensure_ascii=False, default=str) if new_value else None,
        }
        
        if request:
            log_data['request_path'] = request.path
            log_data['request_method'] = request.method
            log_data['ip_address'] = cls._get_client_ip(request)
            log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
            log_data['session_id'] = request.session.session_key if hasattr(request, 'session') else None
            
            # 记录请求数据（排除敏感信息）
            try:
                request_data = dict(request.data) if hasattr(request, 'data') else {}
                # 移除敏感字段
                sensitive_fields = ['password', 'old_password', 'new_password', 'confirm_password', 'token']
                for field in sensitive_fields:
                    request_data.pop(field, None)
                log_data['request_data'] = json.dumps(request_data, ensure_ascii=False, default=str)
            except Exception:
                log_data['request_data'] = None
        
        return cls.objects.create(**log_data)
    
    @staticmethod
    def _get_client_ip(request):
        """获取客户端IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip