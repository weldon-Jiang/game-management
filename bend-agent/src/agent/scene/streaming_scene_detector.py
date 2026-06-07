"""
Streaming-style Scene Detector - 基于Streaming项目的场景检测器

功能说明：
- 支持多区域模板匹配
- 支持场景识别和转移
- 使用 Streaming 项目的场景配置

技术实现：
- 参考 D:\\auto-xbox\\streaming\\xsrpst.py 的场景识别逻辑
- 使用 TM_CCORR_NORMED 算法
- 支持场景转移图

使用方式：
    from agent.scene.streaming_scene_detector import StreamingSceneDetector

    detector = StreamingSceneDetector(template_dir="templates")
    scene_id = detector.recognize_scene(frame)
"""

import os
import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass
from enum import Enum

from ..core.logger import get_logger
from configs.scene_schemas import SCENE_SCHEMAS, SCENE_COLUMNS, SCENE_NAMES, ALGORITHM_NAMES


class MatchAlgorithm(Enum):
    """OpenCV 模板匹配算法枚举"""
    TM_SQDIFF = 0              # 平方差匹配
    TM_SQDIFF_NORMED = 1      # 归一化平方差
    TM_CCORR = 2              # 相关匹配
    TM_CCORR_NORMED = 3       # 归一化相关（推荐）
    TM_CCOEFF = 4             # 相关系数
    TM_CCOEFF_NORMED = 5      # 归一化相关系数


@dataclass
class SceneMatchResult:
    """场景匹配结果"""
    scene_id: int
    matched: bool
    confidence: float
    template_results: List[Dict]


