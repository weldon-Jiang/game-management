package com.bend.platform.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.listener.PatternTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.listener.adapter.MessageListenerAdapter;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

/**
 * Redis配置类
 *
 * 功能说明：
 * - 配置Redis连接工厂
 * - 配置RedisTemplate用于对象存储
 * - 配置StringRedisTemplate用于字符串操作
 * - 配置Redis消息监听容器用于发布订阅
 *
 * 应用场景：
 * - 分布式锁
 * - 任务消息队列
 * - 会话缓存
 * - Agent在线状态缓存
 */
@Configuration
public class RedisConfig {

    /**
     * 配置RedisTemplate
     *
     * 功能说明：
     * - 使用JSON序列化器存储对象
     * - 使用String序列化器存储键
     */
    @Bean
    public RedisTemplate<String, Object> redisTemplate(RedisConnectionFactory connectionFactory) {
        RedisTemplate<String, Object> template = new RedisTemplate<>();
        template.setConnectionFactory(connectionFactory);

        // 使用String序列化器存储键
        template.setKeySerializer(new StringRedisSerializer());
        template.setHashKeySerializer(new StringRedisSerializer());

        // 使用JSON序列化器存储值
        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer();
        template.setValueSerializer(jsonSerializer);
        template.setHashValueSerializer(jsonSerializer);

        template.afterPropertiesSet();
        return template;
    }

    /**
     * 配置StringRedisTemplate
     *
     * 功能说明：
     * - 用于简单的字符串操作
     * - 如计数器、缓存键值等
     */
    @Bean
    public StringRedisTemplate stringRedisTemplate(RedisConnectionFactory connectionFactory) {
        return new StringRedisTemplate(connectionFactory);
    }

    /**
     * 配置Redis消息监听容器
     *
     * 功能说明：
     * - 用于订阅Redis频道消息
     * - 支持模式匹配订阅
     *
     * 应用场景：
     * - 分布式任务分发
     * - 跨实例消息通知
     */
    @Bean
    public RedisMessageListenerContainer redisMessageListenerContainer(
            RedisConnectionFactory connectionFactory,
            MessageListenerAdapter taskMessageListener,
            MessageListenerAdapter agentMessageListener) {

        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);

        // 订阅任务消息频道
        container.addMessageListener(taskMessageListener, new PatternTopic("task:*"));
        // 订阅Agent消息频道
        container.addMessageListener(agentMessageListener, new PatternTopic("agent:*"));

        return container;
    }

    /**
     * 任务消息监听适配器
     */
    @Bean
    public MessageListenerAdapter taskMessageListener(RedisMessageSubscriber subscriber) {
        return new MessageListenerAdapter(subscriber, "handleTaskMessage");
    }

    /**
     * Agent消息监听适配器
     */
    @Bean
    public MessageListenerAdapter agentMessageListener(RedisMessageSubscriber subscriber) {
        return new MessageListenerAdapter(subscriber, "handleAgentMessage");
    }
}
