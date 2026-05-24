/**
 * 主题状态管理
 */
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  // 从 localStorage 读取，默认暗色
  const saved = localStorage.getItem('theme_mode') as ThemeMode | null
  const mode = ref<ThemeMode>(saved || 'dark')

  // 是否为暗色模式
  const isDark = () => mode.value === 'dark'

  // 应用主题到 DOM
  const applyTheme = () => {
    const html = document.documentElement
    html.setAttribute('data-theme', mode.value)

    // 同步 body 背景色，防止切换时闪烁
    document.body.style.background = mode.value === 'dark' ? '#0f1117' : '#f0f2f5'
  }

  // 切换主题
  const toggleTheme = () => {
    mode.value = mode.value === 'dark' ? 'light' : 'dark'
  }

  // 设置指定主题
  const setTheme = (newMode: ThemeMode) => {
    mode.value = newMode
  }

  // 监听变化，自动持久化并应用
  watch(mode, (val) => {
    localStorage.setItem('theme_mode', val)
    applyTheme()
  }, { immediate: true })

  return {
    mode,
    isDark,
    toggleTheme,
    setTheme,
    applyTheme
  }
})
