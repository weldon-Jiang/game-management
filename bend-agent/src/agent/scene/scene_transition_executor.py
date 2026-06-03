
"""
场景转移执行器
==============

基于 streaming 项目的场景转移配置，实现自动场景跳转功能

作者：技术团队
版本：1.0
"""

import asyncio
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass

from ..core.logger import get_logger
from configs.scene_transitions import SCENE_TRANSITIONS, get_transitions_by_scene


@dataclass
class ControllerOption:
    """手柄操作配置"""
    duration_ms: int  # 持续时间（毫秒）
    count: int        # 执行次数（0表示无限循环直到目标场景）
    buttons: int      # 按钮位掩码
    left_trigger: int
    right_trigger: int
    left_thumb_x: int
    left_thumb_y: int
    right_thumb_x: int
    right_thumb_y: int


@dataclass
class SceneTransition:
    """场景转移配置"""
    scene_id: int
    transition_id: int
    description: str
    controller_options: List[ControllerOption]
    target_scenes: List[int]


class SceneTransitionExecutor:
    """场景转移执行器"""

    def __init__(self):
        self.logger = get_logger('scene_transition')
        self.scene_detector = None
        self.controller = None
        self._transitions = self._load_transitions()

    def _load_transitions(self) -> Dict[int, List[SceneTransition]]:
        """加载场景转移配置"""
        transitions_dict = {}
        for data in SCENE_TRANSITIONS:
            scene_id = data['scene_id']
            transition = SceneTransition(
                scene_id=scene_id,
                transition_id=data['transition_id'],
                description=data['description'],
                controller_options=[
                    ControllerOption(*opt) for opt in data['controller_options']
                ],
                target_scenes=data['target_scenes']
            )
            if scene_id not in transitions_dict:
                transitions_dict[scene_id] = []
            transitions_dict[scene_id].append(transition)
        return transitions_dict

    def initialize(self, scene_detector, controller):
        """初始化"""
        self.scene_detector = scene_detector
        self.controller = controller
        self.logger.info("场景转移执行器初始化完成")

    def get_available_transitions(self, scene_id: int) -> List[SceneTransition]:
        """获取指定场景可用的转移"""
        return self._transitions.get(scene_id, [])

    async def execute_transition(
        self,
        transition: SceneTransition,
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        执行场景转移
        
        参数:
            transition: 场景转移配置
            check_cancel: 取消检查回调
            report_progress: 进度报告回调
            
        返回:
            是否成功到达目标场景
        """
        self.logger.info(f"开始执行场景转移: {transition.description}")
        self.logger.info(f"目标场景: {transition.target_scenes}")

        if report_progress:
            report_progress(f"开始场景转移: {transition.description}")

        for option in transition.controller_options:
            success = await self._execute_controller_option(
                option,
                transition.target_scenes,
                check_cancel,
                report_progress
            )
            if not success:
                self.logger.error(f"手柄操作执行失败或超时")
                return False

        if report_progress:
            report_progress("场景转移完成")

        return True

    async def _execute_controller_option(
        self,
        option: ControllerOption,
        target_scenes: List[int],
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        执行单个手柄操作配置
        """
        max_attempts = option.count if option.count > 0 else 20

        for attempt in range(max_attempts):
            if check_cancel and check_cancel():
                self.logger.info("场景转移被取消")
                return False

            if report_progress:
                report_progress(f"执行手柄操作 ({attempt + 1}/{max_attempts})")

            await self._send_controller_signal(option)

            if target_scenes:
                await asyncio.sleep(0.5)
                current_scene = await self._detect_current_scene()
                if current_scene in target_scenes:
                    self.logger.info(f"成功到达目标场景: {current_scene}")
                    if report_progress:
                        report_progress(f"到达目标场景: {current_scene}")
                    return True

        if option.count == 0 or option.count > 1:
            self.logger.warning(f"未到达目标场景，已尝试 {max_attempts} 次")
            return False

        return True

    async def _send_controller_signal(self, option: ControllerOption):
        """发送手柄信号"""
        if not self.controller:
            self.logger.warning("控制器未设置，无法发送手柄信号")
            return

        duration_sec = option.duration_ms / 1000.0

        try:
            await self.controller.send_signal(
                buttons=option.buttons,
                left_trigger=option.left_trigger,
                right_trigger=option.right_trigger,
                left_thumb_x=option.left_thumb_x,
                left_thumb_y=option.left_thumb_y,
                right_thumb_x=option.right_thumb_x,
                right_thumb_y=option.right_thumb_y,
                duration=duration_sec
            )
        except Exception as e:
            self.logger.error(f"发送手柄信号失败: {e}")

    async def _detect_current_scene(self) -> Optional[int]:
        """检测当前场景"""
        if not self.scene_detector:
            return None

        try:
            result = await self.scene_detector.recognize_scene()
            if result and result.matched:
                return result.scene_id
        except Exception as e:
            self.logger.error(f"场景检测失败: {e}")

        return None

    async def navigate_to(
        self,
        target_scene: int,
        start_scene: Optional[int] = None,
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        导航到目标场景
        
        注意：这是一个简化版本，实际项目可能需要更复杂的路径规划
        """
        if start_scene is None:
            start_scene = await self._detect_current_scene()
            if start_scene is None:
                self.logger.error("无法检测当前场景")
                return False

        if start_scene == target_scene:
            self.logger.info("已经在目标场景")
            return True

        transitions = self.get_available_transitions(start_scene)
        for transition in transitions:
            if target_scene in transition.target_scenes:
                return await self.execute_transition(
                    transition,
                    check_cancel,
                    report_progress
                )

        self.logger.warning(f"未找到从 {start_scene} 到 {target_scene} 的直接转移路径")
        return False

    async def auto_play_football_match(
        self,
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable[[str], None]] = None
    ) -> bool:
        """
        自动执行足球比赛流程
        
        这是一个完整的示例流程
        """
        # 场景1 -> 场景2 (西瓜主页)
        transition_1_2 = self._find_transition(1, 1)
        if transition_1_2:
            success = await self.execute_transition(transition_1_2, check_cancel, report_progress)
            if not success:
                return False

        # 场景2 -> 场景203 (游戏选择)
        transition_2_203 = self._find_transition(2, 1)
        if transition_2_203:
            success = await self.execute_transition(transition_2_203, check_cancel, report_progress)
            if not success:
                return False

        # 场景203 -> 场景101 (游戏启动)
        transition_203_101 = self._find_transition(203, 1)
        if transition_203_101:
            success = await self.execute_transition(transition_203_101, check_cancel, report_progress)
            if not success:
                return False

        # 继续执行后续场景跳转...
        # 这里可以根据实际需求继续添加更多的场景转移

        self.logger.info("足球比赛自动化流程完成")
        return True

    def _find_transition(self, scene_id: int, transition_id: int) -> Optional[SceneTransition]:
        """查找指定的场景转移"""
        transitions = self.get_available_transitions(scene_id)
        for t in transitions:
            if t.transition_id == transition_id:
                return t
        return None


# 单例
_scene_transition_executor = None


def get_scene_transition_executor() -> SceneTransitionExecutor:
    """获取场景转移执行器单例"""
    global _scene_transition_executor
    if _scene_transition_executor is None:
        _scene_transition_executor = SceneTransitionExecutor()
    return _scene_transition_executor

