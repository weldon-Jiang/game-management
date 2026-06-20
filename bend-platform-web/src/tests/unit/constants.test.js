import { describe, it, expect } from 'vitest'
import {
  TASK_STATUS_MAP,
  TASK_TYPE_MAP,
  GAME_ACCOUNT_STATUS_MAP,
  AGENT_STATUS_MAP,
  getTaskStatusText,
  getTaskStatusType,
  getEffectiveTaskStatus,
  getSessionPhaseText,
  getTaskTypeText,
  getAgentStatusText,
  getAgentStatusType,
  getRoleType,
  resolveTaskEventAccountLabel
} from '@/utils/constants'

describe('constants.js - 状态映射常量', () => {
  describe('TASK_STATUS_MAP', () => {
    it('应该包含所有任务状态', () => {
      expect(TASK_STATUS_MAP).toHaveProperty('pending')
      expect(TASK_STATUS_MAP).toHaveProperty('running')
      expect(TASK_STATUS_MAP).toHaveProperty('paused')
      expect(TASK_STATUS_MAP).toHaveProperty('completed')
      expect(TASK_STATUS_MAP).toHaveProperty('failed')
      expect(TASK_STATUS_MAP).toHaveProperty('cancelled')
      expect(TASK_STATUS_MAP).toHaveProperty('stopped')
    })

    it('每个状态应该有 text 和 type 属性', () => {
      Object.values(TASK_STATUS_MAP).forEach(status => {
        expect(status).toHaveProperty('text')
        expect(status).toHaveProperty('type')
      })
    })

    it('状态类型值应该是有效的 Element Plus 类型', () => {
      const validTypes = ['warning', 'primary', 'success', 'danger', 'info']
      Object.values(TASK_STATUS_MAP).forEach(status => {
        expect(validTypes).toContain(status.type)
      })
    })
  })

  describe('TASK_TYPE_MAP', () => {
    it('应该包含所有任务类型', () => {
      expect(TASK_TYPE_MAP).toHaveProperty('template_match')
      expect(TASK_TYPE_MAP).toHaveProperty('input_sequence')
      expect(TASK_TYPE_MAP).toHaveProperty('scene_detection')
      expect(TASK_TYPE_MAP).toHaveProperty('account_switch')
      expect(TASK_TYPE_MAP).toHaveProperty('stream_control')
      expect(TASK_TYPE_MAP).toHaveProperty('custom')
    })

    it('每个类型应该有文本描述', () => {
      Object.values(TASK_TYPE_MAP).forEach(type => {
        expect(typeof type).toBe('string')
        expect(type.length).toBeGreaterThan(0)
      })
    })
  })

  describe('GAME_ACCOUNT_STATUS_MAP', () => {
    it('应该包含所有游戏账号状态', () => {
      expect(GAME_ACCOUNT_STATUS_MAP).toHaveProperty('active')
      expect(GAME_ACCOUNT_STATUS_MAP).toHaveProperty('locked')
      expect(GAME_ACCOUNT_STATUS_MAP).toHaveProperty('disabled')
    })
  })

  describe('AGENT_STATUS_MAP', () => {
    it('应该包含所有 Agent 状态', () => {
      expect(AGENT_STATUS_MAP).toHaveProperty('online')
      expect(AGENT_STATUS_MAP).toHaveProperty('offline')
      expect(AGENT_STATUS_MAP).toHaveProperty('reconnecting')
      expect(AGENT_STATUS_MAP).toHaveProperty('uninstalled')
    })
  })
})

