# Presentation readiness — 2026-10-23

Scope: **v0.12.0-rc.1** map/filter acceptance, with separately dated
**v0.11.0-rc.1** portable/media and **v0.10.0-rc.1** baseline evidence; original SC2 Editor
**5.0.17.98310**, DXVK 3.1.1 and the installed test machine/dependencies.
This is a prerelease developer toolkit. Demonstrate the verified workflow;
do not describe every experimental operation as production-complete.

## What the product does

The toolkit starts a separate original Editor, operates its native generator,
compiler and renderer through a bridge DLL, and exposes results through HTTP
and MCP. Editor UI stays on a private Windows desktop; the technical render
window remains invisible. No physical mouse/keyboard automation is required.
It uses an interactive Windows session and GPU; it is not a GPU-free or
session-independent Windows service.

One API/MCP server owns one persistent hidden Editor. Multiple independent
servers use different work directories, loopback ports, random tokens, instance
GUIDs, singleton allowlist suffixes, IPC identities, private documents and
renderer caches. Requests within one worker are serialized; separate workers
can perform independent operations concurrently. There is no shared worker pool
or general job queue.

The 2026-10-21 live test verified an already-open normal Editor beside the hidden
worker, including hidden-worker restart. The normal process/document/window
remained unchanged, no toolkit bridge was loaded into it, and it was left open.
That was a read-only preservation check, not automated interactive editing of
the normal Editor. See the dated [validation history](VALIDATION.md).

## v0.12.0-rc.1 map and filter acceptance on 2026-10-23

The complete native overhead exporter and its independent unit/doodad model
filters are ready for a scoped technical demonstration. The fix writes the
original flag model rather than only painting its checkboxes. Native model IDs
are resolved through the exact tree item, independently of sorted row positions
or Win32 item metadata; readback and custom mode are required before publication.

| Check | Result |
|---|---|
| Python / native C++ suites | 66 Python tests / 4 native C++ suites PASS |
| Packaged HTTP / MCP | PASS; the existing 18 tools, no added MCP tools |
| Native visibility matrix | All, units off, both off, doodads off, then both restored PASS in one persistent map |
| Independent worker | Separate owned Editor exported both categories off while the first exported all models; distinct instance IDs and correct images |
| Geometry acceptance | Six building/doodad regions compared with an independently rendered private copy with placements removed; disabled geometry matches the empty reference; known broken old output correctly fails |
| Image sizes | 512×384, 1024×768, 2048×1536 and 4096×3072 PASS on the 64×48 fixture |
| Full-resolution objects | Additional 4096×3072 capture in the second worker: buildings, ten Marines and four doodads visually confirmed; six geometry regions and exact TGA/PNG/download checked |
| Saved-object filters | Query, kinds, owner, inclusive XY bounds and pagination PASS; 14 units and 4 doodads; no Editor needed for search |
| Compile / Galaxy / Console | Original generation and compilation: 0 compiler errors; exact Galaxy download; actual Editor log readable, complete and clear |
| Background | 22,715 recorded per-worker observations: zero owned foreground samples, visible windows or input-desktop transitions; no input injection or desktop-switch calls |
| Preservation / cleanup | Source and installed-Editor hashes unchanged; both owned test Editors closed; existing Editor processes uncontrolled |
| Package | Exact tested native files and pinned renderer embedded in both EXEs; unused build-machine NumPy/BLAS excluded |

This fixture has textured relief and native placements but no water. A dedicated
water case and a broader map/dependency matrix remain outside this acceptance.
The southwest crop visibly contains Command Center, while general region
calibration retains its explicit experimental status. Earlier portable selection,
normal-Editor coexistence, cutscene/audio and larger Nydus evidence remain scoped
to their dated sections below; they are not fresh v0.12 media tests.

