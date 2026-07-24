<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>License管理</h2>
        <span class="header-desc">管理商户软件授权凭证（签发 / 吊销），使用权限请到「权限管理」配置</span>
      </div>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="primary" @click="showIssueDialog">
          <el-icon><Plus /></el-icon>
          签发License
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="filterMerchantId" placeholder="按商户筛选" clearable filterable style="width: 220px" @change="handleFilterChange">
        <el-option v-for="m in merchantOptions" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="按状态筛选" clearable style="width: 140px" @change="handleFilterChange">
        <el-option label="有效" value="active" />
        <el-option label="已吊销" value="revoked" />
        <el-option label="未激活" value="pending" />
      </el-select>
    </div>

    <div class="content-card table-container">
      <el-table :data="tableData" v-loading="loading" class="data-table">
        <el-table-column prop="merchantId" label="商户" width="150">
          <template #default="{ row }">
            <span class="merchant-name">{{ getMerchantName(row.merchantId) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="licenseKey" label="License Key" width="260" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)" size="small" effect="light">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastVerifiedAt" label="最后校验时间" width="170">
          <template #default="{ row }">{{ formatDate(row.lastVerifiedAt) }}</template>
        </el-table-column>
        <el-table-column prop="lastVerifyIp" label="最后校验IP" width="140">
          <template #default="{ row }">
            <span v-if="row.lastVerifyIp">{{ row.lastVerifyIp }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="签发时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdTime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              type="danger" link size="small"
              @click="handleRevoke(row)"
            >吊销</el-button>
            <span v-else class="text-muted">-</span>
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

    <!-- 签发对话框 -->
    <el-dialog v-model="issueDialogVisible" title="签发License" width="450px" :close-on-click-modal="false">
      <el-form ref="issueFormRef" :model="issueForm" :rules="issueFormRules" label-width="100px">
        <el-form-item label="选择商户" prop="merchantId">
          <el-select v-model="issueForm.merchantId" placeholder="请选择商户" filterable style="width: 100%">
            <el-option v-for="m in merchantOptions" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="机器指纹(可选)">
          <el-input v-model="issueForm.machineFingerprint" placeholder="预绑定机器指纹（留空则激活时自动绑定）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="issueLoading" @click="handleIssue">确定签发</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * License（软件授权凭证）管理：签发 / 吊销。
 * License 终身有效，不包含到期时间和使用配额。
 * 使用权限（到期/续期/配额）请到「权限管理」页面操作。
 */
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { licenseApi, merchantApi } from '@/api'

const loading = ref(false)
const tableData = ref([])
const merchantOptions = ref([])
const pagination = reactive({ pageNum: 1, pageSize: 10, total: 0 })

const filterMerchantId = ref('')
const filterStatus = ref('')

const issueDialogVisible = ref(false)
const issueLoading = ref(false)
const issueFormRef = ref(null)
const issueForm = reactive({ merchantId: '', machineFingerprint: '' })
const issueFormRules = {
  merchantId: [{ required: true, message: '请选择商户', trigger: 'change' }]
}

const loadMerchants = async () => {
  try {
    const res = await merchantApi.listAll()
    merchantOptions.value = res.data || []
  } catch (e) { console.error('Failed to load merchants:', e) }
}

const loadData = async () => {
  loading.value = true
  try {
    const params = { pageNum: pagination.pageNum, pageSize: pagination.pageSize }
    if (filterMerchantId.value) params.merchantId = filterMerchantId.value
    if (filterStatus.value) params.status = filterStatus.value
    const res = await licenseApi.list(params)
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (e) { console.error('Failed to load licenses:', e) }
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

const showIssueDialog = () => {
  issueForm.merchantId = ''
  issueForm.machineFingerprint = ''
  issueDialogVisible.value = true
}

const handleIssue = async () => {
  const valid = await issueFormRef.value?.validate().catch(() => false)
  if (!valid) return
  issueLoading.value = true
  try {
    await licenseApi.issue({
      merchantId: issueForm.merchantId,
      machineFingerprint: issueForm.machineFingerprint || undefined
    })
    ElMessage.success('License签发成功')
    issueDialogVisible.value = false
    loadData()
  } catch (e) { /* 拦截器已处理 */ }
  finally { issueLoading.value = false }
}

const handleRevoke = async (row) => {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      `确定要吊销商户「${getMerchantName(row.merchantId)}」的License吗？`,
      '吊销License',
      { confirmButtonText: '确定吊销', cancelButtonText: '取消', type: 'warning', inputPlaceholder: '吊销原因（可选）' }
    )
    await licenseApi.revoke(row.id, reason || '')
    ElMessage.success('已吊销')
    loadData()
  } catch (e) { if (e !== 'cancel' && e !== 'close') { /* ignore */ } }
}

const getStatusTag = (s) => ({ active: 'success', revoked: 'info', pending: 'warning' }[s] || 'info')
const getStatusText = (s) => ({ active: '有效', revoked: '已吊销', pending: '未激活' }[s] || s)

const formatDate = (d) => {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => { loadMerchants(); loadData() })
</script>

<style scoped>
.filter-bar { display: flex; gap: var(--spacing-md); margin-top: var(--spacing-lg); margin-bottom: var(--spacing-lg); }
.merchant-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
.text-muted { color: var(--text-muted); font-size: 13px; }
.table-container { padding: var(--spacing-lg); }
.data-table { width: 100%; }
:deep(.el-table__body-wrapper .el-table__row:hover td.el-table__cell) { background-color: #1a1a2e !important; }
:deep(.el-table__fixed-right:hover), :deep(.el-table__fixed:hover) { background-color: #0f0f1a !important; }
:deep(.el-table__fixed-right .el-table__row:hover td) { background-color: #0f0f1a !important; }
.pagination-wrap { margin-top: var(--spacing-lg); display: flex; justify-content: flex-end; }
</style>
