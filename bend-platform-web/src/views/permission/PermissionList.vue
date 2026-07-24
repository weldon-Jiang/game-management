<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>权限管理</h2>
        <span class="header-desc">管理商户使用权限：到期时间 / 配额 / 续期 / 停用</span>
      </div>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          创建权限
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="filterMerchantId" placeholder="按商户筛选" clearable filterable style="width: 220px" @change="handleFilterChange">
        <el-option v-for="m in merchantOptions" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="按状态筛选" clearable style="width: 140px" @change="handleFilterChange">
        <el-option label="有效" value="active" />
        <el-option label="已到期" value="expired" />
        <el-option label="已停用" value="suspended" />
      </el-select>
    </div>

    <div class="content-card table-container">
      <el-table :data="tableData" v-loading="loading" class="data-table">
        <el-table-column prop="merchantId" label="商户" width="150">
          <template #default="{ row }">
            <span class="merchant-name">{{ getMerchantName(row.merchantId) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)" size="small" effect="light">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expireAt" label="到期时间" width="170">
          <template #default="{ row }">
            <span :class="{ 'expired-text': isExpired(row) }">{{ formatDate(row.expireAt) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="maxAgents" label="最大Agent数" width="110" align="center" />
        <el-table-column prop="maxTasks" label="最大任务数" width="110" align="center" />
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 'active' || row.status === 'expired'" type="primary" link size="small" @click="showRenewDialog(row)">
              续期
            </el-button>
            <el-button v-if="row.status === 'active'" type="warning" link size="small" @click="handleSuspend(row)">
              停用
            </el-button>
            <el-button v-if="row.status === 'suspended'" type="success" link size="small" @click="handleResume(row)">
              启用
            </el-button>
            <span v-if="!['active', 'expired', 'suspended'].includes(row.status)" class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum" v-model:page-size="pagination.pageSize"
          :total="pagination.total" :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next" @change="loadData"
        />
      </div>
    </div>

    <!-- 创建/续期对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="480px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item v-if="dialogType === 'create'" label="选择商户" prop="merchantId">
          <el-select v-model="form.merchantId" placeholder="请选择商户" filterable style="width: 100%">
            <el-option v-for="m in merchantOptions" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dialogType === 'renew'" label="商户">
          <span class="info-text">{{ getMerchantName(renewTarget?.merchantId) }}</span>
        </el-form-item>
        <el-form-item v-if="dialogType === 'renew'" label="当前到期">
          <span class="info-text">{{ formatDate(renewTarget?.expireAt) }}</span>
        </el-form-item>
        <el-form-item label="到期时间" prop="expireAt">
          <el-date-picker
            v-model="form.expireAt" type="datetime" placeholder="选择到期时间"
            format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="最大Agent数" v-if="dialogType === 'create'">
          <el-input-number v-model="form.maxAgents" :min="1" :max="999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="最大任务数" v-if="dialogType === 'create'">
          <el-input-number v-model="form.maxTasks" :min="1" :max="9999" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ dialogType === 'create' ? '确定创建' : '确定续期' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 商户使用权限管理：创建 / 续期 / 停用 / 恢复。
 * License 只负责软件授权，到期和配额由 Permission 控制。
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { permissionApi, merchantApi } from '@/api'

const loading = ref(false)
const tableData = ref([])
const merchantOptions = ref([])
const pagination = reactive({ pageNum: 1, pageSize: 10, total: 0 })

const filterMerchantId = ref('')
const filterStatus = ref('')

// 对话框
const dialogVisible = ref(false)
const dialogType = ref('create') // 'create' | 'renew'
const submitLoading = ref(false)
const formRef = ref(null)
const form = reactive({ merchantId: '', expireAt: '', maxAgents: 5, maxTasks: 50 })
const formRules = {
  merchantId: [{ required: true, message: '请选择商户', trigger: 'change' }],
  expireAt: [{ required: true, message: '请选择到期时间', trigger: 'change' }]
}
const renewTarget = ref(null)

const dialogTitle = computed(() => dialogType.value === 'create' ? '创建权限' : '续期权限')

const loadMerchants = async () => {
  try { const res = await merchantApi.listAll(); merchantOptions.value = res.data || [] }
  catch (e) { console.error('Failed to load merchants:', e) }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: pagination.pageNum, pageSize: pagination.pageSize }
    if (filterMerchantId.value) params.merchantId = filterMerchantId.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await permissionApi.list(params)
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (e) { console.error('Failed to load permissions:', e) }
  finally { loading.value = false }
}

// 筛选条件变更时回到第 1 页，避免在深页码上筛选得到空结果
const handleFilterChange = () => {
  pagination.pageNum = 1
  loadData()
}

const getMerchantName = (id) => {
  const m = merchantOptions.value.find(x => x.id === id)
  return m ? m.name : id
}

// --- 创建 ---
const showCreateDialog = () => {
  dialogType.value = 'create'
  form.merchantId = ''
  form.expireAt = ''
  form.maxAgents = 5
  form.maxTasks = 50
  dialogVisible.value = true
}

// --- 续期 ---
const showRenewDialog = (row) => {
  dialogType.value = 'renew'
  renewTarget.value = row
  form.expireAt = ''
  form.merchantId = '' // not used for renew
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!form.expireAt) { ElMessage.warning('请选择到期时间'); return }
  if (dialogType.value === 'create') {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
  }
  submitLoading.value = true
  try {
    if (dialogType.value === 'create') {
      await permissionApi.create({
        merchantId: form.merchantId,
        expireAt: form.expireAt,
        maxAgents: form.maxAgents,
        maxTasks: form.maxTasks
      })
      ElMessage.success('权限创建成功')
    } else {
      await permissionApi.renew(renewTarget.value.id, form.expireAt)
      ElMessage.success('续期成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (e) { /* 拦截器已处理 */ }
  finally { submitLoading.value = false }
}

// --- 停用 ---
const handleSuspend = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要停用商户「${getMerchantName(row.merchantId)}」的使用权限吗？分控将无法操作。`, '停用权限', { type: 'warning' })
    await permissionApi.suspend(row.id)
    ElMessage.success('已停用')
    loadData()
  } catch (e) { if (e !== 'cancel' && e !== 'close') { /* ignore */ } }
}

// --- 恢复 ---
const handleResume = async (row) => {
  try {
    await permissionApi.resume(row.id)
    ElMessage.success('已启用')
    loadData()
  } catch (e) { /* 拦截器已处理 */ }
}

const getStatusTag = (s) => ({ active: 'success', expired: 'danger', suspended: 'warning' }[s] || 'info')
const getStatusText = (s) => ({ active: '有效', expired: '已到期', suspended: '已停用' }[s] || s)

const isExpired = (row) => row.expireAt && new Date(row.expireAt) < new Date()

const formatDate = (d) => {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => { loadMerchants(); loadData() })
</script>

<style scoped>
.filter-bar { display: flex; gap: var(--spacing-md); margin-top: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
.merchant-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.expired-text { color: var(--danger); font-weight: 500; }
.text-muted { color: var(--text-muted); font-size: 13px; }
.info-text { font-size: 14px; color: var(--text-primary); }
.table-container { padding: var(--spacing-lg); }
.data-table { width: 100%; }
:deep(.el-table__body-wrapper .el-table__row:hover td.el-table__cell) { background-color: #1a1a2e !important; }
:deep(.el-table__fixed-right:hover), :deep(.el-table__fixed:hover) { background-color: #0f0f1a !important; }
:deep(.el-table__fixed-right .el-table__row:hover td) { background-color: #0f0f1a !important; }
.pagination-wrap { margin-top: var(--spacing-lg); display: flex; justify-content: flex-end; }
</style>
