"""
优化后的场景检测器
==================

功能说明：
- 降频检测：每N帧检测一次，节省CPU资源
- 增量检测：只检测有变化的区域
- 缓存机制：场景稳定时复用结果
- 异步处理：支持异步调用

技术实现参考（streaming项目优化）：
- 帧间差异检测
- ROI区域检测
- 检测结果缓存

作者：技术团队
版本：1.0
"""

import time
import asyncio
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

from ..core.logger import get_logger


class SceneState(Enum):
    """场景状态枚举"""
    HOME = "home"                    # Xbox主界面
    GAME_LIST = "game_list"         # 游戏列表
    MATCHMAKING = "matchmaking"     # 匹配中
    IN_GAME = "in_game"             # 游戏中
    SETTLEMENT = "settlement"       # 结算界面
    ACCOUNT_SWITCH = "account_switch"  # 账号切换
    LOADING = "loading"             # 加载中
    UNKNOWN = "unknown"              # 未知


@dataclass
class DetectionResult:
    """检测结果数据类"""
    scene: SceneState
    confidence: float  # 0.0 到 1.0
    timestamp: float
    detection_time_ms: float
    method: str  # 'full', 'cached', 'incremental'


@dataclass
class SceneConfig:
    """场景检测配置"""
    frame_interval: int = 5  # 每N帧检测一次
    confidence_threshold: float = 0.7  # 置信度阈值
    cache_timeout_sec: float = 2.0  # 缓存超时时间
    stability_count: int = 2  # 稳定判定次数
    diff_threshold: int = 30  # 画面变化阈值


