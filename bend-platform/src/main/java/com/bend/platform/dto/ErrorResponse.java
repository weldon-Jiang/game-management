package com.bend.platform.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 统一错误响应格式
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ErrorResponse {

    /**
     * 错误时间
     */
    private LocalDateTime timestamp;

    /**
     * 错误码
     */
    private int code;

    /**
     * 错误类型
     */
    private String error;

    /**
     * 错误消息
     */
    private String message;

    /**
     * 请求路径
     */
    private String path;

    /**
     * 详细错误信息（用于开发环境）
     */
    private String detail;

    /**
     * 字段验证错误
     * key: 字段名
     * value: 错误消息
     */
    private Map<String, String> validationErrors;

    /**
     * 创建简单错误响应
     */
    public static ErrorResponse of(int code, String error, String message, String path) {
        return ErrorResponse.builder()
                .timestamp(LocalDateTime.now())
                .code(code)
                .error(error)
                .message(message)
                .path(path)
                .build();
    }

    /**
     * 创建带详细信息的错误响应
     */
    public static ErrorResponse of(int code, String error, String message, String path, String detail) {
        return ErrorResponse.builder()
                .timestamp(LocalDateTime.now())
                .code(code)
                .error(error)
                .message(message)
                .path(path)
                .detail(detail)
                .build();
    }

    /**
     * 创建字段验证错误响应
     */
    public static ErrorResponse validationError(String path, Map<String, String> validationErrors) {
        return ErrorResponse.builder()
                .timestamp(LocalDateTime.now())
                .code(400)
                .error("Validation Error")
                .message("请求参数验证失败")
                .path(path)
                .validationErrors(validationErrors)
                .build();
    }
}
