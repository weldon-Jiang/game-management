package com.bend.platform.service;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * AgentInstanceService 单元测试
 *
 * 测试场景：
 * - Agent注册
 * - Agent状态管理
 * - Agent心跳处理
 * - Agent查询和分页
 */
@ExtendWith(MockitoExtension.class)
class AgentInstanceServiceTest {

    @Mock
    private AgentInstanceMapper agentInstanceMapper;

    @InjectMocks
    private AgentInstanceServiceImpl agentInstanceService;

    private AgentInstance testAgent;

    @BeforeEach
    void setUp() {
        testAgent = new AgentInstance();
        testAgent.setId("agent-001");
        testAgent.setAgentId("agent-abc-123");
        testAgent.setAgentSecret("secret-xyz");
        testAgent.setMerchantId("merchant-001");
        testAgent.setHost("192.168.1.100");
        testAgent.setPort(8888);
        testAgent.setStatus("online");
        testAgent.setVersion("1.0.0");
    }

    /**
     * 测试：创建Agent实例
     */
    @Test
    void testCreate() {
        when(agentInstanceMapper.insert(any(AgentInstance.class))).thenReturn(1);

        AgentInstance created = agentInstanceService.create(testAgent);

        assertNotNull(created);
        verify(agentInstanceMapper, times(1)).insert(any(AgentInstance.class));
    }

    /**
     * 测试：根据AgentId查询
     */
    @Test
    void testFindByAgentId() {
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);

        AgentInstance found = agentInstanceService.findByAgentId("agent-abc-123");

        assertNotNull(found);
        assertEquals("agent-abc-123", found.getAgentId());
    }

    /**
     * 测试：根据AgentId查询不存在的Agent
     */
    @Test
    void testFindByAgentIdNotFound() {
        when(agentInstanceMapper.selectByAgentId("non-existent")).thenReturn(null);

        AgentInstance found = agentInstanceService.findByAgentId("non-existent");

        assertNull(found);
    }

    /**
     * 测试：查询所有在线Agent
     */
    @Test
    void testFindAllOnline() {
        AgentInstance agent1 = new AgentInstance();
        agent1.setAgentId("agent-001");
        agent1.setStatus("online");

        AgentInstance agent2 = new AgentInstance();
        agent2.setAgentId("agent-002");
        agent2.setStatus("online");

        when(agentInstanceMapper.selectOnlineAgents()).thenReturn(Arrays.asList(agent1, agent2));

        List<AgentInstance> onlineAgents = agentInstanceService.findAllOnline();

        assertEquals(2, onlineAgents.size());
    }

    /**
     * 测试：更新Agent状态为离线
     */
    @Test
    void testUpdateStatusToOffline() {
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);
        when(agentInstanceMapper.updateByAgentId(any(AgentInstance.class))).thenReturn(1);

        AgentInstance updated = agentInstanceService.updateStatusToOffline("agent-abc-123");

        assertEquals("offline", updated.getStatus());
        assertNotNull(updated.getLastOnlineTime());
    }

    /**
     * 测试：更新不存在的Agent状态
     */
    @Test
    void testUpdateStatusToOfflineNotFound() {
        when(agentInstanceMapper.selectByAgentId("non-existent")).thenReturn(null);

        AgentInstance updated = agentInstanceService.updateStatusToOffline("non-existent");

        assertNull(updated);
    }

    /**
     * 测试：Agent心跳更新
     */
    @Test
    void testUpdateHeartbeat() {
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);
        when(agentInstanceMapper.updateByAgentId(any(AgentInstance.class))).thenReturn(1);

        AgentInstance updated = agentInstanceService.updateHeartbeat("agent-abc-123");

        assertNotNull(updated);
        assertNotNull(updated.getLastHeartbeat());
    }

    /**
     * 测试：分页查询Agent
     */
    @Test
    void testFindPage() {
        com.baomidou.mybatisplus.core.metadata.IPage<AgentInstance> mockPage =
            new com.baomidou.mybatisplus.extension.plugins.pagination.Page<>(1, 10);
        mockPage.setRecords(Arrays.asList(testAgent));
        mockPage.setTotal(1);

        when(agentInstanceMapper.selectPage(any(), any())).thenReturn(mockPage);

        com.baomidou.mybatisplus.core.metadata.IPage<AgentInstance> result =
            agentInstanceService.findPage(1, 10, "online", null);

        assertNotNull(result);
        assertEquals(1, result.getTotal());
    }

    /**
     * 测试：删除Agent（软删除）
     */
    @Test
    void testDelete() {
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);
        when(agentInstanceMapper.updateByAgentId(any(AgentInstance.class))).thenReturn(1);

        agentInstanceService.delete("agent-abc-123");

        verify(agentInstanceMapper, times(1)).updateByAgentId(argThat(agent ->
            agent.getDeleted() != null && agent.getDeleted()
        ));
    }

    /**
     * 测试：检查Agent是否在线
     */
    @Test
    void testIsOnline() {
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);

        boolean isOnline = agentInstanceService.isOnline("agent-abc-123");

        assertTrue(isOnline);
    }

    /**
     * 测试：检查Agent是否离线
     */
    @Test
    void testIsOffline() {
        testAgent.setStatus("offline");
        when(agentInstanceMapper.selectByAgentId("agent-abc-123")).thenReturn(testAgent);

        boolean isOnline = agentInstanceService.isOnline("agent-abc-123");

        assertFalse(isOnline);
    }

    /**
     * 测试：检查不存在的Agent
     */
    @Test
    void testIsOnlineNotFound() {
        when(agentInstanceMapper.selectByAgentId("non-existent")).thenReturn(null);

        boolean isOnline = agentInstanceService.isOnline("non-existent");

        assertFalse(isOnline);
    }

    /**
     * 测试：获取Agent统计信息
     */
    @Test
    void testGetAgentStats() {
        when(agentInstanceMapper.selectCount(any())).thenReturn(10L);

        var stats = agentInstanceService.getAgentStats();

        assertNotNull(stats);
        assertTrue(stats.containsKey("total"));
        assertTrue(stats.containsKey("online"));
        assertTrue(stats.containsKey("offline"));
    }
}
