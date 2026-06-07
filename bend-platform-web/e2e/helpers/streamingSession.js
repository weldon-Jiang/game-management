/**
 * E2E helpers for streaming-session/task-reuse flows.
 *
 * Provides:
 *  - injectAuth(page): bypass login by writing token+user into localStorage.
 *  - mockTaskBackend(page, state): intercept platform/gateway APIs and return
 *    deterministic data so we can drive UI through scenarios without a live agent.
 *
 * Mocked endpoints cover:
 *   GET  /api/tasks/:id/detail
 *   GET  /api/tasks/:id/events
 *   GET  /api/tasks/:id/sessions
 *   POST /api/tasks/:id/start-automation
 *   POST /api/tasks/:id/terminate
 *   POST /api/tasks/:id/reconnect-stream
 *   POST /api/tasks/:id/window/show
 *   POST /api/streaming-accounts/:sid/tasks/start-streaming
 *   GET  /api/streaming-accounts/page
 *   GET  /api/agents/online
 *   GET  /api/subscriptions/status
 *   POST /api/subscriptions/validate-automation-request
 *   GET  /api/game-accounts/page
 *   GET  /api/xbox-hosts/page
 *
 * Each scenario adapts state by reaching into `state` and triggering route refresh.
 */

const ok = (data) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 200, message: 'success', data })
})

export const FAKE_TOKEN = 'e2e-fake-token'
export const FAKE_USER = {
  userId: 'u-e2e',
  username: 'e2e-tester',
  merchantId: 'm-e2e',
  role: 'merchant_owner'
}

const STREAMING_ACCOUNT_ID = 'sa-e2e-001'
const GAME_ACCOUNT_ID = 'ga-e2e-001'
const AGENT_ID = 'AGENT-E2E-001'
const TASK_ID = 'task-e2e-001'

export const ids = {
  STREAMING_ACCOUNT_ID,
  GAME_ACCOUNT_ID,
  AGENT_ID,
  TASK_ID
}

const baseTask = () => ({
  id: TASK_ID,
  name: 'E2E 串流任务',
  status: 'running',
  sessionPhase: 'ready',
  sessionId: 'sess-1',
  streamingAccountId: STREAMING_ACCOUNT_ID,
  streamingAccountName: 'jwdong@example.com',
  targetAgentId: AGENT_ID,
  targetAgentName: 'AGENT-E2E-001',
  gameActionType: '',
  gameActionPending: true,
  pauseMode: '',
  windowVisible: true,
  errorMessage: null,
  createdTime: '2026-06-07T10:00:00'
})

const baseSession = (id, phase, startedAt, gameActionType = '') => ({
  id,
  taskId: TASK_ID,
  phase,
  gameActionType,
  startedTime: startedAt,
  errorMessage: null
})

/**
 * Inject auth into localStorage so router guard skips Login.
 */
export async function injectAuth(page) {
  await page.addInitScript(
    ({ token, user }) => {
      window.localStorage.setItem('token', token)
      window.localStorage.setItem('user', JSON.stringify(user))
      window.localStorage.setItem(
        'token_expiry',
        String(Math.floor(Date.now() / 1000) + 86400)
      )
    },
    { token: FAKE_TOKEN, user: FAKE_USER }
  )
}

/**
 * Build a stateful mocked backend bound to `page.route`. The returned
 * controller exposes mutators so each scenario can drive task transitions.
 */
