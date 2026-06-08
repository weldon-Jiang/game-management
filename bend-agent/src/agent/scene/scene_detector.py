"""
场景检测器 — 检测 Xbox UI 状态与场景。
"""
import asyncio
from typing import Optional, Dict, List
from enum import Enum

from ..core.logger import get_logger
from ..vision.template_matcher import TemplateMatcher, MatchResult


class SceneState(Enum):
    """Xbox UI 场景状态"""
    UNKNOWN = "unknown"
    HOME = "home"
    LOGIN = "login"
    GAME_HUB = "game_hub"
    GAME_PLAYING = "game_playing"
    SETTINGS = "settings"
    STORE = "store"
    SOCIAL = "social"
    PARTIES = "parties"
    GUIDE = "guide"


class SceneDetector:
    """
    使用模板匹配检测 Xbox UI 场景。
    维护场景状态与迁移。
    """

    def __init__(self, template_matcher: TemplateMatcher):
        self.matcher = template_matcher
        self._current_scene = SceneState.UNKNOWN
        self._scene_templates: Dict[SceneState, List[str]] = {
            SceneState.HOME: ['xbox_home.png', 'xbox_home_button.png'],
            SceneState.LOGIN: ['xbox_login.png', 'xbox_signin.png', 'account_picker.png'],
            SceneState.GAME_HUB: ['game_hub.png', 'my_games.png', 'achievements.png'],
            SceneState.GAME_PLAYING: ['playing.png', 'now_playing.png'],
            SceneState.SETTINGS: ['settings.png', 'system_settings.png'],
            SceneState.STORE: ['store.png', 'microsoft_store.png'],
            SceneState.SOCIAL: ['friends.png', 'social.png'],
            SceneState.PARTIES: ['party.png', 'parties.png', 'chat.png'],
            SceneState.GUIDE: ['guide.png', 'xbox_guide.png'],
        }
        self._callbacks: Dict[str, callable] = {}
        self.logger = get_logger('scene')

    @property
    def current_scene(self) -> SceneState:
        """获取当前场景状态"""
        return self._current_scene

    def set_scene(self, new_scene: SceneState):
        """手动设置场景状态"""
        if self._current_scene != new_scene:
            old_scene = self._current_scene
            self._current_scene = new_scene
            self.logger.info(f"Scene changed: {old_scene.value} -> {new_scene.value}")
            self._trigger_callback('scene_changed', new_scene, old_scene)

    def on_scene_changed(self, callback):
        """注册场景变更回调"""
        self._callbacks['scene_changed'] = callback

    def _trigger_callback(self, event: str, *args):
        """触发已注册回调"""
        if event in self._callbacks:
            try:
                self._callbacks[event](*args)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    async def detect_scene(self, frame) -> SceneState:
        """
        从帧检测当前场景。

        参数:
            frame: 当前视频帧（numpy 数组）

        返回:
            检测到的场景状态
        """
        best_match = None
        best_confidence = 0.0

        for scene, templates in self._scene_templates.items():
            for template_name in templates:
                result = await self.matcher.find_template(frame, template_name)
                if result.found and result.confidence > best_confidence:
                    best_match = scene
                    best_confidence = result.confidence

        if best_match and best_confidence > self.matcher._threshold:
            if best_match != self._current_scene:
                self.set_scene(best_match)
            return best_match

        return self._current_scene

    async def wait_for_scene(
        self,
        frame_getter,
        target_scene: SceneState,
        timeout: float = 30.0,
        poll_interval: float = 1.0
    ) -> bool:
        """
        等待指定场景出现。

        参数:
            frame_getter: 返回当前帧的异步函数
            target_scene: 等待的目标场景
            timeout: 最长等待时间
            poll_interval: 轮询间隔

        返回:
            场景出现为 True，超时为 False
        """
        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            frame = await frame_getter()
            if frame is not None:
                current = await self.detect_scene(frame)
                if current == target_scene:
                    return True
            await asyncio.sleep(poll_interval)

        self.logger.debug(f"Scene '{target_scene.value}' not detected within {timeout}s")
        return False

    async def wait_for_home(self, frame_getter, timeout: float = 30.0) -> bool:
        """等待主页的便捷方法"""
        return await self.wait_for_scene(frame_geter, SceneState.HOME, timeout)

    async def wait_for_login(self, frame_getter, timeout: float = 30.0) -> bool:
        """等待登录页的便捷方法"""
        return await self.wait_for_scene(frame_geter, SceneState.LOGIN, timeout)

    def register_scene_template(self, scene: SceneState, template_name: str):
        """为场景检测注册额外模板"""
        if scene not in self._scene_templates:
            self._scene_templates[scene] = []
        if template_name not in self._scene_templates[scene]:
            self._scene_templates[scene].append(template_name)
            self.logger.debug(f"Registered template '{template_name}' for scene '{scene.value}'")
