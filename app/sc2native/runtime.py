"""Local API backed by an owned, isolated instance of the installed SC2 Editor."""
from __future__ import annotations
import argparse, atexit, ctypes, hashlib, json, os, secrets, shutil, subprocess, sys, threading, time, uuid
from ctypes import wintypes as W
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
import native_xml_oracle as oracle
import file_prepare as files

RES=oracle.RES
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
user=ctypes.WinDLL('user32',use_last_error=True)
kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
kernel.CloseHandle.argtypes=[W.HANDLE]
kernel.GetProcessTimes.argtypes=[W.HANDLE,ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME)]
kernel.GetExitCodeProcess.argtypes=[W.HANDLE,ctypes.POINTER(W.DWORD)]
kernel.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
kernel.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];kernel.WaitForSingleObject.restype=W.DWORD
kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)]
user.GetForegroundWindow.restype=W.HWND
user.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
user.IsWindowVisible.argtypes=[W.HWND]
user.OpenInputDesktop.argtypes=[W.DWORD,W.BOOL,W.DWORD];user.OpenInputDesktop.restype=W.HANDLE
user.GetUserObjectInformationW.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.POINTER(W.DWORD)]
user.CloseDesktop.argtypes=[W.HANDLE]
ENUM=ctypes.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
user.EnumWindows.argtypes=[ENUM,W.LPARAM]
class BasicLimit(ctypes.Structure):
    _fields_=[('ProcessTime',ctypes.c_longlong),('JobTime',ctypes.c_longlong),('Flags',W.DWORD),
        ('MinWorkingSet',ctypes.c_size_t),('MaxWorkingSet',ctypes.c_size_t),('ActiveLimit',W.DWORD),
        ('Affinity',ctypes.c_size_t),('Priority',W.DWORD),('Scheduling',W.DWORD)]
class IoCounters(ctypes.Structure):_fields_=[(name,ctypes.c_ulonglong) for name in ('ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes')]
class ExtendedLimit(ctypes.Structure):
    _fields_=[('Basic',BasicLimit),('Io',IoCounters),('ProcessMemory',ctypes.c_size_t),('JobMemory',ctypes.c_size_t),('PeakProcess',ctypes.c_size_t),('PeakJob',ctypes.c_size_t)]
kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];kernel.CreateJobObjectW.restype=W.HANDLE
kernel.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]

def process_time(pid):
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        c,e,k,u=(W.FILETIME() for _ in range(4));code=W.DWORD()
        if not kernel.GetProcessTimes(handle,ctypes.byref(c),ctypes.byref(e),ctypes.byref(k),ctypes.byref(u)):return None
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259:return None
        return (c.dwHighDateTime<<32)|c.dwLowDateTime
    finally:kernel.CloseHandle(handle)

def input_desktop():
    handle=user.OpenInputDesktop(0,False,1)
    if not handle:return None
    try:
        text=ctypes.create_unicode_buffer(256);size=W.DWORD()
        return text.value if user.GetUserObjectInformationW(handle,2,text,ctypes.sizeof(text),ctypes.byref(size)) else None
    finally:user.CloseDesktop(handle)

def watch_frozen_parent():
    # A one-file executable has a bootloader parent. If it is forcibly stopped,
    # Windows does not automatically stop the Python child. Observe that exact
    # parent so its death closes this process's worker Job Object as well.
    if not getattr(sys,'frozen',False):return
    handle=kernel.OpenProcess(0x100000|0x1000,False,os.getppid())
    if not handle:return
    text=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(text))
    if not kernel.QueryFullProcessImageNameW(handle,0,text,ctypes.byref(size)) or os.path.normcase(text.value)!=os.path.normcase(sys.executable):
        kernel.CloseHandle(handle);return
    def wait():
        if kernel.WaitForSingleObject(handle,0xffffffff)==0:os._exit(0)
        kernel.CloseHandle(handle)
    threading.Thread(target=wait,daemon=True).start()

class Observation:
    """Observe the user's desktop; never focus, activate, show, or inject input."""
    def __init__(self,pid):
        self.pid=pid;self.samples=0;self.visible_peak=0;self.foreground_samples=0
        self.initial=input_desktop();self.desktop_changes=0;self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        while not self.stop_event.is_set():
            count=0
            @ENUM
            def enum(hwnd,param):
                nonlocal count
                pid=W.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                if pid.value==self.pid and user.IsWindowVisible(hwnd):count+=1
                return True
            user.EnumWindows(enum,0);self.visible_peak=max(self.visible_peak,count)
            pid=W.DWORD();user.GetWindowThreadProcessId(user.GetForegroundWindow(),ctypes.byref(pid))
            self.foreground_samples+=int(pid.value==self.pid)
            if input_desktop()!=self.initial:self.desktop_changes+=1
            self.samples+=1;self.stop_event.wait(.05)
    def snapshot(self):return dict(samples=self.samples,visibleWindowsOnUserDesktopPeak=self.visible_peak,
        editorForegroundSamples=self.foreground_samples,inputDesktopChanges=self.desktop_changes,
        inputInjectionUsed=False,desktopSwitchApiUsed=False)
    def stop(self):self.stop_event.set();self.thread.join(2)
