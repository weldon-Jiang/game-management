# Streaming模板匹配核心要点

## 1️⃣ 模板存放方式

### 📁 存储位置
```
D:\auto-xbox\streaming\
├── template\              # 原始模板图片目录
│   ├── 1.1.png           # 场景1-模板1
│   ├── 2.1.png           # 场景2-模板1
│   └── ...
└── data\
    └── templates.dat     # 序列化模板数据（gzip压缩）
```

### 🎯 命名规则
- **PNG文件**：`{scene_id}.{template_id}.png`
  - 示例：`1.1.png` = 场景1的模板1
- **序列化键**：`f'{scene_id}.{template_id}'`
  - 示例：`"1.1"` = 场景1的模板1

### 📊 配置数据结构
每个场景的配置定义（硬编码在 [xsrpst.py:L13-600](file:///D:/auto-xbox/streaming/xsrpst.py#L13-L600)）：

```python
[
    场景编号,          # 1, 2, 3...
    场景宽度,          # 960
    场景高度,          # 540

    模板编号,          # 1, 2, 3...
    模板左上X,         # 相对于原图
    模板左上Y,
    模板右下X,
    模板右下Y,

    查找区域编号,
    查找区域左上X,     # 在截图中搜索的区域
    查找区域左上Y,
    查找区域右下X,
    查找区域右下Y,

    相似度阈值,        # 0-100（百分比）
    算法编号           # 0-5
]
```

---

## 2️⃣ 模板获取方式

### 🔄 三层获取优先级

```python
# 第一层：内存缓存（最快）
templates = {}  # dict[str, np.ndarray]

# 第二层：序列化文件（templates.dat）
template_file = "data/templates.dat"
templates = compress_pickle.loads(file_content, compression="gzip")

# 第三层：PNG文件（开发模式）
template_path = f"template/{scene_id}.{template_id}.png"
template = cv2.imread(template_path)
```

### 📝 关键函数

**1. 加载单个模板** ([xsrpst.py:L5921-5956](file:///D:/auto-xbox/streaming/xsrpst.py#L5921-L5956))

```python
def get_template(scene_id, template_id, templates):
    token = f'{scene_id}.{template_id}'

    # 1. 优先从内存字典
    if token in templates:
        return True, templates[token]

    # 2. 回退到PNG文件
    template_file = f"template/{scene_id}.{template_id}.png"
    if os.path.exists(template_file):
        return True, cv2.imread(template_file)

    return False, None
```

**2. 批量加载所有模板** ([xsrpst.py:L5959-5987](file:///D:/auto-xbox/streaming/xsrpst.py#L5959-L5987))

```python
def get_templates():
    template_file = "data/templates.dat"

    if os.path.exists(template_file):
        # gzip解压 + pickle反序列化
        templates = compress_pickle.loads(file_content, compression="gzip")
        return templates

    return {}
```

---

## 3️⃣ 模板匹配方式

### ⚙️ 匹配算法

| 编号 | OpenCV常量 | 类型 | 阈值判断 |
|------|-----------|------|---------|
| 0 | TM_SQDIFF | 平方差 | 越小越好 |
| 1 | TM_SQDIFF_NORMED | 归一化平方差 | min_val ≤ 阈值 |
| 2 | TM_CCORR | 相关匹配 | 越大越好 |
| **3** | **TM_CCORR_NORMED** | **归一化相关** | **max_val ≥ 阈值** ⭐ |
| 4 | TM_CCOEFF | 相关系数 | 越大越好 |
| 5 | TM_CCOEFF_NORMED | 归一化相关系数 | max_val ≥ 阈值 |

### 🔍 核心匹配流程

**单场景识别** ([xsrpst.py:L6224-6315](file:///D:/auto-xbox/streaming/xsrpst.py#L6224-L6315))

```python
def recognize_scene(capture_mat, scene_id, df_templates, templates):

    # 1. 获取该场景的所有模板配置
    scene_configs = df_templates[df_templates['场景编号'] == scene_id]

    # 2. 遍历每个模板
    for config in scene_configs:
        # 加载模板图片
        _, template = get_template(config['模板编号'], templates)

        # 2. 截取搜索区域（模板在截图中的搜索范围）
        search_region = capture_mat[
            config['查找区域左上Y'] : config['查找区域右下Y'],
            config['查找区域左上X'] : config['查找区域右下X']
        ]

        # 3. 执行模板匹配
        method = config['算法编号']
        result = cv2.matchTemplate(search_region, template, method)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        # 4. 判断是否满足阈值
        threshold = config['相似度'] / 100.0  # 转为0-1

        if method in [0, 1]:  # SQDIFF系列
            matched = max_val <= threshold
        else:                 # 其他算法
            matched = max_val >= threshold

        if not matched:
            return False, 0.0

    # 5. 所有模板都匹配才返回成功
    return True, mean(similarities)
```

**多场景识别** ([xsrpst.py:L6160-6219](file:///D:/auto-xbox/streaming/xsrpst.py#L6160-L6219))

```python
def recognize_scenes(capture_mat, candidate_ids=None):
    df_templates = get_templates_schema()
    templates = get_templates()

    # 获取候选场景列表
    if not candidate_ids:
        candidate_ids = df_templates['场景编号'].unique()

    best_scene = -1
    best_score = 0.0

    # 遍历所有候选场景
    for scene_id in candidate_ids:
        success, score = recognize_scene(capture_mat, scene_id, df_templates, templates)

        if success and score > best_score:
            best_scene = scene_id
            best_score = score

    return best_scene
```

---

## 🎯 关键要点总结

### ✅ 模板存放
- PNG源文件在 `template/` 目录
- 序列化数据在 `data/templates.dat`
- 配置硬编码在 `xsrpst.py` 的 `get_templates_schema()` 函数

### ✅ 模板获取
- 内存缓存 > 序列化文件 > PNG文件
- 使用 `{scene_id}.{template_id}` 作为唯一标识
- 支持懒加载（按需读取）

### ✅ 模板匹配
- 使用 **cv2.matchTemplate()** 核心函数
- 推荐算法：**TM_CCORR_NORMED** (编号3)
- 相似度阈值：**90%**（可调整）
- 多区域匹配：所有区域都匹配成功才认为场景识别成功

### ⚡ 性能优化
- 预加载所有模板到内存
- 限制候选场景数量
- 截取搜索区域而非全图搜索

---

*简洁版完成 - 2026-06-02*
