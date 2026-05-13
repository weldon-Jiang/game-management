<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>任务管理</h2>
        <span class="header-desc">创建、下发和管理自动化任务</span>
      </div>
      <div class="header-right">
        <el-button type="primary" @click="showCreateDialog">
          <el-icon><Plus /></el-icon>
          创建任务
        </el-button>
      </div>
    </div>

    <div class="content-card">
      <div class="toolbar">
        <el-select
          v-model="filterStatus"
          placeholder="状态筛选"
          style="width: 140px"
          clearable
          @change="handleSearch"
        >
          <el-option label="全部" value="" />
          <el-option label="待执行" value="pending" />
          <el-option label="执行中" value="running" />
          <el-option label="已完成" value="completed" />
          <el-option label="已失败" value="failed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-select
          v-model="filterType"
          placeholder="类型筛选"
          style="width: 140px"
          clearable
          @change="handleSearch"
        >
          <el-option label="全部" value="" />
          <el-option label="模板匹配" value="template_match" />
          <el-option label="输入序列" value="input_sequence" />
          <el-option label="场景检测" value="scene_detection" />
          <el-option label="账号切换" value="account_switch" />
          <el-option label="串流控制" value="stream_control" />
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
        <el-table-column prop="name" label="任务名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ getTaskTypeText(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row.status)" size="small">
              {{ getTaskStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="游戏账号进度" width="140" align="center">
          <template #default="{ row }">
            <span v-if="row.result && row.result.includes('/')">
              {{ row.result }}
            </span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="agentId" label="执行Agent" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.agentName">{{ row.agentName }}</span>
            <span v-else-if="row.agentId" class="text-muted">{{ row.agentId.substring(0, 8) }}...</span>
            <span v-else class="text-muted">未分配</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center">
          <template #default="{ row }">
            <span :class="'priority-' + row.priority">{{ row.priority }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="result" label="结果" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.result" class="text-muted">{{ row.result }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ row.createdTime ? formatDate(row.createdTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="assignedTime" label="分配时间" width="170">
          <template #default="{ row }">
            {{ row.assignedTime ? formatDate(row.assignedTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              type="primary"
              link
              size="small"
              @click="showAssignDialog(row)"
            >
              分配
            </el-button>
            <el-button
              v-if="row.status === 'pending' || row.status === 'failed'"
              type="warning"
              link
              size="small"
              @click="handleRetry(row)"
            >
              重试
            </el-button>
            <el-button
              v-if="row.status === 'running'"
              type="danger"
              link
              size="small"
              @click="handleCancel(row)"
            >
              取消
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="danger"
              link
              size="small"
              @click="handleDelete(row)"
            >
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

    <el-dialog
      v-model="createDialogVisible"
      title="创建任务"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="createForm" label-width="100px" ref="createFormRef">
        <el-form-item label="任务名称" prop="name" required>
          <el-input v-model="createForm.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="任务类型" prop="type" required>
          <el-select v-model="createForm.type" placeholder="请选择任务类型" style="width: 100%">
            <el-option label="模板匹配" value="template_match" />
            <el-option label="输入序列" value="input_sequence" />
            <el-option label="场景检测" value="scene_detection" />
            <el-option label="账号切换" value="account_switch" />
            <el-option label="串流控制" value="stream_control" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-input-number v-model="createForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="任务参数" prop="params">
          <el-input
            v-model="createForm.paramsJson"
            type="textarea"
            :rows="4"
            placeholder='请输入JSON格式的任务参数，如: {"template": "start_button.png", "threshold": 0.8}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="assignDialogVisible"
      title="分配任务"
      width="500px"
    >
      <el-form label-width="100px">
        <el-form-item label="任务">
          <span>{{ currentTask?.name }}</span>
        </el-form-item>
        <el-form-item label="选择Agent" required>
          <el-select
            v-model="selectedAgentId"
            placeholder="请选择在线Agent"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="agent in onlineAgents"
              :key="agent.agentId"
              :label="agent.agentId.substring(0, 8) + '... - ' + (agent.merchantName || '未知商户')"
              :value="agent.agentId"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAssign">分配</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { taskApi, agentApi } from '@/api'
import { getTaskTypeText, getTaskStatusText, getTaskStatusType } from '@/utils/constants'

const filterStatus = ref('')
const filterType = ref('')
const loading = ref(false)
const tableData = ref([])
const onlineAgents = ref([])

const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

const createDialogVisible = ref(false)
const assignDialogVisible = ref(false)
const currentTask = ref(null)
const selectedAgentId = ref('')

const createForm = reactive({
  name: '',
  type: '',
  priority: 0,
  paramsJson: ''
})

const createFormRef = ref(null)

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
    if (filterType.value) {
      params.type = filterType.value
    }
    const res = await taskApi.list(params)
    if (res.code === 0 || res.code === 200) {
      tableData.value = res.data?.records || []
      pagination.total = res.data?.total || 0
    }
  } catch (error) {
    console.error('Failed to load tasks:', error)
  } finally {
    loading.value = false
  }
}

const loadOnlineAgents = async () => {
  try {
    const res = await agentApi.list({ status: 'online', pageSize: 100 })
    if (res.code === 0 || res.code === 200) {
      onlineAgents.value = res.data?.records || []
    }
  } catch (error) {
    console.error('Failed to load online agents:', error)
  }
}

const showCreateDialog = () => {
  createForm.name = ''
  createForm.type = ''
  createForm.priority = 0
  createForm.paramsJson = ''
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.name || !createForm.type) {
    ElMessage.warning('请填写任务名称和类型')
    return
  }

  try {
    let params = {}
    if (createForm.paramsJson) {
      try {
        params = JSON.parse(createForm.paramsJson)
      } catch (e) {
        ElMessage.error('任务参数JSON格式错误')
        return
      }
    }

    const data = {
      name: createForm.name,
      type: createForm.type,
      priority: createForm.priority,
      params: params
    }

    const res = await taskApi.create(data)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务创建成功')
      createDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch (error) {
    ElMessage.error('创建失败')
  }
}

const showAssignDialog = (task) => {
  currentTask.value = task
  selectedAgentId.value = ''
  assignDialogVisible.value = true
}

const handleAssign = async () => {
  if (!selectedAgentId.value) {
    ElMessage.warning('请选择Agent')
    return
  }

  try {
    const res = await taskApi.assign(currentTask.value.id, selectedAgentId.value)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务分配成功')
      assignDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '分配失败')
    }
  } catch (error) {
    ElMessage.error('分配失败')
  }
}

const handleRetry = async (task) => {
  try {
    const res = await taskApi.retry(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务重试成功')
      loadData()
    } else {
      ElMessage.error(res.message || '重试失败')
    }
  } catch (error) {
    ElMessage.error('重试失败')
  }
}

const handleCancel = async (task) => {
  try {
    const res = await taskApi.cancel(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('任务已取消')
      loadData()
    } else {
      ElMessage.error(res.message || '取消失败')
    }
  } catch (error) {
    ElMessage.error('取消失败')
  }
}

const handleDelete = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除该任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = await taskApi.delete(task.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('删除成功')
      loadData()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadData()
  loadOnlineAgents()
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

.header-right {
  display: flex;
  gap: 12px;
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

.priority-0 { color: #6b7280; }
.priority-1 { color: #22c55e; }
.priority-2 { color: #eab308; }
.priority-3 { color: #f97316; }
.priority-4 { color: #ef4444; }

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

.data-table {
  width: 100%;
}

/* 固定列hover不变透明 */
.data-table >>> .el-table__fixed-right:hover,
.data-table >>> .el-table__fixed:hover {
  background-color: #0f0f1a !important;
}

.data-table >>> .el-table__fixed-right .el-table__row:hover td,
.data-table >>> .el-table__fixed .el-table__row:hover td {
  background-color: #0f0f1a !important;
}

.data-table >>> .el-table__body-wrapper .el-table__row:hover td.el-table__cell {
  background-color: #1a1a2e !important;
}
</style>
