<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>系统监控</h2>
        <p class="header-desc">平台运行资源与最近趋势，仅平台管理员可见</p>
      </div>
      <div class="header-actions">
        <el-switch
          v-model="autoRefresh"
          active-text="60秒刷新"
          inactive-text="手动刷新"
          @change="handleAutoRefreshChange"
        />
        <el-button type="primary" :loading="loading" @click="loadOverview">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="overview.cacheSeconds"
      class="cache-tip"
      :closable="false"
      type="info"
      show-icon
      :title="`后端总览数据缓存 ${overview.cacheSeconds} 秒，避免频繁刷新造成额外查询压力。`"
    />

    <div class="metric-grid">
      <div class="metric-card">
        <span class="metric-label">JVM 内存</span>
        <strong>{{ formatPercent(overview.jvm?.memoryUsagePercent) }}</strong>
        <el-progress
          :percentage="clampPercent(overview.jvm?.memoryUsagePercent)"
          :stroke-width="8"
          :show-text="false"
        />
        <span class="metric-desc">{{ overview.jvm?.usedMemory || '-' }} / {{ overview.jvm?.totalMemory || '-' }}</span>
      </div>

      <div class="metric-card">
        <span class="metric-label">系统内存</span>
        <strong>{{ formatPercent(overview.system?.memoryUsagePercent) }}</strong>
        <el-progress
          :percentage="clampPercent(overview.system?.memoryUsagePercent)"
          :stroke-width="8"
          :show-text="false"
        />
        <span class="metric-desc">{{ overview.system?.freeMemory || '-' }} 可用</span>
      </div>

      <div class="metric-card">
        <span class="metric-label">系统负载</span>
        <strong>{{ formatNumber(overview.system?.cpuUsagePercent) }}</strong>
        <span class="metric-desc">{{ overview.system?.cpuCoreCount || 0 }} 核 CPU</span>
      </div>

      <div class="metric-card">
        <span class="metric-label">API 成功率</span>
        <strong>{{ formatPercent(overview.business?.successRate) }}</strong>
        <span class="metric-desc">
          {{ overview.business?.successRequests || 0 }} 成功 /
          {{ overview.business?.failedRequests || 0 }} 失败
        </span>
      </div>
    </div>

    <el-row :gutter="16" class="content-row">
      <el-col :span="12">
        <div class="content-card">
          <div class="section-title">
            <h3>运行环境</h3>
            <span>{{ formatDateTime(overview.collectedTime) }}</span>
          </div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="主机名">{{ overview.system?.hostName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="主机 IP">{{ overview.system?.hostIp || '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作系统">{{ overview.system?.osName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="Java 版本">{{ overview.jvm?.javaVersion || '-' }}</el-descriptions-item>
            <el-descriptions-item label="运行时长">{{ formatDuration(overview.jvm?.uptime) }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>

      <el-col :span="12">
        <div class="content-card">
          <div class="section-title">
            <h3>请求统计</h3>
            <span>进程内计数</span>
          </div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="总请求">{{ overview.business?.totalRequests || 0 }}</el-descriptions-item>
            <el-descriptions-item label="成功请求">{{ overview.business?.successRequests || 0 }}</el-descriptions-item>
            <el-descriptions-item label="失败请求">{{ overview.business?.failedRequests || 0 }}</el-descriptions-item>
            <el-descriptions-item label="成功率">{{ formatPercent(overview.business?.successRate) }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
    </el-row>

    <div class="content-card trend-card">
      <div class="section-title">
        <h3>最近一小时趋势</h3>
        <span>最多 60 个采样点</span>
      </div>
      <div class="trend-grid">
        <div
          v-for="item in trendItems"
          :key="item.key"
          class="trend-item"
        >
          <div class="trend-header">
            <span>{{ item.label }}</span>
            <strong>{{ latestTrendValue(item.points) }}</strong>
          </div>
          <div v-if="item.points.length" class="sparkline">
            <span
              v-for="(point, index) in item.points"
              :key="`${item.key}-${index}`"
              class="sparkline-bar"
              :style="{ height: `${sparkHeight(point.value)}%` }"
              :title="`${formatDateTime(point.time)} ${formatNumber(point.value)}${point.unit || ''}`"
            />
          </div>
          <el-empty v-else description="暂无趋势数据" :image-size="56" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { monitoringApi } from '@/api'

const loading = ref(false)
const autoRefresh = ref(false)
const overview = ref({})
let refreshTimer = null

/** 将后端 trends 映射为页面展示的三条 sparkline 序列。 */
const trendItems = computed(() => {
  const trends = overview.value.trends || {}
  return [
    { key: 'jvm_memory_usage_percent', label: 'JVM 内存使用率', points: trends.jvm_memory_usage_percent || [] },
    { key: 'system_cpu_usage_percent', label: '系统负载', points: trends.system_cpu_usage_percent || [] },
    { key: 'system_memory_usage_percent', label: '系统内存使用率', points: trends.system_memory_usage_percent || [] }
  ]
})

/** 拉取平台管理员总览；后端有 60s 缓存，频繁手动刷新不会每次都打满指标查询。 */
const loadOverview = async () => {
  loading.value = true
  try {
    const res = await monitoringApi.getOverview()
    if (res.code === 0 || res.code === 200) {
      overview.value = res.data || {}
    }
  } catch (error) {
    console.error('Failed to load monitoring overview:', error)
    ElMessage.error('加载系统监控失败')
  } finally {
    loading.value = false
  }
}

const handleAutoRefreshChange = () => {
  clearRefreshTimer()
  if (autoRefresh.value) {
    // 与后端 overview 缓存周期对齐，避免无意义的高频请求。
    refreshTimer = window.setInterval(loadOverview, 60000)
  }
}

const clearRefreshTimer = () => {
  if (refreshTimer) {
    window.clearInterval(refreshTimer)
    refreshTimer = null
  }
}

/** 进度条与 sparkline 高度共用，防止异常采样值撑破 UI。 */
const clampPercent = (value) => Math.max(0, Math.min(100, Number(value) || 0))

const formatPercent = (value) => {
  if (value === undefined || value === null) return '-'
  return `${formatNumber(value)}%`
}

const formatNumber = (value) => {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toFixed(2)
}

const formatDateTime = (value) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

const formatDuration = (value) => {
  const millis = Number(value)
  if (!Number.isFinite(millis)) return '-'
  const totalSeconds = Math.floor(millis / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  return `${days}天 ${hours}小时 ${minutes}分钟`
}

const sparkHeight = (value) => Math.max(6, clampPercent(value))

const latestTrendValue = (points) => {
  if (!points.length) return '-'
  const latest = points[points.length - 1]
  return `${formatNumber(latest.value)}${latest.unit || ''}`
}

onMounted(loadOverview)

onUnmounted(() => {
  clearRefreshTimer()
})
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.cache-tip {
  margin-bottom: var(--spacing-xl);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  min-height: 150px;
  padding: var(--spacing-xl);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
}

.metric-label {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

.metric-card strong {
  font-size: var(--font-size-2xl);
  color: var(--text-primary);
}

.metric-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.content-row {
  margin-bottom: var(--spacing-xl);
}

.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.section-title h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}

.section-title span {
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

.trend-card {
  margin-bottom: var(--spacing-xl);
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--spacing-lg);
}

.trend-item {
  padding: var(--spacing-lg);
  background: var(--bg-soft);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}

.trend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  color: var(--text-secondary);
}

.trend-header strong {
  color: var(--text-primary);
}

.sparkline {
  display: flex;
  align-items: end;
  gap: 2px;
  height: 120px;
}

.sparkline-bar {
  flex: 1;
  min-width: 2px;
  background: var(--primary-gradient);
  border-radius: var(--radius-sm) var(--radius-sm) 0 0;
}
</style>
