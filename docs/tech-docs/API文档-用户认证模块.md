# 用户认证模块 API 文档

## 概述

本文档描述智能家居异常检测系统的用户认证相关接口，采用 JWT (JSON Web Token) 认证方式。

**Base URL**: `http://localhost:8000/api/v1`

**认证方式**: Bearer Token
```
Authorization: Bearer <access_token>
```

---

## 1. 用户注册

### POST `/auth/register/`

注册新用户账号，注册成功后自动返回登录令牌。

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，3-30位字母数字下划线 |
| password | string | 是 | 密码，6-128位 |
| confirm_password | string | 是 | 确认密码，需与password一致 |
| email | string | 否 | 邮箱地址 |
| phone | string | 否 | 手机号，11位 |

#### 请求示例

```json
{
  "username": "testuser",
  "password": "123456",
  "confirm_password": "123456",
  "email": "test@example.com",
  "phone": "13800138000"
}
```

#### 响应示例

**成功 (201)**
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
      "id": 1,
      "username": "testuser",
      "email": "test@example.com",
      "phone": "13800138000",
      "avatar": null,
      "role": "user",
      "is_active": true,
      "date_joined": "2025-12-12 17:00:00",
      "last_login": null,
      "created_at": "2025-12-12 17:00:00"
    }
  }
}
```

**失败 (400)**
```json
{
  "username": ["用户名已存在"]
}
```

---

## 2. 用户登录

### POST `/auth/login/`

使用用户名和密码登录，返回 JWT 令牌。

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

#### 请求示例

```json
{
  "username": "testuser",
  "password": "123456"
}
```

#### 响应示例

**成功 (200)**
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": {
      "id": 1,
      "username": "testuser",
      "email": "test@example.com",
      "phone": "13800138000",
      "avatar": null,
      "role": "user",
      "is_active": true,
      "date_joined": "2025-12-12 17:00:00",
      "last_login": "2025-12-12 17:30:00",
      "created_at": "2025-12-12 17:00:00"
    }
  }
}
```

**失败 (400)**
```json
{
  "non_field_errors": ["用户名或密码错误"]
}
```

---

## 3. 刷新令牌

### POST `/auth/token/refresh/`

使用刷新令牌获取新的访问令牌。

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refresh | string | 是 | 刷新令牌 |

#### 请求示例

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### 响应示例

**成功 (200)**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

---

## 4. 用户登出

### POST `/auth/logout/`

登出当前用户，使刷新令牌失效。

**需要认证**: 是

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| refresh | string | 否 | 刷新令牌（用于加入黑名单） |

#### 请求示例

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### 响应示例

**成功 (200)**
```json
{
  "code": 0,
  "message": "登出成功"
}
```

---

## 5. 获取当前用户信息

### GET `/auth/me/`

获取当前登录用户的详细信息。

**需要认证**: 是

#### 响应示例

**成功 (200)**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "phone": "13800138000",
    "avatar": null,
    "role": "user",
    "is_active": true,
    "date_joined": "2025-12-12 17:00:00",
    "last_login": "2025-12-12 17:30:00",
    "created_at": "2025-12-12 17:00:00"
  }
}
```

**未登录 (401)**
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

## 6. 更新用户信息

### PUT/PATCH `/auth/update_profile/`

更新当前用户的个人信息。

**需要认证**: 是

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 否 | 邮箱地址 |
| phone | string | 否 | 手机号 |
| avatar | string | 否 | 头像URL |

#### 请求示例

```json
{
  "email": "newemail@example.com",
  "avatar": "https://example.com/avatar.jpg"
}
```

#### 响应示例

**成功 (200)**
```json
{
  "code": 0,
  "message": "更新成功",
  "data": {
    "id": 1,
    "username": "testuser",
    "email": "newemail@example.com",
    "phone": "13800138000",
    "avatar": "https://example.com/avatar.jpg",
    "role": "user",
    "is_active": true,
    "date_joined": "2025-12-12 17:00:00",
    "last_login": "2025-12-12 17:30:00",
    "created_at": "2025-12-12 17:00:00"
  }
}
```

---

## 7. 修改密码

### POST `/auth/change_password/`

修改当前用户的登录密码。

**需要认证**: 是

#### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码，至少6位 |
| confirm_password | string | 是 | 确认新密码 |

#### 请求示例

```json
{
  "old_password": "123456",
  "new_password": "newpassword",
  "confirm_password": "newpassword"
}
```

#### 响应示例

**成功 (200)**
```json
{
  "code": 0,
  "message": "密码修改成功"
}
```

**失败 (400)**
```json
{
  "old_password": ["原密码错误"]
}
```

---

## 8. 获取登录日志

### GET `/login-logs/`

获取当前用户的登录日志列表。

**需要认证**: 是

#### 查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码，默认1 |
| page_size | int | 每页数量，默认20 |

#### 响应示例

**成功 (200)**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "username": "testuser",
      "ip_address": "127.0.0.1",
      "user_agent": "Mozilla/5.0...",
      "login_time": "2025-12-12 17:30:00",
      "status": "success",
      "fail_reason": null
    }
  ]
}
```

---

## 令牌说明

### Access Token
- 有效期：2小时
- 用途：访问需要认证的接口
- 使用方式：放在请求头 `Authorization: Bearer <token>`

### Refresh Token
- 有效期：7天
- 用途：获取新的 Access Token
- 注意：刷新后会生成新的 Refresh Token，旧的失效

---

## 错误码说明

| HTTP状态码 | 说明 |
|------------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证/认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 前端对接示例 (Axios)

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 10000
})

// 请求拦截器 - 添加Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 - 处理Token过期
api.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const res = await axios.post('/api/v1/auth/token/refresh/', {
            refresh: refreshToken
          })
          localStorage.setItem('access_token', res.data.access)
          localStorage.setItem('refresh_token', res.data.refresh)
          // 重试原请求
          error.config.headers.Authorization = `Bearer ${res.data.access}`
          return api.request(error.config)
        } catch {
          // 刷新失败，跳转登录
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// API方法
export const authApi = {
  register: (data: any) => api.post('/auth/register/', data),
  login: (data: any) => api.post('/auth/login/', data),
  logout: (refresh: string) => api.post('/auth/logout/', { refresh }),
  getMe: () => api.get('/auth/me/'),
  updateProfile: (data: any) => api.patch('/auth/update_profile/', data),
  changePassword: (data: any) => api.post('/auth/change_password/', data),
}
```

---

## Swagger 文档

在线API文档地址：`http://localhost:8000/api/docs/`

可以在Swagger UI中直接测试所有接口。
