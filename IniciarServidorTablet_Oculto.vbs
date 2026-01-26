' Inicia el servidor tablet sin abrir consola
' Ejecuta IniciarServidorTablet.bat oculto

Dim shell, fso, root, bat
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
bat = """" & root & "\IniciarServidorTablet.bat"""

' 0 = oculto, False = no esperar
shell.Run bat, 0, False
