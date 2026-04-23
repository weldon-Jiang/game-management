<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>商户订阅</h2>
        <span class="header-desc">查看和管理商户订阅状态</span>
      </div>
    </div>

    <el-row :gutter="20">
      <!-- 订阅状态卡片 -->
      <el-col :span="8">
        <div class="status-card">
          <div class="status-header">
            <span class="status-label">当前状态</span>
            <el-tag :type="subscriptionStatus === 'active' ? 'success' : 'danger'" size="large">
              {{ subscriptionStatus === 'active' ? '已激活' : '未激活/已过期' }}
            </el-tag>
          </div>
          <div class="status-info" v-if="subscriptionStatus === 'active'">
            <div class="info-item">
              <span class="label">VIP类型</span>
              <span class="value">{{ getVipTypeText(currentVipType) || '-' }}</span>
            </div>
            <div class="info-item" v-if="currentVipName">
              <span class="label">套餐名称</span>
              <span class="value">{{ currentVipName }}</span>
            </div>
            <div class="info-item">
              <span class="label">到期时间</span>
              <span class="value expire">{{ expireTime || '永久' }}</span>
            </div>
          </div>
          <div class="status-empty" v-else>
            <p>您的商户尚未激活或已过期</p>
            <p>请使用激活码激活</p>
          </div>
        </div>
      </el-col>

      <!-- 激活码激活 -->
      <el-col :span="16">
        <div class="activate-card">
          <div class="card-title">
            <h3>激活/续费</h3>
          </div>
          <div class="activate-form">
            <el-input
              v-model="activationCode"
              placeholder="请输入激活码"
              size="large"
              class="code-input"
              @keyup.enter="handleActivate"
            >
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
            <el-button
              type="primary"
              size="large"
              :loading="activating"
              @click="handleActivate"
            >
              激 活
            </el-button>
          </div>
          <div class="activate-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>激活码用于开通或续费商户VIP服务，开通后可使用平台全部功能</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 已激活VIP套餐 -->
    <div class="vip-section" v-if="activatedVips.length > 0">
      <div class="section-header">
        <h3>已激活VIP套餐</h3>
      </div>
      <el-table :data="activatedVips" class="data-table">
        <el-table-column prop="vipName" label="套餐名称" min-width="120" />
        <el-table-column prop="vipTypeText" label="VIP类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="success" size="small">{{ row.vipTypeText }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="durationDays" label="时长(天)" width="100" align="center" />
        <el-table-column prop="usedTime" label="开始时间" width="170">
          <template #default="{ row }">
            {{ row.usedTime ? formatDate(row.usedTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="expireTime" label="结束时间" width="170">
          <template #default="{ row }">
            {{ row.expireTime ? formatDate(row.expireTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="code" label="激活码" min-width="150" show-overflow-tooltip />
      </el-table>
    </div>

    <!-- VIP套餐列表 -->
    <div class="vip-section">
      <div class="section-header">
        <h3>可用VIP套餐</h3>
        <span class="tip">平台管理员可以配置VIP套餐</span>
      </div>
      <el-row :gutter="16" v-if="vipList.length > 0">
        <el-col :span="8" v-for="vip in vipList" :key="vip.id">
          <div class="vip-card" :class="{ 'is-default': vip.isDefault }">
            <div class="vip-header">
              <span class="vip-type">{{ getVipTypeText(vip.vipType) }}</span>
              <el-tag v-if="vip.isDefault" type="success" size="small">推荐</el-tag>
            </div>
            <div class="vip-price">
              <span class="currency">¥</span>
              <span class="amount">{{ vip.price }}</span>
            </div>
            <div class="vip-duration">{{ vip.durationDays }}天</div>
            <div class="vip-features" v-if="vip.features">
              {{ vip.features }}
            </div>
          </div>
        </el-col>
      </el-row>
      <el-empty v-else description="暂无可用的VIP套餐" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Key, InfoFilled } from '@element-plus/icons-vue'
import { subscriptionApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { getVipTypeText } from '@/utils/constants'

/**
 * 商户订阅管理页面
 * 提供订阅状态查看、激活码激活和VIP套餐展示功能
 */

// ==================== 状态定义 ====================

const authStore = useAuthStore()

/**
 * 平台管理员标识
 */
const isPlatformAdmin = computed(() => authStore.isPlatformAdmin)

/**
 * 订阅状态
 */
const subscriptionStatus = ref('inactive')
const currentVipType = ref('')
const currentVipName = ref('')
const expireTime = ref('')

/**
 * 激活相关状态
 */
const activationCode = ref('')
const activating = ref(false)

/**
 * VIP套餐列表
 */
const vipList = ref([])

/**
 * 已激活VIP列表
 */
const activatedVips = ref([])

// ==================== 方法定义 ====================

/**
 * 加载订阅状态
 */
const loadSubscriptionStatus = async () => {
  if (isPlatformAdmin.value) {
    subscriptionStatus.value = 'active'
    return
  }

  try {
    const res = await subscriptionApi.getStatus()
    if (res.data) {
      subscriptionStatus.value = res.data.status || 'inactive'
      currentVipType.value = res.data.vipType || ''
      currentVipName.value = res.data.vipName || ''
      expireTime.value = res.data.expireTime ? formatDate(res.data.expireTime) : ''
    }
  } catch (error) {
    subscriptionStatus.value = 'inactive'
  }
}

/**
 * 加载VIP套餐列表
 */
const loadVipList = async () => {
  try {
    const res = await subscriptionApi.getVipConfigs()
    vipList.value = res.data || []
  } catch (error) {
    console.error('Failed to load VIP list:', error)
  }
}

/**
 * 加载已激活VIP列表
 */
const loadActivatedVips = async () => {
  if (isPlatformAdmin.value) {
    activatedVips.value = []
    return
  }

  try {
    const res = await subscriptionApi.getActivatedVips()
    activatedVips.value = res.data || []
  } catch (error) {
    console.error('Failed to load activated VIP list:', error)
  }
}

/**
 * 处理激活码激活
 */
const handleActivate = async () => {
  if (!activationCode.value.trim()) {
    ElMessage.warning('请输入激活码')
    return
  }

  activating.value = true
  try {
    await subscriptionApi.activate(activationCode.value.trim())
    ElMessage.success('激活成功！')
    activationCode.value = ''
    await loadSubscriptionStatus()
    await loadActivatedVips()
  } catch (error) {
  } finally {
    activating.value = false
  }
}

/**
 * 格式化日期时间
 */
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadSubscriptionStatus()
  loadVipList()
  loadActivatedVips()
})
</script>

<style scoped>
.page-container {
  padding: 0;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px;
}

.header-desc {
  font-size: 13px;
  color: #8a8a8a;
}

.status-card,
.activate-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
  height: 100%;
}

.status-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.status-label {
  font-size: 14px;
  color: #8a8a8a;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-item .label {
  font-size: 13px;
  color: #8a8a8a;
}

.info-item .value {
  font-size: 14px;
  color: #ffffff;
  font-weight: 500;
}

.info-item .value.expire {
  color: #10b981;
}

.status-empty {
  text-align: center;
  padding: 20px 0;
}

.status-empty p {
  margin: 8px 0;
  color: #8a8a8a;
  font-size: 14px;
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

.activate-form {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.code-input {
  flex: 1;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: #ffffff;
}

:deep(.el-input__prefix) {
  color: #8a8a8a;
}

.activate-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8a8a8a;
  font-size: 13px;
}

.activate-tip .el-icon {
  color: #6366f1;
}

.vip-section {
  margin-top: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h3 {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.section-header .tip {
  font-size: 12px;
  color: #6b7280;
}

.vip-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 16px;
  transition: all 0.3s ease;
}

.vip-card:hover {
  border-color: rgba(99, 102, 241, 0.3);
  transform: translateY(-4px);
}

.vip-card.is-default {
  border-color: rgba(99, 102, 241, 0.5);
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
}

.vip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.vip-type {
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.vip-price {
  display: flex;
  align-items: baseline;
  margin-bottom: 8px;
}

.vip-price .currency {
  font-size: 18px;
  color: #f59e0b;
  margin-right: 4px;
}

.vip-price .amount {
  font-size: 32px;
  font-weight: 700;
  color: #f59e0b;
}

.vip-duration {
  font-size: 13px;
  color: #8a8a8a;
  margin-bottom: 12px;
}

.vip-features {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

.data-table {
  background: transparent;
  border-radius: 12px;
}

:deep(.el-table) {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.03);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.05);
  --el-table-border-color: rgba(255, 255, 255, 0.06);
}

:deep(.el-table__header th) {
  background: rgba(255, 255, 255, 0.03) !important;
  color: #8a8a8a;
  font-weight: 600;
}

:deep(.el-table__body td) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.el-table__row:hover > td) {
  background: rgba(99, 102, 241, 0.05) !important;
}
</style>