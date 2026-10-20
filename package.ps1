param([string]$Python='python',[string]$OutputDirectory='dist',[string]$BinaryDirectory='bin-release',[string]$MpqCli=(Join-Path $PSScriptRoot 'tools\mpqcli\mpqcli.exe'))
$ErrorActionPreference='Stop'
if(-not (Test-Path -LiteralPath $MpqCli)){throw 'Run scripts/install-mpqcli.ps1 or pass -MpqCli'}
$binaries=@('HiddenEditorHost.exe','SC2StartupBootstrap.dll','SC2NativeBridge.exe','SC2NativeBridge.dll','RenderCapture.exe')
foreach($program in @(@{Name='SC2NativeAPI';Entry='hidden_api.py'},@{Name='SC2NativeMCP';Entry='mcp_server.py'})){
 $pyArgs=@('-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name',$program.Name,
  '--distpath',(Join-Path $PSScriptRoot $OutputDirectory),'--workpath',(Join-Path $PSScriptRoot 'pyinstaller-build'),
  '--specpath',$PSScriptRoot,'--paths',(Join-Path $PSScriptRoot 'app'))
 foreach($file in $binaries){$pyArgs+=@('--add-binary',((Join-Path $PSScriptRoot "$BinaryDirectory\$file")+';.'))}
 $pyArgs+=@('--add-binary',($MpqCli+';.'),(Join-Path $PSScriptRoot ('app\'+$program.Entry)))
 & $Python @pyArgs
 if($LASTEXITCODE){throw ('Package failed: '+$program.Name)}
}
foreach($file in 'README.md','THIRD_PARTY.txt','LICENSE','NOTICE'){
 if(Test-Path -LiteralPath (Join-Path $PSScriptRoot $file)){Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $PSScriptRoot $OutputDirectory)}
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\minhook\LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-MinHook.txt")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vendor\Pillow-LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-Pillow.txt")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'tools\mpqcli\LICENSE.txt') -Destination (Join-Path $PSScriptRoot "$OutputDirectory\LICENSE-mpqcli.txt")
foreach($notice in 'LICENSE-CLI11.txt','LICENSE-StormLib.txt'){
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot "tools\mpqcli\$notice") -Destination (Join-Path $PSScriptRoot "$OutputDirectory\$notice")
}
