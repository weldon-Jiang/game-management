import { ref, onUnmounted, unref, watch } from 'vue'
import { taskApi } from '@/api/task'
import { subscribeToTopic } from '@/utils/stompClient'

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

  const refresh = async () => {
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
    } finally {
      loading.value = false
    }
  }

  const applyProgressPatch = (payload) => {
    if (!detail.value?.task || !payload?.taskId) return
    const id = unref(taskIdRef)
    if (payload.taskId !== id) return

    // Patch only volatile fields immediately; full detail is reloaded right after to avoid stale derived state.
    if (payload.sessionPhase || payload.phase) {
      detail.value.task.sessionPhase = payload.sessionPhase || payload.phase
    }
    if (payload.message) {
      detail.value.lastProgressMessage = payload.message
    }
    if (payload.status === 'FAILED') {
      detail.value.task.status = 'failed'
    }
  }

  const startWs = async () => {
    try {
      wsSubscription = await subscribeToTopic('/topic/admins/task_progress', (payload) => {
        const id = unref(taskIdRef)
        if (payload?.taskId === id) {
          applyProgressPatch(payload)
          refresh()
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
    refresh()
    pollTimer = setInterval(refresh, intervalMs)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
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
      () => refresh()
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
