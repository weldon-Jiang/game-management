/**
 * F8 键盘映射：按分组可选的 KeyAction（与 bend-platform AgentKeyboardMappingDefaults 对齐）。
 */
export const ACTION_OPTIONS_BY_CATEGORY = {
  left_stick: [
    { value: 'MOVE_UP', label: '左摇杆 ↑' },
    { value: 'MOVE_DOWN', label: '左摇杆 ↓' },
    { value: 'MOVE_LEFT', label: '左摇杆 ←' },
    { value: 'MOVE_RIGHT', label: '左摇杆 →' }
  ],
  dpad: [
    { value: 'MOVE_UP', label: '十字键 ↑' },
    { value: 'MOVE_DOWN', label: '十字键 ↓' },
    { value: 'MOVE_LEFT', label: '十字键 ←' },
    { value: 'MOVE_RIGHT', label: '十字键 →' }
  ],
  face: [
    { value: 'TAP_Y', label: 'Y' },
    { value: 'TAP_X', label: 'X' },
    { value: 'TAP_A', label: 'A' },
    { value: 'TAP_B', label: 'B' }
  ],
  shoulder: [
    { value: 'TAP_L1', label: 'LB' },
    { value: 'TAP_R1', label: 'RB' }
  ],
  trigger: [
    { value: 'HOLD_L2', label: 'LT 左扳机' },
    { value: 'HOLD_R2', label: 'RT 右扳机' }
  ],
  right_stick: [
    { value: 'LOOK_UP', label: '右摇杆 ↑' },
    { value: 'LOOK_DOWN', label: '右摇杆 ↓' },
    { value: 'LOOK_LEFT', label: '右摇杆 ←' },
    { value: 'LOOK_RIGHT', label: '右摇杆 →' }
  ],
  stick_click: [
    { value: 'TAP_L3', label: 'L3' },
    { value: 'TAP_R3', label: 'R3' }
  ],
  system: [
    { value: 'TAP_START', label: 'Start' },
    { value: 'TAP_SELECT', label: 'View' },
    { value: 'TAP_NEXUS', label: 'Xbox 键' }
  ]
}

export function actionOptionsForCategory(category) {
  return ACTION_OPTIONS_BY_CATEGORY[category] || []
}

export function actionLabelForCategory(category, action) {
  const opt = actionOptionsForCategory(category).find((item) => item.value === action)
  return opt?.label || action || ''
}

/** 浏览器按键 → pygame 键名 */
export function normalizeBrowserKeyName(event) {
  if (event.key === ' ') return 'space'
  if (event.key === 'Enter') return 'return'
  if (event.key === 'Escape') return 'escape'
  if (event.key === 'ArrowUp') return 'up'
  if (event.key === 'ArrowDown') return 'down'
  if (event.key === 'ArrowLeft') return 'left'
  if (event.key === 'ArrowRight') return 'right'
  if (event.key && event.key.length === 1) return event.key.toLowerCase()
  const code = event.code || ''
  if (code.startsWith('Key')) return code.slice(3).toLowerCase()
  if (code.startsWith('Digit')) return code.slice(5)
  if (code === 'ShiftLeft') return 'left shift'
  if (code === 'ShiftRight') return 'right shift'
  if (code === 'ControlLeft') return 'left ctrl'
  if (code === 'ControlRight') return 'right ctrl'
  return event.key?.toLowerCase() || ''
}
