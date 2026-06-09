import { test, expect } from '@playwright/test'
import { gotoAuthenticated } from './helpers/auth.js'

test.describe('Agent 管理流程', () => {
  test.beforeEach(async ({ page }) => {
    await gotoAuthenticated(page, '/')
  })

  test('应该显示 Agent 列表页面', async ({ page }) => {
    await page.goto('/agents')
    await expect(page.locator('h2')).toContainText('Agent')
    await expect(page.locator('.el-table')).toBeVisible()
  })

  test('应该显示 Agent 列表数据', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const rows = page.locator('.el-table__row')
    await expect(rows.first()).toBeVisible()
  })

  test('Agent 列表应该包含必要列', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__header', { timeout: 5000 })

    await expect(page.getByRole('columnheader', { name: 'Agent名称' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Agent ID' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '主机地址' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: '状态' })).toBeVisible()
  })

  test('应该支持状态筛选', async ({ page }) => {
    await page.goto('/agents')

    const statusSelect = page.locator('.el-select').first()
    await statusSelect.click()
    await page.locator('.el-select-dropdown__item').filter({ hasText: '在线' }).click()

    await page.waitForTimeout(500)
    await expect(statusSelect).toContainText('在线')
  })

  test('应该显示在线和离线状态标签', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table', { timeout: 5000 })

    const statusTags = page.locator('.el-tag')
    const count = await statusTags.count()
    expect(count).toBeGreaterThan(0)
  })

  test('应该支持刷新操作', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const refreshButton = page.locator('button').filter({ has: page.locator('.el-icon') }).first()
    await refreshButton.click()

    await page.waitForTimeout(500)
  })

  test('应该支持分页', async ({ page }) => {
    await page.goto('/agents')

    const pagination = page.locator('.el-pagination')
    if (await pagination.isVisible()) {
      await expect(pagination.locator('.el-pager li').first()).toBeVisible()
    }
  })

  test('点击查看任务应该跳转到任务管理并带上 Agent 条件', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const viewButton = page.locator('text=查看任务').first()
    if (await viewButton.isVisible()) {
      await viewButton.click()
      await page.waitForURL('**/tasks?agentId=*', { timeout: 5000 })
      await expect(page.locator('h2')).toContainText('任务管理')
      await expect(page.url()).toContain('agentId=')
    }
  })
})
