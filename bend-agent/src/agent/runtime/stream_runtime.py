"""
StreamRuntime — 对齐 streaming StreamWindow 长/短寿命并行模型。

长寿命（Step3→会话结束）：capture 泵（WorkerCapture）、SDL 显示读 latest_frame
短寿命（Step4 自动化）：graph ~1Hz、play ~20Hz；失败时 stop_automation 保留 capture/display
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Optional

import numpy as np

from ..core.logger import get_logger
from ..scene.fc_scene_client import FC_ERR_MATCH_OVER, FC_ERR_NETWORK, FC_ERR_OK
from ..vision.frame_capture import Frame
from ..vision.frame_utils import frame_to_bgr_ndarray

GRAPH_INTERVAL_SEC = 1.0
PLAY_INTERVAL_SEC = 0.05
FRAME_QUEUE_MAX = 5

ApplyFcActionsFn = Callable[[Any, list, Any], Awaitable[None]]
PlayFrameHandler = Callable[[np.ndarray], Awaitable[int]]


class StreamRuntime:
    """单任务串流运行时：统一管理帧泵与 graph/play 自动化标志。"""

    def __init__(self, context: Any):
        self._context = context
        self._logger = get_logger("stream_runtime")
        self.frame_queue: asyncio.Queue = asyncio.Queue(maxsize=FRAME_QUEUE_MAX)
        self.scene_queue: asyncio.Queue = asyncio.Queue(maxsize=FRAME_QUEUE_MAX)
        self._latest_frame: Optional[Frame] = None
        self._capture_task: Optional[asyncio.Task] = None
        self._graph_task: Optional[asyncio.Task] = None
        self._play_task: Optional[asyncio.Task] = None
        self._stop_capture = asyncio.Event()
        self.auto_graph = False
        self.auto_play = False
        self._scene_detector = None
        self._fc_client = None
        self._apply_fc_actions: Optional[ApplyFcActionsFn] = None
        self._play_handler: Optional[PlayFrameHandler] = None
        self._match_over = asyncio.Event()

    @property
    def match_over(self) -> asyncio.Event:
        return self._match_over

    @property
    def is_capture_running(self) -> bool:
        return self._capture_task is not None and not self._capture_task.done()

    @property
    def is_automation_active(self) -> bool:
        return self.auto_graph or self.auto_play

    def is_manual_input_allowed(self) -> bool:
        """InputPump 在人工接管、任务暂停或非 graph/play 时发送 manual。"""
        ctx = self._context
        if getattr(ctx, "_manual_takeover", False):
            return True
        if ctx is not None and hasattr(ctx, "is_paused") and ctx.is_paused():
            return True
        return not self.is_automation_active

    def seed_latest_frame(self, frame: Frame) -> None:
        """Step3 首帧校验通过后写入，避免 SDL 显示泵空窗。"""
        self._latest_frame = frame
        ctx = self._context
        if ctx is not None:
            ctx._stream_video_stale = False

    def invalidate_latest_frame(self) -> None:
        """断流/重连前丢弃缓存，防止 SDL 展示静态旧帧。"""
        self._latest_frame = None

    def get_latest_frame(self) -> Optional[Frame]:
        return self._latest_frame

    def get_latest_image(self) -> Optional[np.ndarray]:
        frame = self._latest_frame
        if frame is None:
            return None
        return frame_to_bgr_ndarray(frame)

    async def wait_for_latest_frame(self, timeout: float = 1.0) -> Optional[Frame]:
        """等待 capture 泵产出首帧/新帧，避免与 capture 泵并发 poll frame_capture。"""
        deadline = time.monotonic() + timeout
        last_id = getattr(self._latest_frame, "frame_id", None)
        while time.monotonic() < deadline:
            frame = self._latest_frame
            if frame is not None and getattr(frame, "frame_id", None) != last_id:
                return frame
            if frame is not None and last_id is None:
                return frame
            await asyncio.sleep(0.05)
        return self._latest_frame

    async def start_long_lived(self, task_logger=None) -> None:
        if self.is_capture_running:
            return
        self._stop_capture.clear()
        log = task_logger or self._logger
        self._capture_task = asyncio.create_task(self._capture_loop(log))
        log.info("StreamRuntime capture 泵已启动")

    async def stop_long_lived(self) -> None:
        await self.stop_automation()
        self._stop_capture.set()
        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass
            self._capture_task = None
        self._latest_frame = None
        self._drain_queue(self.frame_queue)
        self._drain_queue(self.scene_queue)

    async def start_automation(
        self,
        task_logger=None,
        scene_detector=None,
        fc_client=None,
        apply_fc_actions: Optional[ApplyFcActionsFn] = None,
        play_handler: Optional[PlayFrameHandler] = None,
    ) -> None:
        """Step4 入口：确保 capture 运行并启动 graph 循环。"""
        await self.start_long_lived(task_logger)
        self._scene_detector = scene_detector
        self._fc_client = fc_client
        self._apply_fc_actions = apply_fc_actions
        self._play_handler = play_handler
        self.auto_graph = True
        self.auto_play = False
        if self._graph_task and not self._graph_task.done():
            return
        log = task_logger or self._logger
        self._graph_task = asyncio.create_task(self._graph_loop(log))
        log.info("StreamRuntime graph 循环已启动 (auto_graph=True)")

    async def stop_automation(self) -> None:
        """Step4 结束/失败：仅停 graph/play，保留 capture/display。"""
        self.auto_graph = False
        self.auto_play = False
        for attr in ("_graph_task", "_play_task"):
            task = getattr(self, attr)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            setattr(self, attr, None)

    def enter_play_mode(self) -> None:
        """进入比赛：停 graph、启 play（对齐 streaming auto_play）。"""
        self.auto_graph = False
        self.auto_play = True
        self._match_over.clear()
        if self._play_task is None or self._play_task.done():
            self._play_task = asyncio.create_task(self._play_loop(self._logger))

    def exit_play_mode(self) -> None:
        """比赛结束：停 play、恢复 graph。"""
        self.auto_play = False
        self.auto_graph = True
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
            self._play_task = None

    async def _capture_loop(self, task_logger) -> None:
        while not self._stop_capture.is_set():
            try:
                capture = getattr(self._context, "frame_capture", None)
                if capture is None:
                    await asyncio.sleep(0.1)
                    continue
                frame = await capture.capture_frame()
                if frame is not None:
                    img = frame_to_bgr_ndarray(frame)
                    if img is None:
                        await asyncio.sleep(0.05)
                        continue
                    if getattr(frame, "data", None) is not img:
                        frame = Frame(
                            data=img,
                            frame_id=frame.frame_id,
                            timestamp=frame.timestamp,
                            width=img.shape[1],
                            height=img.shape[0],
                            fps=getattr(frame, "fps", 0.0),
                        )
                    self._latest_frame = frame
                    try:
                        from ..xbox.stream_liveness_monitor import touch_video_frame_at

                        touch_video_frame_at(self._context)
                    except Exception:
                        pass
                    await self._offer_queue(self.frame_queue, frame)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                task_logger.debug("StreamRuntime capture: %s", exc)
                await asyncio.sleep(0.05)

    async def _graph_loop(self, task_logger) -> None:
        while True:
            try:
                await asyncio.sleep(GRAPH_INTERVAL_SEC)
                if not self.auto_graph:
                    continue
                image = self.get_latest_image()
                if image is None:
                    continue
                scene_label = await self._recognize_scene(image, task_logger)
                await self._offer_queue(self.scene_queue, scene_label)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                task_logger.debug("StreamRuntime graph: %s", exc)

    async def _play_loop(self, task_logger) -> None:
        play_tp = time.monotonic()
        while True:
            try:
                if not self.auto_play:
                    await asyncio.sleep(PLAY_INTERVAL_SEC)
                    continue
                ctx = self._context
                if (
                    ctx is not None
                    and hasattr(ctx, "is_paused")
                    and ctx.is_paused()
                ):
                    await asyncio.sleep(PLAY_INTERVAL_SEC)
                    continue
                elapsed = time.monotonic() - play_tp
                if elapsed < PLAY_INTERVAL_SEC:
                    await asyncio.sleep(PLAY_INTERVAL_SEC - elapsed)
                handler = self._play_handler
                image = self.get_latest_image()
                if handler and image is not None:
                    errno = await handler(image)
                    if errno == FC_ERR_MATCH_OVER:
                        self._match_over.set()
                        self.exit_play_mode()
                    elif errno == FC_ERR_NETWORK:
                        self.auto_play = False
                        self.auto_graph = False
                play_tp = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                task_logger.debug("StreamRuntime play: %s", exc)
                await asyncio.sleep(PLAY_INTERVAL_SEC)

    async def _recognize_scene(self, image: np.ndarray, task_logger) -> str:
        if self._fc_client:
            scene_id, actions = await self._fc_client.recognize_scene_id(image)
            if actions and self._apply_fc_actions:
                await self._apply_fc_actions(self._context, actions, task_logger)
            if scene_id >= 0:
                from ..input.manual_nav import update_last_streaming_scene_id

                update_last_streaming_scene_id(self._context, scene_id)
                return str(scene_id)
            return "UNKNOWN"

        detector = self._scene_detector
        if detector is None:
            return "UNKNOWN"

        try:
            from ..vision.template_manager import STEP4_REQUIRED_SCENE_IDS

            candidate_ids = list(STEP4_REQUIRED_SCENE_IDS)
        except Exception:
            candidate_ids = []

        if not candidate_ids:
            return "UNKNOWN"

        try:
            result = detector.recognize_scenes_batch(image, candidate_ids)
            if result.matched and result.scene_id > 0:
                from ..input.manual_nav import update_last_streaming_scene_id

                update_last_streaming_scene_id(self._context, result.scene_id)
                return str(result.scene_id)
        except Exception as exc:
            task_logger.debug("StreamRuntime scene detect: %s", exc)
        return "UNKNOWN"

    @staticmethod
    async def _offer_queue(queue: asyncio.Queue, item: Any) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(item)
        except asyncio.QueueFull:
            pass

    @staticmethod
    def _drain_queue(queue: asyncio.Queue) -> None:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break


def get_or_create_stream_runtime(context: Any) -> StreamRuntime:
    runtime = getattr(context, "_stream_runtime", None)
    if runtime is None:
        runtime = StreamRuntime(context)
        context._stream_runtime = runtime
    return runtime


async def capture_task_frame(context: Any, timeout: float = 1.0) -> Optional[Frame]:
    """
    从 StreamRuntime 读取帧，避免与 capture 泵并发 poll frame_capture。

    无 runtime 或未启动 capture 时回退到 frame_capture.capture_frame()。
    """
    runtime = getattr(context, "_stream_runtime", None)
    if runtime and runtime.is_capture_running:
        return await runtime.wait_for_latest_frame(timeout)
    capture = getattr(context, "frame_capture", None)
    if capture is None:
        return None
    return await capture.capture_frame()
