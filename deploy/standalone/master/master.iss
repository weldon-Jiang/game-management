; ================================================
; BendPlatform 总控安装器 (Inno Setup)
; ================================================
; 用途: 在公网服务器部署总控平台(backend + gateway + web + MySQL + Redis)
; 产物来源(打包前需放入 deploy/standalone/staging/master/):
;   backend.jar          <- mvn -f bend-platform/pom.xml -DskipTests package
;   gateway.jar          <- mvn -f bend-gateway/pom.xml -DskipTests package
;   web/                 <- bend-platform-web npm run build 产物
;   mysql/                <- MySQL 8.x green(zip解压版)
;   redis/               <- Redis Windows green(或 Memurai)
;   jre/                 <- JRE 21 green(jlink 或解压版)
;   nginx/               <- nginx green(承载前端静态资源)
;
; 编译: iscc deploy\standalone\master\master.iss
; ================================================

#define MyAppName "BendPlatform 总控"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "BendPlatform"
#define MyInstallDir "BendPlatformMaster"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={pf}\{#MyInstallDir}
DefaultGroupName={#MyAppName}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
OutputDir=deploy\standalone\master\Output
OutputBaseFilename=BendPlatformMasterSetup

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
; JRE
Source: "staging\master\jre\*"; DestDir: "{app}\jre"; Flags: recursesubdirs ignoreversion
; 后端
Source: "staging\master\backend.jar"; DestDir: "{app}\backend"; Flags: ignoreversion
; 网关
Source: "staging\master\gateway.jar"; DestDir: "{app}\gateway"; Flags: ignoreversion
; 前端静态资源(nginx 承载)
Source: "staging\master\web\*"; DestDir: "{app}\web"; Flags: recursesubdirs ignoreversion
; nginx
Source: "staging\master\nginx\*"; DestDir: "{app}\nginx"; Flags: recursesubdirs ignoreversion
; MySQL green
Source: "staging\master\mysql\*"; DestDir: "{app}\mysql"; Flags: recursesubdirs ignoreversion
; 总控 schema.sql(建库脚本)
Source: "staging\master\schema.sql"; DestDir: "{app}\mysql"; Flags: ignoreversion
; Redis green
Source: "staging\master\redis\*"; DestDir: "{app}\redis"; Flags: recursesubdirs ignoreversion
; 启动/停止/配置脚本 + nssm
Source: "staging\master\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\master\scripts\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Run]
; 初始化 MySQL green: --initialize-insecure 后注册服务
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--initialize-insecure"; Flags: runhidden; StatusMsg: "初始化 MySQL 数据目录..."
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--install BendPlatformMySQL --defaults-file=""{app}\mysql\my.ini"""; Flags: runhidden; StatusMsg: "注册 MySQL 服务..."
Filename: "{sys}\net.exe"; Parameters: "start BendPlatformMySQL"; Flags: runhidden; StatusMsg: "启动 MySQL..."
; 建库 + 导入 schema(用 mysql 客户端,cmd /c 重定向)
Filename: "{cmd}"; Parameters: "/c ""{app}\mysql\bin\mysql.exe"" -u root -e ""CREATE DATABASE IF NOT EXISTS bend_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"""; Flags: runhidden; StatusMsg: "创建总控数据库..."
Filename: "{cmd}"; Parameters: "/c ""{app}\mysql\bin\mysql.exe"" -u root bend_platform < ""{app}\mysql\schema.sql"""; Flags: runhidden; StatusMsg: "导入总控表结构..."
; 注册 Redis 服务
Filename: "{app}\redis\redis-server.exe"; Parameters: "--service-install ""{app}\redis\redis.windows.conf"" --service-name BendPlatformRedis"; Flags: runhidden; StatusMsg: "注册 Redis 服务..."
Filename: "{app}\redis\redis-server.exe"; Parameters: "--service-start --service-name BendPlatformRedis"; Flags: runhidden; StatusMsg: "启动 Redis..."
; 注册 nginx 服务(用 nssm 或 WinSW;这里用 nssm)
Filename: "{app}\nssm.exe"; Parameters: "install BendPlatformNginx ""{app}\nginx\nginx.exe"""; Flags: runhidden; StatusMsg: "注册 Nginx 服务..."
; 注册 gateway 服务
Filename: "{app}\nssm.exe"; Parameters: "install BendPlatformGateway ""{app}\jre\bin\java.exe"" -jar ""{app}\gateway\gateway.jar"" --spring.profiles.active=master --server.port=8060"; Flags: runhidden; StatusMsg: "注册 Gateway 服务..."
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformGateway AppEnvironmentExtra LOG_PATH={app}\logs"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformGateway AppStdout {app}\logs\gateway-stdout.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformGateway AppStderr {app}\logs\gateway-stdout.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformGateway AppRotateFiles 1"; Flags: runhidden
; 注册 backend 服务
Filename: "{app}\nssm.exe"; Parameters: "install BendPlatformBackend ""{app}\jre\bin\java.exe"" -jar ""{app}\backend\backend.jar"" --spring.profiles.active=master --server.port=8061"; Flags: runhidden; StatusMsg: "注册 Backend 服务..."
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformBackend AppEnvironmentExtra LOG_PATH={app}\logs"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformBackend AppStdout {app}\logs\backend-stdout.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformBackend AppStderr {app}\logs\backend-stdout.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendPlatformBackend AppRotateFiles 1"; Flags: runhidden
; 启动所有服务
Filename: "{app}\nssm.exe"; Parameters: "start BendPlatformNginx"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start BendPlatformGateway"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start BendPlatformBackend"; Flags: runhidden

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop BendPlatformBackend"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "stop BendPlatformGateway"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "stop BendPlatformNginx"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendPlatformBackend confirm"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendPlatformGateway confirm"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendPlatformNginx confirm"; Flags: runhidden
Filename: "{app}\redis\redis-server.exe"; Parameters: "--service-stop --service-name BendPlatformRedis"; Flags: runhidden
Filename: "{app}\redis\redis-server.exe"; Parameters: "--service-uninstall --service-name BendPlatformRedis"; Flags: runhidden
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--remove BendPlatformMySQL"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\mysql\data"
Type: dirifempty; Name: "{app}"

[Code]
function GetDefaultPort(): String;
begin
  Result := '8060';
end;
