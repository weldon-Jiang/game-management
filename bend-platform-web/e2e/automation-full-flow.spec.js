import { test, expect } from '@playwright/test'

test('automation full flow smoke test', async ({ page }) => {
  const apiEvents = []

  page.on('response', async (response) => {
    const url = response.url()
    if (
      url.includes('/api/auth/login') ||
      url.includes('/api/automation/') ||
      url.includes('/api/agents') ||
      url.includes('/api/streaming') ||
      url.includes('/api/game-accounts') ||
      url.includes('/api/agent-callback')
    ) {
      let body = ''
      try {
        body = (await response.text()).slice(0, 500)
      } catch {
        body = '<unreadable>'
      }
      apiEvents.push({
        url,
        status: response.status(),
        body
      })
    }
  })

  await page.goto('http://localhost:3090/login')
  await page.locator('input').nth(0).fill('weldon')
  await page.locator('input').nth(1).fill('123456')
  await page.locator('button').filter({ hasText: /登|鐧|录|褰/ }).first().click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 })

  await page.goto('http://localhost:3090/streaming-accounts')
  await page.waitForLoadState('networkidle')
  await expect(page.locator('.el-table__body-wrapper')).toBeVisible({ timeout: 15000 })
  await expect(page.getByText('jwdong', { exact: true })).toBeVisible({ timeout: 15000 })

  const startButton = page.locator('button').filter({ hasText: /启动|鍚|动|自/ }).first()
  await expect(startButton).toBeVisible({ timeout: 15000 })
  await startButton.click()

  const dialog = page.locator('.el-dialog').filter({ hasText: /Agent|启动|鍚|动/ }).last()
  await expect(dialog).toBeVisible({ timeout: 15000 })

  const agentSelect = dialog.locator('.el-select').first()
  await agentSelect.click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').first().click()

  await dialog.locator('button').filter({ hasText: /启动|鍚|动/ }).last().click()

  await page.waitForTimeout(25000)

  await page.goto('http://localhost:3090/agents')
  await page.waitForLoadState('networkidle')
  await expect(page.getByText('AGENT-37EAD6AC-FB715D0B-6EB5C594')).toBeVisible({ timeout: 15000 })

  console.log(JSON.stringify(apiEvents, null, 2))
})
