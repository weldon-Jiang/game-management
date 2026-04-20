package com.bend.platform.exception;

/**
 * 业务异常类
 * 用于封装业务逻辑中出现的异常，统一异常处理
 *
 * 使用示例：
 * <pre>
 * // 抛出系统异常
 * throw new BusinessException(ResultCode.System.DATA_NOT_FOUND);
 *
 * // 抛出带自定义消息的异常
 * throw new BusinessException(ResultCode.Merchant.NOT_FOUND, "商户ID不存在");
 *
 * // 抛出带参数的异常
 * throw new BusinessException(ResultCode.Auth.USERNAME_PASSWORD_ERROR);
 * </pre>
 */
public class BusinessException extends RuntimeException {

    private final int code;
    private final String message;

    public BusinessException(ResultCode resultCode) {
        super(resultCode.getMessage());
        this.code = resultCode.getCode();
        this.message = resultCode.getMessage();
    }

    public BusinessException(ResultCode resultCode, String customMessage) {
        super(customMessage);
        this.code = resultCode.getCode();
        this.message = customMessage;
    }

    public BusinessException(ResultCode resultCode, Throwable cause) {
        super(resultCode.getMessage(), cause);
        this.code = resultCode.getCode();
        this.message = resultCode.getMessage();
    }

    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
        this.message = message;
    }

    public BusinessException(int code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
        this.message = message;
    }

    public int getCode() {
        return code;
    }

    @Override
    public String getMessage() {
        return message;
    }

    @Override
    public String toString() {
        return String.format("BusinessException{code=%d, message='%s'}", code, message);
    }
}