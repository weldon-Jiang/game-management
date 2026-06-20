<template>
  <div class="edit-groups">
    <div v-for="group in editGroups" :key="group.label" class="edit-group">
      <div class="edit-group-title">{{ group.label }}</div>
      <el-table :data="group.rows" size="small" class="mapping-table">
        <el-table-column label="手柄目标" min-width="140">
          <template #default="{ row }">
            <span class="target-label">{{ row.label }}</span>
          </template>
        </el-table-column>
        <el-table-column label="键盘按键" min-width="180">
          <template #default="{ row }">
            <div class="key-input-wrap">
              <el-input
                v-model="row.key"
                placeholder="聚焦后按一次键"
                maxlength="16"
                size="small"
                :class="{ 'key-conflict': isKeyConflict(row) }"
                @keydown.prevent
                @keyup.prevent="captureKey($event, row)"
              />
              <div v-if="conflictHint(row)" class="conflict-hint">{{ conflictHint(row) }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="defaultKey" label="默认键" width="90" class-name="text-muted-col">
          <template #default="{ row }">
            {{ formatDefaultKey(row.defaultKey) }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
/**
 * 全量键盘映射编辑表（按分组）。
 */
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  normalizeBrowserKeyName
} from '@/composables/useKeyboardMappingActions'
import { capDisplayKey } from '@/composables/useKeyboardMappingLayout'
import {
  duplicateKeyHintForRow,
  findDuplicateKeyConflicts,
  validateKeyboardMappingRows
} from '@/composables/useKeyboardMappingValidation'

const props = defineProps({
  rows: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:rows'])

const editGroups = computed(() => {
  const map = new Map()
  for (const row of props.rows) {
    const label = row.groupLabel || '其他'
    if (!map.has(label)) {
      map.set(label, { label, rows: [] })
    }
    map.get(label).rows.push(row)
  }
  return Array.from(map.values())
})

const formatDefaultKey = (bindingKey) => capDisplayKey(bindingKey)

/** 同一键盘键被多个手柄目标使用时标红输入框。 */
const duplicateKeyLabels = computed(() => {
  const conflicts = new Map()
  for (const item of findDuplicateKeyConflicts(props.rows)) {
    conflicts.set(item.key, item.targets)
  }
  return conflicts
})

const isKeyConflict = (row) => {
  const key = (row.key || '').trim().toLowerCase()
  return key && duplicateKeyLabels.value.has(key)
}

const conflictHint = (row) => duplicateKeyHintForRow(props.rows, row)

const captureKey = (event, row) => {
  const key = normalizeBrowserKeyName(event)
  if (key) {
    row.key = key
    emit('update:rows', props.rows)
    const check = validateKeyboardMappingRows(props.rows)
    if (!check.ok) {
      ElMessage.warning(check.message)
    }
  }
}
</script>

<style scoped>
.edit-groups {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.edit-group-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-xs);
}

.mapping-table {
  width: 100%;
}

.target-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

:deep(.key-conflict .el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger) inset;
}

.key-input-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conflict-hint {
  font-size: 12px;
  line-height: 1.3;
  color: var(--danger);
}
</style>
