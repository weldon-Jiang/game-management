<template>
  <div class="page-container merchant-group-list">
    <div class="page-header">
      <h2>商户分组管理</h2>
      <el-button v-if="authStore.isPlatformAdmin" type="primary" @click="showDialog('add')">
        添加分组
      </el-button>
    </div>

    <div class="content-card">
      <el-table :data="tableData" v-loading="loading">
        <el-table-column prop="name" label="分组名称" />
        <el-table-column prop="vipLevel" label="VIP等级" width="100" />
        <el-table-column label="扣点折扣" width="100">
          <template #default="{ row }">
            {{ (row.discountRate * 100).toFixed(0) }}折
          </template>
        </el-table-column>
        <el-table-column label="解绑返还" width="100">
          <template #default="{ row }">
            {{ (row.unbindRefundRate * 100).toFixed(0) }}%
          </template>
        </el-table-column>
        <el-table-column prop="maxUnbindPerWeek" label="每周解绑上限" width="120" />
        <el-table-column label="主机单价" width="100">
          <template #default="{ row }">
            {{ row.hostPrice }}点/台/月
          </template>
        </el-table-column>
        <el-table-column label="窗口单价" width="100">
          <template #default="{ row }">
            {{ row.windowPrice }}点/个/月
          </template>
        </el-table-column>
        <el-table-column label="游戏号单价" width="110">
          <template #default="{ row }">
            {{ row.accountPrice }}点/个
          </template>
        </el-table-column>
        <el-table-column prop="features" label="功能权限" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="f in parseFeatures(row.features)" :key="f" size="small" class="feature-tag">
              {{ getFeatureName(f) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isPlatformAdmin" label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDialog('edit', row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogType === 'add' ? '添加分组' : '编辑分组'" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="分组名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="VIP等级" prop="vipLevel">
          <el-input-number v-model="formData.vipLevel" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="扣点折扣">
          <el-slider v-model="formData.discountRate" :min="0.5" :max="1" :step="0.01" show-stops />
          <span>{{ (formData.discountRate * 100).toFixed(0) }}折</span>
        </el-form-item>
        <el-form-item label="解绑返还比例">
          <el-slider v-model="formData.unbindRefundRate" :min="0" :max="1" :step="0.1" show-stops />
          <span>{{ (formData.unbindRefundRate * 100).toFixed(0) }}%</span>
        </el-form-item>
        <el-form-item label="每周解绑上限">
          <el-input-number v-model="formData.maxUnbindPerWeek" :min="0" :max="10" />
        </el-form-item>
        <el-form-item label="主机单价">
          <el-input-number v-model="formData.hostPrice" :min="0" :precision="2" /> 点/台/月
        </el-form-item>
        <el-form-item label="窗口单价">
          <el-input-number v-model="formData.windowPrice" :min="0" :precision="2" /> 点/个/月
        </el-form-item>
        <el-form-item label="游戏号单价">
          <el-input-number v-model="formData.accountPrice" :min="0" :precision="2" /> 点/个
        </el-form-item>
        <el-form-item label="功能权限">
          <el-checkbox-group v-model="selectedFeatures">
            <el-checkbox label="1">串流</el-checkbox>
            <el-checkbox label="2">SQB</el-checkbox>
            <el-checkbox label="3">DR</el-checkbox>
            <el-checkbox label="4">Rush</el-checkbox>
            <el-checkbox label="5">转会任务</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.status" active-value="active" inactive-value="inactive" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { merchantGroupApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogType = ref('add')
const submitLoading = ref(false)
const formRef = ref(null)
const selectedFeatures = ref(['1', '2', '3'])

const formData = reactive({
  id: '',
  name: '',
  vipLevel: 1,
  discountRate: 1,
  unbindRefundRate: 0.5,
  maxUnbindPerWeek: 2,
  hostPrice: 20,
  windowPrice: 15,
  accountPrice: 10,
  features: '[]',
  status: 'active'
})

const formRules = {
  name: [{ required: true, message: '请输入分组名称', trigger: 'blur' }],
  vipLevel: [{ required: true, message: '请输入VIP等级', trigger: 'blur' }]
}

const featureNames = {
  '1': '串流',
  '2': 'SQB',
  '3': 'DR',
  '4': 'Rush',
  '5': '转会'
}

const getFeatureName = (f) => featureNames[f] || f

const parseFeatures = (features) => {
  try {
    return JSON.parse(features || '[]')
  } catch {
    return []
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await merchantGroupApi.listAll()
    tableData.value = res.data || []
  } catch (error) {
    console.error('Failed to load groups:', error)
  } finally {
    loading.value = false
  }
}

const showDialog = (type, row = null) => {
  dialogType.value = type
  if (type === 'edit' && row) {
    Object.assign(formData, row)
    selectedFeatures.value = parseFeatures(row.features)
  } else {
    Object.assign(formData, {
      id: '',
      name: '',
      vipLevel: 1,
      discountRate: 1,
      unbindRefundRate: 0.5,
      maxUnbindPerWeek: 2,
      hostPrice: 20,
      windowPrice: 15,
      accountPrice: 10,
      features: '[]',
      status: 'active'
    })
    selectedFeatures.value = ['1', '2', '3']
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    formData.features = JSON.stringify(selectedFeatures.value)
    if (dialogType.value === 'add') {
      await merchantGroupApi.create(formData)
      ElMessage.success('分组创建成功')
    } else {
      await merchantGroupApi.update(formData.id, formData)
      ElMessage.success('分组更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    console.error('Failed to submit:', error)
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该分组?', '警告', { type: 'warning' })
    await merchantGroupApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete:', error)
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
}

.feature-tag {
  margin-right: 4px;
  margin-bottom: 2px;
}
</style>