export async function mockTaskBackend(page) {
  const state = {
    task: baseTask(),
    session: baseSession('sess-1', 'ready', '2026-06-07T10:00:00'),
    sessions: [baseSession('sess-1', 'ready', '2026-06-07T10:00:00')],
    eventsBySession: {
      'sess-1': [
        {
          id: 'ev-1-1',
          taskId: TASK_ID,
          sessionId: 'sess-1',
          scope: 'session',
          phase: 'ready',
          status: 'RUNNING',
          message: '串流就绪，等待选择自动化模式',
          createdTime: '2026-06-07T10:01:00'
        }
      ]
    },
    gameAccountStatuses: [
      {
        gameAccountId: GAME_ACCOUNT_ID,
        gameName: 'jwdong-ga',
        status: 'pending',
        phase: 'ready',
        matchIndex: 0,
        matchTotal: 5,
        completedCount: 0
      }
    ],
    lastProgressMessage: '串流就绪，等待选择自动化模式',
    apiCalls: []
  }

  const recordCall = (method, url) => state.apiCalls.push({ method, url })

  await page.route('**/api/auth/login', async (route) => {
    recordCall('POST', route.request().url())
    await route.fulfill(
      ok({
        token: FAKE_TOKEN,
        userId: FAKE_USER.userId,
        username: FAKE_USER.username,
        merchantId: FAKE_USER.merchantId,
        role: FAKE_USER.role
      })
    )
  })

  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill(ok(FAKE_USER))
  })

  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill(
      ok({
        token: FAKE_TOKEN,
        userId: FAKE_USER.userId,
        username: FAKE_USER.username,
        merchantId: FAKE_USER.merchantId,
        role: FAKE_USER.role
      })
    )
  })

  // Streaming account list (used on /streaming-accounts page).
  await page.route('**/api/streaming-accounts/page**', async (route) => {
    recordCall('GET', route.request().url())
    await route.fulfill(
      ok({
        records: [
          {
            id: STREAMING_ACCOUNT_ID,
            email: 'jwdong@example.com',
            platform: 'xbox',
            status: state.task.status === 'running' || state.task.status === 'paused' ? 'busy' : 'idle',
            taskStatus: state.task.status === 'running' || state.task.status === 'paused' ? 'busy' : 'idle',
            agentId: state.task.status === 'running' ? AGENT_ID : null,
            agentName: 'AGENT-E2E-001',
            merchantId: FAKE_USER.merchantId,
            createdTime: '2026-06-01T08:00:00'
          }
        ],
        total: 1
      })
    )
  })

  await page.route('**/api/agents/online', async (route) => {
    await route.fulfill(
      ok([
        {
          agentId: AGENT_ID,
          agentName: 'AGENT-E2E-001',
          status: 'online',
          merchantName: 'E2E Merchant'
        }
      ])
    )
  })

  await page.route('**/api/agents/page**', async (route) => {
    await route.fulfill(
      ok({
        records: [
          {
            agentId: AGENT_ID,
            agentName: 'AGENT-E2E-001',
            status: 'online',
            merchantName: 'E2E Merchant'
          }
        ],
        total: 1
      })
    )
  })

  await page.route('**/api/subscriptions/status', async (route) => {
    await route.fulfill(
      ok({
        currentSubscription: { id: 'sub-1', planName: 'E2E' },
        balance: 99999
      })
    )
  })

  await page.route('**/api/subscriptions/validate-automation-request', async (route) => {
    await route.fulfill(ok({ canStart: true, errors: [] }))
  })

  await page.route('**/api/game-accounts/page**', async (route) => {
    const url = new URL(route.request().url())
    const streamingId = url.searchParams.get('streamingId')
    if (streamingId === STREAMING_ACCOUNT_ID) {
      await route.fulfill(
        ok({
          records: [
            {
              id: GAME_ACCOUNT_ID,
              email: 'jwdong-ga@example.com',
              gameName: 'jwdong-ga',
              streamingId: STREAMING_ACCOUNT_ID,
              positionIndex: 0
            }
          ],
          total: 1
        })
      )
    } else {
      await route.fulfill(ok({ records: [], total: 0 }))
    }
  })

  await page.route('**/api/xbox-hosts/page**', async (route) => {
    await route.fulfill(ok({ records: [], total: 0 }))
  })

  await page.route('**/api/merchants/all', async (route) => {
    await route.fulfill(ok([]))
  })

  // ---- Task detail / events / sessions ----
  // 注意：前端 request.js 有 pendingRequests 自动取消机制，相同 URL 的并发请求会互相取消。
  // 给 detail 路径加一个微延迟，避免 onMounted 的 loadSessions 与 watch(currentSessionId)
  // 二次触发的 loadSessions 形成并发竞争（导致 sessions 永远为空）。
  await page.route(`**/api/tasks/${TASK_ID}/detail`, async (route) => {
    recordCall('GET', route.request().url())
    await new Promise((r) => setTimeout(r, 250))
    await route.fulfill(
      ok({
        task: { ...state.task },
        session: state.session ? { ...state.session } : null,
        gameAccountStatuses: [...state.gameAccountStatuses],
        lastProgressMessage: state.lastProgressMessage
      })
    )
  })

  await page.route(`**/api/tasks/${TASK_ID}/events**`, async (route) => {
    const url = new URL(route.request().url())
    const sessionId = url.searchParams.get('sessionId')
    recordCall('GET', route.request().url())
    await new Promise((r) => setTimeout(r, 250))
    const events = sessionId
      ? state.eventsBySession[sessionId] || []
      : Object.values(state.eventsBySession).flat()
    await route.fulfill(ok([...events].reverse()))
  })

  await page.route(`**/api/tasks/${TASK_ID}/sessions`, async (route) => {
    recordCall('GET', route.request().url())
    // 最近一次在前
    const sorted = [...state.sessions].sort((a, b) =>
      String(b.startedTime).localeCompare(String(a.startedTime))
    )
    await route.fulfill(ok(sorted))
  })

  await page.route(`**/api/tasks/${TASK_ID}/start-automation`, async (route) => {
    recordCall('POST', route.request().url())
    state.task.gameActionType = 'squad_battle'
    state.task.gameActionPending = false
    state.task.sessionPhase = 'automating'
    if (state.session) state.session.phase = 'automating'
    await route.fulfill(ok({ taskId: TASK_ID }))
  })

  await page.route(`**/api/tasks/${TASK_ID}/terminate`, async (route) => {
    recordCall('POST', route.request().url())
    state.task.status = 'terminated'
    state.task.sessionPhase = 'closed'
    if (state.session) state.session.phase = 'closed'
    await route.fulfill(ok({ taskId: TASK_ID }))
  })

  await page.route(`**/api/tasks/${TASK_ID}/reconnect-stream`, async (route) => {
    recordCall('POST', route.request().url())
    await route.fulfill(ok({ taskId: TASK_ID }))
  })

  await page.route(`**/api/tasks/${TASK_ID}/window/show`, async (route) => {
    recordCall('POST', route.request().url())
    state.task.windowVisible = true
    await route.fulfill(ok({ taskId: TASK_ID }))
  })

  await page.route(
    `**/api/streaming-accounts/${STREAMING_ACCOUNT_ID}/tasks/start-streaming`,
    async (route) => {
      recordCall('POST', route.request().url())
      // 触发任务复用：保持 TASK_ID，但生成新的 session
      const reused = state.sessions.length > 0
      const newSessionId = `sess-${state.sessions.length + 1}`
      const startedAt = new Date().toISOString().slice(0, 19)
      const newSession = baseSession(newSessionId, 'opening', startedAt)
      state.sessions = [...state.sessions, newSession]
      state.session = newSession
      state.task = {
        ...baseTask(),
        sessionId: newSessionId,
        sessionPhase: 'opening',
        gameActionPending: false
      }
      state.eventsBySession[newSessionId] = [
        {
          id: `ev-${newSessionId}-1`,
          taskId: TASK_ID,
          sessionId: newSessionId,
          scope: 'session',
          phase: 'opening',
          status: 'RUNNING',
          message: '新会话启动中',
          createdTime: startedAt
        }
      ]
      await route.fulfill(
        ok({
          taskId: TASK_ID,
          reused,
          sessionId: newSessionId
        })
      )
    }
  )

  // ---- Mutators exposed to tests ----
  const ctrl = {
    state,
    setSessionPhase(phase, { keepStatus = true } = {}) {
      state.task.sessionPhase = phase
      if (state.session) state.session.phase = phase
      if (phase === 'automation_failed') {
        state.task.gameActionPending = true
        if (keepStatus) state.task.status = 'running'
        state.lastProgressMessage = 'Step4 自动化失败，串流保持，可重试'
        const sid = state.task.sessionId
        if (!state.eventsBySession[sid]) state.eventsBySession[sid] = []
        state.eventsBySession[sid].push({
          id: `ev-${sid}-fail-${Date.now()}`,
          taskId: TASK_ID,
          sessionId: sid,
          scope: 'session',
          phase: 'automation_failed',
          status: 'FAILED',
          message: 'Step4 自动化失败，串流保持，可重试',
          createdTime: new Date().toISOString().slice(0, 19)
        })
      }
    },
    setStatus(s) {
      state.task.status = s
    },
    addHistorySession(id, phase, startedAt) {
      const s = baseSession(id, phase, startedAt)
      state.sessions = [...state.sessions, s]
      state.eventsBySession[id] = [
        {
          id: `ev-${id}-1`,
          taskId: TASK_ID,
          sessionId: id,
          scope: 'session',
          phase,
          status: phase === 'closed' ? 'COMPLETED' : 'RUNNING',
          message: `历史会话 ${id} 事件`,
          createdTime: startedAt
        }
      ]
    },
    /** Promote a specific session id to "current". */
    setCurrentSession(id) {
      const found = state.sessions.find((s) => s.id === id)
      if (!found) throw new Error(`session ${id} not in state`)
      state.session = { ...found }
      state.task.sessionId = id
      state.task.sessionPhase = found.phase
    }
  }

  return ctrl
}

/**
 * Wait until an API request matching the predicate has been recorded.
 */
export async function waitForApiCall(state, predicate, timeoutMs = 5000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (state.apiCalls.some(predicate)) return true
    await new Promise((r) => setTimeout(r, 100))
  }
  return false
}
