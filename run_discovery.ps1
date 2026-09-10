# Zamanlanmış görev bu betiği çalıştırır: günde bir kez geniş piyasa keşif taraması.

$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir
& (Join-Path $ProjectDir "venv\Scripts\python.exe") (Join-Path $ProjectDir "discovery.py")
