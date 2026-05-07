# 方案B：直接订阅模式 - 详细设计方案

## 一、业务流程

### 1.1 管理员操作流程
```
管理员创建激活码批次
  ├── 选择类型：points（点数）/ account（游戏账号）/ window（窗口）/ host（主机）
  ├── 设置批次名称
  ├── 设置数量
  └── 根据类型设置参数：
      ├── points: 点数
      ├── account: 目标游戏账号 + 时长(天) + 每天价格
      ├── window: 目标窗口 + 时长(天) + 每天价格
      └── host: 目标主机 + 时长(天) + 每天价格
```

### 1.2 商户操作流程
```
商户输入激活码
  ├── 系统验证激活码
  ├── 根据激活码类型自动处理：
  │   ├── points: 增加商户点数余额
  │   ├── account: 为指定游戏账号创建订阅
  │   ├── window: 为指定窗口创建订阅
  │   └── host: 为主机创建订阅
  └── 返回结果
```

## 二、数据库表结构修改

### 2.1 activation_code_batch 表改造

```sql
ALTER TABLE activation_code_batch
ADD COLUMN subscription_type VARCHAR(20) DEFAULT 'points' COMMENT '订阅类型: points/account/window/host',
ADD COLUMN target_id VARCHAR(36) COMMENT '定向订阅目标ID（游戏账号/窗口/主机ID）',
ADD COLUMN target_name VARCHAR(100) COMMENT '定向订阅目标名称',
ADD COLUMN points INT COMMENT '点数（points类型使用）',
ADD COLUMN duration_days INT COMMENT '时长天数（订阅类型使用）',
ADD COLUMN daily_price DECIMAL(10,2) COMMENT '每日价格（订阅类型使用）';
```

### 2.2 activation_code 表改造

```sql
ALTER TABLE activation_code
ADD COLUMN subscription_type VARCHAR(20) COMMENT '继承自批次的订阅类型',
ADD COLUMN target_id VARCHAR(36) COMMENT '继承自批次的目标ID',
ADD COLUMN target_name VARCHAR(100) COMMENT '继承自批次的目标名称';
```

### 2.3 新增表：subscription_price（订阅价格配置）

```sql
CREATE TABLE subscription_price (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(20) NOT NULL COMMENT '类型: account/window/host',
    target_id VARCHAR(36) COMMENT '目标ID（可为null表示通用价格）',
    target_name VARCHAR(100) COMMENT '目标名称',
    price_per_day DECIMAL(10,2) NOT NULL COMMENT '每日价格',
    min_days INT DEFAULT 1 COMMENT '最小天数',
    max_days INT DEFAULT 365 COMMENT '最大天数',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_target (target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订阅价格配置表';
```

## 三、实体类修改

### 3.1 ActivationCodeBatch.java 修改

```java
// 新增字段
private String subscriptionType;  // points/account/window/host
private String targetId;         // 定向目标ID
private String targetName;       // 定向目标名称
private Integer points;          // 点数
private Integer durationDays;    // 时长天数
private BigDecimal dailyPrice;   // 每日价格
```

### 3.2 ActivationCode.java 修改

```java
// 新增字段
private String subscriptionType;  // 继承自批次
private String targetId;          // 继承自批次
private String targetName;        // 继承自批次
```

### 3.3 新增 SubscriptionPrice.java

```java
@Data
@TableName("subscription_price")
public class SubscriptionPrice {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;
    private String type;                    // account/window/host
    private String targetId;                // null表示通用价格
    private String targetName;
    private BigDecimal pricePerDay;
    private Integer minDays;
    private Integer maxDays;
    private String status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
```

## 四、Service层修改

### 4.1 ActivationCodeServiceImpl 修改

