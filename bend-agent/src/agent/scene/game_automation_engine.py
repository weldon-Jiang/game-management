"""
场景识别与状态决策引擎
=====================

功能说明：
- 识别Xbox UI场景（主页、登录、游戏中心等）
- 管理场景状态转换
- 决策下一步动作
- 执行自动化操作序列

技术实现参考（streaming项目）：
- scene_detector.cpp (C++)
- SceneStateMachine (C++)
- ActionSequence (C++)

作者：技术团队
版本：1.0
"""

import asyncio
import time
from typing import Optional, Dict, List, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from ..core.logger import get_logger


class SceneState(Enum):
    """Xbox UI场景状态枚举"""
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    HOME = "home"
    LOGIN = "login"
    LOGIN_SELECT_ACCOUNT = "login_select_account"
    LOGIN_PASSWORD = "login_password"
    GAME_HUB = "game_hub"
    GAME_LIBRARY = "game_library"
    GAME_DETAILS = "game_details"
    GAME_PLAYING = "game_playing"
    GAME_PAUSED = "game_paused"
    SETTINGS = "settings"
    ACCOUNT_SETTINGS = "account_settings"
    STORE = "store"
    SOCIAL = "social"
    PARTIES = "parties"
    GUIDE = "guide"
    MATCHMAKING = "matchmaking"
    IN_GAME_MENU = "in_game_menu"


class ActionType(Enum):
    """动作类型枚举"""
    PRESS_BUTTON = "press_button"
    PRESS_BUTTON_SEQUENCE = "press_button_sequence"
    MOVE_THUMB = "move_thumb"
    WAIT = "wait"
    DETECT_SCENE = "detect_scene"
    REPEAT_SEQUENCE = "repeat_sequence"
    NAVIGATE = "navigate"


@dataclass
class Action:
    """动作数据类"""
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    timeout: float = 5.0

    @classmethod
    def press_button(cls, button: str, duration: float = 0.1) -> 'Action':
        """创建按按钮动作"""
        return cls(
            type=ActionType.PRESS_BUTTON,
            params={"button": button, "duration": duration},
            description=f"Press {button}",
            timeout=duration + 1.0
        )

    @classmethod
    def wait(cls, seconds: float) -> 'Action':
        """创建等待动作"""
        return cls(
            type=ActionType.WAIT,
            params={"seconds": seconds},
            description=f"Wait {seconds}s",
            timeout=seconds + 1.0
        )

    @classmethod
    def move_thumb(cls, thumb: str, x: float, y: float, duration: float = 0.5) -> 'Action':
        """创建摇杆动作"""
        return cls(
            type=ActionType.MOVE_THUMB,
            params={"thumb": thumb, "x": x, "y": y, "duration": duration},
            description=f"Move {thumb} thumb",
            timeout=duration + 1.0
        )

    @classmethod
    def navigate(cls, path: List[str]) -> 'Action':
        """创建导航动作序列"""
        return cls(
            type=ActionType.NAVIGATE,
            params={"path": path},
            description=f"Navigate: {' -> '.join(path)}",
            timeout=len(path) * 1.5
        )


@dataclass
class SceneTransition:
    """场景转换规则"""
    from_state: SceneState
    to_state: SceneState
    actions: List[Action]
    timeout: float = 30.0
    retry_count: int = 3


@dataclass
class SceneMatch:
    """场景匹配结果"""
    scene: SceneState
    confidence: float
    timestamp: float
    matched_template: Optional[str] = None


