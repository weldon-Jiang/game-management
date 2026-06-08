"""
VisionService — 统一解码管线与 TemplateMatcher API。

帧仅来自 WebRTC/GPU 解码；绝不来自 SDL 窗口后缓冲。
"""

from typing import Any, Callable, List, Optional

from ..core.config import config
from ..core.logger import get_logger
from .decode_strategy import resolve_decode_mode, release_decode_slot
from ..scene.streaming_scene_detector import StreamingSceneDetector


class TemplateMatcher:
    """step4 与 account_provisioning 的统一模板匹配。"""

    def __init__(
        self,
        template_dir: Optional[str] = None,
        threshold: Optional[float] = None,
    ):
        self.logger = get_logger("template_matcher")
        if template_dir:
            resolved_dir = template_dir
        else:
            from ..core.paths import get_templates_dir, resolve_agent_path
            configured = config.get("template.template_dir", "./templates")
            if configured in ("./templates", "templates"):
                resolved_dir = get_templates_dir()
            else:
                resolved_dir = str(resolve_agent_path(configured))
        template_dir = resolved_dir
        threshold = threshold if threshold is not None else float(
            config.get("template.threshold", 0.8)
        )
        self._detector = StreamingSceneDetector(
            template_dir=template_dir,
            default_threshold=threshold,
        )

    def preload(self, scene_ids: Optional[List[int]] = None) -> None:
        """预热指定场景模板缓存（否则首次匹配时懒加载）。"""
        self.logger.debug("Template preload requested for %s", scene_ids or "all")

    def recognize_scene(self, frame: Any, scene_id: Optional[int] = None):
        return self._detector.recognize_scene(frame, scene_id=scene_id)

    def recognize_scenes(self, frame: Any, scene_ids: List[int]):
        return [self._detector.recognize_scene(frame, scene_id=sid) for sid in scene_ids]

    async def wait_for_scene(
        self,
        frame_source: Callable[[], Any],
        scene_id: int,
        timeout: float = 30.0,
        interval: float = 0.5,
    ) -> bool:
        import asyncio
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = frame_source()
            if frame is not None:
                result = self._detector.recognize_scene(frame, scene_id=scene_id)
                if result and result.matched:
                    return True
            await asyncio.sleep(interval)
        return False


class VisionPipeline:
    """解码 + 帧源；显示窗口已解耦。"""

    def __init__(self, mode: str = "auto"):
        self.logger = get_logger("vision_pipeline")
        self.decode_mode = resolve_decode_mode(mode)
        self._frame_capture = None

    def attach_frame_capture(self, capture: Any) -> None:
        self._frame_capture = capture

    def get_frame(self) -> Any:
        if self._frame_capture is None:
            return None
        if hasattr(self._frame_capture, "get_latest_frame"):
            return self._frame_capture.get_latest_frame()
        if hasattr(self._frame_capture, "capture_frame"):
            return self._frame_capture.capture_frame()
        return None

    def release(self) -> None:
        release_decode_slot(self.decode_mode)


class VisionService:
    """VisionPipeline 与 TemplateMatcher 工厂。"""

    @staticmethod
    def create_pipeline(mode: str = "auto") -> VisionPipeline:
        requested = mode or config.get("vision.decode_mode", "auto")
        return VisionPipeline(requested)

    @staticmethod
    def create_matcher(**kwargs) -> TemplateMatcher:
        return TemplateMatcher(**kwargs)
