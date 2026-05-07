<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>注册码管理</h2>
        <span class="header-desc">生成和管理注册码</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="openGenerateDialog">
          <el-icon><Plus /></el-icon>
          生成注册码
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索注册码"
          style="width: 200px"
          clearable
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select
          v-if="isPlatformAdmin"
          v-model="searchMerchantId"
          placeholder="选择商户"
          style="width: 180px"
          clearable
          @change="handleSearch"
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
        <el-button @click="handleSearch">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button
          v-if="isPlatformAdmin"
          type="danger"
          :disabled="selectedCodes.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedCodes.length }})
        </el-button>
      </div>

      <div class="table-container">
        <el-table
          :data="tableData"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
          @selection-change="handleSelectionChange"
        >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="code" label="注册码" min-width="180">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isPlatformAdmin" prop="merchantName" label="商户" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.merchantName">{{ row.merchantName }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'unused' ? 'success' : 'info'" size="small">
              {{ row.status === 'unused' ? '未使用' : '已使用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="usedByAgentId" label="绑定的Agent" width="180">
          <template #default="{ row }">
            <span v-if="row.usedByAgentId" class="text-muted">{{ row.usedByAgentId }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'unused'"
              type="primary"
              link
              size="small"
              @click="copyCode(row.code)"
            >
              复制
            </el-button>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </div>

    <el-dialog
      v-model="showGenerateDialog"
      title="生成注册码"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form :model="generateForm" label-width="80px" class="dialog-form">
        <el-form-item v-if="isPlatformAdmin" label="所属商户" required>
          <el-select
            v-model="generateForm.merchantId"
            placeholder="请选择商户"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="merchant in merchantList"
              :key="merchant.id"
              :label="merchant.name"
              :value="merchant.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="生成数量">
          <el-input-number
            v-model="generateForm.count"
            :min="1"
            :max="100"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleGenerate">
          生成
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showCodeDialogVisible"
      title="注册码生成成功"
      width="600px"
    >
      <div class="generated-code-box">
        <p class="label">请妥善保存以下注册码：</p>
        <div class="code-list">
          <div v-for="code in generatedCodes" :key="code" class="code-item">
            <span class="code">{{ code }}</span>
            <el-button type="primary" link @click="copyCode(code)">
              <el-icon><CopyDocument /></el-icon>
            </el-button>
          </div>
        </div>
        <p class="tip">注册码只显示一次，请及时保存！</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="showCodeDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, CopyDocument, Delete } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { merchantApi, registrationCodeApi } from '@/api'

const authStore = useAuthStore()

const isPlatformAdmin = computed(() => authStore.isPlatformAdmin)

const loading = ref(false)
const submitLoading = ref(false)
const showGenerateDialog = ref(false)
const showCodeDialogVisible = ref(false)
const generatedCodes = ref([])
const tableData = ref([])
const merchantList = ref([])
const selectedCodes = ref([])

const searchKeyword = ref('')
const searchMerchantId = ref('')

const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const generateForm = reactive({
  merchantId: '',
  count: 1
})

const openGenerateDialog = async () => {
  generateForm.count = 1
  generateForm.merchantId = ''
  if (isPlatformAdmin.value && merchantList.value.length === 0) {
    await loadMerchantList()
  }
  showGenerateDialog.value = true
}

const handleSearch = () => {
  pagination.pageNum = 1
  loadCodes()
}

const loadCodes = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    if (isPlatformAdmin.value && searchMerchantId.value) {
      params.merchantId = searchMerchantId.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    const res = await registrationCodeApi.list(params)
    if (res.code === 0 || res.code === 200) {
      tableData.value = res.data?.records || []
      pagination.total = res.data?.total || 0
    }
  } catch (error) {
    console.error('Failed to load registration codes:', error)
  } finally {
    loading.value = false
  }
}

const loadMerchantList = async () => {
  if (!isPlatformAdmin.value) {
    merchantList.value = []
    return
  }
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchants:', error)
    merchantList.value = []
  }
}

const handleGenerate = async () => {
  if (isPlatformAdmin.value && !generateForm.merchantId) {
    ElMessage.warning('请选择商户')
    return
  }

  submitLoading.value = true
  try {
    const requestData = {
      count: generateForm.count
    }
    if (isPlatformAdmin.value) {
      requestData.merchantId = generateForm.merchantId
    }

    const res = await registrationCodeApi.generate(requestData)

    if (res.code === 0 || res.code === 200) {
      generatedCodes.value = res.data || []
      showGenerateDialog.value = false
      showCodeDialogVisible.value = true
      loadCodes()
      ElMessage.success('生成成功')
    } else {
      ElMessage.error(res.message || '生成失败')
    }
  } catch (error) {
    ElMessage.error('生成失败')
  } finally {
    submitLoading.value = false
  }
}

const handleSelectionChange = (selection) => {
  selectedCodes.value = selection
}

const handleDelete = async (row) => {
  if (row.status !== 'unused') {
    ElMessage.warning('只能删除未使用的注册码')
    return
  }

  await ElMessageBox.confirm(
    `确定要删除注册码 ${row.code} 吗？此操作不可恢复！`,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )

  try {
    await registrationCodeApi.delete([row.id])
    ElMessage.success('删除成功')
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

const handleBatchDelete = async () => {
  if (selectedCodes.value.length === 0) {
    ElMessage.warning('请先选择要删除的注册码')
    return
  }

  const unusedCodes = selectedCodes.value.filter(item => item.status === 'unused')
  if (unusedCodes.length === 0) {
    ElMessage.warning('只能删除未使用的注册码')
    return
  }

  const usedCount = selectedCodes.value.length - unusedCodes.length
  const message = usedCount > 0
    ? `选中了 ${selectedCodes.value.length} 个注册码，其中 ${usedCount} 个已使用将无法删除。确定删除 ${unusedCodes.length} 个未使用的注册码吗？`
    : `确定要删除选中的 ${unusedCodes.length} 个未使用注册码吗？此操作不可恢复！`

  await ElMessageBox.confirm(
    message,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )

  try {
    const ids = unusedCodes.map(item => item.id)
    await registrationCodeApi.delete(ids)
    ElMessage.success(`成功删除 ${ids.length} 个注册码`)
    selectedCodes.value = []
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success('注册码已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

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

onMounted(() => {
  loadCodes()
  if (isPlatformAdmin.value) {
    loadMerchantList()
  }
})
</script>

<style scoped>
.page-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px;
}

.header-desc {
  font-size: 13px;
  color: #8a8a8a;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.03);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.15);
  --el-table-current-row-bg-color: rgba(99, 102, 241, 0.1);
  --el-table-border-color: rgba(255, 255, 255, 0.06);
  --el-table-header-border-color: rgba(255, 255, 255, 0.06);
  --el-table-text-color: #b0b0b0;
  --el-table-header-text-color: #888888;
  --el-table-row-hover-text-color: #ffffff;
}

:deep(.el-table__inner-wrapper::before) {
  display: none;
}

:deep(.el-table .el-table__row) {
  background: transparent !important;
}

:deep(.el-table .el-table__row:hover > td) {
  background: rgba(99, 102, 241, 0.15) !important;
}

:deep(.el-table th.el-table__cell) {
  font-weight: 500;
  font-size: 13px;
}

:deep(.el-table td.el-table__cell) {
  font-size: 13px;
  padding: 14px 0;
}

.code-text {
  font-family: 'Consolas', 'Monaco', monospace;
  color: #a78bfa;
  font-size: 13px;
}

.text-muted {
  color: #6b7280;
}

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

:deep(.el-dialog) {
  background: rgba(18, 18, 26, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 20px 24px;
}

:deep(.el-dialog__title) {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
}

:deep(.el-form-item__label) {
  color: #b0b0b0;
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

:deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

.generated-code-box {
  padding: 10px 0;
}

.generated-code-box .label {
  color: #8a8a8a;
  margin-bottom: 16px;
}

.generated-code-box .code-list {
  max-height: 300px;
  overflow-y: auto;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 12px;
}

.generated-code-box .code-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.generated-code-box .code-item:last-child {
  border-bottom: none;
}

.generated-code-box .code {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 14px;
  color: #ffffff;
}

.generated-code-box .tip {
  color: #f59e0b;
  font-size: 12px;
  margin-top: 16px;
}
</style>
