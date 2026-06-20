package com.bend.platform.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * Agent 键盘映射查询/保存响应（含全量映射图数据）。
 */
@Data
@Builder
public class AgentKeyboardMappingResponse {

    /** 是否使用平台默认模板（DB 字段为 NULL） */
    private boolean usingDefault;

    /** DB 中存储的自定义映射；未配置时为 null */
    private Map<String, String> customBindings;

    /** 当前生效全量映射（含扩展键） */
    private Map<String, String> effectiveBindings;

    /** 按动作列出的绑定行（含默认键参考，可编辑 12 项） */
    private List<BindingRow> rows;

    /** 全量映射可视化：按类别分组 */
    private List<AgentKeyboardMappingChartResponse.ChartGroup> groups;

    /** 键盘可视化键帽标注 */
    private List<AgentKeyboardMappingChartResponse.KeyCap> keyCaps;

    /** F8 调试热键（非手柄映射） */
    private List<AgentKeyboardMappingChartResponse.DebugHotkey> debugHotkeys;

    @Data
    @Builder
    public static class BindingRow {
        /** 槽位 ID（默认模板键名，用于分组展示） */
        private String bindingKey;
        /** 当前绑定的 pygame 键名 */
        private String key;
        /** KeyAction 枚举名 */
        private String action;
        /** 手柄目标展示文案 */
        private String label;
        /** 默认键参考 */
        private String defaultKey;
        /** 分组 category */
        private String category;
        /** 分组标题 */
        private String groupLabel;
    }
}
