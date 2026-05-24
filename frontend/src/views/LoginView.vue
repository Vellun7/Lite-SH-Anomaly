<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import type { FormInstance, FormRules } from 'element-plus'

const userStore = useUserStore()
const themeStore = useThemeStore()
const activeTab = ref<'login' | 'register'>('login')
const loading = ref(false)
const formVisible = ref(false)

// 登录表单
const loginFormRef = ref<FormInstance>()
const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// 注册表单
const registerFormRef = ref<FormInstance>()
const registerForm = reactive({
  username: '',
  email: '',
  phone: '',
  password: '',
  confirm_password: ''
})

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 30, message: '用户名长度为3-30个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 登录
const handleLogin = async () => {
  const valid = await loginFormRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  await userStore.login(loginForm.username, loginForm.password)
  loading.value = false
}

// 注册
const handleRegister = async () => {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  const success = await userStore.register({
    username: registerForm.username,
    password: registerForm.password,
    confirm_password: registerForm.confirm_password,
    email: registerForm.email || undefined,
    phone: registerForm.phone || undefined
  })
  loading.value = false

  if (success) {
    registerFormRef.value?.resetFields()
    activeTab.value = 'login'
  }
}

// tab 切换时触发表单区域重新入场动画
const switchTab = (tab: 'login' | 'register') => {
  if (tab === activeTab.value) return
  formVisible.value = false
  activeTab.value = tab
  nextTick(() => {
    setTimeout(() => {
      formVisible.value = true
    }, 30)
  })
}

// ==========================================
// 粒子背景动画
// ==========================================
const canvasRef = ref<HTMLCanvasElement>()
let animationId: number

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  opacity: number
}

const getParticleColor = () => {
  return themeStore.isDark()
    ? { r: 91, g: 141, b: 239 }
    : { r: 60, g: 100, b: 200 }
}

