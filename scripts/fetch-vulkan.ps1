param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
$rendererDir=[IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Path $rendererDir -Force | Out-Null
$dll=Join-Path $rendererDir 'd3d9.dll'
$expectedDll='C126316F7478EAFF1AD8087702EDA5930F2400187B9C8B3592219C34F6632780'
if(-not(Test-Path -LiteralPath $dll) -or (Get-FileHash -LiteralPath $dll).Hash -ne $expectedDll){
 $archive=Join-Path ([IO.Path]::GetTempPath()) ('sc2editor-dxvk-'+[guid]::NewGuid().ToString('N')+'.tar.gz')
 try {
  Invoke-WebRequest 'https://github.com/doitsujin/dxvk/releases/download/v3.1.1/dxvk-3.1.1.tar.gz' -OutFile $archive
  if((Get-FileHash -LiteralPath $archive).Hash -ne '40565B4A724AADC4433FA4E010B4B23916D9B1F1BAEEE64E17186DB94F54E608'){throw 'DXVK archive SHA256 mismatch'}
  & tar -xzf $archive --strip-components=2 -C $rendererDir 'dxvk-3.1.1/x64/d3d9.dll'
  if($LASTEXITCODE){throw 'DXVK extraction failed'}
 }finally{if(Test-Path -LiteralPath $archive){Remove-Item -LiteralPath $archive}}
}
if((Get-FileHash -LiteralPath $dll).Hash -ne $expectedDll){throw 'DXVK DLL SHA256 mismatch'}
$notices=Join-Path (Split-Path -Parent $PSScriptRoot) 'vendor\dxvk'
if((Get-FileHash -LiteralPath (Join-Path $notices 'LICENSE')).Hash -ne 'A5CB1A6DED7D2D7E92D550BA28EDD21BE2D1D4044662B399887351023E30CE64'){throw 'DXVK license SHA256 mismatch'}
Copy-Item -LiteralPath (Join-Path $notices 'LICENSE') -Destination (Join-Path $rendererDir 'LICENSE.txt')
Copy-Item -LiteralPath (Join-Path $notices 'manifest.json') -Destination (Join-Path $rendererDir 'manifest.json')
