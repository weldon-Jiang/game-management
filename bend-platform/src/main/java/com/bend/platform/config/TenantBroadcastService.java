package com.bend.platform.config;

import com.bend.platform.service.LicenseClientService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Conditional;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.UnknownHostException;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * 分控局域网广播服务(仅 tenant 模式装配)
 *
 * <p>每 5 秒向局域网 UDP 广播自身存在,供:
 * <ul>
 *   <li>新分控安装时检测"同局域网是否已有分控",避免重复安装</li>
 *   <li>Agent 启动时自动发现分控 IP,填入 backend.base_url</li>
 * </ul>
 *
 * <p>协议: UDP 47820, payload = "BENDTENANT|ip|port|licenseKey前缀|商户名"
 */
@Slf4j
@Component
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class TenantBroadcastService {

    public static final int BROADCAST_PORT = 47820;
    public static final String PROTOCOL_HEADER = "BENDTENANT";

    @Value("${server.port:8061}")
    private int backendPort;

    @Value("${license.gateway-port:8060}")
    private int gatewayPort;

    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;

    private final LicenseClientService licenseClientService;

    private ScheduledExecutorService executor;
    private volatile boolean running = true;

    @PostConstruct
    public void start() {
        executor = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "tenant-broadcast");
            t.setDaemon(true);
            return t;
        });
        executor.scheduleAtFixedRate(this::broadcast, 5, 5, TimeUnit.SECONDS);
        log.info("分控局域网广播服务已启动,端口 {}", BROADCAST_PORT);
    }

    @PreDestroy
    public void stop() {
        running = false;
        if (executor != null) {
            executor.shutdownNow();
        }
    }

    private void broadcast() {
        if (!running) return;
        String localIp = getLocalIp();
        if (localIp == null) {
            log.debug("无法获取本机局域网IP,跳过广播");
            return;
        }
        String merchantName = "";
        try {
            LicenseClientService.LicenseStatus st = licenseClientService.getStatus();
            // merchantName 不在 status 里,这里用 licenseKey 前缀作为标识即可
        } catch (Exception ignored) {
        }
        String keyPrefix = (licenseKey != null && licenseKey.length() > 12) ? licenseKey.substring(0, 12) : (licenseKey == null ? "" : licenseKey);
        String payload = String.join("|", PROTOCOL_HEADER, localIp, String.valueOf(gatewayPort), keyPrefix, merchantName);

        try (DatagramSocket socket = new DatagramSocket()) {
            socket.setBroadcast(true);
            byte[] data = payload.getBytes(StandardCharsets.UTF_8);
            InetAddress broadcastAddr = InetAddress.getByName("255.255.255.255");
            DatagramPacket packet = new DatagramPacket(data, data.length, broadcastAddr, BROADCAST_PORT);
            socket.send(packet);
            log.debug("广播分控存在: {}", payload);
        } catch (Exception e) {
            log.debug("广播失败: {}", e.getMessage());
        }
    }

    /** 获取本机首个非回环、非虚拟的 IPv4 地址 */
    private String getLocalIp() {
        try {
            Enumeration<NetworkInterface> nics = NetworkInterface.getNetworkInterfaces();
            while (nics.hasMoreElements()) {
                NetworkInterface nic = nics.nextElement();
                if (nic.isLoopback() || !nic.isUp()) continue;
                Enumeration<java.net.InetAddress> addrs = nic.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    java.net.InetAddress addr = addrs.nextElement();
                    if (addr.isLoopbackAddress()) continue;
                    if (addr instanceof java.net.Inet4Address) {
                        String ip = addr.getHostAddress();
                        if (ip != null && !ip.startsWith("169.254")) {
                            return ip;
                        }
                    }
                }
            }
            return InetAddress.getLocalHost().getHostAddress();
        } catch (Exception e) {
            try {
                return InetAddress.getLocalHost().getHostAddress();
            } catch (UnknownHostException ex) {
                return null;
            }
        }
    }
}
