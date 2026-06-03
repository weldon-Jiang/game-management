package com.bend.platform.config;

import jakarta.websocket.HandshakeResponse;
import jakarta.websocket.server.HandshakeRequest;
import jakarta.websocket.server.ServerEndpointConfig;

import java.lang.reflect.Constructor;
import java.util.List;
import java.util.Map;

public class AgentWebSocketConfigurator extends ServerEndpointConfig.Configurator {

    public static final String HANDSHAKE_HEADERS_KEY = "handshakeHeaders";

    @Override
    public void modifyHandshake(ServerEndpointConfig sec, HandshakeRequest request, HandshakeResponse response) {
        sec.getUserProperties().put(HANDSHAKE_HEADERS_KEY, request.getHeaders());
    }

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
