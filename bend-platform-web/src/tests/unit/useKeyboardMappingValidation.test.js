import { describe, it, expect } from 'vitest'
import {
  validateKeyboardMappingRows,
  buildBindingsFromRows,
  formatDuplicateKeyMessage,
  findDuplicateKeyConflicts
} from '@/composables/useKeyboardMappingValidation'

describe('useKeyboardMappingValidation', () => {
  it('重复键盘键应列出全部冲突映射', () => {
    const rows = [
      { key: 'j', action: 'TAP_X', label: 'X', groupLabel: '面键 (Y/X/A/B)' },
      { key: 'j', action: 'MOVE_LEFT', label: '十字键 ←', groupLabel: '十字键 (方向键)' }
    ]
    const conflicts = findDuplicateKeyConflicts(rows)
    expect(conflicts).toHaveLength(1)
    expect(conflicts[0].targets).toEqual([
      '面键 (Y/X/A/B) / X',
      '十字键 (方向键) / 十字键 ←'
    ])

    const result = validateKeyboardMappingRows(rows)
    expect(result.ok).toBe(false)
    expect(result.message).toContain('J')
    expect(result.message).toContain('面键 (Y/X/A/B) / X')
    expect(result.message).toContain('十字键 (方向键) / 十字键 ←')
  })

  it('formatDuplicateKeyMessage 应包含全部冲突项', () => {
    const message = formatDuplicateKeyMessage([
      {
        displayKey: 'J',
        targets: ['面键 (Y/X/A/B) / X', '十字键 (方向键) / 十字键 ←']
      }
    ])
    expect(message).toBe(
      '键盘键「J」被以下 2 项重复使用：面键 (Y/X/A/B) / X、十字键 (方向键) / 十字键 ←'
    )
  })

  it('无冲突时应构建 bindings', () => {
    const rows = [
      { key: 'j', action: 'TAP_X', label: 'X', groupLabel: '面键 (Y/X/A/B)' },
      { key: 'left', action: 'MOVE_LEFT', label: '十字键 ←', groupLabel: '十字键 (方向键)' }
    ]
    expect(buildBindingsFromRows(rows)).toEqual({
      j: 'TAP_X',
      left: 'MOVE_LEFT'
    })
  })
})
