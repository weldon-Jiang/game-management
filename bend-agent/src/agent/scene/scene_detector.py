"""
Scene Detector - Detects Xbox UI states and scenes
"""
import asyncio
from typing import Optional, Dict, List
from enum import Enum

from ..core.logger import get_logger
from ..vision.template_matcher import TemplateMatcher, MatchResult


class SceneState(Enum):
    """Xbox UI scene states"""
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
    Detects Xbox UI scenes using template matching
    Maintains scene state and transitions
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
        """Get current scene state"""
        return self._current_scene

    def set_scene(self, new_scene: SceneState):
        """Manually set scene state"""
        if self._current_scene != new_scene:
            old_scene = self._current_scene
            self._current_scene = new_scene
            self.logger.info(f"Scene changed: {old_scene.value} -> {new_scene.value}")
            self._trigger_callback('scene_changed', new_scene, old_scene)

    def on_scene_changed(self, callback):
        """Register scene change callback"""
        self._callbacks['scene_changed'] = callback

    def _trigger_callback(self, event: str, *args):
        """Trigger registered callback"""
        if event in self._callbacks:
            try:
                self._callbacks[event](*args)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    async def detect_scene(self, frame) -> SceneState:
        """
        Detect current scene from frame

        Args:
            frame: Current video frame (numpy array)

        Returns:
            Detected scene state
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
        Wait for specific scene to appear

        Args:
            frame_getter: Async function that returns current frame
            target_scene: Scene to wait for
            timeout: Maximum wait time
            poll_interval: Time between checks

        Returns:
            True if scene appeared, False if timeout
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
        """Convenience method to wait for home screen"""
        return await self.wait_for_scene(frame_geter, SceneState.HOME, timeout)

    async def wait_for_login(self, frame_getter, timeout: float = 30.0) -> bool:
        """Convenience method to wait for login screen"""
        return await self.wait_for_scene(frame_geter, SceneState.LOGIN, timeout)

    def register_scene_template(self, scene: SceneState, template_name: str):
        """Register additional template for scene detection"""
        if scene not in self._scene_templates:
            self._scene_templates[scene] = []
        if template_name not in self._scene_templates[scene]:
            self._scene_templates[scene].append(template_name)
            self.logger.debug(f"Registered template '{template_name}' for scene '{scene.value}'")
