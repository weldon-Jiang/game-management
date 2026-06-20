/**
 * F8 键盘映射图：全量 ANSI 主键盘 + 方向键区（bindingKey 对齐 pygame 键名）。
 * 已映射键由 keyCaps 高亮；未出现在 keyCaps 中的键显示为 idle。
 */

export const KEYBOARD_GRID_ROWS = 6
export const KEYBOARD_GRID_COLS = 16

/** 主键盘全部键位 */
export const KEYBOARD_SLOTS = [
  { bindingKey: 'escape', row: 1, col: 1, colSpan: 2 },

  { bindingKey: '`', row: 2, col: 1 },
  { bindingKey: '1', row: 2, col: 2 },
  { bindingKey: '2', row: 2, col: 3 },
  { bindingKey: '3', row: 2, col: 4 },
  { bindingKey: '4', row: 2, col: 5 },
  { bindingKey: '5', row: 2, col: 6 },
  { bindingKey: '6', row: 2, col: 7 },
  { bindingKey: '7', row: 2, col: 8 },
  { bindingKey: '8', row: 2, col: 9 },
  { bindingKey: '9', row: 2, col: 10 },
  { bindingKey: '0', row: 2, col: 11 },
  { bindingKey: '-', row: 2, col: 12 },
  { bindingKey: '=', row: 2, col: 13 },
  { bindingKey: 'backspace', row: 2, col: 14, colSpan: 3 },

  { bindingKey: 'tab', row: 3, col: 1, colSpan: 2 },
  { bindingKey: 'q', row: 3, col: 3 },
  { bindingKey: 'w', row: 3, col: 4 },
  { bindingKey: 'e', row: 3, col: 5 },
  { bindingKey: 'r', row: 3, col: 6 },
  { bindingKey: 't', row: 3, col: 7 },
  { bindingKey: 'y', row: 3, col: 8 },
  { bindingKey: 'u', row: 3, col: 9 },
  { bindingKey: 'i', row: 3, col: 10 },
  { bindingKey: 'o', row: 3, col: 11 },
  { bindingKey: 'p', row: 3, col: 12 },
  { bindingKey: '[', row: 3, col: 13 },
  { bindingKey: ']', row: 3, col: 14 },
  { bindingKey: '\\', row: 3, col: 15, colSpan: 2 },

  { bindingKey: 'caps lock', row: 4, col: 1, colSpan: 2 },
  { bindingKey: 'a', row: 4, col: 3 },
  { bindingKey: 's', row: 4, col: 4 },
  { bindingKey: 'd', row: 4, col: 5 },
  { bindingKey: 'f', row: 4, col: 6 },
  { bindingKey: 'g', row: 4, col: 7 },
  { bindingKey: 'h', row: 4, col: 8 },
  { bindingKey: 'j', row: 4, col: 9 },
  { bindingKey: 'k', row: 4, col: 10 },
  { bindingKey: 'l', row: 4, col: 11 },
  { bindingKey: ';', row: 4, col: 12 },
  { bindingKey: "'", row: 4, col: 13 },
  { bindingKey: 'return', row: 4, col: 14, colSpan: 3 },

  { bindingKey: 'left shift', row: 5, col: 1, colSpan: 2 },
  { bindingKey: 'z', row: 5, col: 3 },
  { bindingKey: 'x', row: 5, col: 4 },
  { bindingKey: 'c', row: 5, col: 5 },
  { bindingKey: 'v', row: 5, col: 6 },
  { bindingKey: 'b', row: 5, col: 7 },
  { bindingKey: 'n', row: 5, col: 8 },
  { bindingKey: 'm', row: 5, col: 9 },
  { bindingKey: ',', row: 5, col: 10 },
  { bindingKey: '.', row: 5, col: 11 },
  { bindingKey: '/', row: 5, col: 12 },
  { bindingKey: 'right shift', row: 5, col: 13, colSpan: 4 },

  { bindingKey: 'left ctrl', row: 6, col: 1, colSpan: 2 },
  { bindingKey: 'left meta', row: 6, col: 3 },
  { bindingKey: 'left alt', row: 6, col: 4 },
  { bindingKey: 'space', row: 6, col: 5, colSpan: 6 },
  { bindingKey: 'right alt', row: 6, col: 11 },
  { bindingKey: 'right meta', row: 6, col: 12 },
  { bindingKey: 'right ctrl', row: 6, col: 13, colSpan: 4 }
]

/** 方向键 3×3（空白格占位，保持十字布局） */
export const ARROW_GRID_CELLS = [
  { row: 1, col: 1, bindingKey: null },
  { row: 1, col: 2, bindingKey: 'up' },
  { row: 1, col: 3, bindingKey: null },
  { row: 2, col: 1, bindingKey: 'left' },
  { row: 2, col: 2, bindingKey: 'down' },
  { row: 2, col: 3, bindingKey: 'right' },
  { row: 3, col: 1, bindingKey: null },
  { row: 3, col: 2, bindingKey: null },
  { row: 3, col: 3, bindingKey: null }
]

/** @deprecated 使用 ARROW_GRID_CELLS */
export const ARROW_SLOTS = ARROW_GRID_CELLS.filter((cell) => cell.bindingKey)

const DISPLAY_FALLBACK = {
  escape: 'Esc',
  return: 'Enter',
  space: 'Space',
  'left shift': 'Shift',
  'right shift': 'Shift',
  'left ctrl': 'Ctrl',
  'right ctrl': 'Ctrl',
  'left alt': 'Alt',
  'right alt': 'Alt',
  'left meta': 'Win',
  'right meta': 'Win',
  'caps lock': 'Caps',
  backspace: 'Back',
  tab: 'Tab',
  up: '↑',
  down: '↓',
  left: '←',
  right: '→',
  '`': '`',
  '-': '-',
  '=': '=',
  '[': '[',
  ']': ']',
  '\\': '\\',
  ';': ';',
  "'": "'",
  ',': ',',
  '.': '.',
  '/': '/'
}

export function capDisplayKey(bindingKey) {
  if (!bindingKey) return ''
  if (DISPLAY_FALLBACK[bindingKey]) return DISPLAY_FALLBACK[bindingKey]
  return bindingKey.length === 1 ? bindingKey.toUpperCase() : bindingKey
}

export function slotStyle(slot) {
  const span = Math.max(1, Math.ceil(slot.colSpan || 1))
  return {
    gridRow: slot.row,
    gridColumn: `${slot.col} / span ${span}`
  }
}

export function arrowSlotStyle(slot) {
  return {
    gridRow: slot.row,
    gridColumn: slot.col
  }
}

export function slotDomKey(slot) {
  return `${slot.row}-${slot.col}-${slot.bindingKey || 'spacer'}`
}
