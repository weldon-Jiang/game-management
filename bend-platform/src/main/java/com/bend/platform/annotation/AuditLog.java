package com.bend.platform.annotation;

import java.lang.annotation.*;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface AuditLog {

    String value() default "";

    String action() default "";

    String module() default "";

    String description() default "";
}