/**
 * 键盘映射行校验：重复键、动作次数限制。
 */
import { capDisplayKey } from '@/composables/useKeyboardMappingLayout'

/** 手柄目标展示：分组 + 目标，便于在冲突提示中快速定位。 */
export function formatMappingTarget(row) {
  const group = row?.groupLabel || '其他'
  const target = row?.label || row?.action || '未命名'
  return `${group} / ${target}`
}

/** 扫描重复键盘键，返回 [{ key, displayKey, targets }] */
export function findDuplicateKeyConflicts(rows) {
  const keyToTargets = new Map()
  for (const row of rows || []) {
    const key = (row.key || '').trim().toLowerCase()
    if (!key) continue
    if (!keyToTargets.has(key)) {
      keyToTargets.set(key, [])
    }
    keyToTargets.get(key).push(formatMappingTarget(row))
  }
  const conflicts = []
  for (const [key, targets] of keyToTargets) {
    if (targets.length > 1) {
      conflicts.push({
        key,
        displayKey: capDisplayKey(key),
        targets
      })
    }
  }
  return conflicts
}

/** 将重复键冲突格式化为可读提示。 */
export function formatDuplicateKeyMessage(conflicts) {
  if (!conflicts?.length) return ''
  if (conflicts.length === 1) {
    const { displayKey, targets } = conflicts[0]
    return `键盘键「${displayKey}」被以下 ${targets.length} 项重复使用：${targets.join('、')}`
  }
  return `存在重复键盘键：${conflicts
    .map(({ displayKey, targets }) => `「${displayKey}」→ ${targets.join('、')}`)
    .join('；')}`
}

/** 单行冲突提示（输入框下方）。 */
export function duplicateKeyHintForRow(rows, row) {
  const key = (row?.key || '').trim().toLowerCase()
  if (!key) return ''
  const self = formatMappingTarget(row)
  const conflict = findDuplicateKeyConflicts(rows).find((item) => item.key === key)
  if (!conflict) return ''
  const others = conflict.targets.filter((target) => target !== self)
  if (!others.length) return ''
  return `与 ${others.join('、')} 冲突`
}

/**
 * 校验映射行；失败返回 { ok: false, message }。
 */
export function validateKeyboardMappingRows(rows) {
  if (!rows?.length) {
    return { ok: true }
  }

  for (const row of rows) {
    const key = (row.key || '').trim().toLowerCase()
    if (!key) {
      return {
        ok: false,
        message: `请为「${formatMappingTarget(row)}」设置键盘按键`
      }
    }
  }

  const duplicateConflicts = findDuplicateKeyConflicts(rows)
  if (duplicateConflicts.length) {
    return {
      ok: false,
      message: formatDuplicateKeyMessage(duplicateConflicts)
    }
  }

  const actionOwners = {}
  const actionCounts = {}
  for (const row of rows) {
    const action = row.action
    const max = action?.startsWith('MOVE_') ? 2 : 1
    actionCounts[action] = (actionCounts[action] || 0) + 1
    if (!actionOwners[action]) {
      actionOwners[action] = []
    }
    actionOwners[action].push(formatMappingTarget(row))
    if (actionCounts[action] > max) {
      const targets = actionOwners[action]
      return {
        ok: false,
        message: max === 1
          ? `手柄功能被重复绑定：${targets.join('、')}，每个功能只能对应一个键盘键`
          : `方向功能「${action}」最多绑定 2 个键盘键，当前：${targets.join('、')}`
      }
    }
  }

  return { ok: true }
}

export function buildBindingsFromRows(rows) {
  const check = validateKeyboardMappingRows(rows)
  if (!check.ok) {
    throw new Error(check.message)
  }
  const bindings = {}
  for (const row of rows) {
    bindings[(row.key || '').trim().toLowerCase()] = row.action
  }
  return bindings
}
