package com.bend.platform.service;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.service.impl.AgentInstanceServiceImpl;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * AgentInstanceService 单元测试
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

    @Test
    void testCreate() {
        when(agentInstanceMapper.insert(any(AgentInstance.class))).thenReturn(1);

        AgentInstance created = agentInstanceService.create(testAgent);

        assertNotNull(created);
        verify(agentInstanceMapper, times(1)).insert(any(AgentInstance.class));
    }

    @Test
    void testFindByAgentId() {
        when(agentInstanceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(testAgent);

        AgentInstance found = agentInstanceService.findByAgentId("agent-abc-123");

        assertNotNull(found);
        assertEquals("agent-abc-123", found.getAgentId());
    }

    @Test
    void testFindByAgentIdNotFound() {
        when(agentInstanceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(null);

        AgentInstance found = agentInstanceService.findByAgentId("non-existent");

        assertNull(found);
    }

    @Test
    void testFindAll() {
        AgentInstance agent1 = new AgentInstance();
        agent1.setAgentId("agent-001");
        agent1.setStatus("online");

        AgentInstance agent2 = new AgentInstance();
        agent2.setAgentId("agent-002");
        agent2.setStatus("online");

        when(agentInstanceMapper.selectList(any(LambdaQueryWrapper.class))).thenReturn(Arrays.asList(agent1, agent2));

        List<AgentInstance> allAgents = agentInstanceService.findAll();

        assertEquals(2, allAgents.size());
    }

    @Test
    void testUpdateStatus() {
        when(agentInstanceMapper.selectById("agent-001")).thenReturn(testAgent);
        when(agentInstanceMapper.updateById(any(AgentInstance.class))).thenReturn(1);

        agentInstanceService.updateStatus("agent-001", "offline");

        verify(agentInstanceMapper, times(1)).updateById(any(AgentInstance.class));
    }

    @Test
    void testUpdateHeartbeat() {
        when(agentInstanceMapper.selectById("agent-001")).thenReturn(testAgent);
        when(agentInstanceMapper.updateById(any(AgentInstance.class))).thenReturn(1);

        agentInstanceService.updateHeartbeat("agent-001");

        verify(agentInstanceMapper, times(1)).updateById(any(AgentInstance.class));
    }

    @Test
    void testDelete() {
        when(agentInstanceMapper.selectById("agent-001")).thenReturn(testAgent);
        when(agentInstanceMapper.updateById(any(AgentInstance.class))).thenReturn(1);

        agentInstanceService.delete("agent-001");

        verify(agentInstanceMapper, times(1)).updateById(any(AgentInstance.class));
    }

    @Test
    void testValidateCredentials() {
        when(agentInstanceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(testAgent);

        boolean valid = agentInstanceService.validateCredentials("agent-abc-123", "secret-xyz");

        assertTrue(valid);
    }

    @Test
    void testValidateCredentialsInvalid() {
        when(agentInstanceMapper.selectOne(any(LambdaQueryWrapper.class))).thenReturn(null);

        boolean valid = agentInstanceService.validateCredentials("invalid", "invalid");

        assertFalse(valid);
    }
}
