<template>
  <div class="event-timeline-panel" :class="{ embedded }">
    <div class="panel-header">
      <span class="panel-title">事件时间线</span>
      <span v-if="events.length" class="panel-count">{{ events.length }} 条</span>
    </div>
    <div ref="scrollRef" class="panel-body">
      <el-timeline v-if="events.length">
        <el-timeline-item
          v-for="ev in events"
          :key="ev.id"
          :timestamp="formatTime(ev.createdTime)"
          placement="top"
          class="timeline-entry"
        >
          <div class="entry-row">
            <span class="scope-tag">{{ scopeLabel(ev.scope) }}</span>
            <span v-if="ev.phase" class="phase">{{ phaseLabel(ev.phase, ev.scope) }}</span>
            <span class="msg">{{ displayMessage(ev) }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无事件记录" :image-size="40" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import {
  getSessionPhaseText,
  getTaskStatusText,
  getGameAccountRunStatusText,
  getTaskEventScopeText,
  getTaskEventPhaseText,
  getTaskEventMessageText
} from '@/utils/constants'

const props = defineProps({
  events: { type: Array, default: () => [] },
  /** 嵌入任务详情侧栏时为 true，取消右下角悬浮 */
  embedded: { type: Boolean, default: false }
})

const scrollRef = ref(null)

const formatTime = (t) => {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

const scopeLabel = (scope) => getTaskEventScopeText(scope)

const phaseLabel = (phase, scope) => getTaskEventPhaseText(phase, scope)

const statusLabel = (status) => {
  if (!status) return ''
  const taskText = getTaskStatusText(status)
  if (taskText !== status) return taskText
  return getGameAccountRunStatusText(status)
}

const displayMessage = (ev) => {
  const raw = ev.message || statusLabel(ev.status)
  return getTaskEventMessageText(raw)
}

/** Center the newest event (API returns desc — first item is latest). */
const scrollNewestToCenter = () => {
  nextTick(() => {
    const container = scrollRef.value
    if (!container) return

    const items = container.querySelectorAll('.el-timeline-item')
    const newest = items[0]
    if (!newest) {
      container.scrollTop = 0
      return
    }

    const targetTop = newest.offsetTop - container.clientHeight / 2 + newest.offsetHeight / 2
    container.scrollTop = Math.max(0, Math.min(targetTop, container.scrollHeight - container.clientHeight))
  })
}

watch(
  () => props.events.map((e) => e.id).join(','),
  () => scrollNewestToCenter()
)

onMounted(() => scrollNewestToCenter())
</script>

<style scoped>
.event-timeline-panel {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 100;
  width: 360px;
  max-width: calc(100vw - 40px);
  background: rgba(15, 15, 26, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.event-timeline-panel.embedded {
  position: sticky;
  top: 16px;
  right: auto;
  bottom: auto;
  z-index: 1;
  width: 100%;
  max-width: none;
  height: fit-content;
  max-height: calc(100vh - 120px);
  box-shadow: none;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #e8e8f0;
}

.panel-count {
  font-size: 11px;
  color: #888;
}

.panel-body {
  height: 260px;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 14px 12px;
  scroll-behavior: smooth;
}

.embedded .panel-body {
  height: auto;
  min-height: 200px;
  max-height: calc(100vh - 180px);
}

.panel-body :deep(.el-timeline) {
  padding-left: 2px;
}

.panel-body :deep(.el-timeline-item) {
  padding-bottom: 10px;
}

.panel-body :deep(.el-timeline-item__timestamp) {
  font-size: 11px;
  color: #888;
  margin-bottom: 2px;
}

.entry-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  line-height: 1.4;
}

.scope-tag {
  display: inline-block;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.phase {
  color: var(--el-color-primary);
  font-size: 12px;
  flex-shrink: 0;
}

.msg {
  font-size: 12px;
  word-break: break-word;
}

.panel-body::-webkit-scrollbar {
  width: 6px;
}

.panel-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.18);
  border-radius: 3px;
}

.panel-body::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}
</style>
