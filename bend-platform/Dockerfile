# ============================================
# Bend Platform 后端 Dockerfile
# Spring Boot 应用
# ============================================

# 使用 Spring Boot 官方构建镜像
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# 复制 pom.xml 与 ProGuard 配置
COPY pom.xml .
COPY proguard.conf .

# 使用阿里云镜像源
RUN mkdir -p /root/.m2 && echo '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 http://maven.apache.org/xsd/settings-1.0.0.xsd"><mirrors><mirror><id>aliyunmaven</id><mirrorOf>central</mirrorOf><url>https://maven.aliyun.com/repository/public</url></mirror></mirrors></settings>' > /root/.m2/settings.xml

# 删除旧的 Maven 缓存
RUN rm -rf /root/.m2/repository/org/projectlombok 2>/dev/null || true

# 下载所有依赖（包括Lombok）
RUN mvn dependency:resolve -DskipTests

# 检查 Lombok 是否正确下载
RUN ls -la /root/.m2/repository/org/projectlombok/lombok || echo "Lombok not found"

# 复制源代码
COPY src ./src

# 编译并打包
RUN mvn clean package -DskipTests -Dmaven.test.skip=true

# 运行阶段
FROM eclipse-temurin:17-jre

WORKDIR /app

COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8061

ENTRYPOINT ["java", "-jar", "app.jar"]