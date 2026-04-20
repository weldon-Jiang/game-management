<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>游戏账号</h2>
        <span class="header-desc">管理Xbox游戏账号</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增账号
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
      >
        <el-table-column prop="name" label="账号名称" min-width="120" />
        <el-table-column prop="xboxGamertag" label="Gamertag" min-width="150" show-overflow-tooltip />
        <el-table-column prop="xboxLiveEmail" label="Xbox邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column prop="isActive" label="状态" width="100" align="center">
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
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
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
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        class="dialog-form"
      >
        <el-form-item label="账号名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入账号名称" />
        </el-form-item>
        <el-form-item label="Gamertag" prop="xboxGamertag">
          <el-input v-model="formData.xboxGamertag" placeholder="请输入Gamertag" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onErrorCaptured } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { gameAccountApi } from '@/api'

// 捕获组件内子组件的错误
onErrorCaptured((err, instance, info) => {
  console.error('GameAccountList Error:', err, 'Info:', info)
  ElMessage.error('组件加载错误: ' + err.message)
  return false
})

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

/**
 * 表单数据
 */
const formData = reactive({
  id: '',
  name: '',
  xboxGamertag: '',
  xboxLiveEmail: '',
  xboxLivePassword: ''
})

/**
 * 表单验证规则
 */
const formRules = {
  name: [
    { required: true, message: '请输入账号名称', trigger: 'blur' }
  ],
  xboxGamertag: [
    { required: true, message: '请输入Gamertag', trigger: 'blur' }
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
  console.log('GameAccountList loadData called, loading:', loading.value)
  loading.value = true
  tableData.value = []
  try {
    console.log('GameAccountList calling API...')
    const res = await gameAccountApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    console.log('GameAccountList API response:', res)
    console.log('GameAccountList res.data keys:', Object.keys(res.data || {}))
    console.log('GameAccountList res.data.records:', res.data?.records)
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
    console.log('GameAccountList tableData after load:', tableData.value)
  } catch (error) {
    console.error('GameAccountList load error:', error)
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
    console.log('GameAccountList loadData complete, loading:', loading.value)
  }
}

/**
 * 显示新增对话框
 */
const showAddDialog = () => {
  dialogType.value = 'add'
  formData.id = ''
  formData.name = ''
  formData.xboxGamertag = ''
  formData.xboxLiveEmail = ''
  formData.xboxLivePassword = ''
  dialogVisible.value = true
}

/**
 * 显示编辑对话框
 * @param {Object} row - 当前行数据
 */
const showEditDialog = (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.name = row.name
  formData.xboxGamertag = row.xboxGamertag
  formData.xboxLiveEmail = row.xboxLiveEmail
  formData.xboxLivePassword = ''
  dialogVisible.value = true
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
        name: formData.name,
        xboxGamertag: formData.xboxGamertag,
        xboxLiveEmail: formData.xboxLiveEmail,
        xboxLivePassword: formData.xboxLivePassword
      })
      ElMessage.success('创建成功')
    } else {
      await gameAccountApi.update(formData.id, {
        name: formData.name,
        xboxLiveEmail: formData.xboxLiveEmail,
        xboxLivePassword: formData.xboxLivePassword || undefined
      })
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
  await ElMessageBox.confirm(`确定要删除账号「${row.name}」吗？`, '提示', {
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
  console.log('GameAccountList mounted!')
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

.content-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
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

:deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: #8a8a8a;
  --el-pagination-hover-color: #6366f1;
  --el-pagination-button-disabled-bg-color: transparent;
  --el-pagination-button-bg-color: transparent;
  --el-pagination-border-color: rgba(255, 255, 255, 0.06);
}

:deep(.el-pagination .el-pager li) {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin: 0 3px;
  color: #8a8a8a;
}

:deep(.el-pagination .el-pager li:hover) {
  color: #6366f1;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
}

:deep(.el-pagination .btn-prev, .el-pagination .btn-next) {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  color: #8a8a8a;
}

:deep(.el-pagination .btn-prev:hover, .el-pagination .btn-next:hover) {
  color: #6366f1;
}

:deep(.el-pagination .el-pagination__jump) {
  color: #8a8a8a;
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
</style>