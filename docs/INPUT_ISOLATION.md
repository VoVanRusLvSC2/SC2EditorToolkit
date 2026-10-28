# Input isolation

The toolkit loads its DLLs only into the original Editor process created by its
hidden host. It does not attach to `SC2_x64.exe` or `SC2.exe`, install mouse or
keyboard hooks in the game, send physical input, or switch the input desktop.
GUI dispatch hooks use the current owned Editor thread ID, never thread ID zero.

The startup export additionally verifies the current executable's file identity,
the selected `SC2Editor_x64.exe` name, and the private `SC2Native-` desktop before
installing hooks or starting a rendering thread. Loading the DLL alone does not
install hooks. An unrelated executable or an ordinary visible Editor is refused.

The invisible render thread uses the input desktop for graphics compatibility.
Consequently, forwarding D3D cursor commands would be unsafe even with an
invisible window. Wrapped D3D9 and D3D9Ex devices now discard cursor positioning,
cursor bitmap changes, and show/hide requests. Their cursor remains logically
hidden. These overrides affect only the owned Editor's device vtables; the game
and its graphics devices are untouched.

## Verification

`scripts/test-native.ps1` tests both D3D device ABIs without invoking a driver or
input API, checks that unrelated vtable slots remain unchanged, rejects unrelated
executables even with a forged environment and private desktop, and exercises
thread-local dispatch and hook cleanup.

For a built startup DLL, the identity test also supports a negative integration
check:

```powershell
EditorIdentityTests.exe <original-editor-exe> <absolute-startup-dll-path>
```

It loads the candidate DLL into the test executable and verifies that its real
startup export returns `ERROR_ACCESS_DENIED` without installing patches.

These checks do not simulate gameplay. A read-only module inventory can confirm
that no toolkit DLL is loaded in a running game without sending it any input.
Already running workers retain their loaded DLLs: installing a new build requires
restarting those workers through their owner. Never replace DLLs in a running
worker or stop an Editor owned by another session to apply this change.

### rc.2 checks (2026-10-28)

- 122 Python tests and eight native test executables passed.
- The built startup DLL refused its real initialization export in an unrelated
  test process on a private desktop, with zero installed patches.
- An owned hidden Editor opened a private map in Triggers and produced two
  original nonblack Terrain captures. Source bytes were unchanged, and artifact
  downloads matched their hashes. Observation recorded zero visible owned
  windows, foreground samples or input-desktop changes. The test worker closed.
- Read-only inspection before and after the test found no toolkit DLL in the
  same running `SC2_x64.exe` game process. Gameplay input itself was not driven
  or recorded by this test.
