<template>
  <el-container class="main-layout">
    <!-- 左侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
      <!-- Logo区域 -->
      <div class="logo-area">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <transition name="fade">
          <span v-if="!isCollapse" class="logo-text">Bend Platform</span>
        </transition>
      </div>

      <!-- 导航菜单 -->
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :collapse-transition="false"
        class="nav-menu"
        background-color="transparent"
        text-color="#8a8a8a"
        active-text-color="#ffffff"
      >
        <el-menu-item index="Dashboard" @click="router.push('/dashboard')">
          <el-icon><Odometer /></el-icon>
          <template #title>控制台</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin" index="Merchants" @click="router.push('/merchants')">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>商户管理</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin" index="Users" @click="router.push('/users')">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" index="StreamingAccounts" @click="router.push('/streaming-accounts')">
          <el-icon><VideoPlay /></el-icon>
          <template #title>流媒体账号</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" index="GameAccounts" @click="router.push('/game-accounts')">
          <el-icon><Trophy /></el-icon>
          <template #title>游戏账号</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" index="XboxHosts" @click="router.push('/xbox-hosts')">
          <el-icon><Monitor /></el-icon>
          <template #title>Xbox主机</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" index="Agents" @click="router.push('/agents')">
          <el-icon><Cpu /></el-icon>
          <template #title>Agent管理</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin" index="AgentVersions" @click="router.push('/agent-versions')">
          <el-icon><Box /></el-icon>
          <template #title>Agent版本</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin" index="VipConfigs" @click="router.push('/vip-configs')">
          <el-icon><Coin /></el-icon>
          <template #title>VIP配置</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin" index="ActivationCodes" @click="router.push('/activation-codes')">
          <el-icon><Key /></el-icon>
          <template #title>激活码管理</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isOwner || authStore.isAdmin" index="Subscription" @click="router.push('/subscription')">
          <el-icon><CreditCard /></el-icon>
          <template #title>商户订阅</template>
        </el-menu-item>

        <el-menu-item v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin" index="RegistrationCodes" @click="router.push('/registration-codes')">
          <el-icon><Key /></el-icon>
          <template #title>注册码管理</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧主内容区 -->
    <el-container class="main-container">
      <!-- 顶部导航栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-button
            :icon="isCollapse ? 'Expand' : 'Fold'"
            text
            class="collapse-btn"
            @click="isCollapse = !isCollapse"
          />
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute.meta.title !== '控制台'">
              {{ currentRoute.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <!-- 用户信息 -->
          <el-dropdown @command="handleUserCommand">
            <div class="user-info">
              <el-avatar :size="32" class="user-avatar">
                {{ authStore.username?.charAt(0).toUpperCase() }}
              </el-avatar>
              <div class="user-detail">
                <span class="username">{{ authStore.username }}</span>
                <span class="role-tag">{{ roleText }}</span>
              </div>
              <el-icon class="arrow-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import {
  Odometer,
  OfficeBuilding,
  User,
  VideoPlay,
  Monitor,
  Trophy,
  Coin,
  Key,
  CreditCard,
  Cpu,
  Box,
  Fold,
  Expand,
  ArrowDown,
  SwitchButton
} from '@element-plus/icons-vue'

/**
 * 主布局组件
 * 包含左侧导航栏和右侧内容区
 */
const router = useRouter()
const authStore = useAuthStore()

/**
 * 侧边栏折叠状态
 */
const isCollapse = ref(false)

/**
 * 当前激活的菜单项
 */
const activeMenu = computed(() => currentRoute.name)

/**
 * 当前路由信息
 */
const currentRoute = useRoute()

/**
 * 角色显示文本
 */
const roleText = computed(() => {
  const roleMap = {
    platform_admin: '平台管理员',
    owner: '商户所有者',
    admin: '商户管理员',
    operator: '操作员'
  }
  return roleMap[authStore.role] || authStore.role
})

/**
 * 处理用户下拉菜单命令
 * @param {string} command - 命令标识
 */
const handleUserCommand = (command) => {
  if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(() => {
      authStore.logout()
      router.push('/login')
    }).catch(() => {})
  }
}
</script>

<style scoped>
/* 主布局容器 - 全屏占据 */
.main-layout {
  height: 100vh;
  background: #0a0a0f;
}

/* 左侧边栏样式 */
.aside {
  background: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  transition: width 0.3s ease;
  overflow: hidden;
}

/* Logo区域 */
.logo-area {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-icon {
  width: 32px;
  height: 32px;
  color: #6366f1;
  flex-shrink: 0;
}

.logo-icon svg {
  width: 100%;
  height: 100%;
}

.logo-text {
  margin-left: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
}

/* 导航菜单样式 */
.nav-menu {
  border-right: none;
  padding: 12px 8px;
}

.nav-menu:not(.el-menu--collapse) {
  width: 220px;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 4px 0;
  border-radius: 10px;
  transition: all 0.2s ease;
}

:deep(.el-menu-item:hover) {
  background: rgba(99, 102, 241, 0.15) !important;
  color: #ffffff;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.3) 0%, rgba(139, 92, 246, 0.2) 100%) !important;
  color: #ffffff;
}

:deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: linear-gradient(180deg, #818cf8 0%, #6366f1 100%);
  border-radius: 0 2px 2px 0;
}

/* 主内容区容器 */
.main-container {
  flex-direction: column;
  background: #0a0a0f;
}

/* 顶部导航栏 */
.header {
  height: 64px;
  background: rgba(18, 18, 26, 0.8);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 18px;
  color: #8a8a8a;
  transition: color 0.2s;
}

.collapse-btn:hover {
  color: #ffffff;
}

/* 面包屑导航 */
:deep(.el-breadcrumb) {
  font-size: 14px;
}

:deep(.el-breadcrumb__inner) {
  color: #8a8a8a;
}

:deep(.el-breadcrumb__inner a) {
  color: #8a8a8a;
  font-weight: 400;
}

:deep(.el-breadcrumb__separator) {
  color: #4a4a4a;
}

/* 用户信息区域 */
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 10px;
  transition: background 0.2s;
}

.user-info:hover {
  background: rgba(255, 255, 255, 0.05);
}

.user-avatar {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  font-size: 14px;
  font-weight: 600;
}

.user-detail {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.username {
  font-size: 14px;
  color: #ffffff;
  font-weight: 500;
}

.role-tag {
  font-size: 11px;
  color: #8a8a8a;
}

.arrow-icon {
  color: #8a8a8a;
  font-size: 12px;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

/* 页面切换动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 淡入淡出动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.4s ease;
  position: absolute;
  width: 100%;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>23