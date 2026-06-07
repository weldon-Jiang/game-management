<template>
  <el-dialog v-model="visible" title="启动串流" width="600px" @close="reset">
    <el-steps :active="step" finish-status="success" align-center class="wizard-steps">
      <el-step title="账号" />
      <el-step title="Agent" />
      <el-step title="就绪" />
      <el-step title="自动化" />
    </el-steps>

    <div v-if="step === 0" class="step-body">
      <p class="mb-8">串流账号: <strong>{{ account?.email }}</strong></p>
      <p class="label">选择游戏账号（可多选）</p>
      <el-checkbox-group v-model="form.gameAccountIds" class="ga-list">
        <el-checkbox
          v-for="ga in gameAccounts"
          :key="ga.id"
          :label="ga.id"
          :value="ga.id"
          :disabled="isGameAccountOccupied(ga)"
        >
          {{ ga.gameName || ga.email }}
          <span v-if="ga.positionIndex != null && ga.positionIndex >= 0" class="meta">
            位置 {{ ga.positionIndex }}
          </span>
          <span v-if="isGameAccountOccupied(ga)" class="meta warning">
            已被 {{ ga.agentName || ga.agentId || '其他任务' }} 占用
          </span>
        </el-checkbox>
      </el-checkbox-group>
      <p v-if="!gameAccounts.length" class="text-muted">该串流账号下暂无绑定游戏账号</p>
    </div>

    <div v-else-if="step === 1" class="step-body">
      <el-select v-model="form.agentId" placeholder="选择 Agent" filterable style="width: 100%">
        <el-option v-for="a in agents" :key="a.agentId" :label="getAgentDisplayName(a)" :value="a.agentId" />
      </el-select>
      <p v-if="!agents.length" class="text-muted">当前没有在线 Agent，请先启动 Agent 服务</p>
    </div>

    <div v-else-if="step === 2" class="step-body">
      <p v-if="taskId">任务 ID: <code>{{ taskId }}</code></p>
      <SessionPhaseStepper :phase="sessionPhase" class="phase-stepper" />
      <p class="status-line">{{ statusMessage }}</p>
      <el-progress
        v-if="!isReady"
        :percentage="progressPercent"
        :indeterminate="progressPercent < 5"
        :stroke-width="10"
      />
      <el-alert
        v-else
        type="success"
        :closable="false"
        title="串流已就绪，可选择自动化类型或进入任务详情"
        show-icon
      />
    </div>

    <div v-else class="step-body">
      <el-select v-model="form.gameActionType" placeholder="选择自动化类型" style="width: 100%">
        <el-option label="SQB" value="squad_battle" />
        <el-option label="转会" value="auction_transfer" />
        <el-option label="转会+SQB" value="transfer_sqb_combo" />
        <el-option label="DR" value="divisions_rivals" />
      </el-select>
    </div>

    <template #footer>
      <el-button v-if="step > 0 && step < 2" @click="step--">上一步</el-button>
      <el-button v-if="step === 0" type="primary" @click="nextFromAccount">下一步</el-button>
      <el-button v-else-if="step === 1" type="primary" :loading="submitting" @click="startStreaming">
        启动串流
      </el-button>
      <el-button v-else-if="step === 2 && isReady" type="primary" @click="step = 3">选择自动化</el-button>
      <el-button v-else-if="step === 2" @click="goDetail">进入任务详情</el-button>
      <el-button v-else type="primary" :loading="submitting" @click="startAutomation">开始自动化</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch, computed, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { automationApi } from '@/api/automation'
import { taskApi } from '@/api/task'
import SessionPhaseStepper from '@/components/task/SessionPhaseStepper.vue'
import {
  getAgentDisplayName,
  getSessionPhaseHint,
  getTaskEventMessageText
} from '@/utils/constants'

