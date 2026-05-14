# Bend Platform 数据库 ER 图

## Mermaid ER Diagram

```mermaid
erDiagram
    merchant ||--o{ merchant_user : "用户"
    merchant ||--o{ streaming_account : "流媒体账号"
    merchant ||--o{ game_account : "游戏账号"
    merchant ||--o{ xbox_host : "Xbox主机"
    merchant ||--o{ merchant_balance : "点数账户"
    merchant ||--o{ activation_code : "激活码"
    merchant ||--o{ merchant_group : "VIP分组"
    merchant ||--o{ recharge_card : "充值卡"
    merchant ||--o{ automation_usage : "使用记录"
    merchant ||--o{ operation_log : "操作日志"
    merchant ||--o{ device_binding : "设备绑定"
    merchant ||--o{ point_transaction : "点数变动"

    merchant_user ||--o{ operation_log : "操作日志"
    merchant_user ||--o{ point_transaction : "点数变动"

    streaming_account ||--o{ game_account : "游戏账号"
    streaming_account ||--o{ xbox_host : "Xbox主机"
    streaming_account ||--o{ task : "任务"
    streaming_account ||--o{ subscription : "订阅"
    streaming_account ||--o{ automation_usage : "使用记录"
    streaming_account ||--o{ streaming_account_login_record : "登录记录"

    game_account ||--o{ task_game_account_status : "账号完成状态"
    game_account ||--o{ streaming_account_login_record : "登录记录"

    task ||--o{ task_game_account_status : "游戏账号状态"
    task ||--o| agent_instance : "分配给"

    agent_instance ||--o{ task : "执行任务"
    agent_instance ||--o{ activation_code_batch : "激活码批次"

    merchant_group ||--o{ subscription_price : "定价配置"
    merchant_group ||--o{ subscription : "订阅"

    subscription ||--o{ device_binding : "设备绑定"
    subscription ||--o{ activation_code : "激活码"

    recharge_card_batch ||--o{ recharge_card : "充值卡"
    recharge_card ||--o{ recharge_record : "充值记录"
    recharge_card ||--o{ point_transaction : "点数变动"

    point_transaction ||--o{ recharge_record : "充值记录"

    system_metrics ||--o| system_alert : "触发告警"

    merchant {
        varchar id PK "主键ID"
        varchar phone UK "联系电话"
        varchar name "商户名称"
        enum status "active/expired/suspended"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
        tinyint is_system "系统内置"
        int total_amount "累计消费"
        int vip_level "VIP等级"
    }

    merchant_user {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar username UK "用户名"
        varchar phone UK "手机号"
        varchar password_hash "密码哈希"
        varchar role "角色"
        enum status "active/disabled"
        int total_recharged "累计充值"
        datetime last_login_time "最后登录"
        datetime created_time "创建时间"
        tinyint deleted "逻辑删除"
    }

    merchant_balance {
        varchar id PK "主键ID"
        varchar merchant_id UK "商户ID"
        int balance "当前余额"
        int total_recharged "累计充值"
        int total_consumed "累计消费"
        int version "乐观锁版本"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    merchant_group {
        varchar id PK "主键ID"
        varchar name "分组名称"
        int vip_level "VIP等级"
        int amount_threshold "升级阈值"
        decimal window_original_price "流媒体原价"
        decimal window_discount_price "流媒体折后价"
        decimal account_original_price "游戏账号原价"
        decimal account_discount_price "游戏账号折后价"
        decimal host_original_price "Xbox主机原价"
        decimal host_discount_price "Xbox主机折后价"
        decimal full_original_price "全功能原价"
        decimal full_discount_price "全功能折后价"
        decimal points_original_price "点数原价"
        decimal points_discount_price "点数折后价"
        decimal discount_rate "折扣比例"
        decimal unbind_refund_rate "解绑返还比例"
        int max_unbind_per_week "每周解绑上限"
        text features "功能特性"
        decimal host_price "主机单价"
        decimal window_price "窗口单价"
        decimal account_price "账号单价"
        varchar status "状态"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    streaming_account {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar name "账号名称"
        varchar email UK "账号邮箱"
        varchar password_encrypted "加密密码"
        varchar auth_code "认证码"
        enum status "idle/ready/running/paused/error"
        varchar agent_id "当前Agent ID"
        varchar last_error_code "最近错误代码"
        text last_error_message "最近错误信息"
        datetime last_error_time "最近错误时间"
        int error_retry_count "错误重试次数"
        datetime last_heartbeat "最后心跳时间"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
    }

    game_account {
        varchar id PK "主键ID"
        varchar streaming_id FK "流媒体账号ID"
        varchar xbox_game_name UK "Xbox游戏名称"
        varchar xbox_live_email UK "Xbox登录邮箱"
        varchar xbox_live_password_encrypted "加密密码"
        bigint locked_xbox_id "锁定的Xbox ID"
        tinyint is_primary "是否主账号"
        tinyint is_active "是否激活"
        int priority "使用优先级"
        int daily_match_limit "每日比赛限制"
        int today_match_count "今日已完成场次"
        int total_match_count "总比赛场次"
        datetime last_used_time "最后使用时间"
        varchar agent_id "绑定的Agent ID"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        varchar merchant_id FK "商户ID"
        tinyint deleted "逻辑删除"
    }

    xbox_host {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar xbox_id UK "Xbox主机ID"
        varchar name "主机名称"
        varchar ip_address "IP地址"
        varchar bound_streaming_account_id "绑定的流媒体账号ID"
        varchar bound_gamertag "绑定的Gamertag"
        enum power_state "On/Off/Standby"
        varchar locked_by_agent_id "锁定Agent ID"
        datetime locked_time "锁定时间"
        datetime lock_expires_time "锁定过期时间"
        enum status "idle/streaming/error"
        datetime last_seen_time "最后发现时间"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
        varchar mac_address "MAC地址"
    }

    agent_instance {
        varchar id PK "主键ID"
        varchar agent_id UK "Agent唯一标识"
        varchar agent_secret "Agent密钥"
        varchar merchant_id FK "所属商户ID"
        varchar registration_code "注册码"
        varchar host "主机IP"
        int port "监听端口"
        varchar version "版本号"
        varchar status "online/offline/uninstalled"
        varchar current_streaming_id "当前流媒体账号ID"
        varchar current_task_id "当前任务ID"
        int max_concurrent_tasks "最大并发任务数"
        datetime last_heartbeat "最后心跳时间"
        datetime last_online_time "最后上线时间"
        varchar uninstall_reason "卸载原因"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
    }

    task {
        varchar id PK "主键ID"
        varchar name "任务名称"
        varchar description "任务描述"
        varchar type "任务类型"
        varchar target_agent_id "目标Agent ID"
        varchar streaming_account_id "流媒体账号ID"
        varchar game_account_id "游戏账号ID"
        varchar status "pending/running/completed/failed/cancelled"
        int priority "优先级"
        text params "任务参数JSON"
        text result "任务结果JSON"
        varchar error_message "错误信息"
        varchar created_by "创建人"
        datetime assigned_time "分配时间"
        datetime started_time "开始执行时间"
        datetime completed_time "完成时间"
        datetime expire_time "过期时间"
        int retry_count "重试次数"
        int max_retries "最大重试次数"
        int timeout_seconds "超时时间(秒)"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
    }

    task_game_account_status {
        varchar id PK "主键ID"
        varchar task_id FK "任务ID"
        varchar game_account_id FK "游戏账号ID"
        varchar streaming_account_id "流媒体账号ID"
        varchar status "pending/running/completed/failed/skipped"
        int completed_count "已完成场次"
        int failed_count "失败场次"
        int total_matches "总场次"
        datetime last_match_time "最后比赛时间"
        datetime started_time "开始执行时间"
        datetime completed_time "完成时间"
        varchar error_message "错误信息"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    activation_code {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar code UK "激活码"
        varchar subscription_type "订阅类型"
        varchar bound_resource_type "绑定资源类型"
        text bound_resource_ids "绑定资源ID列表"
        text bound_resource_names "绑定资源名称列表"
        int duration_days "有效期天数"
        int original_price "原价(分)"
        int discount_price "实付价格(分)"
        int points_amount "点数金额"
        datetime start_time "开始时间"
        datetime end_time "结束时间"
        varchar status "unused/used"
        varchar used_by "使用者"
        datetime used_time "使用时间"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    activation_code_batch {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar batch_name "批次名称"
        int total_count "生成总数"
        int used_count "已使用数量"
        int remaining_count "剩余数量"
        int points "充值点数"
        varchar status "状态"
        datetime expire_time "过期时间"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    subscription {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar user_id FK "用户ID"
        varchar activation_code_id FK "激活码ID"
        varchar subscription_type "points/window_account/account/host/full"
        varchar bound_resource_type "绑定资源类型"
        text bound_resource_ids "绑定资源ID列表"
        text bound_resource_names "绑定资源名称列表"
        datetime start_time "开始时间"
        datetime end_time "过期时间"
        int original_price "原价(分)"
        int discount_price "实付价格(分)"
        varchar status "active/expired/cancelled"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    subscription_price {
        varchar id PK "主键ID"
        varchar group_id FK "VIP分组ID"
        varchar type "订阅类型"
        int price "价格(点数)"
        int duration_days "时长(天)"
        varchar status "状态"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    recharge_card {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar card_type "卡类型"
        varchar batch_id FK "批次ID"
        varchar card_no UK "卡号"
        varchar card_pwd "卡密"
        int denomination "面额(点数)"
        int bonus_points "赠送点数"
        int points_to_grant "发放点数"
        decimal price "售价"
        varchar status "unused/sold/used/expired"
        varchar sold_to_merchant_id "售出商户ID"
        varchar sold_by_user_id "售出人ID"
        datetime sold_time "售出时间"
        varchar used_by_merchant_id "使用商户ID"
        varchar used_by_user_id "使用用户ID"
        datetime used_time "使用时间"
        datetime expire_time "过期时间"
        varchar used_recharge_record_id "充值记录ID"
        varchar remark "备注"
        datetime created_time "创建时间"
    }

    recharge_card_batch {
        varchar id PK "主键ID"
        varchar name "批次名称"
        varchar card_type "卡类型"
        varchar target_merchant_id "目标商户ID"
        int total_count "生成总数"
        int denomination "面额(点数)"
        int bonus_points "赠送点数"
        int points_to_grant "总发放点数"
        decimal price "售价"
        int valid_days "有效期(天)"
        varchar status "状态"
        int generated_count "已生成数量"
        int sold_count "已售数量"
        int used_count "已使用数量"
        varchar created_by "创建人"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    recharge_record {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar user_id FK "用户ID"
        decimal amount "充值金额"
        int points "充值点数"
        int bonus_points "赠送点数"
        varchar payment_method "支付方式"
        varchar transaction_id "交易流水号"
        varchar status "状态"
        varchar remark "备注"
        datetime created_time "创建时间"
    }

    automation_usage {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar user_id FK "用户ID"
        varchar task_id FK "任务ID"
        varchar streaming_account_id FK "流媒体账号ID"
        varchar streaming_account_name "流媒体账号名称"
        int game_accounts_count "游戏账号数量"
        int hosts_count "主机数量"
        varchar resource_type "资源类型"
        varchar resource_id "资源ID"
        varchar resource_name "资源名称"
        varchar charge_mode "扣点模式"
        int points_deducted "扣减的点数"
        varchar subscription_id "关联订阅ID"
        datetime usage_time "使用时间"
        varchar remark "备注"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    operation_log {
        varchar id PK "主键ID"
        varchar user_id FK "操作用户ID"
        varchar merchant_id FK "商户ID"
        varchar action "操作动作"
        varchar target_type "操作对象类型"
        varchar target_id "操作对象ID"
        text before_value "修改前值"
        text after_value "修改后值"
        varchar ip_address "IP地址"
        varchar user_agent "User-Agent"
        varchar description "操作描述"
        datetime created_time "创建时间"
    }

    device_binding {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar user_id FK "用户ID"
        varchar type "设备类型"
        varchar device_id "设备ID"
        varchar device_name "设备名称"
        varchar device_model "设备型号"
        varchar bound_subscription_id "绑定的订阅ID"
        datetime bound_time "绑定时间"
        datetime unbound_time "解绑时间"
        tinyint is_active "是否激活"
        int unbind_count "累计解绑次数"
        datetime last_unbind_time "最后解绑时间"
        varchar last_bind_subscription_id "最后绑定的订阅ID"
        varchar remark "备注"
        datetime created_time "创建时间"
        tinyint deleted "逻辑删除"
    }

    point_transaction {
        varchar id PK "主键ID"
        varchar merchant_id FK "商户ID"
        varchar user_id FK "用户ID"
        varchar type "recharge/consume/refund"
        int points "变动点数"
        int balance_before "变动前余额"
        int balance_after "变动后余额"
        varchar ref_subscription_id "关联订阅ID"
        varchar ref_device_binding_id "关联设备绑定ID"
        varchar ref_recharge_record_id "关联充值记录ID"
        varchar ref_recharge_card_id "关联充值卡ID"
        varchar description "描述"
        datetime created_time "创建时间"
    }

    streaming_account_login_record {
        varchar id PK "主键ID"
        varchar streaming_account_id FK "流媒体账号ID"
        varchar xbox_host_id FK "Xbox主机ID"
        varchar logged_gamertag "登录的Gamertag"
        datetime logged_time "登录时间"
        datetime last_used_time "最后使用时间"
        int use_count "使用次数"
        datetime created_time "创建时间"
    }

    agent_version {
        varchar id PK "主键ID"
        varchar version UK "版本号"
        varchar download_url "下载URL"
        varchar md5_checksum "MD5校验码"
        text changelog "更新日志"
        tinyint mandatory "强制更新"
        tinyint force_restart "需要重启"
        varchar min_compatible_version "最低兼容版本"
        tinyint status "状态"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
        tinyint deleted "逻辑删除"
    }

    system_metrics {
        varchar id PK "主键ID"
        varchar metric_type "指标类型"
        varchar metric_name "指标名称"
        double value "指标值"
        varchar unit "单位"
        varchar host_name "服务器主机名"
        varchar description "指标描述"
        datetime recorded_time "记录时间"
    }

    system_alert {
        varchar id PK "主键ID"
        varchar alert_code "告警编码"
        varchar alert_name "告警名称"
        varchar severity "CRITICAL/HIGH/MEDIUM/LOW"
        varchar alert_type "告警类型"
        text message "告警消息"
        json details "告警详情"
        varchar merchant_id "关联商户ID"
        varchar agent_id "关联Agent ID"
        varchar task_id "关联任务ID"
        varchar status "TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED"
        datetime triggered_time "触发时间"
        datetime acknowledged_time "确认时间"
        varchar acknowledged_by "确认人ID"
        datetime resolved_time "解决时间"
        varchar resolved_by "解决人ID"
        text resolution_note "解决备注"
        text remark "备注"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }

    template {
        varchar id PK "主键ID"
        bigint merchant_id FK "商户ID"
        varchar category "分类"
        varchar name "模板名称"
        varchar version "版本"
        enum content_type "image/json/script"
        varchar file_path "文件路径"
        bigint file_size "文件大小"
        varchar checksum "校验码"
        tinyint is_current "是否当前版本"
        text changelog "更新日志"
        bigint created_by "创建人"
        datetime created_time "创建时间"
        datetime updated_time "更新时间"
    }
```

