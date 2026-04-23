import { test, expect } from '@playwright/test'

test.describe('Agent 管理流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/', { timeout: 10000 })
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
    await page.waitForSelector('.el-table', { timeout: 5000 })

    await expect(page.locator('text=Agent ID')).toBeVisible()
    await expect(page.locator('text=主机地址')).toBeVisible()
    await expect(page.locator('text=状态')).toBeVisible()
    await expect(page.locator('text=最后心跳')).toBeVisible()
  })

  test('应该支持状态筛选', async ({ page }) => {
    await page.goto('/agents')

    const statusSelect = page.locator('.el-select').first()
    await statusSelect.click()
    await page.locator('text=在线').click()

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

    const refreshButton = page.locator('button').filter({ has: page.locator('.el-icon-refresh') }).first()
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

  test('点击查看任务应该打开任务弹窗', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const viewButton = page.locator('text=查看任务').first()
    if (await viewButton.isVisible()) {
      await viewButton.click()

      await page.waitForSelector('.el-dialog', { timeout: 3000 })
      await expect(page.locator('.el-dialog')).toBeVisible()
      await expect(page.locator('text=Agent 任务监控')).toBeVisible()
    }
  })

  test('任务弹窗应该显示 Agent 信息', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const viewButton = page.locator('text=查看任务').first()
    if (await viewButton.isVisible()) {
      await viewButton.click()
      await page.waitForSelector('.el-dialog', { timeout: 3000 })

      await expect(page.locator('text=Agent ID')).toBeVisible()
      await expect(page.locator('text=商户')).toBeVisible()
      await expect(page.locator('text=状态')).toBeVisible()
    }
  })

  test('任务弹窗应该支持切换 Tab', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const viewButton = page.locator('text=查看任务').first()
    if (await viewButton.isVisible()) {
      await viewButton.click()
      await page.waitForSelector('.el-dialog', { timeout: 3000 })

      await expect(page.locator('text=运行中的任务')).toBeVisible()
      await expect(page.locator('text=所有任务')).toBeVisible()
    }
  })

  test('任务弹窗应该支持关闭', async ({ page }) => {
    await page.goto('/agents')
    await page.waitForSelector('.el-table__row', { timeout: 5000 })

    const viewButton = page.locator('text=查看任务').first()
    if (await viewButton.isVisible()) {
      await viewButton.click()
      await page.waitForSelector('.el-dialog', { timeout: 3000 })

      await page.locator('.el-dialog__footer button').filter({ hasText: '关闭' }).click()
      await page.waitForTimeout(500)
      await expect(page.locator('.el-dialog')).not.toBeVisible()
    }
  })
})
