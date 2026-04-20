package com.bend.platform.exception;

/**
 * 业务异常码接口
 * 定义所有业务异常的编码
 *
 * 编码规则：
 * - 10xxx: 系统/通用异常
 * - 11xxx: 认证/授权异常
 * - 12xxx: 商户相关异常
 * - 13xxx: 商户用户相关异常
 * - 14xxx: 流媒体账号相关异常
 * - 15xxx: Xbox主机相关异常
 * - 16xxx: VIP配置相关异常
 * - 17xxx: 点卡/激活码相关异常
 * - 18xxx: 游戏账号相关异常
 * - 19xxx: 自动化任务相关异常
 */
public interface ResultCode {

    int getCode();

    String getMessage();

    enum System implements ResultCode {
        UNKNOWN_ERROR(10001, "未知错误"),
        PARAM_INVALID(10002, "参数无效"),
        DATA_NOT_FOUND(10003, "数据不存在"),
        DATA_DUPLICATE(10004, "数据重复"),
        OPERATION_FAILED(10005, "操作失败"),
        SERVICE_UNAVAILABLE(10006, "服务不可用"),
        DATABASE_ERROR(10007, "数据库错误"),
        BAD_REQUEST(10400, "请求参数错误"),
        NOT_FOUND(10404, "数据不存在"),
        UNAUTHORIZED(10401, "未授权"),
        FORBIDDEN(10403, "禁止访问");

        private final int code;
        private final String message;

