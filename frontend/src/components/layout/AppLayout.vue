<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import GuideTour from '@/components/GuideTour.vue'
import DetectionStatusIndicator from '@/components/DetectionStatusIndicator.vue'
import {
  HomeFilled,
  Document,
  DataLine,
  Setting,
  SwitchButton,
  User,
  Sunny,
  Moon,
  Cpu,
  Notebook,
  QuestionFilled,
  Histogram
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const themeStore = useThemeStore()

// 引导组件引用
const guideTourRef = ref<InstanceType<typeof GuideTour>>()

// 重新开始引导
const restartTour = () => {
  guideTourRef.value?.resetTour()
}

const menuItems = [
  { path: '/', icon: HomeFilled, title: '安全概览', desc: '总览面板' },
  { path: '/devices', icon: Cpu, title: '设备管理', desc: '设备列表' },
  { path: '/history', icon: Document, title: '历史记录', desc: '检测日志' },
  { path: '/performance', icon: DataLine, title: '性能监控', desc: '系统指标' },
  { path: '/algorithm', icon: Histogram, title: '算法模型', desc: '模型管理' },
  { path: '/audit-logs', icon: Notebook, title: '操作日志', desc: '审计追踪' }
]

const navigateTo = (path: string) => {
  router.push(path)
}

const userInitial = computed(() => {
  return userStore.username?.charAt(0)?.toUpperCase() || 'U'
})

const currentPageDesc = computed(() => {
  const item = menuItems.find(m => m.path === route.path)
  return item?.desc || ''
})

const handleLogout = () => {
  userStore.logout()
}
</script>

<template>
  <el-container class="app-layout">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="sidebar">
      <!-- Logo 区域 -->
      <div class="logo-area">
        <div class="logo-icon-wrapper">
          <img src="@/assets/logo.svg" alt="Logo" class="logo-icon" />
        </div>
        <transition name="fade">
          <div class="logo-text-group">
            <span class="logo-text">SafeHome</span>
            <span class="logo-sub">Security Monitor</span>
          </div>
        </transition>
      </div>
      
      <!-- 导航菜单 -->
      <nav class="nav-menu">
        <div
          v-for="item in menuItems"
          :key="item.path"
          :class="['nav-item', { 'is-active': route.path === item.path }]"
          @click="navigateTo(item.path)"
        >
          <div class="nav-icon">
            <el-icon :size="20"><component :is="item.icon" /></el-icon>
          </div>
          <span class="nav-label">{{ item.title }}</span>
          <!-- 活跃指示器 -->
          <div v-if="route.path === item.path" class="active-indicator"></div>
        </div>
      </nav>

    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <!-- 顶部栏 -->
      <el-header class="header">
        <div class="header-left">
          <div class="page-title-group">
            <h2 class="page-title">{{ route.meta.title }}</h2>
            <span class="page-desc">{{ currentPageDesc }}</span>
          </div>
        </div>
        <div class="header-right">
          <!-- 检测状态指示器 -->
          <DetectionStatusIndicator />

          <div class="header-divider"></div>

          <!-- 主题切换按钮 -->
          <div class="theme-toggle" @click="themeStore.toggleTheme()" :title="themeStore.mode === 'dark' ? '切换到亮色模式' : '切换到暗色模式'">
            <transition name="theme-icon" mode="out-in">
              <el-icon v-if="themeStore.mode === 'dark'" :size="18" key="moon"><Moon /></el-icon>
              <el-icon v-else :size="18" key="sun"><Sunny /></el-icon>
            </transition>
          </div>

          <div class="header-divider"></div>

          <div class="icon-btn" title="通知">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
            </svg>
          </div>

          <div class="icon-btn help-btn" title="新手引导" @click="restartTour">
            <el-icon :size="18"><QuestionFilled /></el-icon>
          </div>
          
          <el-dropdown trigger="click">
            <div class="user-info">
              <div class="user-avatar">
                <span>{{ userInitial }}</span>
              </div>
              <div class="user-text" v-show="true">
                <span class="username">{{ userStore.username }}</span>
                <span class="user-role">管理员</span>
              </div>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="User" @click="router.push('/profile')">
                  个人信息
                </el-dropdown-item>
                <el-dropdown-item divided :icon="SwitchButton" @click="handleLogout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="main-content">
        <slot />
      </el-main>
    </el-container>

    <!-- 新手引导 -->
    <GuideTour ref="guideTourRef" />
  </el-container>
</template>

<style lang="scss" scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.theme-icon-enter-active,
.theme-icon-leave-active {
  transition: all 0.25s ease;
}
.theme-icon-enter-from {
  opacity: 0;
  transform: rotate(-90deg) scale(0.5);
}
.theme-icon-leave-to {
  opacity: 0;
  transform: rotate(90deg) scale(0.5);
}

.app-layout {
  height: 100vh;
  background: var(--bg-base);
}

// ==========================================
// 侧边栏
// ==========================================
.sidebar {
  background: var(--bg-surface);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  position: relative;
  z-index: 20;

  // 右边缘微光
  &::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 1px;
    background: linear-gradient(180deg, transparent, rgba(91, 141, 239, 0.15), transparent);
  }
}