describe('constants.js - 工具函数', () => {
  describe('getTaskStatusText', () => {
    it('应该返回正确的状态文本', () => {
      expect(getTaskStatusText('pending')).toBe('待执行')
      expect(getTaskStatusText('running')).toBe('执行中')
      expect(getTaskStatusText('paused')).toBe('已暂停')
      expect(getTaskStatusText('completed')).toBe('已完成')
      expect(getTaskStatusText('failed')).toBe('已失败')
      expect(getTaskStatusText('cancelled')).toBe('已取消')
      expect(getTaskStatusText('stopped')).toBe('已停止')
    })

    it('对于未知状态应该返回原值', () => {
      expect(getTaskStatusText('unknown')).toBe('unknown')
      expect(getTaskStatusText('invalid')).toBe('invalid')
    })

    it('对于 null 或 undefined 应该返回 "-"', () => {
      expect(getTaskStatusText(null)).toBe('-')
      expect(getTaskStatusText(undefined)).toBe('-')
    })
  })

  describe('getTaskStatusType', () => {
    it('应该返回正确的状态类型', () => {
      expect(getTaskStatusType('pending')).toBe('warning')
      expect(getTaskStatusType('running')).toBe('primary')
      expect(getTaskStatusType('completed')).toBe('success')
      expect(getTaskStatusType('failed')).toBe('danger')
      expect(getTaskStatusType('cancelled')).toBe('info')
    })

    it('对于未知状态应该返回 "info"', () => {
      expect(getTaskStatusType('unknown')).toBe('info')
    })

    it('对于 null 或 undefined 应该返回 "info"', () => {
      expect(getTaskStatusType(null)).toBe('info')
      expect(getTaskStatusType(undefined)).toBe('info')
    })
  })

  describe('getEffectiveTaskStatus', () => {
    it('活跃会话应将残留 completed 修正为 running', () => {
      expect(getEffectiveTaskStatus({
        status: 'completed',
        sessionPhase: 'opening',
        sessionId: 'sess-1',
        streamingAccountId: 'sa-1'
      })).toBe('running')
    })

    it('会话已关闭时应保留 completed', () => {
      expect(getEffectiveTaskStatus({
        status: 'completed',
        sessionPhase: 'closed',
        sessionId: 'sess-1'
      })).toBe('completed')
    })

    it('暂停会话应展示 paused', () => {
      expect(getEffectiveTaskStatus({
        status: 'running',
        sessionPhase: 'paused_immediate',
        sessionId: 'sess-1'
      })).toBe('paused')
    })

    it('input_reconnecting 子阶段仍应展示 running', () => {
      expect(getEffectiveTaskStatus({
        status: 'running',
        sessionPhase: 'input_reconnecting',
        sessionId: 'sess-1'
      })).toBe('running')
    })
  })

  describe('getSessionPhaseText', () => {
    it('应识别 input 通道子阶段', () => {
      expect(getSessionPhaseText('input_reconnecting')).toBe('输入通道重连中')
      expect(getSessionPhaseText('input_restored')).toBe('输入通道已恢复')
    })
  })

  describe('getTaskTypeText', () => {
    it('应该返回正确的类型文本', () => {
      expect(getTaskTypeText('template_match')).toBe('模板匹配')
      expect(getTaskTypeText('input_sequence')).toBe('输入序列')
      expect(getTaskTypeText('scene_detection')).toBe('场景检测')
    })

    it('对于未知类型应该返回原值', () => {
      expect(getTaskTypeText('unknown')).toBe('unknown')
    })

    it('对于 null 或 undefined 应该返回 "-"', () => {
      expect(getTaskTypeText(null)).toBe('-')
      expect(getTaskTypeText(undefined)).toBe('-')
    })
  })

  describe('getAgentStatusText', () => {
    it('应该返回正确的 Agent 状态文本', () => {
      expect(getAgentStatusText('online')).toBe('在线')
      expect(getAgentStatusText('offline')).toBe('离线')
      expect(getAgentStatusText('reconnecting')).toBe('重连中')
      expect(getAgentStatusText('uninstalled')).toBe('已卸载')
    })

    it('对于未知状态应该返回原值', () => {
      expect(getAgentStatusText('unknown')).toBe('unknown')
    })
  })

  describe('getAgentStatusType', () => {
    it('应该返回正确的 Agent 状态类型', () => {
      expect(getAgentStatusType('online')).toBe('success')
      expect(getAgentStatusType('offline')).toBe('info')
      expect(getAgentStatusType('reconnecting')).toBe('warning')
      expect(getAgentStatusType('uninstalled')).toBe('danger')
    })

    it('对于未知状态应该返回 "info"', () => {
      expect(getAgentStatusType('unknown')).toBe('info')
    })

    it('对于 null 或 undefined 应该返回 "info"', () => {
      expect(getAgentStatusType(null)).toBe('info')
      expect(getAgentStatusType(undefined)).toBe('info')
    })
  })

  describe('getRoleType', () => {
    it('应该返回正确的角色类型', () => {
      expect(getRoleType('admin')).toBe('danger')
      expect(getRoleType('operator')).toBe('warning')
      expect(getRoleType('viewer')).toBe('info')
    })

    it('对于未知角色应该返回 "info"', () => {
      expect(getRoleType('unknown')).toBe('info')
    })

    it('对于 null 或 undefined 应该返回 "info"', () => {
      expect(getRoleType(null)).toBe('info')
      expect(getRoleType(undefined)).toBe('info')
    })
  })

  describe('resolveTaskEventAccountLabel', () => {
    it('无 gameAccountId 时返回空字符串', () => {
      expect(resolveTaskEventAccountLabel({})).toBe('')
      expect(resolveTaskEventAccountLabel(null)).toBe('')
    })

    it('优先使用 nameMap 中的 gamertag', () => {
      const ev = { gameAccountId: 'abc123' }
      expect(resolveTaskEventAccountLabel(ev, { abc123: 'MyGamer' })).toBe('MyGamer')
    })

    it('无映射时回退短 ID', () => {
      const ev = { gameAccountId: '0123456789abcdef' }
      expect(resolveTaskEventAccountLabel(ev)).toBe('01234567…')
    })
  })
})
