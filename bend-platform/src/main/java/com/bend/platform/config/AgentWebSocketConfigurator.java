package com.bend.platform.config;

import jakarta.websocket.server.ServerEndpointConfig;
import java.lang.reflect.Constructor;

public class AgentWebSocketConfigurator extends ServerEndpointConfig.Configurator {

    @Override
    public <T> T getEndpointInstance(Class<T> endpointClass) throws InstantiationException {
        try {
            Constructor<T> constructor = endpointClass.getDeclaredConstructor();
            constructor.setAccessible(true);
            return constructor.newInstance();
        } catch (ReflectiveOperationException e) {
            throw new InstantiationException("Cannot create endpoint instance: " + e.getMessage());
        }
    }
}
