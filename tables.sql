create table bend_platform.activation_code
(
    id             varchar(36)                           not null
        primary key,
    merchant_id    varchar(36)                           null,
    batch_id       varchar(36)                           null comment '批次ID',
    code           varchar(50)                           not null comment '激活码',
    vip_type       varchar(50)                           not null comment 'VIP类型',
    vip_config_id  varchar(36)                           null comment '关联VIP配置ID',
    status         varchar(20) default 'unused'          null comment '状态: unused/used/expired',
    used_by        varchar(36)                           null comment '使用者的用户ID',
    used_time      datetime                              null comment '使用时间',
    expire_time    timestamp                             null comment '过期时间',
    generated_time datetime                              null comment '生成时间',
    created_time   datetime    default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time   datetime    default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint code
        unique (code)
);

create table bend_platform.activation_code_batch
(
    id              varchar(36)                           not null
        primary key,
    merchant_id     varchar(36)                           null,
    batch_name      varchar(100)                          not null comment '批次名称',
    total_count     int                                   not null comment '生成总数',
    used_count      int         default 0                 null comment '已使用数',
    remaining_count int         default 0                 null comment '剩余数',
    vip_type        varchar(50)                           not null comment 'VIP类型',
    expire_time     timestamp                             null comment '激活码过期时间',
    status          varchar(20) default 'active'          null comment '状态: active/inactive/completed',
    created_time    datetime    default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time    datetime    default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间'
);

create table bend_platform.agent_instance
(
    id                   varchar(36)                                                  null,
    agent_id             varchar(64)                                                  not null comment 'Agent唯一标识',
    agent_secret         varchar(255)                                                 null comment 'Agent密钥',
    merchant_id          varchar(64)                                                  null comment '所属商户ID',
    registration_code    varchar(64)                                                  null comment '注册码',
    version              varchar(32)                                                  null comment 'Agent版本',
    host                 varchar(255)                                                 not null comment '主机地址',
    port                 int                                                          not null comment '端口',
    status               enum ('online', 'offline', 'busy') default 'offline'         null comment '状态',
    current_streaming_id varchar(36)                                                  null,
    current_task_id      varchar(36)                                                  null,
    last_heartbeat       datetime                                                     null comment '最后心跳时间',
    last_online_time     datetime                                                     null comment '最后上线时间',
    uninstall_reason     varchar(255)                                                 null comment '卸载原因',
    deleted              tinyint(1)                         default 0                 null comment '逻辑删除标记',
    created_time         datetime                           default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time         datetime                           default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint agent_id
        unique (agent_id)
)
    comment 'Agent实例表' charset = utf8mb4;

create index idx_agent_id
    on bend_platform.agent_instance (agent_id);

create index idx_current_streaming_id
    on bend_platform.agent_instance (current_streaming_id);

create index idx_status
    on bend_platform.agent_instance (status);

create table bend_platform.agent_version
(
    id                     varchar(64)                          not null comment '主键ID'
        primary key,
    version                varchar(32)                          not null comment '版本号',
    download_url           varchar(512)                         not null comment '下载URL',
    md5_checksum           varchar(64)                          null comment 'MD5校验码',
    changelog              text                                 null comment '更新日志',
    mandatory              tinyint(1) default 0                 null comment '是否强制更新：0-否，1-是',
    force_restart          tinyint(1) default 0                 null comment '是否需要重启：0-否，1-是',
    min_compatible_version varchar(32)                          null comment '最低兼容版本',
    status                 tinyint(1) default 0                 null comment '状态：0-未发布，1-已发布',
    created_time           datetime   default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time           datetime   default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    deleted                tinyint(1) default 0                 null comment '逻辑删除标记',
    constraint uk_version
        unique (version)
)
    comment 'Agent版本表';

create index idx_deleted
    on bend_platform.agent_version (deleted);

create index idx_status
    on bend_platform.agent_version (status);

