# Xbox主机增强方案 - MAC地址支持

## 一、问题背景

### 1.1 当前问题

| 问题 | 说明 |
|------|------|
| **缺少MAC地址** | XboxHost表只有IP字段，没有MAC地址 |
| **IP不稳定** | Xbox主机重启后IP可能变化，导致匹配失败 |
| **Agent匹配依赖IP** | 如果IP变化，Agent可能找不到正确的主机 |

### 1.2 为什么需要MAC地址

1. **稳定性**：MAC地址是物理地址，不会随IP变化而变化
2. **唯一性**：每个设备的MAC地址全球唯一
3. **可靠性**：Agent可以根据MAC精确定位Xbox主机
4. **防冲突**：避免多台设备IP相同导致的匹配混乱

---

## 二、数据库改造

### 2.1 新增MAC地址字段

```sql
-- 为 xbox_host 表添加 MAC 地址字段
ALTER TABLE xbox_host
ADD COLUMN mac_address VARCHAR(17) COMMENT 'MAC物理地址（如 AA:BB:CC:DD:EE:FF）' AFTER ip_address;

-- 创建索引加速查询
CREATE INDEX idx_xbox_host_mac ON xbox_host(mac_address);
```

### 2.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| mac_address | VARCHAR(17) | MAC物理地址，格式如 AA:BB:CC:DD:EE:FF |

---

## 三、实体类改造

### 3.1 XboxHost.java 新增字段

```java
/**
 * Xbox主机实体类
 */
@Data
@TableName("xbox_host")
public class XboxHost {
    // ... 现有字段 ...

    private String ipAddress;
    
    // 新增：MAC物理地址
    private String macAddress;
    
    private String status;
    // ... 其他字段 ...
}
```

---

## 四、前端页面改造

### 4.1 XboxHostList.vue 改造

#### 4.1.1 列表增加MAC地址列

```vue
<el-table-column prop="macAddress" label="MAC地址" width="170">
  <template #default="{ row }">
    <span v-if="row.macAddress" class="mac-address">{{ row.macAddress }}</span>
    <span v-else class="text-muted">未填写</span>
  </template>
</el-table-column>
```

#### 4.1.2 新增/编辑对话框增加MAC输入

```vue
<el-dialog
  v-model="dialogVisible"
  :title="dialogType === 'add' ? '新增Xbox主机' : '编辑Xbox主机'"
  width="500px"
>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="formRules"
    label-width="100px"
  >
    <el-form-item v-if="authStore.isPlatformAdmin" label="所属商户" prop="merchantId">
      <el-select v-model="formData.merchantId" placeholder="请选择商户" style="width: 100%">
        <el-option v-for="m in merchantList" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
    </el-form-item>

    <el-form-item label="Xbox ID" prop="xboxId">
      <el-input v-model="formData.xboxId" :disabled="dialogType === 'edit'" placeholder="请输入Xbox ID" />
    </el-form-item>

    <el-form-item label="主机名称" prop="name">
      <el-input v-model="formData.name" placeholder="请输入主机名称" />
    </el-form-item>

    <el-form-item label="IP地址" prop="ipAddress">
      <el-input v-model="formData.ipAddress" placeholder="请输入IP地址" />
    </el-form-item>

    <!-- 新增：MAC地址 -->
    <el-form-item label="MAC地址" prop="macAddress">
      <el-input 
        v-model="formData.macAddress" 
        placeholder="如 AA:BB:CC:DD:EE:FF（可选）"
      />
      <div class="form-tip">MAC地址用于Agent精确匹配主机，建议填写</div>
    </el-form-item>
  </el-form>

  <template #footer>
    <el-button @click="dialogVisible = false">取消</el-button>
    <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
  </template>
</el-dialog>
```

#### 4.1.3 表单验证规则增强

```javascript
const formRules = {
  xboxId: [
    { required: true, message: '请输入Xbox ID', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入主机名称', trigger: 'blur' }
  ],
  ipAddress: [
    { required: true, message: '请输入IP地址', trigger: 'blur' },
    { 
      pattern: /^(\d{1,3}\.){3}\d{1,3}$/, 
      message: '请输入正确的IP地址格式', 
      trigger: 'blur' 
    }
  ],
  // 新增：MAC地址格式验证
  macAddress: [
    {
      pattern: /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/,
      message: 'MAC地址格式错误，示例：AA:BB:CC:DD:EE:FF',
      trigger: 'blur'
    }
  ]
}
```

