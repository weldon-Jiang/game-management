<template>
  <div class="page-container">
    <div class="page-header">
      <div class="header-left">
        <h2>Xbox主机</h2>
        <span class="header-desc">管理Xbox主机设备</span>
      </div>
      <div class="header-right">
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button type="success" @click="showDiscoverDialog">
          <el-icon><Plus /></el-icon>
          发现主机
        </el-button>
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增主机
        </el-button>
      </div>
    </div>

    <div class="content-card table-container">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
      >
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="150" />
        <el-table-column prop="xboxId" label="Xbox ID" min-width="180" show-overflow-tooltip />
        <el-table-column prop="name" label="主机名称" min-width="120">
          <template #default="{ row }">
            <span v-if="row.name" class="text-muted">{{ row.name }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="ipAddress" label="IP地址" width="140" />
        <el-table-column prop="macAddress" label="MAC地址" width="170">
          <template #default="{ row }">
            <span v-if="row.macAddress" class="mac-address">{{ row.macAddress }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getXboxHostStatusType(row.status)" size="small">
              {{ getXboxHostStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="boundStreamingAccountId" label="绑定账号" width="150">
          <template #default="{ row }">
            <span v-if="row.boundGamertag">{{ row.boundGamertag }}</span>
            <span v-else class="text-muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column prop="lastSeenTime" label="最后在线" width="170">
          <template #default="{ row }">
            {{ row.lastSeenTime ? formatDate(row.lastSeenTime) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right" align="center" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <el-button type="success" link size="small" @click="showBindDialog(row)">
              {{ row.boundStreamingAccountId ? '更换绑定' : '绑定账号' }}
            </el-button>
            <el-button
              v-if="row.boundStreamingAccountId"
              type="warning"
              link
              size="small"
              @click="handleUnbind(row)"
            >
              解绑
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="pagination.pageNum"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '新增Xbox主机' : '编辑Xbox主机'"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="90px"
        class="dialog-form"
      >
        <el-form-item v-if="authStore.isPlatformAdmin" label="所属商户" prop="merchantId">
          <el-select
            v-model="formData.merchantId"
            placeholder="请选择商户"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="merchant in merchantList"
              :key="merchant.id"
              :label="merchant.name"
              :value="merchant.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Xbox ID" prop="xboxId">
          <el-input
            v-model="formData.xboxId"
            :disabled="dialogType === 'edit'"
            placeholder="请输入Xbox ID"
          />
        </el-form-item>
        <el-form-item label="主机名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入主机名称" />
        </el-form-item>
        <el-form-item label="IP地址" prop="ipAddress">
          <el-input v-model="formData.ipAddress" placeholder="请输入IP地址" />
        </el-form-item>
        <el-form-item label="MAC地址" prop="macAddress">
          <el-input v-model="formData.macAddress" placeholder="如 AA:BB:CC:DD:EE:FF（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 绑定账号对话框 -->
    <el-dialog
      v-model="bindDialogVisible"
      title="绑定流媒体账号"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form ref="bindFormRef" :model="bindFormData" label-width="90px" class="dialog-form">
        <el-form-item label="Xbox主机">
          <el-input :value="currentHost?.name || currentHost?.xboxId" disabled />
        </el-form-item>
        <el-form-item label="选择账号" prop="streamingAccountId">
          <el-select
            v-model="bindFormData.streamingAccountId"
            placeholder="请选择流媒体账号"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="account in availableAccounts"
              :key="account.id"
              :label="`${account.name} (${account.email})`"
              :value="account.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Gamertag" prop="gamertag">
          <el-input v-model="bindFormData.gamertag" placeholder="请输入Gamertag（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bindDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleBind">
          确定绑定
        </el-button>
      </template>
    </el-dialog>

    <!-- 发现主机对话框 -->
    <el-dialog
      v-model="discoverDialogVisible"
      title="发现Xbox主机"
      width="650px"
      :close-on-click-modal="false"
    >
      <el-form ref="discoverFormRef" :model="discoverFormData" label-width="90px" class="dialog-form">
        <el-form-item label="选择Agent" prop="agentId">
          <el-select
            v-model="discoverFormData.agentId"
            placeholder="请选择在线的Agent"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="agent in onlineAgents"
              :key="agent.agentId"
              :label="`${agent.agentId} - ${agent.merchantName || '未知商户'}`"
              :value="agent.agentId"
            />
          </el-select>
        </el-form-item>
        <div v-if="discoverStatus === 'scanning'" class="scanning-indicator">
          <div class="scanning-content">
            <el-icon size="18" class="scanning-icon">
              <Refresh />
            </el-icon>
            <p>正在扫描局域网...</p>
            <el-progress
              :percentage="scanningProgress"
              :status="scanningProgress === 100 ? 'success' : 'active'"
              :text-inside="true"
              stroke-width="6"
              :show-text="false"
              style="width: 200px; margin: 16px auto 0;"
            />
          </div>
        </div>
        <div v-else-if="discoverStatus === 'result'" class="discover-result-box">
          <div :class="['result-icon', discoverResultData.discoveredCount > 0 ? 'success' : 'empty']">
            <Check v-if="discoverResultData.discoveredCount > 0" :size="14" />
            <Search v-else :size="14" />
          </div>
          <p class="result-message">{{ discoverResultData.message }}</p>
        </div>
        <div v-else class="discover-tips">
          <el-alert
            title="提示"
            type="info"
            :closable="false"
          >
            <p>点击确定后，系统将向指定Agent发送发现指令。</p>
            <p>Agent会扫描局域网内的Xbox主机并自动上报结果。</p>
          </el-alert>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="handleDiscoverClose">取消</el-button>
        <el-button v-if="discoverStatus !== 'scanning'" type="success" :loading="discoverLoading" @click="handleDiscover">
          {{ discoverStatus === 'result' ? '再次扫描' : '开始发现' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Check, Search } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { xboxApi, streamingApi, merchantApi, agentApi } from '@/api'
import { getXboxHostStatusText, getXboxHostStatusType } from '@/utils/constants'
import { connectStomp, subscribeToTopic, getStompClient } from '@/utils/stompClient'

let discoverySubscription = null

const authStore = useAuthStore()

/**
 * Xbox主机管理页面
 * 提供Xbox主机的增删改查和绑定流媒体账号功能
 */

// ==================== 状态定义 ====================

/**
 * 表格数据加载状态
 */
const loading = ref(false)

/**
 * 提交按钮加载状态
 */
const submitLoading = ref(false)

/**
 * 表格数据列表
 */
const tableData = ref([])

/**
 * 商户列表
 */
const merchantList = ref([])

/**
 * 分页参数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

/**
 * 对话框状态
 */
const dialogVisible = ref(false)
const bindDialogVisible = ref(false)
const discoverDialogVisible = ref(false)
const dialogType = ref('add')
const formRef = ref(null)
const bindFormRef = ref(null)
const discoverFormRef = ref(null)
const currentHost = ref(null)
const availableAccounts = ref([])
const onlineAgents = ref([])
const discoverLoading = ref(false)

/**
 * 表单数据
 */
const formData = reactive({
  id: '',
  merchantId: '',
  xboxId: '',
  name: '',
  ipAddress: '',
  macAddress: ''
})

/**
 * 表单验证规则
 */
const formRules = {
  xboxId: [
    { required: true, message: '请输入Xbox ID', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入主机名称', trigger: 'blur' },
    { min: 2, max: 30, message: '长度在 2 到 30 个字符', trigger: 'blur' }
  ],
  ipAddress: [
    { required: true, message: '请输入IP地址', trigger: 'blur' }
  ],
  macAddress: [
    {
      pattern: /^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$/,
      message: 'MAC地址格式错误，示例：AA:BB:CC:DD:EE:FF',
      trigger: 'blur'
    }
  ]
}

/**
 * 绑定表单数据
 */
const bindFormData = reactive({
  streamingAccountId: '',
  gamertag: ''
})

/**
 * 发现表单数据
 */
const discoverFormData = reactive({
  agentId: ''
})

/**
 * 发现状态: select | scanning | result
 */
const discoverStatus = ref('select')

/**
 * 扫描进度
 */
const scanningProgress = ref(0)

/**
 * 扫描进度定时器
 */
let scanningTimer = null

/**
 * 发现结果数据
 */
const discoverResultData = reactive({
  discoveredCount: 0,
  message: '',
  xboxes: [],
  agentId: '',
  agentName: ''
})

// ==================== 方法定义 ====================

/**
 * 加载商户列表
 */
const loadMerchants = async () => {
  if (!authStore.isPlatformAdmin) return
  try {
    const res = await merchantApi.listAll()
    merchantList.value = res.data || []
  } catch (error) {
    console.error('Failed to load merchants:', error)
  }
}

/**
 * 加载Xbox主机列表
 */
const loadData = async () => {
  loading.value = true
  try {
    const res = await xboxApi.listPage({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data.records || []
    pagination.total = res.data.total || 0
  } catch (error) {
    console.error('Failed to load Xbox hosts:', error)
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增对话框
 */
const showAddDialog = () => {
  dialogType.value = 'add'
  formData.id = ''
  formData.merchantId = authStore.isPlatformAdmin ? '' : authStore.merchantId
  formData.xboxId = ''
  formData.name = ''
  formData.ipAddress = ''
  formData.macAddress = ''
  dialogVisible.value = true
}

/**
 * 显示编辑对话框
 * @param {Object} row - 当前行数据
 */
const showEditDialog = (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.merchantId = row.merchantId
  formData.xboxId = row.xboxId
  formData.name = row.name
  formData.ipAddress = row.ipAddress
  formData.macAddress = row.macAddress || ''
  dialogVisible.value = true
}

/**
 * 提交表单
 */
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (dialogType.value === 'add') {
      await xboxApi.create({
        merchantId: formData.merchantId,
        xboxId: formData.xboxId,
        name: formData.name,
        ipAddress: formData.ipAddress,
        macAddress: formData.macAddress || undefined
      })
      ElMessage.success('创建成功')
    } else {
      await xboxApi.update(formData.id, {
        name: formData.name,
        ipAddress: formData.ipAddress,
        macAddress: formData.macAddress || undefined
      })
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 显示绑定账号对话框
 * @param {Object} row - 当前主机数据
 */
const showBindDialog = async (row) => {
  currentHost.value = row
  bindFormData.streamingAccountId = ''
  bindFormData.gamertag = ''

  try {
    const res = await xboxApi.getAvailableAccounts(row.id)
    availableAccounts.value = res.data || []
    bindDialogVisible.value = true
  } catch (error) {
    console.error('Failed to load available accounts:', error)
    availableAccounts.value = []
    bindDialogVisible.value = true
  }
}

/**
 * 提交绑定
 */
const handleBind = async () => {
  if (!bindFormData.streamingAccountId) {
    ElMessage.warning('请选择流媒体账号')
    return
  }

  submitLoading.value = true
  try {
    await xboxApi.bind(
      currentHost.value.id,
      bindFormData.streamingAccountId,
      bindFormData.gamertag || undefined
    )
    ElMessage.success('绑定成功')
    bindDialogVisible.value = false
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    submitLoading.value = false
  }
}

/**
 * 解绑流媒体账号
 * @param {Object} row - 当前主机数据
 */
const handleUnbind = async (row) => {
  await ElMessageBox.confirm(`确定要解绑「${row.name}」的流媒体账号吗？`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await xboxApi.unbind(row.id)
    ElMessage.success('解绑成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 删除主机
 * @param {Object} row - 当前行数据
 */
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定要删除主机「${row.name}」吗？`, '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'error'
  })

  try {
    await xboxApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 加载在线Agent列表
 */
const loadOnlineAgents = async () => {
  try {
    const res = await agentApi.listOnline()
    onlineAgents.value = res.data || []
  } catch (error) {
    console.error('Failed to load online agents:', error)
    onlineAgents.value = []
  }
}

/**
 * 显示发现主机对话框
 */
const showDiscoverDialog = async () => {
  discoverFormData.agentId = ''
  await loadOnlineAgents()
  
  if (onlineAgents.value.length === 0) {
    ElMessage.warning('当前没有在线的Agent，请确保Agent服务已启动并连接')
    return
  }
  
  discoverDialogVisible.value = true
}

/**
 * 初始化WebSocket连接并订阅Xbox发现消息
 */
const initWebSocket = async () => {
  try {
    await connectStomp()
    console.log('WebSocket connected successfully for Xbox discovery')
    
    if (discoverySubscription) {
      discoverySubscription.unsubscribe()
    }
    
    discoverySubscription = await subscribeToTopic('/topic/admins/xbox_discovered', (data) => {
      console.log('Xbox discovery result received:', data)
      
      if (discoverStatus.value === 'scanning') {
        handleDiscoverResult(data)
      } else {
        if (data.message) {
          ElMessage.info(data.message)
        }
        
        if (data.discoveredCount !== undefined) {
          loadData()
        }
      }
    })
  } catch (error) {
    console.error('Failed to connect WebSocket:', error)
  }
}

/**
 * 取消订阅Xbox发现消息
 */
const unsubscribeXboxDiscovery = () => {
  if (discoverySubscription) {
    discoverySubscription.unsubscribe()
    discoverySubscription = null
    console.log('Unsubscribed from Xbox discovery topic')
  }
}

/**
 * 发现超时定时器
 */
let discoverTimeoutTimer = null

/**
 * 检查WebSocket连接状态
 */
const checkWebSocketConnected = () => {
  return new Promise((resolve) => {
    const client = getStompClient()
    if (client && client.connected) {
      resolve(true)
    } else {
      // 尝试重新连接
      initWebSocket().then(() => {
        const newClient = getStompClient()
        resolve(newClient && newClient.connected)
      }).catch(() => {
        resolve(false)
      })
    }
  })
}

/**
 * 处理发现主机
 */
const handleDiscover = async () => {
  if (!discoverFormData.agentId) {
    ElMessage.warning('请选择要执行发现的Agent')
    return
  }

  if (discoverStatus.value === 'result') {
    discoverStatus.value = 'select'
    return
  }

  // 检查WebSocket连接状态
  const isConnected = await checkWebSocketConnected()
  if (!isConnected) {
    ElMessage.error('WebSocket连接失败，请刷新页面重试')
    return
  }

  discoverLoading.value = true
  try {
    await xboxApi.discover(discoverFormData.agentId)
    
    discoverStatus.value = 'scanning'
    scanningProgress.value = 0
    
    startScanningAnimation()
    
    // 设置超时处理（30秒，考虑到SSDP发现和网络扫描可能需要较长时间）
    if (discoverTimeoutTimer) {
      clearTimeout(discoverTimeoutTimer)
    }
    discoverTimeoutTimer = setTimeout(() => {
      if (discoverStatus.value === 'scanning') {
        ElMessage.warning('发现超时，请检查Agent连接并重试')
        discoverStatus.value = 'result'
        discoverResultData.discoveredCount = 0
        discoverResultData.message = '发现超时，请检查Agent连接并重试'
        stopScanningAnimation()
      }
    }, 30000)
    
    discoverLoading.value = false
  } catch (error) {
    discoverLoading.value = false
    discoverStatus.value = 'select'
    ElMessage.error('发起发现请求失败，请重试')
  }
}

/**
 * 启动扫描动画
 */
const startScanningAnimation = () => {
  if (scanningTimer) {
    clearInterval(scanningTimer)
  }
  
  scanningProgress.value = 0
  const increment = 2
  scanningTimer = setInterval(() => {
    if (scanningProgress.value < 95) {
      scanningProgress.value += increment
    }
  }, 100)
}

/**
 * 停止扫描动画
 */
const stopScanningAnimation = () => {
  if (scanningTimer) {
    clearInterval(scanningTimer)
    scanningTimer = null
  }
  scanningProgress.value = 100
}

/**
 * 处理发现结果
 * @param {Object} data - 发现结果数据
 */
const handleDiscoverResult = (data) => {
  // 清除超时定时器
  if (discoverTimeoutTimer) {
    clearTimeout(discoverTimeoutTimer)
    discoverTimeoutTimer = null
  }
  
  stopScanningAnimation()
  
  discoverResultData.discoveredCount = data.discoveredCount || 0
  discoverResultData.message = data.message || '发现完成'
  discoverResultData.xboxes = data.xboxes || []
  discoverResultData.agentId = data.agentId || ''
  discoverResultData.agentName = data.agentName || ''
  
  discoverStatus.value = 'result'
  
  loadData()
}

/**
 * 关闭发现对话框
 */
const handleDiscoverClose = () => {
  // 清除超时定时器
  if (discoverTimeoutTimer) {
    clearTimeout(discoverTimeoutTimer)
    discoverTimeoutTimer = null
  }
  
  stopScanningAnimation()
  discoverStatus.value = 'select'
  discoverDialogVisible.value = false
}

// ==================== 工具函数 ====================

/**
 * 格式化日期时间
 * @param {string} dateStr - 日期字符串
 * @returns {string} 格式化后的日期
 */
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadMerchants()
  loadData()
  initWebSocket()
})

onUnmounted(() => {
  unsubscribeXboxDiscovery()
})
</script>

<style scoped>
.page-container {
  padding: 0;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left h2 {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px;
}

.header-desc {
  font-size: 13px;
  color: #8a8a8a;
}

.mac-address {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: var(--text-secondary);
}

.text-muted {
  color: #6b7280;
  font-size: 13px;
}

:deep(.el-table) {
  background: transparent;
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: transparent;
  --el-table-header-bg-color: rgba(255, 255, 255, 0.03);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.15);
  --el-table-current-row-bg-color: rgba(99, 102, 241, 0.1);
  --el-table-border-color: rgba(255, 255, 255, 0.06);
  --el-table-header-border-color: rgba(255, 255, 255, 0.06);
  --el-table-text-color: #b0b0b0;
  --el-table-header-text-color: #888888;
  --el-table-row-hover-text-color: #ffffff;
}

:deep(.el-table__inner-wrapper::before) {
  display: none;
}

:deep(.el-table .el-table__row) {
  background: transparent !important;
}

:deep(.el-table .el-table__row:hover > td) {
  background: rgba(99, 102, 241, 0.15) !important;
}

:deep(.el-table th.el-table__cell) {
  font-weight: 500;
  font-size: 13px;
}

:deep(.el-table td.el-table__cell) {
  font-size: 13px;
  padding: 14px 0;
}

.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

:deep(.el-dialog) {
  background: rgba(18, 18, 26, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding: 20px 24px;
}

:deep(.el-dialog__title) {
  color: #ffffff;
  font-size: 16px;
  font-weight: 600;
}

:deep(.el-form-item__label) {
  color: #b0b0b0;
}

:deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  box-shadow: none;
}

:deep(.el-input__inner) {
  color: #ffffff;
}

:deep(.el-select__wrapper) {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: none;
}

:deep(.el-select__placeholder) {
  color: #5a5a5a;
}

/* Fixed column hover state */
:deep(.el-table__fixed-right:hover),
:deep(.el-table__fixed:hover) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__fixed-right .el-table__row:hover td),
:deep(.el-table__fixed .el-table__row:hover td) {
  background-color: #0f0f1a !important;
}

:deep(.el-table__body-wrapper .el-table__row:hover td.el-table__cell) {
  background-color: #1a1a2e !important;
}

/* 发现主机对话框样式 */
.scanning-indicator {
  margin-top: 20px;
}

.scanning-content {
  text-align: center;
  padding: 20px;
}

.scanning-icon {
  animation: spin 2s linear infinite;
  color: #6366f1;
  display: block;
  margin: 0 auto 12px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.scanning-content p {
  color: #b0b0b0;
  margin: 0;
}

.discover-result-box {
  text-align: center;
  padding: 20px;
  margin-top: 16px;
}

.result-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 40px;
  height: 40px;
  margin: 0 auto 12px;
}

.result-icon.success {
  color: #22c55e;
}

.result-icon.empty {
  color: #6b7280;
}

.result-message {
  color: #b0b0b0;
  margin: 0;
  font-size: 14px;
}

.discover-tips {
  margin-top: 16px;
}
</style>