create table bend_platform.automation_task
(
    id            varchar(36)                                                                                         null,
    agent_id      bigint                                                                                              null comment '执行的Agent',
    streaming_id  bigint                                                                                              not null comment '串流账号ID',
    game_id       bigint                                                                                              null comment '游戏账号ID',
    task_type     enum ('login', 'stream', 'game_switch', 'custom')                                                   not null comment '任务类型',
    status        enum ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') default 'pending'         null comment '状态',
    started_at    datetime                                                                                            null comment '开始时间',
    finished_at   datetime                                                                                            null comment '结束时间',
    result        json                                                                                                null comment '执行结果',
    error_message text                                                                                                null comment '错误信息',
    created_at    datetime                                                                  default CURRENT_TIMESTAMP null,
    updated_at    datetime                                                                  default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP
)
    comment '自动化任务表' charset = utf8mb4;

create index idx_agent_id
    on bend_platform.automation_task (agent_id);

create index idx_created_at
    on bend_platform.automation_task (created_at);

create index idx_status
    on bend_platform.automation_task (status);

create index idx_streaming_id
    on bend_platform.automation_task (streaming_id);

create table bend_platform.game_account
(
    id                           varchar(36)                          null,
    streaming_id                 varchar(36)                          null,
    name                         varchar(100)                         not null comment '游戏账号名称',
    xbox_gamertag                varchar(50)                          not null comment 'Xbox Gamertag',
    xbox_live_email              varchar(255)                         null comment 'Xbox Live 邮箱',
    xbox_live_password_encrypted varchar(512)                         null comment '密码加密存储',
    locked_xbox_id               bigint                               null comment '当前登录的Xbox主机ID',
    is_primary                   tinyint(1) default 0                 null comment '是否主账号',
    is_active                    tinyint(1) default 1                 null comment '是否启用',
    priority                     int        default 0                 null comment '优先级',
    daily_match_limit            int        default 3                 null comment '每日比赛次数限制',
    today_match_count            int        default 0                 null comment '今日已完成比赛数',
    total_match_count            int        default 0                 null comment '历史总比赛数',
    last_used_time               datetime                             null comment '最后使用时间',
    created_time                 datetime   default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time                 datetime   default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    merchant_id                  varchar(64)                          not null comment '商户ID',
    constraint uk_email
        unique (xbox_live_email),
    constraint uk_gamertag
        unique (xbox_gamertag)
)
    comment '游戏账号表' charset = utf8mb4;

create index idx_locked_xbox_id
    on bend_platform.game_account (locked_xbox_id);

create index idx_streaming_id
    on bend_platform.game_account (streaming_id);

create table bend_platform.merchant
(
    id           varchar(36)                                                       null,
    phone        varchar(20)                                                       not null comment '手机号',
    name         varchar(100)                                                      null comment '商户名称',
    status       enum ('active', 'expired', 'suspended') default 'active'          null comment '状态',
    expire_time  datetime                                                          null comment '账号过期时间',
    created_time datetime                                default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time datetime                                default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint phone
        unique (phone)
)
    comment '商户表' charset = utf8mb4;

create index idx_phone
    on bend_platform.merchant (phone);

create index idx_status
    on bend_platform.merchant (status);

create table bend_platform.merchant_registration_code
(
    id               varchar(36)                  not null comment '主键ID'
        primary key,
    merchant_id      varchar(36)                  not null comment '商户ID',
    code             varchar(50)                  not null comment '注册码',
    status           varchar(20) default 'unused' not null comment '状态: unused-未使用, used-已使用',
    used_by_agent_id varchar(50)                  null comment '使用的Agent ID',
    agent_id         varchar(50)                  null comment '绑定的Agent实例ID',
    created_time     datetime                     not null comment '创建时间',
    expire_time      datetime                     null comment '过期时间',
    used_time        datetime                     null comment '使用时间',
    constraint uk_code
        unique (code)
)
    comment '商户注册码表';

create index idx_merchant_id
    on bend_platform.merchant_registration_code (merchant_id);

create index idx_status
    on bend_platform.merchant_registration_code (status);

create table bend_platform.merchant_user
(
    id              varchar(36)                                           null,
    merchant_id     varchar(36)                                           null,
    username        varchar(50)                                           not null comment '用户名',
    phone           varchar(20)                                           not null comment '手机号',
    password_hash   varchar(255)                                          not null comment '密码哈希',
    role            varchar(30)                 default 'operator'        null,
    status          enum ('active', 'disabled') default 'active'          null comment '状态',
    last_login_time datetime                                              null comment '最后登录时间',
    created_time    datetime                    default CURRENT_TIMESTAMP null comment '创建时间',
    constraint uk_phone
        unique (phone),
    constraint uk_username
        unique (username)
)
    comment '商户用户表' charset = utf8mb4;

