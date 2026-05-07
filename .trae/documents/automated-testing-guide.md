# 自动化测试执行指南

## 概述

本文档定义了在完成用户需求开发后，如何自动执行单元测试、集成测试和端到端测试的流程。

## 项目测试结构

### 前端 (bend-platform-web)

```
bend-platform-web/
├── src/tests/
│   ├── unit/              # 单元测试
│   │   ├── AgentTaskDialog.test.js
│   │   └── constants.test.js
│   ├── integration/       # 集成测试
│   │   └── api.test.js
│   └── mocks/            # Mock 数据
└── e2e/                 # E2E 测试
    ├── agent.spec.js
    ├── login.spec.js
    ├── navigation.spec.js
    └── task.spec.js
```

### 后端 (bend-platform)

```
bend-platform/
└── src/test/
    └── java/com/bend/platform/
        ├── controller/
        │   └── TaskControllerTest.java
        └── service/
            ├── AgentInstanceServiceTest.java
            ├── AlertServiceTest.java
            └── TaskServiceTest.java
```

## 测试类型

### 1. 单元测试 (Unit Tests)

**适用场景**：
- 新增/修改组件
- 新增/修改工具函数
- 新增/修改 Store 逻辑

**前端执行命令**：
```bash
cd bend-platform-web
npm run test
npm run test:coverage    # 带覆盖率报告
npm run test:watch      # 监听模式
```

**后端执行命令**：
```bash
cd bend-platform
mvn test
```

### 2. 集成测试 (Integration Tests)

**适用场景**：
- 修改 API 调用逻辑
- 修改数据转换
- 新增 API 接口

**前端执行命令**：
```bash
cd bend-platform-web
npm run test
```

### 3. 端到端测试 (E2E Tests)

**适用场景**：
- 修改完整用户流程
- 新增功能模块
- 重要的 UI 变更

**前端执行命令**：
```bash
cd bend-platform-web
npm run test:e2e
npm run test:e2e:ui  # UI 模式
```

## 自动化执行流程

### 修改代码后的测试执行步骤

```
1. 判断修改类型
   ├─ 纯 UI 组件修改 → 执行单元测试
   ├─ API/数据修改 → 执行集成测试
   └─ 流程/功能修改 → 执行全量测试

2. 运行对应类型的测试

3. 检查测试结果
   ├─ ✅ 全部通过 → 完成
   └─ ❌ 有失败 → 修复后重跑
```

### 前端测试覆盖率标准

- 单元测试覆盖率：≥ 60%
- 关键逻辑覆盖率：≥ 80%
- 工具函数覆盖率：≥ 90%

## 快速测试执行命令

### 一站式测试命令

```bash
# 前端完整测试
cd bend-platform-web
npm run lint:check    # 代码检查
npm run test         # 单元 + 集成测试
npm run test:e2e     # E2E 测试

# 后端完整测试
cd bend-platform
mvn clean test
```

## 测试失败处理流程

1. **失败即停**：发现测试失败立即停止当前任务
2. **诊断原因**：分析错误信息，定位问题
3. **修复代码**：修改代码以解决问题
4. **重跑测试**：重新运行相关测试
5. **完整验证**：修复后运行完整测试套件

## 测试报告生成

### 前端覆盖率报告

```bash
cd bend-platform-web
npm run test:coverage
# 打开 coverage/index.html 查看报告
```

### 后端测试报告

```bash
cd bend-platform
mvn clean test site
# 查看 target/site 下的报告
```

## 测试最佳实践

### 新增/修改代码时

1. **先写测试**（可选但推荐）
2. **修改代码**
3. **运行测试**
4. **通过测试**
5. **提交代码**

### 测试命名约定

```
describe('模块名 - 功能点', () => {
  it('应该做到什么', () => {
    // 测试内容
  })
})
```

### 快速测试检查清单

- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] E2E 测试通过（功能重大修改时）
- [ ] 代码没有 lint 错误
- [ ] 浏览器中手动验证核心功能