#### generateBatch 方法增强
```java
@Transactional
public ActivationCodeBatch generateBatch(ActivationCodeBatchRequest request) {
    // 1. 保存批次信息（包括新字段）
    ActivationCodeBatch batch = new ActivationCodeBatch();
    batch.setSubscriptionType(request.getSubscriptionType());
    batch.setTargetId(request.getTargetId());
    batch.setTargetName(request.getTargetName());
    batch.setPoints(request.getPoints());
    batch.setDurationDays(request.getDurationDays());
    batch.setDailyPrice(request.getDailyPrice());
    // ... 其他字段

    // 2. 生成激活码
    for (int i = 0; i < request.getCount(); i++) {
        ActivationCode code = new ActivationCode();
        // 继承批次信息
        code.setSubscriptionType(batch.getSubscriptionType());
        code.setTargetId(batch.getTargetId());
        code.setTargetName(batch.getTargetName());
        // ...
    }
}
```

### 4.2 新增 MerchantSubscriptionService

```java
public interface MerchantSubscriptionService {
    /**
     * 激活码激活（直接订阅模式）
     */
    ApiResponse<Map<String, Object>> activate(String code);

    /**
     * 获取订阅价格
     */
    List<SubscriptionPriceDto> getPrices(String type, String targetId);

    /**
     * 创建定向订阅
     */
    ApiResponse<SubscriptionDto> createSubscription(String merchantId, String userId,
        String type, String targetId, Integer durationDays);
}
```

### 4.3 MerchantSubscriptionServiceImpl 实现

```java
@Override
@Transactional
public ApiResponse<Map<String, Object>> activate(String code) {
    // 1. 验证激活码
    ActivationCode activationCode = activationCodeMapper.selectOne(
        new LambdaQueryWrapper<ActivationCode>()
            .eq(ActivationCode::getCode, code)
    );

    // 2. 检查激活码状态
    if (!"unused".equals(activationCode.getStatus())) {
        return ApiResponse.error(400, "激活码已被使用");
    }

    // 3. 根据类型处理
    String subscriptionType = activationCode.getSubscriptionType();
    String merchantId = UserContext.getMerchantId();
    String userId = UserContext.getUserId();

    if ("points".equals(subscriptionType)) {
        // 点数模式：增加余额
        balanceService.addPoints(merchantId, activationCode.getBatch().getPoints(),
            userId, "activation_code", activationCode.getId(), "激活码充值");
    } else {
        // 订阅模式：直接创建订阅
        ActivationCodeBatch batch = activationCode.getBatch();
        Subscription subscription = new Subscription();
        subscription.setMerchantId(merchantId);
        subscription.setUserId(userId);
        subscription.setType(subscriptionType);
        subscription.setTargetId(activationCode.getTargetId());
        subscription.setTargetName(activationCode.getTargetName());
        subscription.setDurationDays(batch.getDurationDays());
        subscription.setPointsCost(batch.getPoints());
        subscription.setStartTime(LocalDateTime.now());
        subscription.setExpireTime(LocalDateTime.now().plusDays(batch.getDurationDays()));
        subscription.setStatus("active");
        subscriptionMapper.insert(subscription);
    }

    // 4. 标记激活码已使用
    activationCode.setStatus("used");
    activationCode.setUsedBy(merchantId);
    activationCode.setUsedTime(LocalDateTime.now());
    activationCodeMapper.updateById(activationCode);

    // 5. 更新商户累计点数（如果需要）
    // ...

    return ApiResponse.success("激活成功", result);
}
```

## 五、DTO修改

### 5.1 ActivationCodeBatchRequest 新增字段

```java
private String subscriptionType;
private String targetId;
private String targetName;
private Integer points;
private Integer durationDays;
private BigDecimal dailyPrice;
```

### 5.2 新增 SubscriptionPriceDto

```java
@Data
public class SubscriptionPriceDto {
    private String id;
    private String type;
    private String targetId;
    private String targetName;
    private BigDecimal pricePerDay;
    private Integer minDays;
    private Integer maxDays;
}
```

## 六、前端修改

### 6.1 创建激活码页面改造

**ActivationCodeList.vue**

