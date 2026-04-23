package com.bend.platform.annotation;

import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface Idempotent {

    String key() default "";

    int expireSeconds() default 60;

    String message() default "请求正在处理中，请勿重复提交";
}