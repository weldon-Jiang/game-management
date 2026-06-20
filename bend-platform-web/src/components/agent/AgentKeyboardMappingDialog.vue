<template>
  <el-dialog
    v-model="visible"
    title="F8 键盘映射"
    width="820px"
    class="keyboard-mapping-dialog"
    :close-on-click-modal="false"
    @open="loadMapping"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mapping-hint"
      title="暂停后在 Agent 电脑点击串流窗口，按 F8 开启人工接管后使用下列按键。下方可编辑全部键位与手柄目标，保存后在线 Agent 将自动同步。"
    />

    <div v-if="usingDefault" class="default-tag">
      <el-tag type="info" size="small">当前使用默认映射</el-tag>
    </div>

    <el-alert
      v-if="mappingValidation.message"
      type="error"
      :closable="false"
      show-icon
      class="mapping-validation-alert"
      :title="mappingValidation.message"
    />

    <KeyboardMappingChartView
      :loading="loading"
      :groups="previewGroups"
      :key-caps="previewKeyCaps"
      :debug-hotkeys="debugHotkeys"
    />

    <div class="edit-section">
      <div class="edit-section-title">键位配置（全量可编辑）</div>
      <KeyboardMappingEditTables v-model:rows="rows" />
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :loading="saving" @click="restoreDefault">恢复默认</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * Agent F8 键盘映射：全量可视化 + 全量可编辑；保存后在线 Agent 自动同步。
 */
import { computed, ref, watch } from 'vue'
import { agentApi } from '@/api'
import { ElMessage } from 'element-plus'
import { isRequestCanceled } from '@/utils/request'
import { actionLabelForCategory } from '@/composables/useKeyboardMappingActions'
import { buildBindingsFromRows, validateKeyboardMappingRows } from '@/composables/useKeyboardMappingValidation'
import { capDisplayKey } from '@/composables/useKeyboardMappingLayout'
import KeyboardMappingChartView from '@/components/agent/KeyboardMappingChartView.vue'
import KeyboardMappingEditTables from '@/components/agent/KeyboardMappingEditTables.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  agentId: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const loading = ref(false)
const saving = ref(false)
const usingDefault = ref(true)
const rows = ref([])
const groups = ref([])
const keyCaps = ref([])
const debugHotkeys = ref([])

/** 编辑过程中根据 rows 实时刷新图例（保存后以服务端为准） */
const previewGroups = computed(() => buildPreviewGroups(rows.value, groups.value))
const previewKeyCaps = computed(() => buildPreviewKeyCaps(rows.value, keyCaps.value))
const mappingValidation = computed(() => validateKeyboardMappingRows(rows.value))

const buildPreviewGroups = (editRows, serverGroups) => {
  if (!editRows?.length) return serverGroups
  const byCategory = new Map()
  for (const row of editRows) {
    if (!row.category || !row.groupLabel) continue
    if (!byCategory.has(row.category)) {
      byCategory.set(row.category, {
        category: row.category,
        label: row.groupLabel,
        customizable: true,
        items: []
      })
    }
    const target = actionLabelForCategory(row.category, row.action)
    const keys = capDisplayKey(row.key)
    const group = byCategory.get(row.category)
    const dup = group.items.some((item) => item.keys === keys && item.target === target)
    if (dup) continue
    group.items.push({ keys, target })
  }
  return Array.from(byCategory.values())
}

const buildPreviewKeyCaps = (editRows, serverCaps) => {
  if (!editRows?.length) return serverCaps
  const seen = new Set()
  const caps = []
  for (const row of editRows) {
    const bindingKey = (row.key || '').trim().toLowerCase()
    if (!bindingKey || seen.has(bindingKey)) continue
    seen.add(bindingKey)
    caps.push({
      bindingKey,
      displayKey: capDisplayKey(row.key),
      targetLabel: actionLabelForCategory(row.category, row.action),
      category: row.category
    })
  }
  return caps
}

const applyResponseData = (data) => {
  usingDefault.value = !!data?.usingDefault
  rows.value = (data?.rows || []).map((row) => ({ ...row }))
  groups.value = data?.groups || []
  keyCaps.value = data?.keyCaps || []
  debugHotkeys.value = data?.debugHotkeys || []
}

const loadMapping = async () => {
  if (!props.agentId) return
  loading.value = true
  try {
    const res = await agentApi.getKeyboardMapping(props.agentId)
    if (res.code === 0 || res.code === 200) {
      applyResponseData(res.data)
    } else {
      ElMessage.error(res.message || '加载键盘映射失败')
    }
  } catch (error) {
    if (isRequestCanceled(error)) return
    ElMessage.error(error?.response?.data?.message || error?.message || '加载键盘映射失败')
  } finally {
    loading.value = false
  }
}

watch(() => props.agentId, () => {
  if (visible.value) loadMapping()
})

const buildBindingsPayload = () => buildBindingsFromRows(rows.value)

const handleSave = async () => {
  if (!props.agentId) return
  if (!mappingValidation.value.ok) {
    ElMessage.error(mappingValidation.value.message)
    return
  }
  saving.value = true
  try {
    const bindings = buildBindingsPayload()
    const res = await agentApi.updateKeyboardMapping(props.agentId, { bindings })
    if (res.code === 0 || res.code === 200) {
      applyResponseData(res.data)
      ElMessage.success('键盘映射已保存，在线 Agent 将自动同步')
      emit('saved')
    } else {
      ElMessage.error(res.message || '保存失败')
    }
  } catch (error) {
    ElMessage.error(error.message || error?.response?.data?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

const restoreDefault = async () => {
  if (!props.agentId) return
  saving.value = true
  try {
    const res = await agentApi.updateKeyboardMapping(props.agentId, { resetToDefault: true })
    if (res.code === 0 || res.code === 200) {
      applyResponseData(res.data)
      ElMessage.success('已恢复默认映射')
      emit('saved')
    } else {
      ElMessage.error(res.message || '恢复默认失败')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '恢复默认失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.mapping-hint {
  margin-bottom: var(--spacing-md);
}

.mapping-validation-alert {
  margin-bottom: var(--spacing-md);
}

.default-tag {
  margin-bottom: var(--spacing-sm);
}

.edit-section {
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--border-subtle);
}

.edit-section-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}
</style>
