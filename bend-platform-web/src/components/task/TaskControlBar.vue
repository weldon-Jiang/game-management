<template>
  <div class="task-control-bar">
    <el-button
      v-if="canShowWindow"
      @click="$emit('window', 'show')"
    >
      显示窗口
    </el-button>

    <span v-if="gameActionType" class="mode-label">自动化: {{ gameActionLabel }}</span>

    <template v-if="canStartAutomation">
      <el-select v-model="selectedMode" placeholder="选择模式" style="width: 140px">
        <el-option label="SQB" value="squad_battle" />
        <el-option label="转会" value="auction_transfer" />
        <el-option label="转会+SQB" value="transfer_sqb_combo" />
        <el-option label="DR" value="divisions_rivals" />
      </el-select>
      <el-button type="primary" @click="$emit('start-automation', selectedMode)">开始自动化</el-button>
    </template>

    <template v-else-if="isPaused">
      <el-button type="primary" @click="$emit('resume')">继续</el-button>
    </template>
    <template v-else-if="isAutomating">
      <el-dropdown @command="(cmd) => $emit('pause', cmd)">
        <el-button type="warning">立即暂停</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="immediate">立即暂停</el-dropdown-item>
            <el-dropdown-item command="after_match">完成本场后暂停</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <el-button
      v-if="canReconnect"
      type="warning"
      plain
      @click="$emit('reconnect')"
    >
      重连串流
    </el-button>

    <el-button
      v-if="canCancel"
      type="warning"
      plain
      @click="$emit('cancel')"
    >
      取消任务
    </el-button>

    <el-button
      v-if="canTerminate"
      type="danger"
      @click="$emit('terminate')"
    >
      终止任务
    </el-button>
  </div>
</template>

<script setup>
/**
 * 任务控制条：pause/resume/cancel（仅 pending）/terminate（running+）、窗口、重连、启动 Step4。
 * 按钮可见性由 taskStatus + sessionPhase 联合判定（见下方 computed 注释）。
 */
import { computed, ref } from 'vue'
import { isTaskTerminal, getGameActionTypeText } from '@/utils/constants'

const props = defineProps({
  taskStatus: { type: String, default: '' },
  sessionPhase: { type: String, default: '' },
  gameActionType: { type: String, default: '' },
  gameActionPending: { type: Boolean, default: false },
  pauseMode: { type: String, default: '' }
})

defineEmits(['window', 'pause', 'resume', 'cancel', 'terminate', 'start-automation', 'reconnect'])

const selectedMode = ref('squad_battle')

const isTerminal = computed(() => isTaskTerminal(props.taskStatus))

// 与后端 startAutomation 一致：仅 ready / automation_failed 允许启动 Step4。
const canStartAutomation = computed(
  () =>
    !isTerminal.value &&
    (props.sessionPhase === 'ready' || props.sessionPhase === 'automation_failed')
)
const isPaused = computed(
  () => !isTerminal.value && (props.sessionPhase?.startsWith('paused') || props.pauseMode)
)
const isAutomating = computed(
  () => !isTerminal.value && props.sessionPhase === 'automating'
)

// pending 仅「取消」；running 及后续串流阶段仅「终止」，避免两按钮同效造成误解。
const canCancel = computed(() => props.taskStatus === 'pending')

const canTerminate = computed(
  () => !isTerminal.value && props.taskStatus !== 'pending'
)

const canShowWindow = computed(() => {
  if (isTerminal.value) return false
  const phase = (props.sessionPhase || '').toLowerCase()
  // opening/closed/failed 没有可接管窗口，其余串流阶段允许用户手动显示。
  return phase && phase !== 'opening' && phase !== 'closed' && phase !== 'failed'
})

const canReconnect = computed(() => {
  if (isTerminal.value) return false
  const phase = (props.sessionPhase || '').toLowerCase()
  // 只在已有串流或显示初始化上下文时允许重连，避免对未建立会话的任务下发无效控制。
  return ['streaming', 'ready', 'automating', 'automation_failed', 'initializing_display', 'initializing_input'].some(
    (p) => phase.includes(p)
  ) || phase.startsWith('paused')
})

const gameActionLabel = computed(() => getGameActionTypeText(props.gameActionType))
</script>

<style scoped>
.task-control-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
}
.mode-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
