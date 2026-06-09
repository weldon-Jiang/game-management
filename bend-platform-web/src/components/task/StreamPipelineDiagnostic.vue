<template>
  <section v-if="steps.length" class="pipeline-diagnostic content-card">
    <h3>串流管道诊断</h3>
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
    <p v-if="extra.firstFrameSize || extra.lanIp || extra.streamMode || extra.rtpPort" class="pipeline-extra">
      <span v-if="extra.streamMode"> · 模式：LAN</span>
      <span v-if="extra.lanIp"> · IP：{{ extra.lanIp }}</span>
      <span v-if="extra.rtpPort"> · RTP：{{ extra.rtpPort }}</span>
      <span v-if="extra.firstFrameSize"> · 首帧：{{ extra.firstFrameSize }}</span>
      <span v-if="extra.inputChannelState"> · 输入：{{ extra.inputChannelState }}</span>
    </p>
  </section>
</template>

<script setup>
/**
 * TaskDetail 管道诊断：auth / discovery / lanConnect / dtlsSrtp / first_frame / input_dc。
 * 数据来自 Agent STEP2/3 上报的 pipelineDiagnostic。
 */
import { computed } from 'vue'

const props = defineProps({
  diagnostic: {
    type: Object,
    default: null
  }
})

const STEP_DEFS = [
  { key: 'auth', label: '认证 (MSAL)' },
  { key: 'discovery', label: '主机发现 (GSSV∩LAN)' },
  { key: 'lanConnect', label: 'LAN 握手' },
  { key: 'dtlsSrtp', label: 'DTLS-SRTP' },
  { key: 'firstFrame', label: '首帧' },
  { key: 'inputDc', label: '输入通道' }
]

const extra = computed(() => props.diagnostic || {})

const steps = computed(() => {
  if (!props.diagnostic) return []
  return STEP_DEFS.filter(s => props.diagnostic[s.key] != null)
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
