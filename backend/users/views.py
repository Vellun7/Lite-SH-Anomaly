"""
用户视图
"""
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter

from .models import User, LoginLog, AuditLog
from .serializers import (
    UserRegisterSerializer,
    UserLoginSerializer,
    UserInfoSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
    LoginLogSerializer,
    TokenResponseSerializer,
    AuditLogSerializer,
    AuditLogDetailSerializer,
)


def get_client_ip(request):
    """获取客户端IP"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@extend_schema_view(
    register=extend_schema(
        tags=['认证'],
        summary='用户注册',
        description='注册新用户账号',
        request=UserRegisterSerializer,
        responses={
            201: OpenApiResponse(response=TokenResponseSerializer, description='注册成功'),
            400: OpenApiResponse(description='参数错误'),
        }
    ),
    login=extend_schema(
        tags=['认证'],
        summary='用户登录',
        description='使用用户名密码登录，返回JWT令牌',
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(response=TokenResponseSerializer, description='登录成功'),
            400: OpenApiResponse(description='用户名或密码错误'),
        }
    ),
    logout=extend_schema(
        tags=['认证'],
        summary='用户登出',
        description='登出当前用户，使刷新令牌失效',
        responses={
            200: OpenApiResponse(description='登出成功'),
        }
    ),
    me=extend_schema(
        tags=['用户'],
        summary='获取当前用户信息',
        description='获取当前登录用户的详细信息',
        responses={
            200: OpenApiResponse(response=UserInfoSerializer, description='成功'),
            401: OpenApiResponse(description='未登录'),
        }
    ),
    update_profile=extend_schema(
        tags=['用户'],
        summary='更新用户信息',
        description='更新当前用户的个人信息',
        request=UserUpdateSerializer,
        responses={
            200: OpenApiResponse(response=UserInfoSerializer, description='更新成功'),
            400: OpenApiResponse(description='参数错误'),
        }
    ),
    change_password=extend_schema(
        tags=['用户'],
        summary='修改密码',
        description='修改当前用户的登录密码',
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description='修改成功'),
            400: OpenApiResponse(description='参数错误'),
        }
    ),
)
class AuthViewSet(viewsets.GenericViewSet):
    """认证视图集"""
    
    queryset = User.objects.all()
    serializer_class = UserInfoSerializer
    
    def get_permissions(self):
        if self.action in ['register', 'login']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """用户注册"""
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # 生成JWT令牌
        refresh = RefreshToken.for_user(user)
        
        # 记录审计日志
        AuditLog.log(
            user=user,
            action='create',
            resource_type='user',
            resource_id=user.id,
            resource_name=user.username,
            description=f'用户 {user.username} 注册成功',
            request=request,
            result='success'
        )
        
        return Response({
            'code': 0,
            'message': '注册成功',
            'data': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserInfoSerializer(user).data
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """用户登录"""
        serializer = UserLoginSerializer(data=request.data)
        
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            
            # 更新用户登录信息
            user.last_login = timezone.now()
            user.last_login_ip = ip_address
            user.save(update_fields=['last_login', 'last_login_ip'])
            
            # 记录登录日志
            LoginLog.objects.create(
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                status='success'
            )
            
            # 记录审计日志
            AuditLog.log(
                user=user,
                action='login',
                resource_type='user',
                resource_id=user.id,
                resource_name=user.username,
                description=f'用户 {user.username} 登录成功',
                request=request,
                result='success'
            )
            
            # 生成JWT令牌
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'code': 0,
                'message': '登录成功',
                'data': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': UserInfoSerializer(user).data
                }
            })
            
        except Exception as e:
            # 记录失败日志（如果能找到用户）
            username = request.data.get('username', '')
            try:
                user = User.objects.get(username=username)
                LoginLog.objects.create(
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status='failed',
                    fail_reason=str(e)
                )
                
                # 记录审计日志 - 登录失败
                AuditLog.log(
                    user=user,
                    action='login',
                    resource_type='user',
                    resource_id=user.id,
                    resource_name=user.username,
                    description=f'用户 {username} 登录失败',
                    request=request,
                    result='failed',
                    error_message=str(e)
                )
            except User.DoesNotExist:
                # 用户不存在时也记录审计日志
                AuditLog.log(
                    user=None,
                    action='login',
                    resource_type='user',
                    description=f'用户名 {username} 登录失败（用户不存在）',
                    request=request,
                    result='failed',
                    error_message='用户不存在'
                )
            raise
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """用户登出"""
        # 记录审计日志
        if request.user and request.user.is_authenticated:
            AuditLog.log(
                user=request.user,
                action='logout',
                resource_type='user',
                resource_id=request.user.id,
                resource_name=request.user.username,
                description=f'用户 {request.user.username} 登出',
                request=request,
                result='success'
            )
        
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception:
            pass
        
        return Response({
            'code': 0,
            'message': '登出成功'
        })
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """获取当前用户信息"""
        serializer = UserInfoSerializer(request.user)
        return Response({
            'code': 0,
            'message': 'success',
            'data': serializer.data
        })
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """更新用户信息"""
        old_data = {
            'email': request.user.email,
            'phone': request.user.phone,
            'avatar': request.user.avatar,
        }
        
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        new_data = {
            'email': request.user.email,
            'phone': request.user.phone,
            'avatar': request.user.avatar,
        }
        
        # 记录审计日志
        AuditLog.log(
            user=request.user,
            action='update',
            resource_type='user',
            resource_id=request.user.id,
            resource_name=request.user.username,
            description=f'用户 {request.user.username} 更新个人信息',
            request=request,
            result='success',
            old_value=old_data,
            new_value=new_data
        )
        
        return Response({
            'code': 0,
            'message': '更新成功',
            'data': UserInfoSerializer(request.user).data
        })
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """修改密码"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        
        # 记录审计日志
        AuditLog.log(
            user=request.user,
            action='update',
            resource_type='user',
            resource_id=request.user.id,
            resource_name=request.user.username,
            description=f'用户 {request.user.username} 修改密码',
            request=request,
            result='success'
        )
        
        return Response({
            'code': 0,
            'message': '密码修改成功'
        })


