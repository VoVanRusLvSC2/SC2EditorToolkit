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
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT (Join-Path $root 'tests\editor_identity_test.cpp') /Fe:EditorIdentityTests.exe
 if($LASTEXITCODE){throw 'Editor identity test build failed'}
 & (Join-Path $destination 'EditorIdentityTests.exe')
 if($LASTEXITCODE){throw 'Editor identity regression test failed'}
 $clipboardSources=@('tests\data_clipboard_test.cpp','vendor\minhook\src\buffer.c','vendor\minhook\src\hook.c','vendor\minhook\src\trampoline.c','vendor\minhook\src\hde\hde64.c') | ForEach-Object {Join-Path $root $_}
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT @clipboardSources /Fe:DataClipboardTests.exe user32.lib uuid.lib
 if($LASTEXITCODE){throw 'Private clipboard test build failed'}
 & (Join-Path $destination 'DataClipboardTests.exe')
 if($LASTEXITCODE){throw 'Private clipboard isolation regression failed'}
 & $compiler /nologo /utf-8 /W4 /std:c++17 /EHsc /MT (Join-Path $root 'tests\diagnostic_output_test.cpp') /Fe:DiagnosticOutputTests.exe
 if($LASTEXITCODE){throw 'Diagnostic output test build failed'}
 & (Join-Path $destination 'DiagnosticOutputTests.exe')
 if($LASTEXITCODE){throw 'Diagnostic output identity regression failed'}
}finally{Pop-Location}
