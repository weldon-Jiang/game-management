# Streaming项目模板匹配核心逻辑详细分析

## 📋 分析目标

深入分析 `D:\auto-xbox\streaming` 项目的模板匹配核心逻辑，包括：
1. **模板的存储位置**
2. **模板的获取方式**
3. **模板匹配的执行流程**
4. **如何在Agent项目中复用这些模板**

---

## 📁 模板存储结构

### 1. 原始模板图片目录

**路径**：`D:\auto-xbox\streaming\template\`

**命名规则**：`{scene_id}.{template_id}.png`

**示例**：
```
template/
├── 1.1.png    # 场景1的模板1（我的游戏和应用图标）
├── 2.1.png    # 场景2的模板1（西瓜图标）
├── 2.2.png    # 场景2的模板2（主页图标）
├── 3.1.png    # 场景3的模板1（档案和系统文字）
├── 3.2.png    # 场景3的模板2（添加和切换文字）
└── ...
```

### 2. 序列化的模板数据文件

**路径**：`D:\auto-xbox\streaming\data\templates.dat`

**格式**：使用 `compress_pickle` 进行 gzip 压缩的二进制文件

**内容**：包含所有模板图片的 numpy 数组数据

**加载方式** ([xsrputil.py:L5959-L5987](file:///D:/auto-xbox/streaming/xsrpst.py#L5959-L5987))：

```python
def get_templates() -> dict:
    """读取内置的模板数据"""
    templates = dict()

    try:
        # 模板数据文件路径
        template_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data",
            "templates.dat"
        )

        if os.path.exists(template_file):
            # 读取压缩的模板数据
            with open(template_file, "rb") as in_fs:
                templates_bytes = in_fs.read()

            # 反序列化（gzip解压 + pickle加载）
            templates = compress_pickle.loads(templates_bytes, compression="gzip")
        else:
            templates = dict()

    except(BaseException) as err:
        logger.error(f'加载模板数据文件出错 {err}')

    return templates
```

### 3. 模板配置数据

**位置**：代码中直接定义 ([xsrpst.py:L13-L600](file:///D:/auto-xbox/streaming/xsrpst.py#L13-L600))

**格式**：Python 列表，定义每个场景的模板匹配规则

**结构**：

```python
schema = [
    场景编号,                    # scene_id
    场景显示宽度,                # scene_width
    场景显示高度,                # scene_height

    模板编号,                    # template_id
    模板左上角X,                # template_lefttop_x
    模板左上角Y,                # template_lefttop_y
    模板右下角X,                # template_rightbottom_x
    模板右下角Y,                # template_rightbottom_y

    查找区域编号,               # search_id
    查找区域左上角X,             # search_lefttop_x
    查找区域左上角Y,             # search_lefttop_y
    查找区域右下角X,             # search_rightbottom_x
    查找区域右下角Y,             # search_rightbottom_y
    相似度阈值百分比,            # likeness (0-100)
    比对算法编号                # algorithm
]
```

**示例** ([xsrpst.py:L19-L38](file:///D:/auto-xbox/streaming/xsrpst.py#L19-L38))：

```python
# 场景1：刚串流上的主页界面
schema = [
    1,      # 场景编号
    960,    # 场景显示宽度
    540,    # 场景显示高度

    1,      # 模板编号
    401,    # 模板左上角X
    50,     # 模板左上角Y
    558,    # 模板右下角X
    63,     # 模板右下角Y

    1,      # 查找区域编号
    399,    # 查找区域左上角X
    48,     # 查找区域左上角Y
    600,    # 查找区域右下角X
    65,     # 查找区域右下角Y
    90,     # 相似度阈值（90%）
    3       # 比对算法编号（3=TM_CCORR_NORMED）
]
schemas += [schema]
```

---

## 🔍 模板获取方式

### 1. 从本地文件获取单个模板

**函数**：[get_template()](file:///D:/auto-xbox/streaming/xsrpst.py#L5921-L5956)

```python
def get_template(scene_id:int, template_id:int, templates:dict):
    """读取单个模板数据"""

    # 生成模板标记（token）
    token = f'{scene_id}.{template_id}'

    # 优先从内存字典中获取
    if token in templates.keys():
        return True, templates[token]

    # 回退：从本地PNG文件读取
    try:
        template_file = os.path.join(
            os.path.dirname(__file__),
            "template",
            f'{scene_id}.{template_id}.png'
        )

        if os.path.exists(template_file):
            template_mat = cv2.imread(template_file)
            return True, template_mat
        else:
            return False, None

    except Exception as err:
        logger.error(f"读取模板文件失败: {err}")
        return False, None
