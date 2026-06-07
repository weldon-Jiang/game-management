<template>
  <el-table :data="rows" size="small" scrollbar-always-on>
    <el-table-column label="账号" width="100" show-overflow-tooltip>
      <template #default="{ row }">
        {{ row.gameAccountName || row.gameAccountId || '-' }}
      </template>
    </el-table-column>
    <el-table-column label="准备阶段" min-width="180" show-overflow-tooltip>
      <template #default="{ row }">
        <span v-if="row.provisioningPhase">
          {{ row.provisioningMessage || getProvisioningPhaseText(row.provisioningPhase) }}
          <template v-if="row.provisioningStep">
            ({{ row.provisioningStep }}/{{ row.provisioningStepTotal || '?' }})
          </template>
        </span>
        <span v-else class="text-muted">已就绪</span>
      </template>
    </el-table-column>
    <el-table-column label="自动化" width="88" align="center">
      <template #default="{ row }">
        {{ getGameAccountPhaseText(row.phase) }}
      </template>
    </el-table-column>
    <el-table-column label="场次" width="108" align="center">
      <template #default="{ row }">
        {{ row.completedCount || 0 }}/{{ row.totalMatches || 0 }}
        <span v-if="row.failedCount" class="text-danger"> (失败{{ row.failedCount }})</span>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="108" align="center">
      <template #default="{ row }">
        <el-tag size="small" :type="getGameAccountRunStatusType(row.status)">
          {{ getGameAccountRunStatusText(row.status) }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="错误" min-width="200" show-overflow-tooltip>
      <template #default="{ row }">
        <span v-if="row.errorMessage" class="text-danger">{{ row.errorMessage }}</span>
        <span v-else class="text-muted">-</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="72" align="center">
      <template #default="{ row }">
        <el-button
          v-if="row.status === 'pending' || row.status === 'running'"
          link
          type="warning"
          @click="$emit('skip', row.gameAccountId)"
        >
          跳过
        </el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup>
import {
  getGameAccountRunStatusText,
  getGameAccountRunStatusType,
  getGameAccountPhaseText,
  getProvisioningPhaseText
} from '@/utils/constants'

defineProps({
  rows: { type: Array, default: () => [] }
})
defineEmits(['skip'])
</script>

<style scoped>
.text-muted {
  color: #6b7280;
}
.text-danger {
  color: #f56c6c;
}
</style>
