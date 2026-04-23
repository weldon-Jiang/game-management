package com.bend.platform.exception;

import com.bend.platform.dto.ApiResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import java.util.stream.Collectors;

/**
 * 全局异常处理器
 * 统一处理所有Controller层抛出的异常，返回标准化的API响应
 *
 * 处理范围：
 * - BusinessException: 业务异常，返回业务错误码
 * - MethodArgumentNotValidException: 参数校验异常
 * - ConstraintViolationException: 约束违反异常
 * - BindException: 参数绑定异常
 * - MissingServletRequestParameterException: 缺少请求参数
 * - MethodArgumentTypeMismatchException: 参数类型不匹配
 * - NoHandlerFoundException: 请求路径不存在
 * - HttpRequestMethodNotSupportedException: 请求方法不支持
 * - Exception: 其他未知异常
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 处理业务异常
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException e, HttpServletRequest request) {
        log.warn("业务异常 - URI: {}, Code: {}, Message: {}", request.getRequestURI(), e.getCode(), e.getMessage());

        int code = e.getCode();
        ApiResponse<Void> response = ApiResponse.error(code, e.getMessage());

        if (code == ResultCode.Auth.TOKEN_INVALID.getCode()
                || code == ResultCode.Auth.TOKEN_EXPIRED.getCode()
                || code == ResultCode.Auth.TOKEN_MISSING.getCode()) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(response);
        }

        return ResponseEntity.ok(response);
    }

    /**
     * 处理参数校验异常（@Valid校验失败）
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMethodArgumentNotValid(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        log.warn("参数校验失败: {}", message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理约束违反异常（@Validated校验失败）
     */
    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleConstraintViolation(ConstraintViolationException e) {
        String message = e.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.joining(", "));
        log.warn("约束校验失败: {}", message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理参数绑定异常
     */
    @ExceptionHandler(BindException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleBindException(BindException e) {
        String message = e.getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining(", "));
        log.warn("参数绑定失败: {}", message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理缺少请求参数异常
     */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMissingServletRequestParameter(MissingServletRequestParameterException e) {
        String message = String.format("缺少必要参数: %s", e.getParameterName());
        log.warn(message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理参数类型不匹配异常
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMethodArgumentTypeMismatch(MethodArgumentTypeMismatchException e) {
        String message = String.format("参数 %s 类型错误，期望类型: %s", e.getName(), e.getRequiredType() != null ? e.getRequiredType().getSimpleName() : "未知");
        log.warn(message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理缺少请求头异常
     */
    @ExceptionHandler(MissingRequestHeaderException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleMissingRequestHeader(MissingRequestHeaderException e) {
        String message = String.format("缺少请求头: %s", e.getHeaderName());
        log.warn(message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理请求路径不存在异常
     */
    @ExceptionHandler(NoHandlerFoundException.class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public ApiResponse<Void> handleNoHandlerFoundException(NoHandlerFoundException e) {
        String message = String.format("请求路径不存在: %s %s", e.getHttpMethod(), e.getRequestURL());
        log.warn(message);
        return ApiResponse.error(ResultCode.System.DATA_NOT_FOUND.getCode(), message);
    }

    /**
     * 处理请求方法不支持异常
     */
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    @ResponseStatus(HttpStatus.METHOD_NOT_ALLOWED)
    public ApiResponse<Void> handleHttpRequestMethodNotSupported(HttpRequestMethodNotSupportedException e) {
        String message = String.format("请求方法不支持: %s", e.getMethod());
        log.warn(message);
        return ApiResponse.error(ResultCode.System.PARAM_INVALID.getCode(), message);
    }

    /**
     * 处理其他未知异常
     */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public ApiResponse<Void> handleException(Exception e, HttpServletRequest request) {
        log.error("系统异常 - URI: {}, Error: {}", request.getRequestURI(), e.getMessage(), e);
        return ApiResponse.error(ResultCode.System.UNKNOWN_ERROR.getCode(), "系统繁忙，请稍后重试");
    }
}