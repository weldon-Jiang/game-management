<template>
  <div v-loading="loading" class="chart-body">
    <div class="keyboard-wrap">
      <div class="keyboard-grid">
        <div
          v-for="slot in KEYBOARD_SLOTS"
          :key="slotDomKey(slot)"
          class="key-cap"
          :class="capClasses(slot.bindingKey)"
          :style="slotStyle(slot)"
        >
          <span class="cap-key">{{ capDisplay(slot.bindingKey) }}</span>
          <span v-if="capMapping(slot.bindingKey)" class="cap-target">
            {{ capMapping(slot.bindingKey) }}
          </span>
        </div>
      </div>
      <div class="arrow-cluster">
        <div class="cluster-title">方向键</div>
        <div class="arrow-grid">
          <div
            v-for="cell in ARROW_GRID_CELLS"
            :key="slotDomKey(cell)"
            class="key-cap key-cap--arrow"
            :class="cell.bindingKey ? capClasses(cell.bindingKey) : ['key-cap--spacer']"
            :style="arrowSlotStyle(cell)"
          >
            <template v-if="cell.bindingKey">
              <span class="cap-key">{{ capDisplay(cell.bindingKey) }}</span>
              <span v-if="capMapping(cell.bindingKey)" class="cap-target">
                {{ capMapping(cell.bindingKey) }}
              </span>
            </template>
          </div>
        </div>
      </div>
    </div>

    <div class="legend">
      <div v-for="group in groups" :key="group.category" class="legend-group">
        <div class="legend-head">
          <span class="legend-dot" :class="`legend-dot--${group.category}`" />
          <span class="legend-title">{{ group.label }}</span>
          <el-tag v-if="group.customizable" size="small" type="primary" effect="plain">可自定义</el-tag>
        </div>
        <div class="legend-items">
          <span
            v-for="(item, idx) in group.items"
            :key="`${group.category}-${idx}`"
            class="legend-item"
          >
            <kbd>{{ item.keys }}</kbd>
            <span class="legend-arrow">→</span>
            <span>{{ item.target }}</span>
          </span>
        </div>
      </div>
    </div>

    <div v-if="debugHotkeys.length" class="debug-hotkeys">
      <div class="debug-title">调试热键（非手柄映射）</div>
      <div class="debug-items">
        <span v-for="item in debugHotkeys" :key="item.key" class="debug-item">
          <kbd>{{ item.key }}</kbd> {{ item.description }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * F8 键盘映射可视化：键位图 + 分类图例（只读展示）。
 */
import { computed } from 'vue'
import {
  ARROW_GRID_CELLS,
  KEYBOARD_SLOTS,
  capDisplayKey,
  arrowSlotStyle,
  slotDomKey,
  slotStyle
} from '@/composables/useKeyboardMappingLayout'

const props = defineProps({
  loading: { type: Boolean, default: false },
  groups: { type: Array, default: () => [] },
  keyCaps: { type: Array, default: () => [] },
  debugHotkeys: { type: Array, default: () => [] }
})

const capMap = computed(() => {
  const map = {}
  for (const cap of props.keyCaps || []) {
    map[cap.bindingKey] = cap
  }
  return map
})

const capDisplay = (bindingKey) => {
  const cap = capMap.value[bindingKey]
  return cap?.displayKey || capDisplayKey(bindingKey)
}

const capMapping = (bindingKey) => capMap.value[bindingKey]?.targetLabel || ''

const capClasses = (bindingKey) => {
  const cap = capMap.value[bindingKey]
  if (!cap) return ['key-cap--idle']
  return [`key-cap--${cap.category}`, 'key-cap--mapped']
}
</script>

<style scoped>
.chart-body {
  min-height: 160px;
}

.keyboard-wrap {
  display: flex;
  gap: var(--spacing-lg);
  align-items: flex-start;
  margin-bottom: var(--spacing-xl);
}

.keyboard-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(16, 1fr);
  grid-template-rows: repeat(6, 38px);
  gap: 3px;
}

.arrow-cluster {
  flex-shrink: 0;
  width: 108px;
}

.cluster-title {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  margin-bottom: var(--spacing-xs);
  text-align: center;
}

.arrow-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-template-rows: repeat(3, 36px);
  gap: 4px;
}

.key-cap {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid var(--border-light);
  background: var(--bg-soft);
  padding: 2px 4px;
  min-height: 36px;
  overflow: hidden;
}

.key-cap--idle {
  opacity: 0.32;
}

.key-cap--spacer {
  visibility: hidden;
  pointer-events: none;
  border-color: transparent;
  background: transparent;
}

.key-cap--mapped {
  opacity: 1;
}

.cap-key {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
}

.cap-target {
  font-size: 10px;
  color: var(--text-secondary);
  line-height: 1.1;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.key-cap--left_stick.key-cap--mapped {
  border-color: var(--primary);
  background: var(--primary-soft);
}

.key-cap--face.key-cap--mapped {
  border-color: var(--success);
  background: var(--success-soft);
}

.key-cap--shoulder.key-cap--mapped {
  border-color: var(--info);
  background: var(--info-soft);
}

.key-cap--trigger.key-cap--mapped {
  border-color: var(--warning);
  background: var(--warning-soft);
}

.key-cap--right_stick.key-cap--mapped {
  border-color: #a855f7;
  background: rgba(168, 85, 247, 0.18);
}

.key-cap--stick_click.key-cap--mapped {
  border-color: #14b8a6;
  background: rgba(20, 184, 166, 0.18);
}

.key-cap--system.key-cap--mapped {
  border-color: var(--text-muted);
  background: rgba(107, 114, 128, 0.2);
}

.key-cap--dpad.key-cap--mapped {
  border-color: var(--warning);
  background: var(--warning-soft);
}

.legend {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  border-top: 1px solid var(--border-subtle);
  padding-top: var(--spacing-lg);
}

.legend-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.legend-head {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-dot--left_stick { background: var(--primary); }
.legend-dot--dpad { background: var(--warning); }
.legend-dot--face { background: var(--success); }
.legend-dot--shoulder { background: var(--info); }
.legend-dot--trigger { background: var(--warning); }
.legend-dot--right_stick { background: #a855f7; }
.legend-dot--stick_click { background: #14b8a6; }
.legend-dot--system { background: var(--text-muted); }

.legend-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm) var(--spacing-lg);
  padding-left: 16px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.legend-arrow {
  color: var(--text-muted);
}

.legend-item kbd,
.debug-item kbd {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
  background: var(--bg-secondary);
  font-family: var(--font-mono);
  font-size: var(--font-size-xs);
  color: var(--text-primary);
}

.debug-hotkeys {
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-subtle);
}

.debug-title {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
  margin-bottom: var(--spacing-sm);
}

.debug-items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-md);
}

.debug-item {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
