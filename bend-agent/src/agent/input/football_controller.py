"""
Football Controller - 足球比赛控制器
=====================================

功能说明：
- 封装足球比赛手柄动作
- 支持动作序列执行
- 与场景检测器集成
- 支持YAML配置加载

作者：技术团队
版本：1.0
"""

import asyncio
import math
import os
from typing import List, Dict, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import yaml
except ImportError:
    yaml = None

from ..core.logger import get_logger
from .controller_protocol import ControllerSignal, XboxButtonFlag


class FootballAction(Enum):
    PASS_GROUND = "pass_ground"
    PASS_LOB = "pass_lob"
    THROUGH_BALL = "through_ball"
    SHOOT = "shoot"
    SHOOT_POWER = "shoot_power"
    SPRINT = "sprint"
    JOCKEY = "jockey"
    TACKLE = "tackle"
    SLIDE_TACKLE = "slide_tackle"
    CONTAIN = "contain"
    CHANGE_PLAYER = "change_player"
    FAKE_SHOT = "fake_shot"
    STOP_BALL = "stop_ball"
    HEADER = "header"
    CLEARANCE = "clearance"
    MOVE_FORWARD = "move_forward"
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    MOVE_BACKWARD = "move_backward"


@dataclass
class ActionStep:
    """动作步骤"""
    buttons: int = 0
    left_trigger: int = 0
    right_trigger: int = 0
    left_thumb_x: int = 0
    left_thumb_y: int = 0
    right_thumb_x: int = 0
    right_thumb_y: int = 0
    duration_ms: int = 100

    def to_signal(self) -> ControllerSignal:
        """转换为ControllerSignal"""
        signal = ControllerSignal()
        signal.buttons = self.buttons
        signal.left_trigger = self.left_trigger
        signal.right_trigger = self.right_trigger
        signal.left_thumb_x = self.left_thumb_x
        signal.left_thumb_y = self.left_thumb_y
        signal.right_thumb_x = self.right_thumb_x
        signal.right_thumb_y = self.right_thumb_y
        return signal


@dataclass
class ActionConfig:
    """动作配置"""
    description: str
    buttons: List[str] = field(default_factory=list)
    duration_ms: int = 100
    repeat: int = 1
    right_trigger: int = 0
    left_trigger: int = 0
    left_stick: Tuple[int, int] = (0, 0)
    right_stick: Tuple[int, int] = (0, 0)
    priority: int = 1


@dataclass
class SequenceStep:
    """序列步骤"""
    action: str
    duration_ms: int
    buttons: List[str] = field(default_factory=list)
    left_stick: Tuple[float, float] = (0.0, 0.0)
    right_stick: Tuple[float, float] = (0.0, 0.0)


