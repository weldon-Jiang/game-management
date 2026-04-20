package com.bend.platform.config;

import javax.websocket.server.ServerEndpointConfig;

public class AgentWebSocketConfigurator extends ServerEndpointConfig.Configurator {

    @Override
    public <T> T getEndpointInstance(Class<T> endpointClass) throws InstantiationException {
        try {
            return endpointClass.newInstance();
        } catch (InstantiationException e) {
            throw e;
        } catch (IllegalAccessException e) {
            throw new InstantiationException("Cannot access endpoint: " + e.getMessage());
        }
    }
}