create index idx_merchant_id
    on bend_platform.merchant_user (merchant_id);

create table bend_platform.streaming_account
(
    id                 varchar(36)                                                                    null,
    merchant_id        varchar(36)                                                                    null,
    name               varchar(100)                                                                   not null comment '账号名称',
    email              varchar(255)                                                                   not null comment '邮箱',
    password_encrypted varchar(512)                                                                   null comment '加密密码',
    auth_code          varchar(512)                                                                   null comment '认证码',
    status             enum ('idle', 'ready', 'running', 'paused', 'error') default 'idle'            null comment '状态',
    agent_id           varchar(64)                                                                    null comment '当前绑定的Agent ID',
    last_error_code    varchar(20)                                                                    null comment '最后错误码',
    last_error_message text                                                                           null comment '最后错误信息',
    last_error_time    datetime                                                                       null comment '最近错误发生时间',
    error_retry_count  int                                                  default 0                 null comment '错误重试次数',
    last_heartbeat     datetime                                                                       null comment '最后心跳时间',
    created_time       datetime                                             default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time       datetime                                             default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint uk_email
        unique (email)
)
    comment '串流账号表' charset = utf8mb4;

create index idx_agent_id
    on bend_platform.streaming_account (agent_id);

create index idx_merchant_id
    on bend_platform.streaming_account (merchant_id);

create index idx_status
    on bend_platform.streaming_account (status);

create table bend_platform.streaming_account_login_record
(
    id                   varchar(36)   not null
        primary key,
    streaming_account_id varchar(36)   not null comment '流媒体账号ID',
    xbox_host_id         varchar(36)   not null comment 'Xbox主机ID',
    logged_gamertag      varchar(100)  null comment '登录时使用的Gamertag',
    logged_time          datetime      null comment '登录时间',
    last_used_time       datetime      null comment '最后使用时间',
    use_count            int default 0 null comment '使用次数',
    constraint uk_streaming_xbox
        unique (streaming_account_id, xbox_host_id)
)
    comment '流媒体账号Xbox登录记录表' charset = utf8mb4;

create index idx_streaming_account_id
    on bend_platform.streaming_account_login_record (streaming_account_id);

create index idx_xbox_host_id
    on bend_platform.streaming_account_login_record (xbox_host_id);

create table bend_platform.streaming_error_log
(
    id                   varchar(36)                        null,
    streaming_account_id bigint                             not null comment '串流账号ID',
    xbox_host_id         bigint                             null comment 'Xbox主机ID',
    error_code           varchar(20)                        not null comment '错误码',
    error_message        text                               null comment '错误信息',
    error_trace          text                               null comment '错误堆栈',
    severity             enum ('HIGH', 'MEDIUM', 'LOW')     not null comment '严重程度',
    retry_count          int      default 0                 null comment '重试次数',
    resolved_at          datetime                           null comment '解决时间',
    created_at           datetime default CURRENT_TIMESTAMP null
)
    comment '流错误日志表' charset = utf8mb4;

create index idx_account_id
    on bend_platform.streaming_error_log (streaming_account_id);

create index idx_created_at
    on bend_platform.streaming_error_log (created_at);

create index idx_error_code
    on bend_platform.streaming_error_log (error_code);

