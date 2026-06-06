<template>
  <el-dialog
    v-model="dialogVisible"
    title="Agent 任务监控"
    width="1200px"
    :close-on-click-modal="false"
  >
    <div v-if="agent" class="agent-info">
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="Agent ID">{{ agent.agentId }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ agent.merchantName || agent.merchantId }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getAgentStatusType(agent.status)" size="small">
            {{ getAgentStatusText(agent.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="主机地址">{{ agent.host }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ agent.version }}</el-descriptions-item>
        <el-descriptions-item label="最后心跳">{{ formatDate(agent.lastHeartbeat) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="运行中的任务" name="running">
        <el-table :data="runningTasks" v-loading="loading" max-height="400">
          <el-table-column prop="id" label="任务ID" width="180" show-overflow-tooltip />
          <el-table-column prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="90" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ getTaskTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusType(row.status)" size="small">
                {{ getTaskStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="currentStep" label="当前步骤" width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <span :class="'step-' + row.currentStep">{{ row.currentStep || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="进度" width="120">
            <template #default="{ row }">
              <el-progress
                :percentage="getTaskProgressPercent(row)"
                :stroke-width="8"
                :color="getProgressColor(getTaskProgressPercent(row))"
              />
            </template>
          </el-table-column>
          <el-table-column prop="message" label="当前状态" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="task-message">{{ row.message || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="errorMessage" label="错误信息" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.errorMessage" class="error-message">{{ row.errorMessage }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'running'"
                size="small"
                @click="handlePause(row)"
              >暂停</el-button>
              <el-button
                v-if="row.status === 'paused'"
                size="small"
                type="success"
                @click="handleResume(row)"
              >恢复</el-button>
              <el-button
                v-if="row.status !== 'completed' && row.status !== 'failed' && row.status !== 'cancelled'"
                size="small"
                type="danger"
                @click="handleStop(row)"
              >停止</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && runningTasks.length === 0" class="empty-tip">
          暂无运行中的任务
        </div>
      </el-tab-pane>

      <el-tab-pane label="所有任务" name="all">
        <el-table :data="allTasks" v-loading="loading" max-height="400">
          <el-table-column prop="id" label="任务ID" width="200" show-overflow-tooltip />
          <el-table-column prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="type" label="类型" width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ getTaskTypeText(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusType(row.status)" size="small">
                {{ getTaskStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="result" label="结果" min-width="150" show-overflow-tooltip />
          <el-table-column prop="createdTime" label="创建时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.createdTime) }}
            </template>
          </el-table-column>
          <el-table-column prop="completedTime" label="完成时间" width="160" show-overflow-tooltip>
            <template #default="{ row }">
              {{ formatDate(row.completedTime) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'failed'"
                size="small"
                type="warning"
                @click="handleRetry(row)"
              >重试</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && allTasks.length === 0" class="empty-tip">
          暂无任务记录
        </div>
      </el-tab-pane>

      <el-tab-pane label="子任务（游戏账号）" name="subtasks">
        <div v-if="selectedTask" class="subtask-container">
          <el-table :data="gameAccountStatuses" v-loading="subtaskLoading" max-height="400">
            <el-table-column prop="gameAccountName" label="游戏账号" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.gameAccountName || row.gameAccountId }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getSubtaskStatusType(row.status)" size="small">
                  {{ getSubtaskStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="completedCount" label="完成场次" width="110" align="center" show-overflow-tooltip>
              <template #default="{ row }">
                <span>{{ row.completedCount || 0 }} / {{ row.totalMatches || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="failedCount" label="失败场次" width="100" align="center">
              <template #default="{ row }">
                <span :class="{ 'failed-count': row.failedCount > 0 }">{{ row.failedCount || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="lastMatchTime" label="最后比赛时间" width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.lastMatchTime) }}
              </template>
            </el-table-column>
            <el-table-column prop="startedTime" label="开始时间" width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.startedTime) }}
              </template>
            </el-table-column>
            <el-table-column prop="completedTime" label="完成时间" width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ formatDate(row.completedTime) }}
              </template>
            </el-table-column>
            <el-table-column prop="errorMessage" label="错误信息" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.errorMessage" class="error-message">{{ row.errorMessage }}</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="!subtaskLoading && gameAccountStatuses.length === 0" class="empty-tip">
            暂无子任务数据
          </div>
        </div>
        <div v-else class="empty-tip">
          请先选择一个任务查看子任务
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button type="primary" @click="handleRefresh" :loading="loading">
        刷新
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { taskApi, automationApi } from '@/api'
import { getAgentStatusText, getAgentStatusType, getTaskStatusText, getTaskStatusType, getTaskTypeText } from '@/utils/constants'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  agent: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:visible'])

const dialogVisible = ref(false)
const activeTab = ref('running')
const loading = ref(false)
const subtaskLoading = ref(false)
const runningTasks = ref([])
const allTasks = ref([])
const selectedTask = ref(null)
const gameAccountStatuses = ref([])
let wsConnection = null

watch(() => props.visible, (val) => {
  dialogVisible.value = val
  if (val && props.agent) {
    activeTab.value = 'running'
    loadTasks()
    connectWebSocket()
  } else {
    disconnectWebSocket()
  }
})

watch(dialogVisible, (val) => {
  emit('update:visible', val)
})

watch(runningTasks, (tasks) => {
  if (tasks.length > 0 && !selectedTask.value) {
    selectedTask.value = tasks[0]
  } else if (tasks.length > 0 && selectedTask.value) {
    const updated = tasks.find(t => t.id === selectedTask.value.id)
    if (updated) {
      selectedTask.value = updated
    }
  }
}, { deep: true })

watch(selectedTask, (task) => {
  if (task && activeTab.value === 'subtasks') {
    loadGameAccountStatuses()
  }
})

watch(activeTab, (tab) => {
  if (tab === 'subtasks' && selectedTask.value) {
    loadGameAccountStatuses()
  }
})

const loadTasks = async () => {
  if (!props.agent?.agentId) return
  loading.value = true
  try {
    const res = await taskApi.list({ agentId: props.agent.agentId, pageSize: 100 })
    if (res.code === 0 || res.code === 200) {
      const tasks = res.data?.records || []
      runningTasks.value = tasks.filter((t) => t.status === 'running' || t.status === 'paused' || t.status === 'pending')
      allTasks.value = tasks
    }
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const handleRefresh = () => {
  loadTasks()
  if (selectedTask.value && activeTab.value === 'subtasks') {
    loadGameAccountStatuses()
  }
}

const loadGameAccountStatuses = async () => {
  if (!selectedTask.value?.id) return
  subtaskLoading.value = true
  try {
    const res = await taskApi.getGameAccountStatus(selectedTask.value.id)
    if (res.code === 0 || res.code === 200) {
      gameAccountStatuses.value = res.data || []
    }
  } catch (error) {
    console.error('Failed to load game account statuses:', error)
  } finally {
    subtaskLoading.value = false
  }
}

const STEP_PROGRESS = {
  STEP1: 25,
  STEP2: 50,
  STEP3: 75,
  STEP4: 100,
  COMPLETED: 100
}

const getTaskProgressPercent = (row) => {
  if (!row) return 0
  if (row.status === 'completed') return 100
  if (row.status === 'failed' || row.status === 'cancelled') return 0
  if (row.currentStep && STEP_PROGRESS[row.currentStep] != null) {
    return STEP_PROGRESS[row.currentStep]
  }
  if (row.status === 'running') return 15
  if (row.status === 'pending') return 5
  return 0
}

const getSubtaskStatusText = (status) => {
  const statusMap = {
    'pending': '待执行',
    'running': '执行中',
    'completed': '已完成',
    'failed': '失败',
    'skipped': '跳过'
  }
  return statusMap[status] || status
}

const getSubtaskStatusType = (status) => {
  const typeMap = {
    'pending': 'info',
    'running': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'skipped': 'info'
  }
  return typeMap[status] || 'info'
}

const handlePause = async (task) => {
  try {
    await taskApi.pause(task.id)
    ElMessage.success('任务已暂停')
    loadTasks()
  } catch (error) {
    console.error('Failed to pause task:', error)
    ElMessage.error('暂停任务失败')
  }
}

const handleResume = async (task) => {
  try {
    await taskApi.resume(task.id)
    ElMessage.success('任务已恢复')
    loadTasks()
  } catch (error) {
    console.error('Failed to resume task:', error)
    ElMessage.error('恢复任务失败')
  }
}

const handleStop = async (task) => {
  try {
    await ElMessageBox.confirm('确定要停止该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await taskApi.stop(task.id)
    ElMessage.success('任务已停止')
    loadTasks()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to stop task:', error)
      ElMessage.error('停止任务失败')
    }
  }
}

const handleRetry = async (task) => {
  try {
    await taskApi.retry(task.id)
    ElMessage.success('任务已重新提交')
    loadTasks()
  } catch (error) {
    console.error('Failed to retry task:', error)
    ElMessage.error('重试任务失败')
  }
}

const connectWebSocket = () => {
  if (wsConnection) return

  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8060/ws/admin'
  wsConnection = new WebSocket(wsUrl)

  wsConnection.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'task_progress') {
        handleTaskProgress(data.data)
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e)
    }
  }

  wsConnection.onclose = () => {
    wsConnection = null
  }
}

const disconnectWebSocket = () => {
  if (wsConnection) {
    wsConnection.close()
    wsConnection = null
  }
}

const handleTaskProgress = (data) => {
  if (!data || !data.agentId || data.agentId !== props.agent?.agentId) return

  const taskId = data.taskId
  const task = runningTasks.value.find(t => t.id === taskId)
  if (task) {
    task.currentStep = data.step
    task.message = data.message
    task.status = data.status
    task.progress = calculateProgress(data.step, data.extraData)
    task.currentGameAccount = data.extraData?.gameAccountName || null

    if (selectedTask.value?.id === taskId) {
      selectedTask.value = { ...task }
    }
  }
}

const calculateProgress = (step, extraData) => {
  const stepMap = {
    'STEP1': 10,
    'STEP2': 30,
    'STEP3': 50,
    'STEP4': 70
  }
  let progress = stepMap[step] || 0

  if (step === 'STEP4' && extraData) {
    const { currentMatch, targetMatches } = extraData
    if (currentMatch && targetMatches) {
      const matchProgress = (currentMatch / targetMatches) * 30
      progress = 70 + matchProgress
    }
  }

  return Math.min(progress, 100)
}

const getProgressColor = (percentage) => {
  if (percentage < 30) return '#909399'
  if (percentage < 70) return '#e6a23c'
  return '#67c23a'
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

onUnmounted(() => {
  disconnectWebSocket()
})
</script>

<style scoped>
.agent-info {
  margin-bottom: 20px;
}

.task-tabs {
  margin-top: 16px;
}

.empty-tip {
  text-align: center;
  color: #6b7280;
  padding: 40px 0;
}

.task-detail {
  padding: 10px 0;
}

.game-account-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.task-message {
  color: #67c23a;
}

.error-message {
  color: #f56c6c;
}

.step-STEP1 { color: #409eff; }
.step-STEP2 { color: #e6a23c; }
.step-STEP3 { color: #f56c6c; }
.step-STEP4 { color: #67c23a; }

.failed-count {
  color: #f56c6c;
  font-weight: 600;
}

.subtask-container {
  padding: 10px 0;
}

:deep(.el-dialog) {
  background: rgb(18, 18, 26);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.el-dialog__title) {
  color: #ffffff;
}

:deep(.el-dialog__body) {
  padding: 20px;
}

:deep(.el-tabs__nav-wrap::after) {
  background: rgba(255, 255, 255, 0.06);
}

:deep(.el-tabs__item) {
  color: #8a8a8a;
}

:deep(.el-tabs__item.is-active) {
  color: #6366f1;
}

:deep(.el-tabs__active-bar) {
  background: #6366f1;
}
</style>
