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
        <el-button @click="loadData">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <!-- 新增账号按钮 -->
        <el-button @click="showImportDialog">
          批量导入
        </el-button>
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon>
          新增账号
        </el-button>
      </div>
    </div>

    <!-- 账号列表表格 -->
    <div class="content-card">
      <div v-if="authStore.isPlatformAdmin" class="toolbar">
        <el-select
          v-model="filterMerchantId"
          placeholder="商户筛选"
          style="width: 180px"
          clearable
          filterable
          @change="handleMerchantFilter"
        >
          <el-option
            v-for="merchant in merchantList"
            :key="merchant.id"
            :label="merchant.name"
            :value="merchant.id"
          />
        </el-select>
        <el-button @click="handleMerchantFilter">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
      <div class="table-container">
      <el-table
        :data="tableData"
        v-loading="loading"
        class="data-table"
        scrollbar-always-on
      >
        <!-- 商户列（仅平台管理员可见） -->
        <el-table-column v-if="authStore.isPlatformAdmin" prop="merchantName" label="所属商户" min-width="150" show-overflow-tooltip />
        <!-- 邮箱 -->
        <el-table-column prop="email" label="邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column prop="platform" label="平台" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="getPlatformTypeTag(row.platform)" size="small">
              {{ getPlatformTypeText(row.platform) }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 状态 -->
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStreamingAccountStatusType(row.status)" size="small">
              {{ getStreamingAccountStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 运行Agent -->
        <el-table-column prop="agentId" label="运行Agent" width="300">
          <template #default="{ row }">
            <span v-if="row.agentId" class="agent-id">{{ row.agentName || row.agentId }}</span>
            <span v-else class="text-muted">未运行</span>
          </template>
        </el-table-column>
        <!-- 最后心跳 -->
        <el-table-column prop="lastHeartbeat" label="最后心跳" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.lastHeartbeat ? formatDate(row.lastHeartbeat) : '-' }}
          </template>
        </el-table-column>
        <!-- 创建时间 -->
        <el-table-column prop="createdTime" label="创建时间" width="170" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatDate(row.createdTime) }}
          </template>
        </el-table-column>
        <!-- 操作列 -->
        <el-table-column label="操作" width="360" fixed="right" align="center" :style="{ backgroundColor: '#0f0f1a' }">
          <template #default="{ row }">
            <!-- 启动自动化按钮（非busy状态显示） -->
            <el-button
              v-if="row.taskStatus !== 'busy'"
              type="success"
              link
              size="small"
              :disabled="!isPlatformAutomationSupported(row.platform)"
              :title="!isPlatformAutomationSupported(row.platform) ? '该账号为 PlayStation 类型，自动化功能尚未开放' : ''"
              @click="showStartAutomationDialog(row)"
            >
              启动串流
            </el-button>
            <!-- 停止自动化按钮（busy状态显示） -->
            <el-button
              v-if="row.taskStatus === 'busy'"
              type="primary"
              link
              size="small"
              @click="goTaskMonitor(row)"
            >
              查看任务
            </el-button>
            <el-button
              v-if="row.taskStatus === 'busy'"
              type="warning"
              link
              size="small"
              @click="handleStopAutomation(row)"
            >
              停止
            </el-button>
            <el-button type="info" link size="small" @click="showHostDialog(row)">
              串流主机
            </el-button>
            <!-- 编辑按钮 -->
            <el-button type="primary" link size="small" @click="showEditDialog(row)">
              编辑
            </el-button>
            <!-- 关联游戏账号按钮 -->
            <el-button type="warning" link size="small" @click="showBindGameAccountsDialog(row)">
              关联游戏账号
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
        <!-- 邮箱 -->
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="formData.email" placeholder="请输入邮箱" />
        </el-form-item>
        <!-- 密码 -->
        <el-form-item label="密码" :prop="dialogType === 'add' ? 'password' : ''">
          <template v-if="dialogType === 'edit' && !passwordVisible">
            <el-input v-model="formData.password" placeholder="请输入新密码（点击输入框查看原密码）" @focus="loadPassword">
            </el-input>
          </template>
          <template v-else-if="dialogType === 'edit' && passwordVisible">
            <el-input
              v-model="formData.password"
              type="text"
              placeholder="请输入新密码（不修改请留空）"
            >
            </el-input>
          </template>
          <template v-else>
            <el-input
              v-model="formData.password"
              type="password"
              placeholder="请输入密码"
              show-password
            />
          </template>
        </el-form-item>
        <el-form-item label="平台类型" prop="platform">
          <el-select v-model="formData.platform" placeholder="请选择平台类型" style="width: 100%">
            <el-option
              v-for="item in PLATFORM_TYPES"
              :key="item.code"
              :label="item.name"
              :value="item.code"
            />
          </el-select>
          <div v-if="formData.platform === 'playstation'" class="form-tip">
            PlayStation 账号已支持录入与管理；自动化功能即将上线，当前仅支持 Xbox。
          </div>
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

    <StartWizard
      v-model="wizardVisible"
      :account="selectedAccount"
      :agents="onlineAgents"
      :game-accounts="wizardGameAccounts"
      @started="onWizardStarted"
    />

    <!-- 遗留单步对话框（保留兼容，默认隐藏） -->
    <el-dialog
      v-if="false"
      v-model="automationDialogVisible"
      title="启动自动化"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="100px">
        <!-- 流媒体账号（只读显示） -->
        <el-form-item label="流媒体账号">
          <span class="automation-account-name">{{ selectedAccount?.email }}</span>
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
        <el-form-item label="主机（可选）">
          <el-select
            v-model="selectedHostId"
            placeholder="不指定，由 Agent 自动匹配"
            style="width: 100%"
            clearable
            filterable
          >
            <el-option
              v-for="host in boundHosts"
              :key="host.id"
              :label="`${host.name || host.xboxId} (${host.ipAddress || '-'})`"
              :value="host.id"
            />
          </el-select>
        </el-form-item>
        <!-- 游戏操作类型 -->
        <el-form-item label="游戏操作类型" required>
          <el-select
            v-model="selectedGameActionType"
            placeholder="请选择游戏操作类型"
            style="width: 100%"
          >
            <el-option
              v-for="type in visibleGameActionTypes"
              :key="type.code"
              :label="type.name"
              :value="type.code"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="automationDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="automationLoading" @click="handleStartAutomation">
          启动
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="批量导入流媒体账号"
      width="600px"
      :close-on-click-modal="false"
    >
      <div class="import-template">
        <h4>导入说明</h4>
        <ol>
          <li>请先点击"下载模板"按钮获取导入模板</li>
          <li>按照模板格式填写流媒体账号信息</li>
          <li>上传填写好的CSV文件</li>
          <li>系统会验证数据格式和重复情况</li>
          <li>验证通过后点击"开始导入"</li>
        </ol>
      </div>
      <el-form-item v-if="authStore.isPlatformAdmin" label="导入到商户">
        <el-select
          v-model="importMerchantId"
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
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="handleFileChange"
        :file-list="fileList"
        class="upload-component"
      >
        <template #trigger>
          <el-button>选择CSV文件</el-button>
        </template>
        <template #tip>
          <div class="el-upload__tip">只能上传CSV文件</div>
        </template>
      </el-upload>
      <div v-if="importResult" class="import-result">
        <el-alert
          :title="`导入完成：成功 ${importResult.successCount} 条，跳过 ${importResult.skipCount} 条，失败 ${importResult.failCount} 条`"
          :type="importResult.failCount > 0 ? 'warning' : 'success'"
          show-icon
        >
          <template v-if="importResult.errors && importResult.errors.length > 0">
            <div v-for="(err, idx) in importResult.errors.slice(0, 10)" :key="idx" class="error-item">
              {{ err }}
            </div>
            <div v-if="importResult.errors.length > 10" class="error-more">
              还有 {{ importResult.errors.length - 10 }} 条错误...
            </div>
          </template>
        </el-alert>
      </div>
      <template #footer>
        <el-button @click="handleDownloadTemplate">下载模板</el-button>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" :disabled="!selectedFile" @click="handleImport">
          开始导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 关联游戏账号对话框 -->
    <el-dialog
      v-model="bindDialogVisible"
      :title="`关联游戏账号 - ${selectedStreamingAccount?.email}`"
      width="700px"
      :close-on-click-modal="false"
    class="bind-dialog"
    >
      <div class="bind-section">
        <h4>已关联的游戏账号</h4>
        <el-table
          :data="boundGameAccounts"
          v-loading="bindLoading"
          max-height="200"
        >
          <el-table-column prop="gameName" label="游戏昵称" />
          <el-table-column prop="email" label="邮箱" />
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-button type="danger" link size="small" @click="handleUnbindGameAccount(row)">
                解绑
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="boundGameAccounts.length === 0 && !bindLoading" class="empty-tip">
          暂无关联的游戏账号
        </div>
      </div>
      <div class="bind-section">
        <h4>添加关联</h4>
        <el-table
          ref="unboundTableRef"
          :data="unboundGameAccounts"
          max-height="200"
          @selection-change="handleUnboundSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          <el-table-column prop="gameName" label="游戏昵称" />
          <el-table-column prop="email" label="邮箱" />
        </el-table>
        <div v-if="unboundGameAccounts.length === 0" class="empty-tip">
          暂无未关联的游戏账号
        </div>
        <div class="bind-actions">
          <el-button
            type="primary"
            size="small"
            :disabled="selectedUnboundAccounts.length === 0"
            @click="handleBindGameAccounts"
          >
            关联选中账号 ({{ selectedUnboundAccounts.length }})
          </el-button>
        </div>
      </div>
    </el-dialog>

    <StreamingAccountHostDialog
      v-model="hostDialogVisible"
      :account="hostDialogAccount"
    />
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
import { ref, reactive, onMounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import StartWizard from '@/components/automation/StartWizard.vue'
import StreamingAccountHostDialog from '@/components/streaming/StreamingAccountHostDialog.vue'
import { Plus, Monitor, Refresh } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { streamingApi, merchantApi, agentApi, automationApi, gameAccountApi, merchantGroupApi, subscriptionApi, xboxApi } from '@/api'
import { getAgentDisplayName, getStreamingAccountStatusText, getStreamingAccountStatusType, getAccountTaskStatusText, getAccountTaskStatusType, PLATFORM_TYPES, getPlatformTypeText, getPlatformTypeTag, isPlatformAutomationSupported, getVisibleGameActionTypes, isSamePlatformType } from '@/utils/constants'

// ==================== 状态定义 ====================

/**
 * 认证状态管理
 * 用于获取当前用户是否为平台管理员
 */
const authStore = useAuthStore()
const router = useRouter()

const goTaskMonitor = (row) => {
  const query = { streamingAccountId: row.id }
  if (row.agentId) {
    query.agentId = row.agentId
  }
  if (row.merchantId) {
    query.merchantId = row.merchantId
  }
  router.push({ name: 'Tasks', query })
}

const wizardVisible = ref(false)
const wizardGameAccounts = ref([])
const hostDialogVisible = ref(false)
const hostDialogAccount = ref(null)

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

/** 平台管理员列表商户筛选 */
const filterMerchantId = ref('')

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

/**
 * 批量导入相关状态
 */
const importDialogVisible = ref(false)
const uploadRef = ref(null)
const fileList = ref([])
const selectedFile = ref(null)
const importLoading = ref(false)
const importResult = ref(null)
const importMerchantId = ref('')

/**
 * 关联游戏账号相关状态
 */
const bindDialogVisible = ref(false)
const bindLoading = ref(false)
const selectedStreamingAccount = ref(null)
const boundGameAccounts = ref([])
const unboundGameAccounts = ref([])
const selectedUnboundAccounts = ref([])
const unboundTableRef = ref(null)

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

const selectedHostId = ref('')

const boundHosts = ref([])

// 可见的游戏操作类型列表
const visibleGameActionTypes = getVisibleGameActionTypes()

// 选中的游戏操作类型
const selectedGameActionType = ref('')

/**
 * 表单数据
 * 用于新增和编辑账号
 */
const formData = reactive({
  id: '',              // 账号ID（编辑时使用）
  merchantId: '',     // 商户ID
  email: '',          // 邮箱
  password: '',       // 密码（必填）
  authCode: '',       // 认证码（非必填）
  platform: ''    // 平台类型（必填）
})

// 密码显示状态（编辑时）
const passwordVisible = ref(false)  // 是否显示真实密码
const passwordLoaded = ref(false)    // 密码是否已加载
const actualPassword = ref('')      // 真实密码（点击输入框后加载）

/**
 * 表单验证规则
 */
const formRules = {
  merchantId: [
    { required: true, message: '请选择商户', trigger: 'change' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ],
  platform: [
    { required: true, message: '请选择平台类型', trigger: 'change' }
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
    const res = await agentApi.listOnline()
    onlineAgents.value = res.data || []
  } catch (error) {
    console.error('Failed to load online agents:', error)
    onlineAgents.value = []
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
    const params = {
      pageNum: pagination.pageNum,
      pageSize: pagination.pageSize
    }
    if (authStore.isPlatformAdmin && filterMerchantId.value) {
      params.merchantId = filterMerchantId.value
    }
    const res = await streamingApi.list(params)
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
  formData.email = ''
  formData.password = ''
  formData.authCode = ''
  formData.platform = ''
  passwordVisible.value = false
  passwordLoaded.value = false
  actualPassword.value = ''
  dialogVisible.value = true
}

/**
 * 加载密码（点击输入框图标或聚焦密码框时调用）
 */
const loadPassword = async () => {
  if (passwordLoaded.value) {
    // 已经加载过，直接显示
    passwordVisible.value = true
    return
  }

  try {
    const res = await streamingApi.getPasswordById(formData.id)
    if (res.code === 0 || res.code === 200) {
      formData.password = res.data.password || ''
      passwordLoaded.value = true
      passwordVisible.value = true
    }
  } catch (error) {
    console.error('Failed to load password:', error)
    ElMessage.error('加载密码失败')
  }
}

/**
 * 显示编辑账号对话框
 *
 * 功能说明：
 * - 通过API获取账号详情（包含解密后的密码）
 * - 填充表单数据为账号信息
 * - 设置对话框类型为编辑
 *
 * 参数说明：
 * - row: 账号行数据
 */
const showEditDialog = async (row) => {
  dialogType.value = 'edit'
  formData.id = row.id
  formData.merchantId = row.merchantId
  formData.email = row.email
  formData.password = ''
  formData.authCode = row.authCode || ''
  formData.platform = row.platform || ''
  passwordVisible.value = false
  passwordLoaded.value = false
  actualPassword.value = ''
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
        email: formData.email,
        password: formData.password,
        authCode: formData.authCode || undefined,
        platform: formData.platform
      })
      ElMessage.success('创建成功')
    } else {
      // 更新账号
      const updateData = {
        merchantId: formData.merchantId,
        email: formData.email,
        authCode: formData.authCode || undefined,
        platform: formData.platform
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
  if (!isPlatformAutomationSupported(row.platform)) {
    ElMessage.warning('该账号为 PlayStation 类型，自动化功能尚未开放')
    return
  }

  let boundAccounts = []

  try {
    const subRes = await subscriptionApi.getStatus()
    const hasSubscription = subRes.data?.currentSubscription
    const balance = subRes.data?.balance || 0
    
    if (!hasSubscription && balance <= 0) {
      ElMessage.warning('当前没有有效的包月且余额不足，请先购买订阅或充值点数')
      return
    }

    const res = await gameAccountApi.list({ streamingId: row.id, pageSize: 1000 })
    boundAccounts = res.data?.records || []
    if (boundAccounts.length === 0) {
      ElMessage.warning('该流媒体账号下没有关联的游戏账号，请先关联游戏账号后再启动自动化')
      return
    }

    const validateRes = await subscriptionApi.validateAutomationRequest({
      streamingAccountId: row.id,
      gameAccountIds: boundAccounts.map(acc => acc.id)
    })

    if (!validateRes.data?.canStart) {
      ElMessage.warning(validateRes.data?.errors?.join('; ') || '无法启动自动化，请检查订阅状态')
      return
    }
  } catch (error) {
    console.error('Failed to validate automation:', error)
    ElMessage.warning('检查订阅状态失败')
    return
  }

  selectedAccount.value = row
  selectedAgentId.value = ''
  selectedHostId.value = ''
  boundHosts.value = []
  wizardGameAccounts.value = boundAccounts
  selectedGameActionType.value = visibleGameActionTypes[0]?.code || 'squad_battle'
  await loadOnlineAgents()
  if (onlineAgents.value.length === 0) {
    ElMessage.warning('当前没有在线的 Agent，请确保 Agent 服务已启动并连接')
    return
  }
  wizardVisible.value = true
}

const onWizardStarted = (data) => {
  loadData()
  if (data?.taskId) {
    ElMessage.success({
      message: '串流已启动，可在任务详情选择自动化类型',
      duration: 5000
    })
  }
}

const loadBoundHosts = async (streamingAccountId, accountPlatform = 'xbox') => {
  try {
    const res = await xboxApi.listPage({ pageNum: 1, pageSize: 500 })
    const records = res.data?.records || []
    boundHosts.value = records.filter(
      (h) =>
        h.boundStreamingAccountId === streamingAccountId &&
        isSamePlatformType(h.platform, accountPlatform)
    )
  } catch (error) {
    console.error('Failed to load bound hosts:', error)
    boundHosts.value = []
  }
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
  const name = getAgentDisplayName(agent)
  const status = agent.status === 'online' ? '在线' : '离线'
  return `${name} (${status})`
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
      hostId: selectedHostId.value || undefined,
      gameActionType: selectedGameActionType.value,
      description: `为账号 ${selectedAccount.value.email} 启动自动化`
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
    `确定要停止账号「${row.email}」的自动化任务吗？`,
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
 * 显示导入对话框
 */
const showImportDialog = async () => {
  importResult.value = null
  selectedFile.value = null
  fileList.value = []
  importMerchantId.value = authStore.isPlatformAdmin ? '' : authStore.merchantId
  if (authStore.isPlatformAdmin && merchantList.value.length === 0) {
    await loadMerchants()
  }
  importDialogVisible.value = true
}

/**
 * 下载导入模板
 */
const handleDownloadTemplate = async () => {
  try {
    const res = await streamingApi.downloadTemplate()
    const template = res.data
    const blob = new Blob(['\ufeff' + template], { type: 'text/csv;charset=utf-8' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'streaming_account_template.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to download template:', error)
  }
}

/**
 * 处理文件选择
 */
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  importResult.value = null
}

/**
 * 处理导入
 */
const handleImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择CSV文件')
    return
  }

  importLoading.value = true
  importResult.value = null

  try {
    const text = await selectedFile.value.text()
    const lines = text.split('\n').filter(line => line.trim())

    if (lines.length < 2) {
      ElMessage.warning('CSV文件内容为空或格式不正确')
      return
    }

    const header = lines[0].split(',').map(h => h.trim())
    const emailIdx = header.indexOf('邮箱')
    const passwordIdx = header.indexOf('密码')
    if (emailIdx < 0 || passwordIdx < 0) {
      ElMessage.warning('CSV文件格式不正确，请检查表头是否包含：邮箱、密码')
      return
    }

    const authCodeIdx = header.indexOf('认证码')
    const platformIdx = header.indexOf('平台类型')
    if (platformIdx < 0) {
      ElMessage.warning('CSV文件必须包含「平台类型」列（xbox 或 playstation）')
      return
    }

    const accounts = []
    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',').map(v => v.trim())
      if (values.length >= 2 && values[emailIdx] && values[passwordIdx]) {
        const platform = values[platformIdx] || ''
        if (!platform) {
          continue
        }
        accounts.push({
          email: values[emailIdx],
          password: values[passwordIdx],
          authCode: authCodeIdx >= 0 ? (values[authCodeIdx] || '') : '',
          platform
        })
      }
    }

    if (accounts.length === 0) {
      ElMessage.warning('没有有效的数据行')
      return
    }

    if (authStore.isPlatformAdmin && !importMerchantId.value) {
      ElMessage.warning('请选择要导入到的商户')
      return
    }

    const res = await streamingApi.batchImport({
      merchantId: importMerchantId.value,
      accounts: accounts
    })
    importResult.value = res.data

    if (res.data.failCount === 0) {
      ElMessage.success('导入成功')
      importDialogVisible.value = false
      loadData()
    } else {
      ElMessage.warning(`导入完成：成功 ${res.data.successCount} 条，跳过 ${res.data.skipCount} 条，失败 ${res.data.failCount} 条`)
    }
  } catch (error) {
    console.error('Import failed:', error)
    ElMessage.error('导入失败')
  } finally {
    importLoading.value = false
  }
}