class StreamingSceneDetector:
    """
    Streaming风格场景检测器

    功能说明：
    - 加载场景模板配置
    - 执行多区域模板匹配
    - 识别当前Xbox UI场景
    - 支持场景转移逻辑

    使用方式：
        detector = StreamingSceneDetector(template_dir="templates")
        result = detector.recognize_scene(frame)
        if result.matched:
            print(f"识别到场景: {result.scene_id}")
    """

    def __init__(
        self,
        template_dir: str = "templates",
        default_threshold: float = 0.8,
        cache_enabled: bool = True
    ):
        """
        初始化场景检测器

        参数说明：
        - template_dir: 模板图片目录路径
        - default_threshold: 默认匹配置信度阈值
        - cache_enabled: 是否启用模板缓存
        """
        self.template_dir = template_dir
        self.default_threshold = default_threshold
        self.cache_enabled = cache_enabled

        self.logger = get_logger('streaming_scene')

        self._schemas = self._load_schemas()
        self._scene_configs = self._build_scene_configs()
        self._template_cache: Dict[str, np.ndarray] = {}
        self._last_scene_id = -1

        self.logger.info(f"StreamingSceneDetector 初始化完成，场景数量: {len(self._scene_configs)}")

    def _load_schemas(self) -> List[List]:
        """
        加载场景模板配置

        返回值：
        - 场景配置列表
        """
        return SCENE_SCHEMAS

    def _build_scene_configs(self) -> Dict[int, List[Dict]]:
        """
        构建场景配置索引

        返回值：
        - 按场景ID分组的配置字典
        """
        configs = {}

        for schema in self._schemas:
            config = dict(zip(SCENE_COLUMNS, schema))
            scene_id = int(config['scene_id'])

            if scene_id not in configs:
                configs[scene_id] = []

            configs[scene_id].append(config)

        return configs

    def _load_template_from_streaming_dat(
        self, scene_id: int, template_id: int
    ) -> Optional[np.ndarray]:
        """Fallback to streaming/data/templates.dat when PNG is unavailable."""
        try:
            from ..vision.template_manager import StreamingTemplateManager

            streaming_dat = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                "..", "..", "streaming", "data", "templates.dat"
            )
            streaming_dat = os.path.normpath(streaming_dat)
            alt_dat = os.path.normpath(r"D:\auto-xbox\streaming\data\templates.dat")

            manager = StreamingTemplateManager(template_dir=self.template_dir)
            for dat_path in (streaming_dat, alt_dat):
                if os.path.exists(dat_path):
                    manager.load_serialized(os.path.basename(dat_path))
                    manager.data_dir = os.path.dirname(dat_path)
                    manager.load_serialized(os.path.basename(dat_path))
                    template = manager.get_template(scene_id, template_id, use_serialized=True)
                    if template is not None:
                        return template
        except Exception as exc:
            self.logger.debug(f"templates.dat fallback failed: {exc}")
        return None

    def _get_template_path(self, scene_id: int, template_id: int) -> str:
        """
        获取模板文件路径

        参数说明：
        - scene_id: 场景编号
        - template_id: 模板编号

        返回值：
        - 模板文件完整路径
        """
        template_name = f"{scene_id}.{template_id}.png"
        return os.path.join(self.template_dir, template_name)

    def _load_template(self, scene_id: int, template_id: int) -> Optional[np.ndarray]:
        """
        加载模板图片

        参数说明：
        - scene_id: 场景编号
        - template_id: 模板编号

        返回值：
        - 成功：模板图片numpy数组
        - 失败：None
        """
        cache_key = f"{scene_id}.{template_id}"

        if self.cache_enabled and cache_key in self._template_cache:
            return self._template_cache[cache_key]

        template_path = self._get_template_path(scene_id, template_id)

        if not os.path.exists(template_path):
            fallback = self._load_template_from_streaming_dat(scene_id, template_id)
            if fallback is not None:
                if self.cache_enabled:
                    self._template_cache[cache_key] = fallback
                return fallback
            self.logger.warning(f"模板文件不存在: {template_path}")
            return None

        try:
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self.logger.error(f"无法读取模板: {template_path}")
                return None

            if self.cache_enabled:
                self._template_cache[cache_key] = template

            self.logger.debug(f"加载模板: {cache_key}")
            return template

        except Exception as e:
            self.logger.error(f"加载模板失败 {template_path}: {e}")
            return None

    def _match_single_template(
        self,
        search_region: np.ndarray,
        template: np.ndarray,
        algorithm_id: int,
        threshold: float
    ) -> Tuple[bool, float]:
        """
        执行单个模板匹配

        参数说明：
        - search_region: 搜索区域图像
        - template: 模板图像
        - algorithm_id: 算法编号
        - threshold: 相似度阈值

        返回值：
        - (是否匹配, 相似度)
        """
        try:
            method = algorithm_id
            result = cv2.matchTemplate(search_region, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if algorithm_id in [0, 1]:
                similarity = 1.0 - min_val
                matched = min_val <= threshold
            else:
                similarity = max_val
                matched = max_val >= threshold

            return matched, similarity

        except Exception as e:
            self.logger.error(f"模板匹配失败: {e}")
            return False, 0.0

    def recognize_scene(
        self,
        frame: np.ndarray,
        scene_id: Optional[int] = None,
        threshold: Optional[float] = None
    ) -> SceneMatchResult:
        """
        识别场景

        参数说明：
        - frame: 当前帧图像
        - scene_id: 指定场景ID（None表示识别所有场景）
        - threshold: 相似度阈值（None使用默认值）

        返回值：
        - SceneMatchResult: 匹配结果
        """
        if threshold is None:
            threshold = self.default_threshold

        if scene_id is not None:
            return self._recognize_single_scene(frame, scene_id, threshold)
        else:
            return self._recognize_all_scenes(frame, threshold)

    def _normalize_frame(self, frame: np.ndarray, scene_id: int) -> np.ndarray:
        """Resize frame to schema scene size (templates are authored at 960x540)."""
        configs = self._scene_configs.get(scene_id)
        if not configs:
            return frame
        target_w = int(configs[0]["scene_width"])
        target_h = int(configs[0]["scene_height"])
        h, w = frame.shape[:2]
        if w == target_w and h == target_h:
            return frame
        return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)

    def _recognize_single_scene(
        self,
        frame: np.ndarray,
        scene_id: int,
        threshold: float
    ) -> SceneMatchResult:
        """
        识别单个场景（按 search_id 分组，对齐 streaming/xsrpst.py）
        """
        frame = self._normalize_frame(frame, scene_id)

        if scene_id not in self._scene_configs:
            self.logger.warning(f"场景ID不存在: {scene_id}")
            return SceneMatchResult(
                scene_id=scene_id,
                matched=False,
                confidence=0.0,
                template_results=[]
            )

        configs = self._scene_configs[scene_id]
        search_groups: Dict[int, List[Dict]] = {}
        for config in configs:
            search_id = int(config['search_id'])
            search_groups.setdefault(search_id, []).append(config)

        best_confidence = 0.0
        best_template_results: List[Dict] = []
        scene_matched = False

        for search_id, group_configs in search_groups.items():
            templates_in_group: Dict[int, List[Dict]] = {}
            for config in group_configs:
                templates_in_group.setdefault(int(config['template_id']), []).append(config)

            group_results = []
            likeness_values = []
            group_matched = True

            for template_id, template_configs in templates_in_group.items():
                template = self._load_template(scene_id, template_id)
                if template is None:
                    group_matched = False
                    group_results.append({
                        'template_id': template_id,
                        'search_id': search_id,
                        'matched': False,
                        'similarity': 0.0,
                    })
                    continue

                template_matched = False
                best_similarity = 0.0
                for config in template_configs:
                    search_region = frame[
                        int(config['search_top']):int(config['search_bottom']),
                        int(config['search_left']):int(config['search_right']),
                    ]
                    if search_region.size == 0:
                        continue

                    # 对齐 streaming/xsrpst.py：默认使用 schema 相似度；仅 Xbox 系统 UI(<=64) 允许运行时降低阈值
                    schema_threshold = float(config['likeness']) / 100.0
                    if threshold < schema_threshold and scene_id <= 64:
                        match_threshold = threshold
                    else:
                        match_threshold = schema_threshold
                    matched, similarity = self._match_single_template(
                        search_region,
                        template,
                        int(config['algorithm']),
                        match_threshold,
                    )
                    if matched:
                        template_matched = True
                        best_similarity = max(best_similarity, similarity)

                if not template_matched:
                    group_matched = False
                else:
                    likeness_values.append(best_similarity)

                group_results.append({
                    'template_id': template_id,
                    'search_id': search_id,
                    'matched': template_matched,
                    'similarity': best_similarity,
                })

            if group_matched and likeness_values:
                scene_matched = True
                avg_confidence = sum(likeness_values) / len(likeness_values)
                if avg_confidence >= best_confidence:
                    best_confidence = avg_confidence
                    best_template_results = group_results

        return SceneMatchResult(
            scene_id=scene_id,
            matched=scene_matched,
            confidence=best_confidence,
            template_results=best_template_results,
        )

    def _recognize_all_scenes(
        self,
        frame: np.ndarray,
        threshold: float
    ) -> SceneMatchResult:
        """
        识别所有场景，返回匹配度最高的场景

        参数说明：
        - frame: 当前帧图像
        - threshold: 相似度阈值

        返回值：
        - SceneMatchResult: 最佳匹配结果
        """
        best_scene_id = -1
        best_confidence = 0.0
        best_template_results = []

        for scene_id in sorted(self._scene_configs.keys()):
            result = self._recognize_single_scene(frame, scene_id, threshold)

            if result.matched and result.confidence > best_confidence:
                best_scene_id = scene_id
                best_confidence = result.confidence
                best_template_results = result.template_results

        if best_scene_id != self._last_scene_id:
            self.logger.info(
                f"场景切换: {self._get_scene_name(self._last_scene_id)} "
                f"-> {self._get_scene_name(best_scene_id)}"
            )
            self._last_scene_id = best_scene_id

        return SceneMatchResult(
            scene_id=best_scene_id,
            matched=best_scene_id > 0,
            confidence=best_confidence,
            template_results=best_template_results
        )

    def _get_scene_name(self, scene_id: int) -> str:
        """获取场景名称"""
        if scene_id <= 0:
            return "未知场景"
        return SCENE_NAMES.get(scene_id, f"场景{scene_id}")

    def recognize_scenes_batch(
        self,
        frame: np.ndarray,
        candidate_ids: List[int]
    ) -> SceneMatchResult:
        """
        批量识别指定场景列表

        参数说明：
        - frame: 当前帧图像
        - candidate_ids: 候选场景ID列表

        返回值：
        - SceneMatchResult: 最佳匹配结果
        """
        best_scene_id = -1
        best_confidence = 0.0
        best_template_results = []

        for scene_id in candidate_ids:
            result = self._recognize_single_scene(frame, scene_id, self.default_threshold)

            if result.matched and result.confidence > best_confidence:
                best_scene_id = scene_id
                best_confidence = result.confidence
                best_template_results = result.template_results

        return SceneMatchResult(
            scene_id=best_scene_id,
            matched=best_scene_id > 0,
            confidence=best_confidence,
            template_results=best_template_results
        )

    def clear_cache(self):
        """清空模板缓存"""
        self._template_cache.clear()
        self.logger.debug("模板缓存已清空")

    def get_scene_count(self) -> int:
        """获取场景总数"""
        return len(self._scene_configs)

    def get_template_count(self) -> int:
        """获取模板总数"""
        return len(self._schemas)
