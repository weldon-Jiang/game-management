<template>
  <!-- 流媒体账号管理页面 -->
  <div class="page-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2>流媒体账号</h2>
        <span class="header-desc">管理流媒体平台账号</span>
      </div>
      <div class="header-right">
        <!-- 新增账号按钮 -->
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增账号
        </el-button>
      </div>
    </div>

    <!-- 账号列表表格 -->
    <div class="content-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
      >
        <!-- 商户列（仅平台管理员可见） -->
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="150" />
        <!-- 账号名称 -->
        <el-table-column prop="name" label="账号名称" min-width="150" />
        <!-- 邮箱 -->
        <el-table-column prop="email" label="邮箱" min-width="200" />
        <!-- 状态 -->
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 运行Agent -->
        <el-table-column prop="agentId" label="运行Agent" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.agentId" class="agent-id">{{ row.agentId.substring(0, 8) }}...</span>
            <span v-else class="text-muted">未运行</span>
          </template>
        </el-table-column>
        <!-- 最后心跳 -->
        <el-table-column prop="lastHeartbeat" label="最后心跳" width="170">
          <template #default="{ row }">
            {{ row.lastHeartbeat ? formatDate(row.lastHeartbeat) : '-' }}
          </template>
        </el-table-column>
        <!-- 创建时间 -->
        <el-table-column prop="createdTime" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <!-- 操作列 -->
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <!-- 启动自动化按钮（非busy状态显示） -->
            <el-button
              v-if="row.status !== 'busy'"
              type="success"
              link
              size="small"
              @click="showStartAutomationDialog(row)"
            >
              启动自动化
            </el-button>
            <!-- 停止自动化按钮（busy状态显示） -->
            <el-button
              v-else
              type="warning"
              link
              size="small"
              @click="handleStopAutomation(row)"
            >
              停止自动化
            </el-button>
            <!-- 编辑按钮 -->
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <!-- 登录记录按钮 -->
            <el-button type="info" link size="small" @click="showLoginRecords(row)">
              登录记录
            </el-button>
            <!-- 删除按钮 -->
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页组件 -->
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
      :title="dialogType === 'add' ? '新增流媒体账号' : '编辑流媒体账号'"
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
        <!-- 商户选择（仅平台管理员） -->
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
        <!-- 账号名称 -->
        <el-form-item label="账号名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入账号名称" />
        </el-form-item>
        <!-- 邮箱 -->
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="formData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <!-- 密码 -->
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="formData.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <!-- 认证码（非必填） -->
        <el-form-item label="认证码" prop="authCode">
          <el-input
            v-model="formData.authCode"
            type="password"
            placeholder="请输入认证码（选填）"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 启动自动化对话框 -->
    <el-dialog
      v-model="automationDialogVisible"
      title="启动自动化"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <!-- 流媒体账号（只读显示） -->
        <el-form-item label="流媒体账号">
          <span class="automation-account-name">{{ selectedAccount?.name }}</span>
        </el-form-item>
        <!-- Agent选择 -->
        <el-form-item label="选择Agent" required>
          <el-select
            v-model="selectedAgentId"
            placeholder="请选择在线Agent"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="agent in onlineAgents"
              :key="agent.agentId"
              :label="formatAgentLabel(agent)"
              :value="agent.agentId"
            />
          </el-select>
        </el-form-item>
        <!-- 任务类型 -->
        <el-form-item label="任务类型">
          <el-select v-model="taskType" style="width: 100%">
            <el-option label="串流控制" value="stream_control" />
            <el-option label="模板匹配" value="template_match" />
            <el-option label="场景检测" value="scene_detection" />
          </el-select>
        </el-form-item>
        <!-- 优先级 -->
        <el-form-item label="优先级">
          <el-input-number v-model="priority" :min="0" :max="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="automationDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="automationLoading" @click="handleStartAutomation">
          启动
        </el-button>
      </template>
    </el-dialog>

    <!-- 登录记录对话框 -->
    <el-dialog
      v-model="recordsDialogVisible"
      title="Xbox主机登录记录"
      width="600px"
    >
      <div class="records-list" v-if="loginRecords.length > 0">
        <div
          v-for="hostId in loginRecords"
          :key="hostId"
          class="record-item"
        >
          <el-icon><Monitor /></el-icon>
          <span>{{ hostId }}</span>
        </div>
      </div>
      <el-empty v-else description="暂无登录记录" />
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 流媒体账号管理组件
 *
 * 功能说明：
 * - 展示和管理流媒体账号列表
 * - 支持账号的增删改查操作
 * - 提供启动和停止自动化功能
 * - 查看账号的登录记录
 *
 * 页面布局：
 * - 页面头部：标题和新增按钮
 * - 内容区域：账号列表表格
 * - 分页组件：数据分页
 * - 对话框：新增/编辑、启动自动化、登录记录
 */
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Monitor } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { streamingApi, merchantApi, agentApi, automationApi } from '@/api'
import { getStatusText, getStatusType } from '@/utils/constants'