class OptimizedSceneDetector:
    """
    优化后的场景检测器

    功能说明：
    - 降频检测：减少不必要的模板匹配
    - 增量检测：检测画面是否有显著变化
    - 缓存机制：场景稳定时快速返回
    - 异步接口：支持异步调用

    使用方式：
    - detector = OptimizedSceneDetector(config)
    - detector.set_matcher(template_matcher)
    - result = await detector.detect_scene(frame)

    架构说明：
    ┌─────────────────────────────────────────────────────────────┐
    │                  OptimizedSceneDetector                    │
    │                                                             │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │              帧控制层                                 │  │
    │  │  - 降频检测（每N帧）                                 │  │
    │  │  - 帧计数                                            │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                           │                               │
    │                           ▼                               │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │              变化检测层                               │  │
    │  │  - 画面差异计算                                      │  │
    │  │  - 变化阈值判定                                     │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                           │                               │
    │                           ▼                               │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │              检测层                                  │  │
    │  │  - 模板匹配                                         │  │
    │  │  - ROI检测                                         │  │
    │  └─────────────────────────────────────────────────────┘  │
    │                           │                               │
    │                           ▼                               │
    │  ┌─────────────────────────────────────────────────────┐  │
    │  │              缓存层                                  │  │
    │  │  - 结果缓存                                         │  │
    │  │  - 超时判定                                         │  │
    │  └─────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────┘
    """

    def __init__(self, config: Optional[SceneConfig] = None):
        self.logger = get_logger('optimized_scene_detector')
        self._config = config or SceneConfig()

        self._template_matcher = None
        self._frame_count = 0
        self._last_frame: Optional[np.ndarray] = None
        self._last_scene: Optional[SceneState] = None
        self._last_detection_time = 0.0
        self._cached_result: Optional[DetectionResult] = None
        self._stability_counter = 0

        self._detection_callbacks: List[Callable] = []
        self._stats = {
            'total_frames': 0,
            'skipped_frames': 0,
            'cached_hits': 0,
            'detections': 0,
            'avg_detection_time_ms': 0
        }

    def set_matcher(self, matcher):
        """
        设置模板匹配器

        参数：
        - matcher: 实现 find_best_match() 方法的匹配器
        """
        self._template_matcher = matcher
        self.logger.info("模板匹配器已设置")

    def add_detection_callback(self, callback: Callable[[DetectionResult], None]):
        """
        添加检测回调

        参数：
        - callback: 检测结果回调函数
        """
        self._detection_callbacks.append(callback)

    async def detect_scene(self, frame: np.ndarray) -> DetectionResult:
        """
        检测场景（优化主方法）

        参数：
        - frame: 当前帧图像

        返回：
        - DetectionResult: 检测结果
        """
        start_time = time.time()
        self._stats['total_frames'] += 1
        self._frame_count += 1

        scene_changed = await self._check_frame_change(frame)
        self._last_frame = frame.copy() if frame is not None else None

        if not scene_changed and self._cached_result:
            self._stats['skipped_frames'] += 1
            self._stats['cached_hits'] += 1

            self.logger.debug(f"场景未变化，使用缓存: {self._cached_result.scene.value}")

            return self._cached_result

        if self._frame_count % self._config.frame_interval != 0:
            self._stats['skipped_frames'] += 1

            if self._cached_result:
                return self._cached_result

        result = await self._perform_detection(frame, start_time)

        self._update_cache(result)
        self._notify_callbacks(result)

        return result

    async def _check_frame_change(self, frame: np.ndarray) -> bool:
        """
        检查画面是否有显著变化

        参数：
        - frame: 当前帧

        返回：
        - True: 有显著变化
        - False: 无显著变化
        """
        if self._last_frame is None:
            return True

        try:
            if frame.shape != self._last_frame.shape:
                return True

            diff = np.abs(frame.astype(np.float32) - self._last_frame.astype(np.float32))
            mean_diff = np.mean(diff)

            self.logger.debug(f"画面差异: {mean_diff:.2f}")

            return mean_diff > self._config.diff_threshold

        except Exception as e:
            self.logger.warning(f"变化检测失败: {e}")
            return True

    async def _perform_detection(
        self,
        frame: np.ndarray,
        start_time: float
    ) -> DetectionResult:
        """
        执行实际场景检测

        参数：
        - frame: 当前帧
        - start_time: 开始时间

        返回：
        - DetectionResult: 检测结果
        """
        if self._template_matcher is None:
            detection_time = (time.time() - start_time) * 1000
            return DetectionResult(
                scene=SceneState.UNKNOWN,
                confidence=0.0,
                timestamp=time.time(),
                detection_time_ms=detection_time,
                method='no_matcher'
            )

        try:
            best_match = await self._template_matcher.find_best_match(frame)

            if best_match and best_match.confidence >= self._config.confidence_threshold:
                scene = SceneState(best_match.label)
                method = 'full'
            else:
                scene = SceneState.UNKNOWN
                method = 'low_confidence'

            detection_time = (time.time() - start_time) * 1000
            confidence = best_match.confidence if best_match else 0.0

            result = DetectionResult(
                scene=scene,
                confidence=confidence,
                timestamp=time.time(),
                detection_time_ms=detection_time,
                method=method
            )

            self._stats['detections'] += 1
            total_time = self._stats['avg_detection_time_ms'] * (self._stats['detections'] - 1)
            self._stats['avg_detection_time_ms'] = (total_time + detection_time) / self._stats['detections']

            self.logger.debug(
                f"场景检测: {scene.value}, 置信度: {confidence:.2f}, "
                f"耗时: {detection_time:.1f}ms"
            )

            return result

        except Exception as e:
            self.logger.error(f"场景检测失败: {e}")
            detection_time = (time.time() - start_time) * 1000
            return DetectionResult(
                scene=SceneState.UNKNOWN,
                confidence=0.0,
                timestamp=time.time(),
                detection_time_ms=detection_time,
                method='error'
            )

    def _update_cache(self, result: DetectionResult):
        """
        更新缓存

        参数：
        - result: 检测结果
        """
        if result.scene == self._last_scene:
            self._stability_counter += 1
        else:
            self._stability_counter = 1
            self._last_scene = result.scene

        self._last_detection_time = time.time()
        self._cached_result = result

    def _notify_callbacks(self, result: DetectionResult):
        """通知所有回调"""
        for callback in self._detection_callbacks:
            try:
                callback(result)
            except Exception as e:
                self.logger.warning(f"回调执行失败: {e}")

    def is_scene_stable(self, scene: SceneState, required_stability: int = None) -> bool:
        """
        检查场景是否稳定

        参数：
        - scene: 场景状态
        - required_stability: 需要的稳定次数

        返回：
        - True: 场景稳定
        - False: 场景不稳定
        """
        required = required_stability or self._config.stability_count
        return (
            self._last_scene == scene and
            self._stability_counter >= required
        )

    def is_cache_valid(self) -> bool:
        """
        检查缓存是否有效

        返回：
        - True: 缓存有效
        - False: 缓存过期
        """
        if self._cached_result is None:
            return False

        elapsed = time.time() - self._last_detection_time
        return elapsed < self._config.cache_timeout_sec

    def reset(self):
        """重置检测器状态"""
        self._frame_count = 0
        self._last_frame = None
        self._last_scene = None
        self._cached_result = None
        self._stability_counter = 0
        self._last_detection_time = 0.0
        self.logger.info("场景检测器已重置")

    def get_stats(self) -> dict:
        """
        获取检测统计

        返回：
        - 统计信息字典
        """
        total = max(1, self._stats['total_frames'])
        skip_rate = self._stats['skipped_frames'] / total * 100
        cache_rate = self._stats['cached_hits'] / max(1, self._stats['total_frames']) * 100

        return {
            'total_frames': self._stats['total_frames'],
            'skipped_frames': self._stats['skipped_frames'],
            'skip_rate': f"{skip_rate:.1f}%",
            'cached_hits': self._stats['cached_hits'],
            'cache_rate': f"{cache_rate:.1f}%",
            'detections': self._stats['detections'],
            'avg_detection_time_ms': f"{self._stats['avg_detection_time_ms']:.1f}",
            'current_scene': self._last_scene.value if self._last_scene else None,
            'stability_counter': self._stability_counter
        }

    @property
    def current_scene(self) -> Optional[SceneState]:
        """获取当前场景"""
        return self._last_scene

    @property
    def config(self) -> SceneConfig:
        """获取配置"""
        return self._config


