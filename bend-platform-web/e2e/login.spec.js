import { test, expect } from '@playwright/test'

test.describe('登录流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('应该显示登录页面', async ({ page }) => {
    await expect(page.locator('h2')).toContainText('登录')
    await expect(page.locator('input[placeholder="用户名"]')).toBeVisible()
    await expect(page.locator('input[placeholder="密码"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('应该正确填写登录表单', async ({ page }) => {
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')

    await expect(page.locator('input[placeholder="用户名"]')).toHaveValue('admin')
    await expect(page.locator('input[placeholder="密码"]')).toHaveValue('password')
  })

  test('应该成功登录并跳转到首页', async ({ page }) => {
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')

    await page.waitForURL('**/')
    await expect(page.locator('.sidebar')).toBeVisible()
  })

  test('空用户名应该显示错误', async ({ page }) => {
    await page.fill('input[placeholder="密码"]', 'password')
    await page.click('button[type="submit"]')

    await expect(page.locator('.el-message--error')).toBeVisible()
  })

  test('错误密码应该显示错误消息', async ({ page }) => {
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'wrongpassword')
    await page.click('button[type="submit"]')

    await expect(page.locator('.el-message--error')).toBeVisible()
  })

  test('应该支持记住登录状态', async ({ page }) => {
    const rememberMeCheckbox = page.locator('input[type="checkbox"]')
    if (await rememberMeCheckbox.isVisible()) {
      await rememberMeCheckbox.check()
      await expect(rememberMeCheckbox).toBeChecked()
    }
  })
})

test.describe('注册流程', () => {
  test('应该显示注册入口', async ({ page }) => {
    await page.goto('/login')
    const registerLink = page.locator('text=注册账号')
    await expect(registerLink).toBeVisible()
  })

  test('应该跳转到注册页面', async ({ page }) => {
    await page.goto('/login')
    await page.click('text=注册账号')
    await expect(page).toHaveURL(/.*register/)
  })
})
