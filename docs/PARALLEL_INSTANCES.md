# Normal Editor and an owned hidden Editor

The toolkit can keep its own original Editor process separate from an existing
normal Editor. The Vulkan renderer is adapted from SC2GameToolkit's parallel
instance implementation. It translates only the **owned hidden Editor's** D3D9
calls and submits actual rendered GPU work without presenting a visible
swapchain. PNG capture reads the real Editor backbuffer.

Use the dated [validation record](VALIDATION.md) for the exact live-tested
scenarios. Hardware/driver support is specific to the tested machine; a Vulkan
backend is not a universal multi-instance guarantee.

## Isolation

- The host creates its own installed Editor child suspended. The bootstrap
  changes Create/Open requests for an allowlist of Editor singleton events,
  mutexes, shared sections and semaphores. Their suffix uses the owned instance
  GUID. No arbitrary kernel objects are renamed.
- The Editor's UI lives on its own `SC2Native-…` desktop. The technical renderer
  window is invisible on the input desktop, with activation vetoes. No
  `SwitchDesktop`, global input injection or user-window activation is used.
- The original installed EXE and DLL files stay unchanged. The DXVK DLL is
  loaded from the toolkit's private resources, never installed beside SC2.
- Native IPC checks exact PID, creation identity, GUI thread, HWND, document and
  protocol. One API/MCP process owns one worker. Separate servers have separate
  loopback endpoints, random tokens, Job Objects, instance GUIDs and artifacts.
  There is no first-window selection or general shared instance dispatcher.
- Each worker uses private map/mod copies, TEMP/TMP, renderer config, shader
  cache, logs and output files. Closing its API Job closes its own hidden tree.
  It does not close, inject into, save or send GUI commands to a normal Editor.
- This is not complete Windows-profile virtualization. General Editor user
  preferences may still share the Windows profile. Do not arrange for two
  editors to independently save the same source archive.

The named `StarCraft II Editor File` kernel object is isolated; that does not
grant permission to concurrently overwrite one map file.

## Portable Editor selection

No machine-specific Editor path is compiled into the host, controller, bridge or
capture helper. The API resolves a unique installation or accepts `editor_path`,
CLI `--editor`, or `SC2_EDITOR_PATH`. Each hidden child receives its selected
executable identity. Helpers compare that file with the exact owned PID's image;
the GUI thread still requires its private desktop and versioned startup marker.
Protocol 12 rejects older dispatch markers. Unsupported binaries fail before
launch; the supported UI adapter remains 5.0.17.98310 x64. See
[selection precedence and examples](../README.md#editor-installation-selection).

## Renderer selection

`/editor/start` accepts `render_backend: "auto" | "legacy" | "vulkan"`.
Requests that start a worker implicitly also accept this option. The shared MCP
argument schema exposes it without adding a new tool.

- `auto` (default): use the bundled DXVK renderer when present, otherwise system
  D3D9. A present but modified renderer fails validation; it never silently
  falls back.
- `vulkan`: require the pinned DXVK **3.1.1 x64** DLL. Missing or wrong SHA-256 is
  rejected before launching an Editor. Vulkan-capable hardware/drivers required.
- `legacy`: use system D3D9. It can fail with `0x88760868` while another SC2 owns
  incompatible display resources. That failure is reported, not hidden.

`SC2EDITOR_RENDER_BACKEND` supplies the startup default. A live worker keeps its
backend; explicitly requesting another backend requires restarting that owned
API/MCP worker. Selection and `instanceId` appear in startup/health/capture
results. Configuring a child never changes the parent's environment or the
normal Editor/game graphics settings.

Build a renderer-enabled package:

```powershell
.\build.ps1 -WithVulkan
.\package.ps1 -WithVulkan -Python '.venv\Scripts\python.exe'
```

The dependency fetcher pins the upstream release archive, x64 DLL and license.
Source distributions contain its manifest and full Zlib notice, not the binary.
The renderer-enabled EXEs include the verified DLL and notices in their private
resources. See [third-party notices](../THIRD_PARTY.txt).

## Reproduce the coexistence test

Open your normal Editor with a disposable map first, then obtain its exact PID.
The test only reads that process's captions, readiness flags, identity and
module list. It never launches or controls the normal Editor.

```powershell
.venv\Scripts\python.exe tests\live_coexistence.py --package `
  --visible-pid 12345 --template 'D:\Fixtures\Empty.SC2Map' `
  --map 'D:\Fixtures\Cameras.SC2Map' --map-camera 2001 `
  --roundtrip --work 'D:\FreshCoexistenceTest'
```

The test starts two owned sessions in sequence. It checks original XML → Galaxy
generation, native compilation, diagnostics, exact script downloads, isolated
shutdown/restart, rejection of the old token/artifact, optional save/reopen and
actual Terrain/scene PNGs. An external observer records foreground PIDs, visible
hidden-process windows and input desktop. The normal Editor remains open.

Optional cutscene coverage adds `--scene-template`, `--scene` and
`--scene-camera`. Tests use fresh private files and keep all maps, images, tokens
and raw observations outside Git. No toolkit DLL may already be present in the
normal Editor for the independent-baseline check.

## Reproduce simultaneous hidden workers

The separate 2026-10-23 test starts two API servers and two hidden original
Editors concurrently. It submits different XML fixtures at the same time,
checks exact native PID/result identities and downloads, rejects cross-server
tokens/artifacts, closes one Editor and compiles again in the survivor.
It observes existing Editors without controlling them.

```powershell
.venv\Scripts\python.exe tests\live_parallel_workers.py --package `
  --template 'D:\Fixtures\Empty.SC2Map' `
  --editor-path 'D:\Games\StarCraft II' `
  --map 'D:\Fixtures\Cameras.SC2Map' --map-camera 2001 `
  --work 'D:\FreshConcurrentWorkersTest'
```

Omit `--map` for compilation/isolation-only coverage. With a map, one worker
captures the native saved-camera Terrain view while the other compiles. A pass
applies to two independent owned workers, not an arbitrary number of instances.
See [presentation readiness](PRESENTATION_READINESS.md) for the tested scope and
remaining feature limits.
