package com.bend.platform.dto;

import lombok.Data;

import java.util.Map;

/**
 * 更新 Agent 键盘映射请求。
 *
 * <p>{@code resetToDefault=true} 或 {@code bindings=null} 表示恢复默认模板。
 */
@Data
public class UpdateAgentKeyboardMappingRequest {

    /** true 时忽略 bindings，清空 DB 自定义配置 */
    private Boolean resetToDefault;

    /** 全量自定义映射（pygame 键名 → KeyAction） */
    private Map<String, String> bindings;
}
