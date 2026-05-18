"""
浏览器登录并发控制器
====================

功能说明：
- 控制浏览器登录的并发数量
- 防止同时打开过多浏览器实例
- 支持多账号并发场景下的资源管理

使用方式：
    # 限制最多同时进行3个浏览器登录
    controller = BrowserLoginController(max_concurrent=3)
    
    async with controller.acquire():
        # 执行浏览器自动化登录
        ...

作者：技术团队
版本：1.0
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger('browser_login_controller')


class BrowserLoginController:
    """
    浏览器登录并发控制器

    功能：
    1. 使用信号量限制同时进行的浏览器登录数量
    2. 防止系统资源耗尽
    3. 支持异步上下文管理器

    使用示例：
        controller = BrowserLoginController(max_concurrent=3)
        
        # 方式1：使用上下文管理器
        async with controller.acquire():
            # 执行登录逻辑
            ...
        
        # 方式2：手动获取和释放
        await controller.acquire()
        try:
            # 执行登录逻辑
            ...
        finally:
            await controller.release()
    """

    _instance: Optional['BrowserLoginController'] = None

    def __init__(self, max_concurrent: int = 3):
        """
        初始化控制器

        参数：
        - max_concurrent: 最大并发数（默认3个浏览器实例）
        """
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._active_count = 0
        self._lock = asyncio.Lock()
        logger.info(f"浏览器登录控制器已初始化（最大并发: {max_concurrent}）")

    @classmethod
    def get_instance(cls, max_concurrent: int = 3) -> 'BrowserLoginController':
        """
        获取单例实例

        参数：
        - max_concurrent: 最大并发数

        返回：
        - BrowserLoginController 实例
        """
        if cls._instance is None:
            cls._instance = cls(max_concurrent)
        return cls._instance

    async def acquire(self):
        """
        获取登录许可

        如果当前活跃登录数已达到上限，将等待直到有登录完成
        """
        await self._semaphore.acquire()
        async with self._lock:
            self._active_count += 1
            logger.info(f"获得浏览器登录许可（活跃: {self._active_count}/{self._max_concurrent}）")

    async def release(self):
        """
        释放登录许可

        允许其他登录任务开始
        """
        async with self._lock:
            self._active_count -= 1
        self._semaphore.release()
        logger.info(f"释放浏览器登录许可（活跃: {self._active_count}/{self._max_concurrent}）")

    def acquire_context(self):
        """
        获取异步上下文管理器

        返回：
        - 异步上下文管理器

        使用示例：
            controller = BrowserLoginController(max_concurrent=3)
            async with controller.acquire_context():
                # 执行登录逻辑
                ...
        """
        return BrowserLoginContext(self)

    @property
    def active_count(self) -> int:
        """获取当前活跃登录数"""
        return self._active_count

    @property
    def max_concurrent(self) -> int:
        """获取最大并发数"""
        return self._max_concurrent

    def is_available(self) -> bool:
        """检查是否还有可用的登录槽位"""
        return self._active_count < self._max_concurrent


class BrowserLoginContext:
    """
    浏览器登录上下文管理器

    用于简化登录控制的获取和释放
    """

    def __init__(self, controller: BrowserLoginController):
        """
        初始化上下文

        参数：
        - controller: BrowserLoginController 实例
        """
        self._controller = controller
        self._acquired = False

    async def __aenter__(self):
        """进入上下文，获取许可"""
        await self._controller.acquire()
        self._acquired = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，释放许可"""
        if self._acquired:
            await self._controller.release()
            self._acquired = False


async def test_concurrent_login():
    """
    测试并发登录控制

    模拟多个账号同时进行登录
    """
    controller = BrowserLoginController(max_concurrent=3)

    async def login_task(task_id: int, delay: float):
        """模拟登录任务"""
        async with controller.acquire_context():
            print(f"任务 {task_id}: 开始登录（活跃: {controller.active_count}）")
            await asyncio.sleep(delay)
            print(f"任务 {task_id}: 登录完成（活跃: {controller.active_count}）")

    # 模拟5个任务同时发起
    tasks = [
        login_task(1, 2.0),
        login_task(2, 1.5),
        login_task(3, 1.0),
        login_task(4, 2.5),
        login_task(5, 1.8)
    ]

    print("开始并发测试...")
    await asyncio.gather(*tasks)
    print("所有任务完成！")


if __name__ == "__main__":
    print("测试浏览器登录并发控制")
    print("=" * 50)
    asyncio.run(test_concurrent_login())
