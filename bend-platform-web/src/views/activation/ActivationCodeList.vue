<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>激活码管理</h2>
        <span class="header-desc">生成和管理激活码</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showGenerateDialog">
          <el-icon><Plus /></el-icon>
          生成激活码
        </el-button>
      </div>
    </div>

    <!-- 激活码列表 -->
    <div class="content-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索激活码"
          style="width: 200px"
          clearable
          @keyup.enter="loadCodes"
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
          @change="loadCodes"
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
        <el-button @click="loadCodes">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button
          v-if="authStore.isPlatformAdmin"
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
          :data="filteredCodes"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
          @selection-change="handleSelectionChange"
        >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="code" label="激活码" min-width="220">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.merchantName">{{ row.merchantName }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="vipType" label="VIP类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="warning" size="small">
              {{ getVipTypeText(row.vipType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getCodeStatusType(row.status)" size="small">
              {{ getCodeStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="usedByName" label="使用者" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.usedByName">{{ row.usedByName }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="usedTime" label="使用时间" width="170">
          <template #default="{ row }">
            {{ row.usedTime ? formatDate(row.usedTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="expireTime" label="过期时间" width="170">
          <template #default="{ row }">
            {{ row.expireTime ? formatDate(row.expireTime) : '永不过期' }}
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
          @size-change="loadCodes"
          @current-change="loadCodes"
        />
      </div>
    </div>

    <!-- 生成激活码对话框 -->
    <el-dialog
      v-model="generateDialogVisible"
      title="生成激活码"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="generateFormRef"
        :model="generateFormData"
        :rules="generateFormRules"
        label-width="80px"
        class="dialog-form"
      >
        <el-form-item v-if="isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="generateFormData.merchantId"
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
        <el-form-item label="批次名称" prop="batchName">
          <el-input v-model="generateFormData.batchName" placeholder="请输入批次名称（可选）" />
        </el-form-item>
        <el-form-item label="生成数量" prop="count">
          <el-input-number
            v-model="generateFormData.count"
            :min="1"
            :max="100"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="过期时间" prop="expireTime">
          <el-date-picker
            v-model="generateFormData.expireTime"
            type="datetime"
            placeholder="选择过期时间（可选）"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleGenerate">
          生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 生成的激活码展示对话框 -->
    <el-dialog
      v-model="showCodeDialogVisible"
      title="激活码生成成功"
      width="420px"
    >
      <div class="generated-code-box">
        <p class="label">请妥善保存以下激活码：</p>
        <div class="code-display">
          <span class="code">{{ generatedCode }}</span>
          <el-button type="primary" link @click="copyCode(generatedCode)">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </div>
        <p class="tip">激活码只显示一次，请及时保存！</p>
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
import { activationApi, merchantApi } from '@/api'
import { getVipTypeText, getCodeStatusText, getCodeStatusType } from '@/utils/constants'

/**
 * 激活码管理页面
 * 提供单个激活码的生成、查看、复制和删除功能
 * 激活码只能使用一次，使用后状态变为已使用
 */

// ==================== 状态定义 ====================

const authStore = useAuthStore()

const isPlatformAdmin = computed(() => authStore.isPlatformAdmin)

const merchantList = ref([])

/**
 * 表格加载状态
 */
const loading = ref(false)

/**
 * 提交按钮加载状态
 */
const submitLoading = ref(false)

/**
 * 激活码列表数据
 */
const tableData = ref([])

/**
 * 选中的激活码列表
 */
const selectedCodes = ref([])

/**
 * 搜索关键词
 */
const searchKeyword = ref('')

/**
 * 商户查询条件
 */
const searchMerchantId = ref('')

/**
 * 分页参数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 20,
  total: 0
})

/**
 * 过滤后的激活码列表
 */
const filteredCodes = computed(() => {
  if (!searchKeyword.value) return tableData.value
  const keyword = searchKeyword.value.toLowerCase()
  return tableData.value.filter(c =>
    c.code.toLowerCase().includes(keyword)
  )
})

/**
 * 生成对话框状态
 */
const generateDialogVisible = ref(false)
const generateFormRef = ref(null)

/**
 * 生成表单数据
 */
const generateFormData = reactive({
  merchantId: '',
  batchName: '',
  vipType: '',
  count: 1,
  expireTime: null
})

/**
 * 生成表单验证规则
 */
const generateFormRules = {
  vipType: [
    { required: true, message: '请选择VIP类型', trigger: 'change' }
  ]
}

/**
 * 激活码展示对话框状态
 */
const showCodeDialogVisible = ref(false)
const generatedCode = ref('')

// ==================== 方法定义 ====================

/**
 * 加载激活码列表
 */
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
    const res = await activationApi.listCodes(params)
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load activation codes:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 加载商户列表
 */
const loadMerchantList = async () => {
  if (!isPlatformAdmin.value) {
    merchantList.value = []
    return
  }
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchant list:', error)
    merchantList.value = []
  }
}

/**
 * 显示生成对话框
 */
const showGenerateDialog = async () => {
  generateFormData.merchantId = ''
  generateFormData.batchName = ''
  generateFormData.vipType = ''
  generateFormData.count = 1
  generateFormData.expireTime = null
  await loadMerchantList()
  generateDialogVisible.value = true
}

/**
 * 生成激活码
 */
const handleGenerate = async () => {
  const valid = await generateFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    const res = await activationApi.generateBatch({
      merchantId: generateFormData.merchantId || null,
      batchName: generateFormData.batchName || null,
      vipType: generateFormData.vipType,
      count: generateFormData.count,
      expireTime: generateFormData.expireTime
    })
    generatedCode.value = res.data ? `批次 ${res.data.batchName || ''} 创建成功` : '创建成功'
    generateDialogVisible.value = false
    showCodeDialogVisible.value = true
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 复制激活码
 * @param {string} code - 激活码
 */
const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success('激活码已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

/**
 * 处理表格选择变化
 * @param {Array} selection - 选中的行数据
 */
const handleSelectionChange = (selection) => {
  selectedCodes.value = selection
}

/**
 * 批量删除激活码（仅能删除未使用的）
 */
const handleBatchDelete = async () => {
  if (selectedCodes.value.length === 0) {
    ElMessage.warning('请先选择要删除的激活码')
    return
  }

  const unusedCodes = selectedCodes.value.filter(item => item.status === 'unused')
  if (unusedCodes.length === 0) {
    ElMessage.warning('只能删除未使用的激活码')
    return
  }

  const usedCount = selectedCodes.value.length - unusedCodes.length
  const message = usedCount > 0
    ? `选中了 ${selectedCodes.value.length} 个激活码，其中 ${usedCount} 个已使用将无法删除。确定删除 ${unusedCodes.length} 个未使用的激活码吗？`
    : `确定要删除选中的 ${unusedCodes.length} 个未使用激活码吗？此操作不可恢复！`

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
    await activationApi.deleteBatch(ids)
    ElMessage.success(`成功删除 ${ids.length} 个激活码`)
    selectedCodes.value = []
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 格式化日期时间
 * @param {string} dateStr - 日期字符串
 * @returns {string} 格式化后的日期
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

.text-warning {
  color: #f59e0b;
  font-size: 13px;
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
  text-align: center;
  padding: 20px 0;
}

.generated-code-box .label {
  color: #8a8a8a;
  font-size: 14px;
  margin-bottom: 16px;
}

.generated-code-box .code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 10px;
  margin-bottom: 12px;
}

.generated-code-box .code {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 18px;
  font-weight: 600;
  color: #a78bfa;
  letter-spacing: 1px;
}

.generated-code-box .tip {
  color: #f59e0b;
  font-size: 12px;
}
</style>