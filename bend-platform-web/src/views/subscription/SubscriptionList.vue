<template>
  <div class="page-container subscription-list">
    <div class="page-header">
      <h2>订阅管理</h2>
    </div>

    <!-- 订阅概览卡片 -->
    <div class="overview-section">
      <div class="overview-cards">
        <!-- 当前订阅状态 -->
        <div class="overview-card subscription-card" :class="{ 'has-subscription': currentSubscription }">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-label">当前订阅</div>
            <div class="card-value" v-if="currentSubscription">
              <el-tag :type="getTypeTag(currentSubscription.subscriptionType)" size="small">
                {{ getTypeName(currentSubscription.subscriptionType) }}
              </el-tag>
            </div>
            <div class="card-value empty" v-else>暂无订阅</div>
            <div class="card-desc" v-if="currentSubscription">
              到期时间：{{ formatDate(currentSubscription.endTime) }}
            </div>
          </div>
          <div class="card-status" :class="currentSubscription?.status || 'none'">
            {{ getStatusText(currentSubscription?.status) }}
          </div>
        </div>

        <!-- 点数余额 -->
        <div class="overview-card balance-card">
          <div class="card-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v12M6 12h12"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-label">可用点数</div>
            <div class="card-value points-value">{{ balance?.balance || 0 }}</div>
            <div class="card-desc">累计消费 {{ balance?.totalConsumed || 0 }} 点</div>
          </div>
        </div>

        <!-- VIP等级 -->
        <div class="overview-card vip-card">
          <div class="card-icon vip-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
            </svg>
          </div>
          <div class="card-content">
            <div class="card-label">VIP等级</div>
            <div class="card-value vip-level">VIP{{ merchantVipLevel || 0 }}</div>
            <div class="card-desc">享受更多特权</div>
          </div>
        </div>
      </div>

      <!-- 激活码激活区域 -->
      <div class="activation-section">
        <div class="activation-header">
          <span class="activation-title">激活码激活</span>
          <span class="activation-hint">输入平台管理员提供的激活码</span>
        </div>
        <div class="activation-form">
          <el-input
            v-model="activationCode"
            placeholder="请输入激活码"
            class="activation-input"
            :prefix-icon="Tickets"
            clearable
          />
          <el-button
            type="primary"
            class="activation-btn"
            :loading="activating"
            :disabled="!activationCode.trim()"
            @click="handleActivate"
          >
            激活
          </el-button>
        </div>
        <div v-if="activationResult" class="activation-result" :class="activationResult.type">
          {{ activationResult.message }}
        </div>
      </div>
    </div>

    <!-- 订阅历史 -->
    <div class="history-section">
      <div class="section-header">
        <span class="section-title">订阅记录</span>
        <div class="section-actions">
          <el-button @click="loadSubscriptions" :loading="loading">
            <el-icon><Refresh /></el-icon>
          </el-button>
          <el-radio-group v-model="historyFilter" size="small">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="active">有效</el-radio-button>
            <el-radio-button value="expired">已过期</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div class="content-card">
        <el-table
          :data="filteredSubscriptionList"
          v-loading="loading"
          class="data-table"
          stripe
        >
          <el-table-column prop="subscriptionType" label="订阅类型" width="150">
            <template #default="{ row }">
              <div class="type-cell">
                <el-tag :type="getTypeTag(row.subscriptionType)" size="small" effect="plain">
                  {{ getTypeName(row.subscriptionType) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="boundResourceNames" label="绑定资源" min-width="150">
            <template #default="{ row }">
              <span v-if="row.boundResourceNames" class="resource-names">{{ row.boundResourceNames }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="startTime" label="开始时间" width="120">
            <template #default="{ row }">
              <span class="date-cell">{{ formatDate(row.startTime) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="endTime" label="到期时间" width="120">
            <template #default="{ row }">
              <span class="date-cell">{{ formatDate(row.endTime) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="originalPrice" label="原价" width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.originalPrice" class="price-original">{{ (row.originalPrice / 100).toFixed(2) }}元</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="discountPrice" label="实付" width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.discountPrice" class="price-paid">{{ (row.discountPrice / 100).toFixed(2) }}元</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusTag(row.status)" size="small" effect="light">
                {{ getStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrap">
          <el-pagination
            v-model:current-page="pagination.pageNum"
            v-model:page-size="pagination.pageSize"
            :total="pagination.total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @change="loadSubscriptions"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Tickets, Refresh } from '@element-plus/icons-vue'
import { subscriptionApi, billingApi, activationApi } from '@/api'

const loading = ref(false)
const activationCode = ref('')
const activating = ref(false)
const activationResult = ref(null)
const subscriptionList = ref([])
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})
const balance = ref(null)
const merchantVipLevel = ref(0)
const historyFilter = ref('all')

const currentSubscription = computed(() => {
  return subscriptionList.value.find(s => s.status === 'active') || null
})

const filteredSubscriptionList = computed(() => {
  if (historyFilter.value === 'all') {
    return subscriptionList.value
  }
  return subscriptionList.value.filter(s => s.status === historyFilter.value)
})

const loadSubscriptions = async () => {
  loading.value = true
  try {
    const res = await subscriptionApi.listSubscriptions({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    subscriptionList.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load subscriptions:', error)
  } finally {
    loading.value = false
  }
}

const loadBalance = async () => {
  try {
    const res = await billingApi.getBalance()
    balance.value = res.data
    merchantVipLevel.value = res.data?.vipLevel || 0
  } catch (error) {
    console.error('Failed to load balance:', error)
  }
}

const handleActivate = async () => {
  if (!activationCode.value.trim()) {
    ElMessage.warning('请输入激活码')
    return
  }

  activating.value = true
  activationResult.value = null

  try {
    const res = await activationApi.activate(activationCode.value.trim())
    if (res.success !== false) {
      activationResult.value = { type: 'success', message: '激活成功！' }
      activationCode.value = ''
      loadSubscriptions()
      loadBalance()
      setTimeout(() => {
        activationResult.value = null
      }, 3000)
    } else {
      activationResult.value = { type: 'error', message: res.message || '激活失败' }
    }
  } catch (error) {
    activationResult.value = { type: 'error', message: error.message || '激活失败，请检查激活码是否正确' }
  } finally {
    activating.value = false
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定要取消该订阅吗？', '提示', { type: 'warning' })
    await subscriptionApi.cancelSubscription(row.id)
    ElMessage.success('订阅已取消')
    loadSubscriptions()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to cancel subscription:', error)
    }
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const getTypeTag = (type) => {
  const map = {
    'points': 'primary',
    'account': 'success',
    'window_account': 'warning',
    'host': 'danger',
    'full': 'info'
  }
  return map[type] || 'info'
}

const getTypeName = (type) => {
  const map = {
    'points': '点数充值',
    'account': '游戏账号包月',
    'window_account': '流媒体账号包月',
    'host': 'Xbox主机包月',
    'full': '全功能包月'
  }
  return map[type] || type || '点数充值'
}

const getStatusTag = (status) => {
  const map = {
    'active': 'success',
    'expired': 'info',
    'cancelled': 'danger'
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    'active': '有效',
    'expired': '已过期',
    'cancelled': '已取消'
  }
  return map[status] || status || '无订阅'
}

onMounted(() => {
  loadSubscriptions()
  loadBalance()
})
</script>

<style scoped>
.subscription-list {
  padding: var(--spacing-xl);
}

.page-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* 概览卡片区域 */
.overview-section {
  margin-top: var(--spacing-xl);
}

.overview-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-lg);
}

.overview-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-lg);
  position: relative;
  overflow: hidden;
  transition: all 0.3s ease;
}

.overview-card:hover {
  border-color: var(--border-strong);
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.overview-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary) 0%, transparent 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
}

.overview-card:hover::before {
  opacity: 1;
}

.overview-card.subscription-card.has-subscription::before {
  opacity: 1;
  background: linear-gradient(90deg, var(--success) 0%, transparent 100%);
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  background: var(--bg-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-icon svg {
  width: 24px;
  height: 24px;
  color: var(--primary);
}

.balance-card .card-icon svg {
  color: var(--success);
}

.vip-card .card-icon {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.05) 100%);
}

.vip-icon svg {
  color: var(--warning);
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-label {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
}

.card-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.card-value.empty {
  color: var(--text-muted);
  font-weight: 400;
}

.card-value.points-value {
  font-size: 28px;
  background: linear-gradient(135deg, var(--success) 0%, #10b981 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-value.vip-level {
  background: linear-gradient(135deg, var(--warning) 0%, #f59e0b 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.card-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.card-status {
  position: absolute;
  top: var(--spacing-lg);
  right: var(--spacing-lg);
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

.card-status.active {
  background: rgba(34, 197, 94, 0.1);
  color: var(--success);
}

.card-status.expired {
  background: rgba(156, 163, 175, 0.1);
  color: var(--text-muted);
}

/* 激活码区域 */
.activation-section {
  margin-top: var(--spacing-xl);
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: var(--spacing-xl);
}

.activation-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.activation-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.activation-hint {
  font-size: 13px;
  color: var(--text-muted);
}

.activation-form {
  display: flex;
  gap: var(--spacing-md);
  max-width: 500px;
}

.activation-input {
  flex: 1;
}

.activation-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-lg);
}

.activation-btn {
  border-radius: var(--radius-lg);
  padding: 0 24px;
  font-weight: 500;
}

.activation-result {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  border-radius: var(--radius-lg);
  font-size: 14px;
}

.activation-result.success {
  background: rgba(34, 197, 94, 0.1);
  color: var(--success);
  border: 1px solid rgba(34, 197, 94, 0.2);
}

.activation-result.error {
  background: rgba(239, 68, 68, 0.1);
  color: var(--danger);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

/* 历史记录区域 */
.history-section {
  margin-top: 48px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
}

.section-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.content-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  padding: var(--spacing-lg);
}

.data-table {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.data-table :deep(.el-table__header th) {
  background: var(--bg-tertiary) !important;
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 13px;
}

.data-table :deep(.el-table__row) {
  transition: background 0.2s ease;
}

.data-table :deep(.el-table__row:hover > td) {
  background: var(--bg-tertiary) !important;
}

.type-cell {
  display: flex;
  align-items: center;
}

.resource-names {
  font-size: 13px;
  color: var(--text-secondary);
}

.date-cell {
  font-size: 13px;
  color: var(--text-secondary);
}

.price-original {
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: line-through;
}

.price-paid {
  font-size: 14px;
  font-weight: 600;
  color: var(--success);
}

.text-muted {
  color: var(--text-muted);
  font-size: 13px;
}

.pagination-wrap {
  margin-top: var(--spacing-lg);
  display: flex;
  justify-content: flex-end;
}

/* 响应式 */
@media (max-width: 1200px) {
  .overview-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .overview-cards .overview-card:last-child {
    grid-column: span 2;
  }
}

@media (max-width: 768px) {
  .overview-cards {
    grid-template-columns: 1fr;
  }

  .overview-cards .overview-card:last-child {
    grid-column: span 1;
  }

  .activation-form {
    flex-direction: column;
  }

  .activation-btn {
    width: 100%;
  }
}
</style>
