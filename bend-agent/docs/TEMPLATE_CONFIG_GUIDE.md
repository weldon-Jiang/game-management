# Streaming场景模板配置指南

## 📋 概述

本指南说明如何在Agent项目中配置和使用Streaming风格的场景模板匹配系统。

参考项目：[D:\auto-xbox\streaming\xsrpst.py](file:///D:/auto-xbox/streaming/xsrpst.py)

---

## 📁 文件结构

### 新增文件

```
bend-agent/
├── configs/
│   └── scene_schemas.py          # 场景模板配置（新增）
├── src/agent/
│   ├── scene/
│   │   └── streaming_scene_detector.py  # Streaming场景检测器（新增）
│   └── vision/
│       └── template_manager.py    # Streaming模板管理器（新增）
└── templates/                     # 模板图片目录（需创建）
    ├── 1.1.png                   # 场景1-模板1
    ├── 2.1.png                   # 场景2-模板1
    ├── 2.2.png                   # 场景2-模板2
    └── ...
```

---

## 🎯 核心概念

### 1. 场景（Scene）

场景是指Xbox UI的特定界面状态，例如：
- 场景1：刚串流上的主页界面
- 场景2：西瓜主页界面
- 场景10：XB账号登录页面

### 2. 模板（Template）

模板是用于识别场景的图片，例如：
- "我的游戏和应用" 图标
- "档案和系统" 文字
- 各种键盘按键图标

### 3. 搜索区域（Search Region）

在截图中的特定区域进行模板匹配，可以：
- 提高匹配准确性
- 减少计算量
- 避免误匹配

---

## 📊 场景配置详解

### 配置格式

每个场景配置包含15个字段：

```python
[
    场景ID,           # 场景唯一标识 (1, 2, 3...)
    场景宽度,        # 通常 960
    场景高度,        # 通常 540

    模板ID,          # 模板唯一标识 (1, 2, 3...)
    模板左上X,        # 模板在模板图片中的位置
    模板左上Y,
    模板右下X,
    模板右下Y,

    搜索区域ID,      # 搜索区域标识
    搜索区域左上X,    # 在截图中的搜索范围
    搜索区域左上Y,
    搜索区域右下X,
    搜索区域右下Y,

    相似度阈值,      # 0-100（百分比）
    算法编号          # 0-5
]
```

### 配置示例

```python
# 场景1：刚串流上的主页界面
[1, 960, 540, 1, 401, 50, 558, 63, 1, 399, 48, 600, 65, 90, 3]
```

**含义**：
- 场景ID：1
- 场景分辨率：960x540
- 模板ID：1（"我的游戏和应用"）
- 模板区域：(401,50)-(558,63)
- 搜索区域：(399,48)-(600,65)
- 相似度阈值：90%
- 算法：TM_CCORR_NORMED（编号3）

---

## 🔧 模板文件命名规则

### 命名格式

```
{场景ID}.{模板ID}.png
```

### 示例

```
templates/
├── 1.1.png    # 场景1的模板1
├── 2.1.png    # 场景2的模板1
├── 2.2.png    # 场景2的模板2
├── 3.1.png    # 场景3的模板1
├── 3.2.png    # 场景3的模板2
├── 3.3.png    # 场景3的模板3
├── 10.1.png   # 场景10的模板1
├── 10.2.png   # 场景10的模板2
└── ...
```

---

## 🛠️ 使用方式

### 1. 基本使用

```python
from agent.scene.streaming_scene_detector import StreamingSceneDetector

# 初始化检测器
detector = StreamingSceneDetector(
    template_dir="templates",
    default_threshold=0.8
)

# 获取场景数量
print(f"场景总数: {detector.get_scene_count()}")
print(f"模板总数: {detector.get_template_count()}")

# 识别场景
result = detector.recognize_scene(frame)

if result.matched:
    print(f"识别到场景: {result.scene_id}")
    print(f"匹配置信度: {result.confidence:.2f}")
else:
    print("未识别到场景")
```

### 2. 识别指定场景

```python
# 只识别场景1
result = detector.recognize_scene(frame, scene_id=1)

if result.matched:
    print(f"场景1匹配成功，置信度: {result.confidence:.2f}")
```

### 3. 批量识别候选场景

```python
# 识别多个候选场景
result = detector.recognize_scenes_batch(frame, candidate_ids=[1, 2, 3])

if result.matched:
    print(f"最佳匹配场景: {result.scene_id}")
```

### 4. 模板管理

```python
from agent.vision.template_manager import StreamingTemplateManager

# 初始化管理器
manager = StreamingTemplateManager(
    template_dir="templates",
    data_dir="data"
)

# 预加载所有模板
count = manager.preload_all_templates()
print(f"预加载了 {count} 个模板")

# 获取单个模板
template = manager.get_template(1, 1)  # 场景1的模板1

# 保存为序列化数据
manager.save_serialized()

# 从序列化数据加载
manager.load_serialized()

# 获取缓存大小
print(f"缓存中模板数: {manager.get_cache_size()}")
```

---

## 📝 场景清单

### UI导航场景（1-9）

| 场景ID | 场景名称 | 模板数量 | 说明 |
|--------|---------|---------|------|
| 1 | 刚串流上的主页界面 | 1 | 检测"我的游戏和应用"图标 |
| 2 | 西瓜主页界面 | 2 | 检测"西瓜图标"和"主页图标" |
| 3 | 档案和系统页面-添加和切换 | 3 | 检测"档案和系统"等文字 |
| 4 | 档案和系统页面-注销 | 1 | 检测"注销"选项 |
| 5 | 你是谁-添加和切换页面 | 3 | 检测"您是谁"等文字 |
| 6 | 添加和切换页面-选择用户 | 2 | 检测"已登录状态" |
| 7 | 您希望做什么-关机重启页面 | 3 | 检测"您希望做什么" |
| 8 | 您希望做什么-关闭主机 | 2 | 检测"关闭主机" |
| 9 | 您希望做什么-重启系统 | 2 | 检测"重新启动主机" |

### 账号登录场景（10-23）

| 场景ID | 场景名称 | 模板数量 | 说明 |
|--------|---------|---------|------|
| 10 | XB账号登录页面 | 3 | 检测"登录"和输入框 |
| 11 | #+= LT键位 | 2 | LT键 |
| 12 | LB键位 | 2 | LB键 |
| 13 | 大写L键位 | 2 | 大写L键 |
| 14 | @键位 | 2 | @符号键 |
| 15 | RT键位 | 2 | RT键 |
| 16 | RB键位 | 2 | RB键 |
| 17 | Y键位 | 2 | Y键 |
| 18 | RB键位 | 2 | RB键 |
| 19 | X键位 | 2 | X键 |
| 20 | 1键位 | 2 | 数字1键 |
| 21 | 2键位 | 2 | 数字2键 |
| 22 | 3键位 | 2 | 数字3键 |
| 23 | 4键位 | 2 | 数字4键 |

---

## ⚙️ 算法说明

### 支持的算法

| 编号 | 算法名称 | 说明 | 阈值判断 |
|------|---------|------|---------|
| 0 | TM_SQDIFF | 平方差匹配 | 越小越好 |
| 1 | TM_SQDIFF_NORMED | 归一化平方差 | min_val ≤ 阈值 |
| 2 | TM_CCORR | 相关匹配 | 越大越好 |
| **3** | **TM_CCORR_NORMED** | **归一化相关（推荐）** | **max_val ≥ 阈值** |
| 4 | TM_CCOEFF | 相关系数 | 越大越好 |
| 5 | TM_CCOEFF_NORMED | 归一化相关系数 | max_val ≥ 阈值 |

### 推荐配置

```
推荐算法：TM_CCORR_NORMED (编号3)
推荐阈值：90%
原因：平衡性能和准确性
```

---

## 📦 模板准备指南

### 1. 截图分辨率

所有模板应为 **960x540** 像素

### 2. 截取模板区域

根据配置中的坐标截取模板：

```python
# 配置中的坐标
template_left = 401
template_top = 50
template_right = 558
template_bottom = 63

# 从截图截取
template = frame[template_top:template_bottom, template_left:template_right]
```

### 3. 保存模板

```python
import cv2

# 保存为PNG
cv2.imwrite(f"templates/1.1.png", template)
```

### 4. 检查清单

- [ ] 模板分辨率为 960x540
- [ ] 模板区域与配置一致
- [ ] 文件命名为 `{场景ID}.{模板ID}.png`
- [ ] 放置在 `templates/` 目录

---

## 🔄 集成到现有代码

### 在步骤三中使用

```python
# step3_streaming_init.py
from agent.scene.streaming_scene_detector import StreamingSceneDetector

async def step3_init_streaming(context, check_cancel, report_progress):
    # 初始化场景检测器
    detector = StreamingSceneDetector(
        template_dir="templates",
        default_threshold=0.8
    )

    # 预加载模板
    detector.preload_all_templates()

    # 保存到上下文供步骤四使用
    context.scene_detector = detector

    return Step3Result(success=True)
```

### 在步骤四中使用

```python
# step4_game_automation.py
async def step4_execute_automation(context, check_cancel, report_progress):
    detector = context.scene_detector

    while True:
        # 获取画面
        frame = await context.frame_capture.capture_frame()

        # 识别场景
        result = detector.recognize_scene(frame)

        if result.matched:
            print(f"当前场景: {result.scene_id}")

            # 根据场景执行操作
            if result.scene_id == 1:
                # 执行主页相关操作
                pass
            elif result.scene_id == 10:
                # 执行登录相关操作
                pass

        await asyncio.sleep(0.5)
```

---

## 📊 性能优化

### 1. 模板预加载

```python
# 启动时预加载所有模板
detector = StreamingSceneDetector(template_dir="templates")
detector.preload_all_templates()  # 预加载
```

### 2. 限制候选场景

```python
# 只识别可能的场景
result = detector.recognize_scenes_batch(frame, candidate_ids=[1, 2, 3])
```

### 3. 缓存策略

```python
# 使用缓存
manager = StreamingTemplateManager(template_dir="templates", use_cache=True)

# 清空缓存
manager.clear_cache()
```

---

## 🐛 常见问题

### 1. 模板文件不存在

```
WARNING: 模板文件不存在: templates/1.1.png
```

**解决**：确保模板文件放置在正确目录

### 2. 匹配失败

```
WARNING: 场景ID不存在: 99
```

**解决**：检查场景ID是否在 SCENE_SCHEMAS 中定义

### 3. 置信度低

**解决**：
- 检查模板图片质量
- 调整相似度阈值
- 扩大搜索区域范围

---

## 📚 参考资料

- [Streaming项目分析报告](../.trae/documents/Streaming场景与模板完整清单.md)
- [Streaming模板匹配核心分析](../.trae/documents/Streaming模板匹配核心要点.md)
- Streaming项目源码：[D:\auto-xbox\streaming\xsrpst.py](file:///D:/auto-xbox/streaming/xsrpst.py)

---

*文档版本：1.0*
*最后更新：2026-06-02*
