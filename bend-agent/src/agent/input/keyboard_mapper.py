"""
键盘到手柄映射模块
==================

功能说明：
- 将键盘按键映射为Xbox手柄动作
- 支持WASD移动、鼠标视角等映射
- 配置文件驱动，易于自定义

技术实现参考（streaming项目）：
- keybinding.csv

作者：技术团队
版本：1.0
"""

import asyncio
import sys
import pygame
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Callable, Set
from enum import Enum

from ..core.logger import get_logger
from ..core.paths import get_config_path
from .keyboard_mapping_defaults import DEFAULT_KEYBOARD_BINDINGS


class KeyAction(Enum):
    """按键动作枚举"""
    TAP_A = "TAP_A"
    TAP_B = "TAP_B"
    TAP_X = "TAP_X"
    TAP_Y = "TAP_Y"
    TAP_START = "TAP_START"
    TAP_SELECT = "TAP_SELECT"
    TAP_L1 = "TAP_L1"
    TAP_R1 = "TAP_R1"
    MOVE_UP = "MOVE_UP"
    MOVE_DOWN = "MOVE_DOWN"
    MOVE_LEFT = "MOVE_LEFT"
    MOVE_RIGHT = "MOVE_RIGHT"
    LOOK_UP = "LOOK_UP"
    LOOK_DOWN = "LOOK_DOWN"
    LOOK_LEFT = "LOOK_LEFT"
    LOOK_RIGHT = "LOOK_RIGHT"


# Windows 物理键轮询（绕过中文 IME 吞 pygame 字母键）
_WIN32_VK_BY_BINDING_KEY = {
    "w": 0x57,
    "a": 0x41,
    "s": 0x53,
    "d": 0x44,
    "j": 0x4A,
    "b": 0x42,
    "x": 0x58,
    "y": 0x59,
    "q": 0x51,
    "e": 0x45,
    "return": 0x0D,
    "escape": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
}

_PYGAME_KEY_BY_BINDING = {
    "w": pygame.K_w,
    "s": pygame.K_s,
    "a": pygame.K_a,
    "d": pygame.K_d,
    "j": pygame.K_j,
    "b": pygame.K_b,
    "x": pygame.K_x,
    "y": pygame.K_y,
    "q": pygame.K_q,
    "e": pygame.K_e,
    "return": pygame.K_RETURN,
    "escape": pygame.K_ESCAPE,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
}


# 人工 WASD：仅发 DPAD（对齐 streaming/xsrputil TapController，不发左摇杆）。
# Xbox 系统 UI 只认十字键；双发 DPAD+摇杆会导致列表/焦点异常跳动。
def _move_dpad_button(action: KeyAction):
    from .controller_protocol import XboxButtonFlag

    return {
        KeyAction.MOVE_UP: XboxButtonFlag.DPAD_UP,
        KeyAction.MOVE_DOWN: XboxButtonFlag.DPAD_DOWN,
        KeyAction.MOVE_LEFT: XboxButtonFlag.DPAD_LEFT,
        KeyAction.MOVE_RIGHT: XboxButtonFlag.DPAD_RIGHT,
    }.get(action)


def _action_button_map():
    from .controller_protocol import XboxButtonFlag

    return {
        KeyAction.TAP_A: XboxButtonFlag.A,
        KeyAction.TAP_B: XboxButtonFlag.B,
        KeyAction.TAP_X: XboxButtonFlag.X,
        KeyAction.TAP_Y: XboxButtonFlag.Y,
        KeyAction.TAP_START: XboxButtonFlag.START,
        KeyAction.TAP_SELECT: XboxButtonFlag.VIEW,
        KeyAction.TAP_L1: XboxButtonFlag.L1,
        KeyAction.TAP_R1: XboxButtonFlag.R1,
    }


@dataclass
class KeyBinding:
    """按键绑定配置"""
    key: str
    action: KeyAction
    holdable: bool = True


