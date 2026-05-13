<template>
  <div class="page-container recharge-card-management">
    <div class="page-header">
      <h2>充值卡管理</h2>
      <div class="header-actions">
        <el-button v-if="authStore.isPlatformAdmin" type="primary" @click="showBatchDialog">
          生成批次
        </el-button>
        <el-button @click="loadBatches">刷新</el-button>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="批次管理" name="batches">
        <div class="content-card">
          <el-table :data="batchTableData" v-loading="batchLoading" class="data-table">
            <el-table-column prop="name" label="批次名称" />
            <el-table-column prop="cardType" label="类型" width="120">
              <template #default="{ row }">
                {{ getCardTypeName(row.cardType) }}
              </template>
            </el-table-column>
            <el-table-column prop="denomination" label="面额(点)" width="100" />
            <el-table-column prop="bonusPoints" label="赠送" width="80" />
            <el-table-column prop="price" label="售价(元)" width="100">
              <template #default="{ row }">
                {{ row.price ? `¥${row.price}` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="totalCount" label="生成数量" width="100" />
            <el-table-column prop="generatedCount" label="已生成" width="100" />
            <el-table-column prop="soldCount" label="已售出" width="100" />
            <el-table-column prop="usedCount" label="已使用" width="100" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getBatchStatusType(row.status)" size="small">
                  {{ getBatchStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="showCardList(row)">查看卡密</el-button>
                <el-button v-if="row.status === 'completed'" type="success" link size="small" @click="exportCards(row)">
                  导出
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap">
            <el-pagination
              v-model:current-page="batchPagination.pageNum"
              v-model:page-size="batchPagination.pageSize"
              :total="batchPagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              @change="loadBatches"
            />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="卡密查询" name="cards">
        <div class="content-card">
          <div class="table-filters">
            <el-input v-model="searchCardNo" placeholder="输入卡号查询" clearable style="width: 200px" />
            <el-button @click="searchCard">查询</el-button>
          </div>

          <el-table :data="cardTableData" v-loading="cardLoading" class="data-table">
            <el-table-column prop="cardNo" label="卡号" width="180" show-overflow-tooltip />
            <el-table-column label="面额" width="100">
              <template #default="{ row }">
                {{ row.denomination + row.bonusPoints }}点
              </template>
            </el-table-column>
            <el-table-column prop="price" label="售价" width="80">
              <template #default="{ row }">
                {{ row.price ? `¥${row.price}` : '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getCardStatusType(row.status)" size="small">
                  {{ getCardStatusName(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="所属商户" min-width="150">
              <template #default="{ row }">
                {{ row.soldToMerchantId || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="使用商户" min-width="150">
              <template #default="{ row }">
                {{ row.usedByMerchantId || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="有效期至" width="120">
              <template #default="{ row }">
                {{ row.expireTime ? formatDate(row.expireTime) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="创建时间" width="120">
              <template #default="{ row }">
                {{ formatDate(row.createdTime) }}
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrap">
            <el-pagination
              v-model:current-page="cardPagination.pageNum"
              v-model:page-size="cardPagination.pageSize"
              :total="cardPagination.total"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              @change="loadCards"
            />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="batchDialogVisible" title="生成充值卡批次" width="500px">
      <el-form ref="batchFormRef" :model="batchForm" label-width="100px">
        <el-form-item label="批次名称" required>
          <el-input v-model="batchForm.name" placeholder="请输入批次名称" />
        </el-form-item>
        <el-form-item label="卡类型">
          <el-select v-model="batchForm.cardType">
            <el-option label="平台卡" value="platform_card" />
            <el-option label="商户卡" value="merchant_card" />
          </el-select>
        </el-form-item>
        <el-form-item label="生成数量">
          <el-input-number v-model="batchForm.count" :min="1" :max="10000" />
        </el-form-item>
        <el-form-item label="面额(点)">
          <el-input-number v-model="batchForm.denomination" :min="1" />
        </el-form-item>
        <el-form-item label="赠送点数">
          <el-input-number v-model="batchForm.bonusPoints" :min="0" />
        </el-form-item>
        <el-form-item label="售价(元)">
          <el-input-number v-model="batchForm.price" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="有效期(天)">
          <el-input-number v-model="batchForm.validDays" :min="1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchLoading" @click="handleCreateBatch">生成</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cardListDialogVisible" title="卡密列表" width="900px">
      <div class="card-list-toolbar">
        <el-select v-model="cardListFilter.status" placeholder="状态" clearable style="width: 120px">
          <el-option label="未使用" value="unused" />
          <el-option label="已售出" value="sold" />
          <el-option label="已使用" value="used" />
        </el-select>
        <el-button @click="loadCardList">筛选</el-button>
        <el-button type="success" @click="exportCurrentBatchCards">导出当前批次</el-button>
      </div>
      <el-table :data="cardListData" max-height="400" class="data-table">
        <el-table-column prop="cardNo" label="卡号" width="180" show-overflow-tooltip />
        <el-table-column label="卡密" width="150">
          <template #default="{ row }">
            ********
          </template>
        </el-table-column>
        <el-table-column label="面额" width="100">
          <template #default="{ row }">
            {{ row.denomination + row.bonusPoints }}点
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getCardStatusType(row.status)" size="small">
              {{ getCardStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="有效期至" width="120">
          <template #default="{ row }">
            {{ row.expireTime ? formatDate(row.expireTime) : '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rechargeCardApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const activeTab = ref('batches')

const batchLoading = ref(false)
const batchTableData = ref([])
const batchPagination = reactive({ pageNum: 1, pageSize: 10, total: 0 })
const batchDialogVisible = ref(false)
const batchFormRef = ref(null)
const batchForm = reactive({
  name: '',
  cardType: 'platform_card',
  count: 100,
  denomination: 100,
  bonusPoints: 0,
  price: 100,
  validDays: 365
})

const cardLoading = ref(false)
const cardTableData = ref([])
const cardPagination = reactive({ pageNum: 1, pageSize: 10, total: 0 })
const searchCardNo = ref('')

const cardListDialogVisible = ref(false)
const currentBatchId = ref(null)
const cardListFilter = reactive({ status: '' })
const cardListData = ref([])

const cardTypeNames = {
  platform_card: '平台卡',
  merchant_card: '商户卡'
}

const getCardTypeName = (type) => cardTypeNames[type] || type

const getBatchStatusName = (status) => {
  const map = { pending: '待生成', generating: '生成中', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

const getBatchStatusType = (status) => {
  const map = { pending: 'info', generating: 'warning', completed: 'success', cancelled: 'danger' }
  return map[status] || 'info'
}

const getCardStatusName = (status) => {
  const map = { unused: '未使用', sold: '已售出', used: '已使用', cancelled: '已取消', expired: '已过期' }
  return map[status] || status
}

const getCardStatusType = (status) => {
  const map = { unused: 'success', sold: 'warning', used: 'info', cancelled: 'danger', expired: 'danger' }
  return map[status] || 'info'
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const loadBatches = async () => {
  batchLoading.value = true
  try {
    const res = await rechargeCardApi.listBatches({
      pageNum: batchPagination.pageNum,
      pageSize: batchPagination.pageSize
    })
    batchTableData.value = res.data?.records || []
    batchPagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load batches:', error)
  } finally {
    batchLoading.value = false
  }
}

const loadCards = async () => {
  cardLoading.value = true
  try {
    const res = await rechargeCardApi.listCards({
      pageNum: cardPagination.pageNum,
      pageSize: cardPagination.pageSize
    })
    cardTableData.value = res.data?.records || []
    cardPagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load cards:', error)
  } finally {
    cardLoading.value = false
  }
}

const onTabChange = () => {
  if (activeTab.value === 'batches') {
    loadBatches()
  } else {
    loadCards()
  }
}

const showBatchDialog = () => {
  Object.assign(batchForm, {
    name: '',
    cardType: 'platform_card',
    count: 100,
    denomination: 100,
    bonusPoints: 0,
    price: 100,
    validDays: 365
  })
  batchDialogVisible.value = true
}

const handleCreateBatch = async () => {
  if (!batchForm.name) {
    ElMessage.warning('请输入批次名称')
    return
  }
  batchLoading.value = true
  try {
    await rechargeCardApi.createBatch(batchForm)
    ElMessage.success('批次创建成功')
    batchDialogVisible.value = false
    loadBatches()
  } catch (error) {
    console.error('Failed to create batch:', error)
  } finally {
    batchLoading.value = false
  }
}

const showCardList = (row) => {
  currentBatchId.value = row.id
  cardListFilter.status = ''
  loadCardList()
  cardListDialogVisible.value = true
}

const loadCardList = async () => {
  try {
    const res = await rechargeCardApi.listCards({
      batchId: currentBatchId.value,
      status: cardListFilter.status,
      pageNum: 1,
      pageSize: 1000
    })
    cardListData.value = res.data?.records || []
  } catch (error) {
    console.error('Failed to load cards:', error)
  }
}

const exportCards = async (row) => {
  try {
    const res = await rechargeCardApi.exportCards(row.id)
    const cards = res.data || []
    let content = '卡号,卡密,面额,状态,有效期\n'
    cards.forEach(card => {
      content += `${card.cardNo},******${card.pointsToGrant},${card.status},${card.expireTime || '-'}\n`
    })
    const blob = new Blob([content], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recharge_cards_${row.id}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (error) {
    console.error('Export failed:', error)
  }
}

const exportCurrentBatchCards = () => {
  if (!currentBatchId.value) return
  const batch = batchTableData.value.find(b => b.id === currentBatchId.value)
  if (batch) {
    exportCards(batch)
  }
}

const searchCard = async () => {
  if (!searchCardNo.value) {
    loadCards()
    return
  }
  cardLoading.value = true
  try {
    const res = await rechargeCardApi.getCard(searchCardNo.value)
    cardTableData.value = res.data ? [res.data] : []
    cardPagination.total = res.data ? 1 : 0
  } catch (error) {
    console.error('Search failed:', error)
  } finally {
    cardLoading.value = false
  }
}

onMounted(() => {
  loadBatches()
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

.header-actions {
  display: flex;
  gap: 12px;
}

.table-filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.card-list-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
