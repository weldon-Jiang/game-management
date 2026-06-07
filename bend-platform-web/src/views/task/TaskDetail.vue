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
              <span class="value">{{ displayGameActionType ? getGameActionTypeText(displayGameActionType) : '-' }}</span>
            </div>
            <div class="overview-item">
              <span class="label">会话阶段</span>
              <el-tag
                v-if="displaySessionPhase"
                size="small"
                :type="getSessionPhaseType(displaySessionPhase)"
              >
                {{ getSessionPhaseText(displaySessionPhase) }}
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
            <span v-if="displaySession?.errorMessage" class="alert-item error">
              会话错误：{{ getTaskEventMessageText(displaySession.errorMessage) }}
            </span>
          </div>
        </div>

        <div v-if="sessions.length" class="session-switcher">
          <span class="label">查看会话轮次：</span>
          <el-select
            v-model="selectedSessionId"
            size="small"
            style="min-width: 280px"
          >
            <el-option
              v-for="(s, idx) in sessions"
              :key="s.id"
              :label="formatSessionLabel(s, sessions.length - idx)"
              :value="s.id"
            />
          </el-select>
          <el-tag v-if="!isCurrentSession" type="info" size="small" class="history-tag">
            历史会话（只读）
          </el-tag>
        </div>

        <div class="phase-control-row">
          <SessionPhaseStepper
            class="phase-stepper"
            :phase="displaySessionPhase || 'opening'"
          />
          <TaskControlBar
            v-if="isCurrentSession"
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
          v-if="isCurrentSession && task.windowVisible === false"
          type="info"
          :closable="false"
          title="窗口已隐藏，任务仍在后台运行"
          class="window-hint"
        />

        <el-alert
          v-if="isCurrentSession && (task.sessionPhase || session?.phase) === 'automation_failed'"
          type="warning"
          :closable="false"
          title="自动化未完成，串流窗口仍保持连接，可重新选择模式后重试"
          class="window-hint"
        />

        <section class="account-section">
          <h3>游戏账号</h3>
          <GameAccountRunTable
            :rows="gameAccountStatuses"
            :show-match-progress="showMatchProgress"
            :readonly="!isCurrentSession"
            @skip="handleSkip"
          />
        </section>
      </div>

      <aside class="detail-aside">
        <TaskEventTimeline :events="events" embedded />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
const sessions = ref([])
const selectedSessionId = ref('')

const { detail, events, loading, startMonitor } = useTaskMonitor(taskId, selectedSessionId)

const task = computed(() => detail.value?.task)
const session = computed(() => detail.value?.session)
const gameAccountStatuses = computed(() => detail.value?.gameAccountStatuses || [])
const lastProgressMessage = computed(() => detail.value?.lastProgressMessage)

const currentSessionId = computed(() => task.value?.sessionId || session.value?.id || '')

const isCurrentSession = computed(() => {
  if (!selectedSessionId.value) return true
  return selectedSessionId.value === currentSessionId.value
})

const displaySession = computed(() => {
  if (isCurrentSession.value) return session.value
  return sessions.value.find(s => s.id === selectedSessionId.value) || null
})

const displaySessionPhase = computed(() => {
  if (isCurrentSession.value) return task.value?.sessionPhase || session.value?.phase || ''
  return displaySession.value?.phase || ''
})

const displayGameActionType = computed(() => {
  if (isCurrentSession.value) return task.value?.gameActionType
  return displaySession.value?.gameActionType || ''
})

const hasAlerts = computed(
  () =>
    lastProgressMessage.value ||
    task.value?.errorMessage ||
    displaySession.value?.errorMessage
)

// 会话列表兜底刷新间隔（detail 轮询的约 3 倍，降低 /sessions 请求量）
const SESSIONS_REFRESH_INTERVAL = 12000
let sessionsTimer = null

/**
 * 拉取任务的全部串流会话轮次。
 *
 * <p>容错要点：① 失败时**不清空**已有 sessions，避免成功结果被后续瞬时失败覆盖导致切换器消失；
 * ② 失败后短延迟自动重试一次，降低首屏请求抖动（含 request.js 同 URL 去重取消）造成的永久空列表；
 * ③ 仅在 sessions 为空时回退重试，已有数据则交给周期兜底刷新自愈。</p>
 *
 * @param retry 是否允许失败后重试一次（默认 true）
 */
const loadSessions = async (retry = true) => {
  if (!taskId.value) return
  try {
    const res = await taskApi.listSessions(taskId.value)
    sessions.value = res.data || []
    if (!selectedSessionId.value && currentSessionId.value) {
      selectedSessionId.value = currentSessionId.value
    } else if (!selectedSessionId.value && sessions.value.length) {
      selectedSessionId.value = sessions.value[0].id
    }
  } catch (e) {
    console.warn('Failed to load sessions:', e)
    // 保留已有 sessions，不覆盖为空；仅在列表仍为空时重试一次
    if (retry && !sessions.value.length) {
      setTimeout(() => loadSessions(false), 800)
    }
  }
}

watch(currentSessionId, (id) => {
  if (id && !selectedSessionId.value) {
    selectedSessionId.value = id
  }
  loadSessions()
})

const formatSessionLabel = (s, ordinal) => {
  const start = s.startedTime ? String(s.startedTime).replace('T', ' ').slice(0, 16) : '--'
  const phase = s.phase ? getSessionPhaseText(s.phase) : '-'
  const isCurrent = s.id === currentSessionId.value
  const marker = isCurrent ? '当前' : `#${ordinal}`
  return `${marker} · ${start} · ${phase}`
}

const accountProgress = computed(() => {
  const rows = gameAccountStatuses.value
  if (!rows.length) {
    return task.value?.result && task.value.result.includes('/') ? task.value.result : '-'
  }
  const completed = rows.filter(r => r.status === 'completed' || r.status === 'skipped').length
  return `${completed}/${rows.length}`
})

const showMatchProgress = computed(() => {
  const type = task.value?.gameActionType
  return !type || type === 'squad_battle' || type === 'transfer_sqb_combo'
})

const formatTime = (t) => {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}

onMounted(async () => {
  startMonitor(4000)
  await loadSessions()
  // 周期兜底刷新：即使首屏请求被取消/失败，下一拍也能自愈，保证会话切换器最终可见
  sessionsTimer = setInterval(() => loadSessions(false), SESSIONS_REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (sessionsTimer) {
    clearInterval(sessionsTimer)
    sessionsTimer = null
  }
})

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

.session-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.session-switcher .label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.session-switcher .history-tag {
  margin-left: 4px;
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
