"""
Template Manager - Streaming项目模板管理器

功能说明：
- 模板文件管理（加载、保存、缓存）
- 支持PNG文件和序列化数据
- 模板预加载和按需加载
- 从场景截图中提取模板

参考Streaming项目 (D:\\auto-xbox\\streaming\\xsrpst.py) 的设计：
- 原始模板：PNG文件在 template/ 目录
- 序列化数据：templates.dat (gzip压缩)
- 场景截图：用于生成模板

使用方式：
    from agent.vision.template_manager import StreamingTemplateManager

    manager = StreamingTemplateManager("templates")
    template = manager.get_template(1, 1)  # 场景1的模板1
"""

import os
import cv2
import compress_pickle
import numpy as np
from typing import Optional, Dict, List, Tuple
from pathlib import Path

from ..core.logger import get_logger
from configs.scene_schemas import SCENE_SCHEMAS, SCENE_COLUMNS


class StreamingTemplateManager:
    """
    Streaming风格模板管理器

    功能说明：
    - 管理模板文件的加载和缓存
    - 支持PNG源文件和序列化数据
    - 提供模板预加载和按需加载
    - 从场景截图中提取和生成模板

    使用方式：
        manager = StreamingTemplateManager("templates")

        # 加载单个模板
        template = manager.get_template(1, 1)

        # 预加载所有模板
        manager.preload_all_templates()

        # 保存序列化数据
        manager.save_serialized()
        
        # 从场景截图生成模板
        manager.generate_templates_from_scenes("scenes")
    """

    def __init__(
        self,
        template_dir: str = "templates",
        data_dir: str = "data",
        scene_dir: str = "scenes",
        use_cache: bool = True
    ):
        """
        初始化模板管理器

        参数说明：
        - template_dir: 模板图片目录
        - data_dir: 序列化数据目录
        - scene_dir: 场景截图目录
        - use_cache: 是否启用缓存
        """
        self.template_dir = Path(template_dir)
        self.data_dir = Path(data_dir)
        self.scene_dir = Path(scene_dir)
        self.use_cache = use_cache

        self.logger = get_logger('template_manager')

        self._template_cache: Dict[str, np.ndarray] = {}
        self._serialized_data: Optional[Dict[str, np.ndarray]] = None

        self.logger.info(f"StreamingTemplateManager 初始化，模板目录: {self.template_dir}")

    def _get_template_key(self, scene_id: int, template_id: int) -> str:
        """
        生成模板唯一标识符

        参数说明：
        - scene_id: 场景编号
        - template_id: 模板编号

        返回值：
        - 模板键（格式："{scene_id}.{template_id}"）
        """
        return f"{scene_id}.{template_id}"

    def _get_template_path(self, scene_id: int, template_id: int) -> Path:
        """
        获取模板文件路径

        参数说明：
        - scene_id: 场景编号
        - template_id: 模板编号

        返回值：
        - 模板PNG文件路径
        """
        filename = f"{scene_id}.{template_id}.png"
        return self.template_dir / filename

    def get_template(
        self,
        scene_id: int,
        template_id: int,
        use_serialized: bool = True
    ) -> Optional[np.ndarray]:
        """
        获取模板图片

        参数说明：
        - scene_id: 场景编号
        - template_id: 模板编号
        - use_serialized: 是否优先使用序列化数据

        返回值：
        - 成功：模板图片numpy数组
        - 失败：None
        """
        cache_key = self._get_template_key(scene_id, template_id)

        if self.use_cache and cache_key in self._template_cache:
            return self._template_cache[cache_key]

        if use_serialized:
            if self._serialized_data is None:
                self.load_serialized()

            if self._serialized_data and cache_key in self._serialized_data:
                template = self._serialized_data[cache_key]
                if self.use_cache:
                    self._template_cache[cache_key] = template
                return template

        template_path = self._get_template_path(scene_id, template_id)
        if not template_path.exists():
            self.logger.warning(f"模板文件不存在: {template_path}")
            return None

        try:
            template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
            if template is None:
                self.logger.error(f"无法读取模板: {template_path}")
                return None

            if self.use_cache:
                self._template_cache[cache_key] = template

            self.logger.debug(f"加载模板: {cache_key}")
            return template

        except Exception as e:
            self.logger.error(f"加载模板失败 {template_path}: {e}")
            return None

    def preload_all_templates(self) -> int:
        """
        预加载所有模板

        返回值：
        - 成功加载的模板数量
        """
        count = 0

        if not self.template_dir.exists():
            self.logger.warning(f"模板目录不存在: {self.template_dir}")
            return 0

        for template_file in self.template_dir.glob("*.png"):
            try:
                template_name = template_file.stem
                template = cv2.imread(str(template_file), cv2.IMREAD_COLOR)

                if template is not None:
                    self._template_cache[template_name] = template
                    count += 1

            except Exception as e:
                self.logger.error(f"预加载失败 {template_file}: {e}")

        self.logger.info(f"预加载完成，共 {count} 个模板")
        return count

    def load_serialized(self, filename: str = "templates.dat") -> bool:
        """
        加载序列化的模板数据

        参数说明：
        - filename: 序列化文件名

        返回值：
        - 是否加载成功
        """
        serialized_path = self.data_dir / filename

        if not serialized_path.exists():
            self.logger.warning(f"序列化文件不存在: {serialized_path}")
            return False

        try:
            with open(serialized_path, "rb") as f:
                data_bytes = f.read()

            self._serialized_data = compress_pickle.loads(
                data_bytes,
                compression="gzip"
            )

            self.logger.info(
                f"加载序列化数据完成，共 {len(self._serialized_data)} 个模板"
            )
            return True

        except Exception as e:
            self.logger.error(f"加载序列化数据失败: {e}")
            return False

    def save_serialized(self, filename: str = "templates.dat") -> bool:
        """
        保存模板到序列化数据文件

        参数说明：
        - filename: 序列化文件名

        返回值：
        - 是否保存成功
        """
        if not self._template_cache:
            self.logger.warning("没有缓存的模板可保存")
            return False

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            serialized_path = self.data_dir / filename

            data_bytes = compress_pickle.dumps(
                self._template_cache,
                compression="gzip"
            )

            with open(serialized_path, "wb") as f:
                f.write(data_bytes)

            self.logger.info(f"保存序列化数据: {serialized_path}")
            return True

        except Exception as e:
            self.logger.error(f"保存序列化数据失败: {e}")
            return False

    def clear_cache(self):
        """清空模板缓存"""
        self._template_cache.clear()
        self.logger.debug("模板缓存已清空")

    def get_cache_size(self) -> int:
        """获取缓存中的模板数量"""
        return len(self._template_cache)

    def get_template_list(self) -> list:
        """
        获取所有可用模板列表

        返回值：
        - 模板路径列表
        """
        if not self.template_dir.exists():
            return []

        return [
            str(f.relative_to(self.template_dir))
            for f in self.template_dir.glob("*.png")
        ]

    def _get_scene_path(self, scene_id: int) -> Path:
        """
        获取场景截图文件路径

        参数说明：
        - scene_id: 场景编号

        返回值：
        - 场景PNG文件路径
        """
        filename = f"{scene_id}.png"
        return self.scene_dir / filename

    def generate_templates_from_scenes(self, scene_dir: Optional[str] = None) -> int:
        """
        从场景截图中提取模板

        参考Streaming项目中的generate_templates()函数：
        - 读取场景截图
        - 根据scene_schemas.py中的定义截取模板区域
        - 保存为模板文件

        参数说明：
        - scene_dir: 场景截图目录（可选，默认使用初始化时设置的目录）

        返回值：
        - 成功生成的模板数量
        """
        if scene_dir:
            self.scene_dir = Path(scene_dir)

        if not self.scene_dir.exists():
            self.logger.error(f"场景目录不存在: {self.scene_dir}")
            return 0

        count = 0
        processed_scenes = set()

        for schema in SCENE_SCHEMAS:
            scene_id = schema[0]
            scene_width = schema[1]
            scene_height = schema[2]
            template_id = schema[3]
            template_left = schema[4]
            template_top = schema[5]
            template_right = schema[6]
            template_bottom = schema[7]

            if scene_id in processed_scenes:
                continue

            scene_path = self._get_scene_path(scene_id)
            if not scene_path.exists():
                self.logger.warning(f"场景文件不存在: {scene_path}")
                continue

            try:
                scene_mat = cv2.imread(str(scene_path), cv2.IMREAD_COLOR)
                if scene_mat is None:
                    self.logger.error(f"无法读取场景文件: {scene_path}")
                    continue

                if scene_mat.shape[1] < scene_width or scene_mat.shape[0] < scene_height:
                    self.logger.warning(
                        f"场景尺寸不匹配 {scene_path}: "
                        f"期望 {scene_width}x{scene_height}, "
                        f"实际 {scene_mat.shape[1]}x{scene_mat.shape[0]}"
                    )
                    continue

                processed_scenes.add(scene_id)

                for s in SCENE_SCHEMAS:
                    if s[0] != scene_id:
                        continue

                    tid = s[3]
                    t_left = s[4]
                    t_top = s[5]
                    t_right = s[6]
                    t_bottom = s[7]

                    try:
                        template_mat = scene_mat[t_top:t_bottom, t_left:t_right]

                        if template_mat.size == 0:
                            self.logger.warning(f"模板区域为空: 场景{scene_id}模板{tid}")
                            continue

                        self.template_dir.mkdir(parents=True, exist_ok=True)
                        template_path = self._get_template_path(scene_id, tid)
                        cv2.imwrite(str(template_path), template_mat)

                        self.logger.info(f"生成模板: {scene_id}.{tid}")
                        count += 1

                    except Exception as e:
                        self.logger.error(f"提取模板失败 场景{scene_id}模板{tid}: {e}")
                        continue

            except Exception as e:
                self.logger.error(f"处理场景失败 {scene_path}: {e}")
                continue

        self.logger.info(f"模板生成完成，共生成 {count} 个模板")
        
        if count > 0:
            self.save_serialized()
            
        return count

    def compare_templates(self, other: Dict[str, np.ndarray]) -> bool:
        """
        比较当前缓存的模板和另一个模板字典是否一致

        参数说明：
        - other: 另一个模板字典

        返回值：
        - True: 完全一致
        - False: 不一致
        """
        if not self._template_cache:
            return len(other) == 0

        if len(self._template_cache) != len(other):
            return False

        for key, template1 in self._template_cache.items():
            if key not in other:
                return False

            template2 = other[key]
            if template1.shape != template2.shape:
                return False

            comparison = cv2.compare(template1, template2, cv2.CMP_NE)
            if np.sum(comparison) > 0:
                return False

        return True

    def export_as_serialized(self, output_path: Optional[str] = None) -> bool:
        """
        将当前缓存的模板导出为序列化文件

        参数说明：
        - output_path: 输出文件路径（可选）

        返回值：
        - 是否导出成功
        """
        if not self._template_cache:
            self.logger.warning("没有缓存的模板可导出")
            return False

        if output_path is None:
            output_path = str(self.data_dir / "templates.dat")

        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)

            data_bytes = compress_pickle.dumps(
                self._template_cache,
                compression="gzip"
            )

            with open(output_path, "wb") as f:
                f.write(data_bytes)

            self.logger.info(f"模板已导出到: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"导出模板失败: {e}")
            return False


# 账号开通、切换与 FC 启动导航所需的场景。
STEP4_REQUIRED_SCENE_IDS = [
    1, 2, 3, 4, 5, 6, 7, 10, 24, 101, 126, 127, 147, 149, 203,
]


def required_template_names(scene_ids: Optional[List[int]] = None) -> List[str]:
    """返回指定场景的模板文件名（{scene}.{template}.png）。"""
    target_scenes = set(scene_ids or STEP4_REQUIRED_SCENE_IDS)
    names: List[str] = []
    for schema in SCENE_SCHEMAS:
        row = dict(zip(SCENE_COLUMNS, schema))
        scene_id = int(row["scene_id"])
        if scene_id not in target_scenes:
            continue
        template_id = int(row["template_id"])
        names.append(f"{scene_id}.{template_id}.png")
    return sorted(set(names))


def validate_templates(
    template_dir: str,
    scene_ids: Optional[List[int]] = None,
) -> Tuple[bool, List[str]]:
    """
    检查 template_dir 下必需的 PNG 模板是否存在。

    返回 (ok, missing_filenames)。
    """
    root = Path(template_dir)
    missing = [
        name for name in required_template_names(scene_ids)
        if not (root / name).exists()
    ]
    return len(missing) == 0, missing