#### 4.1.4 表单数据初始化

```javascript
const formData = reactive({
  id: '',
  merchantId: '',
  xboxId: '',
  name: '',
  ipAddress: '',
  macAddress: ''  // 新增
})

// 重置表单时清空MAC地址
const resetForm = () => {
  Object.keys(formData).forEach(key => {
    if (key !== 'merchantId') {
      formData[key] = ''
    }
  })
}
```

### 4.2 MAC地址样式

```css
.mac-address {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.form-tip {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}
```

---

## 五、Agent端支持

### 5.1 任务参数已包含MAC

在之前的优化中，已将Xbox主机完整信息传给Agent：

```json
{
  "taskId": "xxx",
  "streamingAccount": {
    "id": "xxx",
    "name": "流媒体账号A"
  },
  "gameAccount": {
    "id": "xxx",
    "name": "游戏账号B"
  },
  "xboxHost": {
    "id": "xxx",
    "xboxId": "XBOX12345",
    "name": "客厅Xbox",
    "ipAddress": "192.168.1.100",
    "macAddress": "AA:BB:CC:DD:EE:FF",  // ← Agent可用
    "boundStreamingAccountId": "xxx",
    "boundGamertag": "PlayerOne"
  }
}
```

### 5.2 Agent根据MAC匹配主机

**xbox_discovery.py 已支持**：

```python
class XboxDiscovery:
    def discover_xbox(self, identifier):
        """
        根据标识符发现Xbox主机
        
        Args:
            identifier: 可以是MAC地址、IP地址或Xbox ID
            
        Returns:
            Xbox主机对象或None
        """
        # 1. 首先尝试MAC地址匹配（最精确）
        if self._is_mac_address(identifier):
            xbox = self._find_by_mac(identifier)
            if xbox:
                return xbox
        
        # 2. 然后尝试IP地址匹配
        if self._is_ip_address(identifier):
            xbox = self._find_by_ip(identifier)
            if xbox:
                return xbox
        
        # 3. 最后尝试Xbox ID匹配
        xbox = self._find_by_xbox_id(identifier)
        if xbox:
            return xbox
        
        return None
```

### 5.3 Agent匹配优先级

| 优先级 | 匹配方式 | 说明 |
|-------|---------|------|
| 1 | MAC地址 | 最精确，设备唯一标识 |
| 2 | IP地址 | 可能有变化 |
| 3 | Xbox ID | 唯一但需要网络发现 |

---

## 六、自动化发现增强

### 6.1 Xbox主机发现流程

```
1. Agent启动时扫描网络中的Xbox主机
   ↓
2. 发现的主机记录：MAC地址、IP、Xbox ID
   ↓
3. 定时广播发现请求
   ↓
4. 更新主机状态（online/offline）
   ↓
5. 记录lastSeenTime
```

### 6.2 手动维护的优势

| 方式 | 优势 |
|------|------|
| **手动维护+Agent发现** | ✅ 数据准确<br>✅ 自动同步状态<br>✅ 可预分配资源 |
| **仅Agent发现** | ❌ 数据不完整<br>❌ 无法提前绑定账号<br>❌ 难以管理 |

---

## 七、实施步骤

### 第一步：数据库（0.5天）
```sql
ALTER TABLE xbox_host ADD COLUMN mac_address VARCHAR(17) COMMENT 'MAC物理地址';
CREATE INDEX idx_xbox_host_mac ON xbox_host(mac_address);
```

### 第二步：后端实体（0.5天）
- 修改 XboxHost.java
- 修改 XboxHostServiceImpl.java

### 第三步：前端（1天）
- XboxHostList.vue 增加MAC输入
- 列表显示MAC地址
- 表单验证增强

### 第四步：测试（0.5天）
- 手动填写MAC地址
- Agent根据MAC匹配测试
- 完整流程测试

---

## 八、注意事项

1. **MAC地址格式**：统一使用 `AA:BB:CC:DD:EE:FF` 格式
2. **可选字段**：MAC地址不是必填，但建议填写
3. **唯一性**：同一商户下的MAC地址应唯一
4. **兼容性**：旧数据没有MAC地址，Agent降级使用IP匹配
