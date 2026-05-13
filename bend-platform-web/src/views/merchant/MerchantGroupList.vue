<template>
  <div class="page-container merchant-group-list">
    <div class="page-header">
      <h2>VIP分组管理</h2>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button v-if="authStore.isPlatformAdmin" type="primary" @click="showDialog('add')">
          添加分组
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <el-table :data="tableData" v-loading="loading" class="data-table">
        <el-table-column prop="name" label="分组名称" width="120"/>
        <el-table-column prop="vipLevel" label="VIP等级" width="80">
          <template #default="{ row }">
            VIP{{ row.vipLevel }}
          </template>
        </el-table-column>
        <el-table-column prop="amountThreshold" label="升级门槛" width="120" align="right">
          <template #default="{ row }">
            {{ formatPrice(row.amountThreshold) }}
          </template>
        </el-table-column>
        <el-table-column label="流媒体账号包月" width="180" align="right">
          <template #header>
            流媒体账号包月<br/>
            <span class="price-label">(原价/折后价)元</span>
          </template>
          <template #default="{ row }">
            {{ formatPrice(row.windowOriginalPrice) }} / {{ formatPrice(row.windowDiscountPrice) }}
          </template>
        </el-table-column>
        <el-table-column label="游戏账号包月" width="180" align="right">
          <template #header>
            游戏账号包月<br/>
            <span class="price-label">(原价/折后价)元</span>
          </template>
          <template #default="{ row }">
            {{ formatPrice(row.accountOriginalPrice) }} / {{ formatPrice(row.accountDiscountPrice) }}
          </template>
        </el-table-column>
        <el-table-column label="Xbox主机包月" width="180" align="right">
          <template #header>
            Xbox主机包月<br/>
            <span class="price-label">(原价/折后价)元</span>
          </template>
          <template #default="{ row }">
            {{ formatPrice(row.hostOriginalPrice) }} / {{ formatPrice(row.hostDiscountPrice) }}
          </template>
        </el-table-column>
        <el-table-column label="全功能包月" width="180" align="right">
          <template #header>
            全功能包月<br/>
            <span class="price-label">(原价/折后价)元</span>
          </template>
          <template #default="{ row }">
            {{ formatPrice(row.fullOriginalPrice) }} / {{ formatPrice(row.fullDiscountPrice) }}
          </template>
        </el-table-column>
        <el-table-column label="点数单价" width="170" align="right">
          <template #header>
            点数单价<br/>
            <span class="price-label">(原价/折后价)元</span>
          </template>
          <template #default="{ row }">
            {{ formatPrice(row.pointsOriginalPrice) }} / {{ formatPrice(row.pointsDiscountPrice) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isPlatformAdmin" label="操作" width="120" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDialog('edit', row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogType === 'add' ? '添加分组' : '编辑分组'" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="110px">
        <el-form-item label="分组名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="VIP等级">
          <span v-if="dialogType === 'add'" class="vip-level-auto">
            将自动分配为 VIP{{ nextVipLevel }}
          </span>
          <span v-else class="vip-level-display">VIP{{ formData.vipLevel }}</span>
        </el-form-item>
        <el-form-item label="升级门槛">
          <el-input-number v-model="formData.amountThreshold" :min="0" :precision="2" />
          <span class="field-hint">累计消费金额达到此数值时，自动升级到该VIP等级</span>
        </el-form-item>
        <el-form-item label="流媒体账号" prop="windowDiscountPrice" :rules="formRules.windowDiscountPrice">
          <div class="price-row">
            <div class="price-item">
              <span class="price-label">原价(元):</span>
              <el-input-number v-model="formData.windowOriginalPrice" :min="0" :precision="2" />
            </div>
            <div class="price-item">
              <span class="price-label">折后(元):</span>
              <el-input-number v-model="formData.windowDiscountPrice" :min="0" :precision="2" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="游戏账号" prop="accountDiscountPrice" :rules="formRules.accountDiscountPrice">
          <div class="price-row">
            <div class="price-item">
              <span class="price-label">原价(元):</span>
              <el-input-number v-model="formData.accountOriginalPrice" :min="0" :precision="2" />
            </div>
            <div class="price-item">
              <span class="price-label">折后(元):</span>
              <el-input-number v-model="formData.accountDiscountPrice" :min="0" :precision="2" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="Xbox主机" prop="hostDiscountPrice" :rules="formRules.hostDiscountPrice">
          <div class="price-row">
            <div class="price-item">
              <span class="price-label">原价(元):</span>
              <el-input-number v-model="formData.hostOriginalPrice" :min="0" :precision="2" />
            </div>
            <div class="price-item">
              <span class="price-label">折后(元):</span>
              <el-input-number v-model="formData.hostDiscountPrice" :min="0" :precision="2" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="全功能" prop="fullDiscountPrice" :rules="formRules.fullDiscountPrice">
          <div class="price-row">
            <div class="price-item">
              <span class="price-label">原价(元):</span>
              <el-input-number v-model="formData.fullOriginalPrice" :min="0" :precision="2" />
            </div>
            <div class="price-item">
              <span class="price-label">折后(元):</span>
              <el-input-number v-model="formData.fullDiscountPrice" :min="0" :precision="2" />
            </div>
          </div>
        </el-form-item>
        <el-form-item label="点数" prop="pointsDiscountPrice" :rules="formRules.pointsDiscountPrice">
          <div class="price-row">
            <div class="price-item">
              <span class="price-label">原价(元):</span>
              <el-input-number v-model="formData.pointsOriginalPrice" :min="0" :precision="2" />
            </div>
            <div class="price-item">
              <span class="price-label">折后(元):</span>
              <el-input-number v-model="formData.pointsDiscountPrice" :min="0" :precision="2" />
            </div>
          </div>
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
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { merchantGroupApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogType = ref('add')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  id: '',
  name: '',
  vipLevel: 0,
  amountThreshold: 0,
  windowOriginalPrice: 10000,
  windowDiscountPrice: 10000,
  accountOriginalPrice: 5000,
  accountDiscountPrice: 5000,
  hostOriginalPrice: 20000,
  hostDiscountPrice: 20000,
  fullOriginalPrice: 30000,
  fullDiscountPrice: 30000,
  pointsOriginalPrice: 500,
  pointsDiscountPrice: 500,
  status: 'active'
})

const formRules = {
  name: [{ required: true, message: '请输入分组名称', trigger: 'blur' }],
  vipLevel: [{ required: true, message: '请输入VIP等级', trigger: 'blur' }],
  windowDiscountPrice: [
    { validator: (rule, value, callback) => {
      if (value > formData.windowOriginalPrice) {
        callback(new Error('折后价不能大于原价'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ],
  accountDiscountPrice: [
    { validator: (rule, value, callback) => {
      if (value > formData.accountOriginalPrice) {
        callback(new Error('折后价不能大于原价'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ],
  hostDiscountPrice: [
    { validator: (rule, value, callback) => {
      if (value > formData.hostOriginalPrice) {
        callback(new Error('折后价不能大于原价'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ],
  fullDiscountPrice: [
    { validator: (rule, value, callback) => {
      if (value > formData.fullOriginalPrice) {
        callback(new Error('折后价不能大于原价'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ],
  pointsDiscountPrice: [
    { validator: (rule, value, callback) => {
      if (value > formData.pointsOriginalPrice) {
        callback(new Error('折后价不能大于原价'))
      } else {
        callback()
      }
    }, trigger: 'change' }
  ]
}

const nextVipLevel = computed(() => {
  const maxVip = tableData.value.reduce((max, item) => Math.max(max, item.vipLevel || 0), 0)
  return maxVip + 1
})

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
    Object.assign(formData, {
      id: row.id,
      name: row.name,
      vipLevel: row.vipLevel,
      amountThreshold: row.amountThreshold ? row.amountThreshold / 100 : 0,
      windowOriginalPrice: row.windowOriginalPrice ? row.windowOriginalPrice / 100 : 0,
      windowDiscountPrice: row.windowDiscountPrice ? row.windowDiscountPrice / 100 : 0,
      accountOriginalPrice: row.accountOriginalPrice ? row.accountOriginalPrice / 100 : 0,
      accountDiscountPrice: row.accountDiscountPrice ? row.accountDiscountPrice / 100 : 0,
      hostOriginalPrice: row.hostOriginalPrice ? row.hostOriginalPrice / 100 : 0,
      hostDiscountPrice: row.hostDiscountPrice ? row.hostDiscountPrice / 100 : 0,
      fullOriginalPrice: row.fullOriginalPrice ? row.fullOriginalPrice / 100 : 0,
      fullDiscountPrice: row.fullDiscountPrice ? row.fullDiscountPrice / 100 : 0,
      pointsOriginalPrice: row.pointsOriginalPrice ? row.pointsOriginalPrice / 100 : 0,
      pointsDiscountPrice: row.pointsDiscountPrice ? row.pointsDiscountPrice / 100 : 0,
      status: row.status
    })
  } else {
    Object.assign(formData, {
      id: '',
      name: '',
      vipLevel: 0,
      amountThreshold: 0,
      windowOriginalPrice: 100,
      windowDiscountPrice: 100,
      accountOriginalPrice: 50,
      accountDiscountPrice: 50,
      hostOriginalPrice: 200,
      hostDiscountPrice: 200,
      fullOriginalPrice: 300,
      fullDiscountPrice: 300,
      pointsOriginalPrice: 5,
      pointsDiscountPrice: 5,
      status: 'active'
    })
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    const submitData = {
      name: formData.name,
      amountThreshold: Math.round(formData.amountThreshold * 100),
      windowOriginalPrice: Math.round(formData.windowOriginalPrice * 100),
      windowDiscountPrice: Math.round(formData.windowDiscountPrice * 100),
      accountOriginalPrice: Math.round(formData.accountOriginalPrice * 100),
      accountDiscountPrice: Math.round(formData.accountDiscountPrice * 100),
      hostOriginalPrice: Math.round(formData.hostOriginalPrice * 100),
      hostDiscountPrice: Math.round(formData.hostDiscountPrice * 100),
      fullOriginalPrice: Math.round(formData.fullOriginalPrice * 100),
      fullDiscountPrice: Math.round(formData.fullDiscountPrice * 100),
      pointsOriginalPrice: Math.round(formData.pointsOriginalPrice * 100),
      pointsDiscountPrice: Math.round(formData.pointsDiscountPrice * 100),
      status: formData.status || 'active'
    }
    if (dialogType.value === 'add') {
      submitData.vipLevel = nextVipLevel.value
      await merchantGroupApi.create(submitData)
      ElMessage.success('分组创建成功')
    } else {
      submitData.id = formData.id
      submitData.vipLevel = formData.vipLevel
      await merchantGroupApi.update(submitData.id, submitData)
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

const formatPrice = (cents) => {
  if (!cents) return '-'
  return (cents / 100).toFixed(2) + '元'
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

.price-row {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.price-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.price-item .price-label {
  min-width: 70px;
}

.field-hint {
  margin-left: 12px;
  color: #8a8a8a;
  font-size: 12px;
}

.vip-level-auto {
  color: #67c23a;
  font-weight: 500;
}

.vip-level-display {
  color: #409eff;
  font-weight: 600;
  font-size: 16px;
}

.price-label {
  margin-right: 4px;
  color: #606266;
}

.page-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin: 0;
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