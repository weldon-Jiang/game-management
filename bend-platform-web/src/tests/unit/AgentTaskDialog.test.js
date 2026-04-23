import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import AgentTaskDialog from '@/views/agent/AgentTaskDialog.vue'
import { mockAgent, mockTaskList } from '../mocks/data.js'

vi.mock('@/api', () => ({
  taskApi: {
    list: vi.fn()
  }
}))

const { taskApi } = await import('@/api')

describe('AgentTaskDialog.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  const createWrapper = (props = {}) => {
    return mount(AgentTaskDialog, {
      props: {
        visible: true,
        agent: mockAgent,
        ...props
      },
      global: {
        stubs: {
          'el-dialog': true,
          'el-descriptions': true,
          'el-descriptions-item': true,
          'el-tabs': true,
          'el-tab-pane': true,
          'el-table': true,
          'el-table-column': true,
          'el-tag': true,
          'el-button': true
        }
      }
    })
  }

  describe('组件渲染', () => {
    it('当 visible 为 true 时应该显示', () => {
      const wrapper = createWrapper({ visible: true })
      expect(wrapper.isVisible()).toBe(true)
    })

    it('当 visible 为 false 时应该隐藏', () => {
      const wrapper = createWrapper({ visible: false })
      expect(wrapper.isVisible()).toBe(false)
    })

    it('应该接收并显示 agent 信息', () => {
      const wrapper = createWrapper()
      expect(wrapper.props('agent')).toEqual(mockAgent)
    })
  })

  describe('任务加载逻辑', () => {
    it('当 agent 存在时应该调用 taskApi.list', async () => {
      taskApi.list.mockResolvedValue({
        code: 200,
        data: {
          records: mockTaskList
        }
      })

      const wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      expect(taskApi.list).toHaveBeenCalledWith({
        agentId: mockAgent.agentId,
        pageSize: 100
      })
    })

    it('应该正确分离运行中的任务和所有任务', async () => {
      taskApi.list.mockResolvedValue({
        code: 200,
        data: {
          records: mockTaskList
        }
      })

      const wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.runningTasks).toHaveLength(1)
      expect(wrapper.vm.runningTasks[0].status).toBe('running')
      expect(wrapper.vm.allTasks).toHaveLength(2)
    })

    it('API 错误时应该处理异常', async () => {
      taskApi.list.mockRejectedValue(new Error('Network error'))

      const wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      expect(console.error).toHaveBeenCalled()
    })
  })

  describe('刷新功能', () => {
    it('handleRefresh 应该重新加载任务', async () => {
      taskApi.list.mockResolvedValue({
        code: 200,
        data: { records: [] }
      })

      const wrapper = createWrapper()
      await wrapper.vm.handleRefresh()

      expect(taskApi.list).toHaveBeenCalledTimes(2)
    })
  })

  describe('日期格式化', () => {
    it('formatDate 应该正确格式化日期', () => {
      const wrapper = createWrapper()
      const dateStr = '2024-01-15T10:30:00'
      const formatted = wrapper.vm.formatDate(dateStr)

      expect(formatted).toContain('2024')
      expect(formatted).toContain('01')
      expect(formatted).toContain('15')
    })

    it('formatDate 应该处理空值', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.formatDate(null)).toBe('-')
      expect(wrapper.vm.formatDate('')).toBe('-')
      expect(wrapper.vm.formatDate(undefined)).toBe('-')
    })
  })

  describe('弹窗关闭', () => {
    it('关闭弹窗时应该触发 update:visible 事件', async () => {
      const wrapper = createWrapper()
      wrapper.vm.dialogVisible = false
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:visible')).toBeTruthy()
      expect(wrapper.emitted('update:visible')[0]).toEqual([false])
    })
  })

  describe('Tab 切换', () => {
    it('默认应该显示 running tab', () => {
      const wrapper = createWrapper()
      expect(wrapper.vm.activeTab).toBe('running')
    })

    it('应该支持切换到 all tab', async () => {
      const wrapper = createWrapper()
      wrapper.vm.activeTab = 'all'
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.activeTab).toBe('all')
    })
  })
})