/**
 * 显示串流主机绑定对话框
 */
const showHostDialog = (row) => {
  hostDialogAccount.value = row
  hostDialogVisible.value = true
}

/**
 * 显示关联游戏账号对话框
 */
const showBindGameAccountsDialog = async (row) => {
  selectedStreamingAccount.value = row
  bindDialogVisible.value = true
  await loadBoundGameAccounts()
  await loadUnboundGameAccounts()
}

/**
 * 加载已关联的游戏账号
 */
const loadBoundGameAccounts = async () => {
  bindLoading.value = true
  try {
    const res = await gameAccountApi.list({ streamingId: selectedStreamingAccount.value.id, pageSize: 1000 })
    boundGameAccounts.value = res.data?.records || []
  } catch (error) {
    console.error('Failed to load bound game accounts:', error)
    boundGameAccounts.value = []
  } finally {
    bindLoading.value = false
  }
}

/**
 * 加载未关联的游戏账号
 */
const loadUnboundGameAccounts = async () => {
  try {
    const res = await gameAccountApi.getUnbound(
      selectedStreamingAccount.value.merchantId,
      selectedStreamingAccount.value.platform || 'xbox'
    )
    unboundGameAccounts.value = res.data || []
  } catch (error) {
    console.error('Failed to load unbound game accounts:', error)
    unboundGameAccounts.value = []
  }
}

