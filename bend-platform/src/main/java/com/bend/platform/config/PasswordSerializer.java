package com.bend.platform.config;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.JsonSerializer;
import com.fasterxml.jackson.databind.SerializerProvider;

import java.io.IOException;

/**
 * 密码序列化器
 * 返回时将密码替换为星号，保护敏感信息
 */
public class PasswordSerializer extends JsonSerializer<String> {

    @Override
    public void serialize(String value, JsonGenerator gen, SerializerProvider serializers) throws IOException {
        if (value != null && !value.isEmpty()) {
            gen.writeString("******");
        } else {
            gen.writeNull();
        }
    }
}
