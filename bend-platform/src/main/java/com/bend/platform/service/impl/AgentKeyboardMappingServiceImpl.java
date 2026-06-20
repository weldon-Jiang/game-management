package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bend.platform.dto.AgentKeyboardMappingChartResponse;
import com.bend.platform.dto.AgentKeyboardMappingResponse;
import com.bend.platform.dto.UpdateAgentKeyboardMappingRequest;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.service.AgentKeyboardMappingService;
import com.bend.platform.util.AgentKeyboardMappingDefaults;
import com.bend.platform.util.DataSecurityUtil;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent 键盘映射读写：NULL 使用默认模板，非 NULL 为全量自定义 JSON。
 */
@Service
@RequiredArgsConstructor
public class AgentKeyboardMappingServiceImpl implements AgentKeyboardMappingService {

    private final AgentInstanceMapper agentInstanceMapper;
    private final DataSecurityUtil dataSecurityUtil;

    @Override
    public AgentKeyboardMappingResponse getMappingForAgent(String agentId) {
        AgentInstance instance = requireAccessibleAgent(agentId);
        return buildResponse(instance.getKeyboardMappingJson());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public AgentKeyboardMappingResponse updateMapping(
            String agentId,
            UpdateAgentKeyboardMappingRequest request) {
        AgentInstance instance = requireAccessibleAgent(agentId);
        boolean reset = request != null && Boolean.TRUE.equals(request.getResetToDefault());
        Map<String, String> bindings = request != null ? request.getBindings() : null;

        String storedJson;
        if (reset) {
            storedJson = null;
        } else if (bindings == null || bindings.isEmpty()) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "请提供 bindings 或设置 resetToDefault=true");
        } else {
            Map<String, String> normalized = AgentKeyboardMappingDefaults.validateFullBindings(bindings);
            storedJson = AgentKeyboardMappingDefaults.toJson(normalized);
        }

        LambdaUpdateWrapper<AgentInstance> wrapper = new LambdaUpdateWrapper<>();
        wrapper.eq(AgentInstance::getAgentId, agentId)
                .set(AgentInstance::getKeyboardMappingJson, storedJson);
        agentInstanceMapper.update(null, wrapper);

        instance.setKeyboardMappingJson(storedJson);
        return buildResponse(storedJson);
    }

    @Override
    public Map<String, String> getEffectiveBindingsForAgent(String agentId) {
        AgentInstance instance = agentInstanceMapper.selectByAgentId(agentId);
        if (instance == null) {
            return AgentKeyboardMappingDefaults.copyAgentFullDefault();
        }
        return AgentKeyboardMappingDefaults.resolveFullEffectiveBindings(instance.getKeyboardMappingJson());
    }

    @Override
    public AgentKeyboardMappingResponse buildDefaultResponse() {
        return buildResponse(null);
    }

    @Override
    public AgentKeyboardMappingChartResponse getChartForAgent(String agentId) {
        AgentInstance instance = requireAccessibleAgent(agentId);
        return AgentKeyboardMappingDefaults.buildChartResponse(instance.getKeyboardMappingJson());
    }

    private AgentKeyboardMappingResponse buildResponse(String keyboardMappingJson) {
        boolean usingDefault = keyboardMappingJson == null || keyboardMappingJson.isBlank();
        Map<String, String> effectiveFull = AgentKeyboardMappingDefaults.resolveFullEffectiveBindings(keyboardMappingJson);
        Map<String, String> custom = usingDefault ? null : new LinkedHashMap<>(effectiveFull);

        List<AgentKeyboardMappingResponse.BindingRow> rows = new ArrayList<>();
        for (AgentKeyboardMappingDefaults.BindingSlotRow slot
                : AgentKeyboardMappingDefaults.buildBindingSlotRows(effectiveFull)) {
            rows.add(AgentKeyboardMappingResponse.BindingRow.builder()
                    .bindingKey(slot.bindingKey())
                    .key(slot.key())
                    .action(slot.action())
                    .label(slot.label())
                    .defaultKey(slot.defaultKey())
                    .category(slot.category())
                    .groupLabel(slot.groupLabel())
                    .build());
        }

        AgentKeyboardMappingChartResponse chart =
                AgentKeyboardMappingDefaults.buildChartResponse(keyboardMappingJson);

        return AgentKeyboardMappingResponse.builder()
                .usingDefault(usingDefault)
                .customBindings(custom)
                .effectiveBindings(effectiveFull)
                .rows(rows)
                .groups(chart.getGroups())
                .keyCaps(chart.getKeyCaps())
                .debugHotkeys(chart.getDebugHotkeys())
                .build();
    }

    private AgentInstance requireAccessibleAgent(String agentId) {
        AgentInstance instance = agentInstanceMapper.selectByAgentId(agentId);
        if (instance == null) {
            throw new BusinessException(ResultCode.AgentInstance.NOT_FOUND);
        }
        if (!UserContext.isPlatformAdmin()) {
            dataSecurityUtil.validateMerchantAccess(instance.getMerchantId(), "AgentInstance");
        }
        return instance;
    }
}
