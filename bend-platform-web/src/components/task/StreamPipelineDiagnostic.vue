<template>
  <section v-if="steps.length" class="pipeline-diagnostic content-card">
    <h3>串流管道诊断</h3>
    <p v-if="stackHint" class="pipeline-stack-hint">{{ stackHint }}</p>
    <div class="pipeline-steps">
      <div
        v-for="step in steps"
        :key="step.key"
        class="pipeline-step"
        :class="stepClass(step.value)"
      >
        <span class="step-dot" />
        <div class="step-body">
          <span class="step-label">{{ step.label }}</span>
          <span class="step-detail">{{ stepDetail(step.value) }}</span>
        </div>
      </div>
    </div>
    <p v-if="hasExtra" class="pipeline-extra">
      <span v-if="streamModeLabel">模式：{{ streamModeLabel }}</span>
      <span v-if="extra.frameCaptureMode"> · 截帧：{{ extra.frameCaptureMode }}</span>
      <span v-if="extra.decodeMode"> · 解码：{{ extra.decodeMode }}</span>
      <span v-if="extra.firstFrameSize"> · 首帧：{{ extra.firstFrameSize }}</span>
      <span v-if="extra.inputChannelState"> · 输入：{{ extra.inputChannelState }}</span>
      <span v-if="legacyLanIp"> · LAN IP：{{ legacyLanIp }}</span>
      <span v-if="extra.rtpPort"> · RTP：{{ extra.rtpPort }}</span>
    </p>
  </section>
</template>

<script setup>
/**
 * TaskDetail 管道诊断：对齐 Agent xsrp 云端 GSSV/WebRTC 上报字段；
 * 旧 LAN 任务若仍含 lanConnect/dtlsSrtp 则自动展示 legacy 步骤。
 */
import { computed } from 'vue'

const props = defineProps({
  diagnostic: {
    type: Object,
    default: null
  }
})

/** xblive/xsrp 云端串流（Route B） */
const CLOUD_STEP_DEFS = [
  { key: 'auth', label: '认证 (xblive)' },
  { key: 'discovery', label: 'GSSV 主机发现' },
  { key: 'gssvPlay', label: 'Play 会话' },
  { key: 'webrtc', label: 'WebRTC 握手' },
  { key: 'firstFrame', label: '首帧' },
  { key: 'inputDc', label: '输入通道' },
  { key: 'display', label: 'SDL 显示' }
]

/** 历史 LAN SmartGlass 任务 */
const LEGACY_STEP_DEFS = [
  { key: 'auth', label: '认证' },
  { key: 'discovery', label: '主机发现 (GSSV∩LAN)' },
  { key: 'lanConnect', label: 'LAN 握手' },
  { key: 'dtlsSrtp', label: 'DTLS-SRTP' },
  { key: 'firstFrame', label: '首帧' },
  { key: 'inputDc', label: '输入通道' }
]

const extra = computed(() => props.diagnostic || {})

const isLegacyLan = computed(() => {
  const d = props.diagnostic
  if (!d) return false
  return d.lanConnect != null || d.dtlsSrtp != null
})

const stepDefs = computed(() => (isLegacyLan.value ? LEGACY_STEP_DEFS : CLOUD_STEP_DEFS))

const steps = computed(() => {
  if (!props.diagnostic) return []
  return stepDefs.value.filter((s) => props.diagnostic[s.key] != null)
})

const stackHint = computed(() => {
  const stack = extra.value.streamingStack
  if (stack === 'xsrp') return '串流栈：xblive / GSSV 云端 Remote Play'
  if (isLegacyLan.value) return '串流栈：LAN SmartGlass（历史任务）'
  return ''
})

const streamModeLabel = computed(() => {
  const mode = String(extra.value.streamMode || '').toLowerCase()
  if (mode.includes('cloud') || mode.includes('xsrp')) return '云端 GSSV (xsrp)'
  if (isLegacyLan.value) return '局域网 SmartGlass'
  if (extra.value.streamMode) return extra.value.streamMode
  return ''
})

const legacyLanIp = computed(() => (isLegacyLan.value ? extra.value.lanIp : null))

const hasExtra = computed(() => {
  return !!(
    streamModeLabel.value
    || extra.value.frameCaptureMode
    || extra.value.decodeMode
    || extra.value.firstFrameSize
    || extra.value.inputChannelState
    || legacyLanIp.value
    || extra.value.rtpPort
  )
})

const stepClass = (value) => {
  const v = String(value || '').toLowerCase()
  if (v === 'ok') return 'is-ok'
  if (v === 'fail' || v === 'failed') return 'is-fail'
  return 'is-pending'
}

const stepDetail = (value) => {
  const v = String(value || '').toLowerCase()
  if (v === 'ok') return '正常'
  if (v === 'fail' || v === 'failed') return '失败'
  if (v === 'pending') return '等待'
  return value
}
</script>

<style scoped>
.pipeline-diagnostic {
  margin-bottom: var(--spacing-md);
}

.pipeline-diagnostic h3 {
  margin: 0 0 var(--spacing-sm);
  font-size: var(--font-size-md);
}

.pipeline-stack-hint {
  margin: 0 0 var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.pipeline-steps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.pipeline-step {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-xs);
  min-width: 140px;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border);
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
  background: var(--color-text-muted);
}

.pipeline-step.is-ok .step-dot {
  background: var(--color-success);
}

.pipeline-step.is-fail .step-dot {
  background: var(--color-danger);
}

.pipeline-step.is-pending .step-dot {
  background: var(--color-warning);
}

.step-label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--color-text-primary);
}

.step-detail {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}

.pipeline-extra {
  margin: var(--spacing-sm) 0 0;
  font-size: var(--font-size-xs);
  color: var(--color-text-muted);
}
</style>
