<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>用户管理</h2>
        <span class="header-desc">管理商户用户信息</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增用户
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
      >
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="150" />
        <el-table-column prop="id" label="用户ID" width="280" show-overflow-tooltip />
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="phone" label="手机号" width="140" />
        <el-table-column prop="role" label="角色" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)" size="small">
              {{ getRoleText(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastLoginTime" label="最后登录" width="170">
          <template #default="{ row }">
            {{ row.lastLoginTime ? formatDate(row.lastLoginTime) : '从未登录' }}
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-button type="warning" link size="small" @click="showPasswordDialog(row)">
              重置密码
            </el-button>
            <el-button
              v-if="row.id !== currentUserId"
              type="danger"
              link
              size="small"
              @click="handleDelete(row)"
            >
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

    <!-- 编辑用户对话框 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑用户"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="editFormRef"
        :model="editFormData"
        :rules="editFormRules"
        label-width="80px"
        class="dialog-form"
      >
        <el-form-item v-if="authStore.isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="editFormData.merchantId"
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
        <el-form-item label="用户名" prop="username">
          <el-input v-model="editFormData.username" disabled placeholder="不可修改" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editFormData.phone" disabled placeholder="不可修改" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="editFormData.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="商户所有者" value="owner" />
            <el-option label="商户管理员" value="admin" />
            <el-option label="操作员" value="operator" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editFormData.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="正常" value="active" />
            <el-option label="禁用" value="disabled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleEditSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 新增用户对话框 -->
    <el-dialog
      v-model="addDialogVisible"
      title="新增用户"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="addFormRef"
        :model="addFormData"
        :rules="addFormRules"
        label-width="80px"
        class="dialog-form"
      >
        <el-form-item v-if="authStore.isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="addFormData.merchantId"
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
        <el-form-item label="用户名" prop="username">
          <el-input v-model="addFormData.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="addFormData.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="addFormData.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="addFormData.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="商户所有者" value="owner" />
            <el-option label="商户管理员" value="admin" />
            <el-option label="操作员" value="operator" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleAddSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="passwordDialogVisible"
      title="重置密码"
      width="420px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="passwordFormRef"
        :model="passwordFormData"
        :rules="passwordFormRules"
        label-width="80px"
        class="dialog-form"
      >
        <el-form-item label="用户" prop="username">
          <el-input v-model="passwordFormData.username" disabled />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="passwordFormData.newPassword"
            type="password"
            placeholder="请输入新密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordFormData.confirmPassword"
            type="password"
            placeholder="请再次输入新密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handlePasswordSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { userApi, merchantApi } from '@/api'

/**
 * 用户管理列表页面
 * 提供用户的查看、编辑、重置密码和删除功能
 */

// ==================== 状态定义 ====================

const authStore = useAuthStore()

/**
 * 当前用户ID（防止删除自己）
 */
const currentUserId = computed(() => authStore.userId)

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
 * 商户列表
 */
const merchantList = ref([])

/**
 * 分页参数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

/**
 * 编辑对话框状态
 */
const editDialogVisible = ref(false)
const editFormRef = ref(null)
const editFormData = reactive({
  id: '',
  merchantId: '',
  username: '',
  phone: '',
  role: '',
  status: ''
})

/**
 * 编辑表单验证规则
 */
const editFormRules = {
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
}

/**
 * 重置密码对话框状态
 */
const passwordDialogVisible = ref(false)
const passwordFormRef = ref(null)
const passwordFormData = reactive({
  id: '',
  username: '',
  newPassword: '',
  confirmPassword: ''
})

/**
 * 密码表单验证规则
 */
const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordFormData.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordFormRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 4, max: 20, message: '密码长度为4-20个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

/**
 * 新增用户对话框状态
 */
const addDialogVisible = ref(false)
const addFormRef = ref(null)
const addFormData = reactive({
  merchantId: '',
  username: '',
  password: '',
  phone: '',
  role: ''
})

/**
 * 新增用户表单验证规则
 */
const validateAddConfirmPassword = (rule, value, callback) => {
  if (value !== addFormData.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const addFormRules = {
  merchantId: [
    { required: true, message: '请选择商户', trigger: 'change' }
  ],
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为2-20个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 20, message: '密码长度为4-20个字符', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  role: [
    { required: true, message: '请选择角色', trigger: 'change' }
  ]
}

// ==================== 方法定义 ====================

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
  }
}

/**
 * 加载用户列表数据
 */
const loadData = async () => {
  loading.value = true
  try {
    const res = await userApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load users:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增用户对话框
 */
const showAddDialog = () => {
  addFormData.merchantId = authStore.isPlatformAdmin ? '' : authStore.merchantId
  addFormData.username = ''
  addFormData.password = ''
  addFormData.phone = ''
  addFormData.role = ''
  addDialogVisible.value = true
}

/**
 * 提交新增用户表单
 */
const handleAddSubmit = async () => {
  const valid = await addFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await userApi.create({
      merchantId: addFormData.merchantId,
      username: addFormData.username,
      password: addFormData.password,
      phone: addFormData.phone || undefined,
      role: addFormData.role
    })
    ElMessage.success('用户创建成功')
    addDialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 显示编辑用户对话框
 * @param {Object} row - 当前行数据
 */
const showEditDialog = (row) => {
  editFormData.id = row.id
  editFormData.merchantId = row.merchantId
  editFormData.username = row.username
  editFormData.phone = row.phone || ''
  editFormData.role = row.role
  editFormData.status = row.status
  editDialogVisible.value = true
}

/**
 * 提交编辑用户表单
 */
const handleEditSubmit = async () => {
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await userApi.update(editFormData.id, {
      phone: editFormData.phone,
      role: editFormData.role,
      status: editFormData.status
    })
    ElMessage.success('用户更新成功')
    editDialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 显示重置密码对话框
 * @param {Object} row - 当前行数据
 */
const showPasswordDialog = (row) => {
  passwordFormData.id = row.id
  passwordFormData.username = row.username
  passwordFormData.newPassword = ''
  passwordFormData.confirmPassword = ''
  passwordDialogVisible.value = true
}

/**
 * 提交重置密码表单
 */
const handlePasswordSubmit = async () => {
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    await userApi.resetPassword(passwordFormData.id, passwordFormData.newPassword)
    ElMessage.success('密码重置成功')
    passwordDialogVisible.value = false
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 删除用户
 * @param {Object} row - 当前行数据
 */
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除用户「${row.username}」吗？此操作不可恢复！`, '危险操作', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'error'
  })

  try {
    await userApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 获取角色标签类型
 * @param {string} role - 角色值
 * @returns {string} 标签类型
 */
const getRoleType = (role) => {
  const typeMap = {
    platform_admin: 'danger',
    owner: 'primary',
    admin: 'warning',
    operator: 'info'
  }
  return typeMap[role] || 'info'
}

/**
 * 获取角色显示文本
 * @param {string} role - 角色值
 * @returns {string} 角色文本
 */
const getRoleText = (role) => {
  const textMap = {
    platform_admin: '平台管理员',
    owner: '商户所有者',
    admin: '管理员',
    operator: '操作员'
  }
  return textMap[role] || role
}

/**
 * 获取状态标签类型
 * @param {string} status - 状态值
 * @returns {string} 标签类型
 */
const getStatusType = (status) => {
  const typeMap = {
    active: 'success',
    disabled: 'danger'
  }
  return typeMap[status] || 'info'
}

/**
 * 获取状态显示文本
 * @param {string} status - 状态值
 * @returns {string} 状态文本
 */
const getStatusText = (status) => {
  const textMap = {
    active: '正常',
    disabled: '禁用'
  }
  return textMap[status] || status
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
  loadMerchants()
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

:deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

:deep(.el-select__placeholder) {
  color: #5a5a5a;
}
</style>