.logo-area {
  height: 72px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 12px;
  border-bottom: 1px solid var(--border-color);

  .logo-icon-wrapper {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--primary-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 2px 10px rgba(91, 141, 239, 0.2);

    .logo-icon {
      width: 22px;
      height: 22px;
      filter: brightness(10);
    }
  }

  .logo-text-group {
    display: flex;
    flex-direction: column;
    white-space: nowrap;

    .logo-text {
      color: var(--text-primary);
      font-size: 16px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }

    .logo-sub {
      color: var(--text-muted);
      font-size: 10px;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }
  }
}

.nav-menu {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  color: var(--text-muted);

  .nav-icon {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
    background: transparent;
  }

  .nav-label {
    font-size: 14px;
    font-weight: 500;
    white-space: nowrap;
  }

  .active-indicator {
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 3px;
    height: 20px;
    background: var(--primary-color);
    border-radius: 0 3px 3px 0;
  }

  &:hover {
    color: var(--text-secondary);
    background: var(--bg-hover);

    .nav-icon {
      background: rgba(91, 141, 239, 0.08);
    }
  }

  &.is-active {
    color: var(--primary-color);
    background: rgba(91, 141, 239, 0.08);

    .nav-icon {
      background: rgba(91, 141, 239, 0.12);
      color: var(--primary-color);
    }

    .nav-label {
      font-weight: 600;
    }
  }
}



// ==========================================
// 主内容区
// ==========================================
.main-container {
  flex-direction: column;
  background: var(--bg-base);
}

.header {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 72px;
  z-index: 10;

  .header-left {
    .page-title-group {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
      letter-spacing: -0.3px;
    }

    .page-desc {
      font-size: 12px;
      color: var(--text-muted);
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;

    .system-status {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      background: rgba(94, 196, 158, 0.08);
      border-radius: 20px;
      border: 1px solid rgba(94, 196, 158, 0.15);

      .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--success-color);
        animation: pulse-soft 2s ease-in-out infinite;
      }

      .status-text {
        font-size: 12px;
        color: var(--success-color);
        font-weight: 500;
      }
    }

    .header-divider {
      width: 1px;
      height: 24px;
      background: var(--border-color);
    }

    .theme-toggle {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--text-muted);
      background: var(--bg-elevated);
      border: 1px solid var(--border-color);
      transition: all 0.3s ease;

      &:hover {
        color: var(--primary-color);
        background: var(--bg-hover);
        border-color: rgba(91, 141, 239, 0.3);
        transform: rotate(15deg);
      }

      &:active {
        transform: rotate(0deg) scale(0.95);
      }
    }

    .icon-btn {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      color: var(--text-muted);
      background: var(--bg-elevated);
      border: 1px solid var(--border-color);
      transition: all 0.2s ease;

      &:hover {
        color: var(--text-primary);
        background: var(--bg-hover);
        border-color: rgba(255, 255, 255, 0.12);
      }

      &.help-btn:hover {
        color: var(--primary-color);
        border-color: rgba(91, 141, 239, 0.3);
      }
    }

    .notification-badge {
      :deep(.el-badge__content) {
        background: var(--danger-color);
        border: none;
      }
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      padding: 6px 10px;
      border-radius: 10px;
      transition: background 0.2s;

      &:hover {
        background: var(--bg-hover);
      }

      .user-avatar {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: var(--primary-gradient);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 14px;
        font-weight: 600;
      }

      .user-text {
        display: flex;
        flex-direction: column;

        .username {
          font-size: 13px;
          font-weight: 500;
          color: var(--text-primary);
        }

        .user-role {
          font-size: 11px;
          color: var(--text-muted);
        }
      }
    }
  }
}

.main-content {
  padding: 24px 28px;
  overflow-y: auto;
  background: var(--bg-base);
}
</style>
