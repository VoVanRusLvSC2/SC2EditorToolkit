param([string]$OutputDirectory='bin-release')
. (Join-Path $PSScriptRoot 'scripts\toolchain.ps1')
$destination=Join-Path $PSScriptRoot $OutputDirectory
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Push-Location $destination
try {
 $options=@('/nologo','/utf-8','/W4','/std:c++17','/EHsc','/O2','/MT','/DUNICODE','/D_UNICODE')
 $sources=@('src\bootstrap.cpp','src\graphics_bridge.cpp','vendor\minhook\src\buffer.c','vendor\minhook\src\hook.c','vendor\minhook\src\trampoline.c','vendor\minhook\src\hde\hde64.c') | ForEach-Object {Join-Path $PSScriptRoot $_}
 & $compiler @options /LD @sources /Fe:SC2StartupBootstrap.dll
 if($LASTEXITCODE){throw 'Startup/graphics DLL build failed'}
 & $compiler @options (Join-Path $PSScriptRoot 'src\hidden_host.cpp') /Fe:HiddenEditorHost.exe
 if($LASTEXITCODE){throw 'Hidden host build failed'}
}finally{Pop-Location}