// ==================== 状态定义 ====================

/**
 * 认证状态管理
 * 用于获取当前用户是否为平台管理员
 */
const authStore = useAuthStore()

/**
 * 加载状态标识
 * 控制表格loading显示
 */
const loading = ref(false)

/**
 * 提交按钮loading状态
 * 防止重复提交
 */
const submitLoading = ref(false)

/**
 * 自动化操作loading状态
 */
const automationLoading = ref(false)

/**
 * 账号列表数据
 */
const tableData = ref([])

/**
 * 商户列表数据
 * 用于新增/编辑时的商户选择
 */
const merchantList = ref([])

/**
 * 在线Agent列表
 * 用于启动自动化时的Agent选择
 */
const onlineAgents = ref([])

/**
 * 分页参数
 * - pageNum: 当前页码
 * - pageSize: 每页数量
 * - total: 总记录数
 */
const pagination = reactive({
  pageNum: 1,
  pageSize: 10,
  total: 0
})

/**
 * 新增/编辑对话框可见性
 */
const dialogVisible = ref(false)

/**
 * 登录记录对话框可见性
 */
const recordsDialogVisible = ref(false)

/**
 * 启动自动化对话框可见性
 */
const automationDialogVisible = ref(false)

/**
 * 对话框类型
 * - 'add': 新增模式
 * - 'edit': 编辑模式
 */
const dialogType = ref('add')

/**
 * 表单引用
 * 用于表单验证
 */
const formRef = ref(null)

/**
 * 登录记录列表
 */
const loginRecords = ref([])

/**
 * 选中的流媒体账号
 * 用于启动自动化时传递账号信息
 */
const selectedAccount = ref(null)

/**
 * 选中的Agent ID
 * 用于启动自动化
 */
const selectedAgentId = ref('')

/**
 * 任务类型
 * - stream_control: 串流控制
 * - template_match: 模板匹配
 * - scene_detection: 场景检测
 */
const taskType = ref('stream_control')

/**
 * 任务优先级
 * 数值越小优先级越高
 */
const priority = ref(0)

/**
 * 表单数据
 * 用于新增和编辑账号
 */
const formData = reactive({
  id: '',              // 账号ID（编辑时使用）
  merchantId: '',     // 商户ID
  name: '',           // 账号名称
  email: '',          // 邮箱
  password: '',       // 密码（必填）
  authCode: ''        // 认证码（非必填）
})

/**
 * 表单验证规则
 */
