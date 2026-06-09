import { test, expect } from '@playwright/test'
import {
  LOGIN_KEY_SELECTOR,
  PASSWORD_SELECTOR,
  gotoAuthenticated,
  mockLoginApi,
  mockCommonApis
} from './helpers/auth.js'

test.describe('登录流程', () => {
  test.beforeEach(async ({ page }) => {
    await mockCommonApis(page)
    await page.goto('/login')
  })

  test('应该显示登录页面', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('Bend Platform')
    await expect(page.locator(LOGIN_KEY_SELECTOR)).toBeVisible()
    await expect(page.locator(PASSWORD_SELECTOR)).toBeVisible()
    await expect(page.locator('button').filter({ hasText: '登' })).toBeVisible()
  })

  test('应该正确填写登录表单', async ({ page }) => {
    await page.fill(LOGIN_KEY_SELECTOR, 'admin')
    await page.fill(PASSWORD_SELECTOR, 'password')

    await expect(page.locator(LOGIN_KEY_SELECTOR)).toHaveValue('admin')
    await expect(page.locator(PASSWORD_SELECTOR)).toHaveValue('password')
  })

  test('应该成功登录并跳转到首页', async ({ page }) => {
    await mockLoginApi(page, true)
    await page.fill(LOGIN_KEY_SELECTOR, 'admin')
    await page.fill(PASSWORD_SELECTOR, 'password')
    await page.locator('button').filter({ hasText: '登' }).click()

    await page.waitForURL('**/dashboard**', { timeout: 10000 })
    await expect(page.locator('.sidebar, aside, [class*="sidebar"]').first()).toBeVisible()
  })

  test('空用户名应该显示错误', async ({ page }) => {
    await page.fill(PASSWORD_SELECTOR, 'password')
    await page.locator('button').filter({ hasText: '登' }).click()

    await expect(page.locator('.el-form-item__error').first()).toBeVisible()
  })

  test('错误密码应该显示错误消息', async ({ page }) => {
    await mockLoginApi(page, false)
    await page.fill(LOGIN_KEY_SELECTOR, 'admin')
    await page.fill(PASSWORD_SELECTOR, 'wrongpassword')
    await page.locator('button').filter({ hasText: '登' }).click()

    await expect(page.locator('.el-message--error')).toBeVisible()
  })
})
