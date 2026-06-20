/**
 * 全局常量配置
 * 统一管理所有硬编码的映射值
 */

// 认证错误码
export const AUTH_ERROR_CODES = {
  TOKEN_INVALID: 11001,
  TOKEN_EXPIRED: 11002,
  TOKEN_MISSING: 11003,
  USERNAME_PASSWORD_ERROR: 11004
}

export const isAuthError = (code) => {
  return code === AUTH_ERROR_CODES.TOKEN_INVALID
    || code === AUTH_ERROR_CODES.TOKEN_EXPIRED
    || code === AUTH_ERROR_CODES.TOKEN_MISSING
}

export const STATUS_TEXT_MAP = {
  active: '正常',
  inactive: '未激活',
  expired: '已过期',
  suspended: '已停用',
  disabled: '已禁用'
}

export const STATUS_TYPE_MAP = {
  active: 'success',
  inactive: 'info',
  expired: 'danger',
  suspended: 'warning',
  disabled: 'danger'
}

export const CODE_STATUS_MAP = {
  unused: '未使用',
  used: '已使用',
  expired: '已过期'
}

export const CODE_STATUS_TYPE_MAP = {
  unused: 'success',
  used: 'info',
  expired: 'danger'
}

export const AGENT_STATUS_MAP = {
  online: '在线',
  offline: '离线',
  reconnecting: '重连中',
  busy: '忙碌',
  error: '异常',
  uninstalled: '已卸载'
}

export const AGENT_STATUS_TYPE_MAP = {
  online: 'success',
  offline: 'info',
  reconnecting: 'warning',
  busy: 'warning',
  error: 'danger',
  uninstalled: 'warning'
}

export const XBOX_HOST_STATUS_MAP = {
  online: '在线',
  offline: '离线',
  busy: '忙碌',
  error: '异常'
}

export const XBOX_HOST_STATUS_TYPE_MAP = {
  online: 'success',
  offline: 'info',
  busy: 'warning',
  error: 'danger'
}

export const TASK_STATUS_MAP = {
  pending: { text: '待执行', type: 'warning' },
  running: { text: '执行中', type: 'primary' },
  paused: { text: '已暂停', type: 'warning' },
  completed: { text: '已完成', type: 'success' },
  failed: { text: '已失败', type: 'danger' },
  cancelled: { text: '已取消', type: 'info' },
  stopped: { text: '已停止', type: 'info' }
}

/** 已结束、不可再操作的任务状态 */
export const TASK_TERMINAL_STATUSES = ['completed', 'cancelled', 'failed', 'stopped']

export const isTaskTerminal = (status) => {
  if (!status) return false
  return TASK_TERMINAL_STATUSES.includes(status)
}

export const ACCOUNT_TASK_STATUS_MAP = {
  idle: { text: '空闲', type: 'success' },
  busy: { text: '忙碌', type: 'warning' }
}

export const TASK_TYPE_MAP = {
  template_match: '模板匹配',
  input_sequence: '输入序列',
  scene_detection: '场景检测',
  account_switch: '账号切换',
  stream_control: '串流控制',
  automation: '自动化任务',
  custom: '自定义'
}

export const AUTOMATION_TASK_TYPES = [
  { code: 'automation', name: '自动化任务' }
]

// 游戏操作类型（可见的才会在前端下拉中显示）
export const GAME_ACTION_TYPE_MAP = {
  auction_transfer: { text: '拍卖行转会', visible: true },
  squad_battle: { text: 'SQB模式', visible: true },
  transfer_sqb_combo: { text: '转会+SQB组合', visible: true },
  divisions_rivals: { text: 'DR模式', visible: true },
  weekend_league: { text: '周赛', visible: false },
  // 历史/默认类型（后端存量数据）
  daily_match: { text: '每日比赛', visible: false },
  training: { text: '训练模式', visible: false },
  mission: { text: '任务挑战', visible: false },
  custom: { text: '自定义操作', visible: false }
}

export const PLATFORM_TYPES = [
  { code: 'xbox', name: 'Xbox', automationSupported: true },
  { code: 'playstation', name: 'PlayStation', automationSupported: false }
]

export const PLATFORM_TYPE_MAP = {
  xbox: 'Xbox',
  playstation: 'PlayStation'
}

export const PLATFORM_TYPE_TAG_MAP = {
  xbox: 'primary',
  playstation: 'warning'
}

