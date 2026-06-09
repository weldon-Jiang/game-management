<template>
  <el-dialog
    :model-value="modelValue"
    :title="`串流主机 - ${account?.email || ''}`"
    width="720px"
    :close-on-click-modal="false"
    class="host-bind-dialog"
    @update:model-value="emit('update:modelValue', $event)"
    @open="onOpen"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="host-hint"
      title="不绑定也可启动串流：Agent 会自动发现并连接，成功后自动建立绑定。"
    />

    <div class="bind-section">
      <h4>已绑定主机</h4>
      <el-table :data="boundHosts" v-loading="loading" max-height="220">
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.name || row.xboxId || '-' }}</template>
        </el-table-column>
        <el-table-column prop="platform" label="平台" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getPlatformTypeTag(row.platform)" size="small">
              {{ getPlatformTypeText(row.platform) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ipAddress" label="IP" width="130" />
        <el-table-column prop="locked" label="锁定" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.locked ? 'danger' : 'success'" size="small">
              {{ row.locked ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="handleUnbind(row)">解绑</el-button>
            <el-button
              v-if="row.locked"
              type="warning"
              link
              size="small"
              @click="handleUnlock(row)"
            >
              解锁
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="!loading && !boundHosts.length" class="empty-tip">暂无绑定，首次串流成功后会自动绑定</p>
    </div>

    <div class="bind-section">
      <h4>手动绑定</h4>
      <p class="section-desc">从商户已登记主机中选择（需与账号同平台）</p>
      <el-table
        ref="candidateTableRef"
        :data="candidateHosts"
        v-loading="candidatesLoading"
        max-height="200"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.name || row.xboxId || row.id }}</template>
        </el-table-column>
        <el-table-column prop="ipAddress" label="IP" width="130" />
        <el-table-column prop="xboxId" label="设备 ID" min-width="160" show-overflow-tooltip />
      </el-table>
      <p v-if="!candidatesLoading && !candidateHosts.length" class="empty-tip">
        暂无可绑定的同平台主机（Agent 串流/LAN 发现后会登记到本商户主机库）
      </p>
      <div class="bind-actions">
        <el-button
          type="primary"
          size="small"
          :disabled="!selectedCandidates.length"
          :loading="binding"
          @click="handleBindSelected"
        >
          绑定选中 ({{ selectedCandidates.length }})
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
/**
 * 串流账号 ↔ 主机绑定管理（M:N）。
 * 替代独立「Xbox主机」菜单中的账号绑定能力。
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { streamingApi } from '@/api/streaming'
import { xboxApi } from '@/api/xbox'
import {
  getPlatformTypeTag,
  getPlatformTypeText,
  isSamePlatformType,
  normalizePlatformType
} from '@/utils/constants'

const props = defineProps({
  modelValue: Boolean,
  account: { type: Object, default: null }
})
const emit = defineEmits(['update:modelValue', 'changed'])

const loading = ref(false)
const candidatesLoading = ref(false)
const binding = ref(false)
const boundHosts = ref([])
const candidateHosts = ref([])
const selectedCandidates = ref([])
const candidateTableRef = ref(null)

const onOpen = async () => {
  selectedCandidates.value = []
  if (candidateTableRef.value) {
    candidateTableRef.value.clearSelection()
  }
  await loadBoundHosts()
  await loadCandidates()
}

const loadBoundHosts = async () => {
  if (!props.account?.id) return
  loading.value = true
  try {
    const res = await streamingApi.getBoundHosts(props.account.id)
    boundHosts.value = res.data || []
  } catch (error) {
    console.error('Failed to load bound hosts:', error)
    boundHosts.value = []
  } finally {
    loading.value = false
  }
}

const loadCandidates = async () => {
  if (!props.account?.id) return
  candidatesLoading.value = true
  try {
    const res = await xboxApi.listPage({ pageNum: 1, pageSize: 500 })
    const platform = normalizePlatformType(props.account.platform)
    const boundIds = new Set(boundHosts.value.map((h) => h.id))
    candidateHosts.value = (res.data?.records || []).filter(
      (h) => isSamePlatformType(h.platform, platform) && !boundIds.has(h.id)
    )
  } catch (error) {
    console.error('Failed to load host candidates:', error)
    candidateHosts.value = []
  } finally {
    candidatesLoading.value = false
  }
}

const onSelectionChange = (rows) => {
  selectedCandidates.value = rows
}

const handleBindSelected = async () => {
  if (!selectedCandidates.value.length || !props.account?.id) return
  binding.value = true
  try {
    for (const host of selectedCandidates.value) {
      await streamingApi.bindHost(props.account.id, host.id)
    }
    ElMessage.success('绑定成功')
    selectedCandidates.value = []
    if (candidateTableRef.value) {
      candidateTableRef.value.clearSelection()
    }
    await loadBoundHosts()
    await loadCandidates()
    emit('changed')
  } catch (error) {
    console.error('Failed to bind hosts:', error)
  } finally {
    binding.value = false
  }
}

const handleUnbind = async (row) => {
  try {
    await ElMessageBox.confirm(`确定解绑主机「${row.name || row.xboxId}」？`, '解绑确认', {
      type: 'warning'
    })
    await streamingApi.unbindHost(props.account.id, row.id)
    ElMessage.success('解绑成功')
    await loadBoundHosts()
    await loadCandidates()
    emit('changed')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to unbind host:', error)
    }
  }
}

const handleUnlock = async (row) => {
  try {
    await ElMessageBox.confirm('确定强制解锁该主机？', '解锁确认', { type: 'warning' })
    await xboxApi.unlock(row.id)
    ElMessage.success('解锁成功')
    await loadBoundHosts()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to unlock host:', error)
    }
  }
}
</script>

<style scoped>
.host-hint {
  margin-bottom: 16px;
}
.bind-section {
  margin-bottom: 20px;
}
.bind-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--text-primary);
}
.section-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--text-muted);
}
.empty-tip {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
}
.bind-actions {
  margin-top: 12px;
  text-align: right;
}
</style>
