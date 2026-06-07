<template>
  <div class="event-timeline" v-if="events.length">
    <h4>事件时间线</h4>
    <el-timeline>
      <el-timeline-item
        v-for="ev in events"
        :key="ev.id"
        :timestamp="formatTime(ev.createdTime)"
        placement="top"
      >
        <span class="scope-tag">{{ scopeLabel(ev.scope) }}</span>
        <span v-if="ev.phase" class="phase">{{ phaseLabel(ev.phase) }}</span>
        <span class="msg">{{ ev.message || statusLabel(ev.status) }}</span>
      </el-timeline-item>
    </el-timeline>
  </div>
  <el-empty v-else description="暂无事件记录" :image-size="48" />
</template>

<script setup>
import {
  getSessionPhaseText,
  getTaskStatusText,
  getGameAccountRunStatusText
} from '@/utils/constants'

defineProps({
  events: { type: Array, default: () => [] }
})

const formatTime = (t) => {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 19)
}

const scopeLabel = (scope) => {
  const map = { task: '任务', session: '会话', game_account: '游戏账号' }
  return map[scope] || scope || '任务'
}

const phaseLabel = (phase) => getSessionPhaseText(phase)

const statusLabel = (status) => {
  if (!status) return ''
  const taskText = getTaskStatusText(status)
  if (taskText !== status) return taskText
  return getGameAccountRunStatusText(status)
}
</script>

<style scoped>
.event-timeline h4 {
  margin: 0 0 12px;
  font-size: 14px;
}
.scope-tag {
  display: inline-block;
  font-size: 11px;
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 6px;
}
.phase {
  color: var(--el-color-primary);
  margin-right: 6px;
  font-size: 12px;
}
.msg {
  font-size: 13px;
}
</style>
