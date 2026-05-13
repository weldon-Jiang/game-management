<template>
  <el-container class="main-layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="aside">
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

        <el-divider style="margin: 8px 0; border-color: rgba(255,255,255,0.06);" />

        <div class="menu-group-title" v-if="!isCollapse && showUserManagementGroup">账号管理</div>
        <el-menu-item v-if="authStore.isPlatformAdmin" index="Merchants" @click="router.push('/merchants')">
          <el-icon><OfficeBuilding /></el-icon>
          <template #title>商户管理</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.hasManagementPermission" index="Users" @click="router.push('/users')">
          <el-icon><User /></el-icon>
          <template #title>用户管理</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.isPlatformAdmin" index="MerchantGroups" @click="router.push('/merchant-groups')">
          <el-icon><Collection /></el-icon>
          <template #title>VIP分组</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.isPlatformAdmin" index="ActivationCodes" @click="router.push('/activation-codes')">
          <el-icon><Key /></el-icon>
          <template #title>激活码管理</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.isPlatformAdmin" index="AgentVersions" @click="router.push('/agent-versions')">
          <el-icon><Box /></el-icon>
          <template #title>Agent版本</template>
        </el-menu-item>

        <div class="menu-group-title" v-if="!isCollapse && showAccountGroup">账号管理</div>
        <el-menu-item v-if="authStore.hasManagementPermission || authStore.isOperator" index="StreamingAccounts" @click="router.push('/streaming-accounts')">
          <el-icon><VideoPlay /></el-icon>
          <template #title>流媒体账号</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.hasManagementPermission || authStore.isOperator" index="GameAccounts" @click="router.push('/game-accounts')">
          <el-icon><Trophy /></el-icon>
          <template #title>游戏账号</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.hasManagementPermission || authStore.isOperator" index="XboxHosts" @click="router.push('/xbox-hosts')">
          <el-icon><Monitor /></el-icon>
          <template #title>Xbox主机</template>
        </el-menu-item>

        <div class="menu-group-title" v-if="!isCollapse && showAgentGroup">Agent管理</div>
        <el-menu-item v-if="authStore.hasManagementPermission || authStore.isOperator" index="Agents" @click="router.push('/agents')">
          <el-icon><Cpu /></el-icon>
          <template #title>Agent管理</template>
        </el-menu-item>
        <el-menu-item v-if="authStore.isPlatformAdmin" index="RegistrationCodes" @click="router.push('/registration-codes')">
          <el-icon><Key /></el-icon>
          <template #title>注册码管理</template>
        </el-menu-item>

        <div class="menu-group-title" v-if="!isCollapse && showBillingGroup">订阅与计费</div>
        <el-menu-item v-if="authStore.hasManagementPermission" index="Subscription" @click="router.push('/subscription')">
          <el-icon><Wallet /></el-icon>
          <template #title>订阅管理</template>
        </el-menu-item>
        <!-- 暂时隐藏充值卡管理菜单 -->
        <!--
        <el-menu-item v-if="authStore.isPlatformAdmin" index="RechargeCards" @click="router.push('/recharge-cards')">
          <el-icon><Tickets /></el-icon>
          <template #title>充值卡管理</template>
        </el-menu-item>
        -->
      </el-menu>
    </el-aside>

    <el-container class="main-container">
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
  SwitchButton,
  Wallet,
  Tickets,
  Collection
} from '@element-plus/icons-vue'

const router = useRouter()
const authStore = useAuthStore()

const isCollapse = ref(false)

const showUserManagementGroup = computed(() => authStore.hasManagementPermission)
const showPlatformGroup = computed(() => authStore.isPlatformAdmin)
const showAccountGroup = computed(() => authStore.hasManagementPermission || authStore.isOperator)
const showAgentGroup = computed(() => authStore.hasManagementPermission || authStore.isOperator)
const showBillingGroup = computed(() => authStore.hasManagementPermission)

const activeMenu = computed(() => currentRoute.name)
const currentRoute = useRoute()

const roleText = computed(() => {
  const roleMap = {
    platform_admin: '平台管理员',
    merchant_owner: '商户管理员',
    operator: '操作员'
  }
  return roleMap[authStore.role] || authStore.role
})

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
.main-layout {
  height: 100vh;
  background: #0a0a0f;
}

.aside {
  background: linear-gradient(180deg, #12121a 0%, #0a0a0f 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  transition: width 0.3s ease;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: rgba(99, 102, 241, 0.3) transparent;
}

.aside::-webkit-scrollbar {
  width: 4px;
}

.aside::-webkit-scrollbar-track {
  background: transparent;
}

.aside::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.3);
  border-radius: 4px;
}

.aside::-webkit-scrollbar-thumb:hover {
  background: rgba(99, 102, 241, 0.5);
}

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

.nav-menu {
  border-right: none;
  padding: 12px 8px;
}

.nav-menu:not(.el-menu--collapse) {
  width: 220px;
}

.menu-group-title {
  padding: 12px 12px 8px;
  font-size: 11px;
  font-weight: 600;
  color: #5a5a5a;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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

.main-container {
  flex-direction: column;
  background: #0a0a0f;
}

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

.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}

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
</style>