class FootballController:
    """
    足球比赛控制器

    功能说明：
    - 加载动作配置（YAML或默认）
    - 执行单个动作
    - 执行动作序列
    - 与Xbox手柄信号发送器集成

    使用方式：
        controller = FootballController()
        controller.set_signal_sender(send_func)
        await controller.execute_action(FootballAction.SHOOT)
        await controller.execute_sequence("basic_attack")
    """

    BUTTON_MAP = {
        'A': XboxButtonFlag.A,
        'B': XboxButtonFlag.B,
        'X': XboxButtonFlag.X,
        'Y': XboxButtonFlag.Y,
        'LB': XboxButtonFlag.L1,
        'RB': XboxButtonFlag.R1,
        'LS': XboxButtonFlag.L3,
        'RS': XboxButtonFlag.R3,
    }

    DEFAULT_ACTIONS = {
        'pass_ground': ActionConfig(
            description="地面传球",
            buttons=['A'],
            duration_ms=150,
            priority=1
        ),
        'pass_lob': ActionConfig(
            description="高空传球",
            buttons=['X'],
            duration_ms=150,
            priority=2
        ),
        'through_ball': ActionConfig(
            description="直塞球",
            buttons=['Y'],
            duration_ms=150,
            priority=3
        ),
        'shoot': ActionConfig(
            description="射门",
            buttons=['B'],
            duration_ms=200,
            priority=1
        ),
        'shoot_power': ActionConfig(
            description="大力射门",
            buttons=['B'],
            duration_ms=300,
            right_trigger=32767,
            priority=2
        ),
        'sprint': ActionConfig(
            description="加速",
            buttons=['RB'],
            duration_ms=500,
            priority=1
        ),
        'jockey': ActionConfig(
            description="移动拦截",
            buttons=['LB'],
            duration_ms=300,
            priority=1
        ),
        'tackle': ActionConfig(
            description="抢断",
            buttons=['B'],
            duration_ms=200,
            priority=2
        ),
        'slide_tackle': ActionConfig(
            description="滑铲",
            buttons=['LB', 'B'],
            duration_ms=300,
            priority=3
        ),
        'contain': ActionConfig(
            description="围堵",
            buttons=['LB'],
            duration_ms=200,
            priority=1
        ),
        'change_player': ActionConfig(
            description="切换球员",
            buttons=['LB'],
            duration_ms=100,
            priority=1
        ),
        'fake_shot': ActionConfig(
            description="假射",
            buttons=['X'],
            duration_ms=150,
            priority=1
        ),
        'stop_ball': ActionConfig(
            description="停球",
            buttons=['A'],
            duration_ms=100,
            priority=1
        ),
        'header': ActionConfig(
            description="头球",
            buttons=['B'],
            duration_ms=200,
            priority=2
        ),
        'clearance': ActionConfig(
            description="解围",
            buttons=['X'],
            duration_ms=200,
            priority=1
        ),
        'move_forward': ActionConfig(
            description="前进",
            duration_ms=500,
            left_stick=(0, -1),
            priority=1
        ),
        'move_backward': ActionConfig(
            description="后退",
            duration_ms=500,
            left_stick=(0, 1),
            priority=1
        ),
        'move_left': ActionConfig(
            description="左移",
            duration_ms=500,
            left_stick=(-1, 0),
            priority=1
        ),
        'move_right': ActionConfig(
            description="右移",
            duration_ms=500,
            left_stick=(1, 0),
            priority=1
        ),
    }

    DEFAULT_SEQUENCES = {
        'kickoff': [
            SequenceStep('move_forward', 500, left_stick=(0, -1)),
            SequenceStep('pass_ground', 150),
        ],
        'basic_attack': [
            SequenceStep('sprint', 300),
            SequenceStep('move_forward', 1000, left_stick=(0, -1)),
            SequenceStep('shoot', 200),
        ],
        'skip_celebration': [
            SequenceStep('pass_ground', 150),
            SequenceStep('pass_ground', 150),
            SequenceStep('pass_ground', 150),
        ],
        'exit_match': [
            SequenceStep('pass_ground', 150),
            SequenceStep('pass_ground', 150),
        ],
        'basic_defend': [
            SequenceStep('change_player', 100),
            SequenceStep('jockey', 500),
            SequenceStep('tackle', 200),
        ],
    }

    def __init__(self, config_path: str = None):
        self.logger = get_logger('football_controller')
        self.signal_sender: Optional[Callable] = None
        self.actions: Dict[str, ActionConfig] = self.DEFAULT_ACTIONS.copy()
        self.sequences: Dict[str, List[SequenceStep]] = self.DEFAULT_SEQUENCES.copy()

        if config_path and yaml:
            self._load_config(config_path)

        self.logger.info(f"FootballController 初始化完成，动作数: {len(self.actions)}, 序列数: {len(self.sequences)}")

    def _load_config(self, config_path: str):
        """加载YAML配置文件"""
        try:
            if not os.path.exists(config_path):
                self.logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
                return

            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if 'basic_actions' in config:
                self._load_actions(config['basic_actions'])

            if 'action_sequences' in config:
                self._load_sequences(config['action_sequences'])

            self.logger.info(f"成功加载配置文件: {config_path}")

        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")

    def _load_actions(self, actions_config: Dict):
        """加载动作配置"""
        for name, cfg in actions_config.items():
            buttons = cfg.get('buttons', [])
            duration_ms = cfg.get('duration_ms', 100)
            right_trigger = cfg.get('right_trigger', 0)
            left_trigger = cfg.get('left_trigger', 0)
            left_stick = cfg.get('left_stick', (0, 0))
            right_stick = cfg.get('right_stick', (0, 0))

            if isinstance(left_stick, list):
                left_stick = tuple(left_stick)
            if isinstance(right_stick, list):
                right_stick = tuple(right_stick)

            self.actions[name] = ActionConfig(
                description=cfg.get('description', name),
                buttons=buttons,
                duration_ms=duration_ms,
                right_trigger=right_trigger,
                left_trigger=left_trigger,
                left_stick=left_stick,
                right_stick=right_stick,
                priority=cfg.get('priority', 1)
            )

    def _load_sequences(self, sequences_config: Dict):
        """加载动作序列配置"""
        for name, cfg in sequences_config.items():
            if isinstance(cfg, dict) and 'steps' in cfg:
                steps = []
                for step_cfg in cfg['steps']:
                    steps.append(SequenceStep(
                        action=step_cfg.get('action', ''),
                        duration_ms=step_cfg.get('duration_ms', 100),
                        buttons=step_cfg.get('buttons', []),
                        left_stick=tuple(step_cfg.get('left_stick', (0, 0))),
                        right_stick=tuple(step_cfg.get('right_stick', (0, 0)))
                    ))
                self.sequences[name] = steps

    def set_signal_sender(self, sender: Callable):
        """设置手柄信号发送器"""
        self.signal_sender = sender
        self.logger.info("手柄信号发送器已设置")

    def set_action_sender(self, sender: Callable[[ControllerSignal], Any]):
        """设置动作发送器（别名）"""
        self.signal_sender = sender

    async def execute_action(
        self,
        action: FootballAction,
        duration_ms: int = None,
        **kwargs
    ) -> bool:
        """执行单个动作"""
        action_name = action.value if isinstance(action, FootballAction) else action
        return await self.execute_action_by_name(action_name, duration_ms, **kwargs)

    async def execute_action_by_name(
        self,
        action_name: str,
        duration_ms: int = None,
        **kwargs
    ) -> bool:
        """按名称执行动作"""
        action_config = self.actions.get(action_name)
        if not action_config:
            self.logger.error(f"未找到动作: {action_name}")
            return False

        duration = duration_ms or action_config.duration_ms

        step = self._build_action_step(action_config, duration, **kwargs)
        await self._execute_step(step)

        return True

    def _build_action_step(
        self,
        action_config: ActionConfig,
        duration_ms: int,
        **kwargs
    ) -> ActionStep:
        """构建动作步骤"""
        buttons = kwargs.get('buttons', action_config.buttons)
        left_trigger = kwargs.get('left_trigger', action_config.left_trigger)
        right_trigger = kwargs.get('right_trigger', action_config.right_trigger)
        left_stick = kwargs.get('left_stick', action_config.left_stick)
        right_stick = kwargs.get('right_stick', action_config.right_stick)

        buttons_mask = self._build_buttons(buttons)

        left_x, left_y = self._normalize_stick(left_stick)
        right_x, right_y = self._normalize_stick(right_stick)

        return ActionStep(
            buttons=buttons_mask,
            left_trigger=left_trigger,
            right_trigger=right_trigger,
            left_thumb_x=left_x,
            left_thumb_y=left_y,
            right_thumb_x=right_x,
            right_thumb_y=right_y,
            duration_ms=duration_ms
        )

    async def execute_sequence(
        self,
        sequence_name: str,
        repeat: int = 1,
        **kwargs
    ) -> bool:
        """执行动作序列"""
        sequence = self.sequences.get(sequence_name)
        if not sequence:
            self.logger.error(f"未找到动作序列: {sequence_name}")
            return False

        self.logger.info(f"开始执行动作序列: {sequence_name} x {repeat}")

        for r in range(repeat):
            for step in sequence:
                await self._execute_sequence_step(step, **kwargs)

        self.logger.info(f"动作序列完成: {sequence_name}")
        return True

    async def _execute_sequence_step(self, step: SequenceStep, **kwargs):
        """执行序列中的单个步骤"""
        if step.action in self.actions:
            await self.execute_action_by_name(
                step.action,
                step.duration_ms,
                **kwargs
            )
        elif step.left_stick != (0, 0):
            step_obj = ActionStep(
                buttons=self._build_buttons(step.buttons),
                left_thumb_x=int(step.left_stick[0] * 32767),
                left_thumb_y=int(step.left_stick[1] * 32767),
                duration_ms=step.duration_ms
            )
            await self._execute_step(step_obj)

    async def _execute_step(self, step: ActionStep):
        """执行单个步骤"""
        if not self.signal_sender:
            self.logger.warning("未设置信号发送器，跳过执行")
            return

        try:
            signal = step.to_signal()
            await self.signal_sender(signal)
            await asyncio.sleep(step.duration_ms / 1000.0)

            zero_signal = ControllerSignal()
            await self.signal_sender(zero_signal)
            await asyncio.sleep(0.05)

        except Exception as e:
            self.logger.error(f"执行动作步骤失败: {e}")

    def _build_buttons(self, button_list: List[str]) -> int:
        """构建按钮位掩码"""
        buttons = 0
        for btn in button_list:
            if btn in self.BUTTON_MAP:
                buttons |= self.BUTTON_MAP[btn].value
        return buttons

    def _normalize_stick(self, stick: Tuple[float, float]) -> Tuple[int, int]:
        """标准化摇杆值"""
        x = int(max(-32768, min(32767, stick[0] * 32767)))
        y = int(max(-32768, min(32767, stick[1] * 32767)))
        return x, y

    def angle_to_stick(self, angle_degrees: float) -> Tuple[int, int]:
        """角度转换为摇杆坐标"""
        angle_rad = math.radians(angle_degrees)
        x = int(32767 * math.cos(angle_rad))
        y = int(32767 * math.sin(angle_rad))
        return x, y

    def get_action_config(self, action_name: str) -> Optional[ActionConfig]:
        """获取动作配置"""
        return self.actions.get(action_name)

    def get_sequence(self, sequence_name: str) -> Optional[List[SequenceStep]]:
        """获取动作序列"""
        return self.sequences.get(sequence_name)