export const FEATURE_CODE_MAP = {
  stream_control: '串流控制',
  sqb: 'SQB任务',
  dr: 'DR任务',
  rush: 'Rush任务',
  transfer: '转会任务'
}

export const FEATURE_CODES = Object.keys(FEATURE_CODE_MAP)

export const GAME_ACCOUNT_STATUS_MAP = {
  active: '正常',
  locked: '已锁定',
  disabled: '已禁用'
}

export const GAME_ACCOUNT_STATUS_TYPE_MAP = {
  active: 'success',
  locked: 'warning',
  disabled: 'danger'
}

export const STREAMING_ACCOUNT_STATUS_MAP = {
  idle: '空闲',
  busy: '忙碌',
  error: '异常'
}

export const STREAMING_ACCOUNT_STATUS_TYPE_MAP = {
  idle: 'success',
  busy: 'warning',
  error: 'danger'
}

export const ROLE_TEXT_MAP = {
  platform_admin: '平台管理员',
  owner: '商户所有者',
  admin: '商户管理员',
  operator: '操作员'
}

export const ROLE_TYPE_MAP = {
  platform_admin: 'danger',
  owner: 'warning',
  admin: 'success',
  operator: 'info'
}

/**
 * 获取状态中文名称
 */
export const getStatusText = (status) => {
  if (!status) return '-'
  return STATUS_TEXT_MAP[status] || status
}

/**
 * 获取状态标签类型 (Element Plus tag type)
 */
export const getStatusType = (status) => {
  if (!status) return 'info'
  return STATUS_TYPE_MAP[status] || 'info'
}

/**
 * 获取激活码状态中文名称
 */
export const getCodeStatusText = (status) => {
  if (!status) return '-'
  return CODE_STATUS_MAP[status] || status
}

/**
 * 获取激活码状态标签类型
 */
export const getCodeStatusType = (status) => {
  if (!status) return 'info'
  return CODE_STATUS_TYPE_MAP[status] || 'info'
}

/**
 * 获取Agent状态中文名称
 */
export const getAgentStatusText = (status) => {
  if (!status) return '-'
  return AGENT_STATUS_MAP[status] || status
}

/**
 * 获取Agent状态标签类型
 */
export const getAgentStatusType = (status) => {
  if (!status) return 'info'
  return AGENT_STATUS_TYPE_MAP[status] || 'info'
}

/**
 * 获取Xbox主机状态中文名称
 */
export const getXboxHostStatusText = (status) => {
  if (!status) return '-'
  return XBOX_HOST_STATUS_MAP[status] || status
}

/**
 * 获取Xbox主机状态标签类型
 */
export const getXboxHostStatusType = (status) => {
  if (!status) return 'info'
  return XBOX_HOST_STATUS_TYPE_MAP[status] || 'info'
}

/**
 * 获取游戏账号状态中文名称
 */
export const getGameAccountStatusText = (status) => {
  if (!status) return '-'
  return GAME_ACCOUNT_STATUS_MAP[status] || status
}

/**
 * 获取游戏账号状态标签类型
 */
export const getGameAccountStatusType = (status) => {
  if (!status) return 'info'
  return GAME_ACCOUNT_STATUS_TYPE_MAP[status] || 'info'
}

export const getStreamingAccountStatusText = (status) => {
  if (!status) return '-'
  return STREAMING_ACCOUNT_STATUS_MAP[status] || status
}

export const getStreamingAccountStatusType = (status) => {
  if (!status) return 'info'
  return STREAMING_ACCOUNT_STATUS_TYPE_MAP[status] || 'info'
}

/**
 * 获取角色中文名称
 */
export const getRoleText = (role) => {
  if (!role) return '-'
  return ROLE_TEXT_MAP[role] || role
}

/**
 * 获取角色标签类型
 */
export const getRoleType = (role) => {
  if (!role) return 'info'
  return ROLE_TYPE_MAP[role] || 'info'
}

export const getAgentDisplayName = (agent, fallbackId = '') => {
  if (agent && typeof agent === 'object') {
    return agent.agentName || agent.host || agent.agentId || '-'
  }
  const id = typeof agent === 'string' ? agent : fallbackId
  return id || '-'
}

export const getTaskStatusText = (status) => {
  if (!status) return '-'
  return TASK_STATUS_MAP[status]?.text || status
}

