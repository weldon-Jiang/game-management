# Agent 自动化模块测试

## 测试概览

本模块包含以下测试：

### 1. 单元测试 (Unit Tests)

- `test_task_context.py` - 任务上下文数据结构测试
- `test_platform_api_client.py` - 平台API客户端测试
- `test_automation_scheduler.py` - 任务调度器测试

### 2. 集成测试 (Integration Tests)

- `test_integration.py` - 自动化任务流程集成测试

### 3. 端到端测试 (E2E Tests)

- `test_e2e.py` - 自动化任务全流程端到端测试

## 运行测试

### 前置条件

```bash
pip install pytest pytest-asyncio
```

### 运行所有测试

```bash
cd bend-agent
pytest
```

### 运行特定测试文件

```bash
pytest src/agent/automation/tests/test_task_context.py
```

### 运行特定测试类

```bash
pytest src/agent/automation/tests/test_task_context.py::TestAgentTaskContext
```

### 运行带有"integration"标记的测试

```bash
pytest -m integration
```

## 测试覆盖

| 模块 | 测试类 | 测试方法数 |
|------|--------|-----------|
| task_context | TestGameAccountInfo | 2 |
| task_context | TestXboxInfo | 2 |
| task_context | TestAgentTaskContext | 8 |
| task_context | TestStepStatus | 2 |
| task_context | TestAutomationResult | 2 |
| task_context | TestStepResults | 4 |
| task_context | TestTaskEnums | 2 |
| platform_api_client | TestPlatformApiClient | 6 |
| platform_api_client | TestProgressReporter | 3 |
| automation_scheduler | TestAutomationScheduler | 7 |
| automation_scheduler | TestTaskContextCreation | 1 |
| integration | TestAutomationFlow | 8 |
| integration | TestGameAccountProgressTracking | 2 |
| e2e | TestEndToEndAutomationFlow | 4 |
| e2e | TestEndToEndTaskControlFlow | 3 |
| e2e | TestEndToEndErrorHandling | 2 |

**总计**: 50+ 测试用例

## 测试报告

```bash
# 生成HTML报告
pytest --html=report.html --self-contained-html

# 生成覆盖率报告
pytest --cov=src/agent/automation --cov-report=html
```
