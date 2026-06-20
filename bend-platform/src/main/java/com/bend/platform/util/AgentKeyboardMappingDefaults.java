package com.bend.platform.util;

import com.bend.platform.dto.AgentKeyboardMappingChartResponse;
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
 * 与 bend-agent {@code keyboard_mapping_defaults.DEFAULT_KEYBOARD_BINDINGS} 保持一致。
 */
public final class AgentKeyboardMappingDefaults {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    /** 平台可编辑的 12 项（WASD + 面键 + Start/View + LB/RB） */
    public static final Map<String, String> DEFAULT_BINDINGS = Map.ofEntries(
            Map.entry("w", "MOVE_UP"),
            Map.entry("s", "MOVE_DOWN"),
            Map.entry("a", "MOVE_LEFT"),
            Map.entry("d", "MOVE_RIGHT"),
            Map.entry("k", "TAP_A"),
            Map.entry("l", "TAP_B"),
            Map.entry("j", "TAP_X"),
            Map.entry("i", "TAP_Y"),
            Map.entry("return", "TAP_START"),
            Map.entry("escape", "TAP_SELECT"),
            Map.entry("q", "TAP_L1"),
            Map.entry("e", "TAP_R1")
    );

    /**
     * Agent 端扩展键（方向键、扳机、右摇杆等）；每手柄功能仅一个键（LT=Shift，Xbox=Ctrl）。
     */
    public static final Map<String, String> AGENT_EXTENDED_BINDINGS = Map.ofEntries(
            Map.entry("up", "MOVE_UP"),
            Map.entry("down", "MOVE_DOWN"),
            Map.entry("left", "MOVE_LEFT"),
            Map.entry("right", "MOVE_RIGHT"),
            Map.entry("left ctrl", "TAP_NEXUS"),
            Map.entry("left shift", "HOLD_L2"),
            Map.entry("space", "HOLD_R2"),
            Map.entry("c", "TAP_L3"),
            Map.entry("v", "TAP_R3"),
            Map.entry("t", "LOOK_UP"),
            Map.entry("g", "LOOK_DOWN"),
            Map.entry("f", "LOOK_LEFT"),
            Map.entry("h", "LOOK_RIGHT")
    );

    private static final Set<String> ALLOWED_ACTIONS = Set.of(
            "TAP_A", "TAP_B", "TAP_X", "TAP_Y",
            "TAP_START", "TAP_SELECT", "TAP_L1", "TAP_R1",
            "TAP_NEXUS", "TAP_L3", "TAP_R3",
            "HOLD_L2", "HOLD_R2",
            "MOVE_UP", "MOVE_DOWN", "MOVE_LEFT", "MOVE_RIGHT",
            "LOOK_UP", "LOOK_DOWN", "LOOK_LEFT", "LOOK_RIGHT"
    );

    /** 全量默认模板中每种动作至少出现一次（MOVE_* 允许左摇杆+十字键各一） */
    private static final Set<String> REQUIRED_ACTIONS = Set.copyOf(copyAgentFullDefault().values());

    /** UI 展示顺序与中文标签（平台 12 项编辑表） */
    public static final List<ActionMeta> ACTION_METAS = List.of(
            new ActionMeta("MOVE_UP", "方向上", "w"),
            new ActionMeta("MOVE_DOWN", "方向下", "s"),
            new ActionMeta("MOVE_LEFT", "方向左", "a"),
            new ActionMeta("MOVE_RIGHT", "方向右", "d"),
            new ActionMeta("TAP_A", "确认(A)", "k"),
            new ActionMeta("TAP_B", "返回(B)", "l"),
            new ActionMeta("TAP_X", "功能(X)", "j"),
            new ActionMeta("TAP_Y", "功能(Y)", "i"),
            new ActionMeta("TAP_START", "Start", "return"),
            new ActionMeta("TAP_SELECT", "View/Select", "escape"),
            new ActionMeta("TAP_L1", "LB(L1)", "q"),
            new ActionMeta("TAP_R1", "RB(R1)", "e")
    );

    private static final List<KeyGroupDef> KEY_GROUP_DEFS = List.of(
            new KeyGroupDef("left_stick", "左摇杆 (WASD)", true, List.of("w", "a", "s", "d")),
            new KeyGroupDef("dpad", "十字键 (方向键)", true, List.of("up", "down", "left", "right")),
            new KeyGroupDef("face", "面键 (Y/X/A/B)", true, List.of("i", "j", "k", "l")),
            new KeyGroupDef("shoulder", "肩键 (LB/RB)", true, List.of("q", "e")),
            new KeyGroupDef("trigger", "扳机 (LT/RT)", true, List.of("left shift", "space")),
            new KeyGroupDef("right_stick", "右摇杆 (T/F/G/H)", true, List.of("t", "f", "g", "h")),
            new KeyGroupDef("stick_click", "摇杆按下 (L3/R3)", true, List.of("c", "v")),
            new KeyGroupDef("system", "系统键", true, List.of("return", "escape", "left ctrl"))
    );