class IncrementalSceneDetector:
    """
    增量场景检测器

    功能说明：
    - 只检测指定ROI区域
    - 减少检测区域提高性能
    - 支持多区域联合检测
    """

    def __init__(self, detector: OptimizedSceneDetector):
        self._detector = detector
        self._roi_regions: List[Tuple[int, int, int, int]] = []
        self._logger = get_logger('incremental_detector')

    def add_roi(self, x: int, y: int, width: int, height: int):
        """
        添加ROI区域

        参数：
        - x, y: 区域左上角坐标
        - width, height: 区域宽高
        """
        self._roi_regions.append((x, y, width, height))
        self._logger.info(f"添加ROI区域: ({x}, {y}) {width}x{height}")

    def clear_roi(self):
        """清空所有ROI区域"""
        self._roi_regions.clear()

    def extract_roi_frames(self, frame: np.ndarray) -> List[np.ndarray]:
        """
        提取ROI区域帧

        参数：
        - frame: 原始帧

        返回：
        - ROI区域帧列表
        """
        roi_frames = []
        for x, y, w, h in self._roi_regions:
            if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
                roi = frame[y:min(y+h, frame.shape[0]), x:min(x+w, frame.shape[1])]
                roi_frames.append(roi)
        return roi_frames

    async def detect_with_roi(self, frame: np.ndarray) -> DetectionResult:
        """
        使用ROI检测场景

        参数：
        - frame: 当前帧

        返回：
        - DetectionResult: 检测结果
        """
        if not self._roi_regions:
            return await self._detector.detect_scene(frame)

        roi_frames = self.extract_roi_frames(frame)

        best_result = None
        best_confidence = 0.0

        for roi_frame in roi_frames:
            result = await self._detector.detect_scene(roi_frame)
            if result.confidence > best_confidence:
                best_confidence = result.confidence
                best_result = result

        if best_result:
            best_result.method = 'incremental'

        return best_result or DetectionResult(
            scene=SceneState.UNKNOWN,
            confidence=0.0,
            timestamp=time.time(),
            detection_time_ms=0.0,
            method='incremental'
        )


optimized_scene_detector = OptimizedSceneDetector()
