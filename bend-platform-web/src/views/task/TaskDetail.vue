<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <div class="header-left">
        <el-button link @click="$router.push('/tasks')">← 返回列表</el-button>
        <h2>任务详情</h2>
        <el-tag v-if="task">{{ task.name }}</el-tag>
      </div>
    </div>

    <div v-if="task" class="detail-layout">
      <div class="detail-main">
        <div class="overview-bar">
          <div class="overview-grid">
            <div class="overview-item">
              <span class="label">任务状态</span>
              <el-tag :type="getTaskStatusType(task.status)" size="small">
                {{ getTaskStatusText(task.status) }}
              </el-tag>
            </div>
            <div class="overview-item">
              <span class="label">串流账号</span>
              <span class="value">{{ task.streamingAccountName || task.streamingAccountId || '-' }}</span>
            </div>
            <div class="overview-item">
              <span class="label">执行 Agent</span>
              <span class="value">{{ task.targetAgentName || task.targetAgentId || '未分配' }}</span>
            </div>
            <div class="overview-item">
              <span class="label">游戏操作</span>
              <span class="value">{{ task.gameActionType ? getGameActionTypeText(task.gameActionType) : '-' }}</span>
            </div>
            <div class="overview-item">
              <span class="label">会话阶段</span>
              <el-tag
                v-if="task.sessionPhase || session?.phase"
                size="small"
                :type="getSessionPhaseType(task.sessionPhase || session?.phase)"
              >
                {{ getSessionPhaseText(task.sessionPhase || session?.phase) }}
              </el-tag>
              <span v-else class="value">-</span>
            </div>
            <div class="overview-item">
              <span class="label">账号进度</span>
              <span class="value">{{ accountProgress }}</span>
            </div>
            <div class="overview-item">
              <span class="label">创建时间</span>
              <span class="value">{{ formatTime(task.createdTime) }}</span>
            </div>
          </div>
          <div v-if="hasAlerts" class="alert-strip">
            <span v-if="lastProgressMessage" class="alert-item info">
              最新进度：{{ getTaskEventMessageText(lastProgressMessage) }}
            </span>
            <span v-if="task.errorMessage" class="alert-item error">
              任务错误：{{ task.errorMessage }}
            </span>
            <span v-if="session?.errorMessage" class="alert-item error">
              会话错误：{{ getTaskEventMessageText(session.errorMessage) }}
            </span>
          </div>
        </div>

        <div class="phase-control-row">
          <SessionPhaseStepper
            class="phase-stepper"
            :phase="task.sessionPhase || session?.phase || 'opening'"
          />
          <TaskControlBar
            class="control-bar"
            :task-status="task.status"
            :session-phase="task.sessionPhase || session?.phase"
            :game-action-type="task.gameActionType"
            :game-action-pending="task.gameActionPending"
            :pause-mode="task.pauseMode"
            @window="handleWindow"
            @pause="handlePause"
            @resume="handleResume"
            @cancel="handleCancel"
            @terminate="handleTerminate"
            @start-automation="handleStartAutomation"
            @reconnect="handleReconnect"
          />
        </div>

        <el-alert
          v-if="task.windowVisible === false"
          type="info"
          :closable="false"
          title="窗口已隐藏，任务仍在后台运行"
          class="window-hint"
        />

        <section class="account-section">
          <h3>游戏账号</h3>
          <GameAccountRunTable :rows="gameAccountStatuses" @skip="handleSkip" />
        </section>
      </div>

      <aside class="detail-aside">
        <TaskEventTimeline :events="events" embedded />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useTaskMonitor } from '@/composables/useTaskMonitor'
import { taskApi } from '@/api/task'
import {
  getTaskStatusText,
  getTaskStatusType,
  getGameActionTypeText,
  getSessionPhaseText,
  getSessionPhaseType,
  getTaskEventMessageText
} from '@/utils/constants'
import SessionPhaseStepper from '@/components/task/SessionPhaseStepper.vue'
import TaskControlBar from '@/components/task/TaskControlBar.vue'
import GameAccountRunTable from '@/components/task/GameAccountRunTable.vue'
import TaskEventTimeline from '@/components/task/TaskEventTimeline.vue'

const route = useRoute()
const taskId = computed(() => route.params.id)
const { detail, events, loading, startMonitor } = useTaskMonitor(taskId)

const task = computed(() => detail.value?.task)
const session = computed(() => detail.value?.session)
const gameAccountStatuses = computed(() => detail.value?.gameAccountStatuses || [])
const lastProgressMessage = computed(() => detail.value?.lastProgressMessage)

const hasAlerts = computed(
  () => lastProgressMessage.value || task.value?.errorMessage || session.value?.errorMessage
)

const accountProgress = computed(() => {
  const rows = gameAccountStatuses.value
  if (!rows.length) {
    return task.value?.result && task.value.result.includes('/') ? task.value.result : '-'
  }
  const completed = rows.filter(r => r.status === 'completed' || r.status === 'skipped').length
  return `${completed}/${rows.length}`
})

const formatTime = (t) => {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}

onMounted(() => startMonitor(4000))

const handleWindow = async () => {
  await taskApi.showWindow(taskId.value)
  ElMessage.success('已发送显示窗口指令')
}

const handlePause = async (mode) => {
  await taskApi.pause(taskId.value, { mode })
  ElMessage.success('已暂停')
}

const handleResume = async () => {
  await taskApi.resume(taskId.value)
  ElMessage.success('已恢复')
}

const handleCancel = async () => {
  await ElMessageBox.confirm('确定取消该任务？', '确认')
  await taskApi.cancel(taskId.value)
  ElMessage.success('已取消')
}

const handleTerminate = async () => {
  await ElMessageBox.confirm(
    '终止将停止任务并关闭串流窗口，确定继续？',
    '终止任务',
    { type: 'warning' }
  )
  await taskApi.terminate(taskId.value)
  ElMessage.success('任务已终止，窗口将关闭')
}

const handleStartAutomation = async (gameActionType) => {
  await taskApi.startAutomation(taskId.value, { gameActionType })
  ElMessage.success('自动化已启动')
}

const handleSkip = async (gameAccountId) => {
  await taskApi.skipGameAccount(taskId.value, gameAccountId)
  ElMessage.success('已跳过该账号')
}

const handleReconnect = async () => {
  await taskApi.reconnectStream(taskId.value)
  ElMessage.success('已发送重连串流指令')
}
</script>

<style scoped>
.detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
}

.detail-main {
  min-width: 0;
}

.overview-bar {
  margin-bottom: 12px;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px 16px;
}

.overview-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  min-width: 0;
}

.overview-item .label {
  color: #888;
  font-size: 12px;
  flex-shrink: 0;
}

.overview-item .value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.alert-item {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  line-height: 1.4;
}

.alert-item.info {
  background: rgba(64, 158, 255, 0.12);
  color: #a0cfff;
}

.alert-item.error {
  background: rgba(245, 108, 108, 0.12);
  color: #f89898;
}

.phase-control-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.phase-stepper :deep(.el-step__title) {
  font-size: 13px;
}

.phase-stepper :deep(.el-step__description) {
  font-size: 11px;
}

.control-bar {
  padding: 0;
}

.window-hint {
  margin-bottom: 12px;
}

.account-section h3 {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 600;
}

.detail-aside {
  min-width: 0;
}

@media (max-width: 1100px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }

  .detail-aside {
    order: -1;
  }
}
</style>
