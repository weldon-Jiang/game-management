<template>
  <div class="page-container">
    <!-- 页面标题栏 -->
    <div class="page-header">
      <div class="header-left">
        <h2>商户管理</h2>
        <span class="header-desc">管理平台所有商户信息</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showDialog('add')">
          <el-icon><Plus /></el-icon>
          新增商户
        </el-button>
      </div>
    </div>

    <!-- 商户列表表格 -->
    <div class="content-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
      >
        <el-table-column prop="id" label="商户ID" width="280" show-overflow-tooltip />
        <el-table-column prop="name" label="商户名称" min-width="150" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)" size="small">
              {{ getStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expireTime" label="有效期至" width="170">
          <template #default="{ row }">
            {{ row.expireTime ? formatDate(row.expireTime) : '永久' }}
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDialog('edit', row)">
              编辑
            </el-button>
            <el-button
              v-if="isExpirable(row)"
              :type="getActionBtnType(row)"
              link
              size="small"
              @click="handleStatus(row)"
            >
              {{ getActionBtnText(row) }}
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页组件 -->
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

    <!-- 新增/编辑商户对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '新增商户' : '编辑商户'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="80px"
        class="dialog-form"
      >
        <el-form-item label="商户名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入商户名称" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="formData.phone" placeholder="请输入手机号" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { merchantApi } from '@/api'

/**
 * 商户管理列表页面
 * 提供商户的增删改查功能
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
 * 对话框显示状态
 */
const dialogVisible = ref(false)

/**
 * 对话框类型: add-新增, edit-编辑
 */
const dialogType = ref('add')

/**
 * 表单引用
 */
const formRef = ref(null)

/**
 * 表单数据
 */
const formData = reactive({
  id: '',
  name: '',
  phone: ''
})

/**
 * 表单验证规则
 */
const formRules = {
  name: [
    { required: true, message: '请输入商户名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
}

// ==================== 方法定义 ====================

/**
 * 加载商户列表数据
 */
const loadData = async () => {
  loading.value = true
  try {
    const res = await merchantApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load merchants:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增/编辑对话框
 * @param {string} type - 对话框类型
 * @param {Object} row - 当前行数据（编辑时）
 */
const showDialog = (type, row = null) => {
  dialogType.value = type
  if (type === 'edit' && row) {
    formData.id = row.id
    formData.name = row.name
    formData.phone = row.phone
  } else {
    formData.id = ''
    formData.name = ''
    formData.phone = ''
  }
  dialogVisible.value = true
}

/**
 * 提交表单数据
 */
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (dialogType.value === 'add') {
      await merchantApi.create({
        name: formData.name,
        phone: formData.phone
      })
      ElMessage.success('商户创建成功')
    } else {
      // 编辑暂不支持（后端接口未提供）
      ElMessage.info('编辑功能开发中')
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
 * 更新商户状态
 * @param {Object} row - 当前行数据
 */
const handleStatus = async (row) => {
  // 如果是启用操作，检查是否已过期
  if (row.status === 'suspended' || isExpired(row)) {
    // 启用操作 - 检查是否已过期
    if (isExpired(row)) {
      ElMessage.warning('账号已过期，请先续费后再启用')
      return
    }
  }

  const newStatus = row.status === 'active' ? 'suspended' : 'active'
  const actionText = newStatus === 'active' ? '启用' : '停用'

  await ElMessageBox.confirm(`确定要${actionText}商户「${row.name}」吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await merchantApi.updateStatus(row.id, newStatus)
    ElMessage.success(`${actionText}成功`)
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 判断商户是否已过期
 * @param {Object} row - 商户数据
 * @returns {boolean}
 */
const isExpired = (row) => {
  if (!row.expireTime) return false
  return new Date(row.expireTime) > new Date()
}

/**
 * 判断是否显示启用/停用按钮（expireTime >= 当前时间才显示）
 * @param {Object} row - 商户数据
 * @returns {boolean}
 */
const isExpirable = (row) => {
  // 如果没有过期时间（永久），一直显示
  if (!row.expireTime) return true
  // 如果已过期，不显示按钮
  if (isExpired(row)) return false

  return true
}

/**
 * 获取操作按钮类型
 * @param {Object} row - 商户数据
 * @returns {string}
 */
const getActionBtnType = (row) => {
  if (row.status === 'active') return 'warning'
  return 'success'
}

/**
 * 获取操作按钮文本
 * @param {Object} row - 商户数据
 * @returns {string}
 */
const getActionBtnText = (row) => {
  if (row.status === 'active') return '停用'
  return '启用'
}

/**
 * 删除商户
 * @param {Object} row - 当前行数据
 */
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除商户「${row.name}」吗？此操作不可恢复！`, '危险操作', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'error'
  })

  try {
    await merchantApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 获取状态标签类型（根据status和expireTime综合判断）
 * @param {Object} row - 商户数据
 * @returns {string} 标签类型
 */
const getStatusType = (row) => {
  const { status, expireTime } = row
  // 已过期（expireTime > 当前时间）
  if (expireTime && new Date(expireTime) > new Date()) return 'warning'

  // 正常（status=active且未过期）
  if (status === 'active' && new Date(expireTime) <= new Date()) return 'success'
  
  // 已停用
  if (status === 'suspended') return 'danger'

  // 其他状态
  return 'info'
}

/**
 * 获取状态显示文本（根据status和expireTime综合判断）
 * @param {Object} row - 商户数据
 * @returns {string} 状态文本
 */
const getStatusText = (row) => {
  const { status, expireTime } = row
    // 已过期（status=active但expireTime > 当前时间）
  if (expireTime && new Date(expireTime) > new Date()) return '已过期'

  // 正常（status=active且未过期）
  if (status === 'active' && new Date(expireTime) <= new Date()) return '正常'

  // 已停用
  if (status === 'suspended') return '已停用'

  // 其他状态
  return status
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

.content-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
}

.data-table {
  width: 100%;
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

:deep(.el-table__inner-wrapper::before) {
  display: none;
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
  --el-pagination-disabled-color: #5a5a5a;
  --el-pagination-button-color: #8a8a8a;
}

:deep(.el-pagination .el-pager li) {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin: 0 3px;
  color: #8a8a8a;
  font-size: 13px;
  min-width: 32px;
  height: 32px;
  line-height: 32px;
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

:deep(.el-dialog__body) {
  padding: 28px 24px;
}

:deep(.el-dialog__footer) {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding: 16px 24px;
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

:deep(.el-input__inner::placeholder) {
  color: #5a5a5a;
}
</style>