## 表关系说明

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Bend Platform 数据库 ER 图                            │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  ┌────────────────── merchant (商户) ──────────────────────────────────┐    │
│  │                                                                      │    │
│  │   ├── merchant_balance (点数账户)                                    │    │
│  │   ├── merchant_group (VIP分组)                                       │    │
│  │   ├── merchant_user (用户) ────────────────────────────────────┐    │    │
│  │   │                                                               │    │    │
│  │   │   ├── point_transaction (点数变动)                            │    │    │
│  │   │   └── operation_log (操作日志)                                │    │    │
│  │   │                                                               │    │    │
│  │   └── streaming_account (流媒体账号) ◄── 核心表                    │    │    │
│  │                           │                                        │    │    │
│  │        ┌──────────────────┼──────────────────┐                     │    │    │
│  │        │                  │                  │                      │    │    │
│  │        ▼                  ▼                  ▼                      │    │    │
│  │   game_account      xbox_host         subscription                 │    │    │
│  │   (游戏账号)         (Xbox主机)         (订阅)                       │    │    │
│  │        │                  │                  │                      │    │    │
│  │        │                  │                  ▼                      │    │    │
│  │        ▼                  ▼         device_binding                 │    │    │
│  │   task_game_account   streaming_      (设备绑定)                     │    │    │
│  │   _status            account_                                     │    │    │
│  │   (账号完成状态)      login_record                                 │    │    │
│  │                       (登录记录)                                    │    │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  其他核心表：                                                               │
│  ├── agent_instance (Agent实例) ──── task (任务)                            │
│  ├── activation_code_batch ──── activation_code (激活码)                      │
│  ├── recharge_card_batch ──── recharge_card (充值卡) ──── recharge_record     │
│  ├── system_metrics ──── system_alert (监控告警)                             │
│  └── template (模板)                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心表说明