export const getTaskStatusType = (status) => {
  if (!status) return 'info'
  return TASK_STATUS_MAP[status]?.type || 'info'
}

/** 会话已结束或失败时，任务 status 可与 sessionPhase 对齐展示 */
const TERMINAL_SESSION_PHASES = new Set(['closed', 'failed'])

/**
 * 长寿命串流任务复用新会话时，task.status 可能残留上一轮 completed；
 * 当前会话仍在进行时应展示 running / paused / pending。
 *
 * @param {object|null|undefined} task 含 status、sessionPhase、streamingAccountId、sessionId
 */
export const getEffectiveTaskStatus = (task) => {
  if (!task) return ''
  const rawStatus = String(task.status || '').toLowerCase()
  const phase = String(task.sessionPhase || '').toLowerCase()

  if (!phase) return task.status || ''

  if (phase.startsWith('paused') || rawStatus === 'paused') return 'paused'

  if (TERMINAL_SESSION_PHASES.has(phase)) {
    if (phase === 'failed') return 'failed'
    // STEP2/3 失败后 session 已 closed 但 task.status 可能残留 running
    if (phase === 'closed' && String(task.stepStatus || '').toUpperCase() === 'FAILED') {
      return 'failed'
    }
    return phase === 'failed' ? 'failed' : (task.status || rawStatus)
  }

  const isStreamingTask = Boolean(task.sessionId || task.streamingAccountId)
  if (isStreamingTask && ['completed', 'stopped', 'failed'].includes(rawStatus)) {
    return 'running'
  }

  if (rawStatus === 'pending' && isStreamingTask) {
    return 'running'
  }

  return task.status || ''
}

export const getAccountTaskStatusText = (status) => {
  if (!status) return '-'
  return ACCOUNT_TASK_STATUS_MAP[status]?.text || status
}

export const getAccountTaskStatusType = (status) => {
  if (!status) return 'info'
  return ACCOUNT_TASK_STATUS_MAP[status]?.type || 'info'
}

export const getTaskTypeText = (type) => {
  if (!type) return '-'
  return TASK_TYPE_MAP[type] || type
}

export const getPlatformTypeText = (platform) => {
  if (!platform) return 'Xbox'
  return PLATFORM_TYPE_MAP[platform] || platform
}

export const getPlatformTypeTag = (platform) => {
  if (!platform) return 'primary'
  return PLATFORM_TYPE_TAG_MAP[platform] || 'info'
}

/** 启动串流时主机选择提示：平台无法校验账号与主机远程授权关系 */
export const STREAMING_HOST_REMOTE_HINT = {
  xbox:
    '请确认所选 Xbox 已在该微软账号的 Xbox App 中完成远程游玩授权，且与当前串流账号对应。平台无法自动识别，选错主机将导致串流失败。',
  playstation:
    '请确认所选 PlayStation 已使用该账号启用 Remote Play 并完成主机注册。平台无法自动识别，需您自行确认主机与账号的对应关系。'
}

export const getStreamingHostRemoteHint = (platform) => {
  const code = platform || 'xbox'
  return STREAMING_HOST_REMOTE_HINT[code] || STREAMING_HOST_REMOTE_HINT.xbox
}

export const normalizePlatformType = (platform) => platform || 'xbox'

export const isSamePlatformType = (left, right) =>
  normalizePlatformType(left) === normalizePlatformType(right)

export const isPlatformAutomationSupported = (platform) => {
  const normalized = platform || 'xbox'
  const item = PLATFORM_TYPES.find(p => p.code === normalized)
  return item ? item.automationSupported : normalized === 'xbox'
}

/**
 * 获取可见的游戏操作类型列表（用于前端下拉选择）
 */
export const getVisibleGameActionTypes = () => {
  return Object.entries(GAME_ACTION_TYPE_MAP)
    .filter(([_, config]) => config.visible)
    .map(([code, config]) => ({ code, name: config.text }))
}

/**
 * 获取游戏操作类型中文名称
 */
export const getGameActionTypeText = (code) => {
  if (!code) return '-'
  return GAME_ACTION_TYPE_MAP[code]?.text || code
}

