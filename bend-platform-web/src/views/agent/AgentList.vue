<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>Agent管理</h2>
        <span class="header-desc">查看和管理Agent实例</span>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-select
          v-model="filterStatus"
          placeholder="状态筛选"
          style="width: 120px"
          clearable
          @change="handleSearch"
        >
          <el-option label="全部" value="" />
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
          <el-option label="已卸载" value="uninstalled" />
        </el-select>
        <el-button @click="handleSearch">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>

      <div class="table-container">
        <el-table
          :data="tableData"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
        >
        <el-table-column prop="agentId" label="Agent ID" min-width="180" show-overflow-tooltip />
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantId" label="商户" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.merchantName">{{ row.merchantName }}</span>
            <span v-else class="text-muted">{{ row.merchantId || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="host" label="主机地址" width="150" />
        <el-table-column prop="port" label="端口" width="80" align="center" />
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getAgentStatusType(row.status)" size="small">
              {{ getAgentStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastHeartbeat" label="最后心跳" width="170">
          <template #default="{ row }">
            {{ row.lastHeartbeat ? formatDate(row.lastHeartbeat) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showTaskDialog(row)">
              查看任务
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </div>

    <AgentTaskDialog
      v-model:visible="taskDialogVisible"
      :agent="selectedAgent"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { agentApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { getAgentStatusText, getAgentStatusType } from '@/utils/constants'
import AgentTaskDialog from './AgentTaskDialog.vue'

const authStore = useAuthStore()

const filterStatus = ref('')

const loading = ref(false)
const tableData = ref([])

const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const taskDialogVisible = ref(false)
const selectedAgent = ref(null)

const handleSearch = () => {
  pagination.pageNum = 1
  loadData()
}

const loadData = async () => {
  loading.value = true
  try {
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    const res = await agentApi.list(params)
    if (res.code === 0 || res.code === 200) {
      tableData.value = res.data?.records || []
      pagination.total = res.data?.total || 0
    }
  } catch (error) {
    console.error('Failed to load agent instances:', error)
  } finally {
    loading.value = false
  }
}

const showTaskDialog = (agent) => {
  selectedAgent.value = agent
  taskDialogVisible.value = true
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

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.page-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px;
}

.header-desc {
  font-size: 13px;
  color: #8a8a8a;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.03);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.15);
  --el-table-current-row-bg-color: rgba(99, 102, 241, 0.1);
  --el-table-border-color: rgba(255, 255, 255, 0.06);
  --el-table-header-border-color: rgba(255, 255, 255, 0.06);
  --el-table-text-color: #b0b0b0;
  --el-table-header-text-color: #888888;
  --el-table-row-hover-text-color: #ffffff;
}

:deep(.el-table__inner-wrapper::before) {
  display: none;
}

:deep(.el-table .el-table__row) {
  background: transparent !important;
}

:deep(.el-table .el-table__row:hover > td) {
  background: rgba(99, 102, 241, 0.15) !important;
}

:deep(.el-table__fixed-right:hover),
:deep(.el-table__fixed:hover) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__fixed-right .el-table__row:hover td),
:deep(.el-table__fixed .el-table__row:hover td) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__body-wrapper .el-table__row:hover td.el-table__cell) {
  background-color: #1a1a2e !important;
}

:deep(.el-table th.el-table__cell) {
  font-weight: 500;
  font-size: 13px;
}

:deep(.el-table td.el-table__cell) {
  font-size: 13px;
  padding: 14px 0;
}

.text-muted {
  color: #6b7280;
  font-size: 12px;
}

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}
</style>