const props = defineProps({
  modelValue: Boolean,
  account: Object,
  agents: { type: Array, default: () => [] },
  gameAccounts: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue', 'started'])

const router = useRouter()
const visible = ref(false)
const step = ref(0)
const submitting = ref(false)
const taskId = ref('')
const sessionPhase = ref('opening')
const statusMessage = ref('等待启动...')
let pollTimer = null

const form = reactive({
  agentId: '',
  gameActionType: 'squad_battle',
  gameAccountIds: []
})

// Step1-3 是串流准备阶段，进度只反映会话 phase，不代表 Step4 自动化进度。
const phaseProgress = {
  opening: 10,
  authenticating: 25,
  discovering: 45,
  streaming: 65,
  initializing_display: 80,
  initializing_input: 90,
  ready: 100
}

const progressPercent = computed(() => phaseProgress[sessionPhase.value] ?? 5)
const isReady = computed(() => sessionPhase.value === 'ready')

watch(() => props.modelValue, (v) => {
  visible.value = v
  if (v) {
    // 默认选中当前未被其他任务占用的游戏账号，避免用户误启动冲突账号。
    form.gameAccountIds = props.gameAccounts
      .filter((ga) => !isGameAccountOccupied(ga))
      .map((ga) => ga.id)
    const boundAgent = props.agents.find((a) => a.agentId === props.account?.agentId)
    form.agentId = boundAgent?.agentId || (props.agents.length === 1 ? props.agents[0].agentId : '')
  }
})
watch(visible, (v) => emit('update:modelValue', v))

const stopPoll = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const pollTaskDetail = async () => {
  if (!taskId.value) return
  try {
    // 启动串流阶段使用轮询兜底，直到后端会话进入 ready 后再让用户选择自动化。
    const res = await taskApi.getDetail(taskId.value)
    const task = res.data?.task
    const session = res.data?.session
    sessionPhase.value = task?.sessionPhase || session?.phase || 'opening'
    statusMessage.value =
      getSessionPhaseHint(sessionPhase.value, session?.errorMessage || task?.errorMessage || '') ||
      getTaskEventMessageText(session?.errorMessage || task?.sessionPhase || '串流建立中...')
    if (isReady.value) {
      stopPoll()
    }
  } catch {
    /* ignore transient errors */
  }
}

const startPoll = () => {
  stopPoll()
  pollTaskDetail()
  pollTimer = setInterval(pollTaskDetail, 3000)
}

const reset = () => {
  stopPoll()
  step.value = 0
  taskId.value = ''
  sessionPhase.value = 'opening'
  statusMessage.value = '等待启动...'
  form.agentId = ''
  form.gameAccountIds = []
}

onUnmounted(stopPoll)

const nextFromAccount = () => {
  if (!form.gameAccountIds.length) {
    ElMessage.warning('请至少选择一个未被占用的游戏账号')
    return
  }
  step.value++
}

const isGameAccountOccupied = (gameAccount) =>
  gameAccount?.status === 'busy' || Boolean(gameAccount?.agentId)

const startStreaming = async () => {
  if (!form.agentId) {
    ElMessage.warning('请选择 Agent')
    return
  }
  submitting.value = true
  try {
    // 第一阶段只建立长寿命串流任务；Step4 自动化类型在 ready 后单独下发。
    const res = await automationApi.startStreaming(props.account.id, {
      agentId: form.agentId,
      gameAccountIds: form.gameAccountIds
    })
    taskId.value = res.data?.taskId
    step.value = 2
    sessionPhase.value = 'opening'
    statusMessage.value = '正在认证与发现主机...'
    startPoll()
    emit('started', res.data)
    ElMessage.success(res.data?.reused ? '已复用任务并启动串流' : '串流已启动')
  } catch (error) {
    const conflict = error?.data
    if (conflict?.conflicts?.length) {
      // 多账号任一被占用都不能启动，后端返回冲突列表供前端精确提示。
      const names = conflict.conflicts
        .map((item) => item.gameAccountName || item.gameAccountId)
        .join('、')
      ElMessage.error(`以下游戏账号已被其他任务占用：${names}`)
    } else if (conflict?.taskId) {
      try {
        // 同一串流账号已有长寿命任务时，引导用户进入现有任务而不是重复启动。
        await ElMessageBox.confirm(
          error.message || '该串流账号正在运行任务',
          '无法启动串流',
          {
            confirmButtonText: '查看任务',
            cancelButtonText: '知道了',
            type: 'warning'
          }
        )
        router.push(`/tasks/${conflict.taskId}`)
        visible.value = false
      } catch {
        // user dismissed
      }
    } else {
      ElMessage.error(error?.message || '启动串流失败')
    }
  } finally {
    submitting.value = false
  }
}

const goDetail = () => {
  if (taskId.value) router.push(`/tasks/${taskId.value}`)
  visible.value = false
}

const startAutomation = async () => {
  submitting.value = true
  try {
    // 第二阶段只下发 gameActionType，Agent 在 Step4 确认账号登录后才真正应用该模式。
    await taskApi.startAutomation(taskId.value, { gameActionType: form.gameActionType })
    goDetail()
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.wizard-steps { margin-bottom: 20px; }
.step-body { min-height: 100px; padding: 8px 0; }
.text-muted { color: var(--el-text-color-secondary); font-size: 13px; }
.label { font-size: 13px; margin-bottom: 8px; color: var(--el-text-color-regular); }
.ga-list { display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; }
.meta { color: var(--el-text-color-secondary); font-size: 12px; margin-left: 6px; }
.meta.warning { color: var(--el-color-warning); }
.phase-stepper { margin: 12px 0; }
.status-line { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 8px; }
.mb-8 { margin-bottom: 8px; }
</style>
