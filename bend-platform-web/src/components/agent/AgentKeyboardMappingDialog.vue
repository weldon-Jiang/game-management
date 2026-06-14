<template>
  <el-dialog
    v-model="visible"
    title="键盘映射"
    width="560px"
    :close-on-click-modal="false"
    @open="loadMapping"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mapping-hint"
      title="暂停后在 Agent 电脑点击串流窗口，使用下列按键模拟手柄。未保存自定义配置时使用默认模板。"
    />

    <div v-if="usingDefault" class="default-tag">
      <el-tag type="info" size="small">当前使用默认映射</el-tag>
    </div>

    <el-table :data="rows" v-loading="loading" size="small" class="mapping-table">
      <el-table-column prop="label" label="手柄动作" min-width="120" />
      <el-table-column label="键盘按键" min-width="140">
        <template #default="{ row }">
          <el-input
            v-model="row.key"
            placeholder="如 w / j / return"
            maxlength="16"
            @keydown.prevent
            @keyup.prevent="captureKey($event, row)"
          />
        </template>
      </el-table-column>
      <el-table-column prop="defaultKey" label="默认键" width="90" class-name="text-muted-col" />
    </el-table>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button :loading="loading" @click="restoreDefault">恢复默认</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * Agent 键盘→手柄映射配置：按动作编辑键位，未配置时使用平台默认模板。
 */
import { computed, ref, watch } from 'vue'
import { agentApi } from '@/api'
import { ElMessage } from 'element-plus'

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

const loadMapping = async () => {
  if (!props.agentId) return
  loading.value = true
  try {
    const res = await agentApi.getKeyboardMapping(props.agentId)
    if (res.code === 0 || res.code === 200) {
      usingDefault.value = !!res.data?.usingDefault
      rows.value = (res.data?.rows || []).map((row) => ({ ...row }))
    } else {
      ElMessage.error(res.message || '加载键盘映射失败')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || '加载键盘映射失败')
  } finally {
    loading.value = false
  }
}

watch(() => props.agentId, () => {
  if (visible.value) loadMapping()
})

/** 在输入框聚焦时按一次键写入 pygame 键名 */
const captureKey = (event, row) => {
  const key = normalizeKeyName(event)
  if (key) {
    row.key = key
  }
}

const normalizeKeyName = (event) => {
  if (event.key === ' ') return 'space'
  if (event.key === 'Enter') return 'return'
  if (event.key === 'Escape') return 'escape'
  if (event.key && event.key.length === 1) return event.key.toLowerCase()
  const code = event.code || ''
  if (code.startsWith('Key')) return code.slice(3).toLowerCase()
  if (code.startsWith('Digit')) return code.slice(5)
  return event.key?.toLowerCase() || ''
}

const buildBindingsPayload = () => {
  const bindings = {}
  for (const row of rows.value) {
    const key = (row.key || '').trim().toLowerCase()
    if (!key) {
      throw new Error(`请为「${row.label}」设置按键`)
    }
    bindings[key] = row.action
  }
  return bindings
}

const handleSave = async () => {
  if (!props.agentId) return
  saving.value = true
  try {
    const bindings = buildBindingsPayload()
    const res = await agentApi.updateKeyboardMapping(props.agentId, { bindings })
    if (res.code === 0 || res.code === 200) {
      usingDefault.value = !!res.data?.usingDefault
      rows.value = (res.data?.rows || []).map((row) => ({ ...row }))
      ElMessage.success('键盘映射已保存，在线 Agent 将自动同步')
      emit('saved')
      visible.value = false
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
      usingDefault.value = true
      rows.value = (res.data?.rows || []).map((row) => ({ ...row }))
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

.default-tag {
  margin-bottom: var(--spacing-sm);
}

.mapping-table {
  margin-top: var(--spacing-sm);
}
</style>
