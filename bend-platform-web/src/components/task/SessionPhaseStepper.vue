<template>
  <el-steps :active="activeIndex" finish-status="success" align-center>
    <el-step title="认证" description="微软/xHome" />
    <el-step title="发现主机" />
    <el-step title="串流就绪" />
    <el-step title="选择模式" />
    <el-step title="自动化" />
  </el-steps>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  phase: { type: String, default: 'opening' }
})

const phaseIndex = {
  opening: 0,
  authenticating: 0,
  discovering: 1,
  streaming: 2,
  initializing_display: 2,
  initializing_input: 2,
  ready: 3,
  automation_failed: 3,
  automating: 4,
  paused_immediate: 4,
  paused_after_match: 4,
  closing: 4,
  closed: 5,
  failed: 0
}

const activeIndex = computed(() => phaseIndex[props.phase] ?? 0)
</script>
