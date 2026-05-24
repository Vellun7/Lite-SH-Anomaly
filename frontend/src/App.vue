<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from './components/layout/AppLayout.vue'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()

// 初始化主题（会自动从 localStorage 读取并应用到 DOM）
useThemeStore()

// 登录页不使用布局
const showLayout = computed(() => {
  return route.name !== 'login'
})
</script>

<template>
  <AppLayout v-if="showLayout">
    <transition name="page" mode="out-in">
      <RouterView :key="route.path" />
    </transition>
  </AppLayout>
  <transition name="page" mode="out-in">
    <RouterView v-if="!showLayout" :key="route.path" />
  </transition>
</template>

<style scoped>
</style>