For a live demo, warm the map exporter before presenting. The first exports here
took about 209–219 seconds; subsequent same-map captures took about 10–12 seconds.
Omit `map` on repeated requests to reuse the current private document. Opening a
different map can require another native loading period. Use the complete
protocol-13 package and restart workers when upgrading.

## v0.11.0-rc.1 portable acceptance on 2026-10-23

The core is ready for a technical demonstration as a prerelease. Editor selection
has no fixed drive or user path: choose by discovery, `SC2_EDITOR_PATH`, server
CLI `--editor`, or request `editor_path`. Multiple distinct installations require
an explicit choice; missing, modified, x86 and unsupported binaries fail before
launch. The verified adapter remains original 5.0.17.98310 x64. This is path
portability, not automatic adaptation to untested Editor builds/locales.

| Check | Result |
|---|---|
| Python / C++ suites | 65 Python tests / 4 native C++ suites PASS |
| Packaged HTTP/MCP | PASS; 18 tools; missing/unsupported Editor rejected without starting it; MCP readonly operations work with no installed selection |
| Direct native path selection | Host, primary GUI-thread attachment and controller PASS through an installation alias containing Unicode/spaces, without a fixed default-path comparison |
| Concurrent packaged workers | Two owned Editors, CLI selection for A and request selection for B; six original native conversions, zero compiler errors, exact Galaxy downloads |
| Isolation/lifecycle | Cross-token 403, foreign-artifact 404, different process/instance identities; close A then compile/export in B PASS |
| Native media | Saved-camera Terrain PNG while B compiles, Nydus-derived scene frame and H.264/AAC clip at 990..1980 ms PASS; cue required to be non-silent, video/audio full decode and download verified |
| Background | 2,002 external samples, 1,912 with both owned Editors alive; zero visible hidden windows, owned foreground samples or input-desktop changes |
| Cleanup/inputs | All test-owned Editors closed; both pre-existing Editor processes left running and uncontrolled; input/installed executable hashes unchanged |
| Package contents | Both EXEs contain the exact tested native files and pinned DXVK DLL/license/manifest |

The alias test does not physically relocate installed assets or certify separate
Battle.net asset profiles. General Editor preferences can still be shared.
Upgrade the complete matching package and restart owned workers: native protocol
12 deliberately rejects protocol-11 dispatch markers.

## Published v0.10.0-rc.1 baseline rechecked on 2026-10-23

The local API/MCP EXEs match the published v0.10.0-rc.1 ZIP byte for byte. The
ZIP SHA-256 matches GitHub's asset digest. Tests start only new owned processes
and use private archive copies; already-running Editor/MCP sessions are not
controlled.

| Check | Result |
|---|---|
| Python / C++ tests | 57 Python tests and 3 native C++ suites PASS |
| Packaged HTTP / MCP | PASS; 18 existing MCP tools |
| Simultaneous original Editors | Two owned hidden workers in separate API servers PASS; two pre-existing Editors remained running |
| Concurrent native generation/compilation | Six total conversions, including overlapping A/B submissions and survivor compilation; zero native compiler errors |
| Request/result isolation | Unique process/instance identities, different marker scripts, exact Galaxy downloads; cross-server tokens rejected with 403 and foreign artifacts with 404 |
| Render plus compile | Native saved-camera Terrain rendering in worker A while worker B compiles PASS; real relief, Command Center, Marines and doodad visually confirmed |
| Independent shutdown | Close worker A, then generate/compile/export again in B PASS; all test-owned Editors subsequently closed |
| Messages/Console | Readable and complete, empty in the inspected parallel fixture sessions; compiler diagnostics kept separate |
| External observations | 1,435 samples, 1,350 with both test Editors alive; zero visible hidden windows, hidden foreground samples or input-desktop changes |
| Nydus v54 native compilation/export | PASS; 342,851-byte Galaxy, zero compiler errors, exact file/HTTP export |
| NydusIntroBlue cameras/time | Four actual frames: Front Formation Camera at 990/1980/2970 ms and Top at 1980 ms; native readback, changed/visually reviewed frames, bad-camera rejection PASS |
| MP4/native audio | Original scene short range and a private derivative with Marine_Ready cue; H.264/AAC decode, camera/range changes, repeat export and audio-pass cancellation PASS |
| Native PCM preservation | AAC/PCM envelope correlation 0.997786; timing difference about -0.62 ms on the private cue fixture |