const formRules = {
  name: [
    { required: true, message: '请输入账号名称', trigger: 'blur' },
    { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// ==================== 方法定义 ====================

/**
 * 加载商户列表
 *
 * 功能说明：
 * - 仅平台管理员需要加载商户列表
 * - 用于新增/编辑账号时的商户选择
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
 * 加载在线Agent列表
 *
 * 功能说明：
 * - 查询状态为online的Agent
 * - 用于启动自动化时的Agent选择
 */
const loadOnlineAgents = async () => {
  try {
    const res = await agentApi.list({ status: 'online', pageSize: 100 })
    if (res.code === 0 || res.code === 200) {
      onlineAgents.value = res.data?.records || []
    }
  } catch (error) {
    console.error('Failed to load online agents:', error)
  }
}

/**
 * 加载账号列表数据
 *
 * 功能说明：
 * - 调用API获取流媒体账号分页数据
 * - 更新表格数据和分页信息
 */
const loadData = async () => {
  loading.value = true
  tableData.value = [] // 立即清空旧数据，避免显示过期内容
  try {
    const res = await streamingApi.list({
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    })
    tableData.value = res.data?.records || []
    pagination.total = res.data?.total || 0
  } catch (error) {
    console.error('Failed to load streaming accounts:', error)
    tableData.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

/**
 * 显示新增账号对话框
 *
 * 功能说明：
 * - 重置表单数据
 * - 设置对话框类型为新增
 * - 非平台管理员自动填入当前商户ID
 */
const showAddDialog = () => {
  dialogType.value = 'add'
  formData.id = ''
  formData.merchantId = authStore.isPlatformAdmin ? '' : authStore.merchantId
  formData.name = ''
  formData.email = ''
  formData.password = ''
  formData.authCode = ''
  dialogVisible.value = true
}

/**
 * 显示编辑账号对话框
 *
 * 功能说明：
 * - 填充表单数据为选中行的信息
 * - 设置对话框类型为编辑
 *
 * 参数说明：
 * - row: 账号行数据
 */
const showEditDialog = (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.merchantId = row.merchantId
  formData.name = row.name
  formData.email = row.email
  formData.password = ''  // 编辑时不显示原密码
  formData.authCode = ''  // 编辑时不清空认证码
  dialogVisible.value = true
}

/**
 * 提交表单（新增/编辑）
 *
 * 功能说明：
 * - 验证表单数据
 * - 调用对应的创建或更新API
 * - 成功后关闭对话框并刷新列表
 */
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitLoading.value = true
  try {
    if (dialogType.value === 'add') {
      // 新增账号
      await streamingApi.create({
        merchantId: formData.merchantId,
        name: formData.name,
        email: formData.email,
        password: formData.password,
        authCode: formData.authCode || undefined
      })
      ElMessage.success('创建成功')
    } else {
      // 更新账号
      const updateData = {
        name: formData.name,
        authCode: formData.authCode || undefined
      }
      // 如果填写了新密码，则更新密码
      if (formData.password) {
        updateData.password = formData.password
      }
      await streamingApi.update(formData.id, updateData)
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
 * 显示启动自动化对话框
 *
 * 功能说明：
 * - 保存选中的账号信息
 * - 重置选择项
 * - 加载在线Agent列表
 *
 * 参数说明：
 * - row: 选中的账号行数据
 */
const showStartAutomationDialog = async (row) => {
  selectedAccount.value = row
  selectedAgentId.value = ''
  taskType.value = 'stream_control'
  priority.value = 0
  await loadOnlineAgents()
  automationDialogVisible.value = true
}

/**
 * 格式化Agent显示标签
 *
 * 功能说明：
 * - 生成Agent下拉选项的显示文本
 * - 格式：短ID... - 商户名 (在线状态)
 *
 * 参数说明：
 * - agent: Agent对象
 *
 * 返回值：
 * - 格式化的显示文本
 */
const formatAgentLabel = (agent) => {
  const shortId = agent.agentId ? agent.agentId.substring(0, 8) : 'unknown'
  const merchant = agent.merchantName || '未知商户'
  const status = agent.status === 'online' ? '在线' : '离线'
  return `${shortId}... - ${merchant} (${status})`
}

/**
 * 启动自动化任务
 *
 * 功能说明：
 * - 验证是否已选择Agent
 * - 调用启动自动化API
 * - 成功后关闭对话框并刷新列表
 */
const handleStartAutomation = async () => {
  if (!selectedAgentId.value) {
    ElMessage.warning('请选择Agent')
    return
  }

  automationLoading.value = true
  try {
    const res = await automationApi.start({
      streamingAccountIds: [selectedAccount.value.id],
      agentId: selectedAgentId.value,
      taskType: taskType.value,
      priority: priority.value,
      description: `为账号 ${selectedAccount.value.name} 启动自动化`
    })

    if (res.code === 0 || res.code === 200) {
      const data = res.data || {}
      ElMessage.success(`已创建${data.total || 1}个自动化任务`)
      automationDialogVisible.value = false
      loadData()
    } else {
      ElMessage.error(res.message || '启动自动化失败')
    }
  } catch (error) {
    ElMessage.error('启动自动化失败')
  } finally {
    automationLoading.value = false
  }
}

/**
 * 停止自动化任务
 *
 * 功能说明：
 * - 弹出确认对话框
 * - 调用停止自动化API
 * - 成功后刷新列表
 *
 * 参数说明：
 * - row: 账号行数据
 */
const handleStopAutomation = async (row) => {
  await ElMessageBox.confirm(
    `确定要停止账号「${row.name}」的自动化任务吗？`,
    '停止自动化',
    {
      confirmButtonText: '确定停止',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )

  try {
    const res = await automationApi.stop(row.id)
    if (res.code === 0 || res.code === 200) {
      ElMessage.success('已停止自动化任务')
      loadData()
    } else {
      ElMessage.error(res.message || '停止自动化失败')
    }
  } catch (error) {
    ElMessage.error('停止自动化失败')
  }
}

/**
 * 显示登录记录
 *
 * 功能说明：
 * - 调用API获取该账号的Xbox主机登录记录
 * - 打开登录记录对话框显示结果
 *
 * 参数说明：
 * - row: 账号行数据
 */
const showLoginRecords = async (row) => {
  try {
    const res = await streamingApi.getXboxHosts(row.id)
    loginRecords.value = res.data || []
    recordsDialogVisible.value = true
  } catch (error) {
    console.error('Failed to load login records:', error)
  }
}

/**
 * 删除账号
 *
 * 功能说明：
 * - 正在运行自动化的账号不能删除
 * - 弹出确认对话框
 * - 调用删除API后刷新列表
 *
 * 参数说明：
 * - row: 账号行数据
 */
const handleDelete = async (row) => {
  if (row.status === 'busy') {
    ElMessage.warning('该账号正在运行自动化任务，请先停止')
    return
  }

  await ElMessageBox.confirm(`确定要删除账号「${row.name}」吗？`, '提示', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  })

  try {
    await streamingApi.delete(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (error) {
    // 错误已在拦截器中处理
  }
}

/**
 * 格式化日期显示
 *
 * 功能说明：
 * - 将ISO日期字符串转换为本地化日期时间格式
 * - 格式：YYYY-MM-DD HH:mm
 *
 * 参数说明：
 * - dateStr: ISO格式的日期字符串
 *
 * 返回值：
 * - 格式化后的日期字符串
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

/**
 * 组件挂载完成后
 * - 加载商户列表（如果是平台管理员）
 * - 加载账号列表数据
 */
onMounted(() => {
  loadMerchants()
  loadData()
})
</script>

<style scoped>
/* 页面容器 */
.page-container {
  padding: 0;
}

/* 页面头部样式 */
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

/* 内容卡片样式 */
.content-card {
  background: rgba(18, 18, 26, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 24px;
}

/* 表格样式覆盖 */
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

/* Agent ID样式 */
.agent-id {
  color: #10b981;
  font-size: 12px;
}

/* 灰色文字样式 */
.text-muted {
  color: #6b7280;
}

/* 分页组件样式 */
.pagination-wrap {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 分页组件样式覆盖 */
:deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: #8a8a8a;
  --el-pagination-hover-color: #6366f1;
  --el-pagination-button-disabled-bg-color: transparent;
  --el-pagination-button-bg-color: transparent;
  --el-pagination-border-color: rgba(255, 255, 255, 0.06);
  --el-pagination-disabled-color: #5a5a5a;
  --el-pagination-button-color: #8a8a8a;
}

:deep(.el-pagination .el-pager li) {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  margin: 0 3px;
  color: #8a8a8a;
  font-size: 13px;
  min-width: 32px;
  height: 32px;
  line-height: 32px;
}

:deep(.el-pagination .el-pager li:hover) {
  color: #6366f1;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
}

:deep(.el-pagination .btn-prev, .el-pagination .btn-next) {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  color: #8a8a8a;
}

:deep(.el-pagination .btn-prev:hover, .el-pagination .btn-next:hover) {
  color: #6366f1;
}

:deep(.el-pagination .el-pagination__jump) {
  color: #8a8a8a;
}

:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

/* 对话框样式 */
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

/* 自动化账号名称样式 */
.automation-account-name {
  color: #10b981;
  font-weight: 500;
}

/* 登录记录列表样式 */
.records-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.record-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  color: #b0b0b0;
  font-size: 13px;
}

.record-item .el-icon {
  color: #3b82f6;
  font-size: 18px;
}
</style>