```

**优先级**：
1. ✅ 从内存字典 `templates` 获取（加载一次，多次使用）
2. ✅ 从 `template/` 目录的PNG文件读取（开发模式）

### 2. 批量加载所有模板

**函数**：[get_templates()](file:///D:/auto-xbox/streaming/xsrpst.py#L5959-L5987)

```python
def get_templates() -> dict:
    """读取内置的模板数据"""

    templates = dict()

    # 尝试从序列化的数据文件加载
    template_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data",
        "templates.dat"
    )

    if os.path.exists(template_file):
        with open(template_file, "rb") as in_fs:
            templates_bytes = in_fs.read()

        # 使用 gzip 解压 + pickle 反序列化
        templates = compress_pickle.loads(templates_bytes, compression="gzip")

    return templates
```

### 3. 模板标记生成

**函数**：[get_template_token()](file:///D:/auto-xbox/streaming/xsrpst.py#L5916-L5917)

```python
def get_template_token(scene_id:int, template_id:int) -> str:
    """生成模板的唯一标识符"""
    return f'{scene_id}.{template_id}'
```

**示例**：
- `get_template_token(1, 1)` → `"1.1"`
- `get_template_token(2, 1)` → `"2.1"`

---

## ⚙️ 模板匹配核心算法

### 1. 单场景识别

**函数**：[recognize_scene()](file:///D:/auto-xbox/streaming/xsrpst.py#L6224-L6315)

```python
def recognize_scene(capture_mat, candidate_scene_id, df_templates, templates):
    """
    识别单个场景

    参数：
    - capture_mat: 当前截取的图像矩阵
    - candidate_scene_id: 待识别的场景编号
    - df_templates: 场景模板定义表
    - templates: 模板数据字典
    """

    # 1. 筛选当前场景的所有模板定义
    df_templates_by_scene = df_templates[
        df_templates[Template.key_scene_id] == candidate_scene_id
    ]

    # 2. 获取所有查找区域
    search_ids = list(set(df_templates_by_scene[Template.key_search_id]))

    # 3. 遍历每个查找区域
    for search_id in search_ids:
        # 读取该场景+区域下的所有模板
        df_templates_by_scene_search = df_templates[
            (df_templates[Template.key_scene_id] == candidate_scene_id) &
            (df_templates[Template.key_search_id] == search_id)
        ]

        # 4. 遍历每个模板
        for template_item in template_dict:
            # 截取搜索区域
            src_mat = capture_mat[
                template_item[Template.key_search_lefttop_y]:
                template_item[Template.key_search_rightbottom_y],
                template_item[Template.key_search_lefttop_x]:
                template_item[Template.key_search_rightbottom_x]
            ].copy()

            # 加载模板图片
            result, template_mat = get_template(
                candidate_scene_id,
                template_id,
                templates
            )

            # 执行模板匹配
            method = template_item[Template.key_search_algorithm]
            result = cv2.matchTemplate(src_mat, template_mat, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # 判断是否满足阈值
            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                # 平方差算法：min_val越小越好
                if min_val <= template_item[Template.key_search_likeness] / 100:
                    template_flags[template_idx] = True
                    template_likeness[template_idx] = 1.0 - min_val
            else:
                # 相关系数算法：max_val越大越好
                if max_val >= template_item[Template.key_search_likeness] / 100:
                    template_flags[template_idx] = True
                    template_likeness[template_idx] = max_val

    # 5. 判断该场景是否识别成功
    if template_flags.all():
        return True, np.mean(template_likeness)

    return False, 0
```

### 2. 多场景批量识别

**函数**：[recognize_scenes()](file:///D:/auto-xbox/streaming/xsrpst.py#L6160-L6219)

```python
def recognize_scenes(capture_mat:cv2.Mat, limit_ids:list) -> int:
    """
    批量识别场景

    返回：
    - 匹配度最高的场景编号，失败返回-1
    """

    ret_scene_id = -1
    max_likeness = 0

    # 加载模板配置和模板数据
    df_templates = get_templates_schema()
    templates = get_templates()

    # 获取候选场景列表
    if len(limit_ids) > 0:
        candidate_scene_ids = limit_ids
    else:
        # 从配置中获取所有场景
        candidate_scene_ids = list(set(df_templates[Template.key_scene_id]))

    # 逐个识别候选场景
    for candidate_scene_id in candidate_scene_ids:
        result, mean_likeness = recognize_scene(
            capture_mat,
            candidate_scene_id,
            df_templates,
            templates
        )

        if result and mean_likeness > max_likeness:
            max_likeness = mean_likeness
            ret_scene_id = candidate_scene_id

    return ret_scene_id
```

---

## 🎯 支持的匹配算法

### 算法编号对照表

| 算法编号 | OpenCV常量 | 说明 | 阈值判断 |
|---------|-----------|------|---------|
| 0 | TM_SQDIFF | 平方差匹配 | min_val ≤ 阈值 |
| 1 | TM_SQDIFF_NORMED | 归一化平方差 | min_val ≤ 阈值 |
| 2 | TM_CCORR | 相关匹配 | max_val ≥ 阈值 |
| 3 | TM_CCORR_NORMED | 归一化相关 | max_val ≥ 阈值 |
| 4 | TM_CCOEFF | 相关系数 | max_val ≥ 阈值 |
| 5 | TM_CCOEFF_NORMED | 归一化相关系数 | max_val ≥ 阈值 |

### 常用算法对比

```
推荐算法（按性能排序）：
1. TM_CCORR_NORMED (3) - 平衡性能和准确性 ⭐ 推荐
2. TM_CCOEFF_NORMED (5) - 最佳准确性，但稍慢
3. TM_SQDIFF_NORMED (1) - 适合光照变化场景
```

---

## 📊 模板数据结构详解

### 模板配置表（get_templates_schema）

返回 pandas DataFrame，包含以下列：

| 列名 | 类型 | 说明 |
|------|------|------|
| `场景编号` | int | 场景的唯一标识 |
| `场景显示宽度` | int | 场景截图宽度（通常960） |
| `场景显示高度` | int | 场景截图高度（通常540） |
| `场景的模板 编号` | int | 模板的唯一标识 |
| `场景的模板 左上角 X` | int | 模板在原图中的位置 |
| `场景的模板 左上角 Y` | int | 模板在原图中的位置 |
| `场景的模板 右下角 X` | int | 模板在原图中的位置 |
| `场景的模板 右下角 Y` | int | 模板在原图中的位置 |
| `查找区域编号` | int | 搜索区域的标识 |
| `查找区域 左上角 X` | int | 搜索区域位置 |
| `查找区域 左上角 Y` | int | 搜索区域位置 |
| `查找区域 右下角 X` | int | 搜索区域位置 |
| `查找区域 右下角 Y` | int | 搜索区域位置 |
| `查找相似度` | int | 相似度阈值（0-100） |
| `比对算法 编号` | int | 使用的算法编号 |

### 模板数据字典（templates）

**结构**：`dict[str, np.ndarray]`

**键格式**：`"{scene_id}.{template_id}"`

**值**：模板图片的 numpy 数组（BGR格式）

```python
{
    "1.1": np.array([[[...]]]),  # 场景1的模板1
    "2.1": np.array([[[...]]]),  # 场景2的模板1
    "2.2": np.array([[[...]]]),  # 场景2的模板2
    ...
}
```

---

## 🛠️ Agent项目适配方案

### 1. 模板迁移策略

**步骤1：导出Streaming项目的模板**

```python
# 在Streaming项目中运行
from xsrpst import get_templates, get_templates_schema, save_templates

# 方式1：使用现有的templates.dat
templates = get_templates()

# 方式2：重新生成（如果需要更新模板）
save_templates()
```

**步骤2：在Agent项目中创建模板目录**

```python
# Agent项目结构
agent/
├── templates/
│   ├── 1.1.png   # 场景1的模板1
│   ├── 2.1.png   # 场景2的模板1
│   └── ...
└── configs/
    └── template_schema.py  # 模板配置
```

**步骤3：复用Streaming的模板配置**

```python
# Agent项目 - configs/template_schema.py

# 直接复制Streaming的schema定义
TEMPLATE_SCHEMAS = [
    # 场景1
    [1, 960, 540, 1, 401, 50, 558, 63, 1, 399, 48, 600, 65, 90, 3],
    # 场景2
    [2, 960, 540, 1, 42, 108, 45, 130, 1, 40, 106, 47, 132, 90, 3],
    # ...
]
```

### 2. 模板加载实现

**方案A：保持PNG文件格式（推荐）**

```python
# Agent项目 - vision/template_loader.py

import os
import cv2
from pathlib import Path

class TemplateLoader:
    """模板加载器"""

    def __init__(self, template_dir: str = "templates"):
        self.template_dir = Path(template_dir)
        self._cache = {}

    def get_template(self, scene_id: int, template_id: int) -> Optional[np.ndarray]:
        """获取模板图片"""
        token = f"{scene_id}.{template_id}"

        # 优先从缓存获取
        if token in self._cache:
            return self._cache[token]

        # 加载PNG文件
        template_path = self.template_dir / f"{scene_id}.{template_id}.png"
        if template_path.exists():
            template = cv2.imread(str(template_path))
            if template is not None:
                self._cache[token] = template
                return template

        return None

    def load_all_templates(self):
        """预加载所有模板到缓存"""
        for template_file in self.template_dir.glob("*.png"):
            template = cv2.imread(str(template_file))
            if template is not None:
                self._cache[template_file.stem] = template
```

**方案B：使用序列化数据（节省磁盘IO）**

```python
# Agent项目 - vision/template_store.py

import compress_pickle

class TemplateStore:
    """模板存储管理器"""

    def __init__(self, data_file: str = "data/templates.dat"):
        self.data_file = data_file
        self._templates = {}

    def load(self) -> dict:
        """加载所有模板"""
        if os.path.exists(self.data_file):
            with open(self.data_file, "rb") as f:
                self._templates = compress_pickle.loads(
                    f.read(),
                    compression="gzip"
                )
        return self._templates

    def save(self, templates: dict):
        """保存所有模板"""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "wb") as f:
            f.write(compress_pickle.dumps(templates, compression="gzip"))

    def get_template(self, scene_id: int, template_id: int):
        """获取单个模板"""
        token = f"{scene_id}.{template_id}"
        return self._templates.get(token)
