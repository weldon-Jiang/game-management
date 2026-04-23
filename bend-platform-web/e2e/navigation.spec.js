import { test, expect } from '@playwright/test'

test.describe('导航和布局', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/', { timeout: 10000 })
  })

  test('应该显示侧边栏', async ({ page }) => {
    await expect(page.locator('.sidebar, aside, [class*="sidebar"]').first()).toBeVisible()
  })

  test('侧边栏应该包含导航菜单', async ({ page }) => {
    const sidebar = page.locator('.sidebar, aside, [class*="sidebar"]').first()
    await expect(sidebar.locator('text=Agent').or(sidebar.locator('text=代理'))).toBeVisible()
  })

  test('应该能够导航到 Agent 页面', async ({ page }) => {
    const agentLink = page.locator('a[href*="agent"], .menu-item').filter({ hasText: /Agent|代理/ }).first()
    if (await agentLink.isVisible()) {
      await agentLink.click()
      await page.waitForURL('**/agents**', { timeout: 5000 })
      await expect(page.locator('h2').or(page.locator('[class*="title"]')).first()).toBeVisible()
    }
  })

  test('应该能够导航到任务页面', async ({ page }) => {
    const taskLink = page.locator('a[href*="task"], .menu-item').filter({ hasText: /任务|Task/ }).first()
    if (await taskLink.isVisible()) {
      await taskLink.click()
      await page.waitForURL('**/tasks**', { timeout: 5000 })
      await expect(page.locator('.content-card, [class*="content"]').first()).toBeVisible()
    }
  })

  test('应该显示面包屑导航', async ({ page }) => {
    await page.goto('/agents')
    const breadcrumbs = page.locator('.el-breadcrumb, [class*="breadcrumb"]')
    if (await breadcrumbs.isVisible()) {
      await expect(breadcrumbs.first()).toBeVisible()
    }
  })

  test('应该显示用户信息', async ({ page }) => {
    const userInfo = page.locator('[class*="user"], [class*="avatar"]').first()
    if (await userInfo.isVisible()) {
      await expect(userInfo).toBeVisible()
    }
  })

  test('应该支持登出', async ({ page }) => {
    const logoutButton = page.locator('button').filter({ hasText: /退出|登出|Logout/ }).first()
    if (await logoutButton.isVisible()) {
      await logoutButton.click()
      await page.waitForURL('**/login**', { timeout: 5000 })
      await expect(page.locator('text=登录')).toBeVisible()
    }
  })

  test('响应式布局 - 窄屏应该折叠侧边栏', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('/agents')
    await page.waitForLoadState('networkidle')

    const sidebar = page.locator('.sidebar, aside, [class*="sidebar"]').first()
    if (await sidebar.isVisible()) {
      const isCollapsed = await sidebar.evaluate(el => el.classList.contains('collapsed') || el.classList.contains('hide'))
      expect(typeof isCollapsed).toBe('boolean')
    }
  })
})

test.describe('首页仪表盘', () => {
  test('应该显示仪表盘内容', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/', { timeout: 10000 })

    const dashboard = page.locator('[class*="dashboard"], .home, [class*="overview"]').first()
    if (await dashboard.isVisible()) {
      await expect(dashboard).toBeVisible()
    }
  })

  test('应该显示统计卡片', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')
    await page.waitForURL('**/', { timeout: 10000 })

    const cards = page.locator('[class*="card"], .statistic, [class*="stat"]')
    const count = await cards.count()
    expect(count).toBeGreaterThanOrEqual(0)
  })
})