| 表名 | 说明 | 关联表 |
|------|------|--------|
| **merchant** | 商户主表 | 1:N 所有商户相关表 |
| **streaming_account** | 流媒体账号（核心） | 1:N game_account, xbox_host, task, subscription |
| **game_account** | 游戏账号 | 属于流媒体账号，含今日完成场次 |
| **xbox_host** | Xbox主机 | 绑定到流媒体账号，含分布式锁字段 |
| **agent_instance** | Agent实例 | 接收任务，含最大并发任务数 |
| **task** | 自动化任务 | 关联流媒体账号和Agent |
| **task_game_account_status** | 任务游戏账号完成状态 | 跟踪每个游戏账号的完成情况 |
| **subscription** | 订阅记录 | 关联商户和激活码 |
| **merchant_group** | VIP分组 | 定义各VIP等级的价格 |

## 关键字段说明

### streaming_account.status (流媒体账号状态)
- `idle` - 空闲
- `ready` - 就绪（Token刷新+Xbox锁定成功）
- `running` - 运行中（自动化执行中）
- `paused` - 暂停
- `error` - 异常

### game_account (游戏账号状态)
- `today_match_count` - 今日已完成场次
- `daily_match_limit` - 每日限制场次
- `last_used_time` - 最后使用时间

### task.status (任务状态)
- `pending` - 待执行
- `running` - 执行中
- `completed` - 已完成
- `failed` - 失败
- `cancelled` - 已取消

### task_game_account_status.status (任务游戏账号状态)
- `pending` - 待执行
- `running` - 执行中
- `completed` - 已完成
- `failed` - 失败
- `skipped` - 跳过（超时取消时）

### xbox_host.power_state (Xbox电源状态)
- `On` - 开机
- `Off` - 关机
- `Standby` - 待机
