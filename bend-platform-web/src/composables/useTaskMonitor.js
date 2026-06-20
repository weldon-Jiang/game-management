import { ref, onUnmounted, unref, watch } from 'vue'
import { taskApi } from '@/api/task'
import { subscribeToTopic } from '@/utils/stompClient'
import { isRequestCanceled } from '@/utils/request'
import { getEffectiveTaskStatus } from '@/utils/constants'

/**
 * Monitor a task detail page with WebSocket push plus polling fallback.
 *
 * WebSocket progress updates are fast but not guaranteed during reconnects, so
 * polling remains the source of truth and also reloads the event timeline.
 */
export function useTaskMonitor(taskIdRef, sessionIdRef = null) {
  const detail = ref(null)
  const events = ref([])
  const loading = ref(false)
  let pollTimer = null
  let wsSubscription = null
  let refreshTimer = null

  const refreshCore = async () => {
    const id = unref(taskIdRef)
    if (!id) return
    loading.value = true
    try {
      const sessionId = unref(sessionIdRef)
      const eventParams = { limit: 50 }
      // Session filter lets the detail page inspect old automation rounds without mixing event timelines.
      if (sessionId) eventParams.sessionId = sessionId
      const [detailRes, eventsRes] = await Promise.all([
        taskApi.getDetail(id),
        taskApi.getEvents(id, eventParams).catch(() => ({ data: [] }))
      ])
      detail.value = detailRes.data
      events.value = eventsRes.data || []
    } catch (e) {
      if (!isRequestCanceled(e)) {
        console.warn('Task detail refresh failed:', e)
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * 刷新详情与事件流。WS 推送与 session 切换会短时间连发，debounce 避免同 URL 去重取消导致首屏永远加载不出。
   *
   * @param {{ immediate?: boolean, debounceMs?: number }} [options]
   */
  const refresh = (options = {}) => {
    const { immediate = false, debounceMs = 0 } = options
    if (immediate || debounceMs <= 0) {
      if (refreshTimer) {
        clearTimeout(refreshTimer)
        refreshTimer = null
      }
      return refreshCore()
    }
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      refreshTimer = null
      refreshCore()
    }, debounceMs)
  }

  const applyProgressPatch = (payload) => {
    if (!detail.value?.task || !payload?.taskId) return
    const id = unref(taskIdRef)
    if (payload.taskId !== id) return

    // Patch only volatile fields immediately; full detail is reloaded right after to avoid stale derived state.
    if (payload.sessionPhase || payload.phase) {
      detail.value.task.sessionPhase = payload.sessionPhase || payload.phase
      const effective = getEffectiveTaskStatus(detail.value.task)
      if (effective && effective !== detail.value.task.status) {
        detail.value.task.status = effective
      }
    }
    if (payload.message) {
      detail.value.lastProgressMessage = payload.message
    }
    if (payload.status === 'FAILED') {
      detail.value.task.status = 'failed'
    } else if (payload.status === 'RUNNING') {
      const effective = getEffectiveTaskStatus(detail.value.task)
      if (effective === 'running' && detail.value.task.status !== 'running') {
        detail.value.task.status = 'running'
      }
    }
  }

  const startWs = async () => {
    try {
      wsSubscription = await subscribeToTopic('/topic/admins/task_progress', (payload) => {
        const id = unref(taskIdRef)
        if (payload?.taskId === id) {
          applyProgressPatch(payload)
          refresh({ debounceMs: 600 })
        }
      })
    } catch (e) {
      console.warn('Task progress WS unavailable, polling only', e)
    }
  }

  const stopWs = () => {
    if (wsSubscription?.unsubscribe) {
      wsSubscription.unsubscribe()
      wsSubscription = null
    }
  }

  const startPolling = (intervalMs = 8000) => {
    // Start with an immediate refresh so the page has data before the first interval tick.
    refresh({ immediate: true })
    pollTimer = setInterval(() => refresh({ immediate: true }), intervalMs)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    if (refreshTimer) {
      clearTimeout(refreshTimer)
      refreshTimer = null
    }
  }

  const startMonitor = (intervalMs = 8000) => {
    startPolling(intervalMs)
    startWs()
  }

  const stopMonitor = () => {
    stopPolling()
    stopWs()
  }

  watch(
    () => unref(taskIdRef),
    (id) => {
      // Route changes can reuse the same component instance; restart subscriptions for the new taskId.
      stopMonitor()
      if (id) startMonitor()
    }
  )

  if (sessionIdRef) {
    watch(
      () => unref(sessionIdRef),
      // Session switch only needs a reload; the WS topic remains task-scoped.
      () => refresh({ debounceMs: 200 })
    )
  }

  onUnmounted(stopMonitor)

  return {
    detail,
    events,
    loading,
    refresh,
    startPolling,
    stopPolling,
    startMonitor,
    stopMonitor
  }
}
