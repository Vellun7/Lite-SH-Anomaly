"""
审计中间件 - 自动记录用户所有操作
"""
import json
import logging
import re
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class AuditMiddleware(MiddlewareMixin):
    """
    审计中间件 - 自动记录用户的所有写操作
    
    记录范围：
    - POST/PUT/PATCH/DELETE 请求
    - 排除白名单中的路径（如健康检查、token刷新等）
    """
    
    # 不记录的请求路径（白名单）
    EXCLUDE_PATHS = [
        r'^/api/token/refresh/?$',  # token刷新
        r'^/api/health/?$',  # 健康检查
        r'^/admin/',  # Django admin
        r'^/api/docs/',  # API文档
        r'^/api/schema/',  # OpenAPI schema
        r'^/__debug__/',  # Django debug toolbar
        r'^/api/audit-logs/',  # 审计日志查询本身（避免循环）
    ]
    
    # 需要记录的请求方法
    AUDIT_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']
    
    # 只读操作路径（即使是POST也只记录为view操作）
    READ_ONLY_PATHS = [
        r'/statistics/?$',
        r'/search/?$',
        r'/export/?$',
        r'/list/?$',
    ]
    
    # URL到资源类型的映射
    RESOURCE_TYPE_MAP = {
        r'/api/auth/': 'user',
        r'/api/devices/': 'device',
        r'/api/device-groups/': 'device_group',
        r'/api/detection/': 'detection_task',
        r'/api/alerts/': 'detection_result',
        r'/api/users/': 'user',
    }
    
    # HTTP方法到操作类型的映射
    METHOD_ACTION_MAP = {
        'POST': 'create',
        'PUT': 'update',
        'PATCH': 'update',
        'DELETE': 'delete',
    }
    
    # 特殊路径到操作类型的映射
    PATH_ACTION_MAP = {
        r'/login/?$': 'login',
        r'/logout/?$': 'logout',
        r'/register/?$': 'create',
        r'/start/?$': 'start',
        r'/stop/?$': 'stop',
        r'/batch-delete/?$': 'delete',
        r'/batch-start/?$': 'start',
        r'/batch-stop/?$': 'stop',
        r'/config/?$': 'config',
        r'/export/?$': 'export',
        r'/import/?$': 'import',
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
        self._exclude_patterns = [re.compile(p) for p in self.EXCLUDE_PATHS]
        self._read_only_patterns = [re.compile(p) for p in self.READ_ONLY_PATHS]
        self._resource_patterns = [(re.compile(p), t) for p, t in self.RESOURCE_TYPE_MAP.items()]
        self._path_action_patterns = [(re.compile(p), a) for p, a in self.PATH_ACTION_MAP.items()]
    
    def __call__(self, request):
        # 处理请求前的逻辑
        response = self.get_response(request)
        
        # 处理请求后记录审计日志
        self._log_audit(request, response)
        
        return response
    
    def _should_audit(self, request):
        """判断是否需要记录审计日志"""
        # 只记录写操作
        if request.method not in self.AUDIT_METHODS:
            return False
        
        # 排除白名单路径
        path = request.path
        for pattern in self._exclude_patterns:
            if pattern.search(path):
                return False
        
        return True
    
    def _get_resource_type(self, path):
        """根据URL路径推断资源类型"""
        for pattern, resource_type in self._resource_patterns:
            if pattern.search(path):
                return resource_type
        return 'other'
    
    def _get_action(self, request):
        """根据请求方法和路径推断操作类型"""
        path = request.path
        
        # 先检查特殊路径
        for pattern, action in self._path_action_patterns:
            if pattern.search(path):
                return action
        
        # 再根据HTTP方法判断
        return self.METHOD_ACTION_MAP.get(request.method, 'other')
    
    def _get_resource_id(self, path):
        """从URL路径中提取资源ID"""
        # 匹配类似 /api/devices/123/ 或 /api/devices/123 的模式
        match = re.search(r'/(\d+)/?$', path)
        if match:
            return match.group(1)
        
        # 匹配UUID格式
        uuid_match = re.search(r'/([a-f0-9\-]{36})/?$', path, re.IGNORECASE)
        if uuid_match:
            return uuid_match.group(1)
        
        return None
    
    def _get_description(self, request, response, action, resource_type):
        """生成操作描述"""
        method = request.method
        path = request.path
        user = request.user.username if request.user and request.user.is_authenticated else '匿名用户'
        
        # 操作类型描述
        action_desc_map = {
            'login': '登录',
            'logout': '登出',
            'create': '创建',
            'update': '更新',
            'delete': '删除',
            'view': '查看',
            'export': '导出',
            'import': '导入',
            'start': '启动',
            'stop': '停止',
            'config': '配置',
            'other': '操作',
        }
        action_desc = action_desc_map.get(action, '操作')
        
        # 资源类型描述
        resource_desc_map = {
            'user': '用户',
            'device': '设备',
            'device_group': '设备分组',
            'detection_task': '检测任务',
            'detection_result': '检测结果',
            'system': '系统',
            'other': '资源',
        }
        resource_desc = resource_desc_map.get(resource_type, '资源')
        
        # 组装描述
        resource_id = self._get_resource_id(path)
        if resource_id:
            return f'{user} {action_desc}了{resource_desc} (ID: {resource_id})'
        else:
            return f'{user} 执行了{resource_desc}{action_desc}操作'
    
    def _log_audit(self, request, response):
        """记录审计日志"""
        if not self._should_audit(request):
            return
        
        # 避免导入循环
        from users.models import AuditLog
        
        try:
            path = request.path
            action = self._get_action(request)
            resource_type = self._get_resource_type(path)
            
            # 获取用户
            user = None
            if request.user and request.user.is_authenticated:
                user = request.user
            
            # 判断操作结果
            status_code = response.status_code
            if 200 <= status_code < 300:
                result = 'success'
            elif 400 <= status_code < 500:
                result = 'failed'
            else:
                result = 'failed'
            
            # 获取错误信息
            error_message = None
            if result == 'failed':
                try:
                    if hasattr(response, 'content'):
                        content = json.loads(response.content.decode('utf-8'))
                        error_message = content.get('message') or content.get('detail') or str(content)
                except Exception:
                    error_message = f'HTTP {status_code}'
            
            # 获取请求数据（排除敏感信息）
            request_data = None
            try:
                if hasattr(request, 'body') and request.body:
                    data = json.loads(request.body.decode('utf-8'))
                    # 移除敏感字段
                    sensitive_fields = [
                        'password', 'old_password', 'new_password', 
                        'confirm_password', 'token', 'access', 'refresh'
                    ]
                    for field in sensitive_fields:
                        data.pop(field, None)
                    request_data = json.dumps(data, ensure_ascii=False, default=str)
            except Exception:
                pass
            
            # 生成描述
            description = self._get_description(request, response, action, resource_type)
            
            # 获取资源ID和名称
            resource_id = self._get_resource_id(path)
            resource_name = None
            
            # 尝试从请求数据中提取名称
            try:
                if hasattr(request, 'body') and request.body:
                    data = json.loads(request.body.decode('utf-8'))
                    resource_name = data.get('name') or data.get('username') or data.get('title')
            except Exception:
                pass
            
            # 获取客户端信息
            ip_address = self._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            
            # 创建审计日志
            AuditLog.objects.create(
                user=user,
                username=user.username if user else None,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                description=description,
                request_path=path,
                request_method=request.method,
                request_data=request_data,
                response_code=status_code,
                result=result,
                error_message=error_message,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
        except Exception as e:
            # 记录日志失败不应影响正常业务
            logger.error(f'记录审计日志失败: {str(e)}')
    
    @staticmethod
    def _get_client_ip(request):
        """获取客户端IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
