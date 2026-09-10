# Zamanlanmış görev bu betiği çalıştırır. Loglama main.py içinde
# yapıldığı için burada sadece doğru klasörden venv python'u çağırmak yeterli.

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir
& (Join-Path $ProjectDir "venv\Scripts\python.exe") (Join-Path $ProjectDir "main.py")
