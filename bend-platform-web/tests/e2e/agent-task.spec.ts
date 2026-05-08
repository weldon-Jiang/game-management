import { test, expect } from '@playwright/test';

test.describe('Agent Task Dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display agent task dialog', async ({ page }) => {
    await expect(page.locator('text=Agent任务监控')).toBeVisible();
  });

  test('should show running tasks section', async ({ page }) => {
    await expect(page.locator('text=运行中任务')).toBeVisible();
  });

  test('should show all tasks section', async ({ page }) => {
    await expect(page.locator('text=所有任务')).toBeVisible();
  });

  test('should display task details when selecting a task', async ({ page }) => {
    await page.click('text=test_task_001');
    await expect(page.locator('text=任务详情')).toBeVisible();
  });

  test('should have pause button', async ({ page }) => {
    const pauseButton = page.getByRole('button', { name: /暂停/i });
    await expect(pauseButton).toBeVisible();
  });

  test('should have resume button', async ({ page }) => {
    const resumeButton = page.getByRole('button', { name: /恢复/i });
    await expect(resumeButton).toBeVisible();
  });

  test('should have stop button', async ({ page }) => {
    const stopButton = page.getByRole('button', { name: /停止/i });
    await expect(stopButton).toBeVisible();
  });

  test('should display progress correctly', async ({ page }) => {
    await page.click('text=test_task_001');
    await expect(page.locator('[data-testid="progress-bar"]')).toBeVisible();
  });

  test('should show game accounts status', async ({ page }) => {
    await page.click('text=test_task_001');
    await expect(page.locator('text=Player1')).toBeVisible();
    await expect(page.locator('text=Player2')).toBeVisible();
  });
});

test.describe('Task Control Buttons', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.click('text=test_task_001');
  });

  test('should pause task when click pause button', async ({ page }) => {
    await page.click('button:has-text("暂停")');
    await expect(page.locator('text=已暂停')).toBeVisible();
  });

  test('should resume task when click resume button', async ({ page }) => {
    await page.click('button:has-text("暂停")');
    await page.click('button:has-text("恢复")');
    await expect(page.locator('text=运行中')).toBeVisible();
  });

  test('should stop task when click stop button', async ({ page }) => {
    await page.click('button:has-text("停止")');
    await expect(page.locator('text=已停止')).toBeVisible();
  });
});

test.describe('WebSocket Live Updates', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should update task status in real-time', async ({ page }) => {
    const statusElement = page.locator('[data-testid="task-status"]');
    await expect(statusElement).toContainText('pending');

    await page.waitForTimeout(1000);

    await expect(statusElement).toContainText('running');
  });

  test('should update progress bar in real-time', async ({ page }) => {
    await page.click('text=test_task_001');
    const progressBar = page.locator('[data-testid="progress-bar"]');
    await expect(progressBar).toBeVisible();
  });

  test('should update match count in real-time', async ({ page }) => {
    await page.click('text=test_task_001');
    const matchCount = page.locator('[data-testid="match-count"]');
    await expect(matchCount).toContainText('0/3');
  });
});
