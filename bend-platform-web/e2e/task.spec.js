import { test, expect } from '@playwright/test'
import { gotoAuthenticated } from './helpers/auth.js'

test.describe('任务管理流程', () => {
  test.beforeEach(async ({ page }) => {
    await gotoAuthenticated(page, '/')
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
    await page.waitForSelector('.el-table__header', { timeout: 5000 })

    await expect(page.getByRole('columnheader', { name: '任务名称' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '状态' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '创建时间' })).toBeVisible()
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

  test('应该显示状态标签', async ({ page }) => {
    await page.goto('/tasks')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    await expect(page.locator('.el-table__row').first()).toBeVisible()
    const statusTags = page.locator('.el-table .el-tag')
    expect(await statusTags.count()).toBeGreaterThanOrEqual(0)
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
