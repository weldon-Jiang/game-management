<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>任务管理</h2>
        <span class="header-desc">查看自动化任务执行情况</span>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-select
          v-if="authStore.isPlatformAdmin"
          v-model="filterMerchantId"
          placeholder="商户筛选"
          style="width: 160px"
          clearable
          filterable
          @change="handleMerchantChange"
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
        <el-select
          v-model="filterAgentId"
          placeholder="Agent筛选"
          style="width: 220px"
          clearable
          filterable
          :disabled="authStore.isPlatformAdmin && !filterMerchantId"
          @change="handleSearch"
        >
          <el-option
            v-for="agent in agentOptions"
            :key="agent.agentId"
            :label="formatAgentLabel(agent)"
            :value="agent.agentId"
          />
        </el-select>
        <el-select
          v-model="filterStreamingAccountId"
          placeholder="串流账号筛选"
          style="width: 200px"
          clearable
          filterable
          :disabled="authStore.isPlatformAdmin && !filterMerchantId"
          @change="handleSearch"
        >
          <el-option
            v-for="account in streamingAccountOptions"
            :key="account.id"
            :label="formatStreamingLabel(account)"
            :value="account.id"
          />
        </el-select>
        <el-select
          v-model="filterStatus"
          placeholder="状态筛选"
          style="width: 140px"
          clearable
          @change="handleSearch"
        >
          <el-option label="全部" value="" />
          <el-option label="待执行" value="pending" />
          <el-option label="执行中" value="running" />
          <el-option label="已暂停" value="paused" />
          <el-option label="已完成" value="completed" />
          <el-option label="已失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
          <el-option label="已停止" value="stopped" />
        </el-select>
        <el-button @click="handleSearch">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>

      <div class="table-container">
        <el-table
          :data="tableData"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
        >
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.merchantName || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="streamingAccountName" label="串流账号" width="108" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.streamingAccountName || row.streamingAccountId || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="name" label="任务名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="88" align="center">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row.status)" size="small">
              {{ getTaskStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="gameActionType" label="游戏操作" width="96" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag v-if="row.gameActionType" size="small" type="info">
              {{ getGameActionTypeText(row.gameActionType) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="sessionPhase" label="会话阶段" width="132" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.sessionPhase" size="small" :type="getSessionPhaseType(row.sessionPhase)">
              {{ getSessionPhaseText(row.sessionPhase) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="账号进度" width="88" align="center" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.result && row.result.includes('/')">
              {{ row.result }}
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="targetAgentId" label="执行Agent" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.targetAgentId">{{ row.targetAgentName || row.targetAgentId }}</span>
            <span v-else class="text-muted">未分配</span>
          </template>
        </el-table-column>
        <el-table-column prop="errorMessage" label="错误信息" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.errorMessage" class="text-danger">{{ row.errorMessage }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="168" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.createdTime ? formatDate(row.createdTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="goDetail(row)">
              详情
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="primary"
              link
              size="small"
              @click="showAssignDialog(row)"
            >
              分配
            </el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'failed'"
              type="warning"
              link
              size="small"
              @click="handleRetry(row)"
            >
              重试
            </el-button>
            <el-button
              v-if="row.status === 'running' || row.status === 'pending'"
              type="danger"
              link
              size="small"
              @click="handleCancel(row)"
            >
              取消
            </el-button>
            <el-button
              v-if="row.status === 'running' && row.targetAgentId"
              type="success"
              link
              size="small"
              @click="handleShowWindow(row)"
            >
              显示窗口
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
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
      </div>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      title="创建任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="100px" ref="createFormRef">
        <el-form-item label="任务名称" prop="name" required>
          <el-input v-model="createForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务类型" prop="type" required>
          <el-select v-model="createForm.type" placeholder="请选择任务类型" style="width: 100%">
            <el-option label="模板匹配" value="template_match" />
            <el-option label="输入序列" value="input_sequence" />
            <el-option label="场景检测" value="scene_detection" />
            <el-option label="账号切换" value="account_switch" />
            <el-option label="串流控制" value="stream_control" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-input-number v-model="createForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="任务参数" prop="params">
          <el-input
            v-model="createForm.paramsJson"
            type="textarea"
            :rows="4"
            placeholder='请输入JSON格式的任务参数，如: {"template": "start_button.png", "threshold": 0.8}'
          />
        </el-form-item>
        <el-form-item label="显示游戏窗口" prop="enableWindowDisplay">
          <el-switch
            v-model="createForm.enableWindowDisplay"
            :active-value="true"
            :inactive-value="false"
            active-text="显示"
            inactive-text="隐藏"
          />
          <div class="form-item-tip">开启后Agent将在任务执行时显示游戏窗口</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="assignDialogVisible"
      title="分配任务"
      width="500px"
    >
      <el-form label-width="100px">
        <el-form-item label="任务">
          <span>{{ currentTask?.name }}</span>
        </el-form-item>
        <el-form-item label="选择Agent" required>
          <el-select
            v-model="selectedAgentId"
            placeholder="请选择在线Agent"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="agent in onlineAgents"
              :key="agent.agentId"
              :label="getAgentDisplayName(agent)"
              :value="agent.agentId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAssign">分配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi, agentApi, streamingApi, merchantApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import {
  getAgentDisplayName,
  getTaskStatusText,
  getTaskStatusType,
  getGameActionTypeText,
  getSessionPhaseText,
  getSessionPhaseType
} from '@/utils/constants'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const TASK_LIST_AGENT_KEY = 'taskList.defaultAgentId'

const goDetail = (row) => {
  router.push(`/tasks/${row.id}`)
}

const filterMerchantId = ref('')
const filterAgentId = ref('')
const filterStreamingAccountId = ref('')
const filterStatus = ref('')
const loading = ref(false)
const tableData = ref([])
const onlineAgents = ref([])
const agentOptions = ref([])
const streamingAccountOptions = ref([])
const merchantList = ref([])

const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const createDialogVisible = ref(false)
const assignDialogVisible = ref(false)
const currentTask = ref(null)
const selectedAgentId = ref('')

const createForm = reactive({
  name: '',
  type: '',
  priority: 0,
  paramsJson: '',
  enableWindowDisplay: true
})

const createFormRef = ref(null)

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

const formatAgentLabel = (agent) => getAgentDisplayName(agent)

const formatStreamingLabel = (account) => {
  const name = account.name || account.email || account.id
  if (authStore.isPlatformAdmin && account.merchantName) {
    return `${name} - ${account.merchantName}`
  }
  return name
}

const getMerchantScope = () => {
  // 平台管理员必须显式选择商户后才加载商户内 Agent/串流账号，避免跨商户误筛选。
  if (authStore.isPlatformAdmin) {
    return filterMerchantId.value || undefined
  }
  return authStore.merchantId
}

const handleMerchantChange = async () => {
  // 商户切换会使 Agent 和串流账号选项失效，必须先清空再重新加载。
  filterAgentId.value = ''
  filterStreamingAccountId.value = ''
  await loadFilterOptions()
  await loadOnlineAgents()
  handleSearch()
}

const handleSearch = () => {
  pagination.pageNum = 1
  loadData()
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    const merchantId = getMerchantScope()
    // 查询参数只传有意义的过滤条件，交由后端按角色和 merchantId 做最终隔离。
    if (merchantId) {
      params.merchantId = merchantId
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterAgentId.value) {
      params.targetAgentId = filterAgentId.value
    }
    if (filterStreamingAccountId.value) {
      params.streamingAccountId = filterStreamingAccountId.value
    }
    const res = await taskApi.list(params)
    if (res.code === 0 || res.code === 200) {
      tableData.value = res.data?.records || []
      pagination.total = res.data?.total || 0
    }
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const loadMerchants = async () => {
  if (!authStore.isPlatformAdmin) return
  try {
    const res = await merchantApi.listAll()
    if (res.code === 0 || res.code === 200) {
      merchantList.value = res.data || []
    }
  } catch (error) {
    console.error('Failed to load merchants:', error)
  }
}

const loadFilterOptions = async () => {
  const merchantId = getMerchantScope()
  if (authStore.isPlatformAdmin && !merchantId) {
    // 未选商户时不展示全平台 Agent/账号，避免用户误以为可以跨商户分配任务。
    agentOptions.value = []
    streamingAccountOptions.value = []
    return
  }

  const params = { pageSize: 100 }
  if (merchantId) {
    params.merchantId = merchantId
  }

  try {
    const [agentRes, streamingRes] = await Promise.all([
      agentApi.list(params),
      streamingApi.list(params)
    ])
    if (agentRes.code === 0 || agentRes.code === 200) {
      agentOptions.value = agentRes.data?.records || []
    }
    if (streamingRes.code === 0 || streamingRes.code === 200) {
      streamingAccountOptions.value = streamingRes.data?.records || []
    }
  } catch (error) {
    console.error('Failed to load filter options:', error)
  }
}

const loadOnlineAgents = async () => {
  try {
    const params = { status: 'online', pageSize: 100 }
    const merchantId = getMerchantScope()
    if (merchantId) {
      params.merchantId = merchantId
    }
    const res = await agentApi.list(params)
    if (res.code === 0 || res.code === 200) {
      onlineAgents.value = res.data?.records || []
    }
  } catch (error) {
    console.error('Failed to load online agents:', error)
  }
}

const resolveMerchantFromRoute = async () => {
  if (!authStore.isPlatformAdmin || filterMerchantId.value) {
    return
  }
  if (route.query.merchantId) {
    filterMerchantId.value = route.query.merchantId
    return
  }
  if (route.query.agentId) {
    try {
      const res = await agentApi.getById(route.query.agentId)
      if ((res.code === 0 || res.code === 200) && res.data?.merchantId) {
        filterMerchantId.value = res.data.merchantId
        return
      }
    } catch (error) {
      console.error('Failed to resolve agent merchant:', error)
    }
  }
  if (route.query.streamingAccountId) {
    try {
      const res = await streamingApi.getById(route.query.streamingAccountId)
      if ((res.code === 0 || res.code === 200) && res.data?.merchantId) {
        filterMerchantId.value = res.data.merchantId
      }
    } catch (error) {
      console.error('Failed to resolve streaming account merchant:', error)
    }
  }
}

const initFromRoute = async () => {
  // 支持从 Agent/串流账号页面跳转时带入筛选条件，减少用户手动定位任务。
  if (route.query.status) {
    filterStatus.value = route.query.status
  }
  if (route.query.streamingAccountId) {
    filterStreamingAccountId.value = route.query.streamingAccountId
  }
  if (route.query.agentId) {
    filterAgentId.value = route.query.agentId
  }
  await resolveMerchantFromRoute()
}

const applyDefaultAgentFilter = () => {
  if (filterAgentId.value) {
    return
  }
  // 从 Agent/串流页跳转时只使用路由带入的筛选，不自动套用默认 Agent。
  if (route.query.agentId || route.query.streamingAccountId) {
    return
  }
  const saved = localStorage.getItem(TASK_LIST_AGENT_KEY)
  // 记住上次使用的 Agent，便于运维反复观察同一台 Agent 的任务列表。
  if (saved && agentOptions.value.some((agent) => agent.agentId === saved)) {
    filterAgentId.value = saved
    return
  }
  const online = onlineAgents.value.find((agent) => agent.status === 'online')
  if (online) {
    filterAgentId.value = online.agentId
  } else if (agentOptions.value.length) {
    filterAgentId.value = agentOptions.value[0].agentId
  }
}

watch(filterAgentId, (value) => {
  if (value) {
    // 只保存有效选择，不在用户清空筛选时覆盖默认值。
    localStorage.setItem(TASK_LIST_AGENT_KEY, value)
  }
})

const showCreateDialog = () => {
  createForm.name = ''
  createForm.type = ''
  createForm.priority = 0
  createForm.paramsJson = ''
  createForm.enableWindowDisplay = true
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.name || !createForm.type) {
    ElMessage.warning('请填写任务名称和类型')
    return
  }

  try {
    let params = {}
    if (createForm.paramsJson) {
      try {
        // 自定义任务参数直接透传后端，前端只负责保证 JSON 格式合法。
        params = JSON.parse(createForm.paramsJson)
      } catch (e) {
        ElMessage.error('任务参数JSON格式错误')
        return
      }
    }

    const data = {
      name: createForm.name,
      type: createForm.type,
      priority: createForm.priority,
      params: params,
      enableWindowDisplay: createForm.enableWindowDisplay
    }

    const res = await taskApi.create(data)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务创建成功')
      createDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

const showAssignDialog = async (task) => {
  currentTask.value = task
  selectedAgentId.value = ''
  await loadOnlineAgents()
  assignDialogVisible.value = true
}

const handleAssign = async () => {
  if (!selectedAgentId.value) {
    ElMessage.warning('请选择Agent')
    return
  }

  try {
    const res = await taskApi.assign(currentTask.value.id, selectedAgentId.value)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务分配成功')
      assignDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '分配失败')
    }
  } catch (error) {
    ElMessage.error('分配失败')
  }
}

const handleRetry = async (task) => {
  try {
    const res = await taskApi.retry(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务重试成功')
      loadData()
    } else {
      ElMessage.error(res.message || '重试失败')
    }
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const handleCancel = async (task) => {
  try {
    // 运行中任务走 terminate（TaskControl 控制面）；pending 仍可用 cancel 语义。
    const res = task.status === 'pending'
      ? await taskApi.cancel(task.id)
      : await taskApi.terminate(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务已取消')
      loadData()
    } else {
      ElMessage.error(res.message || '取消失败')
    }
  } catch (error) {
    ElMessage.error('取消失败')
  }
}

const handleShowWindow = async (task) => {
  try {
    // 仅下发显示窗口控制，不改变任务执行阶段或自动化状态。
    const res = await taskApi.showWindow(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('窗口显示命令已发送')
    } else {
      ElMessage.error(res.message || '显示窗口失败')
    }
  } catch (error) {
    ElMessage.error('显示窗口失败')
  }
}

const handleDelete = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await taskApi.delete(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('删除成功')
      loadData()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await loadMerchants()
  await initFromRoute()
  await loadFilterOptions()
  await loadOnlineAgents()
  applyDefaultAgentFilter()
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

.header-right {
  display: flex;
  gap: 12px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
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

.text-muted {
  color: #6b7280;
  font-size: 12px;
}

.text-danger {
  color: #f56c6c;
}

.agent-id-text {
  cursor: pointer;
  color: #409eff;
}

.priority-0 { color: #6b7280; }
.priority-1 { color: #22c55e; }
.priority-2 { color: #eab308; }
.priority-3 { color: #f97316; }
.priority-4 { color: #ef4444; }

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

.data-table {
  width: 100%;
}

/* 固定列hover不变透明 */
.data-table >>> .el-table__fixed-right:hover,
.data-table >>> .el-table__fixed:hover {
  background-color: #0f0f1a !important;
}

.data-table >>> .el-table__fixed-right .el-table__row:hover td,
.data-table >>> .el-table__fixed .el-table__row:hover td {
  background-color: #0f0f1a !important;
}

.data-table >>> .el-table__body-wrapper .el-table__row:hover td.el-table__cell {
  background-color: #1a1a2e !important;
}

.form-item-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
