package com.bend.platform.util;

import org.springframework.stereotype.Component;

import java.net.InetAddress;
import java.net.NetworkInterface;
import java.security.MessageDigest;
import java.util.Enumeration;

/**
 * 机器指纹工具
 *
 * <p>用于 license 绑定。基于首个非回环网卡的 MAC + 主机名 + OS 生成稳定哈希。
 * 与 Agent 端 machine_identity.py 不要求算法一致 —— license 首次校验时绑定,
 * 后续只比对一致性,因此分控服务端与 Agent 各自稳定即可。
 */
@Component
public class MachineFingerprintUtil {

    public String getFingerprint() {
        try {
            String mac = getFirstMac();
            String host = InetAddress.getLocalHost().getHostName();
            String os = System.getProperty("os.name");
            String raw = (mac != null ? mac : "nomac") + "|" + host + "|" + os;
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(raw.getBytes("UTF-8"));
            return bytesToHex(hash);
        } catch (Exception e) {
            return "unknown-" + System.currentTimeMillis();
        }
    }

    private String getFirstMac() {
        try {
            Enumeration<NetworkInterface> nics = NetworkInterface.getNetworkInterfaces();
            while (nics.hasMoreElements()) {
                NetworkInterface nic = nics.nextElement();
                if (nic.isLoopback() || !nic.isUp()) {
                    continue;
                }
                byte[] mac = nic.getHardwareAddress();
                if (mac != null && mac.length > 0) {
                    StringBuilder sb = new StringBuilder();
                    for (byte b : mac) {
                        sb.append(String.format("%02X", b));
                    }
                    return sb.toString();
                }
            }
        } catch (Exception ignored) {
        }
        return null;
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder();
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