create table bend_platform.system_alert
(
    id                varchar(36)                           not null comment '涓婚敭锛圲UID锛'
        primary key,
    alert_code        varchar(50)                           not null comment '鍛婅?缂栫爜',
    alert_name        varchar(100)                          null comment '鍛婅?鍚嶇О',
    severity          varchar(20)                           not null comment '鍛婅?绾у埆: CRITICAL/HIGH/MEDIUM/LOW',
    alert_type        varchar(50)                           not null comment '鍛婅?绫诲瀷',
    message           text                                  null comment '鍛婅?娑堟伅',
    details           json                                  null comment '鍛婅?璇︽儏',
    merchant_id       varchar(36)                           null comment '鍏宠仈鍟嗘埛ID',
    agent_id          varchar(36)                           null comment '鍏宠仈Agent ID',
    task_id           varchar(36)                           null comment '鍏宠仈浠诲姟ID',
    status            varchar(20) default 'TRIGGERED'       null comment '鐘舵?: TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED',
    triggered_time    datetime                              null comment '触发时间',
    acknowledged_time datetime                              null comment '确认时间',
    acknowledged_by   varchar(36)                           null comment '纭??浜篒D',
    resolved_time     datetime                              null comment '解决时间',
    resolved_by       varchar(36)                           null comment '瑙ｅ喅浜篒D',
    resolution_note   text                                  null comment '瑙ｅ喅澶囨敞',
    remark            text                                  null comment '澶囨敞',
    created_time      datetime    default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time      datetime    default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间'
)
    comment '绯荤粺鍛婅?琛' charset = utf8mb4;

create index idx_agent_id
    on bend_platform.system_alert (agent_id);

create index idx_alert_type
    on bend_platform.system_alert (alert_type);

create index idx_merchant_id
    on bend_platform.system_alert (merchant_id);

create index idx_severity
    on bend_platform.system_alert (severity);

create index idx_status
    on bend_platform.system_alert (status);

create index idx_triggered_time
    on bend_platform.system_alert (triggered_time);

create table bend_platform.system_metrics
(
    id            varchar(36)                        not null comment '涓婚敭锛圲UID锛'
        primary key,
    metric_type   varchar(50)                        not null comment '鎸囨爣绫诲瀷: jvm/system/business',
    metric_name   varchar(100)                       not null comment '鎸囨爣鍚嶇О',
    value         double                             null comment '鎸囨爣鍊',
    unit          varchar(20)                        null comment '鍗曚綅: %/bytes/涓?绉',
    host_name     varchar(100)                       null comment '鏈嶅姟鍣ㄤ富鏈哄悕',
    description   varchar(255)                       null comment '鎸囨爣鎻忚堪',
    recorded_time datetime default CURRENT_TIMESTAMP null comment '记录时间'
)
    comment '绯荤粺鐩戞帶鎸囨爣琛' charset = utf8mb4;

create index idx_metric_name
    on bend_platform.system_metrics (metric_name);

create index idx_metric_type
    on bend_platform.system_metrics (metric_type);

create index idx_recorded_time
    on bend_platform.system_metrics (recorded_time);

create table bend_platform.task
(
    id                   varchar(64)                           not null comment '主键ID'
        primary key,
    name                 varchar(128)                          not null comment '任务名称',
    description          varchar(512)                          null comment '任务描述',
    type                 varchar(32)                           not null comment '任务类型',
    target_agent_id      varchar(64)                           null comment '目标Agent ID',
    streaming_account_id varchar(64)                           null comment '关联的流媒体账号ID',
    game_account_id      varchar(64)                           null comment '关联的游戏账号ID',
    status               varchar(16) default 'pending'         null comment '状态：pending-待执行,running-执行中,completed-已完成,failed-失败,cancelled-已取消',
    priority             int         default 0                 null comment '优先级',
    params               text                                  null comment '任务参数JSON',
    result               text                                  null comment '任务结果JSON',
    error_message        varchar(512)                          null comment '错误信息',
    created_by           varchar(64)                           null comment '创建人',
    assigned_time        datetime                              null comment '分配时间',
    started_time         datetime                              null comment '开始执行时间',
    completed_time       datetime                              null comment '完成时间',
    expire_time          datetime                              null comment '过期时间',
    retry_count          int         default 0                 null comment '重试次数',
    max_retries          int         default 3                 null comment '最大重试次数',
    created_time         datetime    default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time         datetime    default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    deleted              tinyint(1)  default 0                 null comment '逻辑删除标记'
)
    comment '任务表';

create index idx_created_time
    on bend_platform.task (created_time);

create index idx_deleted
    on bend_platform.task (deleted);

create index idx_game_account
    on bend_platform.task (game_account_id);

create index idx_status
    on bend_platform.task (status);

create index idx_streaming_account
    on bend_platform.task (streaming_account_id);

create index idx_target_agent
    on bend_platform.task (target_agent_id);

create index idx_type
    on bend_platform.task (type);

