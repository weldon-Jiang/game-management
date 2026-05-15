<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>游戏账号</h2>
        <span class="header-desc">管理Xbox游戏账号</span>
      </div>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button @click="showImportDialog">
          批量导入
        </el-button>
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增账号
        </el-button>
      </div>
    </div>

    <div class="content-card table-container">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
      >
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="150" />
        <el-table-column prop="streamingName" label="关联流媒体账号" min-width="150" show-overflow-tooltip />
        <el-table-column prop="xboxGameName" label="Xbox玩家名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="xboxLiveEmail" label="Xbox邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column prop="isActive" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.isActive)" size="small">
              {{ getStatusText(row.isActive) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="isPrimary" label="主账号" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.isPrimary" type="warning" size="small">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center">
          <template #default="{ row }">
            {{ row.priority ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="dailyMatchLimit" label="每日限制" width="90" align="center">
          <template #default="{ row }">
            <span>{{ row.todayMatchCount ?? 0 }}/{{ row.dailyMatchLimit ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="totalMatchCount" label="总场次" width="80" align="center">
          <template #default="{ row }">
            {{ row.totalMatchCount ?? 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="lastUsedTime" label="最后使用" width="170">
          <template #default="{ row }">
            {{ formatDate(row.lastUsedTime) }}
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '新增游戏账号' : '编辑游戏账号'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="110px"
        class="dialog-form"
      >
        <el-form-item v-if="authStore.isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="formData.merchantId"
            placeholder="请选择商户"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="merchant in merchantList"
              :key="merchant.id"
              :label="merchant.name"
              :value="merchant.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Xbox玩家名" prop="xboxGameName">
          <el-input v-model="formData.xboxGameName" placeholder="请输入Xbox玩家名称" />
        </el-form-item>
        <el-form-item label="Xbox邮箱" prop="xboxLiveEmail">
          <el-input v-model="formData.xboxLiveEmail" placeholder="请输入Xbox邮箱" />
        </el-form-item>
        <el-form-item label="Xbox密码" prop="xboxLivePassword">
          <el-input
            v-model="formData.xboxLivePassword"
            type="password"
            placeholder="请输入Xbox密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="批量导入游戏账号"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="import-template">
        <h4>导入说明</h4>
        <ol>
          <li>请先点击"下载模板"按钮获取导入模板</li>
          <li>按照模板格式填写游戏账号信息</li>
          <li>上传填写好的CSV文件</li>
          <li>系统会验证数据格式和重复情况</li>
          <li>验证通过后点击"开始导入"</li>
        </ol>
      </div>
      <el-form-item v-if="authStore.isPlatformAdmin" label="导入到商户">
        <el-select
          v-model="importMerchantId"
          placeholder="请选择商户"
          style="width: 100%"
          filterable
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
      </el-form-item>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="handleFileChange"
        :file-list="fileList"
        class="upload-component"
      >
        <template #trigger>
          <el-button>选择CSV文件</el-button>
        </template>
        <template #tip>
          <div class="el-upload__tip">只能上传CSV文件</div>
        </template>
      </el-upload>
      <div v-if="importResult" class="import-result">
        <el-alert
          :title="`导入完成：成功 ${importResult.successCount} 条，失败 ${importResult.failCount} 条`"
          :type="importResult.failCount > 0 ? 'warning' : 'success'"
          show-icon
        >
          <template v-if="importResult.errors && importResult.errors.length > 0">
            <div v-for="(err, idx) in importResult.errors.slice(0, 10)" :key="idx" class="error-item">
              {{ err }}
            </div>
            <div v-if="importResult.errors.length > 10" class="error-more">
              还有 {{ importResult.errors.length - 10 }} 条错误...
            </div>
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="handleDownloadTemplate">下载模板</el-button>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" :disabled="!selectedFile" @click="handleImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { gameAccountApi, merchantApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

/**
 * 游戏账号管理页面
 * 提供游戏账号的增删改查功能
 */

// ==================== 状态定义 ====================

/**
 * 表格数据加载状态
 */
const loading = ref(false)

/**
 * 提交按钮加载状态
 */
const submitLoading = ref(false)

/**
 * 表格数据列表
 */
const tableData = ref([])

/**
 * 分页参数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

/**
 * 对话框状态
 */
const dialogVisible = ref(false)
const dialogType = ref('add')
const formRef = ref(null)
const importDialogVisible = ref(false)
const uploadRef = ref(null)
const fileList = ref([])
const selectedFile = ref(null)
const importLoading = ref(false)
const importResult = ref(null)
const merchantList = ref([])
const importMerchantId = ref('')

/**
 * 表单数据
 */
const formData = reactive({
  id: '',
  merchantId: '',
  xboxGameName: '',
  xboxLiveEmail: '',
  xboxLivePassword: ''
})

/**
 * 表单验证规则
 */
const formRules = {
  merchantId: [
    { required: true, message: '请选择商户', trigger: 'change' }
  ],
  xboxGameName: [
    { required: true, message: '请输入Xbox玩家名称', trigger: 'blur' }
  ],
  xboxLiveEmail: [
    { required: true, message: '请输入Xbox邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

// ==================== 方法定义 ====================

/**
 * 加载游戏账号列表
 */
const loadData = async () => {
  loading.value = true
  tableData.value = []
  try {
    const res = await gameAccountApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load game accounts:', error)
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增对话框
 */
const showAddDialog = async () => {
  dialogType.value = 'add'
  formData.id = ''
  formData.merchantId = authStore.isPlatformAdmin ? '' : authStore.merchantId
  formData.xboxGameName = ''
  formData.xboxLiveEmail = ''
  formData.xboxLivePassword = ''
  if (authStore.isPlatformAdmin && merchantList.value.length === 0) {
    await loadMerchants()
  }
  dialogVisible.value = true
}

/**
 * 显示编辑对话框
 * @param {Object} row - 当前行数据
 */
const showEditDialog = async (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.merchantId = row.merchantId || ''
  formData.xboxGameName = row.xboxGameName
  formData.xboxLiveEmail = row.xboxLiveEmail
  
  // 通过API获取账号详情，包含解密后的密码
  try {
    const res = await gameAccountApi.getById(row.id)
    if (res.code === 0 || res.code === 200) {
      const account = res.data
      // 使用解密后的密码
      formData.xboxLivePassword = account.xboxLivePasswordEncrypted || ''
    } else {
      formData.xboxLivePassword = ''
    }
  } catch (error) {
    console.error('Failed to get game account detail:', error)
    formData.xboxLivePassword = ''
  }
  
  if (authStore.isPlatformAdmin && merchantList.value.length === 0) {
    await loadMerchants()
  }
  dialogVisible.value = true
}

/**
 * 加载商户列表
 */
const loadMerchants = async () => {
  if (!authStore.isPlatformAdmin) return
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchants:', error)
    merchantList.value = []
  }
}

/**
 * 提交表单
 */
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (dialogType.value === 'add') {
      await gameAccountApi.create({
        merchantId: formData.merchantId,
        xboxGameName: formData.xboxGameName,
        xboxLiveEmail: formData.xboxLiveEmail,
        xboxLivePassword: formData.xboxLivePassword
      })
      ElMessage.success('创建成功')
    } else {
      const updateData = {
        merchantId: formData.merchantId,
        xboxLiveEmail: formData.xboxLiveEmail,
        xboxLivePassword: formData.xboxLivePassword || undefined
      }
      await gameAccountApi.update(formData.id, updateData)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 删除游戏账号
 * @param {Object} row - 当前行数据
 */
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除账号「${row.xboxGameName}」吗？`, '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await gameAccountApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 显示导入对话框
 */
const showImportDialog = async () => {
  importResult.value = null
  selectedFile.value = null
  fileList.value = []
  importMerchantId.value = authStore.isPlatformAdmin ? '' : authStore.merchantId
  if (authStore.isPlatformAdmin && merchantList.value.length === 0) {
    await loadMerchants()
  }
  importDialogVisible.value = true
}

/**
 * 下载导入模板
 */
const handleDownloadTemplate = async () => {
  try {
    const res = await gameAccountApi.downloadTemplate()
    const template = res.data
    const blob = new Blob(['\ufeff' + template], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'game_account_template.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to download template:', error)
  }
}

/**
 * 处理文件选择
 */
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  importResult.value = null
}

/**
 * 处理导入
 */
const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择CSV文件')
    return
  }

  importLoading.value = true
  importResult.value = null

  try {
    const text = await selectedFile.value.text()
    const lines = text.split('\n').filter(line => line.trim())

    if (lines.length < 2) {
      ElMessage.warning('CSV文件内容为空或格式不正确')
      return
    }

    const header = lines[0].split(',').map(h => h.trim())
    const requiredHeaders = ['Xbox玩家名称', 'Xbox邮箱', 'Xbox密码']
    const hasRequiredHeaders = requiredHeaders.every(h => header.includes(h))

    if (!hasRequiredHeaders) {
      ElMessage.warning('CSV文件格式不正确，请检查表头是否包含：Xbox玩家名称、Xbox邮箱、Xbox密码')
      return
    }

    const accounts = []
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim())
      if (values.length >= 3 && values[0] && values[1] && values[2]) {
        accounts.push({
          xboxGameName: values[0],
          xboxLiveEmail: values[1],
          xboxLivePassword: values[2] || ''
        })
      }
    }

    if (accounts.length === 0) {
      ElMessage.warning('没有有效的数据行')
      return
    }

    if (authStore.isPlatformAdmin && !importMerchantId.value) {
      ElMessage.warning('请选择要导入到的商户')
      return
    }

    const res = await gameAccountApi.batchImport({
      merchantId: importMerchantId.value,
      accounts: accounts
    })
    importResult.value = res.data

    if (res.data.failCount === 0) {
      ElMessage.success('导入成功')
      importDialogVisible.value = false
      loadData()
    } else {
      ElMessage.warning(`导入完成：成功 ${res.data.successCount} 条，失败 ${res.data.failCount} 条`)
    }
  } catch (error) {
    console.error('Import failed:', error)
    ElMessage.error('导入失败')
  } finally {
    importLoading.value = false
  }
}

/**
 * 获取状态标签类型
 * @param {boolean} isActive - 是否激活
 * @returns {string} 标签类型
 */
const getStatusType = (isActive) => {
  return isActive ? 'success' : 'danger'
}

/**
 * 获取状态显示文本
 * @param {boolean} isActive - 是否激活
 * @returns {string} 状态文本
 */
const getStatusText = (isActive) => {
  return isActive ? '正常' : '未激活'
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
  loadData()
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

.import-template {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.import-template h4 {
  color: #ffffff;
  margin: 0 0 12px;
  font-size: 14px;
}

.import-template ol {
  color: #b0b0b0;
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
}

.upload-component {
  margin-top: 16px;
}

.import-result {
  margin-top: 20px;
}

.error-item {
  font-size: 12px;
  color: #e6a23c;
  margin-top: 4px;
}

.error-more {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

/* 固定列hover不变透明 */
:deep(.el-table__fixed-right:hover),
:deep(.el-table__fixed:hover) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__fixed-right .el-table__row:hover td),
:deep(.el-table__fixed .el-table__row:hover td) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__body-wrapper .el-table__row:hover td.el-table__cell) {
  background-color: #1a1a2e !important;
}
</style>