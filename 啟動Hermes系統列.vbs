Set WshShell = CreateObject("WScript.Shell")
hermes = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\hermes\hermes-agent\venv\Scripts\pythonw.exe"
tray = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\Desktop\Hermes工具區\hermes_tray.pyw"
WshShell.Run """" & hermes & """ """ & tray & """", 0, False