export const SESSION_PHASE_MAP = {
  opening: { text: '启动中', type: 'info' },
  authenticating: { text: '认证中', type: 'info' },
  discovering: { text: '发现主机', type: 'info' },
  streaming: { text: '串流连接中', type: 'primary' },
  initializing_display: { text: '初始化画面', type: 'primary' },
  initializing_input: { text: '初始化输入', type: 'primary' },
  ready: { text: '串流就绪（待选模式）', type: 'success' },
  automation_failed: { text: '自动化失败（可重试）', type: 'warning' },
  automating: { text: '自动化执行中', type: 'primary' },
  input_reconnecting: { text: '输入通道重连中', type: 'warning' },
  input_restored: { text: '输入通道已恢复', type: 'success' },
  input_reconnect_failed: { text: '输入通道重连失败', type: 'danger' },
  paused_immediate: { text: '已暂停', type: 'warning' },
  paused_after_match: { text: '本场后暂停', type: 'warning' },
  closing: { text: '关闭中', type: 'info' },
  closed: { text: '已关闭', type: 'info' },
  failed: { text: '失败', type: 'danger' }
}

export const SESSION_PHASE_HINT_MAP = {
  opening: '正在启动串流任务...',
  authenticating: '正在认证微软/xHome 账号...',
  discovering: '正在发现 Xbox 主机...',
  streaming: '正在建立云端串流连接...',
  ready: '账号、主机、LAN 首帧和 SmartGlass 输入通道已通过检查，可选择自动化类型。',
  automation_failed: 'Step4 自动化未完成，但串流会话仍保留，可重新选择模式后重试。',
  input_reconnecting: 'Input DataChannel 已关闭，Agent 正在自动重连；暂停/终止控制仍可用。',
  input_reconnect_failed: 'Input DataChannel 重连失败，可尝试「重连串流」或终止后重新启动。',
  initializing_display: '正在建立 LAN 首帧和显示链路；若失败通常与主机画面或网络有关。',
  initializing_input: '正在验证 SmartGlass 输入通道；若失败通常与 LAN 握手或网络有关。',
  failed: '串流准备失败，请结合错误信息区分账号认证、主机匹配、LAN 首帧或输入通道问题。',
  closed: '串流会话已结束。'
}

export const GAME_ACCOUNT_RUN_STATUS_MAP = {
  pending: { text: '待执行', type: 'info' },
  running: { text: '操作中', type: 'primary' },
  game_preparing: { text: '游戏准备中', type: 'primary' },
  gaming: { text: '比赛中', type: 'success' },
  completed: { text: '已完成', type: 'success' },
  failed: { text: '失败', type: 'danger' },
  cancelled: { text: '已取消', type: 'info' },
  skipped: { text: '已跳过', type: 'warning' },
  timeout: { text: '超时', type: 'danger' }
}

export const GAME_ACCOUNT_PHASE_MAP = {
  pending: '待执行',
  provisioning: '账号准备',
  automating: '自动化中',
  completed: '已完成',
  failed: '失败',
  skipped: '已跳过'
}

export const PROVISIONING_PHASE_MAP = {
  idle: '空闲',
  detecting: '检测中',
  adding: '添加账号',
  verifying: '校验中',
  ready: '准备完成',
  failed: '失败',
  skipped: '已跳过',
  login: '登录游戏',
  navigate: '导航中',
  switch_account: '切换账号',
  calibrate: '校准位置'
}

/** 任务事件 scope 中文 */
export const TASK_EVENT_SCOPE_MAP = {
  task: '任务',
  session: '会话',
  game_account: '游戏账号',
  module: '模块'
}

/** 自动化步骤 phase/step 中文（时间线展示） */
export const TASK_STEP_PHASE_MAP = {
  STEP1: '步骤一·登录',
  STEP2: '步骤二·串流握手',
  STEP3: '步骤三·串流环境',
  STEP4: '步骤四·游戏自动化',
  SESSION: '会话阶段'
}

const HOST_ATTEMPT_STATUS_MAP = {
  trying: '尝试中',
  success: '握手成功',
  connect_failed: '连接失败',
  wakeup_failed: '唤醒失败',
  offline: '未开机',
  occupied: '已被占用'
}

