# Bend Platform 数据库 ER 图

## Mermaid ER Diagram

```mermaid
erDiagram
    merchant ||--o{ merchant_user : "商户用户"
    merchant ||--o{ streaming_account : "串流账号"
    merchant ||--o{ template : "模板"

    merchant {
        bigint id PK "主键"
        varchar phone UK "手机号"
        varchar password_hash "密码"
        varchar name "商户名称"
        enum status "状态"
        datetime expire_time "过期时间"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    merchant_user {
        bigint id PK "主键"
        bigint merchant_id FK "所属商户"
        varchar username UK "用户名"
        varchar phone UK "手机号"
        varchar password_hash "密码"
        enum role "角色"
        enum status "状态"
        datetime last_login_at "最后登录"
        datetime created_at "创建时间"
    }

    streaming_account ||--o{ game_account : "游戏账号"
    streaming_account ||--o{ xbox_host : "Xbox主机"
    streaming_account ||--o{ agent_instance : "Agent实例"
    streaming_account ||--o{ automation_task : "自动化任务"
    streaming_account ||--o{ streaming_error_log : "错误日志"

    streaming_account {
        bigint id PK "主键"
        bigint merchant_id FK "所属商户"
        varchar name "账号名称"
        varchar email UK "邮箱"
        varchar password_encrypted "加密密码"
        varchar auth_code "认证码"
        enum status "状态:idle/ready/running/paused/error"
        varchar last_error_code "最后错误码"
        text last_error_message "最后错误信息"
        datetime last_error_at "最后错误时间"
        int error_retry_count "错误重试次数"
        datetime last_heartbeat "最后心跳"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    game_account {
        bigint id PK "主键"
        bigint streaming_id FK "串流账号"
        varchar name "游戏名称"
        varchar xbox_gamertag UK "Gamertag"
        varchar xbox_live_email UK "Xbox邮箱"
        varchar xbox_live_password_encrypted "密码"
        bigint locked_xbox_id "当前Xbox"
        tinyint is_primary "主账号"
        tinyint is_active "启用"
        int priority "优先级"
        int daily_match_limit "每日限制"
        int today_match_count "今日次数"
        int total_match_count "总次数"
        datetime last_used_at "最后使用"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    xbox_host {
        bigint id PK "主键"
        varchar xbox_id UK "Xbox标识"
        varchar name "名称"
        varchar ip_address "IP地址"
        bigint bound_streaming_account_id "绑定串流账号"
        varchar bound_gamertag "绑定Gamertag"
        enum power_state "电源状态"
        bigint locked_by_agent_id "持有锁Agent"
        datetime locked_at "锁定时间"
        datetime lock_expires_at "锁过期时间"
        enum status "状态"
        datetime last_seen_at "最后在线"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    agent_instance {
        bigint id PK "主键"
        varchar agent_id UK "Agent标识"
        varchar host "主机地址"
        int port "端口"
        enum status "状态"
        bigint current_streaming_id "当前串流账号"
        bigint current_task_id "当前任务"
        datetime last_heartbeat "最后心跳"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    automation_task {
        bigint id PK "主键"
        bigint agent_id "Agent"
        bigint streaming_id FK "串流账号"
        bigint game_id "游戏账号"
        enum task_type "任务类型"
        enum status "状态"
        datetime started_at "开始时间"
        datetime finished_at "结束时间"
        json result "结果"
        text error_message "错误信息"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    task_statistics {
        bigint id PK "主键"
        bigint streaming_id "串流账号"
        bigint game_id "游戏账号"
        date stat_date "统计日期"
        int total_tasks "总任务"
        int completed_tasks "完成"
        int failed_tasks "失败"
        bigint total_duration_seconds "总时长"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }

    streaming_error_log {
        bigint id PK "主键"
        bigint streaming_account_id FK "串流账号"
        bigint xbox_host_id "Xbox主机"
        varchar error_code "错误码"
        text error_message "错误信息"
        text error_trace "堆栈"
        enum severity "严重程度"
        int retry_count "重试次数"
        datetime resolved_at "解决时间"
        datetime created_at "创建时间"
    }

    template {
        bigint id PK "主键"
        bigint merchant_id FK "所属商户"
        varchar category "分类"
        varchar name "名称"
        varchar version "版本"
        enum content_type "内容类型"
        varchar file_path "文件路径"
        bigint file_size "文件大小"
        varchar checksum "校验和"
        tinyint is_current "当前版本"
        text changelog "更新日志"
        bigint created_by "创建人"
        datetime created_at "创建时间"
        datetime updated_at "更新时间"
    }
```

## 表关系说明

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Bend Platform 数据库 ER 图                          │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│                          merchant (商户)                                     │
│                              │                                               │
│           ┌──────────────────┼──────────────────┐                            │
│           │                  │                  │                            │
│           ▼                  ▼                  ▼                            │
│    merchant_user      streaming_account       template                       │
│    (商户用户)            (串流账号)            (模板)                        │
│           │                  │                                               │
│           │                  ├─── game_account (游戏账号)                     │
│           │                  │                                               │
│           │                  ├─── xbox_host (Xbox主机)                       │
│           │                  │                                               │
│           │                  ├─── agent_instance (Agent)                    │
│           │                  │                                               │
│           │                  ├─── automation_task (自动化任务)                │
│           │                  │                                               │
│           │                  └─── streaming_error_log (错误日志)             │
│           │                                                               │
│           └─── (其他商户相关)                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心表说明

| 表名 | 说明 | 关联表 |
|------|------|--------|
| **merchant** | 商户主表 | 1:N merchant_user, streaming_account, template |
| **streaming_account** | 串流账号（核心） | 1:N game_account, xbox_host, agent_instance, automation_task, streaming_error_log |
| **game_account** | 游戏账号 | 属于某个串流账号 |
| **xbox_host** | Xbox主机 | 绑定到串流账号，含分布式锁字段 |
| **agent_instance** | Agent实例 | 绑定到串流账号 |
| **automation_task** | 自动化任务 | 关联串流账号和游戏账号 |
| **streaming_error_log** | 错误日志 | 关联串流账号和Xbox主机 |
| **template** | 模板表 | 属于商户 |

## 关键字段说明

### streaming_account.status (串流账号状态)
- `idle` - 空闲
- `ready` - 就绪（Token刷新+Xbox锁定成功）
- `running` - 运行中（自动化执行中）
- `paused` - 暂停
- `error` - 异常

### xbox_host.locked_by_agent_id (分布式锁)
- NULL - 未被占用
- 有值 - 被某个Agent锁定

### error.severity (错误严重程度)
- `HIGH` - 需要商户介入
- `MEDIUM` - Agent自动重试
- `LOW` - 自动处理
