<template>
  <div class="page-container subscription-list">
    <div class="page-header">
      <h2>订阅管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="showRechargeDialog">
          充值点数
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

    <el-dialog v-model="rechargeDialogVisible" title="充值点数" width="400px">
      <el-form ref="rechargeFormRef" :model="rechargeForm" :rules="rechargeRules" label-width="80px">
        <el-form-item label="卡号" prop="cardNo">
          <el-input v-model="rechargeForm.cardNo" placeholder="请输入卡号" />
        </el-form-item>
        <el-form-item label="卡密" prop="cardPwd">
          <el-input v-model="rechargeForm.cardPwd" placeholder="请输入卡密" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rechargeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="rechargeLoading" @click="handleRecharge">充值</el-button>
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
import { billingApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
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
  cardNo: '',
  cardPwd: ''
})
const rechargeRules = {
  cardNo: [{ required: true, message: '请输入卡号', trigger: 'blur' }],
  cardPwd: [{ required: true, message: '请输入卡密', trigger: 'blur' }]
}

const renewDialogVisible = ref(false)
const renewLoading = ref(false)
const renewFormRef = ref(null)
const currentSubscription = ref(null)
const renewForm = reactive({
  durationDays: 30
})

const typeNames = {
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

const getTypeName = (type) => typeNames[type] || type
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

const getPricePerDay = (type) => {
  const prices = {
    host: 0.67,
    window: 0.5,
    account: 0.33
  }
  return prices[type] || 1
}

const loadBalance = async () => {
  try {
    const res = await billingApi.getBalance()
    balance.value = res.data
  } catch (error) {
    console.error('Failed to load balance:', error)
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
  rechargeForm.cardNo = ''
  rechargeForm.cardPwd = ''
  rechargeDialogVisible.value = true
}

const handleRecharge = async () => {
  const valid = await rechargeFormRef.value.validate().catch(() => false)
  if (!valid) return

  rechargeLoading.value = true
  try {
    await billingApi.recharge(rechargeForm.cardNo, rechargeForm.cardPwd)
    ElMessage.success('充值成功')
    rechargeDialogVisible.value = false
    loadBalance()
  } catch (error) {
    console.error('Recharge failed:', error)
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
  loadBalance()
  loadActiveCount()
  loadData()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
}

.stat-card.balance-card {
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
  border-color: rgba(99, 102, 241, 0.3);
}

.stat-label {
  font-size: 13px;
  color: #8a8a8a;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #ffffff;
}

.table-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
