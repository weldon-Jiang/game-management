package com.bend.platform.util;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.security.MessageDigest;
import java.util.Enumeration;

/**
 * 机器指纹工具
 *
 * <p>用于 license 绑定。取值优先级:
 * <ol>
 *   <li>env {@code MACHINE_ID}（可选覆盖，测试/调试用）</li>
 *   <li>Windows 注册表 {@code MachineGuid}（生产推荐：唯一稳定不可拷贝）</li>
 *   <li>退回：首个非回环网卡 MAC + 主机名 + OS 的 SHA-256（非 Windows，如 Linux 容器）</li>
 * </ol>
 *
 * <p>关键：激活脚本（activate-tenant.ps1）与本工具必须取到同一值，
 * 否则 license 首次校验即 MACHINE_MISMATCH。两边统一用 Windows MachineGuid。
 * 与 Agent 端 machine_identity.py 不要求算法一致 —— license 首次校验时绑定,
 * 后续只比对一致性,因此分控服务端与 Agent 各自稳定即可。
 */
@Slf4j
@Component
public class MachineFingerprintUtil {

    @Value("${machine.id:${MACHINE_ID:}}")
    private String machineId;

    public String getFingerprint() {
        // 1. env 覆盖（测试/调试）
        if (machineId != null && !machineId.isBlank()) {
            return machineId.trim();
        }
        // 2. Windows 注册表 MachineGuid（生产推荐）
        String guid = readWindowsMachineGuid();
        if (guid != null && !guid.isBlank()) {
            return guid;
        }
        // 3. 退回：MAC + 主机名 + OS 哈希（非 Windows，如本地 Linux 容器）
        return legacyMacHash();
    }

    /**
     * 读 Windows 注册表 HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid。
     * 用 reg query（Windows 自带，不依赖 wmic）。非 Windows 或读失败返回 null。
     */
    private String readWindowsMachineGuid() {
        if (!System.getProperty("os.name", "").toLowerCase().contains("win")) {
            return null;
        }
        try {
            Process p = new ProcessBuilder("reg",
                    "query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid")
                    .redirectErrorStream(true).start();
            try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream()))) {
                String line;
                while ((line = r.readLine()) != null) {
                    int idx = line.indexOf("MachineGuid");
                    if (idx >= 0) {
                        // 形如: "    MachineGuid    REG_SZ    xxxxxxxx-xxxx-..."
                        String[] parts = line.split("\\s+");
                        for (int i = parts.length - 1; i >= 0; i--) {
                            if (!parts[i].isEmpty() && !parts[i].equals("REG_SZ")
                                    && !parts[i].equalsIgnoreCase("MachineGuid")) {
                                return parts[i].trim();
                            }
                        }
                    }
                }
            }
            p.waitFor();
        } catch (Exception e) {
            log.warn("读 Windows MachineGuid 失败，退回 MAC 算法: {}", e.getMessage());
        }
        return null;
    }

    private String legacyMacHash() {
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
