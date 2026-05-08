<template>
  <div class="page-container">
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

    <div class="content-card table-container">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
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
        <el-table-column prop="vipLevel" label="VIP等级" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.vipLevel && row.vipLevel > 0" type="warning" size="small">
              VIP{{ row.vipLevel }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="totalPoints" label="累计点数" width="120" align="right">
          <template #default="{ row }">
            <span class="points-text">{{ row.totalPoints || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDialog('edit', row)">
              编辑
            </el-button>
            <el-button
              v-if="!row.isSystem"
              :type="getActionBtnType(row)"
              link
              size="small"
              @click="handleStatus(row)"
            >
              {{ getActionBtnText(row) }}
            </el-button>
            <el-button v-if="!row.isSystem" type="danger" link size="small" @click="handleDelete(row)">
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
        <el-form-item v-if="authStore.isPlatformAdmin" label="系统商户">
          <el-switch v-model="formData.isSystem" />
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
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { merchantApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const loading = ref(false)
const submitLoading = ref(false)
const tableData = ref([])
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const dialogVisible = ref(false)
const dialogType = ref('add')
const formRef = ref(null)

const formData = reactive({
  id: '',
  name: '',
  phone: '',
  isSystem: false
})

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

const showDialog = (type, row = null) => {
  dialogType.value = type
  if (type === 'edit' && row) {
    formData.id = row.id
    formData.name = row.name
    formData.phone = row.phone
    formData.isSystem = row.isSystem || false
  } else {
    formData.id = ''
    formData.name = ''
    formData.phone = ''
    formData.isSystem = false
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (dialogType.value === 'add') {
      await merchantApi.create({
        name: formData.name,
        phone: formData.phone,
        isSystem: formData.isSystem
      })
      ElMessage.success('商户创建成功')
    } else {
      await merchantApi.update(formData.id, {
        name: formData.name,
        phone: formData.phone,
        isSystem: formData.isSystem
      })
      ElMessage.success('商户更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

const handleStatus = async (row) => {
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

const getActionBtnType = (row) => {
  if (row.status === 'active') return 'warning'
  return 'success'
}

const getActionBtnText = (row) => {
  if (row.status === 'active') return '停用'
  return '启用'
}

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

const getStatusType = (row) => {
  if (row.status === 'active') return 'success'
  if (row.status === 'suspended') return 'danger'
  return 'info'
}

const getStatusText = (row) => {
  if (row.status === 'active') return '正常'
  if (row.status === 'suspended') return '已停用'
  return row.status
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
  loadData()
})
</script>

<style scoped>
.data-table {
  width: 100%;
}

.points-text {
  color: var(--warning);
  font-weight: 500;
}
</style>
