; ================================================
; BendPlatform 分控通用安装器 (Inno Setup)
; ================================================
; 用途: 在商户局域网部署分控平台
; 本安装包为通用包,不含 License 和商户数据。
; 商户安装时输入 总控地址 + 激活码,安装器向总控实时激活。
;
; 产物来源: deploy/standalone/staging/base/(jre/mysql/nginx/nssm.exe)
; ================================================

#define MyAppName "BendPlatform 分控"
#define MyAppVersion "1.0.0"
#define MyInstallDir "BendPlatformTenant"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\{#MyInstallDir}
DefaultGroupName={#MyAppName}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
DisableProgramGroupPage=yes
OutputDir=deploy\standalone\tenant\Output
OutputBaseFilename=BendPlatformTenantSetup

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "staging\tenant\jre\*"; DestDir: "{app}\jre"; Flags: recursesubdirs ignoreversion
Source: "staging\tenant\backend.jar"; DestDir: "{app}\backend"; Flags: ignoreversion
Source: "staging\tenant\gateway.jar"; DestDir: "{app}\gateway"; Flags: ignoreversion
Source: "staging\tenant\web\*"; DestDir: "{app}\web"; Flags: recursesubdirs ignoreversion
Source: "staging\tenant\nginx\*"; DestDir: "{app}\nginx"; Flags: recursesubdirs ignoreversion
Source: "staging\tenant\mysql\*"; DestDir: "{app}\mysql"; Flags: recursesubdirs ignoreversion
; 环境配置(占位,激活后回写)
Source: "staging\tenant\tenant.env"; DestDir: "{app}"; Flags: onlyifdoesntexist ignoreversion
; schema.sql 全量表结构(含全局配置 merchant_group)
Source: "staging\tenant\schema.sql"; DestDir: "{app}\mysql"; Flags: ignoreversion
; migration SQL 增量脚本(升级用)
Source: "staging\tenant\migration\*.sql"; DestDir: "{app}\mysql\migration"; Flags: ignoreversion
; nssm(服务托管)
Source: "staging\tenant\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
; 同局域网分控检测脚本(安装前调用)
Source: "detect-tenant.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall
; 安装时激活脚本(安装器 [Run] 段调用)
Source: "staging\tenant\activate-tenant.ps1"; DestDir: "{app}"; Flags: ignoreversion
; 升级脚本(安装器 [Run] 段调用)
Source: "upgrade-tenant.ps1"; DestDir: "{app}"; Flags: ignoreversion
; 日志查看 + 打开分控平台 + 卸载
Source: "view-logs.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "open-tenant.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "uninstall.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\查看运行日志"; Filename: "{app}\view-logs.bat"
Name: "{group}\打开分控平台"; Filename: "{app}\open-tenant.bat"
Name: "{group}\卸载分控"; Filename: "{app}\uninstall.bat"
Name: "{group}\卸载分控 (控制面板)"; Filename: "{uninstallexe}"
Name: "{userdesktop}\BendPlatform分控"; Filename: "{app}\open-tenant.bat"; IconFilename: "{app}\nginx\nginx.exe"

[Run]
; ================================================================
; 首次安装 (IsFirstInstall=true)
; ================================================================

; ---------- 1. MySQL green 初始化 ----------
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--initialize-insecure"; \
    Flags: runhidden; StatusMsg: "初始化数据库..."; \
    Check: IsFirstInstall
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--install BendTenantMySQL --defaults-file=""{app}\mysql\my.ini"""; \
    Flags: runhidden; StatusMsg: "注册数据库服务..."; \
    Check: IsFirstInstall
Filename: "{sys}\net.exe"; Parameters: "start BendTenantMySQL"; \
    Flags: runhidden; StatusMsg: "启动数据库..."; \
    Check: IsFirstInstall

; ---------- 2. 建库 + 导入 schema ----------
Filename: "{cmd}"; Parameters: "/c ""{app}\mysql\bin\mysql.exe"" -u root -e ""CREATE DATABASE IF NOT EXISTS bend_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"""; \
    Flags: runhidden; StatusMsg: "创建数据库..."; \
    Check: IsFirstInstall
Filename: "{cmd}"; Parameters: "/c ""{app}\mysql\bin\mysql.exe"" -u root bend_platform < ""{app}\mysql\schema.sql"""; \
    Flags: runhidden; StatusMsg: "导入表结构..."; \
    Check: IsFirstInstall

; ---------- 3. 调激活脚本(向总控签发 License + 拉取商户数据) ----------
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -File ""{app}\activate-tenant.ps1"" -MasterUrl ""{code:GetMasterUrl}"" -ActivationCode ""{code:GetActivationCode}"" -AppDir ""{app}"""; \
    Flags: waituntilterminated; \
    StatusMsg: "正在激活分控授权..."; \
    Check: IsFirstInstall

; ================================================================
; 升级 (IsFirstInstall=false, IsUpgrade=true)
; ================================================================

; 执行增量 migration SQL(按文件名字典序,跳过已执行的)
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; \
    Parameters: "-ExecutionPolicy Bypass -File ""{app}\upgrade-tenant.ps1"" -AppDir ""{app}"""; \
    Flags: waituntilterminated; \
    StatusMsg: "正在执行数据库增量升级..."; \
    Check: IsUpgrade

; ================================================================
; 通用(首次安装 + 升级均执行)
; ================================================================

; ---------- 4. 注册/更新服务 ----------
Filename: "{app}\nssm.exe"; Parameters: "install BendTenantNginx ""{app}\nginx\nginx.exe"""; \
    Flags: runhidden; StatusMsg: "注册 Nginx 服务..."
Filename: "{app}\nssm.exe"; Parameters: "install BendTenantGateway ""{app}\jre\bin\java.exe"" -jar ""{app}\gateway\gateway.jar"" --spring.profiles.active=tenant --server.port=8060"; \
    Flags: runhidden; StatusMsg: "注册 Gateway 服务..."
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantGateway AppEnvironmentExtra LOG_PATH={app}\logs"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantGateway AppStdout {app}\logs\gateway-stdout.log"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantGateway AppStderr {app}\logs\gateway-stdout.log"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantGateway AppRotateFiles 1"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "install BendTenantBackend ""{app}\start-backend.bat"""; \
    Flags: runhidden; StatusMsg: "注册 Backend 服务..."
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantBackend AppStdout {app}\logs\backend-stdout.log"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantBackend AppStderr {app}\logs\backend-stdout.log"; \
    Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendTenantBackend AppRotateFiles 1"; \
    Flags: runhidden

; ---------- 5. 防火墙 + 启动服务 ----------
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""BendTenant-Web"" dir=in action=allow protocol=TCP localport=8090"; \
    Flags: runhidden; StatusMsg: "配置防火墙规则(Web)..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""BendTenant-Gateway"" dir=in action=allow protocol=TCP localport=8060"; \
    Flags: runhidden; StatusMsg: "配置防火墙规则(Gateway)..."
Filename: "{app}\nssm.exe"; Parameters: "start BendTenantNginx"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start BendTenantGateway"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start BendTenantBackend"; Flags: runhidden

; 安装完成后:打开分控平台
Filename: "{app}\open-tenant.bat"; Description: "立即打开分控平台(浏览器)"; \
    Flags: postinstall nowait shellexec skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""BendTenant-Web"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""BendTenant-Gateway"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "stop BendTenantBackend"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "stop BendTenantGateway"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "stop BendTenantNginx"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendTenantBackend confirm"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendTenantGateway confirm"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendTenantNginx confirm"; Flags: runhidden
Filename: "{app}\mysql\bin\mysqld.exe"; Parameters: "--remove BendTenantMySQL"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\mysql\data"
Type: dirifempty; Name: "{app}"

[Code]
var
  MasterUrlPage: TInputQueryWizardPage;
  ActivationCodePage: TInputQueryWizardPage;
  _isFirstInstall: Integer;  { 0=未检测, 1=首次安装, 2=升级 }

{ 检测是否为首次安装(MySQL data 目录不存在为首次) }
function DetectInstallType: Integer;
var
  DataDir: String;
begin
  if _isFirstInstall <> 0 then
  begin
    Result := _isFirstInstall;
    Exit;
  end;
  DataDir := ExpandConstant('{app}\mysql\data');
  if DirExists(DataDir) then
    _isFirstInstall := 2  { 升级 }
  else
    _isFirstInstall := 1; { 首次安装 }
  Result := _isFirstInstall;
end;

{ 首次安装时返回 True -- 用于 [Run] Check }
function IsFirstInstall: Boolean;
begin
  Result := DetectInstallType = 1;
end;

{ 升级时返回 True -- 用于 [Run] Check }
function IsUpgrade: Boolean;
begin
  Result := DetectInstallType = 2;
end;

{ 返回用户输入的总控地址 }
function GetMasterUrl(Param: String): String;
begin
  Result := MasterUrlPage.Values[0];
end;

{ 返回用户输入的激活码 }
function GetActivationCode(Param: String): String;
begin
  Result := ActivationCodePage.Values[0];
end;

{ 安装前检测:同局域网是否已有分控(仅首次安装时检测) + 升级警告 }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  if DetectInstallType = 2 then
  begin
    { 升级: 提示用户确认 }
    if MsgBox('检测到已安装分控平台(目录已存在)。'#13#10#13#10 +
              '将进入升级模式：'#13#10 +
              '  - 保留数据库和配置文件'#13#10 +
              '  - 更新程序文件(jar/web/nginx)'#13#10 +
              '  - 执行增量数据库迁移'#13#10#13#10 +
              '是否继续升级？', mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := '用户取消了升级';
      Exit;
    end;
    Result := '';
    Exit;
  end;

  { 首次安装: 检测同局域网是否已有分控 }
  if Exec(ExpandConstant('{cmd.exe}'), '/C powershell -ExecutionPolicy Bypass -File "{tmp}\detect-tenant.ps1" -TimeoutSec 6',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 1 then
    begin
      Result := '检测到本局域网内已存在分控服务:'#13#10 +
                '一个局域网只能安装一个分控,请勿重复安装,'#13#10 +
                '或先卸载已有的分控服务后再安装。';
      Exit;
    end;
  end;
  Result := '';
end;

{ 添加安装界面:总控地址 + 激活码(仅首次安装显示) }
procedure InitializeWizard;
begin
  if DetectInstallType = 1 then
  begin
    { 总控地址输入页 }
    MasterUrlPage := CreateInputQueryPage(wpSelectDir,
      '总控地址', '请输入总控平台的访问地址',
      '分控需要连接到总控平台进行授权激活和定期校验。'#13#10 +
      '例如: http://your-master.example.com:8060');
    MasterUrlPage.Add('总控地址:', False);
    MasterUrlPage.Values[0] := 'http://';

    { 激活码输入页 }
    ActivationCodePage := CreateInputQueryPage(MasterUrlPage.ID,
      '激活码', '请输入分控激活码',
      '激活码由总控管理员生成,每个激活码只能使用一次。'#13#10 +
      '请联系总控运维获取属于您的激活码。');
    ActivationCodePage.Add('激活码:', False);
    ActivationCodePage.Values[0] := '';
  end;
end;

{ 安装完成后提示 }
procedure CurStepChanged(CurStep: TSetupStep);
var
  msg: String;
  isFirst: Boolean;
begin
  if CurStep = ssPostInstall then
  begin
    isFirst := DetectInstallType = 1;
    if isFirst then
      msg := '分控平台已安装并启动!'#13#10#13#10
    else
      msg := '分控平台已升级并启动!'#13#10#13#10;
    msg := msg +
           '【如何使用】'#13#10 +
           '1. 访问分控:双击桌面"BendPlatform分控"快捷方式(用本机局域网IP打开浏览器,'#13#10 +
           '   地址栏显示的就是局域网地址,可复制给同局域网其他电脑访问)'#13#10 +
           '   - 本机访问:http://localhost:8090'#13#10 +
           '   - 其他电脑访问:http://本机IP:8090(如 http://192.168.1.10:8090)'#13#10 +
           '2. 首次登录:使用总控分配给您的商户用户名和密码'#13#10 +
           '3. 安装 Agent:在需要挂机的电脑上双击 BendAgentSetup.exe 安装,'#13#10 +
           '   Agent 会自动发现本分控并注册,无需任何配置'#13#10 +
           '4. 查看运行日志:开始菜单 → BendPlatform分控 → 查看运行日志'#13#10 +
           '5. 服务管理:本机服务 BendTenantBackend / BendTenantGateway / BendTenantNginx / BendTenantMySQL'#13#10#13#10 +
           '如遇问题,请查看安装目录下 logs 文件夹。';
    MsgBox(msg, mbInformation, MB_OK);
  end;
end;
