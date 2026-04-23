package com.bend.platform.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 统一API响应封装类
 *
 * <p>所有Controller接口统一返回此格式，确保前端处理一致性。
 *
 * <p>响应格式：
 * <pre>
 * {
 *   "code": 200,          // 状态码：0或200表示成功，其他表示错误
 *   "message": "success", // 提示信息
 *   "data": { ... }       // 数据实体
 * }
 * </pre>
 *
 * <p>状态码约定：
 * <ul>
 *   <li>200 - 成功</li>
 *   <li>400 - 请求参数错误</li>
 *   <li>401 - 未认证（Token缺失或无效）</li>
 *   <li>403 - 无权限访问</li>
 *   <li>404 - 资源不存在</li>
 *   <li>500 - 服务器内部错误</li>
 * </ul>
 *
 * @param <T> data数据类型
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ApiResponse<T> {

    /** 状态码：0或200表示成功 */
    private int code;

    /** 提示信息 */
    private String message;

    /** 数据实体 */
    private T data;

    /**
     * 成功响应（默认消息"success"）
     *
     * @param data 返回数据
     * @param <T> 数据类型
     * @return 成功响应
     */
    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .code(200)
                .message("success")
                .data(data)
                .build();
    }

    /**
     * 成功响应（自定义消息）
     *
     * @param message 自定义提示信息
     * @param data 返回数据
     * @param <T> 数据类型
     * @return 成功响应
     */
    public static <T> ApiResponse<T> success(String message, T data) {
        return ApiResponse.<T>builder()
                .code(200)
                .message(message)
                .data(data)
                .build();
    }

    /**
     * 错误响应
     *
     * @param code 错误状态码
     * @param message 错误信息
     * @param <T> 数据类型
     * @return 错误响应
     */
    public static <T> ApiResponse<T> error(int code, String message) {
        return ApiResponse.<T>builder()
                .code(code)
                .message(message)
                .data(null)
                .build();
    }

    /**
     * 错误响应（默认500状态码）
     *
     * @param message 错误信息
     * @param <T> 数据类型
     * @return 错误响应
     */
    public static <T> ApiResponse<T> error(String message) {
        return error(500, message);
    }
}