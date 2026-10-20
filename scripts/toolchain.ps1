$ErrorActionPreference='Stop'
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if(-not (Test-Path -LiteralPath $vswhere)){throw 'Install Visual Studio C++ Build Tools (x64)'}
$vsInstall=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if(-not $vsInstall){throw 'MSVC x64 toolchain not found'}
$msvcRoot=(Get-ChildItem -LiteralPath (Join-Path $vsInstall 'VC\Tools\MSVC') -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
$sdkRoot=Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10'
$sdkVersion=(Get-ChildItem -LiteralPath (Join-Path $sdkRoot 'Include') -Directory | Where-Object {Test-Path -LiteralPath (Join-Path $_.FullName 'um\windows.h')} | Sort-Object Name -Descending | Select-Object -First 1).Name
if(-not $sdkVersion){throw 'Windows SDK not found'}
$compiler=Join-Path $msvcRoot 'bin\Hostx64\x64\cl.exe'
$env:PATH=(Split-Path -Parent $compiler)+';'+$env:PATH
$env:INCLUDE=(Join-Path $msvcRoot 'include')+';'+(Join-Path $sdkRoot "Include\$sdkVersion\ucrt")+';'+(Join-Path $sdkRoot "Include\$sdkVersion\shared")+';'+(Join-Path $sdkRoot "Include\$sdkVersion\um")
$env:LIB=(Join-Path $msvcRoot 'lib\x64')+';'+(Join-Path $sdkRoot "Lib\$sdkVersion\ucrt\x64")+';'+(Join-Path $sdkRoot "Lib\$sdkVersion\um\x64")
