$ErrorActionPreference='Stop'
$destination=Join-Path (Split-Path -Parent $PSScriptRoot) 'tools\mpqcli\mpqcli.exe'
$expected='efed6d68060b70b5f71b383f3dc3b87db84ff1a299f02f8e32ae6be93eb6dcfc'
if(Test-Path -LiteralPath $destination){
 if((Get-FileHash -LiteralPath $destination).Hash.ToLowerInvariant() -eq $expected){Write-Output 'mpqcli v0.10.0 already verified';exit 0}
 throw 'Existing mpqcli differs from pinned release; preserve/rename it before installing'
}
New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
$temporary=$destination+'.download'
try {
 Invoke-WebRequest -Uri 'https://github.com/thegraydot/mpqcli/releases/download/v0.10.0/mpqcli-windows-amd64.exe' -OutFile $temporary
 if((Get-FileHash -LiteralPath $temporary).Hash.ToLowerInvariant() -ne $expected){throw 'mpqcli download SHA256 mismatch'}
 Move-Item -LiteralPath $temporary -Destination $destination
}finally{if(Test-Path -LiteralPath $temporary){Remove-Item -LiteralPath $temporary}}
