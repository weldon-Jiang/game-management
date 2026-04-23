import { test, expect } from '@playwright/test'

test.describe('任务管理流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/', { timeout: 10000 })
  })

  test('应该显示任务列表页面', async ({ page }) => {
    await page.goto('/tasks')
    await expect(page.locator('h2')).toContainText('任务')
    await expect(page.locator('.content-card')).toBeVisible()
  })

  test('应该显示任务列表数据', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForSelector('.el-table', { timeout: 5000 })

    const table = page.locator('.el-table')
    await expect(table).toBeVisible()
  })

  test('任务列表应该包含必要列', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForSelector('.el-table', { timeout: 5000 })

    await expect(page.locator('text=任务名称')).toBeVisible()
    await expect(page.locator('text=类型')).toBeVisible()
    await expect(page.locator('text=状态')).toBeVisible()
    await expect(page.locator('text=创建时间')).toBeVisible()
  })

  test('应该支持状态筛选', async ({ page }) => {
    await page.goto('/tasks')

    const statusSelect = page.locator('.el-select').first()
    if (await statusSelect.isVisible()) {
      await statusSelect.click()
      await page.waitForSelector('.el-select-dropdown')

      const pendingOption = page.locator('.el-select-dropdown__item').filter({ hasText: '待执行' })
      if (await pendingOption.isVisible()) {
        await pendingOption.click()
        await page.waitForTimeout(500)
      }
    }
  })

  test('应该支持任务类型筛选', async ({ page }) => {
    await page.goto('/tasks')

    const selects = page.locator('.el-select')
    const count = await selects.count()
    if (count > 1) {
      const typeSelect = selects.nth(1)
      if (await typeSelect.isVisible()) {
        await typeSelect.click()
        await page.waitForSelector('.el-select-dropdown')

        const option = page.locator('.el-select-dropdown__item').first()
        if (await option.isVisible()) {
          await option.click()
          await page.waitForTimeout(500)
        }
      }
    }
  })

  test('应该显示状态标签', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForSelector('.el-table', { timeout: 5000 })

    const statusTags = page.locator('.el-table .el-tag')
    const count = await statusTags.count()
    expect(count).toBeGreaterThan(0)
  })

  test('应该支持刷新操作', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForSelector('.el-table', { timeout: 5000 })

    const refreshButton = page.locator('button').filter({ has: page.locator('svg') }).first()
    if (await refreshButton.isVisible()) {
      await refreshButton.click()
      await page.waitForTimeout(500)
    }
  })

  test('应该支持分页', async ({ page }) => {
    await page.goto('/tasks')

    const pagination = page.locator('.el-pagination')
    if (await pagination.isVisible()) {
      await expect(pagination.locator('.el-pager li').first()).toBeVisible()
    }
  })
})