class KeyboardMapper:
    """
    键盘到手柄动作映射器

    功能说明：
    - 监听键盘事件
    - 将键盘按键映射为手柄动作
    - 支持按住不放的持续动作

    使用方式：
    - 创建实例后调用 start() 开始监听
    - 使用 register_action_callback() 注册动作回调
    - 调用 stop() 停止监听
    """

    # WASD → 方向键；J/B/X/Y → 手柄面键（A 不与左方向共用 a，pygame 键名为小写单字母）
    DEFAULT_BINDINGS = {
        'j': KeyAction.TAP_A,
        'b': KeyAction.TAP_B,
        'x': KeyAction.TAP_X,
        'y': KeyAction.TAP_Y,
        'return': KeyAction.TAP_START,
        'escape': KeyAction.TAP_SELECT,
        'q': KeyAction.TAP_L1,
        'e': KeyAction.TAP_R1,
        'w': KeyAction.MOVE_UP,
        's': KeyAction.MOVE_DOWN,
        'a': KeyAction.MOVE_LEFT,
        'd': KeyAction.MOVE_RIGHT,
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        bindings: Optional[Dict[str, str]] = None,
    ):
        self.logger = get_logger('keyboard_mapper')
        self.config_path = config_path
        self._initial_bindings = bindings
        self._bindings: Dict[str, KeyAction] = {}
        self._pressed_keys: set = set()
        self._action_callbacks: List[Callable[[KeyAction, bool], None]] = []
        self._hotkey_callbacks: Dict[str, Callable[[], None]] = {}
        self._running = False
        self._input_task: Optional[asyncio.Task] = None
        self._on_window_close: Optional[Callable[[], None]] = None
        # SDL 显示泵独占 pygame.event.get 时，由 SDLWindow.process_events 转发键盘事件
        self._external_event_pump = False
        # F8 人工接管且串流窗口获焦时启用 Win32 轮询（绕过 IME；无焦点时不轮询防误触）
        self._allow_focused_win32_poll = False
        self._manual_face_hold = False
        self._manual_wasd_stick = True
        self._pygame_poll_map: Dict[int, str] = {}
        self._overlay_refresh_fn: Optional[Callable[[], None]] = None
        self._holdable_actions: set = {
            KeyAction.MOVE_UP, KeyAction.MOVE_DOWN,
            KeyAction.MOVE_LEFT, KeyAction.MOVE_RIGHT,
            KeyAction.LOOK_UP, KeyAction.LOOK_DOWN,
            KeyAction.LOOK_LEFT, KeyAction.LOOK_RIGHT
        }
        self._face_hold_actions: set = {
            KeyAction.TAP_A, KeyAction.TAP_B,
            KeyAction.TAP_X, KeyAction.TAP_Y,
            KeyAction.TAP_START, KeyAction.TAP_SELECT,
            KeyAction.TAP_L1, KeyAction.TAP_R1,
        }
        self._load_bindings()

    def _load_bindings(self):
        """加载按键绑定：显式 bindings > YAML 文件 > 平台缓存/默认。"""
        if self._initial_bindings:
            self._apply_binding_dict(self._initial_bindings, source="platform/runtime")
            return

        if self.config_path:
            try:
                import yaml
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)

                bindings_config = config.get('keyboard_mapping', {}).get('bindings', {})
                if bindings_config:
                    self._apply_binding_dict(bindings_config, source=f"file:{self.config_path}")
                    return
            except Exception as e:
                self.logger.warning(f"加载配置文件失败: {e}")

        try:
            from .agent_keyboard_config import get_effective_keyboard_bindings
            self._apply_binding_dict(get_effective_keyboard_bindings(), source="platform/default")
        except Exception:
            self._bindings = self._dict_to_key_actions(self.DEFAULT_BINDINGS)
            self.logger.info("使用内置默认按键绑定")
            self._rebuild_pygame_poll_map()

    def _dict_to_key_actions(self, raw: Dict) -> Dict[str, KeyAction]:
        result: Dict[str, KeyAction] = {}
        for key, action in raw.items():
            try:
                if isinstance(action, KeyAction):
                    result[str(key).lower()] = action
                else:
                    result[str(key).lower()] = KeyAction(str(action))
            except ValueError:
                self.logger.warning("Unknown action: %s", action)
        return result

    def _apply_binding_dict(self, raw: Dict[str, str], *, source: str) -> None:
        parsed = self._dict_to_key_actions(raw)
        if not parsed:
            parsed = self._dict_to_key_actions(self.DEFAULT_BINDINGS)
        self._bindings = parsed
        self.logger.info("键盘映射已加载 (%s, %d 项)", source, len(self._bindings))
        self._rebuild_pygame_poll_map()

    def _rebuild_pygame_poll_map(self) -> None:
        self._pygame_poll_map: Dict[int, str] = {}
        for name, key_const in _PYGAME_KEY_BY_BINDING.items():
            if name in self._bindings:
                self._pygame_poll_map[key_const] = name

    def _poll_win32_binding_keys(self) -> Set[str]:
        if sys.platform != "win32":
            return set()
        active: Set[str] = set()
        try:
            import ctypes

            user32 = ctypes.windll.user32
            for name, vk in _WIN32_VK_BY_BINDING_KEY.items():
                if name not in self._bindings:
                    continue
                if user32.GetAsyncKeyState(vk) & 0x8000:
                    active.add(name)
        except Exception as exc:
            self.logger.debug("Win32 键位轮询失败: %s", exc)
        return active

    def _poll_pygame_binding_keys(self) -> Set[str]:
        active: Set[str] = set()
        poll_map = getattr(self, "_pygame_poll_map", None)
        if not poll_map:
            return active
        try:
            pressed = pygame.key.get_pressed()
            for key_const, name in poll_map.items():
                if pressed[key_const]:
                    active.add(name)
        except Exception as exc:
            self.logger.debug("pygame 键位轮询失败: %s", exc)
        return active

    def _iter_active_binding_keys(self) -> Set[str]:
        """
        合并按键状态供 InputPump 采样。

        SDL 窗口转发路径（external_event_pump）仅信任 feed_pygame_event 写入的
        _pressed_keys；禁止 Win32/pygame 全局轮询，否则焦点外误报 W/S 导致菜单乱跳。
        """
        keys = {str(k).lower() for k in self._pressed_keys if str(k).lower() in self._bindings}
        if not self._external_event_pump:
            keys |= self._poll_win32_binding_keys()
            keys |= self._poll_pygame_binding_keys()
        elif self._allow_focused_win32_poll:
            keys |= self._poll_win32_binding_keys()
        for hotkey in self._hotkey_callbacks:
            keys.discard(hotkey.lower())
        return keys

    def set_manual_face_hold(self, enabled: bool) -> None:
        """F8 人工接管：J/B/X/Y 等面键随物理键按住，不再 100ms 自动松键。"""
        self._manual_face_hold = bool(enabled)
        if not enabled:
            to_clear = [
                k for k, a in self._bindings.items()
                if a in self._face_hold_actions
            ]
            for key in to_clear:
                self._pressed_keys.discard(key)

    def set_manual_wasd_stick(self, enabled: bool) -> None:
        """F8 人工：WASD 映射左摇杆（比赛内）；False 时映射 DPad（菜单）。"""
        self._manual_wasd_stick = bool(enabled)

    def _resolve_manual_wasd_stick(self) -> bool:
        if not self._manual_face_hold:
            return False
        return self._manual_wasd_stick

    def _apply_movement_from_actions(self, signal, active: Set[str]) -> None:
        """WASD/方向键 → 左摇杆或 DPad（由 manual_wasd_stick 决定）。"""
        lx = ly = 0.0
        for key in active:
            action = self._bindings.get(key)
            if action == KeyAction.MOVE_UP:
                ly = 1.0
            elif action == KeyAction.MOVE_DOWN:
                ly = -1.0
            elif action == KeyAction.MOVE_LEFT:
                lx = -1.0
            elif action == KeyAction.MOVE_RIGHT:
                lx = 1.0
        if lx and ly:
            lx *= 0.70710678
            ly *= 0.70710678

        if self._resolve_manual_wasd_stick():
            if lx or ly:
                signal.set_thumb("left", lx, ly)
            return

        dpad_btn = None
        if ly > 0:
            dpad_btn = _move_dpad_button(KeyAction.MOVE_UP)
        elif ly < 0:
            dpad_btn = _move_dpad_button(KeyAction.MOVE_DOWN)
        if lx < 0:
            signal.set_button(_move_dpad_button(KeyAction.MOVE_LEFT), True)
        elif lx > 0:
            signal.set_button(_move_dpad_button(KeyAction.MOVE_RIGHT), True)
        if dpad_btn is not None:
            signal.set_button(dpad_btn, True)

    def _is_holdable_action(self, action: Optional[KeyAction]) -> bool:
        if action is None:
            return False
        if action in self._holdable_actions:
            return True
        if self._manual_face_hold and action in self._face_hold_actions:
            return True
        return False

    def set_overlay_refresh(self, callback: Optional[Callable[[], None]]) -> None:
        """InputPump 轮询时全量重建 overlay（WASD→DPAD + 面键）。"""
        self._overlay_refresh_fn = callback

    def apply_active_keys_to_signal(self, signal) -> None:
        """将当前按下的映射键写入 ControllerSignal。"""
        active = self._iter_active_binding_keys()
        self._apply_movement_from_actions(signal, active)
        action_map = _action_button_map()
        for key in active:
            action = self._bindings.get(key)
            if not action:
                continue
            if action in (
                KeyAction.MOVE_UP,
                KeyAction.MOVE_DOWN,
                KeyAction.MOVE_LEFT,
                KeyAction.MOVE_RIGHT,
            ):
                continue
            btn = action_map.get(action)
            if btn is not None:
                signal.set_button(btn, True)

    def sync_overlay_from_poll(self) -> None:
        """按物理键轮询结果刷新 overlay，与 build_controller_signal 保持一致。"""
        if self._overlay_refresh_fn is not None:
            try:
                self._overlay_refresh_fn()
            except Exception as exc:
                self.logger.error("overlay 轮询刷新失败: %s", exc)
            return
        if not self._action_callbacks:
            return
        active = self._iter_active_binding_keys()
        action_map = _action_button_map()
        for key_name, action in self._bindings.items():
            btn = action_map.get(action)
            if btn is None:
                continue
            is_pressed = key_name in active
            for callback in self._action_callbacks:
                try:
                    callback(action, is_pressed)
                except Exception as exc:
                    self.logger.error("overlay 轮询同步失败 (%s): %s", key_name, exc)

    def apply_bindings(self, raw: Dict[str, str]) -> None:
        """热更新键位（平台保存或 WS 推送后调用）。"""
        self._pressed_keys.clear()
        self._apply_binding_dict(raw or DEFAULT_KEYBOARD_BINDINGS, source="hot-reload")
        self._rebuild_pygame_poll_map()

    def register_hotkey(self, key_name: str, callback: Callable[[], None]) -> None:
        """注册调试/功能热键（不参与手柄映射，单次 KEYDOWN 触发）。"""
        self._hotkey_callbacks[key_name.lower()] = callback

    def set_window_close_handler(self, handler: Optional[Callable[[], None]]) -> None:
        """用户点击 SDL 窗口关闭按钮时调用（隐藏，非退出进程）。"""
        self._on_window_close = handler

    def set_external_event_pump(self, enabled: bool) -> None:
        """启用后不再轮询 pygame.event.get，改由 SDL 窗口 process_events 转发。"""
        self._external_event_pump = bool(enabled)
        if not enabled:
            self._allow_focused_win32_poll = False
        if enabled:
            self.logger.debug("键盘事件改由 SDL 窗口转发")
        else:
            self.logger.debug("键盘事件恢复 KeyboardMapper 轮询")

    def set_focused_win32_poll(self, enabled: bool) -> None:
        """SDL 转发模式下，仅在前台获焦时启用 Win32 物理键轮询（F8 人工输入）。"""
        self._allow_focused_win32_poll = bool(enabled)

    def feed_pygame_event(self, event: Any) -> bool:
        """
        处理 SDL 窗口转发的 pygame 事件（避免与显示泵双消费 event queue）。

        返回 True 表示 KEYDOWN/KEYUP/QUIT 已由本模块处理。
        """
        if not self._running:
            return False

        try:
            if event.type == pygame.QUIT:
                if self._on_window_close:
                    try:
                        self._on_window_close()
                    except Exception as exc:
                        self.logger.warning("窗口关闭回调失败: %s", exc)
                return True

            if event.type == pygame.KEYDOWN:
                key_name = pygame.key.name(event.key).lower()
                if key_name not in self._pressed_keys:
                    self._pressed_keys.add(key_name)
                    if key_name.lower() in self._hotkey_callbacks:
                        self._schedule_key_handler(self._handle_key_press(key_name))
                    else:
                        self._apply_action_sync(key_name, True)
                        action = self._bindings.get(key_name.lower())
                        if action and not self._is_holdable_action(action):
                            self._schedule_key_handler(
                                self._auto_tap_release(key_name, action)
                            )
                return True

            if event.type == pygame.KEYUP:
                key_name = pygame.key.name(event.key).lower()
                if key_name in self._pressed_keys:
                    self._pressed_keys.discard(key_name)
                    if key_name.lower() not in self._hotkey_callbacks:
                        self._apply_action_sync(key_name, False)
                    else:
                        self._schedule_key_handler(self._handle_key_release(key_name))
                return True
        except Exception as exc:
            self.logger.error("转发键盘事件异常: %s", exc)

        return False

    def _schedule_key_handler(self, coro) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            self.logger.warning("无运行中事件循环，跳过异步键处理")

    def _apply_action_sync(self, key_name: str, pressed: bool) -> None:
        """同步更新 overlay（SDL process_events 路径须立即生效，不能等 async 任务）。"""
        action = self._bindings.get(key_name.lower())
        if action is None:
            return
        for callback in self._action_callbacks:
            try:
                callback(action, pressed)
            except Exception as exc:
                self.logger.error("同步键位回调异常 (%s): %s", key_name, exc)

    async def _auto_tap_release(self, key_name: str, action: KeyAction) -> None:
        """面键短按：保持约 100ms 后释放。"""
        await asyncio.sleep(0.1)
        if key_name in self._pressed_keys:
            self._pressed_keys.discard(key_name)
        self._apply_action_sync(key_name, False)

    def register_action_callback(self, callback: Callable[[KeyAction, bool], None]):
        """
        注册动作回调函数

        参数：
        - callback: 回调函数，参数为 (action, is_pressed)
        """
        self._action_callbacks.append(callback)

    async def start(self):
        """开始监听键盘事件"""
        if self._running:
            return

        try:
            pygame.init()
            # 若 step3 已创建 SDL 串流窗口则复用
            if pygame.display.get_surface() is None:
                pygame.display.set_mode((1, 1), pygame.NOFRAME)
        except Exception:
            pass

        self._running = True
        self._input_task = asyncio.create_task(self._keyboard_loop())
        self.logger.info("键盘映射已启动")

    async def _keyboard_loop(self):
        """键盘事件循环；SDL 窗口活跃时由 feed_pygame_event 接管，此处仅保活。"""
        while self._running:
            try:
                if not self._external_event_pump:
                    for event in pygame.event.get():
                        if self.feed_pygame_event(event):
                            continue
                        # 未识别事件交还队列（如 SDL 自定义回调）
                        try:
                            pygame.event.post(event)
                        except Exception:
                            pass

                await asyncio.sleep(0.016)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"键盘事件处理异常: {e}")

    async def _handle_key_press(self, key_name: str):
        """处理按键按下"""
        hotkey = self._hotkey_callbacks.get(key_name.lower())
        if hotkey is not None:
            try:
                hotkey()
            except Exception as e:
                self.logger.error(f"热键回调异常 ({key_name}): {e}")
            return

        action = self._bindings.get(key_name.lower())
        if action:
            self.logger.debug(f"Key pressed: {key_name} -> {action.value}")
            for callback in self._action_callbacks:
                try:
                    callback(action, True)
                except Exception as e:
                    self.logger.error(f"回调异常: {e}")

            if not self._is_holdable_action(action):
                await asyncio.sleep(0.1)
                self._pressed_keys.discard(key_name)
                for callback in self._action_callbacks:
                    try:
                        callback(action, False)
                    except Exception as e:
                        self.logger.error(f"回调异常: {e}")

    async def _handle_key_release(self, key_name: str):
        """处理按键释放"""
        action = self._bindings.get(key_name.lower())
        if action and self._is_holdable_action(action):
            self.logger.debug(f"Key released: {key_name}")
            for callback in self._action_callbacks:
                try:
                    callback(action, False)
                except Exception as e:
                    self.logger.error(f"回调异常: {e}")

    async def stop(self):
        """停止监听"""
        self._running = False
        self._external_event_pump = False

        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass

        # 勿调用 pygame.display.quit()，会销毁 SDL 串流窗口
        self.logger.info("键盘映射已停止")

    def map_key_to_action(self, key: str) -> Optional[KeyAction]:
        """
        将键盘按键映射为动作

        参数：
        - key: 键盘按键名称

        返回值：
        - KeyAction或None
        """
        return self._bindings.get(key.lower())

    def get_all_bindings(self) -> Dict[str, KeyAction]:
        """获取所有按键绑定"""
        return self._bindings.copy()

    def build_controller_signal(self):
        """根据物理键轮询 + 事件队列合成 ControllerSignal（供 InputPump 125Hz 采样）。"""
        from .controller_protocol import ControllerSignal

        signal = ControllerSignal()
        self.apply_active_keys_to_signal(signal)
        return signal


keyboard_mapper = KeyboardMapper()
