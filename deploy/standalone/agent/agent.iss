; ================================================
; BendAgent 安装器 (Inno Setup)
; ================================================
; 用途: 在商户的 Agent 机器上安装 Agent
; 分控架构特征:
;   - 内嵌 BendAgent.exe(PyInstaller --onefile 产物)
;   - 内嵌 Playwright Chromium 目录(离线,不运行时拉取)
;   - 内嵌 VC++ Redistributable(静默安装)
;   - agent.yaml 中 backend.base_url 指向【本机局域网分控地址】(打包时预填)
;   - agent.yaml 中 backend.registration_code 预置(首次启动自动激活,无需交互)
;
; 产物来源(打包前需放入 deploy/standalone/staging/agent/):
;   BendAgent.exe          <- bend-agent/scripts/build.bat 产物
;   agent.yaml             <- 打包脚本预填分控地址+注册码
;   chromium/              <- Playwright Chromium 目录
;   vc_redist.x64.exe      <- VC++ 2015-2022 x64
;   nssm.exe               <- 服务托管
;   templates/             <- 游戏场景模板
; ================================================

#define MyAppName "BendAgent"
#define MyAppVersion "1.0.0"
#define MyInstallDir "BendAgent"

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
OutputDir=deploy\standalone\agent\Output
OutputBaseFilename=BendAgentSetup

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
; 主程序
Source: "staging\agent\BendAgent.exe"; DestDir: "{app}"; Flags: ignoreversion
; 配置(打包预填分控地址+注册码)
Source: "staging\agent\agent.yaml"; DestDir: "{app}"; Flags: onlyifdoesntexist ignoreversion
; Playwright Chromium(离线预制)
Source: "staging\agent\chromium\*"; DestDir: "{app}\chromium"; Flags: recursesubdirs ignoreversion
; 场景模板
Source: "staging\agent\templates\*"; DestDir: "{app}\templates"; Flags: recursesubdirs ignoreversion
; 服务托管 + 卸载脚本
Source: "staging\agent\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\agent\uninstall_agent.ps1"; DestDir: "{app}"; Flags: ignoreversion
; VC++ redist(内嵌)
Source: "staging\agent\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
; 日志查看脚本
Source: "view-logs.bat"; DestDir: "{app}"; Flags: ignoreversion
; 卸载脚本(先清服务+环境变量,再删目录即完全卸载)
Source: "uninstall.bat"; DestDir: "{app}"; Flags: ignoreversion
; 安装前分控检测脚本
Source: "discover-tenant.ps1"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\查看运行日志"; Filename: "{app}\view-logs.bat"
Name: "{group}\卸载 Agent"; Filename: "{app}\uninstall.bat"
Name: "{group}\卸载 Agent (控制面板)"; Filename: "{uninstallexe}"

[Code]

{ 检测 Windows 服务是否存在 }
function ServiceExists(name: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := ShellExec('open', 'sc.exe', 'query ' + name, '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
end;

{ 卸载已有的 Agent 服务 }
procedure UninstallExistingAgent;
var
  ResultCode: Integer;
begin
  if not ServiceExists('BendAgent') then
    Exit;

  // 停掉旧服务
  Exec(ExpandConstant('{cmd}'), '/C sc stop BendAgent',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(2000); // 等两秒确保进程退出

  // 删掉旧服务
  Exec(ExpandConstant('{cmd}'), '/C sc delete BendAgent',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  // 如果旧安装目录还在,nssm remove 清理残留(忽略错误)
  if DirExists(ExpandConstant('{app}')) then begin
    if FileExists(ExpandConstant('{app}\nssm.exe')) then begin
      Exec(ExpandConstant('{app}\nssm.exe'), 'remove BendAgent confirm',
           '', SW_HIDE, ewNoWait, ResultCode);
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // 1. 检测同局域网是否已有分控在运行,否则中止安装
  if Exec(ExpandConstant('{cmd}'), '/C powershell -ExecutionPolicy Bypass -File "{tmp}\discover-tenant.ps1" -TimeoutSec 6',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode <> 0 then
    begin
      Result := '未发现同局域网内的分控服务:'#13#10#13#10 +
                'Agent 必须连接分控平台才能工作,'#13#10 +
                '请先在本局域网的一台机器上安装并启动【分控平台服务】,'#13#10 +
                '确认分控正常运行后,再安装 Agent。'#13#10#13#10 +
                '(分控服务安装包为 BendPlatformTenantSetup.exe)';
      Exit;
    end;
  end;

  // 2. 本机已有旧 Agent,自动卸载再继续安装(一台电脑只能装一个 Agent)
  if ServiceExists('BendAgent') then begin
    UninstallExistingAgent;
  end;

  Result := '';
end;

// 安装完成后提示
procedure CurStepChanged(CurStep: TSetupStep);
var
  msg: String;
begin
  if CurStep = ssPostInstall then
  begin
    msg := 'BendAgent 已安装并启动!'#13#10#13#10 +
           'Agent 已自动:'#13#10 +
           '  - 发现同局域网的分控服务并自动注册'#13#10 +
           '  - 连接分控开始接收任务'#13#10#13#10 +
           '无需任何手动配置。'#13#10#13#10 +
           '【重要说明】'#13#10 +
           '  - 一台电脑只能安装一个 Agent'#13#10 +
           '  - 本机服务: BendAgent(开机自启,无需手动启动)'#13#10 +
           '  - 重新安装会自动卸载旧版本'#13#10 +
           '  - 查看日志: 开始菜单 → BendAgent → 查看运行日志'#13#10#13#10 +
           '如 Agent 未能上线,请查看安装目录 logs 文件夹,并确认分控平台正常运行。';
    MsgBox(msg, mbInformation, MB_OK);
  end;
end;

[Run]
; 静默安装 VC++ Redistributable(已装则跳过)
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; Flags: runhidden; StatusMsg: "安装 Visual C++ 运行库..."
; 设置 PLAYWRIGHT_BROWSERS_PATH 指向内嵌 Chromium(系统级环境变量,setx /M 需管理员权限)
Filename: "{sys}\setx.exe"; Parameters: "PLAYWRIGHT_BROWSERS_PATH ""{app}\chromium"" /M"; Flags: runhidden; StatusMsg: "配置 Playwright 浏览器路径..."
; 注册 Agent 为 Windows 服务(自启动)
Filename: "{app}\nssm.exe"; Parameters: "install BendAgent ""{app}\BendAgent.exe"" --config ""{app}\agent.yaml"""; Flags: runhidden; StatusMsg: "注册 Agent 服务..."
Filename: "{app}\nssm.exe"; Parameters: "set BendAgent AppDirectory ""{app}"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendAgent Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendAgent AppStdout {app}\logs\service_stdout.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendAgent AppStderr {app}\logs\service_stderr.log"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "set BendAgent AppRotateFiles 1"; Flags: runhidden
; 启动前确保 logs 目录存在(nssm AppStdout 写入需要)
Filename: "{cmd}"; Parameters: "/c if not exist ""{app}\logs"" mkdir ""{app}\logs"""; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "start BendAgent"; Flags: runhidden; StatusMsg: "启动 Agent..."

[UninstallRun]
Filename: "{app}\nssm.exe"; Parameters: "stop BendAgent"; Flags: runhidden
Filename: "{app}\nssm.exe"; Parameters: "remove BendAgent confirm"; Flags: runhidden

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\credentials"
Type: dirifempty; Name: "{app}"