    private static final List<AgentKeyboardMappingChartResponse.DebugHotkey> DEBUG_HOTKEYS = List.of(
            AgentKeyboardMappingChartResponse.DebugHotkey.builder().key("F8").description("人工接管 开/关").build(),
            AgentKeyboardMappingChartResponse.DebugHotkey.builder().key("F9").description("保存调试截图").build(),
            AgentKeyboardMappingChartResponse.DebugHotkey.builder().key("F10").description("显示快捷键帮助").build()
    );

    private AgentKeyboardMappingDefaults() {
    }

    /**
     * Agent 实际生效映射：DB 存全量 JSON；旧版仅 12 项时与扩展键合并。
     */
    public static Map<String, String> resolveFullEffectiveBindings(String keyboardMappingJson) {
        if (keyboardMappingJson == null || keyboardMappingJson.isBlank()) {
            return copyAgentFullDefault();
        }
        try {
            Map<String, String> parsed = MAPPER.readValue(
                    keyboardMappingJson, new TypeReference<LinkedHashMap<String, String>>() {});
            if (isLegacyPartialBindings(parsed)) {
                Map<String, String> merged = copyAgentFullDefault();
                merged.putAll(parsed);
                return enforceOneToOneBindings(merged);
            }
            return enforceOneToOneBindings(parsed);
        } catch (Exception ex) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "键盘映射 JSON 格式无效");
        }
    }

    /** DB 中缺少任一扩展键时视为旧版 12 项自定义 */
    private static boolean isLegacyPartialBindings(Map<String, String> parsed) {
        if (parsed == null || parsed.isEmpty()) {
            return true;
        }
        for (String extKey : AGENT_EXTENDED_BINDINGS.keySet()) {
            if (!parsed.containsKey(extKey)) {
                return true;
            }
        }
        return false;
    }

    public static Map<String, String> copyAgentFullDefault() {
        Map<String, String> merged = new LinkedHashMap<>(AGENT_EXTENDED_BINDINGS);
        merged.putAll(DEFAULT_BINDINGS);
        return merged;
    }

    /**
     * 构建 F8 键盘映射图：与编辑表槽位一致，键帽按实际绑定键高亮（非左右 Shift/Ctrl 重复）。
     */
    public static AgentKeyboardMappingChartResponse buildChartResponse(String keyboardMappingJson) {
        boolean usingDefault = keyboardMappingJson == null || keyboardMappingJson.isBlank();
        Map<String, String> effective = resolveFullEffectiveBindings(keyboardMappingJson);
        List<BindingSlotRow> slots = buildBindingSlotRows(effective);

        Map<String, AgentKeyboardMappingChartResponse.ChartGroup> groupMap = new LinkedHashMap<>();
        List<AgentKeyboardMappingChartResponse.KeyCap> keyCaps = new ArrayList<>();
        Set<String> seenCapKeys = new LinkedHashSet<>();

        for (BindingSlotRow slot : slots) {
            if (slot.key() == null || slot.key().isBlank() || slot.action() == null || slot.action().isBlank()) {
                continue;
            }
            AgentKeyboardMappingChartResponse.ChartGroup group = groupMap.computeIfAbsent(
                    slot.category(),
                    cat -> AgentKeyboardMappingChartResponse.ChartGroup.builder()
                            .category(slot.category())
                            .label(slot.groupLabel())
                            .customizable(true)
                            .items(new ArrayList<>())
                            .build()
            );
            group.getItems().add(AgentKeyboardMappingChartResponse.ChartItem.builder()
                    .keys(formatKeyDisplay(slot.key()))
                    .target(slot.label())
                    .build());
            if (seenCapKeys.add(slot.key())) {
                keyCaps.add(AgentKeyboardMappingChartResponse.KeyCap.builder()
                        .bindingKey(slot.key())
                        .displayKey(formatKeyDisplay(slot.key()))
                        .targetLabel(slot.label())
                        .category(slot.category())
                        .build());
            }
        }

        return AgentKeyboardMappingChartResponse.builder()
                .usingDefault(usingDefault)
                .groups(new ArrayList<>(groupMap.values()))
                .keyCaps(keyCaps)
                .debugHotkeys(DEBUG_HOTKEYS)
                .build();
    }

    private static String targetLabelForGroup(String category, String action) {
        return switch (category) {
            case "left_stick" -> switch (action) {
                case "MOVE_UP" -> "左摇杆 ↑";
                case "MOVE_DOWN" -> "左摇杆 ↓";
                case "MOVE_LEFT" -> "左摇杆 ←";
                case "MOVE_RIGHT" -> "左摇杆 →";
                default -> action;
            };
            case "dpad" -> switch (action) {
                case "MOVE_UP" -> "十字键 ↑";
                case "MOVE_DOWN" -> "十字键 ↓";
                case "MOVE_LEFT" -> "十字键 ←";
                case "MOVE_RIGHT" -> "十字键 →";
                default -> action;
            };
            case "face" -> switch (action) {
                case "TAP_Y" -> "Y";
                case "TAP_X" -> "X";
                case "TAP_A" -> "A";
                case "TAP_B" -> "B";
                default -> action;
            };
            case "shoulder" -> switch (action) {
                case "TAP_L1" -> "LB";
                case "TAP_R1" -> "RB";
                default -> action;
            };
            case "trigger" -> switch (action) {
                case "HOLD_L2" -> "LT 左扳机";
                case "HOLD_R2" -> "RT 右扳机";
                default -> action;
            };
            case "right_stick" -> switch (action) {
                case "LOOK_UP" -> "右摇杆 ↑";
                case "LOOK_DOWN" -> "右摇杆 ↓";
                case "LOOK_LEFT" -> "右摇杆 ←";
                case "LOOK_RIGHT" -> "右摇杆 →";
                default -> action;
            };
            case "stick_click" -> switch (action) {
                case "TAP_L3" -> "L3";
                case "TAP_R3" -> "R3";
                default -> action;
            };
            case "system" -> switch (action) {
                case "TAP_START" -> "Start";
                case "TAP_SELECT" -> "View";
                case "TAP_NEXUS" -> "Xbox 键";
                default -> action;
            };
            default -> action;
        };
    }

    static String formatKeyDisplay(String bindingKey) {
        if (bindingKey == null) {
            return "";
        }
        return switch (bindingKey) {
            case "left shift", "right shift" -> "Shift";
            case "left ctrl", "right ctrl" -> "Ctrl";
            case "return" -> "Enter";
            case "escape" -> "Esc";
            case "space" -> "Space";
            case "up" -> "↑";
            case "down" -> "↓";
            case "left" -> "←";
            case "right" -> "→";
            default -> bindingKey.length() == 1 ? bindingKey.toUpperCase() : bindingKey;
        };
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
     * 校验并规范化全量自定义映射：一键一动作；MOVE_* 允许 2 键（WASD + 方向键）。
     */
    public static Map<String, String> validateFullBindings(Map<String, String> bindings) {
        if (bindings == null || bindings.isEmpty()) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "键盘映射不能为空");
        }
        Map<String, String> normalized = new LinkedHashMap<>();
        Set<String> usedKeys = new LinkedHashSet<>();
        Set<String> actionsPresent = new LinkedHashSet<>();

        for (Map.Entry<String, String> entry : bindings.entrySet()) {
            String key = normalizeKey(entry.getKey());
            String action = normalizeAction(entry.getValue());
            if (!ALLOWED_ACTIONS.contains(action)) {
                throw new BusinessException(ResultCode.System.PARAM_INVALID, "不支持的动作: " + action);
            }
            if (!usedKeys.add(key)) {
                throw new BusinessException(ResultCode.System.PARAM_INVALID, "重复绑定按键: " + key);
            }
            actionsPresent.add(action);
            normalized.put(key, action);
        }

        assertSlotKeysUnique(normalized);
        assertOneToOneActionLimits(normalized);

        for (String required : REQUIRED_ACTIONS) {
            if (!actionsPresent.contains(required)) {
                throw new BusinessException(
                        ResultCode.System.PARAM_INVALID,
                        "缺少必需动作映射: " + required
                );
            }
        }
        return normalized;
    }

    /** 槽位展开后校验：同一键盘键不能绑多个手柄目标（如 J 同时绑 X 与十字键左）。 */
    private static void assertSlotKeysUnique(Map<String, String> normalized) {
        List<BindingSlotRow> slots = buildBindingSlotRows(normalized);
        Map<String, List<String>> keyToDescriptors = new LinkedHashMap<>();
        for (BindingSlotRow slot : slots) {
            if (slot.key() == null || slot.key().isBlank()) {
                continue;
            }
            String key = normalizeKey(slot.key());
            keyToDescriptors.computeIfAbsent(key, ignored -> new ArrayList<>())
                    .add(formatSlotDescriptor(slot));
        }
        List<String> conflictParts = new ArrayList<>();
        for (Map.Entry<String, List<String>> entry : keyToDescriptors.entrySet()) {
            if (entry.getValue().size() > 1) {
                conflictParts.add("「" + formatKeyDisplay(entry.getKey()) + "」→ "
                        + String.join("、", entry.getValue()));
            }
        }
        if (!conflictParts.isEmpty()) {
            throw new BusinessException(
                    ResultCode.System.PARAM_INVALID,
                    "键盘键被重复使用：" + String.join("；", conflictParts)
            );
        }
    }

    private static String formatSlotDescriptor(BindingSlotRow slot) {
        return slot.groupLabel() + " / " + slot.label();
    }

    /** MOVE_* 最多 2 键（左摇杆 + 十字键），其余动作仅允许 1 键。 */
    private static void assertOneToOneActionLimits(Map<String, String> normalized) {
        Map<String, Integer> counts = new LinkedHashMap<>();
        for (String action : normalized.values()) {
            counts.merge(action, 1, Integer::sum);
        }
        for (Map.Entry<String, Integer> entry : counts.entrySet()) {
            String action = entry.getKey();
            int maxAllowed = action.startsWith("MOVE_") ? 2 : 1;
            if (entry.getValue() > maxAllowed) {
                throw new BusinessException(
                        ResultCode.System.PARAM_INVALID,
                        "动作「" + action + "」只能绑定 " + maxAllowed + " 个键盘键"
                );
            }
        }
    }

    /** 读取 DB 时去掉重复动作键（保留先出现的 canonical 槽位键）。 */
    private static Map<String, String> enforceOneToOneBindings(Map<String, String> parsed) {
        Map<String, String> canonicalKeys = new LinkedHashMap<>();
        for (KeyGroupDef group : KEY_GROUP_DEFS) {
            for (String slotKey : group.keys()) {
                canonicalKeys.put(slotKey, copyAgentFullDefault().get(slotKey));
            }
        }
        Map<String, String> out = new LinkedHashMap<>();
        Map<String, Integer> actionCounts = new LinkedHashMap<>();

        for (String slotKey : canonicalKeys.keySet()) {
            if (parsed.containsKey(slotKey)) {
                String action = parsed.get(slotKey);
                int max = action != null && action.startsWith("MOVE_") ? 2 : 1;
                if (actionCounts.getOrDefault(action, 0) < max) {
                    out.put(slotKey, action);
                    actionCounts.merge(action, 1, Integer::sum);
                }
            }
        }
        for (Map.Entry<String, String> entry : parsed.entrySet()) {
            if (out.containsKey(entry.getKey())) {
                continue;
            }
            String action = entry.getValue();
            int max = action != null && action.startsWith("MOVE_") ? 2 : 1;
            if (actionCounts.getOrDefault(action, 0) >= max) {
                continue;
            }
            out.put(entry.getKey(), action);
            actionCounts.merge(action, 1, Integer::sum);
        }
        return out;
    }

    /**
     * 校验并规范化旧版 12 项自定义（动作与键一一对应，兼容历史数据）。
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

    /** 编辑表行：固定槽位 bindingKey + 当前键与动作 */
    public record BindingSlotRow(
            String bindingKey,
            String key,
            String action,
            String label,
            String defaultKey,
            String category,
            String groupLabel
    ) {
    }

    /**
     * 构建全量可编辑行（按分组槽位；支持键位 remap 后反查）。
     */
    public static List<BindingSlotRow> buildBindingSlotRows(Map<String, String> effectiveFull) {
        Map<String, String> defaults = copyAgentFullDefault();
        Map<String, String> effective = effectiveFull != null ? effectiveFull : defaults;
        List<BindingSlotRow> rows = new ArrayList<>();
        Set<String> usedKeys = new LinkedHashSet<>();

        for (KeyGroupDef group : KEY_GROUP_DEFS) {
            for (String slotKey : group.keys()) {
                String defaultAction = defaults.get(slotKey);
                String key = slotKey;
                String action = defaultAction != null ? defaultAction : "";

                if (effective.containsKey(slotKey)) {
                    key = slotKey;
                    action = effective.get(slotKey);
                    usedKeys.add(slotKey);
                } else if (defaultAction != null) {
                    for (Map.Entry<String, String> entry : effective.entrySet()) {
                        if (!usedKeys.contains(entry.getKey()) && defaultAction.equals(entry.getValue())) {
                            key = entry.getKey();
                            action = entry.getValue();
                            usedKeys.add(key);
                            break;
                        }
                    }
                }

                rows.add(new BindingSlotRow(
                        slotKey,
                        key,
                        action,
                        targetLabelForGroup(group.category(), action),
                        slotKey,
                        group.category(),
                        group.label()
                ));
            }
        }
        return rows;
    }

    private record KeyGroupDef(String category, String label, boolean customizable, List<String> keys) {
    }
}
