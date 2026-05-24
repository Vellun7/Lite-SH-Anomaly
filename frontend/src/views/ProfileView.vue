<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { updateProfile, changePassword, type UpdateProfileParams, type ChangePasswordParams } from '@/api/auth'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, Phone, Calendar, Clock } from '@element-plus/icons-vue'

const userStore = useUserStore()

// 用户信息
const userInfo = computed(() => userStore.userInfo)

// 编辑状态
const isEditingProfile = ref(false)
const isChangingPassword = ref(false)

// 表单数据
const profileForm = ref<UpdateProfileParams>({
  email: '',
  phone: ''
})

const passwordForm = ref<ChangePasswordParams>({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

// 加载状态
const profileLoading = ref(false)
const passwordLoading = ref(false)

// 初始化表单数据
const initProfileForm = () => {
  profileForm.value = {
    email: userInfo.value?.email || '',
    phone: userInfo.value?.phone || ''
  }
}

// 开始编辑资料
const startEditProfile = () => {
  initProfileForm()
  isEditingProfile.value = true
}

// 取消编辑资料
const cancelEditProfile = () => {
  isEditingProfile.value = false
  initProfileForm()
}

// 保存资料
const saveProfile = async () => {
  profileLoading.value = true
  try {
    await updateProfile(profileForm.value)
    await userStore.fetchUserInfo()
    ElMessage.success('资料更新成功')
    isEditingProfile.value = false
  } catch (error: any) {
    const msg = error.response?.data?.message || '更新失败'
    ElMessage.error(msg)
  } finally {
    profileLoading.value = false
  }
}

// 开始修改密码
const startChangePassword = () => {
  passwordForm.value = {
    old_password: '',
    new_password: '',
    confirm_password: ''
  }
  isChangingPassword.value = true
}

// 取消修改密码
const cancelChangePassword = () => {
  isChangingPassword.value = false
}

// 提交修改密码
const submitChangePassword = async () => {
  // 验证
  if (!passwordForm.value.old_password) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!passwordForm.value.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.value.new_password.length < 6) {
    ElMessage.warning('新密码至少需要6个字符')
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  passwordLoading.value = true
  try {
    await changePassword(passwordForm.value)
    ElMessage.success('密码修改成功')
    isChangingPassword.value = false
  } catch (error: any) {
    const msg = error.response?.data?.message || error.response?.data?.old_password?.[0] || '密码修改失败'
    ElMessage.error(msg)
  } finally {
    passwordLoading.value = false
  }
}

// 格式化日期
const formatDate = (dateStr: string | null | undefined) => {
  if (!dateStr) return '暂无'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取角色显示名
const getRoleName = (role: string | undefined) => {
  const roleMap: Record<string, string> = {
    admin: '管理员',
    user: '普通用户',
    guest: '访客'
  }
  return roleMap[role || ''] || role || '未知'
}

// 用户头像首字母
const userInitial = computed(() => {
  return userInfo.value?.username?.charAt(0)?.toUpperCase() || 'U'
})

onMounted(() => {
  initProfileForm()
})
</script>

<template>
  <div class="profile-view">
    <!-- 用户基本信息卡片 -->
    <div class="profile-card">
      <div class="card-header">
        <h3>
          <el-icon><User /></el-icon>
          个人信息
        </h3>
        <el-button 
          v-if="!isEditingProfile" 
          type="primary" 
          size="small"
          @click="startEditProfile"
        >
          编辑资料
        </el-button>
        <div v-else class="edit-actions">
          <el-button size="small" @click="cancelEditProfile">取消</el-button>
          <el-button 
            type="primary" 
            size="small" 
            :loading="profileLoading"
            @click="saveProfile"
          >
            保存
          </el-button>
        </div>
      </div>

      <div class="profile-content">
        <!-- 头像区域 -->
        <div class="avatar-section">
          <div class="avatar-large">
            <span>{{ userInitial }}</span>
          </div>
          <div class="user-basic">
            <h2 class="username">{{ userInfo?.username }}</h2>
            <el-tag :type="userInfo?.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ getRoleName(userInfo?.role) }}
            </el-tag>
          </div>
        </div>

        <!-- 信息列表 -->
        <div class="info-list">
          <div class="info-item">
            <div class="info-label">
              <el-icon><Message /></el-icon>
              邮箱
            </div>
            <div class="info-value">
              <template v-if="!isEditingProfile">
                {{ userInfo?.email || '未设置' }}
              </template>
              <el-input 
                v-else 
                v-model="profileForm.email" 
                placeholder="请输入邮箱"
                clearable
              />
            </div>
          </div>

          <div class="info-item">
            <div class="info-label">
              <el-icon><Phone /></el-icon>
              手机号
            </div>
            <div class="info-value">
              <template v-if="!isEditingProfile">
                {{ userInfo?.phone || '未设置' }}
              </template>
              <el-input 
                v-else 
                v-model="profileForm.phone" 
                placeholder="请输入手机号"
                clearable
              />
            </div>
          </div>

          <div class="info-item">
            <div class="info-label">
              <el-icon><Calendar /></el-icon>
              注册时间
            </div>
            <div class="info-value">
              {{ formatDate(userInfo?.date_joined || userInfo?.created_at) }}
            </div>
          </div>

          <div class="info-item">
            <div class="info-label">
              <el-icon><Clock /></el-icon>
              最后登录
            </div>
            <div class="info-value">
              {{ formatDate(userInfo?.last_login) }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 安全设置卡片 -->
    <div class="security-card">
      <div class="card-header">
        <h3>
          <el-icon><Lock /></el-icon>
          安全设置
        </h3>
      </div>

      <div class="security-content">
        <div class="security-item">
          <div class="security-info">
            <h4>登录密码</h4>
            <p>定期更换密码可以保护账户安全</p>
          </div>
          <el-button 
            v-if="!isChangingPassword"
            type="primary" 
            plain
            @click="startChangePassword"
          >
            修改密码
          </el-button>
        </div>

        <!-- 修改密码表单 -->
        <transition name="slide-fade">
          <div v-if="isChangingPassword" class="password-form">
            <el-form label-position="top">
              <el-form-item label="当前密码">
                <el-input 
                  v-model="passwordForm.old_password" 
                  type="password" 
                  placeholder="请输入当前密码"
                  show-password
                />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input 
                  v-model="passwordForm.new_password" 
                  type="password" 
                  placeholder="请输入新密码（至少6位）"
                  show-password
                />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input 
                  v-model="passwordForm.confirm_password" 
                  type="password" 
                  placeholder="请再次输入新密码"
                  show-password
                />
              </el-form-item>
              <div class="form-actions">
                <el-button @click="cancelChangePassword">取消</el-button>
                <el-button 
                  type="primary" 
                  :loading="passwordLoading"
                  @click="submitChangePassword"
                >
                  确认修改
                </el-button>
              </div>
            </el-form>
          </div>
        </transition>

        <div class="security-item">
          <div class="security-info">
            <h4>账户状态</h4>
            <p>当前账户状态正常</p>
          </div>
          <el-tag :type="userInfo?.is_active ? 'success' : 'danger'">
            {{ userInfo?.is_active ? '正常' : '已禁用' }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.profile-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.profile-card,
.security-card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  box-shadow: var(--shadow-light);
  overflow: hidden;
  animation: fadeInUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) both;

  &:nth-child(2) {
    animation-delay: 0.1s;
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-elevated);

  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;

    .el-icon {
      color: var(--primary-color);
    }
  }

  .edit-actions {
    display: flex;
    gap: 8px;
  }
}

// 个人信息内容
.profile-content {
  padding: 24px;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 32px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border-color);

  .avatar-large {
    width: 80px;
    height: 80px;
    border-radius: 20px;
    background: var(--primary-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 32px;
    font-weight: 700;
    box-shadow: 0 8px 24px rgba(91, 141, 239, 0.25);
  }

  .user-basic {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .username {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-primary);
      margin: 0;
    }
  }
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-item {
  display: flex;
  align-items: center;

  .info-label {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 120px;
    font-size: 14px;
    color: var(--text-muted);
    flex-shrink: 0;

    .el-icon {
      font-size: 16px;
    }
  }

  .info-value {
    flex: 1;
    font-size: 14px;
    color: var(--text-primary);

    .el-input {
      max-width: 300px;
    }
  }
}

// 安全设置内容
.security-content {
  padding: 24px;
}

.security-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;

  &:not(:last-child) {
    border-bottom: 1px solid var(--border-color);
  }

  .security-info {
    h4 {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0 0 4px 0;
    }

    p {
      font-size: 13px;
      color: var(--text-muted);
      margin: 0;
    }
  }
}

// 修改密码表单
.password-form {
  padding: 20px;
  margin: 16px 0;
  background: var(--bg-elevated);
  border-radius: 12px;
  border: 1px solid var(--border-color);

  :deep(.el-form-item) {
    margin-bottom: 16px;

    &:last-of-type {
      margin-bottom: 0;
    }

    .el-form-item__label {
      color: var(--text-secondary);
      font-size: 13px;
    }
  }

  :deep(.el-input) {
    max-width: 400px;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
}

// 动画
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}

.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

// 响应式
@media (max-width: 600px) {
  .avatar-section {
    flex-direction: column;
    text-align: center;
  }

  .info-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;

    .info-label {
      width: auto;
    }

    .info-value {
      width: 100%;

      .el-input {
        max-width: 100%;
      }
    }
  }

  .security-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .password-form :deep(.el-input) {
    max-width: 100%;
  }
}
</style>
