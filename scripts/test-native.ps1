param([string]$OutputDirectory='bin-tests')
. (Join-Path $PSScriptRoot 'toolchain.ps1')
$root=Split-Path -Parent $PSScriptRoot
$destination=Join-Path $root $OutputDirectory
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Push-Location $destination
try {
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT (Join-Path $root 'tests\document_window_test.cpp') /Fe:DocumentWindowTests.exe
 if($LASTEXITCODE){throw 'Readiness regression test build failed'}
 & (Join-Path $destination 'DocumentWindowTests.exe')
 if($LASTEXITCODE){throw 'Readiness regression test failed'}
}finally{Pop-Location}