class ActionExecutor:
    """
    动作执行器

    功能说明：
    - 执行手柄动作序列
    - 与Xbox SmartGlass协议集成
    - 支持动作超时和重试

    使用方式：
    - set_controller(controller): 设置Xbox控制器
    - execute(action): 执行单个动作
    - execute_sequence(actions): 执行动作序列
    """

    def __init__(self):
        self.logger = get_logger('action_executor')
        self._controller = None
        self._xbox_session = None
        self._controller_protocol = None
        self._input_gate = None
        self._task_context = None

    def set_task_context(self, context: Any) -> None:
        self._task_context = context

    def set_input_gate(self, gate) -> None:
        self._input_gate = gate

    def set_controller(self, controller):
        """设置Xbox控制器"""
        self._controller = controller
        self.logger.info("动作执行器已绑定控制器")

    def set_xbox_session(self, session):
        """设置Xbox SmartGlass会话"""
        self._xbox_session = session
        self.logger.info("动作执行器已绑定Xbox会话")

    def set_controller_protocol(self, protocol):
        """绑定 ControllerProtocol 并同步 SmartGlass 会话。"""
        self._controller_protocol = protocol
        if protocol and getattr(protocol, "_stream_controller", None):
            self.set_xbox_session(protocol._stream_controller)
        self.logger.info("动作执行器已绑定手柄协议")

    async def _send_gamepad_state(self, gamepad_data: Dict[str, Any]) -> bool:
        """经 SmartGlass 输入通道发送手柄状态。"""
        if self._input_gate is not None and not self._input_gate.is_allowed():
            return False
        if not self._xbox_session:
            return False
        if hasattr(self._xbox_session, "send_gamepad_state"):
            from ..xbox.controller_write import write_controller_final

            return await write_controller_final(
                self._xbox_session,
                gamepad_data,
                context=self._task_context,
            )
        if hasattr(self._xbox_session, "send_input"):
            await self._xbox_session.send_input("gamepad", gamepad_data)
            return True
        return False

    async def execute(self, action: Action) -> bool:
        """
        执行单个动作

        参数：
        - action: 动作数据

        返回：
        - True: 执行成功
        - False: 执行失败
        """
        try:
            self.logger.debug(f"Executing: {action.description}")

            if action.type == ActionType.PRESS_BUTTON:
                return await self._press_button(action)

            elif action.type == ActionType.WAIT:
                await asyncio.sleep(action.params.get('seconds', 1.0))
                return True

            elif action.type == ActionType.MOVE_THUMB:
                return await self._move_thumb(action)

            elif action.type == ActionType.NAVIGATE:
                return await self._navigate(action)

            elif action.type == ActionType.PRESS_BUTTON_SEQUENCE:
                return await self._press_button_sequence(action)

            else:
                self.logger.warning(f"Unknown action type: {action.type}")
                return False

        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Execute action failed: {e}")
            return False

    async def _press_button(self, action: Action) -> bool:
        """按下手柄按钮"""
        button = action.params.get('button', 'A')
        duration = action.params.get('duration', 0.1)

        button_map = {
            'A': 'A', 'B': 'B', 'X': 'X', 'Y': 'Y',
            'START': 'START', 'SELECT': 'SELECT', 'VIEW': 'VIEW', 'MENU': 'MENU',
            'L1': 'L1', 'R1': 'R1', 'LB': 'L1', 'RB': 'R1',
            'UP': 'DPAD_UP', 'DOWN': 'DPAD_DOWN', 'LEFT': 'DPAD_LEFT', 'RIGHT': 'DPAD_RIGHT',
            'DPAD_UP': 'DPAD_UP', 'DPAD_DOWN': 'DPAD_DOWN',
            'DPAD_LEFT': 'DPAD_LEFT', 'DPAD_RIGHT': 'DPAD_RIGHT',
            'XBOX': 'NEXUS', 'NEXUS': 'NEXUS', 'GUIDE': 'NEXUS',
        }

        flag_name = button_map.get(button.upper(), 'A')

        task_id = None
        if self._task_context is not None:
            task_id = getattr(self._task_context, "task_id", None)

        from ..debug.automation_trace import log_gamepad_input

        log_gamepad_input(
            flag_name,
            duration=duration,
            source="action_executor",
            task_id=task_id,
        )

        if self._xbox_session:
            try:
                from ..input.controller_protocol import ControllerSignal, XboxButtonFlag

                if not hasattr(XboxButtonFlag, flag_name):
                    self.logger.warning(f"Unknown button: {button}")
                    return False

                flag = getattr(XboxButtonFlag, flag_name)
                signal = ControllerSignal()
                signal.set_button(flag, True)
                ok_press = await self._send_gamepad_state(signal.to_dict())
                if not ok_press:
                    self.logger.warning(
                        f"Gamepad press failed: {button} -> {flag_name} ({flag.value})"
                    )

                await asyncio.sleep(duration)

                signal.set_button(flag, False)
                ok_release = await self._send_gamepad_state(signal.to_dict())
                if not ok_release:
                    self.logger.warning(
                        f"Gamepad release failed: {button} -> {flag_name} ({flag.value})"
                    )
                return ok_press and ok_release
            except Exception as e:
                self.logger.error(f"Send button signal failed: {e}")
                return False

        return False

    async def _move_thumb(self, action: Action) -> bool:
        """移动摇杆"""
        thumb = action.params.get('thumb', 'left')
        x = action.params.get('x', 0.0)
        y = action.params.get('y', 0.0)
        duration = action.params.get('duration', 0.5)

        if self._xbox_session:
            try:
                from ..input.controller_protocol import ControllerSignal

                signal = ControllerSignal()
                signal.set_thumb(thumb, x, y)
                await self._send_gamepad_state(signal.to_dict())

                await asyncio.sleep(duration)

                signal = ControllerSignal()
                await self._send_gamepad_state(signal.to_dict())

                return True
            except Exception as e:
                self.logger.error(f"Send thumb signal failed: {e}")
                return False

        return False

    async def _navigate(self, action: Action) -> bool:
        """导航动作序列"""
        path = action.params.get('path', [])

        for button in path:
            btn_action = Action.press_button(button, 0.1)
            success = await self.execute(btn_action)
            if not success:
                return False
            await asyncio.sleep(0.2)

        return True

    async def _press_button_sequence(self, action: Action) -> bool:
        """按钮序列"""
        sequence = action.params.get('sequence', [])
        interval = action.params.get('interval', 0.3)

        for button in sequence:
            btn_action = Action.press_button(button, 0.1)
            success = await self.execute(btn_action)
            if not success:
                return False
            await asyncio.sleep(interval)

        return True

    async def execute_sequence(self, actions: List[Action], stop_on_failure: bool = True) -> bool:
        """
        执行动作序列

        参数：
        - actions: 动作列表
        - stop_on_failure: 失败时是否停止

        返回：
        - True: 所有动作执行成功
        - False: 任一动作执行失败
        """
        for action in actions:
            success = await self.execute(action)
            if not success and stop_on_failure:
                self.logger.warning(f"Action failed: {action.description}")
                return False

        return True