/** Agent 上报的英文事件消息 → 中文 */
export const TASK_EVENT_MESSAGE_MAP = {
  'Session closed': '会话已关闭',
  'Closing session': '正在关闭会话',
  'SESSION_READY': '串流就绪',
  'Reconnected': '重连成功',
  'Reconnecting': '正在重连',
  'Opening stream': '正在打开串流',
  'Window + decode ready': '窗口与解码就绪',
  'Authenticating': '正在认证',
  'Discovering console': '正在发现主机',
  'Starting streaming': '正在启动串流',
  'LAN 首帧未到达，无法确认真实主机画面': 'LAN 首帧失败：无法确认真实主机画面',
  'SmartGlass 输入通道未建立，无法确认真实主机串流': 'SmartGlass 输入通道失败：无法确认真实主机串流',
  'WebRTC 首帧未到达，无法确认真实主机画面': 'LAN 首帧失败：无法确认真实主机画面',
  'WebRTC DataChannel/媒体通道未建立，无法确认真实主机串流': 'SmartGlass 输入通道失败：无法确认真实主机串流',
  'input DataChannel 未 open': 'SmartGlass 输入通道未打开',
  'input DataChannel keepalive 发送失败': 'SmartGlass 输入保活失败',
  'Cancelled': '已取消',
  'Account skipped': '账号已跳过',
  '准备完成（跳过添加）': '准备完成（跳过添加）',
  '准备完成（账号已存在）': '准备完成（账号已存在）',
  '添加账号失败': '添加账号失败',
  '账号校验失败': '账号校验失败',
  'Input mode: virtual': '输入模式：虚拟手柄',
  'Input mode: physical': '输入模式：实体手柄',
  'Manual takeover ON': '人工接管已开启',
  'Manual takeover OFF': '人工接管已关闭',
  'Input channel closed': 'Input 通道已断开',
  'Input channel reconnecting': 'Input 通道重连中',
  'Input channel restored': 'Input 通道已恢复',
  'Manual input detected': '检测到人工按键',
  '用户终止串流': '用户终止串流',
  '用户关闭串流窗口，任务已结束': '用户关闭串流窗口，任务已结束',
  '用户取消执行': '用户取消执行',
  '用户手动停止': '用户手动停止',
  '被管理员停止': '被管理员停止',
  'Agent离线，任务已取消': 'Agent 离线，任务已取消',
  'Agent重新上线，任务已清理': 'Agent 重新上线，任务已清理',
  '任务被取消': '任务被取消'
}

const TERMINAL_TASK_STATUSES = new Set(['failed', 'cancelled', 'stopped'])
const ERROR_SESSION_PHASES = new Set(['failed', 'closed', 'automation_failed'])

/** 任务级 errorMessage 是否应在 UI 展示（排除 running 时残留的历史错误） */
export const shouldShowTaskErrorMessage = (task) => {
  if (!task?.errorMessage) return false
  const status = String(task.status || '').toLowerCase()
  const phase = String(task.sessionPhase || '').toLowerCase()
  if (TERMINAL_TASK_STATUSES.has(status)) return true
  if (ERROR_SESSION_PHASES.has(phase)) return true
  return false
}

/** 会话级 errorMessage 是否应作为错误展示（正常进度文案不算错误） */
export const shouldShowSessionErrorMessage = (session, task) => {
  if (!session?.errorMessage) return false
  const phase = String(session.phase || task?.sessionPhase || '').toLowerCase()
  if (ERROR_SESSION_PHASES.has(phase)) return true
  const trimmed = String(session.errorMessage).trim()
  if (TASK_EVENT_MESSAGE_MAP[trimmed]) return false
  return false
}

/**
 * 修复 UTF-8 中文被误按 Latin-1 解码后的乱码（如 ç"¨æˆ· → 用户）。
 */
export const repairUtf8Mojibake = (text) => {
  if (!text || typeof text !== 'string') return text
  if (!/[\u00C0-\u00FF]/.test(text)) return text
  try {
    const bytes = Uint8Array.from(text, (char) => char.charCodeAt(0) & 0xff)
    const repaired = new TextDecoder('utf-8').decode(bytes)
    if (/[\u4e00-\u9fff]/.test(repaired)) return repaired
  } catch {
    /* ignore */
  }
  return text
}

export const getSessionPhaseText = (phase) => {
  if (!phase) return '-'
  const key = String(phase).toLowerCase()
  if (SESSION_PHASE_MAP[key]) return SESSION_PHASE_MAP[key].text
  if (key.startsWith('paused')) return '已暂停'
  return phase
}

export const getSessionPhaseType = (phase) => {
  if (!phase) return 'info'
  const key = String(phase).toLowerCase()
  if (SESSION_PHASE_MAP[key]) return SESSION_PHASE_MAP[key].type
  if (key.startsWith('paused')) return 'warning'
  return 'info'
}

