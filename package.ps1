param([string]$Python='python',[string]$OutputDirectory='dist',[string]$BinaryDirectory='bin-release',[string]$MpqCli=(Join-Path $PSScriptRoot 'tools\mpqcli\mpqcli.exe'),[switch]$WithVulkan)
$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath $MpqCli)){throw 'Run scripts/install-mpqcli.ps1 or pass -MpqCli'}
$binaries=@('HiddenEditorHost.exe','SC2StartupBootstrap.dll','SC2NativeBridge.exe','SC2NativeBridge.dll','RenderCapture.exe')
$renderer=Join-Path $PSScriptRoot "$BinaryDirectory\renderers\dxvk"
if($WithVulkan){& (Join-Path $PSScriptRoot 'scripts\fetch-vulkan.ps1') -Destination $renderer}
$hasVulkan=Test-Path -LiteralPath (Join-Path $renderer 'd3d9.dll')
if($hasVulkan -and (Get-FileHash -LiteralPath (Join-Path $renderer 'd3d9.dll')).Hash -ne 'C126316F7478EAFF1AD8087702EDA5930F2400187B9C8B3592219C34F6632780'){throw 'DXVK renderer hash mismatch'}
foreach($program in @(@{Name='SC2NativeAPI';Entry='hidden_api.py'},@{Name='SC2NativeMCP';Entry='mcp_server.py'})){
 # Pillow's optional NumPy integration is unused. Do not pull build-machine
 # analysis extras (and their BLAS DLLs) into the redistributable toolkit.
 $pyArgs=@('-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--exclude-module','numpy','--name',$program.Name,
  '--distpath',(Join-Path $PSScriptRoot $OutputDirectory),'--workpath',(Join-Path $PSScriptRoot 'pyinstaller-build'),
  '--specpath',$PSScriptRoot,'--paths',(Join-Path $PSScriptRoot 'app'))
 foreach($file in $binaries){$pyArgs+=@('--add-binary',((Join-Path $PSScriptRoot "$BinaryDirectory\$file")+';.'))}
 if($hasVulkan){
  $pyArgs+=@('--add-binary',((Join-Path $renderer 'd3d9.dll')+';renderers/dxvk'))
  foreach($file in 'LICENSE.txt','manifest.json'){$pyArgs+=@('--add-data',((Join-Path $renderer $file)+';renderers/dxvk'))}
 }
 $pyArgs+=@('--add-binary',($MpqCli+';.'),(Join-Path $PSScriptRoot ('app\'+$program.Entry)))
 & $Python @pyArgs
 if($LASTEXITCODE){throw ('Package failed: '+$program.Name)}
}
foreach($file in 'README.md','THIRD_PARTY.txt','LICENSE','NOTICE'){
 if(Test-Path -LiteralPath (Join-Path $PSScriptRoot $file)){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $PSScriptRoot $OutputDirectory)}
}
$docsDestination=Join-Path $PSScriptRoot "$OutputDirectory\docs"
New-Item -ItemType Directory -Force -Path $docsDestination | Out-Null
foreach($file in 'VALIDATION.md','MODKIT_BRIDGE_STATUS.md','NATIVE_DISPATCH.md','PARALLEL_INSTANCES.md','PRESENTATION_READINESS.md','MAP_EXPORT.md','JOBS_AND_REPORTS.md','DATA_AND_RESOURCES.md'){
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot "docs\$file") -Destination $docsDestination
}
if($hasVulkan){Copy-Item -LiteralPath (Join-Path $renderer 'LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-DXVK.txt")}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\minhook\LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-MinHook.txt")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\Pillow-LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-Pillow.txt")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tools\mpqcli\LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-mpqcli.txt")
foreach($notice in 'LICENSE-CLI11.txt','LICENSE-StormLib.txt'){
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot "tools\mpqcli\$notice") -Destination (Join-Path $PSScriptRoot "$OutputDirectory\$notice")
}