class StateDecisionEngine:
    """
    状态决策引擎

    功能说明：
    - 管理场景状态
    - 定义状态转换规则
    - 决策下一步动作
    - 执行自动化流程

    使用方式：
    - add_transition(transition): 添加转换规则
    - set_scene_callback(callback): 设置场景检测回调
    - execute_until(target_scene): 执行直到目标场景
    """

    def __init__(self, action_executor: ActionExecutor):
        self.logger = get_logger('state_decision')
        self._executor = action_executor
        self._transitions: Dict[SceneState, List[SceneTransition]] = {}
        self._current_scene = SceneState.UNKNOWN
        self._scene_callback: Optional[Callable] = None
        self._running = False
        self._setup_default_transitions()

    def _setup_default_transitions(self):
        """设置默认转换规则"""

        self.add_transition(SceneTransition(
            from_state=SceneState.LOGIN,
            to_state=SceneState.HOME,
            actions=[
                Action.navigate(['A']),
            ],
            timeout=30.0
        ))

        self.add_transition(SceneTransition(
            from_state=SceneState.HOME,
            to_state=SceneState.GAME_LIBRARY,
            actions=[
                Action.navigate(['LEFT', 'LEFT', 'A']),
            ],
            timeout=10.0
        ))

        self.add_transition(SceneTransition(
            from_state=SceneState.GAME_LIBRARY,
            to_state=SceneState.GAME_HUB,
            actions=[
                Action.navigate(['DOWN', 'A']),
            ],
            timeout=10.0
        ))

        self.add_transition(SceneTransition(
            from_state=SceneState.GAME_HUB,
            to_state=SceneState.GAME_PLAYING,
            actions=[
                Action.navigate(['A']),
            ],
            timeout=60.0
        ))

        self.add_transition(SceneTransition(
            from_state=SceneState.GAME_PLAYING,
            to_state=SceneState.IN_GAME_MENU,
            actions=[
                Action.press_button('START', 0.1),
            ],
            timeout=5.0
        ))

        self.add_transition(SceneTransition(
            from_state=SceneState.IN_GAME_MENU,
            to_state=SceneState.GAME_PLAYING,
            actions=[
                Action.navigate(['B']),
            ],
            timeout=5.0
        ))

        self.logger.info("默认转换规则已加载")

    def add_transition(self, transition: SceneTransition):
        """添加场景转换规则"""
        if transition.from_state not in self._transitions:
            self._transitions[transition.from_state] = []
        self._transitions[transition.from_state].append(transition)
        self.logger.debug(f"Added transition: {transition.from_state.value} -> {transition.to_state.value}")

    def set_scene(self, scene: SceneState):
        """设置当前场景"""
        if self._current_scene != scene:
            old_scene = self._current_scene
            self._current_scene = scene
            self.logger.info(f"Scene changed: {old_scene.value} -> {scene.value}")

    def set_scene_callback(self, callback: Callable):
        """设置场景检测回调"""
        self._scene_callback = callback

    async def get_current_scene(self) -> SceneState:
        """获取当前场景"""
        if self._scene_callback:
            try:
                scene = await self._scene_callback()
                if scene:
                    self.set_scene(scene)
            except Exception as e:
                self.logger.error(f"Scene callback failed: {e}")

        return self._current_scene

    async def transition_to(self, target_scene: SceneState, max_retries: int = 3) -> bool:
        """
        执行到目标场景的转换

        参数：
        - target_scene: 目标场景
        - max_retries: 最大重试次数

        返回：
        - True: 转换成功
        - False: 转换失败
        """
        if self._current_scene == target_scene:
            self.logger.debug(f"Already at target scene: {target_scene.value}")
            return True

        self.logger.info(f"Transitioning: {self._current_scene.value} -> {target_scene.value}")

        for retry in range(max_retries):
            transitions = self._transitions.get(self._current_scene, [])

            matched_transition = None
            for trans in transitions:
                if trans.to_state == target_scene:
                    matched_transition = trans
                    break

            if not matched_transition:
                self.logger.error(f"No transition found: {self._current_scene.value} -> {target_scene.value}")
                return False

            self.logger.info(f"Executing {len(matched_transition.actions)} actions...")

            for action in matched_transition.actions:
                success = await self._executor.execute(action)
                if not success:
                    self.logger.warning(f"Action failed: {action.description}")
                    break
                await asyncio.sleep(0.3)

            await asyncio.sleep(1.0)

            current = await self.get_current_scene()
            if current == target_scene:
                self.logger.info(f"Successfully transitioned to: {target_scene.value}")
                return True

            self.logger.warning(f"Retry {retry + 1}/{max_retries}")

        return False

    async def execute_until(
        self,
        target_scene: SceneState,
        frame_getter: Callable,
        timeout: float = 120.0,
        poll_interval: float = 2.0
    ) -> bool:
        """
        执行直到检测到目标场景

        参数：
        - target_scene: 目标场景
        - frame_getter: 获取当前帧的函数
        - timeout: 超时时间
        - poll_interval: 检测间隔

        返回：
        - True: 检测到目标场景
        - False: 超时
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            frame = await frame_getter()
            if frame is not None:
                await self.get_current_scene()
                if self._current_scene == target_scene:
                    return True

            await asyncio.sleep(poll_interval)

        self.logger.warning(f"Timeout waiting for scene: {target_scene.value}")
        return False


class GameAutomationEngine:
    """
    游戏自动化引擎

    功能说明：
    - 整合场景识别和动作执行
    - 管理游戏自动化流程
    - 支持自定义场景转换

    使用方式：
    - initialize(scene_detector, action_executor): 初始化
    - switch_account(account_info): 切换账号
    - start_game(game_id): 启动游戏
    - execute_match(): 执行比赛
    - cleanup(): 清理资源
    """

    def __init__(self):
        self.logger = get_logger('game_automation')
        self._scene_detector = None
        self._action_executor = ActionExecutor()
        self._decision_engine = StateDecisionEngine(self._action_executor)
        self._running = False

    def initialize(self, scene_detector, xbox_session):
        """
        初始化自动化引擎

        参数：
        - scene_detector: 场景检测器
        - xbox_session: Xbox SmartGlass会话
        """
        self._scene_detector = scene_detector
        self._action_executor.set_xbox_session(xbox_session)

        self._decision_engine.set_scene_callback(
            lambda: self._scene_detector.detect_scene(None)
        )

        self._running = True
        self.logger.info("游戏自动化引擎已初始化")

    async def switch_account(self, account_info: Dict[str, Any]) -> bool:
        """
        切换游戏账号

        参数：
        - account_info: 账号信息，包含 gamertag, email 等

        返回：
        - True: 切换成功
        - False: 切换失败
        """
        try:
            self.logger.info(f"Switching to account: {account_info.get('gamertag', 'unknown')}")

            await self._decision_engine.transition_to(SceneState.HOME)

            await self._action_executor.execute_sequence([
                Action.navigate(['LEFT', 'A']),
            ])

            await asyncio.sleep(2.0)

            await self._action_executor.execute_sequence([
                Action.navigate(['DOWN', 'A']),
            ])

            await asyncio.sleep(1.0)

            for _ in range(5):
                await self._action_executor.execute(Action.press_button('DOWN', 0.1))
                await asyncio.sleep(0.2)

            current = await self._decision_engine.get_current_scene()
            if current == SceneState.LOGIN_SELECT_ACCOUNT:
                self.logger.info("Account selection screen reached")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Switch account failed: {e}")
            return False

    async def navigate_to_game(self, game_index: int = 0) -> bool:
        """
        导航到游戏

        参数：
        - game_index: 游戏在列表中的索引

        返回：
        - True: 导航成功
        - False: 导航失败
        """
        try:
            await self._decision_engine.transition_to(SceneState.GAME_LIBRARY)

            await asyncio.sleep(1.0)

            for i in range(game_index):
                await self._action_executor.execute(Action.press_button('DOWN', 0.1))
                await asyncio.sleep(0.3)

            self.logger.info(f"Navigated to game at index {game_index}")
            return True

        except Exception as e:
            self.logger.error(f"Navigate to game failed: {e}")
            return False

    async def start_game(self) -> bool:
        """
        启动游戏

        返回：
        - True: 启动成功
        - False: 启动失败
        """
        try:
            await self._action_executor.execute(Action.press_button('A', 0.1))

            self.logger.info("Game starting...")

            success = await self._decision_engine.execute_until(
                SceneState.GAME_PLAYING,
                lambda: self._scene_detector.frame_capture.get_frame() if self._scene_detector else None,
                timeout=60.0
            )

            if success:
                self.logger.info("Game started successfully")
            else:
                self.logger.warning("Game may not have started")

            return success

        except Exception as e:
            self.logger.error(f"Start game failed: {e}")
            return False

    async def cleanup(self):
        """清理资源"""
        self._running = False
        self.logger.info("游戏自动化引擎已清理")


game_automation_engine = GameAutomationEngine()
