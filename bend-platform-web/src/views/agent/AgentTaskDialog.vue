<template>
  <el-dialog
    v-model="dialogVisible"
    title="Agent 任务监控"
    width="900px"
    :close-on-click-modal="false"
  >
    <div v-if="agent" class="agent-info">
      <el-descriptions :column="3" size="small" border>
        <el-descriptions-item label="Agent ID">{{ agent.agentId }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ agent.merchantName || agent.merchantId }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getAgentStatusType(agent.status)" size="small">
            {{ getAgentStatusText(agent.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="主机地址">{{ agent.host }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ agent.version }}</el-descriptions-item>
        <el-descriptions-item label="最后心跳">{{ formatDate(agent.lastHeartbeat) }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="运行中的任务" name="running">
        <el-table :data="runningTasks" v-loading="loading" max-height="300">
          <el-table-column prop="id" label="任务ID" width="180" show-overflow-tooltip />
          <el-table-column prop="name" label="任务名称" min-width="150" />
          <el-table-column prop="type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusType(row.status)" size="small">
                {{ getTaskStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="streamingAccountId" label="流媒体账号" width="150" show-overflow-tooltip />
          <el-table-column prop="createdTime" label="创建时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.createdTime) }}
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && runningTasks.length === 0" class="empty-tip">
          暂无运行中的任务
        </div>
      </el-tab-pane>
      <el-tab-pane label="所有任务" name="all">
        <el-table :data="allTasks" v-loading="loading" max-height="300">
          <el-table-column prop="id" label="任务ID" width="180" show-overflow-tooltip />
          <el-table-column prop="name" label="任务名称" min-width="150" />
          <el-table-column prop="type" label="类型" width="120">
            <template #default="{ row }">
              <el-tag size="small" type="info">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getTaskStatusType(row.status)" size="small">
                {{ getTaskStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="result" label="结果" min-width="120" show-overflow-tooltip />
          <el-table-column prop="createdTime" label="创建时间" width="160">
            <template #default="{ row }">
              {{ formatDate(row.createdTime) }}
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!loading && allTasks.length === 0" class="empty-tip">
          暂无任务记录
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button type="primary" @click="handleRefresh" :loading="loading">
        刷新
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { taskApi } from '@/api'
import { getAgentStatusText, getAgentStatusType, getTaskStatusText, getTaskStatusType } from '@/utils/constants'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  agent: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:visible'])

const dialogVisible = ref(false)
const activeTab = ref('running')
const loading = ref(false)
const runningTasks = ref([])
const allTasks = ref([])

watch(() => props.visible, (val) => {
  dialogVisible.value = val
  if (val && props.agent) {
    activeTab.value = 'running'
    loadTasks()
  }
})

watch(dialogVisible, (val) => {
  emit('update:visible', val)
})

const loadTasks = async () => {
  if (!props.agent?.agentId) return
  loading.value = true
  try {
    const res = await taskApi.list({ agentId: props.agent.agentId, pageSize: 100 })
    if (res.code === 0 || res.code === 200) {
      const tasks = res.data?.records || []
      runningTasks.value = tasks.filter((t) => t.status === 'running')
      allTasks.value = tasks
    }
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const handleRefresh = () => {
  loadTasks()
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.agent-info {
  margin-bottom: 20px;
}

.task-tabs {
  margin-top: 16px;
}

.empty-tip {
  text-align: center;
  color: #6b7280;
  padding: 40px 0;
}

:deep(.el-dialog) {
  background: rgba(18, 18, 26, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

:deep(.el-dialog__title) {
  color: #ffffff;
}

:deep(.el-dialog__body) {
  padding: 20px;
}

:deep(.el-tabs__nav-wrap::after) {
  background: rgba(255, 255, 255, 0.06);
}

:deep(.el-tabs__item) {
  color: #8a8a8a;
}

:deep(.el-tabs__item.is-active) {
  color: #6366f1;
}

:deep(.el-tabs__active-bar) {
  background: #6366f1;
}
</style>
