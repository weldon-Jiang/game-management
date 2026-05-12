# 前端样式统一与深色主题重构计划

## 一、现状分析

### 1.1 当前问题

1. **样式分散**：样式代码分布在单个组件的 `<style scoped>`、`style.css` 和 `App.vue` 中，没有统一管理
2. **主题不一致**：Element Plus 默认白色背景与深色主题冲突，覆盖不完整
3. **顽固白色组件**：表格、分页、对话框等组件仍有白色背景残留
4. **固定列问题**：表格横向滚动时，固定列与其他列叠加显示，体验糟糕

### 1.2 现有结构
```
src/
├── App.vue          # 全局样式重置
├── main.js          # 入口，引入 Element Plus
├── style.css        # 全局样式（部分表格/分页覆盖）
└── views/           # 各页面组件
    └── *.vue        # 各自组件内部样式
```

## 二、重构方案

### 2.1 第一阶段：建立统一的样式架构

#### 目标
- 建立统一的样式管理体系
- 统一使用 CSS 变量管理颜色、间距等

#### 具体步骤
1. **创建样式目录结构**
   ```
   src/
   └── styles/
       ├── index.css        # 主入口
       ├── variables.css    # CSS 变量定义
       ├── reset.css        # 基础重置
       ├── element-plus.css # Element Plus 主题覆盖
       └── components/      # 公共组件样式
   ```

2. **定义 CSS 变量**（variables.css）
   - 颜色系统（主色、背景色、文本色、边框色）
   - 间距系统
   - 圆角系统
   - 字体系统

3. **在 main.js 中引入**
   ```javascript
   import './styles/index.css'
   ```

### 2.2 第二阶段：完整 Element Plus 深色主题覆盖

#### 目标
- 彻底消除所有白色/浅色背景
- 统一样式行为

#### 需要覆盖的组件样式（element-plus.css）

| 组件 | 问题 | 覆盖方案 |
|------|------|---------|
| **Dialog（对话框）** | 白色背景 | 半透明深色背景，带边框 |
| **Message Box** | 同上 | 同上 |
| **Table（表格）** | 表头/行/边框白背景 | 透明 + 深色系半透明 |
| **Table Fixed Columns** | 固定列有白色阴影/背景 | 深色渐变阴影 |
| **Pagination（分页）** | 白色按钮 | 深色按钮 + 渐变激活 |
| **Input/Select** | 白色输入框 | 半透明深色输入框 |
| **Button** | 白色背景 | 保持主题按钮 |
| **Tag** | 白色标签 | 半透明深色标签 |
| **Dropdown** | 白色下拉 | 深色下拉 |
| **Date Picker** | 白色面板 | 深色面板 |
| **Switch** | 白色开关 | 深色开关 |
| **Loading** | 白色加载 | 深色加载 |

### 2.3 第三阶段：表格固定列修复

#### 问题描述
Element Plus 表格横向滚动时，`fixed="right"` 的操作列有白色阴影/背景，叠加在其他列上，视觉效果很差

#### 修复方案
1. **修改固定列阴影**：从白色改为深色渐变色
2. **修改固定列背景**：确保固定列背景与整体一致
3. **增加层叠控制**：确保滚动时固定列正确显示/隐藏

### 2.4 第四阶段：各页面组件样式清理

#### 目标
- 移除组件中重复的样式代码
- 统一使用全局样式类
- 保持 `scoped` 只用于组件特有的样式

#### 需要处理的页面
1. `DashboardView.vue` - 控制台
2. `SubscriptionList.vue` - 订阅管理
3. `MerchantList.vue` - 商户管理
4. `ActivationCodeList.vue` - 激活码管理
5. `UserList.vue` - 用户管理
6. `StreamingAccountList.vue` - 流媒体账号
7. `GameAccountList.vue` - 游戏账号
8. `XboxHostList.vue` - Xbox 主机
9. `AgentList.vue` - Agent 管理
10. `AgentVersionList.vue` - Agent 版本
11. `MerchantGroupList.vue` - VIP分组
12. `RechargeCardManagement.vue` - 充值卡
13. `RegistrationCodeList.vue` - 注册码
14. `TaskList.vue` - 任务列表

#### 清理内容
1. 移除重复的 `:deep(.el-table)` 样式
2. 移除重复的 `:deep(.el-pagination)` 样式
3. 移除重复的 `:deep(.el-dialog)` 样式
4. 统一使用全局类名

## 三、具体实施步骤

### 步骤 1：创建样式架构
- [ ] 创建 `src/styles/` 目录
- [ ] 创建 `variables.css` - 定义所有 CSS 变量
- [ ] 创建 `reset.css` - 基础重置
- [ ] 创建 `element-plus.css` - Element Plus 深色主题完整覆盖
- [ ] 创建 `index.css` - 统一引入

### 步骤 2：修改 main.js
- [ ] 移除对 `./style.css` 的引入
- [ ] 引入新的 `./styles/index.css`

### 步骤 3：修复表格固定列问题
- [ ] 在 `element-plus.css` 中添加完整的表格样式
- [ ] 特别处理固定列的背景和阴影
- [ ] 测试滚动时的视觉效果

### 步骤 4：清理页面组件样式
- [ ] 逐个页面清理重复的 `:deep` 样式
- [ ] 确保页面能正常显示
- [ ] 测试交互效果

### 步骤 5：全面测试
- [ ] 测试所有页面
- [ ] 测试所有组件交互
- [ ] 检查是否有白色残留
- [ ] 检查表格滚动
- [ ] 检查对话框/下拉等弹出层

## 四、设计规范（CSS 变量）

### 颜色系统
```css
--bg-primary: #0a0a0f;
--bg-secondary: rgba(18, 18, 26, 0.95);
--bg-tertiary: rgba(18, 18, 26, 0.8);
--bg-hover: rgba(99, 102, 241, 0.15);
--bg-active: rgba(99, 102, 241, 0.3);

--text-primary: #ffffff;
--text-secondary: #b0b0b0;
--text-muted: #6b7280;

--border-subtle: rgba(255, 255, 255, 0.06);
--border-light: rgba(255, 255, 255, 0.1);

--primary: #6366f1;
--primary-soft: rgba(99, 102, 241, 0.2);
--primary-strong: rgba(99, 102, 241, 0.5);

--success: #22c55e;
--warning: #f59e0b;
--danger: #ef4444;
--info: #3b82f6;
```

### 间距系统
```css
--spacing-xs: 4px;
--spacing-sm: 8px;
--spacing-md: 12px;
--spacing-lg: 16px;
--spacing-xl: 24px;
```

### 圆角系统
```css
--radius-sm: 8px;
--radius-md: 10px;
--radius-lg: 12px;
--radius-xl: 16px;
```

### 阴影
```css
--shadow-soft: 0 4px 24px rgba(0, 0, 0, 0.4);
```

## 五、风险与注意事项

1. **兼容性**：确保覆盖所有 Element Plus 组件
2. **Scoped 样式**：组件特殊样式保留 scoped
3. **过渡动画**：保持或增强现有动画效果
4. **移动端适配**：考虑在小屏上的表现
5. **暗色模式检测**：（可选）支持系统自动检测

## 六、预期结果

完成后，系统将拥有：

✅ 完全统一的深色主题，没有白色/浅色背景残留  
✅ 清晰的样式架构，易于维护  
✅ 修复后的表格滚动效果，固定列不再出现叠加问题  
✅ 一致的组件视觉风格  
✅ 完整的 CSS 变量系统，方便后续调整