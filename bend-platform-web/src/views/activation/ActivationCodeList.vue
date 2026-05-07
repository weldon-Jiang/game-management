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

    <!-- 激活码列表 -->
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
          v-if="isPlatformAdmin"
          v-model="searchMerchantId"
          placeholder="选择商户"
          style="width: 180px"
          clearable
          @change="loadCodes"
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
        <el-button @click="loadCodes">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button
          v-if="authStore.isPlatformAdmin"
          type="danger"
          :disabled="selectedCodes.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedCodes.length }})
        </el-button>
      </div>

      <div class="table-container">
        <el-table
          :data="filteredCodes"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
          @selection-change="handleSelectionChange"
        >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="code" label="激活码" min-width="220">
          <template #default="{ row }">
            <span class="code-text">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.merchantName">{{ row.merchantName }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="subscriptionType" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.subscriptionType)" size="small">
              {{ getTypeName(row.subscriptionType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="points" label="内容" min-width="180">
          <template #default="{ row }">
            <template v-if="row.subscriptionType === 'points' || !row.subscriptionType">
              <span class="points-value">{{ row.points || 0 }} 点</span>
            </template>
            <template v-else>
              <div class="subscription-info">
                <span>{{ row.targetName || '-' }}</span>
                <br />
                <small class="text-muted">{{ row.durationDays || 0 }}天</small>
              </div>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getCodeStatusType(row.status)" size="small">
              {{ getCodeStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="usedByName" label="使用者" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.usedByName">{{ row.usedByName }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="usedTime" label="使用时间" width="170">
          <template #default="{ row }">
            {{ row.usedTime ? formatDate(row.usedTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="expireTime" label="过期时间" width="170">
          <template #default="{ row }">
            {{ row.expireTime ? formatDate(row.expireTime) : '永不过期' }}
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" align="center">
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
          </template>
        </el-table-column>
      </el-table>
      </div>

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

    <!-- 生成激活码对话框 -->
    <el-dialog
      v-model="generateDialogVisible"
      title="生成激活码"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="generateFormRef"
        :model="generateFormData"
        :rules="generateFormRules"
        label-width="90px"
        class="dialog-form"
      >
        <el-form-item v-if="isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="generateFormData.merchantId"
            placeholder="请选择商户"
            style="width: 100%"
            clearable
          >
            <el-option
              v-for="merchant in merchantList"
              :key="merchant.id"
              :label="merchant.name"
              :value="merchant.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="批次名称" prop="batchName">
          <el-input v-model="generateFormData.batchName" placeholder="请输入批次名称（可选）" />
        </el-form-item>
        <el-form-item label="类型" prop="subscriptionType">
          <el-radio-group v-model="generateFormData.subscriptionType" @change="handleTypeChange">
            <el-radio v-for="type in filteredSubscriptionTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </el-radio>
          </el-radio-group>
          <div v-if="!generateFormData.merchantId" class="form-tip">请先选择商户</div>
          <div v-else-if="filteredSubscriptionTypes.length === 1 && filteredSubscriptionTypes[0].value === 'points'" class="form-tip">当前商户无VIP等级，仅支持点数充值</div>
        </el-form-item>
        <template v-if="generateFormData.subscriptionType === 'points'">
          <el-form-item label="充值点数" prop="points">
            <el-input-number
              v-model="generateFormData.points"
              :min="1"
              :max="1000000"
              style="width: 100%"
            />
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="选择目标" prop="targetId">
            <el-select
              v-model="generateFormData.targetId"
              placeholder="请选择目标"
              style="width: 100%"
              @visible-change="handleTargetVisibleChange"
            >
              <el-option
                v-for="item in targetList"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="时长">
            <span class="duration-display">30 天（固定）</span>
          </el-form-item>
          <el-form-item label="消耗点数">
            <span class="points-display">{{ generateFormData.points || '请先选择目标' }}</span>
            <span v-if="generateFormData.points" class="form-tip">（单价 × 30天）</span>
          </el-form-item>
        </template>
        <el-form-item label="生成数量" prop="count">
          <el-input-number
            v-model="generateFormData.count"
            :min="1"
            :max="100"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleGenerate">
          生成
        </el-button>
      </template>
    </el-dialog>

    <!-- 生成的激活码展示对话框 -->
    <el-dialog
      v-model="showCodeDialogVisible"
      title="激活码生成成功"
      width="420px"
    >
      <div class="generated-code-box">
        <p class="label">请妥善保存以下激活码：</p>
        <div class="code-display">
          <span class="code">{{ generatedCode }}</span>
          <el-button type="primary" link @click="copyCode(generatedCode)">
            <el-icon><CopyDocument /></el-icon>
          </el-button>
        </div>
        <p class="tip">激活码只显示一次，请及时保存！</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="showCodeDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, CopyDocument, Delete } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { activationApi, merchantApi, gameAccountApi, streamingApi, xboxApi, merchantGroupApi } from '@/api'
import { getCodeStatusText, getCodeStatusType } from '@/utils/constants'

/**
 * 激活码管理页面
 * 提供单个激活码的生成、查看、复制和删除功能
 * 激活码只能使用一次，使用后状态变为已使用
 */

// ==================== 状态定义 ====================

const authStore = useAuthStore()

const isPlatformAdmin = computed(() => authStore.isPlatformAdmin)

const merchantList = ref([])

/**
 * 表格加载状态
 */
const loading = ref(false)

/**
 * 提交按钮加载状态
 */
const submitLoading = ref(false)

/**
 * 激活码列表数据
 */
const tableData = ref([])

/**
 * 选中的激活码列表
 */
const selectedCodes = ref([])

/**
 * 搜索关键词
 */
const searchKeyword = ref('')

/**
 * 商户查询条件
 */
const searchMerchantId = ref('')

/**
 * 分页参数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 20,
  total: 0
})

/**
 * 过滤后的激活码列表
 */
const filteredCodes = computed(() => {
  if (!searchKeyword.value) return tableData.value
  const keyword = searchKeyword.value.toLowerCase()
  return tableData.value.filter(c =>
    c.code.toLowerCase().includes(keyword)
  )
})

/**
 * 生成对话框状态
 */
const generateDialogVisible = ref(false)
const generateFormRef = ref(null)

/**
 * 目标列表（根据类型加载）
 */
const targetList = ref([])

/**
 * 生成表单数据
 */
const generateFormData = reactive({
  merchantId: '',
  batchName: '',
  subscriptionType: 'points',
  targetId: '',
  targetName: '',
  points: null,
  durationDays: 30,
  count: 1
})

/**
 * 生成表单验证规则（动态）
 */
const generateFormRules = computed(() => {
  const rules = {}
  if (generateFormData.subscriptionType === 'points') {
    rules.points = [
      { required: true, message: '请输入充值点数', trigger: 'blur' }
    ]
  } else {
    rules.targetId = [
      { required: true, message: '请选择目标', trigger: 'change' }
    ]
  }
  return rules
})

/**
 * 激活码展示对话框状态
 */
const showCodeDialogVisible = ref(false)
const generatedCode = ref('')

/**
 * 商户VIP分组信息（用于确定允许的订阅类型）
 */
const merchantGroupInfo = ref(null)

/**
 * 允许的订阅类型列表（根据VIP等级和分组权限）
 * 如果商户有VIP等级分组，则允许所有订阅类型；否则仅允许点数充值
 */
const allowedSubscriptionTypes = computed(() => {
  if (!generateFormData.merchantId) {
    return ['points']
  }
  if (!merchantGroupInfo.value || !merchantGroupInfo.value.vipLevel || merchantGroupInfo.value.vipLevel === 0) {
    return ['points']
  }
  return ['points', 'account', 'window', 'host']
})

/**
 * 可用的订阅类型选项
 */
const subscriptionTypeOptions = [
  { value: 'points', label: '点数充值' },
  { value: 'account', label: '游戏账号' },
  { value: 'window', label: '窗口' },
  { value: 'host', label: '主机' }
]

/**
 * 过滤后的订阅类型选项（仅显示允许的类型）
 */
const filteredSubscriptionTypes = computed(() => {
  return subscriptionTypeOptions.filter(opt => allowedSubscriptionTypes.value.includes(opt.value))
})

// ==================== 方法定义 ====================

/**
 * 加载激活码列表
 */
const loadCodes = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    if (isPlatformAdmin.value && searchMerchantId.value) {
      params.merchantId = searchMerchantId.value
    }
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    const res = await activationApi.listCodes(params)
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load activation codes:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 加载商户列表
 */
const loadMerchantList = async () => {
  if (!isPlatformAdmin.value) {
    merchantList.value = []
    return
  }
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchant list:', error)
    merchantList.value = []
  }
}

/**
 * 显示生成对话框
 */
const showGenerateDialog = async () => {
  generateFormData.merchantId = ''
  generateFormData.batchName = ''
  generateFormData.subscriptionType = 'points'
  generateFormData.targetId = ''
  generateFormData.targetName = ''
  generateFormData.points = null
  generateFormData.durationDays = 30
  generateFormData.count = 1
  targetList.value = []
  merchantGroupInfo.value = null
  await loadMerchantList()
  generateDialogVisible.value = true
}

/**
 * 类型变更处理
 */
const handleTypeChange = () => {
  generateFormData.targetId = ''
  generateFormData.targetName = ''
  targetList.value = []
  calculatePoints()
}

/**
 * 监听商户变更，清空目标列表并获取VIP分组信息
 */
watch(() => generateFormData.merchantId, async (newMerchantId) => {
  generateFormData.targetId = ''
  generateFormData.targetName = ''
  targetList.value = []
  merchantGroupInfo.value = null
  generateFormData.points = null
  generateFormData.durationDays = 30

  if (newMerchantId) {
    try {
      const res = await merchantGroupApi.getByMerchantId(newMerchantId)
      if (res.code === 200 && res.data) {
        merchantGroupInfo.value = res.data
        if (!allowedSubscriptionTypes.value.includes(generateFormData.subscriptionType)) {
          generateFormData.subscriptionType = 'points'
        }
        calculatePoints()
      }
    } catch (error) {
      console.error('Failed to load merchant group info:', error)
    }
  }
})

/**
 * 目标下拉框可见性变化处理
 */
const handleTargetVisibleChange = (visible) => {
  if (visible) {
    loadTargets()
  }
}

/**
 * 加载目标列表
 */
const loadTargets = async () => {
  if (!generateFormData.merchantId) {
    ElMessage.warning('请先选择商户')
    targetList.value = []
    return
  }

  try {
    const type = generateFormData.subscriptionType
    const merchantId = generateFormData.merchantId
    let res
    if (type === 'account') {
      res = await gameAccountApi.list({ merchantId, pageNum: 1, pageSize: 1000 })
      targetList.value = (res.data?.records || []).map(item => ({
        id: item.id,
        name: item.xboxGameName || item.id
      }))
    } else if (type === 'window') {
      res = await streamingApi.list({ merchantId, pageNum: 1, pageSize: 1000 })
      targetList.value = (res.data?.records || []).map(item => ({
        id: item.id,
        name: item.username || item.name || 'Unknown'
      }))
    } else if (type === 'host') {
      res = await xboxApi.listPage({ merchantId, pageNum: 1, pageSize: 1000 })
      targetList.value = (res.data?.records || []).map(item => ({
        id: item.id,
        name: item.name || `Xbox-${item.xboxId?.slice(-4) || item.id?.slice(-4)}`
      }))
    }
  } catch (error) {
    console.error('Failed to load targets:', error)
    targetList.value = []
  }
}

/**
 * 根据商户VIP分组定价自动计算点数
 * 时长固定30天，点数 = 单价 × 30
 */
const calculatePoints = () => {
  const type = generateFormData.subscriptionType
  const group = merchantGroupInfo.value

  if (!group || type === 'points') {
    generateFormData.points = null
    generateFormData.durationDays = 30
    return
  }

  let pricePerDay = 0
  if (type === 'host') {
    pricePerDay = parseFloat(group.hostPrice) || 0
  } else if (type === 'window') {
    pricePerDay = parseFloat(group.windowPrice) || 0
  } else if (type === 'account') {
    pricePerDay = parseFloat(group.accountPrice) || 0
  }

  const durationDays = 30
  const totalPoints = Math.round(pricePerDay * durationDays * 100) / 100

  generateFormData.points = totalPoints
  generateFormData.durationDays = durationDays
}

/**
 * 监听目标变更，重新计算点数
 */
watch(() => generateFormData.targetId, () => {
  calculatePoints()
})

/**
 * 生成激活码
 */
const handleGenerate = async () => {
  const valid = await generateFormRef.value.validate().catch(() => false)
  if (!valid) return

  if (generateFormData.subscriptionType !== 'points') {
    if (!generateFormData.targetId) {
      ElMessage.warning('请选择目标')
      return
    }
    const selectedTarget = targetList.value.find(t => t.id === generateFormData.targetId)
    if (selectedTarget) {
      generateFormData.targetName = selectedTarget.name
    }
  }

  submitLoading.value = true
  try {
    const requestData = {
      merchantId: generateFormData.merchantId || null,
      batchName: generateFormData.batchName || null,
      subscriptionType: generateFormData.subscriptionType,
      targetId: generateFormData.subscriptionType !== 'points' ? generateFormData.targetId : null,
      targetName: generateFormData.subscriptionType !== 'points' ? generateFormData.targetName : null,
      points: generateFormData.points || 0,
      durationDays: generateFormData.subscriptionType !== 'points' ? generateFormData.durationDays : null,
      count: generateFormData.count
    }
    const res = await activationApi.generateBatch(requestData)
    generatedCode.value = res.data ? `批次 ${res.data.batchName || ''} 创建成功` : '创建成功'
    generateDialogVisible.value = false
    showCodeDialogVisible.value = true
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 复制激活码
 * @param {string} code - 激活码
 */
const copyCode = (code) => {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success('激活码已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制')
  })
}

/**
 * 处理表格选择变化
 * @param {Array} selection - 选中的行数据
 */
const handleSelectionChange = (selection) => {
  selectedCodes.value = selection
}

/**
 * 批量删除激活码（仅能删除未使用的）
 */
const handleBatchDelete = async () => {
  if (selectedCodes.value.length === 0) {
    ElMessage.warning('请先选择要删除的激活码')
    return
  }

  const unusedCodes = selectedCodes.value.filter(item => item.status === 'unused')
  if (unusedCodes.length === 0) {
    ElMessage.warning('只能删除未使用的激活码')
    return
  }

  const usedCount = selectedCodes.value.length - unusedCodes.length
  const message = usedCount > 0
    ? `选中了 ${selectedCodes.value.length} 个激活码，其中 ${usedCount} 个已使用将无法删除。确定删除 ${unusedCodes.length} 个未使用的激活码吗？`
    : `确定要删除选中的 ${unusedCodes.length} 个未使用激活码吗？此操作不可恢复！`

  await ElMessageBox.confirm(
    message,
    '确认删除',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )

  try {
    const ids = unusedCodes.map(item => item.id)
    await activationApi.deleteBatch(ids)
    ElMessage.success(`成功删除 ${ids.length} 个激活码`)
    selectedCodes.value = []
    loadCodes()
  } catch (error) {
    // 错误已在拦截器中处理
  }
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

/**
 * 获取类型标签颜色
 */
const getTypeTag = (type) => {
  const map = {
    'points': 'primary',
    'account': 'success',
    'window': 'warning',
    'host': 'danger'
  }
  return map[type] || 'info'
}

/**
 * 获取类型名称
 */
const getTypeName = (type) => {
  const map = {
    'points': '点数',
    'account': '游戏账号',
    'window': '窗口',
    'host': '主机'
  }
  return map[type] || type || '点数'
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadCodes()
  if (isPlatformAdmin.value) {
    loadMerchantList()
  }
})
</script>

<style scoped>
/* 组件特有样式，去除重复的全局样式覆盖 */

.code-text {
  font-family: var(--font-mono);
  color: #a78bfa;
  font-size: var(--font-size-sm);
}

.points-value {
  color: var(--warning);
  font-weight: 500;
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
}

.subscription-info {
  line-height: 1.4;
}

.subscription-info small {
  font-size: 11px;
}

.form-tip {
  color: var(--text-muted);
  font-size: var(--font-size-xs);
  margin-top: var(--spacing-sm);
}

.duration-display {
  color: var(--text-primary);
  font-weight: 500;
}

.points-display {
  color: var(--warning);
  font-weight: 600;
  font-size: var(--font-size-lg);
}
</style>