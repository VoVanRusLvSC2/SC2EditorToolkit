# HTTP disconnects, Recent Files and startup evidence

## Scope

The 2026-11-07 report included repeated `ConnectionAbortedError` / WinError 10053
tracebacks and screenshots of temporary worker maps in the normal Editor's File
menu. A separate intermittent startup report is awaiting its original logs.
These are separate failure classes. Terrain appearance needs a specific example;
this change does not claim to improve terrain rendering or resource appearance.

## HTTP transport

The old handler caught broken pipes and connection resets only around the JSON
body write. A connection abort could also happen while flushing headers. The
outer request exception handler then attempted a second response through the same
closed socket, producing the second traceback shown in the report.

JSON and artifact response handling now cover headers and body transfer. Expected
connection errors close that client connection without replaying the operation
or sending another error response. Other I/O/programming errors remain visible.
Failure to open an artifact is still reported before committing success headers.
An incomplete artifact stream closes instead of appending a second HTTP response.

A transport abort does not establish whether native compilation succeeded or
failed. Inspect retained job results and diagnostics. For long operations prefer
`/jobs/submit` followed by `/jobs/status` or `/jobs/wait`, rather than holding one
synchronous HTTP request until native work finishes. Disconnecting a client is
not a cancellation request.

## Recent Files isolation

The normal list is under the current user's
`Software\Blizzard Entertainment\StarCraft II Editor\Recent Files` registry
subtree. Isolating desktops, maps and TEMP alone did not isolate that list.

The startup bootstrap now redirects opens/creates of this exact subtree and its
children inside the owned Editor. Absolute paths and paths relative to an open
registry handle are resolved before matching; similarly named sibling keys are
not redirected. Both ANSI and Unicode Win32 callers reach the native hooks.
The target is a private `Software\SC2EditorToolkit\Workers\{instance-GUID}` key.
It is not populated with the user's history. Creation is volatile, as described
by [Microsoft's registry API documentation](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regcreatekeyexw).

Hook setup is required before resuming the owned Editor. If setup fails, startup
fails closed. The API removes only the validated GUID-scoped private key after
the exact owned PID/creation identity has exited. A crash can leave a volatile
key until its user hive unloads. Other general Editor preferences remain shared;
this is not full profile virtualization. Existing normal history is preserved,
including any temporary entries that were already there before this update.

## Startup diagnosis

The host now records failure phase, local Win32 error, remote thread result and
bootstrap error in `startup/state.json`. It checks the local startup DLL/export
before remote loading, and confirms the remote initialized module by its full
module entry instead of treating a truncated 64-bit module handle as a Boolean.

A document window that appears before its dispatch marker receives a continuous
15-second grace interval. Busy/loading states reset that interval. This removes
an immediate-failure race; it does not prove that this race caused the reported
intermittent failure on another machine.

API failures include `EDITOR_STARTUP_FAILED` evidence and retain a private
`startup-failure.json`. Available host, bootstrap, graphics and dispatch log tails
are bounded to 8 KiB each. Evidence-write failures do not replace the native cause.
There is no automatic retry. Keep these files when reporting a startup failure;
do not publish private maps, account data, tokens or complete runtime folders.

The reported intermittent startup cause remains unconfirmed until its logs are
available. Successful local starts are bounded regression evidence only.

## Reproduction

- `python -m unittest discover -s tests -p test_http_transport.py -v` exercises
  header/body aborts, artifact aborts and three real reset loopback POST requests,
  then checks service health and exactly one completion per request.
- `python -m unittest discover -s tests -p test_startup_evidence.py -v` checks
  bounded native failure evidence and rejects registry cleanup outside an owned
  GUID namespace.
- `scripts/test-native.ps1` includes real process-local registry redirection
  against disposable test keys and deterministic asynchronous startup timing.
- `tests/live_recent_files.py --map <map> --work <fresh-directory>` is opt-in.
  It opens, saves and compiles private copies in two successive owned workers,
  requires native writes in their private history keys, checks the unchanged
  normal history and source bytes, and verifies process/key cleanup.
- `tests/live_bootstrap_failure.py --native <binaries> --map <map> --work
  <fresh-directory>` deliberately omits the bootstrap DLL from a private host
  copy. It checks the real failure phase/code and the owned suspended child's
  cleanup; it is not a native compilation or rendering test.

## Recorded acceptance (2026-11-07)

The Python regression suite passed 131 tests. All ten native test executables
passed. The live history test completed two independent hidden workers; each
opened and natively saved a private map and generated/compiled Galaxy with no
compiler errors. Five native history values were observed in each private key.
The normal history and supplied source bytes were unchanged. Both processes and
their private keys were removed. Observation recorded zero visible owned windows,
foreground samples and input-desktop changes.

The missing-DLL test retained `load-local-bootstrap`, Win32 126 and the host log,
and verified that its suspended owned child exited. These results do not identify
the cause of the separate intermittent startup report awaiting logs. No new
Terrain quality or full Data-audit acceptance is claimed here.

API contract 1, native protocol 16 and the existing 31 MCP tools are unchanged.
Install the complete package and restart its worker to apply the new bootstrap.
