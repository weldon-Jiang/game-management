<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>VIP配置</h2>
        <span class="header-desc">管理VIP套餐类型</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增配置
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
      >
        <el-table-column prop="vipType" label="VIP类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag type="warning" size="small">
              {{ getVipTypeText(row.vipType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="vipName" label="套餐名称" min-width="150" />
        <el-table-column prop="price" label="价格" width="100" align="center">
          <template #default="{ row }">
            <span class="price">¥{{ row.price }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="durationDays" label="时长" width="100" align="center">
          <template #default="{ row }">
            {{ row.durationDays }}天
          </template>
        </el-table-column>
        <el-table-column prop="features" label="功能描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="isDefault" label="默认" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.isDefault" type="success" size="small">是</el-tag>
            <span v-else class="text-muted">否</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.status"
              active-value="active"
              inactive-value="disabled"
              @change="handleStatusChange(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
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
      :title="dialogType === 'add' ? '新增VIP配置' : '编辑VIP配置'"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="90px"
        class="dialog-form"
      >
        <el-form-item label="VIP类型" prop="vipType">
          <el-select v-model="formData.vipType" :disabled="dialogType === 'edit'" style="width: 100%" @change="handleVipTypeChange">
            <el-option label="月卡" value="monthly" />
            <el-option label="季卡" value="quarterly" />
            <el-option label="年卡" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="套餐名称" prop="vipName">
          <el-input v-model="formData.vipName" placeholder="请输入套餐名称" />
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input-number
            v-model="formData.price"
            :min="0"
            :precision="2"
            :step="10"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="时长(天)" prop="durationDays">
          <el-input-number
            v-model="formData.durationDays"
            :min="1"
            :step="1"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="功能描述" prop="features">
          <el-input
            v-model="formData.features"
            type="textarea"
            :rows="3"
            placeholder="请输入功能描述"
          />
        </el-form-item>
        <el-form-item label="设为默认" prop="isDefault">
          <el-switch v-model="formData.isDefault" />
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
import { vipApi } from '@/api'
import { getVipTypeText, getVipDefaultDuration } from '@/utils/constants'

/**
 * VIP配置管理页面
 * 提供VIP套餐的增删改查功能
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
  vipType: 'monthly',
  vipName: '',
  price: 0,
  durationDays: 30,
  features: '',
  isDefault: false
})

/**
 * 表单验证规则
 */
const formRules = {
  vipType: [
    { required: true, message: '请选择VIP类型', trigger: 'change' }
  ],
  vipName: [
    { required: true, message: '请输入套餐名称', trigger: 'blur' },
    { min: 2, max: 30, message: '长度在 2 到 30 个字符', trigger: 'blur' }
  ],
  price: [
    { required: true, message: '请输入价格', trigger: 'blur' },
    { validator: (rule, value, callback) => {
      if (value === 0 || value === '0') {
        callback(new Error('价格不能为0'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ],
  durationDays: [
    { required: true, message: '请输入时长', trigger: 'blur' },
    { validator: (rule, value, callback) => {
      if (value === 0 || value === '0') {
        callback(new Error('时长不能为0'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ]
}

// ==================== 方法定义 ====================

/**
 * 加载VIP配置列表
 */
const loadData = async () => {
  loading.value = true
  try {
    const res = await vipApi.listPage({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load VIP configs:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增对话框
 */
const showAddDialog = () => {
  dialogType.value = 'add'
  formData.id = ''
  formData.vipType = 'monthly'
  formData.vipName = ''
  formData.price = 0
  formData.durationDays = 30
  formData.features = ''
  formData.isDefault = false
  dialogVisible.value = true
}

/**
 * 显示编辑对话框
 * @param {Object} row - 当前行数据
 */
const showEditDialog = (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.vipType = row.vipType
  formData.vipName = row.vipName
  formData.price = row.price
  formData.durationDays = row.durationDays
  formData.features = row.features || ''
  formData.isDefault = row.isDefault
  dialogVisible.value = true
}

/**
 * VIP类型变更处理
 */
const handleVipTypeChange = (value) => {
  const duration = getVipDefaultDuration(value)
  if (duration) {
    formData.durationDays = duration
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
      await vipApi.create({
        vipType: formData.vipType,
        vipName: formData.vipName,
        price: formData.price,
        durationDays: formData.durationDays,
        features: formData.features,
        isDefault: formData.isDefault
      })
      ElMessage.success('创建成功')
    } else {
      await vipApi.update(formData.id, {
        vipName: formData.vipName,
        price: formData.price,
        durationDays: formData.durationDays,
        features: formData.features,
        isDefault: formData.isDefault
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
 * 切换状态
 * @param {Object} row - 当前行数据
 */
const handleStatusChange = async (row) => {
  try {
    await vipApi.updateStatus(row.id, row.status)
    ElMessage.success('状态更新成功')
  } catch (error) {
    // 恢复原状态
    row.status = row.status === 'active' ? 'disabled' : 'active'
    // 错误已在拦截器中处理
  }
}

/**
 * 删除VIP配置
 * @param {Object} row - 当前行数据
 */
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除VIP配置「${row.vipName}」吗？`, '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await vipApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
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

.price {
  color: #f59e0b;
  font-weight: 600;
}

.text-muted {
  color: #6b7280;
  font-size: 13px;
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

:deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

:deep(.el-input-number) {
  --el-input-bg-color: rgba(255, 255, 255, 0.05);
}
</style>