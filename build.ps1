param([string]$OutputDirectory='bin-release',[switch]$WithVulkan)
. (Join-Path $PSScriptRoot 'scripts\toolchain.ps1')
$destination=Join-Path $PSScriptRoot $OutputDirectory
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Push-Location $destination
try {
 $options=@('/nologo','/utf-8','/W4','/std:c++17','/EHsc','/O2','/MT','/DUNICODE','/D_UNICODE')
 $bridgeSources=@('src\bridge.cpp','vendor\minhook\src\buffer.c','vendor\minhook\src\hook.c','vendor\minhook\src\trampoline.c','vendor\minhook\src\hde\hde64.c') | ForEach-Object {Join-Path $PSScriptRoot $_}
 & $compiler @options /LD @bridgeSources /Fe:SC2NativeBridge.dll
 if($LASTEXITCODE){throw 'Native bridge build failed'}
 & $compiler @options (Join-Path $PSScriptRoot 'src\controller.cpp') /Fe:SC2NativeBridge.exe
 if($LASTEXITCODE){throw 'Controller build failed'}
 & $compiler @options (Join-Path $PSScriptRoot 'src\render_capture.cpp') /Fe:RenderCapture.exe
 if($LASTEXITCODE){throw 'Frame capture controller build failed'}
}finally{Pop-Location}
& (Join-Path $PSScriptRoot 'build_host.ps1') -OutputDirectory $OutputDirectory
if($WithVulkan){& (Join-Path $PSScriptRoot 'scripts\fetch-vulkan.ps1') -Destination (Join-Path $destination 'renderers\dxvk')}
