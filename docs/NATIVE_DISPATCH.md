# Owned Editor startup dispatch

Native protocol **12** retains owned-thread startup dispatch and binds native
requests to the selected Editor executable by file identity rather than a fixed
installation path. It supersedes protocol 11; upgrade all native components.
The earlier protocol 11 replaced the per-request cross-process DLL-hook setup.
Use the matching host, bootstrap, bridge DLL and controller from one release.
Restart an old owned worker after upgrading. A client-visible Editor is never
attached to or upgraded in place.

The API verifies the selected original executable's SHA-256 and the host checks
its architecture/version before creating the child. Its early primary-thread
callback binds the running image to that selected file by Windows file identity.
Image-format/resource probing is deliberately outside that early callback: a
diagnostic candidate reproduced Win32 193 there despite passing prelaunch checks.
Controllers check the selected file and exact owned PID again. Private startup
`dispatch.log` records identity/callback setup without map content or tokens.

## Win32 126 diagnosis

The previous controller could load the x64 bridge and resolve both exports,
but `SetWindowsHookExW` rejected its DLL-backed registration with Win32 126.
An unchanged earlier release failed at the same point. A separate disposable
GUI process reproduced the failure with both the original bridge and a minimal
two-export DLL, from both tested drives. The same callbacks could be registered
on their own thread with `hMod = nullptr`. No SC2 commands or user input were
needed for that reproduction.

This isolates the failing dependency to Windows' DLL-backed hook registration;
it does not establish the exact kernel resource or policy responsible. In
particular, missing VC runtimes, a damaged Editor, hook-module exhaustion and
an antivirus rejection are not claimed as proven causes. A historical
`blocked by policy` approval response is separate from this native API error.

## Startup and lifetime

1. The existing hidden host creates its original Editor child suspended on an
   owned `SC2Native-…` desktop, under the API's lifetime Job Object.
2. The existing startup bootstrap loads its sibling bridge DLL. Inside the
   Editor process it resolves the actual relocated initialization address,
   verifies that the primary thread belongs to that process, and queues its
   initialization before the host resumes that thread.
3. Initialization verifies the installed Editor executable and private desktop,
   then installs CBT and CALLWNDPROC callbacks for **the current thread only**,
   with a null module parameter. No cross-process DLL-hook registration occurs.
4. The dispatcher marks its own top-level windows with the protocol version.
   Host readiness and every controller request require that exact marker.
   A missing/incompatible dispatcher fails closed; there is no legacy-hook
   fallback or automatic security-setting change.
5. Requests retain exact document, PID, GUI-thread, protocol and mapping checks.
   They run the existing original Editor commands and capture their results.
   Original generation and compilation remain separate confirmations.
6. The request-local guard is removed after each handler. The two startup
   callbacks and loaded DLL live until the owned Editor exits. `hooksRemoved`
   retains its request-cleanup meaning; `requestGuardRemoved`, `transport`,
   `crossProcessHookRegistrationUsed` and `residentHooksLifetime` make that scope
   explicit. A request timeout retains its IPC while a native handler is pending.

Windows documents both [same-process thread-specific hook callbacks](https://learn.microsoft.com/en-us/windows/win32/winmsg/about-hooks)
and [initial APC execution before a suspended thread begins running](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-queueuserapc).
The queued callback address is resolved inside the destination process; the
host does not assume that a DLL has the same base address in two processes.

All Editor windows remain on the private desktop. The technical render window
remains invisible. This change adds no mouse/keyboard automation, input-desktop
switch, arbitrary-process attachment, filesystem change to the installed Editor,
or new MCP tool.

## Regression checks

`scripts/test-native.ps1` includes a real Windows regression for initialization
before thread entry, local request dispatch, thread isolation, input-desktop
refusal and explicit cleanup. It does not require StarCraft II. The opt-in
`tests/live_stability.py` separately checks original XML loading, generation,
compilation, exact Galaxy download, negative cases and subsequent recovery.
See [validation history](VALIDATION.md) for dated original-Editor results.
