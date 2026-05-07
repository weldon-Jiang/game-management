<template>
  <div class="page-container merchant-group-list">
    <div class="page-header">
      <h2>商户分组管理</h2>
      <el-button v-if="authStore.isPlatformAdmin" type="primary" @click="showDialog('add')">
        添加分组
      </el-button>
    </div>

    <div class="content-card">
      <el-table :data="tableData" v-loading="loading" class="data-table">
        <el-table-column prop="name" label="分组名称" />
        <el-table-column prop="vipLevel" label="VIP等级" width="100">
          <template #default="{ row }">
            VIP{{ row.vipLevel }}
          </template>
        </el-table-column>
        <el-table-column prop="pointsThreshold" label="升级门槛" width="120" align="right">
          <template #default="{ row }">
            {{ row.pointsThreshold || 0 }} 点
          </template>
        </el-table-column>
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
            {{ row.accountPrice }}点/个/月
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
        <el-form-item label="VIP等级">
          <el-input-number v-model="formData.vipLevel" :min="1" :max="10" />
        </el-form-item>
        <el-form-item label="升级门槛">
          <el-input-number v-model="formData.pointsThreshold" :min="0" :step="100" />
          <span class="field-hint">累计充值达到此点数时，自动升级到该VIP等级</span>
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
            <el-checkbox v-for="feature in featureOptions" :key="feature.code" :label="feature.code">
              {{ feature.name }}
            </el-checkbox>
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
import { FEATURE_CODE_MAP } from '@/utils/constants'

const authStore = useAuthStore()
const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogType = ref('add')
const submitLoading = ref(false)
const formRef = ref(null)
const selectedFeatures = ref(['stream_control', 'sqb', 'dr'])

const featureOptions = Object.entries(FEATURE_CODE_MAP).map(([code, name]) => ({ code, name }))

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

const getFeatureName = (code) => FEATURE_CODE_MAP[code] || code

const OLD_TO_NEW_CODE_MAP = {
  '1': 'stream_control',
  '2': 'sqb',
  '3': 'dr',
  '4': 'rush',
  '5': 'transfer'
}

const parseFeatures = (features) => {
  try {
    const parsed = JSON.parse(features || '[]')
    return parsed.map(f => OLD_TO_NEW_CODE_MAP[f] || f)
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
      pointsThreshold: 0,
      discountRate: 1,
      unbindRefundRate: 0.5,
      maxUnbindPerWeek: 2,
      hostPrice: 20,
      windowPrice: 15,
      accountPrice: 10,
      features: '[]',
      status: 'active'
    })
    selectedFeatures.value = ['stream_control', 'sqb', 'dr']
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

.field-hint {
  margin-left: 12px;
  color: #8a8a8a;
  font-size: 12px;
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