The existing two Editors were observed for process liveness only; their native
operations were not exercised or controlled by this test. No unlimited-instance
or long-duration stress-test claim follows from their presence. Source archive
and installed-Editor hashes stayed unchanged. The Terrain test used a saved map
camera, not whole-map export or trigger-driven gameplay.

## Recheck before a demonstration

- Use the complete matching package; do not mix bootstrap/bridge/controller files.
- Keep the original Editor build and map dependencies used by the demo installed.
- Use separate private copies/work directories for independent workers. Do not
  arrange concurrent saves to one original archive.
- Vulkan-compatible drivers are required for the bundled parallel renderer.
  `render_backend: "auto"` selects the pinned bundled renderer. `legacy` uses
  system D3D9, which previously failed with parallel SC2 display resources.
- Warm up the map/Terrain and scene before presenting. Native first-time resource
  loading can take minutes. Use a sufficiently long client timeout; do not kill
  an in-progress native callback to simulate cancellation.
- FFmpeg/ffprobe and an available Windows audio output endpoint are separate
  requirements for video/audio. They are not bundled with the toolkit.
- Export is offline and can take longer than the clip duration. Prepare a short
  pre-exported demo clip as well as showing job progress for a live export.
- Keep API tokens, runtime logs and user maps/scenes out of public source and
  demonstration screenshots.

## Limits to state accurately

- This is not full Windows-profile virtualization. General Editor preferences
  may still share the Windows profile.
- Native compilation verifies generated Galaxy syntax/type checks; it does not
  prove gameplay behavior or complete GUI semantic equivalence.
- Messages/Console reads expose the Editor's actual text. Classification is
  interpretation of that text; unreadable/truncated output remains unknown,
  not zero errors. Opening Data is not an exhaustive engine validator.
- Saved map-camera framing is implemented. Executing Galaxy triggers to play a
  gameplay cinematic and arbitrary Terrain camera overrides are not implemented.
- Whole-map model filters have passed the scoped v0.12 acceptance above.
  A water-specific case and broader map/dependency coverage remain unverified.
  Region crops retain experimental native XY-to-image calibration status.
- HTTP video export supports progress/cancellation endpoints; the current MCP
  stdio export call is blocking and exposes no separate progress/cancel tools.
  General native operations do not
  have a safe cancellation/deadline API or queued scheduling.
- Two verified workers do not establish an unlimited instance count, acceptable
  performance on every map, or support for every Editor build/GPU/driver.

## Suggested demonstration

1. Keep a normal Editor open, then start the toolkit on a private demo map. Show
   that the normal document remains usable while the hidden worker handles API
   requests. Do not expose its token.
2. Submit complete GUI Triggers XML, obtain original Galaxy, invoke the original
   compiler, read compiler errors separately from Messages/Console, and download
   the exact generated script.
3. Select a saved map camera and show the real Terrain PNG with placed objects.
4. Load a cutscene, select its camera/time, and show the original rendered frame.
   When video/audio prerequisites are available, demonstrate a short MP4 range.
5. For parallel operation, start a second API/MCP server with its own work
   directory and port. Submit different marker fixtures concurrently, compare
   the scripts, then close one owned worker and show the other still compiles.

For the map demo, show the full image, independent unit/doodad exclusion and
restoration using [the map-export guide](MAP_EXPORT.md). Keep the same map loaded
for repeated captures.
Use [parallel-instance setup](PARALLEL_INSTANCES.md) and opt-in live tests to
reproduce the exact scope instead of making a general stability claim.
