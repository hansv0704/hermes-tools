Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
vbsDir = fso.GetParentFolderName(WScript.ScriptFullName)
tray = vbsDir & "\hermes_tray.pyw"
hermes = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes\hermes-agent\venv\Scripts\pythonw.exe"
WshShell.Run """" & hermes & """ """ & tray & """", 0, False
