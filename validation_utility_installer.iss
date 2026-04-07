#define MyAppVersion GetEnv("VERSION")

[Setup]
AppName=ValidationUtility
AppVersion={#MyAppVersion}
AppPublisher=Rudra Prajapati

DefaultDirName={pf}\ValidationUtility
DefaultGroupName=ValidationUtility

OutputDir=Output
OutputBaseFilename=ValidationUtility-Setup-{#MyAppVersion}

Compression=lzma
SolidCompression=yes

SetupIconFile=ValidationUtility.ico

; Optional - keep only if this file exists
LicenseFile=release\LICENSE

PrivilegesRequired=admin

[Files]
Source: "ValidationUtility-{#MyAppVersion}.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ValidationUtility"; Filename: "{app}\ValidationUtility-{#MyAppVersion}.exe"
Name: "{commondesktop}\ValidationUtility"; Filename: "{app}\ValidationUtility-{#MyAppVersion}.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; Flags: unchecked

[Run]
Filename: "{app}\ValidationUtility-{#MyAppVersion}.exe"; Description: "Launch ValidationUtility"; Flags: nowait postinstall skipifsilent
