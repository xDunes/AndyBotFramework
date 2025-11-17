' ApexGirl Bot Web Remote - Background Startup Script
' This script starts the server without showing a console window

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw server.py", 0, False
Set WshShell = Nothing

' Show notification (optional - comment out if not needed)
Set objShell = CreateObject("WScript.Shell")
objShell.Popup "ApexGirl Web Remote server started!" & vbCrLf & "Access at http://localhost:5000", 5, "ApexGirl Bot", 64
Set objShell = Nothing
