/**
 * 用户状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo } from '@/api/auth'
import { login as loginApi, register as registerApi, logout as logoutApi, getMe } from '@/api/auth'
import router from '@/router'
import { ElMessage } from 'element-plus'

export const useUserStore = defineStore('user', () => {
  // 状态
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const userInfo = ref<UserInfo | null>(
    localStorage.getItem('user_info') 
      ? JSON.parse(localStorage.getItem('user_info')!) 
      : null
  )

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.username || '')
  const isAdmin = computed(() => userInfo.value?.role === 'admin')

  // 登录
  async function login(username: string, password: string) {
    try {
      const res = await loginApi({ username, password })
      const { access, refresh, user } = res.data.data
      
      // 保存到状态和localStorage
      token.value = access
      refreshToken.value = refresh
      userInfo.value = user
      
      localStorage.setItem('access_token', access)
      localStorage.setItem('refresh_token', refresh)
      localStorage.setItem('user_info', JSON.stringify(user))
      
      ElMessage.success('登录成功')
      router.push('/')
      
      return true
    } catch (error: any) {
      const msg = error.response?.data?.non_field_errors?.[0] || '登录失败'
      ElMessage.error(msg)
      return false
    }
  }

  // 注册
  async function register(data: { 
    username: string
    password: string
    confirm_password: string
    email?: string
    phone?: string 
  }) {
    try {
      const res = await registerApi(data)
      
      ElMessage.success('注册成功，请登录')
      
      return true
    } catch (error: any) {
      const errors = error.response?.data
      if (errors) {
        const firstError = Object.values(errors)[0]
        ElMessage.error(Array.isArray(firstError) ? firstError[0] : String(firstError))
      } else {
        ElMessage.error('注册失败')
      }
      return false
    }
  }

  // 登出
  async function logout() {
    try {
      if (refreshToken.value) {
        await logoutApi(refreshToken.value)
      }
    } catch {
      // 忽略登出错误
    } finally {
      // 清除状态
      token.value = null
      refreshToken.value = null
      userInfo.value = null
      
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user_info')
      
      ElMessage.success('已退出登录')
      router.push('/login')
    }
  }

  // 获取用户信息
  async function fetchUserInfo() {
    try {
      const res = await getMe()
      userInfo.value = res.data.data
      localStorage.setItem('user_info', JSON.stringify(res.data.data))
      return true
    } catch {
      return false
    }
  }

  // 更新Token
  function updateToken(access: string, refresh?: string) {
    token.value = access
    localStorage.setItem('access_token', access)
    if (refresh) {
      refreshToken.value = refresh
      localStorage.setItem('refresh_token', refresh)
    }
  }

  return {
    token,
    refreshToken,
    userInfo,
    isLoggedIn,
    username,
    isAdmin,
    login,
    register,
    logout,
    fetchUserInfo,
    updateToken
  }
})
