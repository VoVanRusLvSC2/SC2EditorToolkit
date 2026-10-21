#pragma once
#include <windows.h>
struct BootstrapConfig { wchar_t suffix[128]; wchar_t logPath[32768]; DWORD patches; DWORD error; DWORD primaryThreadId; };