/**
 * 处理未关联账号选择变化
 */
const handleUnboundSelectionChange = (selection) => {
  selectedUnboundAccounts.value = selection
}

/**
 * 绑定选中的游戏账号
 */
const handleBindGameAccounts = async () => {
  if (selectedUnboundAccounts.value.length === 0) {
    ElMessage.warning('请先选择要关联的游戏账号')
    return
  }

  try {
    const gameAccountIds = selectedUnboundAccounts.value.map(acc => acc.id)
    await gameAccountApi.bind(selectedStreamingAccount.value.id, { gameAccountIds })
    ElMessage.success('关联成功')
    selectedUnboundAccounts.value = []
    if (unboundTableRef.value) {
      unboundTableRef.value.clearSelection()
    }
    await loadBoundGameAccounts()
    await loadUnboundGameAccounts()
  } catch (error) {
    console.error('Failed to bind game accounts:', error)
  }
}

/**
 * 解绑单个游戏账号
 */
const handleUnbindGameAccount = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要解绑账号「${row.gameName}」吗？`, '提示', {
      confirmButtonText: '确定解绑',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await gameAccountApi.unbind({ gameAccountIds: [row.id] })
    ElMessage.success('解绑成功')
    await loadBoundGameAccounts()
    await loadUnboundGameAccounts()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('Failed to unbind game account:', error)
    }
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
    ElMessage.warning('该账号正在运行任务，请等待任务完成，或在任务详情中终止任务后再操作')
    return
  }

  await ElMessageBox.confirm(`确定要删除账号「${row.email}」吗？`, '提示', {
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

const handleMerchantFilter = () => {
  pagination.pageNum = 1
  loadData()
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
.form-tip {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-color-warning);
  line-height: 1.5;
}

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
:deep(.el-pagination .el-pagination__total) {
  color: #6b7280;
}

/* 对话框样式 */
:deep(.el-dialog) {
  background: rgb(18, 18, 26);
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

/* 自动化游戏昵称样式 */
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

.import-template {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.import-template h4 {
  color: #ffffff;
  margin: 0 0 12px;
  font-size: 14px;
}

.import-template ol {
  color: #b0b0b0;
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
}

.upload-component {
  margin-top: 16px;
}

.import-result {
  margin-top: 20px;
}

.error-item {
  font-size: 12px;
  color: #e6a23c;
  margin-top: 4px;
}

.error-more {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.bind-dialog .el-dialog__body {
  padding: 20px;
}

.bind-section {
  margin-bottom: 16px;
}

.bind-section:first-child {
  margin-top: 16px;
}

.bind-section:last-child {
  margin-bottom: 0;
}

.bind-section h4 {
  color: #ffffff;
  margin: 0 0 12px;
  font-size: 14px;
}

.bind-section .empty-tip {
  color: #6b7280;
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}

.bind-actions {
  margin-top: 16px;
  text-align: right;
}

/* 组件特有样式 */

.detail-section {
  margin-top: 16px;
  text-align: right;
}

/* 固定列hover不变透明 */
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

/* 密码可见性输入框样式 */
.password-visible-input :deep(.el-input__inner) {
  color: #409eff;
}
</style>
