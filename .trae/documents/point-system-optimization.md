# 点数制系统优化完成

## 优化内容

### 1. 后端优化

#### MerchantSubscriptionController.java
- `getStatus` 接口：移除 expireTime 依赖，只根据 merchant.status 判断
- `getActivatedInfo` 接口：移除 expireTime 返回

**逻辑变更**：
- **之前**：根据 expireTime 判断 active/expired
- **现在**：只要 merchant.status = 'active' 就算正常

### 2. 前端优化

#### SubscriptionList.vue
- 移除 `expireTime` 变量
- `loadSubscriptionStatus` 不再处理 expireTime
- 状态卡片移除"到期时间"显示
- 状态显示"正常" / "未激活"，不再显示到期时间

## 新的业务逻辑

### 点数制系统核心概念

| 项 | 说明 |
|---|------|
| **激活码** | 充值点数用，充多少得多少 |
| **merchant_balance.balance** | 商户当前可用点数 |
| **subscription** | 某个服务的订阅（按主机/窗口/号），消耗点数 |
| **merchant.expireTime** | **保留但不再使用**（历史兼容） |

### 工作流程

1. 商户使用激活码充值 → 增加点数余额
2. 创建服务订阅 → 扣除相应点数
3. 商户状态始终根据 merchant.status 判断，与点数无关

## 表结构说明

**merchant_balance（主要使用）**：
- `balance` - 当前可用点数
- `totalRecharged` - 累计充值
- `totalConsumed` - 累计消耗

**merchant（保留兼容）**：
- `totalPoints` - 累计充值（冗余字段，与 merchant_balance 同步）
- `expireTime` - **不再使用**（历史保留）

## 后续建议

如需要彻底清理，可以考虑：
1. 完全移除 merchant.expireTime 字段
2. 移除 merchant.totalPoints 字段，完全依赖 merchant_balance
