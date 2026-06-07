/**
 * 端到端：串流会话长寿命化关键场景
 *
 * 覆盖三个 P0 业务场景（见 AGENTS.md §Step1–3 vs Step4 边界）：
 *  1. Step4 失败 → 保留串流 + UI 显示 automation_failed + 可重试
 *  2. 任务终止后再次启动 → 同一 taskId 复用并新增 streaming_session
 *  3. 任务详情页切换历史 session → 事件按 session 过滤 + 历史 session 隐藏控制按钮
 *
 * 默认走 mock 后端（page.route 拦截），保证脚本本地可重复运行无需联调。
 * 如需对真实后端跑，设置 E2E_LIVE=1 环境变量后跳过该 spec（需人工触发对应场景）。
 */
import { test, expect } from '@playwright/test'
import {
  injectAuth,
  mockTaskBackend,
  ids,
  waitForApiCall
} from './helpers/streamingSession.js'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:3090'

test.describe('串流会话长寿命化', () => {
  test.skip(
    !!process.env.E2E_LIVE,
    'E2E_LIVE 模式下跳过 mock 用例，请使用 streaming-session-flow.live.spec.js（如有）'
  )

  test.beforeEach(async ({ page }) => {
    await injectAuth(page)
  })

  test('场景一：Step4 失败 → 串流保持 + automation_failed 警告 + 可重试', async ({
    page
  }) => {
    const ctrl = await mockTaskBackend(page)

    await page.goto(`${BASE}/tasks/${ids.TASK_ID}`)

    await expect(page.locator('h2', { hasText: '任务详情' })).toBeVisible({
      timeout: 10000
    })

    await expect(
      page.locator('.session-switcher .label', { hasText: '查看会话轮次' })
    ).toBeVisible({ timeout: 10000 })

    await expect(
      page.locator('.task-control-bar button', { hasText: '开始自动化' })
    ).toBeVisible({ timeout: 10000 })

    ctrl.setSessionPhase('automation_failed')

    const failedAlert = page.locator(
      '.window-hint .el-alert__title, .window-hint .el-alert',
      { hasText: '自动化未完成' }
    )
    await expect(failedAlert.first()).toBeVisible({ timeout: 15000 })

    await expect(
      page.locator('.task-control-bar button', { hasText: '开始自动化' })
    ).toBeVisible({ timeout: 5000 })

    await expect(
      page.locator('.task-control-bar button', { hasText: '终止任务' })
    ).toBeVisible()
    await expect(
      page.locator('.task-control-bar button', { hasText: '重连串流' })
    ).toBeVisible()

    expect(ctrl.state.task.status).toBe('running')

    const startReq = page.waitForRequest(
      (req) =>
        req.url().includes(`/api/tasks/${ids.TASK_ID}/start-automation`) &&
        req.method() === 'POST'
    )
    await page
      .locator('.task-control-bar button', { hasText: '开始自动化' })
      .click()
    const req = await startReq
    const body = req.postData() ? JSON.parse(req.postData()) : {}
    expect(body.gameActionType).toBeTruthy()

    await expect.poll(() => ctrl.state.task.sessionPhase).toBe('automating')
  })

  test('场景二：终止后再次启动 → 同一 taskId 复用并新增 session', async ({
    page
  }) => {
    const ctrl = await mockTaskBackend(page)

    await page.goto(`${BASE}/tasks/${ids.TASK_ID}`)
    await expect(page.locator('h2', { hasText: '任务详情' })).toBeVisible({
      timeout: 10000
    })

    page.once('dialog', (d) => d.accept())
    const terminateBtn = page.locator('.task-control-bar button', {
      hasText: '终止任务'
    })
    await expect(terminateBtn).toBeVisible({ timeout: 10000 })
    await terminateBtn.click()
    await page
      .locator('.el-message-box__btns button', { hasText: '确定' })
      .click()

    await expect.poll(() => ctrl.state.task.status).toBe('terminated')

    await page.goto(`${BASE}/streaming-accounts`)
    await expect(page.locator('.el-table__body-wrapper')).toBeVisible({
      timeout: 10000
    })

    expect(ctrl.state.sessions.length).toBe(1)
    const startStreamingReq = page.waitForResponse(
      (resp) =>
        resp.url().includes(`/api/streaming-accounts/${ids.STREAMING_ACCOUNT_ID}/tasks/start-streaming`) &&
        resp.request().method() === 'POST'
    )

    await page.evaluate(
      async ({ sid, agentId, gaId, token }) => {
        const res = await fetch(
          `http://localhost:8060/api/streaming-accounts/${sid}/tasks/start-streaming`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`
            },
            body: JSON.stringify({
              agentId,
              gameAccountIds: [gaId]
            })
          }
        )
        return res.json()
      },
      {
        sid: ids.STREAMING_ACCOUNT_ID,
        agentId: ids.AGENT_ID,
        gaId: ids.GAME_ACCOUNT_ID,
        token: 'e2e-fake-token'
      }
    )

    const resp = await startStreamingReq
    const body = await resp.json()
    expect(body.data.taskId).toBe(ids.TASK_ID)
    expect(body.data.reused).toBe(true)

    expect(ctrl.state.sessions.length).toBe(2)
    expect(ctrl.state.task.sessionId).toBe(body.data.sessionId)
    expect(ctrl.state.task.sessionPhase).toBe('opening')

    await page.goto(`${BASE}/tasks/${ids.TASK_ID}`)
    await expect(page.locator('h2', { hasText: '任务详情' })).toBeVisible({
      timeout: 10000
    })

    await page.locator('.session-switcher .el-select').click()
    const dropdownItems = page.locator(
      '.el-select-dropdown:visible .el-select-dropdown__item'
    )
    await expect(dropdownItems).toHaveCount(2, { timeout: 5000 })
    await page.keyboard.press('Escape')
  })

  test('场景三：切换历史 session → 事件按 session 过滤 + 控制按钮隐藏', async ({
    page
  }) => {
    const ctrl = await mockTaskBackend(page)
    ctrl.addHistorySession('sess-history', 'closed', '2026-06-06T08:00:00')

    await page.goto(`${BASE}/tasks/${ids.TASK_ID}`)
    await expect(page.locator('h2', { hasText: '任务详情' })).toBeVisible({
      timeout: 10000
    })

    await expect(page.locator('.session-switcher')).toBeVisible({
      timeout: 10000
    })
    await expect(page.locator('.history-tag')).toBeHidden()
    await expect(
      page.locator('.task-control-bar button', { hasText: '终止任务' })
    ).toBeVisible()

    await page.locator('.session-switcher .el-select').click()
    const items = page.locator(
      '.el-select-dropdown:visible .el-select-dropdown__item'
    )
    await expect(items).toHaveCount(2, { timeout: 5000 })

    const eventsCallStart = ctrl.state.apiCalls.length
    const historyItem = items.filter({ hasText: /#/ }).first()
    await historyItem.click()

    const filteredCallSeen = await waitForApiCall(
      ctrl.state,
      (c) =>
        c.method === 'GET' &&
        c.url.includes(`/api/tasks/${ids.TASK_ID}/events`) &&
        c.url.includes('sessionId=sess-history'),
      8000
    )
    expect(filteredCallSeen).toBe(true)

    await expect(page.locator('.history-tag', { hasText: '历史会话' })).toBeVisible({
      timeout: 5000
    })

    await expect(page.locator('.task-control-bar')).toHaveCount(0)

    await expect(
      page
        .locator('.event-timeline-panel .msg')
        .filter({ hasText: /历史会话 sess-history 事件/ })
    ).toBeVisible({ timeout: 5000 })

    expect(ctrl.state.apiCalls.length).toBeGreaterThan(eventsCallStart)
  })
})