```

### 3. 匹配器实现

**复用Streaming的匹配逻辑** ([xsrpst.py:L6224-L6315](file:///D:/auto-xbox/streaming/xsrpst.py#L6224-L6315))：

```python
# Agent项目 - vision/scene_matcher.py

import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class TemplateConfig:
    """模板配置"""
    scene_id: int
    template_id: int
    search_lefttop_x: int
    search_lefttop_y: int
    search_rightbottom_x: int
    search_rightbottom_y: int
    likeness: int  # 0-100
    algorithm: int

class SceneMatcher:
    """场景匹配器"""

    ALGORITHMS = {
        0: cv2.TM_SQDIFF,
        1: cv2.TM_SQDIFF_NORMED,
        2: cv2.TM_CCORR,
        3: cv2.TM_CCORR_NORMED,
        4: cv2.TM_CCOEFF,
        5: cv2.TM_CCOEFF_NORMED,
    }

    def __init__(self, template_loader: TemplateLoader, schema: List[TemplateConfig]):
        self.template_loader = template_loader
        self.schema = schema
        self._scene_configs = self._build_scene_configs()

    def _build_scene_configs(self) -> dict:
        """按场景分组配置"""
        configs = {}
        for config in self.schema:
            if config.scene_id not in configs:
                configs[config.scene_id] = []
            configs[config.scene_id].append(config)
        return configs

    def recognize_scene(self, capture_mat: np.ndarray, scene_id: int) -> Tuple[bool, float]:
        """识别单个场景"""
        configs = self._scene_configs.get(scene_id, [])
        if not configs:
            return False, 0.0

        template_flags = []
        template_likeness = []

        for config in configs:
            # 加载模板
            template = self.template_loader.get_template(
                config.scene_id,
                config.template_id
            )
            if template is None:
                continue

            # 截取搜索区域
            search_region = capture_mat[
                config.search_lefttop_y:config.search_rightbottom_y,
                config.search_lefttop_x:config.search_rightbottom_x
            ]

            # 执行匹配
            method = self.ALGORITHMS.get(config.algorithm, cv2.TM_CCORR_NORMED)
            result = cv2.matchTemplate(search_region, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            # 判断阈值
            threshold = config.likelihood / 100.0
            if config.algorithm in [0, 1]:  # SQDIFF
                matched = min_val <= threshold
                similarity = 1.0 - min_val
            else:
                matched = max_val >= threshold
                similarity = max_val

            template_flags.append(matched)
            template_likeness.append(similarity)

        # 所有模板都匹配才认为场景识别成功
        if all(template_flags):
            return True, np.mean(template_likeness)

        return False, 0.0

    def recognize_scenes(
        self,
        capture_mat: np.ndarray,
        candidate_ids: Optional[List[int]] = None
    ) -> Tuple[int, float]:
        """批量识别场景，返回匹配度最高的场景"""
        if candidate_ids is None:
            candidate_ids = list(self._scene_configs.keys())

        best_scene_id = -1
        best_likeness = 0.0

        for scene_id in candidate_ids:
            matched, likeness = self.recognize_scene(capture_mat, scene_id)
            if matched and likeness > best_likeness:
                best_scene_id = scene_id
                best_likeness = likeness

        return best_scene_id, best_likeness
```

---

## 📋 Streaming项目当前模板列表

根据代码分析，当前定义的场景和模板：

| 场景ID | 场景名称 | 模板数量 | 说明 |
|--------|---------|---------|------|
| 1 | 刚串流上的主页界面 | 1 | 检测"我的游戏和应用"图标 |
| 2 | 西瓜主页界面 | 2 | 检测"西瓜图标"和"主页图标" |
| 3 | 档案和系统页面-添加和切换 | 3 | 检测"档案和系统"等文字 |
| 4 | 档案和系统页面-注销 | 1 | 检测"注销"选项 |
| 5 | 你是谁-添加和切换页面 | ? | 待续... |

**注意**：完整的模板列表在 [xsrpst.py:L13-L600](file:///D:/auto-xbox/streaming/xsrpst.py#L13-L600)

---

## 🔄 完整使用流程

```
┌─────────────────────────────────────────────────────────────┐
│                 模板匹配完整使用流程                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 初始化阶段                                              │
│     ├─ 加载模板配置 (get_templates_schema)                  │
│     ├─ 加载模板数据 (get_templates)                         │
│     └─ 建立场景-模板索引 (_build_scene_configs)             │
│                                                             │
│  2. 运行时阶段                                              │
│     ├─ 捕获当前画面 (frame_capture)                         │
│     ├─ 传入场景识别函数 (recognize_scenes)                  │
│     │  └─ 遍历候选场景                                      │
│     │  └─ 对每个场景调用 recognize_scene                    │
│     │     ├─ 加载模板图片                                    │
│     │     ├─ 截取搜索区域                                    │
│     │     ├─ 执行 cv2.matchTemplate                         │
│     │     └─ 判断阈值是否满足                                │
│     └─ 返回匹配度最高的场景                                  │
│                                                             │
│  3. 后续处理                                                │
│     ├─ 根据识别的场景执行自动化操作                          │
│     ├─ 触发场景转移                                         │
│     └─ 更新游戏状态                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 💡 最佳实践建议

### 1. 模板管理
- ✅ 保持PNG源文件，便于可视化编辑
- ✅ 使用压缩序列化文件加速加载
- ✅ 实现模板缓存避免重复读取

### 2. 匹配策略
- ✅ 优先使用 TM_CCORR_NORMED 算法
- ✅ 相似度阈值设为 0.8-0.9
- ✅ 多区域匹配提高准确性

### 3. 性能优化
- ✅ 预加载常用场景的模板
- ✅ 限制候选场景数量
- ✅ 使用异步执行避免阻塞

---

*分析完成时间：2026-06-02*
