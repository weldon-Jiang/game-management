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

        <div class="toolbar-right">
          <el-button @click="handleCleanupUninstalled" :loading="cleaningUninstalled">
            清理已卸载
          </el-button>
          <el-button @click="handleCleanupOffline" :loading="cleaningOffline">
            清理离线(30分钟)
          </el-button>
          <el-button
            type="danger"
            :disabled="selectedAgents.length === 0"
            @click="handleBatchDelete"
            :loading="batchDeleting"
          >
            批量删除({{ selectedAgents.length }})
          </el-button>
        </div>
      </div>

      <div class="table-container">
        <el-table
          :data="tableData"
          v-loading="loading"
          class="data-table"
          scrollbar-always-on
          @selection-change="handleSelectionChange"
        >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="agentName" label="Agent名称" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ getAgentDisplayName(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="agentId" label="Agent ID" min-width="180" show-overflow-tooltip class-name="text-muted-col" />
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantId" label="商户" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.merchantName">{{ row.merchantName }}</span>
            <span v-else class="text-muted">{{ row.merchantId || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="host" label="主机地址" width="150" show-overflow-tooltip />
        <el-table-column prop="port" label="端口" width="80" align="center" />
        <el-table-column prop="version" label="版本" width="80" align="center" />
        <el-table-column prop="osType" label="操作系统" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.osType ? row.osType + ' ' + (row.osVersion || '') : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cpuCount" label="CPU核心" width="90" align="center">
          <template #default="{ row }">
            <span>{{ row.cpuCount ? row.cpuCount + '核' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="maxConcurrentTasks" label="最大并发" width="100" align="center">
          <template #default="{ row }">
            <span>{{ row.maxConcurrentTasks || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getAgentStatusType(row.status)" size="small">
              {{ getAgentStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastHeartbeat" label="最后心跳" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.lastHeartbeat ? formatDate(row.lastHeartbeat) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showNameDialog(row)">
              编辑名称
            </el-button>
            <el-button type="primary" link size="small" @click="goAgentTasks(row)">
              查看任务
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
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

    <el-dialog v-model="nameDialogVisible" title="编辑Agent名称" width="480px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="Agent ID">
          <span class="text-muted">{{ editingAgent?.agentId }}</span>
        </el-form-item>
        <el-form-item label="Agent名称" required>
          <el-input v-model="editingAgentName" placeholder="请输入Agent名称，如：办公室1号机" maxlength="64" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="nameDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingName" @click="handleSaveName">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { agentApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { getAgentDisplayName, getAgentStatusText, getAgentStatusType } from '@/utils/constants'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

const authStore = useAuthStore()

const filterStatus = ref('')

const loading = ref(false)
const tableData = ref([])
const selectedAgents = ref([])

const cleaningUninstalled = ref(false)
const cleaningOffline = ref(false)
const batchDeleting = ref(false)
const nameDialogVisible = ref(false)
const editingAgent = ref(null)
const editingAgentName = ref('')
const savingName = ref(false)

const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const goAgentTasks = (agent) => {
  router.push({ name: 'Tasks', query: { agentId: agent.agentId } })
}

const showNameDialog = (agent) => {
  editingAgent.value = agent
  editingAgentName.value = agent.agentName || ''
  nameDialogVisible.value = true
}

const handleSaveName = async () => {
  const name = editingAgentName.value?.trim()
  if (!name) {
    ElMessage.warning('请输入Agent名称')
    return
  }
  savingName.value = true
  try {
    const res = await agentApi.updateName(editingAgent.value.agentId, { agentName: name })
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('Agent名称已更新')
      nameDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '更新失败')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '更新失败')
  } finally {
    savingName.value = false
  }
}

const handleSearch = () => {
  pagination.pageNum = 1
  loadData()
}

const handleSelectionChange = (selection) => {
  selectedAgents.value = selection
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

const handleDelete = async (agent) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除Agent "${getAgentDisplayName(agent)}" 吗？删除后无法恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const res = await agentApi.delete(agent.agentId)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('删除成功')
      loadData()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to delete agent:', error)
      ElMessage.error('删除失败')
    }
  }
}

const handleBatchDelete = async () => {
  if (selectedAgents.value.length === 0) {
    ElMessage.warning('请先选择要删除的Agent')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedAgents.value.length} 个Agent吗？删除后无法恢复。`,
      '确认批量删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    batchDeleting.value = true
    const agentIds = selectedAgents.value.map(a => a.agentId)
    const res = await agentApi.batchDelete(agentIds)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success(`成功删除 ${res.data?.deletedCount || 0} 个Agent`)
      selectedAgents.value = []
      loadData()
    } else {
      ElMessage.error(res.message || '批量删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to batch delete agents:', error)
      ElMessage.error('批量删除失败')
    }
  } finally {
    batchDeleting.value = false
  }
}

const handleCleanupUninstalled = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清理所有已卸载状态的Agent吗？清理后无法恢复。',
      '确认清理',
      {
        confirmButtonText: '清理',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    cleaningUninstalled.value = true
    const res = await agentApi.cleanupUninstalled()
    if (res.code === 0 || res.code === 200) {
      ElMessage.success(`成功清理 ${res.data?.cleanedCount || 0} 个已卸载Agent`)
      loadData()
    } else {
      ElMessage.error(res.message || '清理失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to cleanup uninstalled agents:', error)
      ElMessage.error('清理失败')
    }
  } finally {
    cleaningUninstalled.value = false
  }
}

const handleCleanupOffline = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清理所有离线超过30分钟的Agent吗？清理后无法恢复。',
      '确认清理',
      {
        confirmButtonText: '清理',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    cleaningOffline.value = true
    const res = await agentApi.cleanupOffline(30)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success(`成功清理 ${res.data?.cleanedCount || 0} 个离线Agent`)
      loadData()
    } else {
      ElMessage.error(res.message || '清理失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to cleanup offline agents:', error)
      ElMessage.error('清理失败')
    }
  } finally {
    cleaningOffline.value = false
  }
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
  flex-wrap: wrap;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
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
