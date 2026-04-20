"""
Template Matcher - Image recognition using template matching

功能说明：
- 基于模板匹配算法的图像识别
- 在屏幕截图中查找指定模板图片
- 返回匹配位置和置信度
- 支持模板缓存提高性能

技术实现：
- 使用OpenCV的matchTemplate函数
- TM_CCOEFF_NORMED算法计算匹配度
- 支持多模板同时匹配
- 支持等待模板出现（轮询检测）

性能优化：
- 模板图片缓存机制
- 异步执行避免阻塞
- 可配置匹配阈值
"""
import os
import asyncio
import numpy as np
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass

from ..core.config import config
from ..core.logger import get_logger


@dataclass
class MatchResult:
    """
    模板匹配结果数据类

    属性说明：
    - found: 是否找到匹配
    - template_name: 模板名称
    - confidence: 匹配置信度（0-1）
    - location: 匹配位置 (x1, y1, x2, y2)
    - center: 匹配中心点 (x, y)
    """
    found: bool                              # 是否找到匹配
    template_name: str                       # 模板名称
    confidence: float                        # 匹配置信度
    location: Optional[Tuple[int, int, int, int]] = None  # 匹配位置坐标
    center: Optional[Tuple[int, int]] = None  # 匹配中心点


class TemplateMatcher:
    """
    模板匹配器

    功能说明：
    - 在视频帧中查找预定义的模板图片
    - 计算匹配置信度判断是否匹配成功
    - 支持等待模板出现（用于自动化流程）

    使用方式：
    - 创建实例后调用 find_template() 查找单个模板
    - 调用 find_all_templates() 同时查找多个模板
    - 调用 wait_for_template() 等待模板出现
    """

    def __init__(self):
        """初始化模板匹配器"""
        self._template_dir = config.template_dir  # 模板图片目录
        self._threshold = config.get('template.threshold', 0.8)  # 默认匹配阈值
        self._cache_enabled = config.get('template.cache_enabled', True)  # 是否启用缓存
        self._templates: Dict[str, np.ndarray] = {}  # 模板缓存字典
        self.logger = get_logger('template')  # 日志记录器

    def _load_template(self, template_path: str) -> Optional[np.ndarray]:
        """
        从文件加载模板图片

        参数说明：
        - template_path: 模板图片路径

        返回值：
        - 成功：模板图片numpy数组
        - 失败：None
        """
        if not os.path.exists(template_path):
            # 尝试在模板目录中查找
            template_name = os.path.basename(template_path)
            full_path = os.path.join(self._template_dir, template_name)
            if os.path.exists(full_path):
                template_path = full_path
            else:
                return None

        try:
            import cv2
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self.logger.error(f"Failed to load template: {template_path}")
                return None
            return template
        except Exception as e:
            self.logger.error(f"Error loading template {template_path}: {e}")
            return None

    def _load_cached(self, template_name: str) -> Optional[np.ndarray]:
        """
        带缓存的模板加载

        参数说明：
        - template_name: 模板名称

        返回值：
        - 成功：模板图片numpy数组
        - 失败：None
        """
        # 缓存命中
        if template_name in self._templates:
            return self._templates[template_name]

        # 加载并缓存
        template = self._load_template(template_name)
        if template is not None and self._cache_enabled:
            self._templates[template_name] = template

        return template

    def clear_cache(self):
        """
        清空模板缓存

        使用场景：
        - 模板更新后需要清除旧缓存
        - 内存紧张时释放缓存
        """
        self._templates.clear()
        self.logger.debug("Template cache cleared")

    async def find_template(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: Optional[float] = None
    ) -> MatchResult:
        """
        在帧中查找模板

        参数说明：
        - frame: 源图像（numpy数组）
        - template_name: 模板图片文件名
        - threshold: 匹配阈值（0-1），低于此值视为未匹配

        返回值：
        - MatchResult对象，包含匹配结果信息

        实现说明：
        - 内部使用线程池执行耗时的图像匹配运算
        - 避免阻塞主事件循环
        """
        if threshold is None:
            threshold = self._threshold

        try:
            loop = asyncio.get_event_loop()
            # 在线程池中执行同步的模板匹配
            result = await loop.run_in_executor(
                None,
                self._match_template,
                frame, template_name, threshold
            )
            return result

        except Exception as e:
            self.logger.error(f"Error in template matching: {e}")
            return MatchResult(found=False, template_name=template_name, confidence=0.0)

    def _match_template(
        self,
        frame: np.ndarray,
        template_name: str,
        threshold: float
    ) -> MatchResult:
        """
        同步模板匹配（内部方法）

        参数说明：
        - frame: 源图像
        - template_name: 模板名称
        - threshold: 匹配阈值

        返回值：MatchResult对象
        """
        import cv2

        template = self._load_cached(template_name)
        if template is None:
            self.logger.warning(f"Template not found: {template_name}")
            return MatchResult(found=False, template_name=template_name, confidence=0.0)

        if frame is None or frame.size == 0:
            return MatchResult(found=False, template_name=template_name, confidence=0.0)

        try:
            # 执行模板匹配
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            self.logger.debug(f"Template '{template_name}' match confidence: {max_val:.3f}")

            if max_val >= threshold:
                # 匹配成功，计算位置信息
                h, w = template.shape[:2]
                location = (max_loc[0], max_loc[1], max_loc[0] + w, max_loc[1] + h)
                center = (max_loc[0] + w // 2, max_loc[1] + h // 2)
                return MatchResult(
                    found=True,
                    template_name=template_name,
                    confidence=float(max_val),
                    location=location,
                    center=center
                )
            else:
                # 匹配度低于阈值
                return MatchResult(
                    found=False,
                    template_name=template_name,
                    confidence=float(max_val)
                )

        except Exception as e:
            self.logger.error(f"Template matching error: {e}")
            return MatchResult(found=False, template_name=template_name, confidence=0.0)

    async def find_all_templates(
        self,
        frame: np.ndarray,
        template_names: List[str],
        threshold: Optional[float] = None
    ) -> List[MatchResult]:
        """
        在帧中查找多个模板

        参数说明：
        - frame: 源图像
        - template_names: 模板名称列表
        - threshold: 匹配阈值

        返回值：MatchResult列表
        """
        results = []
        for name in template_names:
            result = await self.find_template(frame, name, threshold)
            results.append(result)
        return results

    async def wait_for_template(
        self,
        frame_getter,
        template_name: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5,
        threshold: Optional[float] = None
    ) -> Optional[MatchResult]:
        """
        等待模板出现在帧中

        参数说明：
        - frame_getter: 异步函数，返回当前帧
        - template_name: 要等待的模板名称
        - timeout: 最大等待时间（秒）
        - poll_interval: 轮询间隔（秒）
        - threshold: 匹配阈值

        返回值：
        - 成功：MatchResult对象
        - 超时：None

        使用场景：
        - 等待游戏场景切换到特定界面
        - 等待弹出对话框出现
        - 等待加载完成
        """
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            frame = await frame_getter()
            if frame is not None:
                result = await self.find_template(frame, template_name, threshold)
                if result.found:
                    return result
            await asyncio.sleep(poll_interval)

        self.logger.debug(f"Template '{template_name}' not found within {timeout}s timeout")
        return None

    def add_template(self, name: str, image: np.ndarray):
        """
        程序化添加模板到缓存

        参数说明：
        - name: 模板名称
        - image: 模板图片数组
        """
        self._templates[name] = image
        self.logger.debug(f"Added template to cache: {name}")

    def remove_template(self, name: str):
        """
        从缓存中移除模板

        参数说明：
        - name: 模板名称
        """
        if name in self._templates:
            del self._templates[name]
            self.logger.debug(f"Removed template from cache: {name}")
