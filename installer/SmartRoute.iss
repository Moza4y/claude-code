; Smart Route for SOLIDWORKS - Inno Setup 6.3+ script (compile with tools\build.ps1)
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId stays the same for every version, so a new Setup.exe upgrades the installed one in place.
AppId={{B7D3C1E4-5A2F-4E8B-9C61-3F0A7D2E8B15}
AppName=Smart Route for SOLIDWORKS
AppVersion={#AppVersion}
AppVerName=Smart Route {#AppVersion}
AppPublisher=Smart Route
DefaultDirName={autopf}\SmartRoute
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=SmartRoute-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; SOLIDWORKS keeps the add-in DLL loaded: let Setup offer to close it (Restart Manager)
CloseApplications=yes
RestartApplications=no
UninstallDisplayName=Smart Route for SOLIDWORKS
VersionInfoVersion={#AppVersion}
InfoAfterFile=..\docs\AFTERINSTALL.txt
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\build\addin\SmartRoute.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\engine\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Run]
; registers the .NET add-in for COM (HKLM\SOFTWARE\SolidWorks\Addins + load-at-startup for the current user)
Filename: "{dotnet4064}\regasm.exe"; Parameters: "/codebase ""{app}\SmartRoute.dll"""; \
  Flags: runhidden waituntilterminated; StatusMsg: "Registering the SOLIDWORKS add-in..."

[UninstallRun]
Filename: "{dotnet4064}\regasm.exe"; Parameters: "/u ""{app}\SmartRoute.dll"""; \
  Flags: runhidden waituntilterminated; RunOnceId: "UnregisterSmartRouteAddin"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not FileExists(ExpandConstant('{dotnet4064}\regasm.exe')) then
  begin
    MsgBox('.NET Framework 4.8 (64-bit) is required.', mbError, MB_OK);
    Result := False;
  end;
end;
