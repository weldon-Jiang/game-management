<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>激活码管理</h2>
        <span class="header-desc">生成和管理激活码</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showGenerateDialog">
          <el-icon><Plus /></el-icon>
          生成激活码
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索激活码"
          style="width: 200px"
          clearable
          @keyup.enter="loadCodes"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select
          v-model="searchStatus"
          placeholder="状态"
          style="width: 120px"
          clearable
          @change="loadCodes"
        >
          <el-option label="全部" value="" />
          <el-option label="未使用" value="unused" />
          <el-option label="已使用" value="used" />
        </el-select>
        <el-button @click="loadCodes">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>

      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
      >
        <el-table-column prop="code" label="激活码" min-width="150">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="subscriptionType" label="类型" width="140" align="center">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.subscriptionType)" size="small">
              {{ getTypeName(row.subscriptionType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="boundResourceNames" label="绑定资源" min-width="150">
          <template #default="{ row }">
            <span v-if="row.boundResourceNames">{{ row.boundResourceNames }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="originalPrice" label="原价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.originalPrice">{{ (row.originalPrice / 100).toFixed(2) }}元</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="discountPrice" label="折后价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.discountPrice" class="price-discount">{{ (row.discountPrice / 100).toFixed(2) }}元</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="durationDays" label="时长" width="80" align="center">
          <template #default="{ row }">
            <span>{{ row.durationDays || 30 }}天</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getCodeStatusType(row.status)" size="small">
              {{ getCodeStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="startTime" label="生效时间" width="110">
          <template #default="{ row }">
            <span v-if="row.startTime">{{ formatDate(row.startTime) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="endTime" label="到期时间" width="110">
          <template #default="{ row }">
            <span v-if="row.endTime">{{ formatDate(row.endTime) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="usedTime" label="使用时间" width="110">
          <template #default="{ row }">
            <span v-if="row.usedTime">{{ formatDate(row.usedTime) }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'unused'"
              type="primary"
              link
              size="small"
              @click="copyCode(row.code)"
            >
              复制
            </el-button>
            <el-button
              v-if="row.status === 'unused'"
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
          @size-change="loadCodes"
          @current-change="loadCodes"
        />
      </div>
    </div>

    <el-dialog
      v-model="generateDialogVisible"
      title="生成激活码"
      width="680px"
      :close-on-click-modal="false"
      class="generate-dialog"
    >
      <el-form
        ref="generateFormRef"
        :model="generateFormData"
        :rules="generateFormRules"
        label-width="100px"
        class="dialog-form"
      >
        <el-form-item v-if="authStore.isPlatformAdmin" label="商户" prop="merchantId">
          <el-select
            v-model="generateFormData.merchantId"
            placeholder="请选择商户"
            style="width: 100%"
            filterable
            @change="handleMerchantChange"
          >
            <el-option
              v-for="item in merchantList"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="订阅类型" prop="subscriptionType">
          <el-select
            v-model="generateFormData.subscriptionType"
            placeholder="请选择订阅类型"
            style="width: 100%"
            @change="handleSubscriptionTypeChange"
          >
            <el-option
              v-for="type in subscriptionTypes"
              :key="type.value"
              :label="type.label"
              :value="type.value"
            />
          </el-select>
        </el-form-item>

        <template v-if="generateFormData.subscriptionType === 'window_account'">
          <el-form-item label="绑定流媒体账号" prop="boundResourceIds">
            <el-select
              v-model="generateFormData.boundResourceIds"
              placeholder="请选择流媒体账号（可多选）"
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              @visible-change="handleStreamingAccountsVisibleChange"
            >
              <el-option
                v-for="item in streamingAccountList"
                :key="item.id"
                :label="item.username || item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
        </template>

        <template v-if="generateFormData.subscriptionType === 'account'">
          <el-form-item label="绑定游戏账号" prop="boundResourceIds">
            <el-select
              v-model="generateFormData.boundResourceIds"
              placeholder="请选择游戏账号（可多选）"
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              @visible-change="handleGameAccountsVisibleChange"
            >
              <el-option
                v-for="item in gameAccountList"
                :key="item.id"
                :label="item.xboxGameName || item.name || item.id"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
        </template>

        <template v-if="generateFormData.subscriptionType === 'host'">
          <el-form-item label="绑定Xbox主机" prop="boundResourceIds">
            <el-select
              v-model="generateFormData.boundResourceIds"
              placeholder="请选择Xbox主机（可多选）"
              multiple
              collapse-tags
              collapse-tags-tooltip
              style="width: 100%"
              @visible-change="handleXboxHostsVisibleChange"
            >
              <el-option
                v-for="item in xboxHostList"
                :key="item.id"
                :label="item.name || `Xbox-${item.xboxId?.slice(-4)}`"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
        </template>

        <template v-if="generateFormData.subscriptionType === 'points'">
          <el-form-item label="充值点数" prop="pointsAmount">
            <el-input-number
              v-model="generateFormData.pointsAmount"
              :min="1"
              :max="1000000"
              style="width: 100%"
              @change="handlePointsAmountChange"
            />
          </el-form-item>
        </template>

        <el-divider content-position="left">价格信息</el-divider>

        <div class="price-info-card">
          <div class="price-row">
            <span class="price-label">{{ generateFormData.subscriptionType === 'points' ? '单价' : '原价' }}</span>
            <span class="price-value price-original">{{ formatPrice(generateFormData.originalPrice) }}</span>
          </div>
          <div v-if="generateFormData.subscriptionType === 'points' && generateFormData.pointsAmount" class="price-row">
            <span class="price-label">总价</span>
            <span class="price-value price-discount">{{ formatPrice(calculateTotalPrice) }}</span>
          </div>
          <div v-else class="price-row">
            <span class="price-label">折后价</span>
            <span class="price-value price-discount">{{ formatPrice(generateFormData.discountPrice) }}</span>
          </div>
        </div>

        <div v-if="generateFormData.vipLevel > 0" class="vip-tip success">
          <el-icon><SuccessFilled /></el-icon>
          <span>当前VIP{{ generateFormData.vipLevel }}，已享受折扣价格</span>
        </div>
        <div v-else class="vip-tip info">
          <el-icon><InfoFilled /></el-icon>
          <span>当前无VIP等级，使用原价</span>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleGenerate">
          生成
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showCodeDialogVisible"
      title="激活码生成成功"
      width="450px"
    >
      <div class="generated-code-box">
        <p class="label">请妥善保存以下激活码：</p>
        <div class="code-display">
          <span class="code">{{ generatedCode }}</span>
          <el-button type="primary" link @click="copyCode(generatedCode)">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </div>
        <el-descriptions :column="1" border size="small" style="margin-top: 16px;">
          <el-descriptions-item label="类型">{{ getTypeName(generatedCodeType) }}</el-descriptions-item>
          <el-descriptions-item label="原价">{{ formatPrice(generatedCodeOriginalPrice) }}</el-descriptions-item>
          <el-descriptions-item label="折后价">{{ formatPrice(generatedCodeDiscountPrice) }}</el-descriptions-item>
        </el-descriptions>
        <p class="tip">激活码只显示一次，请及时保存！</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="showCodeDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, CopyDocument, SuccessFilled, InfoFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { activationApi, streamingApi, gameAccountApi, xboxApi, merchantApi } from '@/api'
import { getCodeStatusText, getCodeStatusType } from '@/utils/constants'

const authStore = useAuthStore()

const loading = ref(false)
const submitLoading = ref(false)
const tableData = ref([])
const searchKeyword = ref('')
const searchStatus = ref('')
const pagination = reactive({
  pageNum: 1,
  pageSize: 20,
  total: 0
})

const generateDialogVisible = ref(false)
const generateFormRef = ref(null)
const merchantList = ref([])
const generateFormData = reactive({
  merchantId: '',
  subscriptionType: 'points',
  boundResourceIds: [],
  boundResourceNames: [],
  pointsAmount: null,
  originalPrice: 0,
  discountPrice: 0,
  vipLevel: 0
})

const streamingAccountList = ref([])
const gameAccountList = ref([])
const xboxHostList = ref([])

const showCodeDialogVisible = ref(false)
const generatedCode = ref('')
const generatedCodeType = ref('')
const generatedCodeOriginalPrice = ref(0)
const generatedCodeDiscountPrice = ref(0)

const subscriptionTypes = [
  { value: 'window_account', label: '流媒体账号包月' },
  { value: 'account', label: '游戏账号包月' },
  { value: 'host', label: 'Xbox主机包月' },
  { value: 'full', label: '全功能包月' },
  { value: 'points', label: '点数充值' }
]

const calculateTotalPrice = computed(() => {
  if (generateFormData.subscriptionType === 'points' && generateFormData.pointsAmount) {
    return generateFormData.pointsAmount * generateFormData.discountPrice
  }
  return generateFormData.discountPrice
})

const generateFormRules = computed(() => {
  const rules = {
    subscriptionType: [{ required: true, message: '请选择订阅类型', trigger: 'change' }]
  }
  if (authStore.isPlatformAdmin) {
    rules.merchantId = [{ required: true, message: '请选择商户', trigger: 'change' }]
  }
  if (['window_account', 'account', 'host'].includes(generateFormData.subscriptionType)) {
    rules.boundResourceIds = [
      { required: true, message: '请选择绑定的资源', trigger: 'change' }
    ]
  }
  if (generateFormData.subscriptionType === 'points') {
    rules.pointsAmount = [
      { required: true, message: '请输入充值点数', trigger: 'blur' }
    ]
  }
  return rules
})

const loadCodes = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    if (searchStatus.value) {
      params.status = searchStatus.value
    }
    const res = await activationApi.listCodes(params)
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load activation codes:', error)
  } finally {
    loading.value = false
  }
}

const loadMerchants = async () => {
  if (!authStore.isPlatformAdmin) return
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchants:', error)
  }
}

const showGenerateDialog = async () => {
  generateFormData.merchantId = authStore.isPlatformAdmin ? '' : authStore.merchantId
  generateFormData.subscriptionType = 'points'
  generateFormData.boundResourceIds = []
  generateFormData.boundResourceNames = []
  generateFormData.pointsAmount = null
  generateFormData.originalPrice = 0
  generateFormData.discountPrice = 0
  generateFormData.vipLevel = 0
  await loadMerchants()
  if (!authStore.isPlatformAdmin) {
    await loadPrices()
  }
  generateDialogVisible.value = true
}

const loadPrices = async () => {
  try {
    const params = {}
    if (generateFormData.merchantId) {
      params.merchantId = generateFormData.merchantId
    }
    const res = await activationApi.getPrices(params)
    if (res.code === 200) {
      const prices = res.data
      const vipLevel = prices.vipLevel || 0
      generateFormData.vipLevel = vipLevel
      if (generateFormData.subscriptionType === 'points') {
        generateFormData.originalPrice = prices.pointsOriginalPrice || 500
        generateFormData.discountPrice = prices.pointsDiscountPrice || 500
      } else if (generateFormData.subscriptionType === 'window_account') {
        generateFormData.originalPrice = prices.windowOriginalPrice || 10000
        generateFormData.discountPrice = prices.windowDiscountPrice || 10000
      } else if (generateFormData.subscriptionType === 'account') {
        generateFormData.originalPrice = prices.accountOriginalPrice || 5000
        generateFormData.discountPrice = prices.accountDiscountPrice || 5000
      } else if (generateFormData.subscriptionType === 'host') {
        generateFormData.originalPrice = prices.hostOriginalPrice || 20000
        generateFormData.discountPrice = prices.hostDiscountPrice || 20000
      } else if (generateFormData.subscriptionType === 'full') {
        generateFormData.originalPrice = prices.fullOriginalPrice || 30000
        generateFormData.discountPrice = prices.fullDiscountPrice || 30000
      }
    }
  } catch (error) {
    console.error('Failed to load prices:', error)
  }
}

const handleMerchantChange = async () => {
  generateFormData.boundResourceIds = []
  generateFormData.boundResourceNames = []
  await loadPrices()
}

const handleSubscriptionTypeChange = async () => {
  generateFormData.boundResourceIds = []
  generateFormData.boundResourceNames = []
  generateFormData.pointsAmount = null
  await loadPrices()
}

const handlePointsAmountChange = () => {
  // 价格会根据 calculateTotalPrice 自动更新
}

const handleStreamingAccountsVisibleChange = async (visible) => {
  if (visible && generateFormData.merchantId) {
    try {
      const res = await streamingApi.list({ merchantId: generateFormData.merchantId, pageNum: 1, pageSize: 1000 })
      streamingAccountList.value = res.data?.records || []
    } catch (error) {
      console.error('Failed to load streaming accounts:', error)
    }
  }
}

const handleGameAccountsVisibleChange = async (visible) => {
  if (visible && generateFormData.merchantId) {
    try {
      const res = await gameAccountApi.list({ merchantId: generateFormData.merchantId, pageNum: 1, pageSize: 1000 })
      gameAccountList.value = res.data?.records || []
    } catch (error) {
      console.error('Failed to load game accounts:', error)
    }
  }
}

const handleXboxHostsVisibleChange = async (visible) => {
  if (visible && generateFormData.merchantId) {
    try {
      const res = await xboxApi.listPage({ merchantId: generateFormData.merchantId, pageNum: 1, pageSize: 1000 })
      xboxHostList.value = res.data?.records || []
    } catch (error) {
      console.error('Failed to load Xbox hosts:', error)
    }
  }
}

const handleGenerate = async () => {
  const valid = await generateFormRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    let boundResourceNames = []
    if (generateFormData.subscriptionType === 'window_account') {
      boundResourceNames = streamingAccountList.value
        .filter(item => generateFormData.boundResourceIds.includes(item.id))
        .map(item => item.username || item.name)
    } else if (generateFormData.subscriptionType === 'account') {
      boundResourceNames = gameAccountList.value
        .filter(item => generateFormData.boundResourceIds.includes(item.id))
        .map(item => item.xboxGameName || item.name)
    } else if (generateFormData.subscriptionType === 'host') {
      boundResourceNames = xboxHostList.value
        .filter(item => generateFormData.boundResourceIds.includes(item.id))
        .map(item => item.name || `Xbox-${item.xboxId?.slice(-4)}`)
    }

    const requestData = {
      merchantId: generateFormData.merchantId || undefined,
      subscriptionType: generateFormData.subscriptionType,
      boundResourceIds: generateFormData.boundResourceIds.length > 0 ? generateFormData.boundResourceIds : null,
      boundResourceNames: boundResourceNames.length > 0 ? boundResourceNames : null,
      pointsAmount: generateFormData.subscriptionType === 'points' ? generateFormData.pointsAmount : null
    }

    const res = await activationApi.createCode(requestData)
    if (res.code === 200) {
      generatedCode.value = res.data.code
      generatedCodeType.value = res.data.subscriptionType
      generatedCodeOriginalPrice.value = res.data.originalPrice
      generatedCodeDiscountPrice.value = res.data.discountPrice
      generateDialogVisible.value = false
      showCodeDialogVisible.value = true
      loadCodes()
    }
  } catch (error) {
    console.error('Failed to generate code:', error)
  } finally {
    submitLoading.value = false
  }
}

const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success('激活码已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该激活码？删除后无法恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    await activationApi.delete(row.id)
    ElMessage.success('激活码删除成功')
    loadCodes()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete:', error)
    }
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

const formatPrice = (cents) => {
  if (!cents) return '-'
  return (cents / 100).toFixed(2) + '元'
}

const getTypeTag = (type) => {
  const map = {
    'points': 'primary',
    'account': 'success',
    'window_account': 'warning',
    'host': 'danger',
    'full': 'info'
  }
  return map[type] || 'info'
}

const getTypeName = (type) => {
  const map = {
    'points': '点数充值',
    'account': '游戏账号包月',
    'window_account': '流媒体账号包月',
    'host': 'Xbox主机包月',
    'full': '全功能包月'
  }
  return map[type] || type || '点数充值'
}

onMounted(() => {
  loadCodes()
})
</script>

<style scoped>
.code-text {
  font-family: var(--font-mono);
  color: #a78bfa;
  font-size: var(--font-size-sm);
}

.price-discount {
  color: var(--success);
  font-weight: 600;
}

.price-original {
  color: var(--text-muted);
  text-decoration: line-through;
}

.generated-code-box {
  text-align: center;
  padding: 20px 0;
}

.generated-code-box .label {
  color: var(--text-muted);
  font-size: var(--font-size-md);
  margin-bottom: var(--spacing-lg);
}

.generated-code-box .code-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--primary-soft);
  border: 1px solid var(--primary-strong);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
}

.generated-code-box .code {
  font-family: var(--font-mono);
  font-size: var(--font-size-xl);
  font-weight: 600;
  color: #a78bfa;
  letter-spacing: 1px;
}

.generated-code-box .tip {
  color: var(--warning);
  font-size: var(--font-size-xs);
  margin-top: var(--spacing-md);
}

.generate-dialog .price-info-card {
  background: #f5f7fa;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

.generate-dialog .price-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.generate-dialog .price-row:not(:last-child) {
  border-bottom: 1px solid #e4e7ed;
}

.generate-dialog .price-label {
  color: #606266;
  font-size: 14px;
}

.generate-dialog .price-value {
  font-size: 18px;
  font-weight: 600;
}

.generate-dialog .price-value.price-original {
  color: #909399;
  text-decoration: line-through;
}

.generate-dialog .price-value.price-discount {
  color: #67c23a;
}

.generate-dialog .vip-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
}

.generate-dialog .vip-tip.success {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #d4edda;
}

.generate-dialog .vip-tip.info {
  background: #f4f4f5;
  color: #909399;
  border: 1px solid #e4e7ed;
}
</style>