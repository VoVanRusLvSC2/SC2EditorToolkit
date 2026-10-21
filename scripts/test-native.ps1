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
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT (Join-Path $root 'tests\map_export_paths_test.cpp') /Fe:MapExportPathTests.exe
 if($LASTEXITCODE){throw 'Map export path test build failed'}
 & (Join-Path $destination 'MapExportPathTests.exe')
 if($LASTEXITCODE){throw 'Map export path regression test failed'}
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT (Join-Path $root 'tests\owned_thread_hooks_test.cpp') /Fe:OwnedThreadHooksTests.exe
 if($LASTEXITCODE){throw 'Owned thread dispatch test build failed'}
 & (Join-Path $destination 'OwnedThreadHooksTests.exe')
 if($LASTEXITCODE){throw 'Owned thread dispatch regression test failed'}
}finally{Pop-Location}
