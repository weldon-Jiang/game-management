# 动态模板注册系统 - 完整方案

## 一、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         平台                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ game_account_template (MySQL)                       │   │
│  │ - account_id, scene_id, template_id                 │   │
│  │ - template_data (BLOB)                              │   │
│  │ - region_json                                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                    │ 下发任务 + 模板
         ┌──────────┴──────────┐
         ▼                     ▼
      Agent1                Agent2
   (内存使用，不落盘)      (内存使用，不落盘)
```

## 二、数据库设计

### 2.1 表结构

```sql
CREATE TABLE `game_account_template` (
    `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
    `tenant_id` BIGINT NOT NULL COMMENT '商户ID',
    `account_id` BIGINT NOT NULL COMMENT '游戏账号ID',
    `scene_id` INT NOT NULL COMMENT '场景编号',
    `template_id` INT NOT NULL COMMENT '模板编号',
    `template_data` VARCHAR(65535) NOT NULL COMMENT '模板图片Base64编码',
    `region_json` JSON NOT NULL COMMENT '裁剪区域配置JSON',
    `version` INT DEFAULT 1 COMMENT '模板版本',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `uk_account_scene_template` (`account_id`, `scene_id`, `template_id`),
    KEY `idx_tenant_id` (`tenant_id`),
    KEY `idx_account_id` (`account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 2.2 平台侧限制

| 限制项 | 值 |
|-------|-----|
| 单模板原始大小 | ≤ 48 KB |
| 单模板 Base64 后 | ≤ 64 KB |
| 编码方式 | Base64 |

### 2.2 region\_json 格式

```json
{
    "template_left": 0,
    "template_top": 0,
    "template_right": 100,
    "template_bottom": 50,
    "search_left": 0,
    "search_top": 0,
    "search_right": 960,
    "search_bottom": 540,
    "likeness": 90,
    "algorithm": 3
}
```

### 2.3 Java 实体类

```java
@Data
@TableName("game_account_template")
public class GameAccountTemplate {

    private Long id;
    private Long accountId;
    private Integer sceneId;
    private Integer templateId;
    private byte[] templateData;  // MEDIUMBLOB
    private String regionJson;     // JSON -> String映射
    private Integer version;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
```

### 2.4 MyBatis-Plus JSON 处理

```java
@Bean
public MybatisPlusInterceptor mybatisPlusInterceptor() {
    MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
    // JSON字段处理器
    interceptor.addInnerInterceptor(new JacksonTypeInnerInterceptor());
    return interceptor;
}
```

## 三、Agent端设计

### 3.1 任务消息格式

```json
{
    "type": "task",
    "task_id": "task_123",
    "account_email": "player@example.com",
    "account_id": "acc_12345",
    "game_action_type": "squad_battle",
    "templates": [
        {
            "scene_id": 50,
            "template_id": 1,
            "template_data": "<base64>",
            "region_json": "{\"template_left\":0,...}"
        }
    ]
}
```

### 3.2 Agent处理逻辑

```python
class StreamingSceneDetector:
    def __init__(self, template_dir: str):
        self.template_dir = template_dir
        self._memory_templates = {}  # 内存中的模板

    def load_templates_from_message(self, templates: List[dict]):
        """
        从消息加载模板到内存

        参数：
        - templates: [{"scene_id": 50, "template_id": 1, "template_data": "<base64>", "region_json": "..."}]
        """
        self._memory_templates.clear()

        for tmpl in templates:
            scene_id = tmpl['scene_id']
            template_id = tmpl['template_id']

            # 解码图片
            image_data = base64.b64decode(tmpl['template_data'])
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # 解析区域配置
            region = json.loads(tmpl['region_json'])

            # 存入内存
            key = f"{scene_id}.{template_id}"
            self._memory_templates[key] = {
                'image': img,
                'region': region
            }

    def get_template(self, scene_id: int, template_id: int):
        """从内存获取模板"""
        key = f"{scene_id}.{template_id}"
        return self._memory_templates.get(key)

    def detect_scene(self, frame, scene_id: int):
        """使用内存模板进行场景检测"""
        # 遍历该scene_id的所有模板
        matches = []
        for key, tmpl in self._memory_templates.items():
            if key.startswith(f"{scene_id}."):
                # 使用tmpl['image']和tmpl['region']进行匹配
                match = self._match_template(frame, tmpl)
                matches.append(match)
        return best_match(matches)
```

### 3.3 任务执行入口

```python
async def handle_task(params):
    account_email = params['account_email']
    templates = params.get('templates', [])

    if templates:
        # 1. 加载模板到内存
        scene_detector.load_templates_from_message(templates)

    # 2. 执行自动化任务
    await execute_automation(params)
```

## 四、平台侧功能

### 4.1 模板管理API

| 接口                                               | 方法     | 说明        |
| ------------------------------------------------ | ------ | --------- |
| `/api/game-account-template/upload`              | POST   | 上传模板      |
| `/api/game-account-template/list?accountId={id}` | GET    | 获取账号的所有模板 |
| `/api/game-account-template/delete/{id}`         | DELETE | 删除模板      |
| `/api/game-account-template/get-by-scene`        | GET    | 按场景查询模板   |

### 4.2 任务下发集成

```java
// 任务下发服务
public class TaskDispatchService {

    @Autowired
    private GameAccountTemplateMapper templateMapper;

    public void dispatchTask(Task task, Agent agent) {
        // 1. 获取该游戏账号的所有模板
        List<GameAccountTemplate> templates =
            templateMapper.selectByAccountId(task.getGameAccountId());

        // 2. 转换为消息格式
        List<Map<String, Object>> templateList = templates.stream()
            .map(t -> {
                Map<String, Object> tmpl = new HashMap<>();
                tmpl.put("scene_id", t.getSceneId());
                tmpl.put("template_id", t.getTemplateId());
                tmpl.put("template_data",
                    Base64.getEncoder().encodeToString(t.getTemplateData()));
                tmpl.put("region_json", t.getRegionJson());
                return tmpl;
            })
            .collect(Collectors.toList());

        // 3. 下发任务消息
        task.setTemplates(templateList);
        websocketClient.sendToAgent(agent.getAgentId(), task);
    }
}
```

### 4.3 模板上传流程

```
┌─────────────────────────────────────────────────────────────┐
│                       模板上传流程                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 用户在Agent端截图                                       │
│           │                                                 │
│           ▼                                                 │
│  2. Agent发送到平台                                         │
│      {                                                      │
│        "type": "upload_template",                          │
│        "account_id": "acc_123",                            │
│        "scene_id": 50,                                     │
│        "template_data": "<base64>"                         │
│      }                                                      │
│           │                                                 │
│           ▼                                                 │
│  3. 平台自动生成序列化配置                                   │
│      {                                                      │
│        "template_left": 0,                                  │
│        "template_top": 0,                                   │
│        "template_right": 100,                               │
│        ...                                                  │
│      }                                                      │
│           │                                                 │
│           ▼                                                 │
│  4. 存入数据库                                              │
│           │                                                 │
│           ▼                                                 │
│  5. 返回结果给Agent                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 五、任务拆解

### 5.1 平台后端 (P0)

| 序号 | 任务                          | 涉及文件                                                 |
| -- | --------------------------- | ---------------------------------------------------- |
| 1  | 创建 `GameAccountTemplate` 实体 | `entity/GameAccountTemplate.java`                    |
| 2  | 创建 Mapper                   | `mapper/GameAccountTemplateMapper.java`              |
| 3  | 创建 Service                  | `service/GameAccountTemplateService.java`            |
| 4  | 创建 Controller               | `controller/GameAccountTemplateController.java`      |
| 5  | 实现模板上传API                   | `GameAccountTemplateService.uploadTemplate()`        |
| 6  | 实现模板查询API                   | `GameAccountTemplateService.getTemplatesByAccount()` |

### 5.2 任务下发集成 (P1)

| 序号 | 任务                         | 涉及文件                                 |
| -- | -------------------------- | ------------------------------------ |
| 7  | 修改任务下发逻辑，支持附带模板            | `TaskDispatchService.dispatchTask()` |
| 8  | WebSocket消息增加 templates 字段 | `websocket/handler/`                 |

### 5.3 Agent端适配 (P2)

| 序号 | 任务                                 | 涉及文件                          |
| -- | ---------------------------------- | ----------------------------- |
| 9  | `StreamingSceneDetector` 支持从消息加载模板 | `streaming_scene_detector.py` |
| 10 | 实现模板上传到平台                          | `api/platform_api_client.py`  |
| 11 | 任务接收时解析 templates                  | `task_executor.py`            |

### 5.4 前端 (P3)

| 序号 | 任务     | 涉及文件                      |
| -- | ------ | ------------------------- |
| 12 | 模板管理页面 | `GameAccountTemplate.vue` |
| 13 | 模板上传组件 | `TemplateUploader.vue`    |

## 六、验证步骤

1. **单元测试**

   * 模板上传后能正确存入数据库

   * 模板查询能返回正确数据

   * Base64编解码正确

2. **集成测试**

   * Agent收到任务后模板能正确加载

   * 场景检测器能使用内存模板进行识别

   * 多Agent并发执行时模板隔离

3. **端到端测试**

   * 用户在Agent端上传模板

   * 平台能看到该模板

   * 任务下发到另一个Agent能使用该模板

## 七、风险与缓解

| 风险           | 缓解措施          |
| ------------ | ------------- |
| 大文件BLOB影响数据库 | 限制单模板大小 < 1MB |
| 网络传输慢        | 模板数据压缩后传输     |
| 内存占用         | 单任务结束后释放模板内存  |
| 数据库单点故障      | 主从备份          |

***

*文档版本: 5.0*
*创建日期: 2026-06-04*
*平台侧中转存储方案*
