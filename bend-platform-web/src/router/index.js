import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '用户登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/login/RegisterView.vue'),
    meta: { title: '用户注册', requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/layout/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/common/DashboardView.vue'),
        meta: { title: '控制台', icon: 'Odometer' }
      },
      {
        path: 'merchants',
        name: 'Merchants',
        component: () => import('@/views/merchant/MerchantList.vue'),
        meta: { title: '商户管理', icon: 'OfficeBuilding', requiresAdmin: true }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/user/UserList.vue'),
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'streaming-accounts',
        name: 'StreamingAccounts',
        component: () => import('@/views/streaming/StreamingAccountList.vue'),
        meta: { title: '流媒体账号', icon: 'VideoPlay' }
      },
      {
        path: 'game-accounts',
        name: 'GameAccounts',
        component: () => import('@/views/game/GameAccountList.vue'),
        meta: { title: '游戏账号', icon: 'Trophy' }
      },
      {
        path: 'xbox-hosts',
        name: 'XboxHosts',
        component: () => import('@/views/xbox/XboxHostList.vue'),
        meta: { title: 'Xbox主机', icon: 'GameConsole' }
      },
      {
        path: 'activation-codes',
        name: 'ActivationCodes',
        component: () => import('@/views/activation/ActivationCodeList.vue'),
        meta: { title: '激活码管理', icon: 'Key', requiresAdmin: true }
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/views/agent/AgentList.vue'),
        meta: { title: 'Agent管理', icon: 'Cpu' }
      },
      {
        path: 'agent-versions',
        name: 'AgentVersions',
        component: () => import('@/views/agent/AgentVersionList.vue'),
        meta: { title: 'Agent版本', icon: 'Box', requiresAdmin: true }
      },
      {
        path: 'registration-codes',
        name: 'RegistrationCodes',
        component: () => import('@/views/registration/RegistrationCodeList.vue'),
        meta: { title: '注册码管理', icon: 'Key' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/task/TaskList.vue'),
        meta: { title: '任务管理', icon: 'List' }
      },
      {
        path: 'subscription',
        name: 'Subscription',
        component: () => import('@/views/subscription/SubscriptionList.vue'),
        meta: { title: '订阅管理', icon: 'Wallet' }
      },
      {
        path: 'merchant-groups',
        name: 'MerchantGroups',
        component: () => import('@/views/merchant/MerchantGroupList.vue'),
        meta: { title: '商户分组', icon: 'User', requiresAdmin: true }
      },
      {
        path: 'recharge-cards',
        name: 'RechargeCards',
        component: () => import('@/views/recharge/RechargeCardManagement.vue'),
        meta: { title: '充值卡管理', icon: 'Tickets' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由错误处理
router.onError((error) => {
  console.error('Router Error:', error)
})

/**
 * 路由守卫 - 控制页面访问权限
 * 1. 验证用户是否已登录
 * 2. 验证用户角色是否有权限访问特定页面
 * 3. 更新页面标题
 */
router.beforeEach((to, from, next) => {
  console.log('Router: navigating to', to.name)
  // 更新页面标题
  document.title = to.meta.title
    ? `${to.meta.title} - ${import.meta.env.VITE_APP_TITLE || 'Bend Platform'}`
    : import.meta.env.VITE_APP_TITLE || 'Bend Platform'

  const authStore = useAuthStore()

  // 如果页面需要登录但用户未登录，重定向到登录页
  if (to.meta.requiresAuth !== false && !authStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 如果用户已登录，访问登录页则重定向到首页
  if (to.name === 'Login' && authStore.isLoggedIn) {
    next({ name: 'Dashboard' })
    return
  }

  // 如果页面需要平台管理员权限，验证用户角色
  if (to.meta.requiresAdmin && !authStore.isPlatformAdmin) {
    ElMessage.warning('您没有权限访问该页面')
    next({ name: 'Dashboard' })
    return
  }

  next()
})

export default router