#define MyAppName "Vak"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Vak"
#define MyAppExeName "Vak.exe"

[Setup]
AppId={{B7A00C26-2534-4A31-BF4C-D81F9360F391}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Vak
DefaultGroupName=Vak
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=VakSetup
SetupIconFile=..\assets\branding\ico\vak.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Vak\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Vak"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Vak"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Vak"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
