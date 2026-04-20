<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h2>控制台</h2>
      <p>欢迎回来，{{ authStore.username }}</p>
    </div>

    <el-row :gutter="20" class="stats-row">
      <el-col v-if="authStore.isPlatformAdmin" :span="6">
        <div class="stat-card">
          <div class="stat-icon merchants">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.merchantCount }}</span>
            <span class="stat-label">商户数量</span>
          </div>
        </div>
      </el-col>

      <el-col v-if="authStore.isPlatformAdmin" :span="6">
        <div class="stat-card">
          <div class="stat-icon users">
            <el-icon><User /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.userCount }}</span>
            <span class="stat-label">用户数量</span>
          </div>
        </div>
      </el-col>

      <el-col v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" :span="6">
        <div class="stat-card">
          <div class="stat-icon streaming">
            <el-icon><VideoPlay /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.streamingCount }}</span>
            <span class="stat-label">流媒体账号</span>
          </div>
        </div>
      </el-col>

      <el-col v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" :span="6">
        <div class="stat-card">
          <div class="stat-icon xbox">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.xboxCount }}</span>
            <span class="stat-label">Xbox主机</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="stats-row">
      <el-col v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" :span="6">
        <div class="stat-card">
          <div class="stat-icon agents">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.agentCount }}</span>
            <span class="stat-label">Agent实例</span>
          </div>
        </div>
      </el-col>

      <el-col v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" :span="6">
        <div class="stat-card">
          <div class="stat-icon games">
            <el-icon><Trophy /></el-icon>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ stats.gameAccountCount }}</span>
            <span class="stat-label">游戏账号</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="content-row">
      <el-col :span="16">
        <div class="content-card">
          <div class="card-title">
            <h3>快捷操作</h3>
          </div>
          <div class="quick-actions">
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin" class="action-item" @click="router.push('/users')">
              <div class="action-icon">
                <el-icon><User /></el-icon>
              </div>
              <span>用户管理</span>
            </div>
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" class="action-item" @click="router.push('/streaming-accounts')">
              <div class="action-icon">
                <el-icon><VideoPlay /></el-icon>
              </div>
              <span>流媒体账号</span>
            </div>
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" class="action-item" @click="router.push('/xbox-hosts')">
              <div class="action-icon">
                <el-icon><Monitor /></el-icon>
              </div>
              <span>Xbox主机</span>
            </div>
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" class="action-item" @click="router.push('/agents')">
              <div class="action-icon">
                <el-icon><Cpu /></el-icon>
              </div>
              <span>Agent管理</span>
            </div>
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin || authStore.isOperator" class="action-item" @click="router.push('/game-accounts')">
              <div class="action-icon">
                <el-icon><Trophy /></el-icon>
              </div>
              <span>游戏账号</span>
            </div>
            <div v-if="authStore.isPlatformAdmin" class="action-item" @click="router.push('/vip-configs')">
              <div class="action-icon">
                <el-icon><Coin /></el-icon>
              </div>
              <span>VIP配置</span>
            </div>
            <div v-if="authStore.isPlatformAdmin" class="action-item" @click="router.push('/activation-codes')">
              <div class="action-icon">
                <el-icon><Key /></el-icon>
              </div>
              <span>激活码</span>
            </div>
            <div v-if="authStore.isPlatformAdmin || authStore.isOwner || authStore.isAdmin" class="action-item" @click="router.push('/subscription')">
              <div class="action-icon">
                <el-icon><CreditCard /></el-icon>
              </div>
              <span>商户订阅</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="8">
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
import { OfficeBuilding, User, VideoPlay, Monitor, Coin, Key, CreditCard, Cpu, Trophy } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { merchantApi, userApi, streamingApi, xboxApi, agentApi, gameAccountApi } from '@/api'

/**
 * 控制台视图组件
 * 展示系统概览、统计数据和快捷操作入口
 */
const router = useRouter()
const authStore = useAuthStore()

/**
 * 统计数据
 */
const stats = ref({
  merchantCount: 0,
  userCount: 0,
  streamingCount: 0,
  xboxCount: 0,
  agentCount: 0,
  gameAccountCount: 0
})

/**
 * 当前时间
 */
const currentTime = ref('')

/**
 * 定时器ID
 */
let timer = null

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
 * 更新当前时间
 */
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

/**
 * 加载统计数据
 * 根据用户角色获取不同的统计数据
 */
const loadStats = async () => {
  try {
    // 获取商户数量（仅平台管理员可见全部）
    if (authStore.isPlatformAdmin) {
      const merchantRes = await merchantApi.list({ pageNum: 1, pageSize: 1 })
      stats.value.merchantCount = merchantRes.data?.total || 0
    }

    // 获取用户数量
    const userRes = await userApi.list({ pageNum: 1, pageSize: 1 })
    stats.value.userCount = userRes.data?.total || 0

    // 获取流媒体账号数量
    const streamingRes = await streamingApi.list({ pageNum: 1, pageSize: 1 })
    stats.value.streamingCount = streamingRes.data?.total || 0

    // 获取Xbox主机数量
    const xboxRes = await xboxApi.listPage({ pageNum: 1, pageSize: 1 })
    stats.value.xboxCount = xboxRes.data?.total || 0

    // 获取Agent实例数量
    const agentRes = await agentApi.listPage({ pageNum: 1, pageSize: 1 })
    stats.value.agentCount = agentRes.data?.total || 0

    // 获取游戏账号数量
    const gameAccountRes = await gameAccountApi.list({ pageNum: 1, pageSize: 1 })
    stats.value.gameAccountCount = gameAccountRes.data?.total || 0
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

/**
 * 组件挂载时
 * 1. 更新初始时间
 * 2. 启动时间定时器
 * 3. 加载统计数据
 */
onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadStats()
})

/**
 * 组件卸载时清除定时器
 */
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

.stats-row {
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
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
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

.quick-actions {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-item:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-2px);
}

.action-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
  color: #6366f1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.action-item span {
  font-size: 13px;
  color: #b0b0b0;
}

.account-info {
  display: flex;
  flex-direction: column;
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