```vue
<el-dialog v-model="createDialogVisible" title="创建激活码批次" width="500px">
  <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
    <!-- 新增：订阅类型选择 -->
    <el-form-item label="类型" prop="subscriptionType">
      <el-select v-model="createForm.subscriptionType" @change="handleTypeChange">
        <el-option label="点数充值" value="points" />
        <el-option label="游戏账号订阅" value="account" />
        <el-option label="窗口订阅" value="window" />
        <el-option label="主机订阅" value="host" />
      </el-select>
    </el-form-item>

    <!-- 根据类型显示不同表单 -->
    <template v-if="createForm.subscriptionType === 'points'">
      <el-form-item label="点数" prop="points">
        <el-input-number v-model="createForm.points" :min="1" />
      </el-form-item>
    </template>

    <template v-else>
      <!-- 定向目标选择 -->
      <el-form-item label="目标" prop="targetId">
        <el-select v-model="createForm.targetId" placeholder="请选择目标">
          <!-- 根据类型加载不同列表 -->
        </el-select>
      </el-form-item>
      <el-form-item label="时长(天)" prop="durationDays">
        <el-input-number v-model="createForm.durationDays" :min="1" :max="365" />
      </el-form-item>
      <el-form-item label="每日价格">
        {{ calculateDailyPrice() }} 元/天
      </el-form-item>
    </template>
  </el-form>
</el-dialog>
```

### 6.2 激活/续费页面改造

**SubscriptionList.vue**

商户端的激活对话框可以简化，因为类型和目标已经在激活码中指定：

```vue
<el-dialog v-model="rechargeDialogVisible" title="激活" width="400px">
  <el-form ref="rechargeFormRef" :model="rechargeForm" :rules="rechargeRules">
    <el-form-item label="激活码" prop="activationCode">
      <el-input v-model="rechargeForm.activationCode" placeholder="请输入激活码" />
    </el-form-item>
    <!-- 显示激活码将创建的内容预览 -->
    <div v-if="previewInfo" class="activation-preview">
      <p>类型：{{ previewInfo.typeName }}</p>
      <p v-if="previewInfo.targetName">目标：{{ previewInfo.targetName }}</p>
      <p v-if="previewInfo.points">点数：{{ previewInfo.points }}</p>
      <p v-if="previewInfo.durationDays">时长：{{ previewInfo.durationDays }}天</p>
    </div>
  </el-form>
</el-dialog>
```

## 七、API接口

### 7.1 管理员接口

| 接口 | 方法 | 说明 |
|------|------|------|
| POST /api/activation-codes/batch | 创建批次 | 支持新字段 |
| GET /api/activation-codes/batch/{id} | 获取批次详情 | |
| GET /api/subscription-prices | 获取价格配置 | type, targetId参数 |
| POST /api/subscription-prices | 创建价格配置 | |

### 7.2 商户接口

| 接口 | 方法 | 说明 |
|------|------|------|
| POST /api/merchant-subscription/activate | 激活（已修改） | 自动识别类型 |
| GET /api/merchant-subscription/preview | 预览激活码信息 | 输入激活码前查看 |

## 八、实施步骤

### 阶段1：数据库改造
1. 修改 activation_code_batch 表
2. 修改 activation_code 表
3. 创建 subscription_price 表

### 阶段2：后端实体和基础服务
1. 修改 ActivationCodeBatch 实体
2. 修改 ActivationCode 实体
3. 创建 SubscriptionPrice 实体和Mapper
4. 创建 SubscriptionPriceService

### 阶段3：核心业务逻辑
1. 修改 ActivationCodeServiceImpl.generateBatch
2. 修改 MerchantSubscriptionServiceImpl.activate
3. 更新 Controller

### 阶段4：前端改造
1. 创建激活码页面增强
2. 商户激活页面简化
3. 测试完整流程

## 九、注意事项

1. **向后兼容**：已有激活码（无subscriptionType）默认为points类型
2. **事务处理**：activate操作需要在事务中完成
3. **幂等性**：防止重复激活
4. **日志记录**：详细记录激活操作便于排查
