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

const canStartAutomation = computed(
  () =>
    !isTerminal.value &&
    (props.gameActionPending ||
      props.sessionPhase === 'ready' ||
      props.sessionPhase === 'automation_failed')
)
const isPaused = computed(
  () => !isTerminal.value && (props.sessionPhase?.startsWith('paused') || props.pauseMode)
)
const isAutomating = computed(
  () => !isTerminal.value && props.sessionPhase === 'automating'
)

const canCancel = computed(
  () => props.taskStatus === 'pending' || props.taskStatus === 'running'
)

const canTerminate = computed(() => !isTerminal.value)

const canShowWindow = computed(() => {
  if (isTerminal.value) return false
  const phase = (props.sessionPhase || '').toLowerCase()
  return phase && phase !== 'opening' && phase !== 'closed' && phase !== 'failed'
})

const canReconnect = computed(() => {
  if (isTerminal.value) return false
  const phase = (props.sessionPhase || '').toLowerCase()
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
