package com.bend.platform.service;

import com.bend.platform.dto.AgentKeyboardMappingChartResponse;
import com.bend.platform.dto.AgentKeyboardMappingResponse;
import com.bend.platform.dto.UpdateAgentKeyboardMappingRequest;

import java.util.Map;

/**
 * Agent 键盘→手柄映射：默认模板、按实例存储与下发。
 */
public interface AgentKeyboardMappingService {

    AgentKeyboardMappingResponse getMappingForAgent(String agentId);

    AgentKeyboardMappingResponse updateMapping(String agentId, UpdateAgentKeyboardMappingRequest request);

    /** Agent 心跳/注册下发用的生效映射 */
    Map<String, String> getEffectiveBindingsForAgent(String agentId);

    AgentKeyboardMappingResponse buildDefaultResponse();

    /** F8 人工接管键盘映射图（含 Agent 扩展键位，只读） */
    AgentKeyboardMappingChartResponse getChartForAgent(String agentId);
}