const initParticles = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const resize = () => {
    canvas.width = canvas.offsetWidth * window.devicePixelRatio
    canvas.height = canvas.offsetHeight * window.devicePixelRatio
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio)
  }
  resize()
  window.addEventListener('resize', resize)

  const particles: Particle[] = []
  const count = 60
  const w = canvas.offsetWidth
  const h = canvas.offsetHeight

  for (let i = 0; i < count; i++) {
    particles.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 1.5 + 0.5,
      opacity: Math.random() * 0.3 + 0.1
    })
  }

  const maxDist = 120

  const animate = () => {
    ctx.clearRect(0, 0, w, h)

    particles.forEach(p => {
      p.x += p.vx
      p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1

      ctx.beginPath()
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(${getParticleColor().r}, ${getParticleColor().g}, ${getParticleColor().b}, ${p.opacity})`
      ctx.fill()
    })

    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x
        const dy = particles[i].y - particles[j].y
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < maxDist) {
          const alpha = (1 - dist / maxDist) * 0.08
          ctx.beginPath()
          ctx.moveTo(particles[i].x, particles[i].y)
          ctx.lineTo(particles[j].x, particles[j].y)
          ctx.strokeStyle = `rgba(${getParticleColor().r}, ${getParticleColor().g}, ${getParticleColor().b}, ${alpha})`
          ctx.lineWidth = 0.5
          ctx.stroke()
        }
      }
    }

    animationId = requestAnimationFrame(animate)
  }

  animate()
}

onMounted(() => {
  initParticles()
  setTimeout(() => {
    formVisible.value = true
  }, 100)
})

onUnmounted(() => {
  cancelAnimationFrame(animationId)
})

watch(() => themeStore.mode, () => {
  cancelAnimationFrame(animationId)
  initParticles()
})
</script>

<template>
  <div class="login-container">
    <!-- 粒子背景 -->
    <canvas ref="canvasRef" class="particle-canvas"></canvas>

    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-badge">
          <span class="badge-dot"></span>
          SECURITY SYSTEM
        </div>
        <h1>
          <span class="brand-line">智能家居</span>
          <span class="brand-line highlight">安全监控系统</span>
        </h1>
        <p class="brand-desc">
          轻量化异常检测引擎，为您的智能家居提供<br />全天候实时监控与智能预警保护
        </p>

        <!-- 分割线 -->
        <div class="brand-divider">
          <span class="divider-line"></span>
          <span class="divider-text">核心能力</span>
          <span class="divider-line"></span>
        </div>

        <!-- 特性列表 -->
        <div class="brand-features">
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon size="18"><Monitor /></el-icon>
            </div>
            <div class="feature-text">
              <span class="feature-title">全天候设备监控</span>
              <span class="feature-desc">7×24 小时不间断监控，设备状态实时可见</span>
            </div>
            <div class="feature-arrow">→</div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon size="18"><Warning /></el-icon>
            </div>
            <div class="feature-text">
              <span class="feature-title">AI 驱动异常检测</span>
              <span class="feature-desc">轻量化模型，毫秒级响应，精准识别异常行为</span>
            </div>
            <div class="feature-arrow">→</div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <el-icon size="18"><DataLine /></el-icon>
            </div>
            <div class="feature-text">
              <span class="feature-title">实时性能分析</span>
              <span class="feature-desc">多维度数据报告，趋势洞察一目了然</span>
            </div>
            <div class="feature-arrow">→</div>
          </div>
        </div>

        <!-- 底部统计 -->
        <div class="brand-stats">
          <div class="stat-item">
            <span class="stat-num">99.9%</span>
            <span class="stat-label">系统可用性</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">&lt;50ms</span>
            <span class="stat-label">检测响应</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">24/7</span>
            <span class="stat-label">持续监控</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="login-form-wrapper">
      <div class="login-form-container" :class="{ visible: formVisible }">
        <!-- 表单头部 -->
        <div class="form-header">
          <div class="logo-icon">
            <img src="@/assets/logo.svg" alt="Logo" class="logo" />
          </div>
          <transition name="header-text" mode="out-in">
            <div :key="activeTab" class="header-text-group">
              <h2>{{ activeTab === 'login' ? '欢迎回来' : '创建账号' }}</h2>
              <p>{{ activeTab === 'login' ? '登录以继续访问控制面板' : '注册后即可开始使用系统' }}</p>
            </div>
          </transition>
        </div>

        <!-- 自定义 Tab 切换器 -->
        <div class="custom-tabs">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'login' }"
            @click="switchTab('login')"
          >
            登录
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'register' }"
            @click="switchTab('register')"
          >
            注册
          </button>
          <div class="tab-indicator" :class="{ right: activeTab === 'register' }"></div>
        </div>

        <!-- 表单内容 -->
        <div class="form-body">
          <transition name="form-slide" mode="out-in">
            <!-- 登录表单 -->
            <el-form
              v-if="activeTab === 'login'"
              key="login"
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              size="large"
              @keyup.enter="handleLogin"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="loginForm.username"
                  placeholder="用户名"
                  :prefix-icon="User"
                />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  placeholder="密码"
                  :prefix-icon="Lock"
                  show-password
                />
              </el-form-item>
              <div class="form-options">
                <span class="forgot-link">忘记密码？</span>
              </div>
              <el-form-item class="submit-item">
                <button
                  class="submit-btn"
                  :class="{ loading }"
                  :disabled="loading"
                  @click.prevent="handleLogin"
                >
                  <span v-if="!loading" class="btn-text">登 录</span>
                  <span v-else class="btn-loading">
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                  </span>
                </button>
              </el-form-item>
            </el-form>

            <!-- 注册表单 -->
            <el-form
              v-else
              key="register"
              ref="registerFormRef"
              :model="registerForm"
              :rules="registerRules"
              size="large"
              @keyup.enter="handleRegister"
            >
              <el-form-item prop="username">
                <el-input
                  v-model="registerForm.username"
                  placeholder="用户名"
                  :prefix-icon="User"
                />
              </el-form-item>
              <el-form-item prop="email">
                <el-input
                  v-model="registerForm.email"
                  placeholder="邮箱（选填）"
                  :prefix-icon="Message"
                />
              </el-form-item>
              <el-form-item prop="phone">
                <el-input
                  v-model="registerForm.phone"
                  placeholder="手机号（选填）"
                  :prefix-icon="Phone"
                />
              </el-form-item>
              <el-form-item prop="password">
                <el-input
                  v-model="registerForm.password"
                  type="password"
                  placeholder="密码"
                  :prefix-icon="Lock"
                  show-password
                />
              </el-form-item>
              <el-form-item prop="confirm_password">
                <el-input
                  v-model="registerForm.confirm_password"
                  type="password"
                  placeholder="确认密码"
                  :prefix-icon="Lock"
                  show-password
                />
              </el-form-item>
              <el-form-item class="submit-item">
                <button
                  class="submit-btn"
                  :class="{ loading }"
                  :disabled="loading"
                  @click.prevent="handleRegister"
                >
                  <span v-if="!loading" class="btn-text">注 册</span>
                  <span v-else class="btn-loading">
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                    <span class="loading-dot"></span>
                  </span>
                </button>
              </el-form-item>
            </el-form>
          </transition>
        </div>

        <div class="form-footer">
          <span>© 2025 SafeHome Security Monitor</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { User, Lock, Message, Phone, Monitor, Warning, DataLine } from '@element-plus/icons-vue'
export default {
  components: { User, Lock, Message, Phone, Monitor, Warning, DataLine }
}
</script>

<style lang="scss" scoped>
// ==========================================
// 容器
// ==========================================
.login-container {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: var(--bg-base);
  position: relative;
}

.particle-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
}

// ==========================================
// 左侧品牌区
// ==========================================
.login-brand {
  flex: 1.1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 80px;
  position: relative;
  z-index: 1;

  .brand-content {
    width: 100%;
    max-width: 520px;
    animation: fadeInLeft 0.9s cubic-bezier(0.4, 0, 0.2, 1) both;
  }

  .brand-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 18px;
    background: rgba(91, 141, 239, 0.08);
    border: 1px solid rgba(91, 141, 239, 0.18);
    border-radius: 20px;
    color: var(--primary-color);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
    margin-bottom: 32px;

    .badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--primary-color);
      animation: pulse 2s ease-in-out infinite;
    }
  }

  h1 {
    margin-bottom: 20px;

    .brand-line {
      display: block;
      font-size: 54px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1.15;
      letter-spacing: -1.5px;

      &.highlight {
        background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
      }
    }
  }

  .brand-desc {
    font-size: 15px;
    color: var(--text-muted);
    line-height: 1.9;
    margin-bottom: 40px;
  }

  .brand-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;

    .divider-line {
      flex: 1;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(91, 141, 239, 0.2), transparent);
    }

    .divider-text {
      font-size: 11px;
      color: var(--text-disabled);
      letter-spacing: 2px;
      white-space: nowrap;
    }
  }

  .brand-features {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 36px;

    .feature-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 18px;
      border-radius: 14px;
      background: rgba(91, 141, 239, 0.04);
      border: 1px solid rgba(91, 141, 239, 0.08);
      cursor: default;
      transition: all 0.25s ease;
      animation: fadeInLeft 0.8s cubic-bezier(0.4, 0, 0.2, 1) both;

      &:nth-child(1) { animation-delay: 0.15s; }
      &:nth-child(2) { animation-delay: 0.25s; }
      &:nth-child(3) { animation-delay: 0.35s; }

      &:hover {
        background: rgba(91, 141, 239, 0.08);
        border-color: rgba(91, 141, 239, 0.2);
        transform: translateX(4px);
      }
    }

    .feature-icon {
      flex-shrink: 0;
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: rgba(91, 141, 239, 0.1);
      border: 1px solid rgba(91, 141, 239, 0.15);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--primary-color);
    }

    .feature-text {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 4px;

      .feature-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--text-primary);
      }

      .feature-desc {
        font-size: 13px;
        color: var(--text-muted);
        line-height: 1.5;
      }
    }

    .feature-arrow {
      font-size: 15px;
      color: var(--text-disabled);
      transition: all 0.25s ease;
    }

    .feature-item:hover .feature-arrow {
      color: var(--primary-color);
      transform: translateX(3px);
    }
  }

  .brand-stats {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 20px 28px;
    background: rgba(91, 141, 239, 0.04);
    border: 1px solid rgba(91, 141, 239, 0.1);
    border-radius: 16px;
    animation: fadeInLeft 0.8s cubic-bezier(0.4, 0, 0.2, 1) 0.45s both;

    .stat-item {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 5px;

      .stat-num {
        font-size: 22px;
        font-weight: 700;
        color: var(--primary-color);
        letter-spacing: -0.5px;
      }

      .stat-label {
        font-size: 12px;
        color: var(--text-muted);
      }
    }

    .stat-divider {
      width: 1px;
      height: 36px;
      background: rgba(91, 141, 239, 0.15);
    }
  }
}

// ==========================================
// 右侧表单区
// ==========================================
.login-form-wrapper {
  width: 600px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 1;
  padding: 40px;
}

.login-form-container {
  width: 100%;
  max-width: 480px;
  padding: 52px 48px;
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: 24px;
  box-shadow: 0 8px 48px rgba(0, 0, 0, 0.35), 0 1px 0 rgba(255, 255, 255, 0.05) inset;
  opacity: 0;
  transform: translateY(24px);
  transition: opacity 0.6s cubic-bezier(0.4, 0, 0.2, 1), transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);

  &.visible {
    opacity: 1;
    transform: translateY(0);
  }
}

// ==========================================
// 表单头部
// ==========================================
.form-header {
  text-align: center;
  margin-bottom: 32px;

  .logo-icon {
    width: 72px;
    height: 72px;
    margin: 0 auto 22px;
    border-radius: 20px;
    background: var(--primary-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 24px rgba(91, 141, 239, 0.3), 0 1px 0 rgba(255, 255, 255, 0.15) inset;

    .logo {
      width: 38px;
      height: 38px;
      filter: brightness(10);
    }
  }

  .header-text-group {
    h2 {
      font-size: 30px;
      font-weight: 700;
      color: var(--text-primary);
      margin-bottom: 10px;
    }

    p {
      font-size: 15px;
      color: var(--text-muted);
    }
  }
}

// ==========================================
// 自定义 Tab 切换器
// ==========================================
.custom-tabs {
  position: relative;
  display: flex;
  background: var(--bg-elevated);
  border-radius: 12px;
  padding: 4px;
  margin-bottom: 32px;
  border: 1px solid rgba(255, 255, 255, 0.05);

  .tab-btn {
    flex: 1;
    height: 42px;
    border: none;
    background: transparent;
    border-radius: 9px;
    font-size: 16px;
    font-weight: 500;
    color: var(--text-muted);
    cursor: pointer;
    position: relative;
    z-index: 1;
    transition: color 0.25s ease;

    &.active {
      color: var(--text-primary);
    }

    &:hover:not(.active) {
      color: var(--text-secondary);
    }
  }

  .tab-indicator {
    position: absolute;
    top: 4px;
    left: 4px;
    width: calc(50% - 4px);
    height: calc(100% - 8px);
    background: var(--glass-bg);
    border: 1px solid rgba(91, 141, 239, 0.15);
    border-radius: 9px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);

    &.right {
      transform: translateX(100%);
    }
  }
}

// ==========================================
// 表单内容
// ==========================================
.form-body {
  min-height: 200px;
}

// 表单切换动画
.form-slide-enter-active,
.form-slide-leave-active {
  transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}

.form-slide-enter-from {
  opacity: 0;
  transform: translateX(16px);
}

.form-slide-leave-to {
  opacity: 0;
  transform: translateX(-16px);
}

// 标题切换动画
.header-text-enter-active,
.header-text-leave-active {
  transition: all 0.22s ease;
}

.header-text-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.header-text-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

// ==========================================
// 表单选项行（忘记密码）
// ==========================================
.form-options {
  display: flex;
  justify-content: flex-end;
  margin: -8px 0 20px;

  .forgot-link {
    font-size: 13px;
    color: var(--primary-color);
    cursor: pointer;
    opacity: 0.8;
    transition: opacity 0.2s ease;

    &:hover {
      opacity: 1;
    }
  }
}

// ==========================================
// 提交按钮
// ==========================================
.submit-item {
  margin-bottom: 0 !important;
  margin-top: 4px;
}

.submit-btn {
  width: 100%;
  height: 52px;
  font-size: 17px;
  font-weight: 600;
  border-radius: 12px;
  background: var(--primary-gradient);
  border: none;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(91, 141, 239, 0.28);
  transition: all 0.25s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.5px;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0);
    transition: background 0.2s ease;
  }

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(91, 141, 239, 0.38);

    &::before {
      background: rgba(255, 255, 255, 0.06);
    }
  }

  &:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(91, 141, 239, 0.2);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }

  &.loading {
    pointer-events: none;
  }
}

// 加载点动画
.btn-loading {
  display: flex;
  align-items: center;
  gap: 5px;

  .loading-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.9);
    animation: dotBounce 1.2s ease-in-out infinite;

    &:nth-child(1) { animation-delay: 0s; }
    &:nth-child(2) { animation-delay: 0.2s; }
    &:nth-child(3) { animation-delay: 0.4s; }
  }
}

// ==========================================
// 输入框样式
// ==========================================
:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-input__wrapper) {
  background: var(--bg-elevated) !important;
  border-radius: 11px !important;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset !important;
  transition: all 0.22s ease;
  padding: 0 14px !important;

  &:hover {
    box-shadow: 0 0 0 1px rgba(91, 141, 239, 0.25) inset !important;
  }

  &.is-focus {
    box-shadow: 0 0 0 1.5px var(--primary-color) inset, 0 0 0 4px rgba(91, 141, 239, 0.08) !important;
  }

  .el-input__inner {
    color: var(--text-primary) !important;
    font-size: 15px !important;

    &::placeholder {
      color: var(--text-disabled) !important;
    }
  }

  .el-input__prefix .el-icon {
    color: var(--text-muted) !important;
    transition: color 0.2s ease;
  }
}

:deep(.el-input__wrapper.is-focus .el-input__prefix .el-icon) {
  color: var(--primary-color) !important;
}

// ==========================================
// 底部版权
// ==========================================
.form-footer {
  margin-top: 32px;
  text-align: center;
  font-size: 12px;
  color: var(--text-disabled);
  letter-spacing: 0.3px;
}

// ==========================================
// 动画关键帧
// ==========================================
@keyframes fadeInLeft {
  from {
    opacity: 0;
    transform: translateX(-24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(0.8);
  }
}

@keyframes dotBounce {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.6;
  }
  40% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

// ==========================================
// 响应式
// ==========================================
@media (max-width: 900px) {
  .login-brand {
    display: none;
  }

  .login-form-wrapper {
    width: 100%;
  }
}
</style>
