/**
 * Shared E2E auth helpers — inject localStorage token and mock list APIs
 * so UI specs run in CI without a live gateway/backend.
 */

import { injectAuth, FAKE_TOKEN, FAKE_USER } from './streamingSession.js'

export { injectAuth, FAKE_TOKEN, FAKE_USER }

export const LOGIN_KEY_SELECTOR = 'input[placeholder="请输入账号或手机号"]'
export const PASSWORD_SELECTOR = 'input[placeholder="请输入密码"]'

const ok = (data) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 200, message: 'success', data })
})

const MOCK_AGENT = {
  agentId: 'AGENT-E2E-001',
  agentName: 'E2E Agent',
  host: '127.0.0.1',
  port: 9000,
  status: 'online',
  version: '1.0.0',
  lastHeartbeat: '2026-06-09T10:00:00',
  merchantId: 'm-e2e',
  merchantName: 'E2E Merchant'
}

const MOCK_TASK = {
  id: 'task-e2e-001',
  name: 'E2E 任务',
  type: 'stream_control',
  status: 'running',
  sessionPhase: 'ready',
  streamingAccountName: 'stream@example.com',
  targetAgentId: 'AGENT-E2E-001',
  createdTime: '2026-06-09T10:00:00'
}

/**
 * Mock auth refresh/me and common list endpoints used by layout + list pages.
 */
export async function mockCommonApis(page) {
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

  await page.route('**/api/agents/page**', async (route) => {
    await route.fulfill(ok({ records: [MOCK_AGENT], total: 1 }))
  })

  await page.route('**/api/agents/online', async (route) => {
    await route.fulfill(ok([MOCK_AGENT]))
  })

  await page.route('**/api/tasks/page**', async (route) => {
    await route.fulfill(ok({ records: [MOCK_TASK], total: 1 }))
  })

  await page.route('**/api/streaming-accounts/page**', async (route) => {
    await route.fulfill(ok({ records: [], total: 0 }))
  })

  await page.route('**/api/merchants/all', async (route) => {
    await route.fulfill(ok([]))
  })

  await page.route('**/api/dashboard/**', async (route) => {
    await route.fulfill(
      ok({
        agentCount: 1,
        onlineAgentCount: 1,
        taskCount: 1,
        runningTaskCount: 1
      })
    )
  })
}

/**
 * Bypass login form: inject token then navigate to app shell.
 */
export async function gotoAuthenticated(page, path = '/') {
  await injectAuth(page)
  await mockCommonApis(page)
  await page.goto(path)
}

/**
 * Mock login API for specs that exercise the login form directly.
 */
export async function mockLoginApi(page, success = true) {
  await page.route('**/api/auth/login', async (route) => {
    if (!success) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: 401, message: '用户名或密码错误', data: null })
      })
      return
    }
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
}
