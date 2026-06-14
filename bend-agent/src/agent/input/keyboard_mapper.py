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
import pygame
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Callable
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
        self._holdable_actions: set = {
            KeyAction.MOVE_UP, KeyAction.MOVE_DOWN,
            KeyAction.MOVE_LEFT, KeyAction.MOVE_RIGHT,
            KeyAction.LOOK_UP, KeyAction.LOOK_DOWN,
            KeyAction.LOOK_LEFT, KeyAction.LOOK_RIGHT
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

    def apply_bindings(self, raw: Dict[str, str]) -> None:
        """热更新键位（平台保存或 WS 推送后调用）。"""
        self._pressed_keys.clear()
        self._apply_binding_dict(raw or DEFAULT_KEYBOARD_BINDINGS, source="hot-reload")

    def register_hotkey(self, key_name: str, callback: Callable[[], None]) -> None:
        """注册调试/功能热键（不参与手柄映射，单次 KEYDOWN 触发）。"""
        self._hotkey_callbacks[key_name.lower()] = callback

    def set_window_close_handler(self, handler: Optional[Callable[[], None]]) -> None:
        """用户点击 SDL 窗口关闭按钮时调用（隐藏，非退出进程）。"""
        self._on_window_close = handler

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
        """键盘事件循环"""
        while self._running:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        if self._on_window_close:
                            try:
                                self._on_window_close()
                            except Exception as exc:
                                self.logger.warning("窗口关闭回调失败: %s", exc)
                        else:
                            # 未绑定关窗回调时交还给 SDL 窗口 process_events 处理
                            try:
                                pygame.event.post(event)
                            except Exception:
                                pass
                        continue
                    if event.type == pygame.KEYDOWN:
                        key_name = pygame.key.name(event.key)
                        if key_name not in self._pressed_keys:
                            self._pressed_keys.add(key_name)
                            await self._handle_key_press(key_name)
                    elif event.type == pygame.KEYUP:
                        key_name = pygame.key.name(event.key)
                        if key_name in self._pressed_keys:
                            self._pressed_keys.discard(key_name)
                            await self._handle_key_release(key_name)

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

            if action not in self._holdable_actions:
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
        if action and action in self._holdable_actions:
            self.logger.debug(f"Key released: {key_name}")
            for callback in self._action_callbacks:
                try:
                    callback(action, False)
                except Exception as e:
                    self.logger.error(f"回调异常: {e}")

    async def stop(self):
        """停止监听"""
        self._running = False

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
        """根据当前按住键合成 ControllerSignal（供 InputPump 轮询）。"""
        from .controller_protocol import ControllerSignal, XboxButtonFlag

        signal = ControllerSignal()
        for key in self._pressed_keys:
            action = self._bindings.get(key.lower())
            if not action:
                continue
            mapping = {
                KeyAction.TAP_A: XboxButtonFlag.A,
                KeyAction.TAP_B: XboxButtonFlag.B,
                KeyAction.TAP_X: XboxButtonFlag.X,
                KeyAction.TAP_Y: XboxButtonFlag.Y,
                KeyAction.TAP_START: XboxButtonFlag.START,
                KeyAction.TAP_SELECT: XboxButtonFlag.VIEW,
                KeyAction.TAP_L1: XboxButtonFlag.L1,
                KeyAction.TAP_R1: XboxButtonFlag.R1,
                KeyAction.MOVE_UP: XboxButtonFlag.DPAD_UP,
                KeyAction.MOVE_DOWN: XboxButtonFlag.DPAD_DOWN,
                KeyAction.MOVE_LEFT: XboxButtonFlag.DPAD_LEFT,
                KeyAction.MOVE_RIGHT: XboxButtonFlag.DPAD_RIGHT,
            }
            btn = mapping.get(action)
            if btn:
                signal.set_button(btn, True)
        return signal


keyboard_mapper = KeyboardMapper()
