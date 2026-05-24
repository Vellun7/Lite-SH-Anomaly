import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { title: '登录', public: true }
    },
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
      meta: { title: '首页' }
    },

    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/HistoryView.vue'),
      meta: { title: '历史记录' }
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/views/DeviceManagementView.vue'),
      meta: { title: '设备管理' }
    },
    {
      path: '/performance',
      name: 'performance',
      component: () => import('@/views/PerformanceView.vue'),
      meta: { title: '性能监控' }
    },
    {
      path: '/audit-logs',
      name: 'audit-logs',
      component: () => import('@/views/AuditLogView.vue'),
      meta: { title: '操作日志' }
    },
    {
      path: '/algorithm',
      name: 'algorithm',
      component: () => import('@/views/AlgorithmModelsView.vue'),
      meta: { title: '算法模型' }
    },
    {
      path: '/algorithm/evaluation',
      name: 'algorithm-evaluation',
      component: () => import('@/views/AlgorithmEvaluationView.vue'),
      meta: { title: '模型评估' }
    },
    {
      path: '/algorithm/features',
      name: 'algorithm-features',
      component: () => import('@/views/AlgorithmFeaturesView.vue'),
      meta: { title: '特征工程' }
    },
    {
      path: '/docs',
      name: 'docs',
      component: () => import('@/views/DocumentView.vue'),
      meta: { title: '文档' }
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('@/views/ProfileView.vue'),
      meta: { title: '个人信息' }
    }
  ]
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || '首页'} - 智能家居安全监控`
  
  const token = localStorage.getItem('access_token')
  const isPublicRoute = to.meta.public === true
  
  if (!token && !isPublicRoute) {
    // 未登录且访问需要认证的页面，跳转登录
    next({ name: 'login', query: { redirect: to.fullPath } })
  } else if (token && to.name === 'login') {
    // 已登录访问登录页，跳转首页
    next({ name: 'home' })
  } else {
    next()
  }
})

export default router
