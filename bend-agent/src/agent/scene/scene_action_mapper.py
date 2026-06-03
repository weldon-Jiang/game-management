"""
Scene Action Mapper - 场景动作映射器
=====================================

功能说明：
- 将检测到的场景映射到对应的手柄动作
- 支持场景转移逻辑
- 与FootballController和StreamingSceneDetector集成

作者：技术团队
版本：1.0
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import get_logger

try:
    from .streaming_scene_detector import StreamingSceneDetector, SceneMatchResult
    from ..input.football_controller import FootballController, FootballAction
    from configs.football_scenes import (
        FOOTBALL_SCENE_NAMES,
        SCENE_CATEGORY,
        FOOTBALL_SCENE_DESCRIPTIONS
    )
except ImportError as e:
    StreamingSceneDetector = None
    SceneMatchResult = None
    FootballController = None
    FootballAction = None
    FOOTBALL_SCENE_NAMES = {}
    SCENE_CATEGORY = {}
    FOOTBALL_SCENE_DESCRIPTIONS = {}


class ActionType(Enum):
    """动作类型"""
    SINGLE = "single"
    SEQUENCE = "sequence"
    CONTINUOUS = "continuous"


@dataclass
class SceneAction:
    """场景动作定义"""
    scene_id: int
    action_type: ActionType
    action_name: str
    priority: int = 0
    conditions: List[str] = field(default_factory=list)
    description: str = ""


class SceneActionMapper:
    """
    场景动作映射器

    功能说明：
    - 管理场景与动作的映射关系
    - 根据场景执行相应动作
    - 支持动作序列和连续动作
    - 与场景检测器联动

    使用方式：
        mapper = SceneActionMapper(
            scene_detector=detector,
            football_controller=controller
        )
        await mapper.on_scene_detected(scene_result)
    """

    DEFAULT_MAPPINGS: Dict[int, SceneAction] = {}

    def __init__(
        self,
        scene_detector=None,
        football_controller=None,
        config_path: str = None
    ):
        self.logger = get_logger('scene_action_mapper')

        self.scene_detector = scene_detector
        self.football_controller = football_controller

        self.current_category: str = "menu"
        self.current_scene_id: int = -1
        self.action_mappings: Dict[int, SceneAction] = self.DEFAULT_MAPPINGS.copy()

        self._last_execution_time: float = 0
        self._execution_cooldown: float = 0.5

        self._load_default_mappings()

        if config_path:
            self._load_config(config_path)

        self.logger.info(f"SceneActionMapper 初始化完成，映射数: {len(self.action_mappings)}")

    def _load_default_mappings(self):
        """加载默认场景动作映射"""
        default_mappings = {
            100: SceneAction(100, ActionType.SEQUENCE, "kickoff", priority=1,
                            description="比赛开始"),
            101: SceneAction(101, ActionType.SEQUENCE, "skip_celebration", priority=1,
                            description="进球庆祝"),
            102: SceneAction(102, ActionType.SEQUENCE, "exit_match", priority=1,
                            description="比赛结束"),
            103: SceneAction(103, ActionType.SEQUENCE, "kickoff", priority=2,
                            description="我方角球"),
            104: SceneAction(104, ActionType.SEQUENCE, "basic_defend", priority=2,
                            description="对方角球"),
            105: SceneAction(105, ActionType.SEQUENCE, "kickoff", priority=2,
                            description="任意球"),
            108: SceneAction(108, ActionType.SEQUENCE, "basic_attack", priority=2,
                            description="点球"),
        }

        for scene_id, action in default_mappings.items():
            self.action_mappings[scene_id] = action

    def _load_config(self, config_path: str):
        """从配置文件加载映射"""
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if 'scene_action_map' in config:
                for scene_id_str, cfg in config['scene_action_map'].items():
                    scene_id = int(scene_id_str)
                    action_type_str = cfg.get('type', 'sequence')
                    action_type = ActionType(action_type_str)

                    self.action_mappings[scene_id] = SceneAction(
                        scene_id=scene_id,
                        action_type=action_type,
                        action_name=cfg.get('action', ''),
                        priority=cfg.get('priority', 0),
                        description=cfg.get('description', '')
                    )

            self.logger.info(f"从配置文件加载映射: {config_path}")

        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")

    def register_action(self, scene_id: int, action: SceneAction):
        """注册场景动作"""
        self.action_mappings[scene_id] = action
        self.logger.info(f"注册场景动作: 场景{scene_id} -> {action.action_name}")

    def unregister_action(self, scene_id: int):
        """取消注册场景动作"""
        if scene_id in self.action_mappings:
            del self.action_mappings[scene_id]
            self.logger.info(f"取消注册场景动作: 场景{scene_id}")

    def get_action(self, scene_id: int) -> Optional[SceneAction]:
        """获取场景对应的动作"""
        return self.action_mappings.get(scene_id)

    def get_scene_name(self, scene_id: int) -> str:
        """获取场景名称"""
        return FOOTBALL_SCENE_NAMES.get(scene_id, f"场景{scene_id}")

    def get_scene_category(self, scene_id: int) -> Optional[str]:
        """获取场景分类"""
        for category, scene_ids in SCENE_CATEGORY.items():
            if scene_id in scene_ids:
                return category
        return None

    def is_cooldown_active(self) -> bool:
        """检查是否在冷却期内"""
        import time
        current_time = time.time()
        if current_time - self._last_execution_time < self._execution_cooldown:
            return True
        return False

    async def on_scene_detected(
        self,
        scene_result: Any,
        force_execute: bool = False
    ) -> bool:
        """
        场景检测回调

        参数：
        - scene_result: 场景检测结果（SceneMatchResult或scene_id）
        - force_execute: 是否强制执行（忽略冷却）

        返回值：
        - True: 动作执行成功
        - False: 执行失败或无对应动作
        """
        if scene_result is None:
            return False

        scene_id = self._extract_scene_id(scene_result)

        if scene_id < 0:
            return False

        if not force_execute and scene_id == self.current_scene_id:
            return False

        if not force_execute and self.is_cooldown_active():
            return False

        self.current_scene_id = scene_id

        scene_name = self.get_scene_name(scene_id)
        scene_category = self.get_scene_category(scene_id)
        if scene_category:
            self.current_category = scene_category

        self.logger.info(f"检测到场景: {scene_id} ({scene_name}), 分类: {scene_category}")

        action = self.get_action(scene_id)
        if not action:
            self.logger.debug(f"场景 {scene_id} 没有对应的动作映射")
            return False

        success = await self._execute_action(action)
        if success:
            import time
            self._last_execution_time = time.time()

        return success

    def _extract_scene_id(self, scene_result: Any) -> int:
        """提取场景ID"""
        if isinstance(scene_result, int):
            return scene_result
        elif hasattr(scene_result, 'scene_id'):
            return scene_result.scene_id
        elif isinstance(scene_result, dict) and 'scene_id' in scene_result:
            return scene_result['scene_id']
        return -1

    async def _execute_action(self, action: SceneAction) -> bool:
        """执行动作"""
        if not self.football_controller:
            self.logger.error("未设置FootballController")
            return False

        try:
            if action.action_type == ActionType.SINGLE:
                action_enum = FootballAction(action.action_name) if FootballAction else None
                if action_enum:
                    success = await self.football_controller.execute_action(action_enum)
                else:
                    success = await self.football_controller.execute_action_by_name(action.action_name)

            elif action.action_type == ActionType.SEQUENCE:
                success = await self.football_controller.execute_sequence(action.action_name)

            elif action.action_type == ActionType.CONTINUOUS:
                success = await self._execute_continuous_action(action)

            else:
                self.logger.error(f"未知的动作类型: {action.action_type}")
                return False

            if success:
                self.logger.info(f"动作执行成功: {action.action_name}")
            else:
                self.logger.warning(f"动作执行失败: {action.action_name}")

            return success

        except Exception as e:
            self.logger.error(f"执行动作异常: {e}")
            return False

    async def _execute_continuous_action(self, action: SceneAction) -> bool:
        """执行连续动作"""
        self.logger.info(f"开始执行连续动作: {action.action_name}")
        return True

    def set_football_controller(self, controller):
        """设置足球控制器"""
        self.football_controller = controller

    def set_scene_detector(self, detector):
        """设置场景检测器"""
        self.scene_detector = detector

    def set_execution_cooldown(self, cooldown: float):
        """设置执行冷却时间（秒）"""
        self._execution_cooldown = cooldown

    def reset_state(self):
        """重置状态"""
        self.current_scene_id = -1
        self.current_category = "menu"
        self._last_execution_time = 0
        self.logger.info("场景动作映射器状态已重置")

    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'current_scene_id': self.current_scene_id,
            'current_category': self.current_category,
            'mapped_scenes': len(self.action_mappings),
            'cooldown': self._execution_cooldown
        }
