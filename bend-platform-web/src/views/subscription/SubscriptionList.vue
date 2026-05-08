<template>
  <div class="page-container subscription-list">
    <div class="page-header">
      <h2>订阅管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showRechargeDialog">
          激活/续费
        </el-button>
      </div>
    </div>

    <div class="stats-cards">
      <div class="stat-card balance-card">
        <div class="stat-label">当前点数</div>
        <div class="stat-value">{{ balance?.balance || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">累计充值</div>
        <div class="stat-value">{{ balance?.totalRecharged || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">累计消耗</div>
        <div class="stat-value">{{ balance?.totalConsumed || 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃订阅</div>
        <div class="stat-value">{{ activeCount }}</div>
      </div>
      <div class="stat-card vip-card">
        <div class="stat-label">VIP等级</div>
        <div class="stat-value vip-level">VIP{{ merchantVipLevel || 0 }}</div>
      </div>
      <div class="stat-card status-card" :class="subscriptionStatus === 'active' ? 'active' : 'inactive'">
        <div class="stat-label">商户状态</div>
        <div class="stat-value">
          <el-tag :type="subscriptionStatus === 'active' ? 'success' : 'danger'" size="small">
            {{ subscriptionStatus === 'active' ? '正常' : '未激活' }}
          </el-tag>
        </div>
        <div class="stat-sub" v-if="subscriptionStatus !== 'active'">
          请联系管理员
        </div>
      </div>
    </div>

    <div class="content-card">
      <div class="table-filters">
        <el-select v-model="filterStatus" placeholder="订阅状态" clearable style="width: 120px">
          <el-option label="全部" value="" />
          <el-option label="生效中" value="active" />
          <el-option label="已过期" value="expired" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-button @click="loadData">刷新</el-button>
      </div>

      <el-table :data="tableData" v-loading="loading">
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            {{ getTypeName(row.type) }}
          </template>
        </el-table-column>
        <el-table-column prop="targetName" label="订阅目标" min-width="150" show-overflow-tooltip />
        <el-table-column prop="pointsCost" label="消耗点数" width="100" />
        <el-table-column prop="durationDays" label="时长(天)" width="100" />
        <el-table-column label="有效期" width="200">
          <template #default="{ row }">
            {{ formatDate(row.startTime) }} ~ {{ formatDate(row.expireTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'active'">
              <el-button type="primary" link size="small" @click="showRenewDialog(row)">续费</el-button>
              <el-button type="warning" link size="small" @click="handleCancel(row)">取消</el-button>
            </template>
            <el-button type="info" link size="small" @click="showDetail(row)">详情</el-button>
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
          @change="loadData"
        />
      </div>
    </div>

    <el-dialog v-model="rechargeDialogVisible" title="激活/续费" width="450px">
      <el-form ref="rechargeFormRef" :model="rechargeForm" :rules="rechargeRules" label-width="80px">
        <el-form-item label="激活码" prop="activationCode">
          <el-input
            v-model="rechargeForm.activationCode"
            placeholder="请输入激活码"
            @blur="previewActivationCode"
            @input="activationPreview = null"
          />
        </el-form-item>
        <div v-if="activationPreview" class="activation-preview">
          <el-divider content-position="left">激活内容预览</el-divider>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="类型">
              <el-tag :type="getPreviewTypeTag(activationPreview.type)" size="small">
                {{ activationPreview.typeName }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="内容">
              <template v-if="activationPreview.type === 'points'">
                {{ activationPreview.points }} 点数
              </template>
              <template v-else>
                {{ activationPreview.targetName || '-' }}
                <br />
                <small class="text-muted">时长: {{ activationPreview.durationDays || 0 }}天</small>
              </template>
            </el-descriptions-item>
          </el-descriptions>
          <el-alert
            v-if="activationConflict?.hasConflict"
            type="warning"
            :title="activationConflict.message"
            :description="'当前已有' + activationConflict.activeTypeName + '「' + activationConflict.activeTargetName + '」的订阅'"
            show-icon
            :closable="false"
            style="margin-top: 16px;"
          />
          <div v-if="vipUpgradeInfo && !activationConflict?.hasConflict" class="vip-upgrade-info">
            <el-divider content-position="left">VIP升级预览</el-divider>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="当前VIP等级">
                VIP{{ vipUpgradeInfo.currentVipLevel }} ({{ vipUpgradeInfo.currentTotalPoints }} 点)
              </el-descriptions-item>
              <el-descriptions-item label="激活后">
                VIP{{ vipUpgradeInfo.newVipLevel }} ({{ vipUpgradeInfo.newTotalPoints }} 点)
              </el-descriptions-item>
            </el-descriptions>
            <el-alert
              v-if="vipUpgradeInfo.willUpgrade"
              type="success"
              :title="vipUpgradeInfo.upgradeMessage"
              :description="'恭喜！激活后您的VIP等级将从 VIP' + vipUpgradeInfo.currentVipLevel + ' 升级到 VIP' + vipUpgradeInfo.newVipLevel"
              show-icon
              :closable="false"
              style="margin-top: 12px;"
            />
            <div v-else-if="vipUpgradeInfo.pointsToNextLevel > 0" class="next-vip-hint">
              <small>再消费 {{ vipUpgradeInfo.pointsToNextLevel }} 点即可升级到 {{ vipUpgradeInfo.nextVipLevelName }}</small>
            </div>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="rechargeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rechargeLoading" :disabled="activationConflict?.hasConflict" @click="handleRecharge">
          {{ activationConflict?.hasConflict ? '存在冲突' : '充值' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="renewDialogVisible" title="续费订阅" width="400px">
      <el-form ref="renewFormRef" :model="renewForm" label-width="80px">
        <el-form-item label="订阅类型">
          {{ getTypeName(currentSubscription?.type) }}
        </el-form-item>
        <el-form-item label="订阅目标">
          {{ currentSubscription?.targetName }}
        </el-form-item>
        <el-form-item label="续费时长">
          <el-input-number v-model="renewForm.durationDays" :min="1" :max="365" /> 天
        </el-form-item>
        <el-form-item label="消耗点数">
          {{ renewForm.durationDays * getPricePerDay(currentSubscription?.type) }} 点
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="renewLoading" @click="handleRenew">确认续费</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { billingApi, subscriptionApi, vipApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const showVipCard = ref(false)
const merchantVipLevel = ref(0)
const subscriptionStatus = ref('inactive')
const loading = ref(false)
const tableData = ref([])
const balance = ref(null)
const activeCount = ref(0)
const filterStatus = ref('')
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const rechargeDialogVisible = ref(false)
const rechargeLoading = ref(false)
const rechargeFormRef = ref(null)
const rechargeForm = reactive({
  activationCode: ''
})
const rechargeRules = {
  activationCode: [{ required: true, message: '请输入激活码', trigger: 'blur' }]
}
const activationPreview = ref(null)
const activationConflict = ref(null)
const vipUpgradeInfo = ref(null)

const renewDialogVisible = ref(false)
const renewLoading = ref(false)
const renewFormRef = ref(null)
const currentSubscription = ref(null)
const renewForm = reactive({
  durationDays: 30
})

const typeNames = {
  points: '点数',
  host: '主机',
  window: '窗口',
  account: '游戏号'
}

const statusNames = {
  active: '生效中',
  expired: '已过期',
  cancelled: '已取消',
  unbound: '已解绑'
}

const getTypeName = (type) => typeNames[type] || type || '点数'
const getStatusName = (status) => statusNames[status] || status

const getStatusType = (status) => {
  const map = {
    active: 'success',
    expired: 'info',
    cancelled: 'danger',
    unbound: 'warning'
  }
  return map[status] || 'info'
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN') + ' ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const getPricePerDay = (type) => {
  const prices = {
    host: 0.67,
    window: 0.5,
    account: 0.33
  }
  return prices[type] || 1
}

const getPreviewTypeTag = (type) => {
  const map = {
    'points': 'primary',
    'account': 'success',
    'window': 'warning',
    'host': 'danger'
  }
  return map[type] || 'info'
}

const previewActivationCode = async () => {
  if (!rechargeForm.activationCode || rechargeForm.activationCode.length < 6) {
    activationPreview.value = null
    activationConflict.value = null
    vipUpgradeInfo.value = null
    return
  }
  try {
    const res = await subscriptionApi.previewActivation(rechargeForm.activationCode)
    if (res.code === 200 || res.code === 0) {
      const data = res.data
      activationPreview.value = {
        type: data.subscriptionType || 'points',
        typeName: typeNames[data.subscriptionType] || '点数',
        points: data.points || 0,
        targetName: data.targetName || '-',
        durationDays: data.durationDays || 0
      }
      if (data.activeSubscriptionConflict) {
        activationConflict.value = {
          hasConflict: true,
          message: data.conflictMessage || '您已有活跃订阅，无法激活此激活码',
          activeTypeName: data.activeSubscriptionTypeName,
          activeTargetName: data.activeSubscriptionTargetName
        }
      } else {
        activationConflict.value = null
      }

      if (data.currentVipLevel !== undefined) {
        vipUpgradeInfo.value = {
          currentVipLevel: data.currentVipLevel,
          currentTotalPoints: data.currentTotalPoints || 0,
          newTotalPoints: data.newTotalPointsAfterActivation || 0,
          newVipLevel: data.newVipLevelAfterActivation || data.currentVipLevel,
          willUpgrade: data.willUpgradeVip || false,
          upgradeMessage: data.vipUpgradeMessage || '',
          pointsToNextLevel: data.pointsToNextVipLevel || 0,
          nextVipLevelName: data.nextVipLevelName || null
        }
      }
    } else {
      activationPreview.value = null
      activationConflict.value = null
      vipUpgradeInfo.value = null
    }
  } catch (error) {
    activationPreview.value = null
    activationConflict.value = null
    vipUpgradeInfo.value = null
  }
}

const loadBalance = async () => {
  try {
    const res = await billingApi.getBalance()
    balance.value = res.data

    const vipRes = await vipApi.getMyInfo()
    if (vipRes.code === 200 || vipRes.code === 0) {
      merchantVipLevel.value = vipRes.data?.currentVipLevel || 0
    }
  } catch (error) {
    console.error('Failed to load balance:', error)
  }
}

const loadSubscriptionStatus = async () => {
  try {
    const res = await subscriptionApi.getStatus()
    if (res.code === 200 || res.code === 0) {
      subscriptionStatus.value = res.data?.status || 'inactive'
    }
  } catch (error) {
    console.error('Failed to load subscription status:', error)
  }
}

const loadActiveCount = async () => {
  try {
    const res = await billingApi.listActiveSubscriptions()
    activeCount.value = res.data?.length || 0
  } catch (error) {
    console.error('Failed to load active subscriptions:', error)
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await billingApi.listSubscriptions({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize,
      status: filterStatus.value
    })
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load subscriptions:', error)
  } finally {
    loading.value = false
  }
}

const showRechargeDialog = () => {
  rechargeForm.activationCode = ''
  activationPreview.value = null
  activationConflict.value = null
  vipUpgradeInfo.value = null
  rechargeDialogVisible.value = true
}

const handleRecharge = async () => {
  const valid = await rechargeFormRef.value.validate().catch(() => false)
  if (!valid) return

  rechargeLoading.value = true
  try {
    const res = await subscriptionApi.activate(rechargeForm.activationCode)
    if (res.code === 200 || res.code === 0) {
      ElMessage.success('激活成功')
      rechargeDialogVisible.value = false
      rechargeForm.activationCode = ''
      loadSubscriptionStatus()
      loadBalance()
      loadData()
    }
  } catch (error) {
    console.error('Activate failed:', error)
  } finally {
    rechargeLoading.value = false
  }
}

const showRenewDialog = (row) => {
  currentSubscription.value = row
  renewForm.durationDays = 30
  renewDialogVisible.value = true
}

const handleRenew = async () => {
  if (!currentSubscription.value) return

  renewLoading.value = true
  try {
    const pointsCost = renewForm.durationDays * getPricePerDay(currentSubscription.value.type)
    await billingApi.renewSubscription(currentSubscription.value.id, {
      durationDays: renewForm.durationDays,
      pointsCost: Math.round(pointsCost)
    })
    ElMessage.success('续费成功')
    renewDialogVisible.value = false
    loadData()
    loadBalance()
  } catch (error) {
    console.error('Renew failed:', error)
  } finally {
    renewLoading.value = false
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定取消该订阅?', '警告', { type: 'warning' })
    await billingApi.cancelSubscription(row.id)
    ElMessage.success('订阅已取消')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Cancel failed:', error)
    }
  }
}

const showDetail = (row) => {
  ElMessageBox.alert(`
    <p><strong>订阅ID:</strong> ${row.id}</p>
    <p><strong>类型:</strong> ${getTypeName(row.type)}</p>
    <p><strong>目标:</strong> ${row.targetName}</p>
    <p><strong>消耗点数:</strong> ${row.pointsCost}</p>
    <p><strong>时长:</strong> ${row.durationDays}天</p>
    <p><strong>开始时间:</strong> ${formatDate(row.startTime)}</p>
    <p><strong>过期时间:</strong> ${formatDate(row.expireTime)}</p>
    <p><strong>状态:</strong> ${getStatusName(row.status)}</p>
  `, '订阅详情', {
    confirmButtonText: '关闭',
    dangerouslyUseHTMLString: true
  })
}

onMounted(() => {
  loadSubscriptionStatus()
  loadBalance()
  loadActiveCount()
  loadData()
})
</script>

<style scoped>
/* 组件特有样式，使用 CSS 变量 */

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xl);
}

.page-header h2 {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.stat-card {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  text-align: center;
}

.stat-card.balance-card {
  /* 使用和其他卡片一致的样式 */
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.table-filters {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.vip-card {
  background: linear-gradient(135deg, var(--warning-soft) 0%, rgba(217, 119, 6, 0.2) 100%);
  border: 1px solid var(--warning-soft);
}

.vip-card .stat-label {
  color: var(--warning);
}

.vip-level {
  color: var(--warning) !important;
  font-weight: 700;
}

.status-card {
  min-width: 140px;
}

.status-card.active {
  background: linear-gradient(135deg, rgba(103, 194, 58, 0.15) 0%, rgba(82, 160, 44, 0.15) 100%);
  border: 1px solid rgba(103, 194, 58, 0.3);
}

.status-card.inactive {
  background: linear-gradient(135deg, rgba(245, 108, 108, 0.15) 0%, rgba(204, 85, 85, 0.15) 100%);
  border: 1px solid rgba(245, 108, 108, 0.3);
}

.stat-sub {
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
.subscription-info small {
  font-size: 11px;
}

.activation-preview {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-soft);
  border-radius: var(--radius-md);
}

.activation-preview .text-muted {
  color: var(--text-muted);
  font-size: 12px;
}

.vip-upgrade-info {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-soft);
  border-radius: var(--radius-md);
}

.vip-upgrade-info .next-vip-hint {
  margin-top: var(--spacing-sm);
  color: var(--text-muted);
  font-size: var(--font-size-xs);
  text-align: center;
}
</style>
