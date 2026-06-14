package com.bend.platform.dto;

import lombok.Builder;
import lombok.Data;

import java.util.List;
import java.util.Map;

/**
 * Agent 键盘映射查询/保存响应。
 */
@Data
@Builder
public class AgentKeyboardMappingResponse {

    /** 是否使用平台默认模板（DB 字段为 NULL） */
    private boolean usingDefault;

    /** DB 中存储的自定义映射；未配置时为 null */
    private Map<String, String> customBindings;

    /** 当前生效映射（默认或自定义） */
    private Map<String, String> effectiveBindings;

    /** 按动作列出的绑定行（含默认键参考） */
    private List<BindingRow> rows;

    @Data
    @Builder
    public static class BindingRow {
        private String action;
        private String label;
        private String defaultKey;
        private String key;
    }
}
