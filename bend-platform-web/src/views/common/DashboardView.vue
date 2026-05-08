<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h2>控制台</h2>
      <p>欢迎回来，{{ authStore.username }}</p>
    </div>

    <div class="stats-grid">
      <div v-if="authStore.isPlatformAdmin" class="stat-card">
        <div class="stat-icon merchants">
          <el-icon><OfficeBuilding /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.merchantCount }}</span>
          <span class="stat-label">商户数量</span>
        </div>
      </div>

      <div v-if="authStore.isPlatformAdmin" class="stat-card">
        <div class="stat-icon users">
          <el-icon><User /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.userCount }}</span>
          <span class="stat-label">用户数量</span>
        </div>
      </div>

      <div v-if="authStore.isPlatformAdmin || authStore.isOperator || authStore.isMerchantOwner" class="stat-card">
        <div class="stat-icon streaming">
          <el-icon><VideoPlay /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.streamingCount }}</span>
          <span class="stat-label">流媒体账号</span>
        </div>
      </div>

      <div v-if="authStore.isPlatformAdmin || authStore.isOperator || authStore.isMerchantOwner" class="stat-card">
        <div class="stat-icon games">
          <el-icon><Trophy /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.gameAccountCount }}</span>
          <span class="stat-label">游戏账号</span>
        </div>
      </div>

      <div v-if="authStore.isPlatformAdmin || authStore.isOperator || authStore.isMerchantOwner" class="stat-card">
        <div class="stat-icon xbox">
          <el-icon><Monitor /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.xboxCount }}</span>
          <span class="stat-label">Xbox主机</span>
        </div>
      </div>

      <div v-if="authStore.isPlatformAdmin || authStore.isOperator || authStore.isMerchantOwner" class="stat-card">
        <div class="stat-icon agents">
          <el-icon><Cpu /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stats.agentCount }}</span>
          <span class="stat-label">Agent管理</span>
        </div>
      </div>
    </div>

    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <div class="content-card">
          <div class="card-title">
            <h3>账户信息</h3>
          </div>
          <div class="account-info">
            <div class="info-item">
              <span class="info-label">用户名</span>
              <span class="info-value">{{ authStore.username }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">角色</span>
              <span class="info-value role-tag">{{ roleText }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">商户ID</span>
              <span class="info-value merchant-id">{{ authStore.merchantId || '无' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">登录时间</span>
              <span class="info-value">{{ currentTime }}</span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { OfficeBuilding, User, VideoPlay, Monitor, Coin, Key, CreditCard, Cpu, Trophy, Box, Wallet, Tickets } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { dashboardApi } from '@/api'

const router = useRouter()
const authStore = useAuthStore()

const stats = ref({
  merchantCount: 0,
  userCount: 0,
  streamingCount: 0,
  xboxCount: 0,
  agentCount: 0,
  gameAccountCount: 0
})

const currentTime = ref('')
let timer = null

const roleText = computed(() => {
  const roleMap = {
    platform_admin: '平台管理员',
    merchant_owner: '商户管理员',
    operator: '操作员'
  }
  return roleMap[authStore.role] || authStore.role
})

const updateTime = () => {
  const now = new Date()
  currentTime.value = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const loadStats = async () => {
  try {
    const res = await dashboardApi.getStats()
    if (res.code === 0 || res.code === 200) {
      const data = res.data
      stats.value.merchantCount = data.merchantCount || 0
      stats.value.userCount = data.merchantUserCount || 0
      stats.value.streamingCount = data.streamingAccountCount || 0
      stats.value.xboxCount = data.xboxHostCount || 0
      stats.value.agentCount = data.agentCount || 0
      stats.value.gameAccountCount = data.gameAccountCount || 0
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadStats()
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.dashboard-header {
  margin-bottom: 28px;
}

.dashboard-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 8px;
}

.dashboard-header p {
  font-size: 14px;
  color: #8a8a8a;
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
  display: flex;
  align-items: center;
  gap: 20px;
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  border-color: rgba(99, 102, 241, 0.3);
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.merchants {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
  color: #6366f1;
}

.stat-icon.users {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.1) 100%);
  color: #10b981;
}

.stat-icon.streaming {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(234, 88, 12, 0.1) 100%);
  color: #f59e0b;
}

.stat-icon.xbox {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.2) 0%, rgba(37, 99, 235, 0.1) 100%);
  color: #3b82f6;
}

.stat-icon.agents {
  background: linear-gradient(135deg, rgba(168, 85, 247, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
  color: #a855f7;
}

.stat-icon.games {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(234, 179, 8, 0.1) 100%);
  color: #f59e0b;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: #8a8a8a;
  margin-top: 4px;
}

.content-row {
  margin-bottom: 20px;
}

.content-card {
  height: 100%;
}

.card-title {
  margin-bottom: 20px;
}

.card-title h3 {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.account-info {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
}

.info-label {
  font-size: 13px;
  color: #8a8a8a;
}

.info-value {
  font-size: 13px;
  color: #ffffff;
  font-weight: 500;
}

.info-value.role-tag {
  padding: 4px 10px;
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
  border-radius: 6px;
  font-size: 12px;
}

.info-value.merchant-id {
  font-size: 11px;
  color: #6b7280;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