        System(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum Auth implements ResultCode {
        TOKEN_INVALID(11001, "Token无效"),
        TOKEN_EXPIRED(11002, "Token已过期"),
        TOKEN_MISSING(11003, "Token缺失"),
        USERNAME_PASSWORD_ERROR(11004, "用户名或密码错误"),
        ACCOUNT_DISABLED(11005, "账号已被禁用"),
        PERMISSION_DENIED(11006, "权限不足");

        private final int code;
        private final String message;

        Auth(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum Merchant implements ResultCode {
        NOT_FOUND(12001, "商户不存在"),
        NAME_DUPLICATE(12002, "商户名称已存在"),
        PHONE_DUPLICATE(12003, "手机号已被使用"),
        STATUS_INVALID(12004, "商户状态无效"),
        EXPIRED(12005, "商户已过期"),
        CREATE_FAILED(12006, "创建商户失败"),
        UPDATE_FAILED(12007, "更新商户失败"),
        DELETE_FAILED(12008, "删除商户失败");

        private final int code;
        private final String message;

        Merchant(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum MerchantUser implements ResultCode {
        NOT_FOUND(13001, "用户不存在"),
        USERNAME_DUPLICATE(13002, "用户名已存在"),
        PHONE_DUPLICATE(13003, "手机号已被使用"),
        PASSWORD_ERROR(13004, "密码错误"),
        ROLE_INVALID(13005, "角色无效"),
        STATUS_DISABLED(13006, "账号已被禁用"),
        REGISTER_FAILED(13007, "注册失败"),
        UPDATE_FAILED(13008, "更新用户失败"),
        DELETE_FAILED(13009, "删除用户失败"),
        LAST_USER_CANNOT_DELETE(13010, "不能删除最后一个用户");

        private final int code;
        private final String message;

        MerchantUser(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum StreamingAccount implements ResultCode {
        NOT_FOUND(14001, "流媒体账号不存在"),
        EMAIL_DUPLICATE(14002, "邮箱已被使用"),
        STATUS_INVALID(14003, "账号状态无效"),
        ALREADY_BOUND(14004, "账号已被绑定"),
        CREATE_FAILED(14005, "创建账号失败"),
        UPDATE_FAILED(14006, "更新账号失败"),
        DELETE_FAILED(14007, "删除账号失败"),
        BIND_FAILED(14008, "绑定失败"),
        UNBIND_FAILED(14009, "解绑失败");

        private final int code;
        private final String message;

        StreamingAccount(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum XboxHost implements ResultCode {
        NOT_FOUND(15001, "Xbox主机不存在"),
        XBOX_ID_DUPLICATE(15002, "Xbox ID已存在"),
        ALREADY_BOUND(15003, "主机已被绑定"),
        POWER_STATE_INVALID(15004, "电源状态无效"),
        CREATE_FAILED(15005, "创建主机失败"),
        UPDATE_FAILED(15006, "更新主机失败"),
        DELETE_FAILED(15007, "删除主机失败"),
        BIND_FAILED(15008, "绑定失败"),
        UNBIND_FAILED(15009, "解绑失败"),
        LOCK_FAILED(15010, "锁定失败"),
        UNLOCK_FAILED(15011, "解锁失败");

        private final int code;
        private final String message;

        XboxHost(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum VipConfig implements ResultCode {
        NOT_FOUND(16001, "VIP配置不存在"),
        NAME_DUPLICATE(16002, "VIP套餐名已存在"),
        CREATE_FAILED(16003, "创建配置失败"),
        UPDATE_FAILED(16004, "更新配置失败"),
        DELETE_FAILED(16005, "删除配置失败"),
        CANNOT_DELETE_DEFAULT(16006, "不能删除默认配置");

        private final int code;
        private final String message;

        VipConfig(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum ActivationCode implements ResultCode {
        NOT_FOUND(17001, "激活码不存在"),
        ALREADY_USED(17002, "激活码已被使用"),
        EXPIRED(17003, "激活码已过期"),
        INVALID(17004, "激活码无效"),
        GENERATE_FAILED(17005, "生成激活码失败"),
        ACTIVATE_FAILED(17006, "激活失败"),
        BATCH_NOT_FOUND(17007, "批次不存在");

        private final int code;
        private final String message;

        ActivationCode(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum Template implements ResultCode {
        NOT_FOUND(17501, "模板不存在"),
        FILE_SAVE_FAILED(17502, "文件保存失败"),
        DELETE_FAILED(17503, "删除失败");

        private final int code;
        private final String message;

        Template(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum GameAccount implements ResultCode {
        NOT_FOUND(18001, "游戏账号不存在"),
        GAMERTAG_DUPLICATE(18002, "Gamertag已存在"),
        CREATE_FAILED(18003, "创建游戏账号失败"),
        UPDATE_FAILED(18004, "更新游戏账号失败"),
        DELETE_FAILED(18005, "删除游戏账号失败"),
        LOCK_FAILED(18006, "锁定失败"),
        UNLOCK_FAILED(18007, "解锁失败"),
        ALREADY_LOCKED(18008, "已被其他主机锁定");

        private final int code;
        private final String message;

        GameAccount(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum AgentInstance implements ResultCode {
        NOT_FOUND(19001, "Agent实例不存在"),
        AGENT_ID_DUPLICATE(19002, "Agent ID已存在"),
        CREATE_FAILED(19003, "创建Agent实例失败"),
        UPDATE_FAILED(19004, "更新Agent实例失败"),
        DELETE_FAILED(19005, "删除Agent实例失败"),
        STATUS_UPDATE_FAILED(19006, "更新状态失败"),
        HEARTBEAT_UPDATE_FAILED(19007, "更新心跳失败"),
        BIND_STREAMING_FAILED(19008, "绑定流媒体账号失败"),
        UNBIND_STREAMING_FAILED(19009, "解绑流媒体账号失败"),
        BIND_TASK_FAILED(19010, "绑定任务失败"),
        UNBIND_TASK_FAILED(19011, "解绑任务失败");

        private final int code;
        private final String message;

        AgentInstance(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum AgentVersion implements ResultCode {
        NOT_FOUND(19501, "Agent版本不存在"),
        VERSION_EXISTS(19502, "版本号已存在"),
        PUBLISH_FAILED(19503, "发布失败"),
        DELETE_FAILED(19504, "删除失败");

        private final int code;
        private final String message;

        AgentVersion(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum RegistrationCode implements ResultCode {
        NOT_FOUND(20001, "注册码不存在"),
        ALREADY_USED(20002, "注册码已被使用"),
        EXPIRED(20003, "注册码已过期"),
        INVALID(20004, "注册码无效"),
        GENERATE_FAILED(20005, "生成注册码失败"),
        MERCHANT_NOT_MATCH(20006, "注册码与商户不匹配");

        private final int code;
        private final String message;

        RegistrationCode(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }

    enum Task implements ResultCode {
        NOT_FOUND(19001, "任务不存在"),
        INVALID_STATUS(19002, "任务状态无效"),
        NOT_PENDING(19003, "任务不在待执行状态"),
        NOT_RUNNING(19004, "任务不在运行中状态"),
        ALREADY_COMPLETED(19005, "任务已完成的");

        private final int code;
        private final String message;

        Task(int code, String message) {
            this.code = code;
            this.message = message;
        }

        @Override
        public int getCode() {
            return code;
        }

        @Override
        public String getMessage() {
            return message;
        }
    }
}