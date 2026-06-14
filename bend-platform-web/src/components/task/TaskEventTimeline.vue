<template>
  <div class="event-timeline-panel" :class="{ embedded }">
    <div class="panel-header">
      <span class="panel-title">事件时间线</span>
      <span v-if="events.length" class="panel-count">{{ events.length }} 条</span>
    </div>
    <div ref="scrollRef" class="panel-body">
      <el-timeline v-if="sortedEvents.length">
        <el-timeline-item
          v-for="ev in sortedEvents"
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
          <div v-if="hostAttemptsHint(ev)" class="host-attempts-hint">
            {{ hostAttemptsHint(ev) }}
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无事件记录" :image-size="40" />
    </div>
  </div>
</template>

<script setup>
/**
 * 任务事件时间线：展示 task_event 流水，scope/phase 映射为中文标签。
 */
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import {
  getSessionPhaseText,
  getTaskStatusText,
  getGameAccountRunStatusText,
  getTaskEventScopeText,
  getTaskEventPhaseText,
  getTaskEventMessageText,
  formatHostAttemptsSummary
} from '@/utils/constants'

const props = defineProps({
  events: { type: Array, default: () => [] },
  /** 嵌入任务详情侧栏时为 true，取消右下角悬浮 */
  embedded: { type: Boolean, default: false }
})

const scrollRef = ref(null)

/** 远→近：最早在上、最新在下（API 默认 desc，此处统一升序展示） */
const sortedEvents = computed(() =>
  [...props.events].sort((a, b) => {
    const ta = a.createdTime ? new Date(a.createdTime).getTime() : 0
    const tb = b.createdTime ? new Date(b.createdTime).getTime() : 0
    if (ta !== tb) return ta - tb
    return String(a.id || '').localeCompare(String(b.id || ''))
  })
)

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

const hostAttemptsHint = (ev) => formatHostAttemptsSummary(ev.payload)

/** 滚动到底部，使最新事件始终出现在可视区域内 */
const scrollToBottom = () => {
  nextTick(() => {
    requestAnimationFrame(() => {
      const container = scrollRef.value
      if (!container) return
      container.scrollTop = container.scrollHeight
    })
  })
}

watch(
  () => sortedEvents.value.map((e) => e.id).join(','),
  () => scrollToBottom()
)

onMounted(() => scrollToBottom())
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

.host-attempts-hint {
  margin-top: 4px;
  font-size: 11px;
  color: #999;
  line-height: 1.35;
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
