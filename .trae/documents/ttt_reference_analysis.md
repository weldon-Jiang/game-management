# 参考代码分析报告

## 一、参考代码架构

### 1.1 模块结构

| 文件 | 功能 |
|------|------|
| `entry.py` | 主入口，Streamlit UI 框架 |
| `accutil.py` | 账号配置读取（CSV） |
| `xsrputil.py` | XSRP 控制器封装，手柄 SDL2 控制 |
| `xsrpst.py` | **核心**：场景模板匹配 + 状态机逻辑 |
| `logutil.py` | 日志工具 |
| `test_xsrp.py` | 主测试脚本，包含登录和游戏自动化 |

### 1.2 核心设计：状态机模式

参考代码采用了**状态机（State Machine）**设计：

```
┌─────────────────────────────────────────────────────────────┐
│                      状态机架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    截图     ┌──────────┐    手柄操作          │
│  │ 当前场景  │ ────────> │ 场景识别  │ ────────>  │ 目标场景 │
│  │  (ID=n)  │   CV2      │          │   执行      │          │
│  └──────────┘            └──────────┘            └──────────┘
│                                                             │
│  场景迁移规则:                                              │
│  - 每个场景有唯一 ID（如 1, 113, 230）                      │
│  - 定义该场景下的手柄操作序列                               │
│  - 定义目标场景 ID 列表                                     │
│  - 循环执行直到到达目标场景                                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 场景定义示例 (`xsrpst.py`)

```python
# 场景 1: 刚串流上的主页界面
schema = [
    1,      # 场景编号
    960,    # 显示宽度
    540,    # 显示高度

    1,      # 模板编号
    401, 50, 558, 63,  # 模板区域坐标

    1,      # 查找区域编号
    399, 48, 600, 65,  # 查找区域坐标
    90,     # 相似度 90%
    3       # 算法 TM_CCORR_NORMED
]
```

### 1.4 状态迁移示例 (`test_xsrp.py`)

```python
# 场景 230: 输入 EA 账号绑定
if a == 230:
    if zh == 0:
        EA()  # 调用 EA 账号输入
        zh = zh + 1

# 场景 235: 输入密码
if a == 235:
    if m == 0:
        m = m + 1
        password()  # 调用密码输入

# 场景 241: 进入游戏首页
if a == 241:
    keystroke_Down()
    keystroke_A()
```

---

## 二、与当前项目对比

| 维度 | 参考代码 | 当前项目 (XStreaming) |
|------|----------|----------------------|
| 登录方式 | Xbox 串流协议 (XSRP) | Web 界面 + JS 注入 |
| UI 框架 | Streamlit | Electron + Next.js |
| 状态管理 | **状态机 + 场景ID** | 顺序步骤 + `fail_on_timeout` |
| 错误处理 | 场景识别失败后继续 | 超时终止 |
| 截图方式 | CV2 实时截图 | 静态模板匹配 |
| 手柄控制 | SDL2 虚拟手柄 | 物理手柄 |
| 游戏自动化 | **场景驱动** | **无** |

---

## 三、参考代码优势分析

### 3.1 状态机设计的优势

1. **鲁棒性高**
   - 即使某个操作失败，状态机可以继续尝试
   - 不会因为单次超时就终止整个流程

2. **可预测性强**
   - 每个场景有明确的 ID
   - 状态转换关系清晰

3. **易于调试**
   - 可以看到当前处于哪个场景
   - 场景迁移过程可追踪

### 3.2 虚拟键盘输入方案

参考代码实现了**虚拟 Xbox 手柄键盘输入**：

```python
# 键盘布局定义
keyboard_layout = {
    'q': (-5, 0), 'w': (-4, 0), 'e': (-3, 0), ...
}

# 移动光标到目标字符位置
def move_to_char(current_position, target_char, keyboard_layout):
    while current_position != target_position:
        if current_position[0] > target_position[0]:
            keystroke_Left()
            ...
    keystroke_A()  # 按下确认
```

---

## 四、优化当前项目的建议

### 4.1 引入状态机模式到登录流程

**当前问题**：
- 依赖固定顺序的步骤
- 超时就终止，不够灵活

**改进方案**：
```python
# 定义登录状态
class LoginState:
    LOGIN_BUTTON = 1
    AUTH_WINDOW = 2
    EMAIL_INPUT = 3
    PASSWORD_INPUT = 4
    HOME_INDICATOR = 5

# 状态转换
LOGIN_FLOW = {
    LoginState.LOGIN_BUTTON: {
        'action': click_login_button,
        'target': [LoginState.AUTH_WINDOW],
        'timeout': 30
    },
    LoginState.AUTH_WINDOW: {
        'action': wait_auth_ready,
        'target': [LoginState.EMAIL_INPUT, LoginState.PASSWORD_INPUT],
        'timeout': 45
    },
    # ...
}
```

### 4.2 增强 UI 检测器的场景识别

**当前**：`ui_detector.py` 只有简单的模板匹配

**改进**：增加场景置信度和多区域检测

```python
class SceneDetector:
    def recognize_scene(self, capture):
        """
        返回识别到的场景 ID 和置信度
        如果置信度低于阈值，尝试多个候选场景
        """
        results = []
        for template in self.templates:
            similarity = self.match_template(capture, template)
            if similarity > 0.8:
                results.append((template.id, similarity))

        return max(results, key=lambda x: x[1]) if results else None
```

### 4.3 增加场景迁移超时和重试

**当前**：单次超时就终止

**改进**：场景迁移时可以循环检测和重试

```python
def wait_for_scene(target_scene_id, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        current = detector.recognize_scene()
        if current == target_scene_id:
            return True
        # 可以执行一些默认操作
        time.sleep(0.5)
    return False
```

### 4.4 虚拟键盘输入（用于 Xbox 登录）

参考代码的 `keyboard_layout` 方案可以借鉴用于 Xbox 登录页面的账号密码输入：

```python
KEYBOARD_LAYOUT = {
    'q': (-5, 0), 'w': (-4, 0), 'e': (-3, 0),
    'a': (-5, -1), 's': (-4, -1), 'd': (-3, -1),
    # ...
}

def input_text_via_gamepad(text):
    for char in text:
        if char.isupper():
            keystroke_LeftThumbStick()  # 切换大小写
            char = char.lower()
        move_to_char(char)
        keystroke_A()
```

---

## 五、总结

### 参考代码的精华

1. **状态机模式** - 这是最值得借鉴的设计
   - 将流程分解为离散的"场景"
   - 每个场景有明确的进入条件和退出条件
   - 失败时不终止，而是尝试恢复或走备用路径

2. **虚拟手柄键盘输入** - 可用于 Xbox 登录页面的字符输入

3. **场景模板多区域检测** - 避免单点匹配失败

### 对当前项目的建议优先级

| 优先级 | 改进项 | 复杂度 | 收益 |
|--------|--------|--------|------|
| **高** | 增强登录流程的错误处理（不等终止，尝试恢复） | 中 | 高 |
| **高** | 增加场景状态定义和状态转换 | 中 | 高 |
| **中** | UI 检测器增加多区域检测和置信度 | 低 | 中 |
| **低** | 虚拟键盘输入（目前 JS 注入已解决） | 高 | 低 |