create table bend_platform.task_statistics
(
    id                     varchar(36)                        null,
    streaming_id           bigint                             not null comment '串流账号ID',
    game_id                bigint                             null comment '游戏账号ID',
    stat_date              date                               not null comment '统计日期',
    total_tasks            int      default 0                 null comment '总任务数',
    completed_tasks        int      default 0                 null comment '完成任务数',
    failed_tasks           int      default 0                 null comment '失败任务数',
    total_duration_seconds bigint   default 0                 null comment '总执行时长(秒)',
    created_at             datetime default CURRENT_TIMESTAMP null,
    updated_at             datetime default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP,
    constraint uk_stream_game_date
        unique (streaming_id, game_id, stat_date)
)
    comment '任务统计表' charset = utf8mb4;

create index idx_stat_date
    on bend_platform.task_statistics (stat_date);

create table bend_platform.template
(
    id           varchar(36)                          null,
    merchant_id  bigint                               not null comment '所属商户',
    category     varchar(100)                         not null comment '模板分类',
    name         varchar(100)                         not null comment '模板名称',
    version      varchar(20)                          not null comment '版本号',
    content_type enum ('image', 'json', 'script')     not null comment '内容类型',
    file_path    varchar(500)                         null comment '文件路径',
    file_size    bigint                               null comment '文件大小',
    checksum     varchar(64)                          null comment '文件校验和',
    is_current   tinyint(1) default 1                 null comment '是否为当前版本',
    changelog    text                                 null comment '更新日志',
    created_by   bigint                               null comment '创建人',
    created_time datetime   default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time datetime   default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint uk_merchant_category_name_version
        unique (merchant_id, category, name, version)
)
    comment '模板表' charset = utf8mb4;

create index idx_category_name
    on bend_platform.template (category, name);

create index idx_is_current
    on bend_platform.template (is_current);

create index idx_merchant_id
    on bend_platform.template (merchant_id);

create table bend_platform.vip_config
(
    id            varchar(36)                           not null
        primary key,
    merchant_id   varchar(36)                           null,
    vip_type      varchar(50)                           not null comment 'VIP类型: monthly/yearly/quarterly',
    vip_name      varchar(100)                          not null comment 'VIP名称',
    price         decimal(10, 2)                        not null comment '价格',
    duration_days int                                   not null comment '时长(天)',
    features      text                                  null comment '功能描述JSON',
    is_default    tinyint(1)  default 0                 null comment '是否默认选中',
    status        varchar(20) default 'active'          null comment '状态: active/inactive',
    sort_order    int         default 0                 null comment '排序',
    created_time  datetime    default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time  datetime    default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间'
);

create table bend_platform.xbox_host
(
    id                         varchar(36)                                                   null,
    merchant_id                varchar(36)                         default '1'               not null comment '所属商户',
    xbox_id                    varchar(64)                                                   not null comment 'Xbox唯一标识',
    name                       varchar(100)                                                  null comment 'Xbox名称',
    ip_address                 varchar(45)                                                   null comment 'IP地址',
    bound_streaming_account_id varchar(36)                                                   null,
    bound_gamertag             varchar(50)                                                   null comment '绑定的Gamertag',
    power_state                enum ('On', 'Off', 'Standby')       default 'Off'             null comment '电源状态',
    locked_by_agent_id         varchar(36)                                                   null,
    locked_time                datetime                                                      null comment '锁定时间',
    lock_expires_time          datetime                                                      null comment '锁定过期时间',
    status                     enum ('idle', 'streaming', 'error') default 'idle'            null comment '状态',
    last_seen_time             datetime                                                      null comment '最后发现时间',
    created_time               datetime                            default CURRENT_TIMESTAMP null comment '创建时间',
    updated_time               datetime                            default CURRENT_TIMESTAMP null on update CURRENT_TIMESTAMP comment '更新时间',
    constraint xbox_id
        unique (xbox_id)
)
    comment 'Xbox主机表' charset = utf8mb4;

create index idx_bound_streaming_id
    on bend_platform.xbox_host (bound_streaming_account_id);

create index idx_merchant_id
    on bend_platform.xbox_host (merchant_id);

create index idx_power_state
    on bend_platform.xbox_host (power_state);

create index idx_status
    on bend_platform.xbox_host (status);

