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
          {{ formatProvisioningDisplay(row) }}
        </span>
        <span v-else class="text-muted">已就绪</span>
      </template>
    </el-table-column>
    <el-table-column label="自动化" width="88" align="center">
      <template #default="{ row }">
        {{ getGameAccountPhaseText(row.phase) }}
      </template>
    </el-table-column>
    <el-table-column v-if="showMatchProgress" label="本次场次" width="108" align="center">
      <template #default="{ row }">
        {{ row.completedCount || 0 }}/{{ row.totalMatches || 0 }}
        <span v-if="row.failedCount" class="text-danger"> (失败{{ row.failedCount }})</span>
      </template>
    </el-table-column>
    <el-table-column label="今日场次" width="96" align="center">
      <template #default="{ row }">
        {{ row.todayMatchCount ?? row.completedCount ?? 0 }}/{{ row.dailyMatchLimit ?? row.totalMatches ?? 0 }}
      </template>
    </el-table-column>
    <el-table-column label="金币" width="120" align="center">
      <template #default="{ row }">
        <span>{{ row.todayCoins ?? 0 }}</span>
        <span class="text-muted"> / {{ row.totalCoins ?? 0 }}</span>
      </template>
    </el-table-column>
    <el-table-column label="DR" width="90" align="center">
      <template #default="{ row }">
        {{ row.drLevel || '-' }}
      </template>
    </el-table-column>
    <el-table-column label="冷却" width="80" align="center">
      <template #default="{ row }">
        {{ row.cooldownHours ?? 23 }}小时
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
    <el-table-column v-if="!readonly" label="操作" width="72" align="center">
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

/**
 * 任务详情页：单任务内各游戏账号的执行进度表。
 * 展示开通阶段、自动化 phase、场次/金币/DR 及 skip 操作；计费相关字段来自后端 join 的游戏账号快照。
 */
defineProps({
  rows: { type: Array, default: () => [] },
  /** 转会等非比赛模式可隐藏「本次场次」列 */
  showMatchProgress: { type: Boolean, default: true },
  /** 历史 session 只读查看时不展示 skip 按钮 */
  readonly: { type: Boolean, default: false }
})
defineEmits(['skip'])

/** 格式化账号开通/档案绑定进度；进行中阶段附带 step/total 供运维判断卡在哪一步。 */
function formatProvisioningDisplay(row) {
  const phase = String(row.provisioningPhase || '').toLowerCase()
  const message = row.provisioningMessage || getProvisioningPhaseText(row.provisioningPhase)
  if (phase === 'ready' || phase === 'failed' || phase === 'skipped') {
    return message
  }
  if (row.provisioningStep && row.provisioningStepTotal) {
    return `${message} (${row.provisioningStep}/${row.provisioningStepTotal})`
  }
  return message
}
</script>

<style scoped>
.text-muted {
  color: #6b7280;
}
.text-danger {
  color: #f56c6c;
}
</style>
