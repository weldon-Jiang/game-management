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

export const VIP_TYPE_MAP = {
  monthly: '月卡',
  quarterly: '季卡',
  yearly: '年卡'
}

export const VIP_TYPE_LIST = [
  { value: 'monthly', label: '月卡' },
  { value: 'quarterly', label: '季卡' },
  { value: 'yearly', label: '年卡' }
]

export const VIP_DEFAULT_DURATION = {
  monthly: 30,
  quarterly: 90,
  yearly: 365
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
  busy: '忙碌',
  error: '异常',
  uninstalled: '已卸载'
}

export const AGENT_STATUS_TYPE_MAP = {
  online: 'success',
  offline: 'info',
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
  completed: { text: '已完成', type: 'success' },
  failed: { text: '已失败', type: 'danger' },
  cancelled: { text: '已取消', type: 'info' }
}

export const TASK_TYPE_MAP = {
  template_match: '模板匹配',
  input_sequence: '输入序列',
  scene_detection: '场景检测',
  account_switch: '账号切换',
  stream_control: '串流控制',
  custom: '自定义'
}

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
 * 获取VIP类型中文名称
 */
export const getVipTypeText = (vipType) => {
  if (!vipType) return '-'
  if (vipType === 'platform_admin') return '平台管理员'
  return VIP_TYPE_MAP[vipType] || vipType
}

/**
 * 获取VIP类型的默认时长(天)
 */
export const getVipDefaultDuration = (vipType) => {
  return VIP_DEFAULT_DURATION[vipType] || null
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

export const getTaskStatusText = (status) => {
  if (!status) return '-'
  return TASK_STATUS_MAP[status]?.text || status
}

export const getTaskStatusType = (status) => {
  if (!status) return 'info'
  return TASK_STATUS_MAP[status]?.type || 'info'
}

export const getTaskTypeText = (type) => {
  if (!type) return '-'
  return TASK_TYPE_MAP[type] || type
}