@extend_schema_view(
    list=extend_schema(
        tags=['用户'],
        summary='获取登录日志',
        description='获取当前用户的登录日志列表',
    ),
)
class LoginLogViewSet(viewsets.ReadOnlyModelViewSet):
    """登录日志视图集"""
    
    serializer_class = LoginLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LoginLog.objects.filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(
        tags=['审计日志'],
        summary='获取审计日志列表',
        description='获取用户操作审计日志列表，支持筛选和搜索',
        parameters=[
            OpenApiParameter(name='action', description='操作类型', type=str),
            OpenApiParameter(name='resource_type', description='资源类型', type=str),
            OpenApiParameter(name='result', description='操作结果', type=str),
            OpenApiParameter(name='username', description='用户名', type=str),
            OpenApiParameter(name='start_time', description='开始时间', type=str),
            OpenApiParameter(name='end_time', description='结束时间', type=str),
            OpenApiParameter(name='search', description='搜索关键词', type=str),
        ],
    ),
    retrieve=extend_schema(
        tags=['审计日志'],
        summary='获取审计日志详情',
        description='获取单条审计日志的详细信息',
    ),
    statistics=extend_schema(
        tags=['审计日志'],
        summary='获取审计日志统计',
        description='获取审计日志的统计数据',
    ),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """审计日志视图集"""
    
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'description', 'resource_name', 'ip_address']
    ordering_fields = ['created_at', 'action', 'resource_type']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = AuditLog.objects.all()
        
        # 非管理员只能查看自己的日志
        if self.request.user.role != 'admin':
            queryset = queryset.filter(user=self.request.user)
        
        # 筛选条件
        action = self.request.query_params.get('action')
        resource_type = self.request.query_params.get('resource_type')
        result = self.request.query_params.get('result')
        username = self.request.query_params.get('username')
        start_time = self.request.query_params.get('start_time')
        end_time = self.request.query_params.get('end_time')
        
        if action:
            queryset = queryset.filter(action=action)
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        if result:
            queryset = queryset.filter(result=result)
        if username:
            queryset = queryset.filter(username__icontains=username)
        if start_time:
            queryset = queryset.filter(created_at__gte=start_time)
        if end_time:
            queryset = queryset.filter(created_at__lte=end_time)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AuditLogDetailSerializer
        return AuditLogSerializer
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """获取审计日志统计数据"""
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        from datetime import timedelta
        
        queryset = self.get_queryset()
        
        # 最近7天的日志统计
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_queryset = queryset.filter(created_at__gte=seven_days_ago)
        
        # 按操作类型统计
        action_stats = list(recent_queryset.values('action').annotate(count=Count('id')))
        
        # 按资源类型统计
        resource_stats = list(recent_queryset.values('resource_type').annotate(count=Count('id')))
        
        # 按结果统计
        result_stats = list(recent_queryset.values('result').annotate(count=Count('id')))
        
        # 按日期统计
        daily_stats = list(
            recent_queryset
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .annotate(count=Count('id'))
            .order_by('date')
        )
        
        # 格式化日期
        for item in daily_stats:
            item['date'] = item['date'].strftime('%Y-%m-%d') if item['date'] else None
        
        return Response({
            'code': 0,
            'message': 'success',
            'data': {
                'total': queryset.count(),
                'recent_total': recent_queryset.count(),
                'action_stats': action_stats,
                'resource_stats': resource_stats,
                'result_stats': result_stats,
                'daily_stats': daily_stats,
            }
        })

    @extend_schema(
        tags=['审计日志'],
        summary='导出审计日志',
        description='导出审计日志为CSV文件',
    )
    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出审计日志"""
        import csv
        from django.http import HttpResponse
        
        queryset = self.get_queryset()
        
        # 限制导出数量，避免内存溢出
        max_export = 10000
        queryset = queryset[:max_export]
        
        # 创建CSV响应
        response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
        
        writer = csv.writer(response)
        
        # 写入表头
        headers = [
            '日志ID', '操作时间', '操作用户', '操作类型', '资源类型',
            '资源ID', '资源名称', '操作描述', 'IP地址', '操作结果', '错误信息'
        ]
        writer.writerow(headers)
        
        # 写入数据
        for log in queryset:
            row = [
                log.id,
                log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
                log.username or '匿名',
                log.get_action_display(),
                log.get_resource_type_display(),
                log.resource_id or '',
                log.resource_name or '',
                log.description or '',
                log.ip_address or '',
                log.get_result_display(),
                log.error_message or ''
            ]
            writer.writerow(row)
        
        # 记录审计日志
        AuditLog.log(
            user=request.user if request.user.is_authenticated else None,
            action='export',
            resource_type='other',
            resource_name='审计日志',
            description=f'导出审计日志，共 {len(queryset)} 条记录',
            request=request,
            result='success'
        )
        
        return response