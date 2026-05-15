# ============================================
# Bend Platform 后端 Dockerfile
# Spring Boot 应用
# ============================================

# 第一阶段：构建应用
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /app

# 复制 pom.xml 和依赖
COPY pom.xml .
COPY src ./src

# 设置镜像源加速构建
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 创建 Maven 配置文件，使用阿里云镜像源
RUN mkdir -p /root/.m2 && echo '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd"><mirrors><mirror><id>aliyunmaven</id><mirrorOf>central</mirrorOf><url>https://maven.aliyun.com/repository/public</url></mirror></mirrors></settings>' > /root/.m2/settings.xml

# 构建应用（跳过测试）
RUN mvn clean package -DskipTests

# ============================================
# 第二阶段：运行应用
FROM eclipse-temurin:21-jre

# 设置时区
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
RUN echo "Asia/Shanghai" > /etc/timezone

# 创建非root用户
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# 复制构建产物
COPY --from=builder /app/target/*.jar app.jar

# 复制配置文件
COPY --from=builder /app/src/main/resources ./resources

# 设置权限
RUN chown -R appuser:appgroup /app

USER appuser

# 暴露端口
EXPOSE 8061

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8061/actuator/health || exit 1

# 启动应用
ENTRYPOINT ["java", "-jar", "-Xms512m", "-Xmx1024m", "app.jar"]
