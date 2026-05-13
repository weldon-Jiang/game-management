<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>Agent版本管理</h2>
        <span class="header-desc">管理Agent版本和更新</span>
      </div>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          发布新版本
        </el-button>
      </div>
    </div>

    <div class="content-card table-container">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
      >
        <el-table-column prop="version" label="版本号" width="120" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
              {{ row.status === 1 ? '已发布' : '未发布' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="mandatory" label="更新类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.mandatory === 1 ? 'danger' : 'warning'" size="small">
              {{ row.mandatory === 1 ? '强制更新' : '可选更新' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="forceRestart" label="重启方式" width="100" align="center">
          <template #default="{ row }">
            <span>{{ row.forceRestart === 1 ? '需要重启' : '热更新' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="changelog" label="更新日志" min-width="200" show-overflow-tooltip />
        <el-table-column prop="downloadUrl" label="下载链接" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <el-link :href="row.downloadUrl" target="_blank" type="primary">
              {{ row.downloadUrl }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="createdTime" label="发布时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right" align="center" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 1"
              type="success"
              link
              size="small"
              @click="handleNotifyAll(row)"
            >
              通知所有Agent
            </el-button>
            <el-button
              v-if="row.status !== 1"
              type="primary"
              link
              size="small"
              @click="handlePublish(row)"
            >
              发布
            </el-button>
            <el-button
              v-if="row.status === 1"
              type="warning"
              link
              size="small"
              @click="handleUnpublish(row)"
            >
              取消发布
            </el-button>
            <el-button
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

    <el-dialog
      v-model="showDialog"
      :title="isEdit ? '编辑版本' : '发布新版本'"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="版本号" prop="version">
          <el-input
            v-model="form.version"
            placeholder="如：1.0.0"
            :disabled="isEdit"
          />
        </el-form-item>
        <el-form-item label="下载链接" prop="downloadUrl">
          <el-input
            v-model="form.downloadUrl"
            placeholder="Agent安装包的下载地址"
          />
        </el-form-item>
        <el-form-item label="MD5校验" prop="md5Checksum">
          <el-input
            v-model="form.md5Checksum"
            placeholder="文件的MD5值（可选）"
          />
        </el-form-item>
        <el-form-item label="更新日志" prop="changelog">
          <el-input
            v-model="form.changelog"
            type="textarea"
            :rows="4"
            placeholder="描述本次更新的内容"
          />
        </el-form-item>
        <el-form-item label="更新类型" prop="mandatory">
          <el-radio-group v-model="form.mandatory">
            <el-radio :label="0">可选更新</el-radio>
            <el-radio :label="1">强制更新</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="重启方式" prop="forceRestart">
          <el-radio-group v-model="form.forceRestart">
            <el-radio :label="0">热更新（无需重启）</el-radio>
            <el-radio :label="1">需要重启</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="最低兼容版本" prop="minCompatibleVersion">
          <el-input
            v-model="form.minCompatibleVersion"
            placeholder="低于此版本的Agent需要更新（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          {{ isEdit ? '保存' : '发布' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { agentVersionApi } from '@/api'

const loading = ref(false)
const submitLoading = ref(false)
const showDialog = ref(false)
const isEdit = ref(false)
const tableData = ref([])
const formRef = ref(null)

const form = reactive({
  version: '',
  downloadUrl: '',
  md5Checksum: '',
  changelog: '',
  mandatory: 0,
  forceRestart: 0,
  minCompatibleVersion: ''
})

const rules = {
  version: [{ required: true, message: '请输入版本号', trigger: 'blur' }],
  downloadUrl: [{ required: true, message: '请输入下载链接', trigger: 'blur' }]
}

const openCreateDialog = () => {
  isEdit.value = false
  Object.assign(form, {
    version: '',
    downloadUrl: '',
    md5Checksum: '',
    changelog: '',
    mandatory: 0,
    forceRestart: 0,
    minCompatibleVersion: ''
  })
  showDialog.value = true
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (isEdit.value) {
      await agentVersionApi.update(form.id, form)
      ElMessage.success('保存成功')
    } else {
      await agentVersionApi.create(form)
      ElMessage.success('发布成功')
    }
    showDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

const handlePublish = async (row) => {
  await ElMessageBox.confirm(`确定要发布版本 ${row.version} 吗？`, '确认发布', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'info'
  })

  try {
    await agentVersionApi.publish(row.id)
    ElMessage.success('发布成功')
    loadData()
  } catch (error) {
    // 已在拦截器处理
  }
}

const handleUnpublish = async (row) => {
  await ElMessageBox.confirm(`确定要取消发布版本 ${row.version} 吗？`, '确认取消', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await agentVersionApi.unpublish(row.id)
    ElMessage.success('取消发布成功')
    loadData()
  } catch (error) {
    // 已在拦截器处理
  }
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除版本 ${row.version} 吗？此操作不可恢复！`, '确认删除', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await agentVersionApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 已在拦截器处理
  }
}

const handleNotifyAll = async (row) => {
  await ElMessageBox.confirm(
    `确定要通知所有在线Agent更新到版本 ${row.version} 吗？`,
    '通知所有Agent',
    {
      confirmButtonText: '确定通知',
      cancelButtonText: '取消',
      type: 'info'
    }
  )

  try {
    const res = await agentVersionApi.notifyAll(row.id)
    if (res.code === 0 || res.code === 200) {
      const data = res.data || {}
      ElMessage.success(`已通知${data.successCount || 0}个Agent`)
    } else {
      ElMessage.error(res.message || '通知失败')
    }
  } catch (error) {
    ElMessage.error('通知失败')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await agentVersionApi.list()
    if (res.code === 0 || res.code === 200) {
      tableData.value = res.data || []
    }
  } catch (error) {
    console.error('Failed to load versions:', error)
  } finally {
    loading.value = false
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

:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.03);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.15);
  --el-table-border-color: rgba(255, 255, 255, 0.06);
  --el-table-text-color: #b0b0b0;
  --el-table-header-text-color: #888888;
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

:deep(.el-dialog) {
  background: rgba(18, 18, 26, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 20px 24px;
}

:deep(.el-dialog__title) {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
}

:deep(.el-form-item__label) {
  color: #b0b0b0;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: #ffffff;
}

:deep(.el-textarea__inner) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
  color: #ffffff;
}
</style>