export const getSessionPhaseHint = (phase, message = '') => {
  const normalizedMessage = message ? getTaskEventMessageText(message) : ''
  const key = phase ? String(phase).toLowerCase() : ''
  const base = SESSION_PHASE_HINT_MAP[key] || ''
  if (!normalizedMessage) return base
  if (/首帧|FIRST_FRAME/i.test(normalizedMessage)) {
    return `LAN 首帧失败：${normalizedMessage}`
  }
  if (/DataChannel|SmartGlass|input|输入/i.test(normalizedMessage)) {
    return `输入通道失败：${normalizedMessage}`
  }
  return base ? `${base} 当前信息：${normalizedMessage}` : normalizedMessage
}

export const getGameAccountRunStatusText = (status) => {
  if (!status) return '-'
  return GAME_ACCOUNT_RUN_STATUS_MAP[status]?.text || status
}

export const getGameAccountRunStatusType = (status) => {
  if (!status) return 'info'
  return GAME_ACCOUNT_RUN_STATUS_MAP[status]?.type || 'info'
}

export const getGameAccountPhaseText = (phase) => {
  if (!phase) return '-'
  return GAME_ACCOUNT_PHASE_MAP[phase] || phase
}

export const getProvisioningPhaseText = (phase) => {
  if (!phase) return ''
  const key = String(phase).toLowerCase()
  return PROVISIONING_PHASE_MAP[key] || phase
}

export const getTaskEventScopeText = (scope) => {
  if (!scope) return '任务'
  const key = String(scope).toLowerCase()
  return TASK_EVENT_SCOPE_MAP[key] || scope
}

/** 时间线事件关联的游戏账号展示名（gamertag）；无映射时回退短 ID */
export const resolveTaskEventAccountLabel = (ev, nameMap = {}) => {
  const id = ev?.gameAccountId
  if (!id) return ''
  const mapped = nameMap[id]
  if (mapped) return mapped
  const shortId = String(id)
  return shortId.length > 10 ? `${shortId.slice(0, 8)}…` : shortId
}

export const getTaskEventPhaseText = (phase, scope) => {
  if (!phase) return ''
  const key = String(phase).toUpperCase()
  if (TASK_STEP_PHASE_MAP[key]) return TASK_STEP_PHASE_MAP[key]
  const lowerKey = String(phase).toLowerCase()
  if (scope === 'module') {
    return PROVISIONING_PHASE_MAP[lowerKey] || phase
  }
  if (SESSION_PHASE_MAP[lowerKey]) return SESSION_PHASE_MAP[lowerKey].text
  if (lowerKey.startsWith('paused')) return '已暂停'
  return PROVISIONING_PHASE_MAP[lowerKey] || phase
}

/** 解析 task_event.payload 中的 hostAttempts 摘要（STEP2 多主机轮询） */
export const formatHostAttemptsSummary = (payloadRaw) => {
  if (!payloadRaw) return ''
  try {
    const payload = typeof payloadRaw === 'string' ? JSON.parse(payloadRaw) : payloadRaw
    const attempts = payload?.hostAttempts
    if (!Array.isArray(attempts) || !attempts.length) return ''
    const parts = attempts.map((item) => {
      const name = item.name || item.serverId || `#${item.index || '?'}`
      const statusText = HOST_ATTEMPT_STATUS_MAP[item.status] || item.status || ''
      return statusText ? `${name}(${statusText})` : name
    })
    return `主机尝试：${parts.join(' → ')}`
  } catch {
    return ''
  }
}

export const getTaskEventMessageText = (message) => {
  if (!message) return ''
  const trimmed = repairUtf8Mojibake(String(message).trim())
  if (TASK_EVENT_MESSAGE_MAP[trimmed]) return TASK_EVENT_MESSAGE_MAP[trimmed]
  const inputModeMatch = trimmed.match(/^Input mode:\s*(\w+)$/i)
  if (inputModeMatch) {
    const mode = inputModeMatch[1].toLowerCase()
    const modeText = mode === 'physical' ? '实体手柄' : mode === 'virtual' ? '虚拟手柄' : mode
    return `输入模式：${modeText}`
  }
  const inputReconnectFail = trimmed.match(/^Input channel reconnect failed:\s*(.+)$/i)
  if (inputReconnectFail) {
    return `Input 通道重连失败：${inputReconnectFail[1]}`
  }
  return message
}