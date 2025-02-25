[Setup]
AppName=Directory Size Viewer
AppVersion=1.0.1
DefaultDirName={pf}\Directory Size Viewer
DefaultGroupName=Directory Size Viewer
UninstallDisplayIcon={app}\Directory_Size_Viewer.exe
Compression=lzma2
SolidCompression=yes
OutputDir=.
OutputBaseFilename=Directory_Size_Viewer_Setup

[Files]
Source: "dist\Directory_Size_Viewer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Directory Size Viewer"; Filename: "{app}\Directory_Size_Viewer.exe"
Name: "{commondesktop}\Directory Size Viewer"; Filename: "{app}\Directory_Size_Viewer.exe"

[Run]
Filename: "{app}\Directory_Size_Viewer.exe"; Description: "Launch Directory Size Viewer"; Flags: nowait postinstall skipifsilent 