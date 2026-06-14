package com.bend.platform.util;

import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Agent 键盘→手柄默认映射模板与校验。
 *
 * <p>键名为 pygame {@code key.name}（小写）；值为 Agent {@code KeyAction} 枚举名。
 * 与 bend-agent {@code KeyboardMapper.DEFAULT_BINDINGS} 保持一致。
 */
public final class AgentKeyboardMappingDefaults {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 平台默认：WASD 方向 + J/B/X/Y 面键 */
    public static final Map<String, String> DEFAULT_BINDINGS = Map.ofEntries(
            Map.entry("w", "MOVE_UP"),
            Map.entry("s", "MOVE_DOWN"),
            Map.entry("a", "MOVE_LEFT"),
            Map.entry("d", "MOVE_RIGHT"),
            Map.entry("j", "TAP_A"),
            Map.entry("b", "TAP_B"),
            Map.entry("x", "TAP_X"),
            Map.entry("y", "TAP_Y"),
            Map.entry("return", "TAP_START"),
            Map.entry("escape", "TAP_SELECT"),
            Map.entry("q", "TAP_L1"),
            Map.entry("e", "TAP_R1")
    );

    private static final Set<String> ALLOWED_ACTIONS = Set.of(
            "TAP_A", "TAP_B", "TAP_X", "TAP_Y",
            "TAP_START", "TAP_SELECT", "TAP_L1", "TAP_R1",
            "MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT"
    );

    /** UI 展示顺序与中文标签 */
    public static final List<ActionMeta> ACTION_METAS = List.of(
            new ActionMeta("MOVE_UP", "方向上", "w"),
            new ActionMeta("MOVE_DOWN", "方向下", "s"),
            new ActionMeta("MOVE_LEFT", "方向左", "a"),
            new ActionMeta("MOVE_RIGHT", "方向右", "d"),
            new ActionMeta("TAP_A", "确认(A)", "j"),
            new ActionMeta("TAP_B", "返回(B)", "b"),
            new ActionMeta("TAP_X", "功能(X)", "x"),
            new ActionMeta("TAP_Y", "功能(Y)", "y"),
            new ActionMeta("TAP_START", "Start", "return"),
            new ActionMeta("TAP_SELECT", "View/Select", "escape"),
            new ActionMeta("TAP_L1", "LB(L1)", "q"),
            new ActionMeta("TAP_R1", "RB(R1)", "e")
    );

    private AgentKeyboardMappingDefaults() {
    }

    /**
     * 解析 DB 中 JSON；空则返回默认模板副本。
     */
    public static Map<String, String> resolveEffectiveBindings(String keyboardMappingJson) {
        if (keyboardMappingJson == null || keyboardMappingJson.isBlank()) {
            return copyDefault();
        }
        try {
            Map<String, String> parsed = MAPPER.readValue(
                    keyboardMappingJson, new TypeReference<LinkedHashMap<String, String>>() {});
            validateCustomBindings(parsed);
            return parsed;
        } catch (BusinessException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "键盘映射 JSON 格式无效");
        }
    }

    /**
     * 校验并规范化自定义映射（全量 12 项，动作与键一一对应）。
     */
    public static Map<String, String> validateCustomBindings(Map<String, String> bindings) {
        if (bindings == null || bindings.isEmpty()) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "键盘映射不能为空");
        }
        Map<String, String> normalized = new LinkedHashMap<>();
        Map<String, String> actionToKey = new LinkedHashMap<>();
        Set<String> usedKeys = new LinkedHashSet<>();

        for (Map.Entry<String, String> entry : bindings.entrySet()) {
            String key = normalizeKey(entry.getKey());
            String action = normalizeAction(entry.getValue());
            if (!ALLOWED_ACTIONS.contains(action)) {
                throw new BusinessException(ResultCode.System.PARAM_INVALID, "不支持的动作: " + action);
            }
            if (!usedKeys.add(key)) {
                throw new BusinessException(ResultCode.System.PARAM_INVALID, "重复绑定按键: " + key);
            }
            if (actionToKey.containsKey(action)) {
                throw new BusinessException(ResultCode.System.PARAM_INVALID, "重复绑定动作: " + action);
            }
            actionToKey.put(action, key);
            normalized.put(key, action);
        }

        for (ActionMeta meta : ACTION_METAS) {
            if (!actionToKey.containsKey(meta.action())) {
                throw new BusinessException(
                        ResultCode.System.PARAM_INVALID,
                        "缺少动作映射: " + meta.label() + " (" + meta.action() + ")"
                );
            }
        }
        return normalized;
    }

    public static Map<String, String> copyDefault() {
        return new LinkedHashMap<>(DEFAULT_BINDINGS);
    }

    public static String toJson(Map<String, String> bindings) {
        try {
            return MAPPER.writeValueAsString(bindings);
        } catch (Exception ex) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "键盘映射序列化失败");
        }
    }

    private static String normalizeKey(String key) {
        if (key == null || key.isBlank()) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "按键名不能为空");
        }
        return key.trim().toLowerCase();
    }

    private static String normalizeAction(String action) {
        if (action == null || action.isBlank()) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "动作不能为空");
        }
        return action.trim().toUpperCase();
    }

    public record ActionMeta(String action, String label, String defaultKey) {
    }
}
