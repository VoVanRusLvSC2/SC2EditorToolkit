# SC2 Editor Toolkit

A modular automation toolkit for the **original StarCraft II Editor**, using its
native generator, compiler and renderer through a DLL, HTTP API and MCP.
Previously published as SC2 Native Toolkit. Original code author and project
owner: **VoVanRusLvSC2**.

**Development 1.1.0-rc.2 adds cursor isolation for the hidden Editor to the Terrain camera and native field-value features introduced in rc.1.** See [input isolation](docs/INPUT_ISOLATION.md), [camera parameters](docs/MAP_EXPORT.md) and [field-value coverage](docs/DATA_AUDIT.md). Replace the complete package and restart its worker when updating. [Download 1.1.0-rc.2](https://github.com/VoVanRusLvSC2/SC2EditorToolkit/releases/tag/v1.1.0-rc.2). The latest stable 1.0 release remains available below.

**v1.0.0 provides a versioned MCP/HTTP contract for the original Editor, indexed Data audits, incoming object references, audit comparison and installation preflight.**
Read inherited/overridden values, search native Object Explorer associations,
and check the selected Model's main file through the original Archive Browser
and native diagnostics. Jobs support status, cancellation, deadlines and recovery.
See [the 1.0 MCP contract](docs/MCP_CONTRACT.md), [indexed audit queries](docs/DATA_AUDIT.md),
and [jobs and reports](docs/JOBS_AND_REPORTS.md),
[Data and resources](docs/DATA_AND_RESOURCES.md), and
[map export and object filters](docs/MAP_EXPORT.md).
[Download v1.0.0](https://github.com/VoVanRusLvSC2/SC2EditorToolkit/releases/tag/v1.0.0).

Editor installation discovery and explicit selection remain portable.
There is no fixed drive or user-specific Editor path. Use automatic discovery,
`SC2_EDITOR_PATH`, CLI `--editor`, or the startup API/MCP `editor_path` argument.
The supported original binary is verified before launch; changing a live worker's
installation requires restarting its server. Development native protocol 16 requires the
matching complete package. See [presentation readiness](docs/PRESENTATION_READINESS.md).

Vulkan offscreen rendering for an owned second Editor is included.
The renderer-enabled package uses pinned DXVK 3.1.1 for the hidden process,
without acquiring a visible display swapchain. Existing singleton isolation,
owned-thread native dispatch, original XML generation/compiler and private
document copies remain in use. The normal Editor/game is not attached to or
controlled. See [parallel instances](docs/PARALLEL_INSTANCES.md),
[native startup dispatch](docs/NATIVE_DISPATCH.md) and the dated
[validation history](docs/VALIDATION.md) for actual acceptance and limits.

The original full-map export supports terrain and native visibility filters for
placed unit/doodad models. Coordinate-region cropping retains its separate
experimental calibration status. A water-containing campaign map has also
passed native export and visual review; broader map/water variants retain their own validation scope. Saved map cameras can drive original Terrain PNG captures.
Explicit Terrain camera overrides use the original Camera Editor and fresh native readback. Galaxy-trigger playback still requires the game.
Operation-scoped load/Data diagnostics and native save/reopen component comparison
are available. See
[validation history](docs/VALIDATION.md). The stable API/MCP contract is version 1; see [the contract and setup guide](docs/MCP_CONTRACT.md) and [1.0 acceptance](docs/V1_ACCEPTANCE.md).

The installed Editor runs on an owned, private Windows desktop. Its technical
render window stays invisible. Operations do not inject mouse/keyboard input or
call `SwitchDesktop`; you can keep using your computer.

## MCP 1.0 workflow

Run `sc2_doctor` first. Submit long native work with `sc2_submit_job`, then use
status/wait/cancel. A completed audit returns `reportId`: read bounded observations
with `sc2_query_audit`, find incoming typed references with `sc2_find_object_uses`,
and compare two revisions with `sc2_compare_audits`. These three operations read
immutable local evidence without starting an Editor. HTTP equivalents are
`POST /doctor`, `/data/audit/query`, `/data/audit/uses`, `/data/audit/compare`.

Each tool has its own validated schema. Responses include `outcome`; failures
include a stable error code and next step. Job SUCCEEDED means execution finished,
so check validation/compilation and coverage fields separately. See the
[contract](docs/MCP_CONTRACT.md) for installation, compatibility and limitations.

## License and attribution

The [SC2 Native Toolkit Attribution License](LICENSE) permits using and modifying
the code while preserving authorship. Products and public services using a
substantial part of it must include **Uses SC2 Native Toolkit by VoVanRusLvSC2**
and a link to this repository in documentation, About, or credits. See [NOTICE](NOTICE).
This requirement applies to the code, not to exported user maps, scripts or videos.
Third-party components retain their own licenses: see [THIRD_PARTY.txt](THIRD_PARTY.txt).

Public documentation, setup instructions and release notes are maintained in **English**.

For integration with ModKit, see the [five-point native bridge assessment](docs/MODKIT_BRIDGE_STATUS.md).
It distinguishes existing original-Editor checks from fast ModKit previews,
saved map-camera framing, remaining camera controls and validation coverage.

## Modules

| Module | Implemented capabilities |
|---|---|
| Jobs | Per-server FIFO, progress, cancellation, deadlines, persisted history and fresh-worker recovery |
| Data | Full effective catalog traversal and original field-value serialization, exact field queries/diffs, typed catalog/file checks with coverage gaps and downloadable JSONL; XML identity and Explorer associations |
| Editor | Revision-bound check report, hidden startup, private map/mod copies, new load/Data diagnostics, native save → close → disk reopen and component comparison |
| Triggers | Original `Triggers XML → Galaxy` generation and native compilation |
| Galaxy | Exact `.galaxy` bytes, SHA-256, artifact download, overwrite protection |
| Objects | Search saved placements by ID/type/name, kind, owner and XY rectangle; no Editor needed |
| Terrain | Current viewport, saved-map-camera or explicit XYZ/angle/distance/FOV PNG with native readback; complete overhead PNG with independent unit/doodad filters; experimental coordinate-region crops |
| Cutscene | Load `.SC2Cutscene`, select camera/time, export PNG and H.264/AAC MP4 |
| MCP | Windowed stdio executable exposing the same worker operations |

Generation and compilation use the **original installed Editor**, not a replacement
Galaxy emitter. Worker readiness accepts the loaded document in Triggers, Terrain
or another supported document module. Activity, disabled workspaces, Script Test,
wrong documents and exited processes do not establish readiness. Startup defaults
to the original `-modtrigger`; `/editor/start` also accepts
`startup_module: "terrain"` or `"default"` (the Editor's saved choice).

## Requirements and downloads

Download the Windows x64 ZIP from [Releases](https://github.com/VoVanRusLvSC2/SC2EditorToolkit/releases).
Extract it into a writable directory. Keep LICENSE, NOTICE and third-party notices.

Required:

- Windows x64 with an interactive user session.
- The original x64 SC2 Editor in any local installation directory; discovery and
  explicit path selection are described below.
- The map/mod's actual dependencies installed locally. The tested adapter targets
  Editor **5.0.17.98310**, using D3D9. Other builds require validation.
- For MP4: separately installed **FFmpeg and ffprobe** on PATH, or the
  `SC2_FFMPEG` and `SC2_FFPROBE` environment variables. They are not bundled.
- For native audio: an available Windows output audio endpoint.
- For legacy rendering: an available system D3D9 device. Device loss or another
  application's display mode may prevent hidden startup/export. The toolkit
  reports failure; it does not change your game's mode or take over your input.

The renderer-enabled package additionally requires a compatible Vulkan driver.
`render_backend: "auto"` uses its pinned bundled renderer when present;
`"legacy"` selects system D3D9 and `"vulkan"` explicitly requires DXVK. The
backend is fixed for the owned worker's lifetime. Detailed coexistence and build
instructions are in [parallel instances](docs/PARALLEL_INSTANCES.md).

## Editor installation selection

Selection order is request `editor_path`, server CLI `--editor`,
`SC2_EDITOR_PATH`, then discovery through Windows registry install/uninstall
records, Program Files environment locations and PATH. Explicit selection accepts
either the original `SC2Editor_x64.exe` or its installation/Support64 directory.
Paths with spaces and Unicode are supported. Multiple distinct installations
require an explicit choice; a bad explicit path never falls back to another one.

```powershell
.\SC2NativeAPI.exe serve --port 0 --work 'D:\SC2WorkerA' --editor 'D:\Games\StarCraft II'
.\SC2NativeMCP.exe --work 'D:\SC2WorkerB' --editor 'D:\Games\StarCraft II'
```

Alternatively set `SC2_EDITOR_PATH`, or start through HTTP/MCP with:

```json
{"template":"D:\\Fixtures\\Empty.SC2Map","editor_path":"D:\\Games\\StarCraft II"}
```

This is path portability, not unverified support for every Editor version or
language. The adapter currently supports the original **5.0.17.98310 x64** binary
and verifies its SHA-256 before launch. Native components additionally check
version, architecture and the selected file's identity. Other builds need adapter
validation; they fail explicitly instead of receiving commands intended for the
tested UI. A complete valid installation is required; the original Editor
resolves its game assets and dependencies. Selection does not virtualize its
Windows/Battle.net profile or certify physically distinct asset installations.

`SC2NativeAPI.exe` is a local HTTP server without a console window.
`SC2NativeMCP.exe` serves MCP stdio when launched by a client with inherited pipes.
The Editor starts lazily on the first operation requiring a map or mod.

## HTTP quick start

Start `SC2NativeAPI.exe`, or run it with explicit options:

```powershell
.\SC2NativeAPI.exe serve --work 'D:\SC2NativeToolkit-data' --port 8765
```

By default the server listens on `http://127.0.0.1:8765`. `api-data/api-info.json`
next to the EXE contains the address and a random token. With `--work`, it is
written to that directory. Keep the token private. Requests other than `/health`
require `X-SC2-Token`; browser Origin requests are rejected.

```powershell
$api = Get-Content 'D:\SC2NativeToolkit-data\api-info.json' -Raw | ConvertFrom-Json
$h = @{'X-SC2-Token'=$api.token}
function Call-SC2($route, $value) {
  $body=[Text.Encoding]::UTF8.GetBytes(($value | ConvertTo-Json -Depth 12))
  Invoke-RestMethod ($api.url+$route) -Method Post -Headers $h `
    -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 1200
}
Call-SC2 '/editor/start' @{template='D:\MyMod.SC2Mod'}
$checked=Call-SC2 '/triggers/compile' @{scope='library:810D62ED'}
$export=Call-SC2 '/galaxy/export' @{output='D:\Native.galaxy'}
```

Editor jobs are serialized per worker. A concurrent editor request is rejected as
busy. Large maps and native rendering can take minutes; use at least a 1200-second
client timeout. Video exports can need longer. Do not terminate a native request
handler while it is still executing inside the Editor.

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Server version, worker state and busy flag |
| GET | `/modules` | Implemented capabilities |
| POST | `/editor/start` | Hidden startup with a `template` map/mod |
| POST | `/open` | Load a private copy supplied as `map` |
| POST | `/convert` | Complete XML + template → native Galaxy; compile by default |
| POST | `/triggers/compile` | Generate and compile the current native triggers |
| POST | `/galaxy/export` | Export the last verified generated script |
| GET | `/artifacts/<id>` | Download an artifact's exact bytes |
| POST | `/editor/diagnostics` | Read Messages/Console controls |
| POST | `/data/audit` | Traverse all effective native catalogs and check typed references/files with explicit coverage gaps |
| POST | `/editor/validate` | Load a private map/mod and original Data module; return new native messages by phase |
| POST | `/editor/save-reopen` | Native Save As → Close → disk reopen, diagnostics and component hashes/diffs |
| POST | `/terrain/capture` | Capture the current original Terrain viewport |
| POST | `/terrain/cameras` | List saved map camera IDs, names, targets and original parameters without starting Editor |
| POST | `/terrain/export` | Export the complete map overhead with native units/doodads |
| POST | `/objects/search` | Search saved placements and return original XYZ without starting Editor |
| POST | `/terrain/region` | Experimental coordinate rectangle crop of the original overhead export |
| POST | `/cutscene/open` | Open the module and optionally import a scene |
| POST | `/cutscene/seek` | Select a unique native camera and time |
| POST | `/render/capture` | PNG of the selected cutscene frame |
| POST | `/cutscene/export` | Export a full scene or time range to MP4 |
| GET | `/cutscene/export/status` | Video job progress |
| POST | `/cutscene/export/cancel` | Request video job cancellation |
| POST | `/shutdown` | Close the API and its owned Editor |

## Triggers XML and Galaxy

```json
{"template":"D:\\MyMod.SC2Mod","triggers_file":"D:\\Triggers.xml",
 "scope":"library:810D62ED","compile":true}
```

Send this to `/convert`. Alternatively pass complete UTF-8 XML as `triggers_xml`.
Without either field the API extracts the template's existing Triggers XML.
The template preserves dependency context and localization. For the currently
loaded document use `/triggers/compile` without supplying replacement XML.

Omitting `scope` selects the sole authored library, or `mapRoot`. If labels are
ambiguous, supply `context_label` as the exact authored root category/library name.
Native compilation and generation are separate confirmations. Compiler errors are
under `diagnostics.compilerErrors`; Editor messages are under `diagnostics.editorLog`.
An unreadable log has `clear:null`, not a fabricated zero-error result. Existing
messages are retained. `/galaxy/export` returns exact native bytes and a SHA-256.
Existing files require `overwrite:true`.

## Full Data audit

`POST /data/audit` or MCP `sc2_audit_data` walks all 109 original native catalogs in the opened map/mod and loaded dependencies. It follows original getters through arrays and nested structures, checks typed catalog targets against effective native entries, and checks typed file paths in the original merged Archive Browser. The input archive is preserved.

Use a queued `audit_data` job for large projects. The result contains per-catalog counts, explicit coverage gaps, missing reference/file findings, a SHA-256 revision, and downloadable JSONL objects/findings plus a JSON summary. Full traversal does not imply complete semantic validation: opaque types, unresolved tokens, actor command strings and runtime-computed references remain explicit limitations. See [Data audit](docs/DATA_AUDIT.md).

## Native map/Data checks and save/reopen

```powershell
$check=Call-SC2 '/editor/validate' @{map='D:\MyMod.SC2Mod'}
$roundtrip=Call-SC2 '/editor/save-reopen' @{
  map='D:\MyMod.SC2Mod'; include_diffs=$true; output='D:\NativeSaved.SC2Mod'
}
```

MCP equivalents are `sc2_validate_document` and `sc2_save_reopen`. Both accept a
saved `.SC2Map` or `.SC2Mod`, preserve its original bytes and operate on a unique
private copy. If no map is supplied, the current worker's saved archive is used.
An optional `baseline_template` supplies a healthy startup document when testing
a failing archive. No user Editor is attached or controlled.

Each native phase retains complete bounded before/after Messages/Console snapshots
and observed output mutations. `phases[].diagnostics` separates `baselineMessages`
from `newErrors`, `newWarnings` and `unclassifiedMessages`. A repeated identical
append still counts as new. Types and related IDs are interpretations of explicit
Editor text; absent IDs remain empty. Unreadable, truncated, reset or ambiguous
logs yield `newErrorsClear:null` / `newErrorCount:null`, never a certified zero.
The GUI is pumped for 300 ms after each synchronous command for posted log updates;
messages arriving outside that window are not certified as part of that operation.
Startup output is marked `freshOwnedSession` when a new owned worker was created.

Opening Data exercises the original module and collects its output. This is not
an exhaustive catalog, asset or gameplay validator: the Editor can silently accept
some invalid parent/field/model references during opening. Compiler results remain
separate from map/Data diagnostics.

Save/reopen invokes the original **File → Save As**, confirms a clean saved
document and nonempty archive, then **File → Close** and original **File → Open**.
It verifies that the saved document's windows disappeared before reopening;
switching to an already open document does not count as a disk reopen. The same
owned Editor is reused. Every MPQ member enumerated by mpqcli is read by its locale
and name and hashed before saving, after saving and after reopening. Archive
metadata changes are reported too; saved-to-reopened equality is checked separately
from expected native serialization changes. Unknown/unreadable members fail the check.

`componentDiffArtifact` downloads the full comparison JSON, including optional UTF-8
diffs (`include_diffs:true`, bounded to 200 lines/64 KiB per member and 1 MiB total).
Binary/large components retain exact byte sizes and hashes. If reopening fails
after saving, the before-to-saved comparison is still available. `savedArchive`
and optional `output` are published only when the whole check is verified and
native diagnostics are known clear. Existing output requires `overwrite:true`;
source and baseline archives cannot be export targets. All phases include the
archive revision hash being checked. Raw evidence remains local to the worker.

## Conversion failure reporting

Failed conversions return `failureKind`, `failureStage` and `failureEvidence`.
Available native/controller diagnostics remain in `failureNative`; missing
native evidence is unknown, not zero errors. Controller setup failures preserve
their exit code and stderr. A failed startup resets only its owned Editor.

A new conversion/open/compile attempt invalidates the previous Galaxy export.
If fresh generation succeeds but compilation reports errors, its new script
can still be inspected/exported with `nativeCompilePassed:false`.

The diagnostic recovery implementation uses original Save As on a fresh private
archive before generating a dirty document. It refuses native serialization
that discards submitted typed GUI identities and retains the comparison report.
Generation's saved-document guard remains enabled. This does not certify full
GUI semantic equivalence or repair the submitted XML. **Acceptance of this
recovery sequence is recorded in the dated validation history**. A historical Win32 126 startup failure is not a current blanket blocker; fresh installation failures must be diagnosed with `sc2_doctor` and native evidence.

## Saved map cameras

`POST /terrain/cameras` (MCP `sc2_list_map_cameras`) reads saved `ObjectCamera`
records from a `.SC2Map` archive. It returns exact `cameraId`, name/reference,
placement position, separate `CameraTarget` XY, original `CameraValue` entries
and attributes. Optional `locale` (default `enUS`) resolves GameStrings references.
This read-only operation does not start an Editor.

Use an ID from that list with existing `/terrain/capture` / `sc2_capture_terrain`:

```json
{"map":"D:\\MyMap.SC2Map","map_camera_id":"2001","output":"D:\\Camera.png"}
```

The owned original Terrain module selects the exact camera palette entry and
invokes **View Selected Camera**. **Get Game Camera** reads back its actual
target, pitch/yaw/roll, distance and FOV. Target XY and available saved core
parameters must match before a PNG is published. UI readback is rounded; target
tolerance is 0.02 map units and scalar/angle tolerance is 0.11 native UI units.
Other saved parameters remain explicitly listed as unverified by readback.
Duplicate IDs/names, unsupported/missing targets, missing native controls,
parameter mismatches and black/uniform frames fail instead of returning a
different/default camera. The current adapter targets the tested English UI
of Editor 5.0.17.98310. Source archives are preserved.

Omit `map` on later captures to reuse this worker's current map and select another
`map_camera_id` without reloading it. A `.SC2Mod` has no Terrain. Cutscene `camera`
and `time_ms` arguments remain separate and are rejected for Terrain capture.

This evaluates the **saved camera's framing and editor placements**, using the
current native Terrain viewport resolution/aspect. It does **not** play a
trigger cinematic: Galaxy execution, trigger-created units/cameras, camera
interpolation over time and gameplay animation/state require a separate game
test. Responses explicitly return `triggerExecution:false` and
`timelineControl:false`; a successful static shot does not certify a running
trigger movie.

## Complete overhead map image

`POST /terrain/export` or MCP `sc2_export_map_image` uses the original **Data →
Export Map Image** operation. The owned worker selects **Full** bounds, **All**
quadrants, a **90°** camera, game lighting, standard shading, water and shadows.
Placed **units and doodads are included by default**. Fog effects and editor
helper/overlay models are disabled so the map's surface remains visible.

**Scoped live acceptance:** a corrected private fixture produced a detailed
1024×768 native image showing both hills, four corner buildings, ten Marines and
four doodads. Native component registration, Objects.version and preloads must be
valid; writing placement XML alone is insufficient. Water and a broader map
matrix remain untested. Detailed-pixel checks alone cannot prove model presence.

```json
{"map":"D:\\MyMap.SC2Map","size":2048,"output":"D:\\WholeMap.png"}
```

This request can start the hidden Editor itself. Omit `map`/`template` to export
the currently open `.SC2Map`. `size` is the horizontal pixel resolution: 512,
1024, 2048 (default), or 4096. The original full bounds determine height and
preserve the map aspect ratio; the native dialog selected 2048×1536 for a 64×48 map.
Images above 8192 pixels in height or 32 million total pixels are rejected.

The `include_units` and `include_doodads` booleans independently select native
unit and doodad models. The adapter uses the original flag-model setter/getter;
painted checkbox state alone is insufficient. Native model IDs are resolved
through the exact tree item, independently of row order or Win32 item metadata.
The response's `objectFiltersVerified:true` requires matching native readback
and custom export mode. Terrain-derived effects such as creep may remain when
unit models are hidden. See [map export](docs/MAP_EXPORT.md).
`output` is optional; an existing PNG requires `overwrite:true`.
The response contains the full PNG artifact/download/SHA-256 and a preview bounded
to 1280 pixels for MCP. `wholeMapVerified:true` requires native export completion,
confirmed Full/All/90° settings and object flags, detailed pixels, unchanged source archive and the
hidden desktop invariant. Black/uniform exports fail rather than being published.

The Editor writes an original private TGA. Its decoded RGB pixels are encoded
losslessly as PNG; no terrain or model rendering is reimplemented. The result is
independent of the current viewport camera and is not a minimap-texture upscale.
The private TGA hash and native report are retained as evidence. The source map
is neither imported into nor overwritten by the export. A `.SC2Mod` has no surface.

Install the map's actual asset dependencies. Export is configured for placed units
and objects resolved by the original Editor; units created only by runtime
triggers require a running game and are outside this static map export.

## Search saved map objects

`POST /objects/search` or MCP `sc2_search_objects` reads a private snapshot of the
saved `.SC2Map` archive. **It does not start or require an Editor.** Supply `map`
or `template`, or omit it to query this worker's current saved map. Unsaved live
Editor changes are not included.

```json
{"map":"D:\\MyMap.SC2Map","query":"Marine","kinds":["unit"],"owner":1,"limit":50}
```

`query` is a case-insensitive substring over saved ID, XML type, name/reference
and object key. `kinds` accepts `unit`, `doodad`, `point`, `camera`, `other`;
points/cameras are returned only when represented by placement records in
`Objects`. Separate region/camera documents are not indexed. Optional `bounds`
uses the same XY rectangle as region capture. `limit` defaults to 100 (max 500),
`offset` defaults to zero; follow `nextOffset` until null.

Each result includes the original ID, kind, type, saved name/reference, owner
when present and `position:{x,y,z}`. XYZ is the **saved placement**, and Z can be
a terrain-relative placement offset rather than absolute surface elevation.
Missing/invalid positions remain null and are counted in `objectsWithoutPosition`;
they cannot match a bounds filter. Names are not resolved through localized
GameStrings. Runtime-created units and inherited dependency placements are excluded.

The response includes source SHA-256, `sourceUnchanged`, full terrain metadata
when available, pagination and an `objectKey` unique within that archive snapshot.
Do not reuse snapshot keys against a different map SHA-256. Reading the archive
or XML unsuccessfully reports an error rather than a successful empty search.

## Capture a coordinate region

`POST /terrain/region` or MCP `sc2_capture_map_region` exports the full map through
the owned hidden original Editor, then crops its original pixels. It does not
move a visible camera, inject input, take a desktop screenshot or upscale pixels.

```json
{"map":"D:\\MyMap.SC2Map","bounds":{"left":8,"bottom":12,"right":24,"top":36},"size":2048,"output":"D:\\MapRegion.png"}
```

Bounds are finite map coordinates with `left < right`, `bottom < top`, wholly
inside the full terrain. Coordinates use bottom-left XY; the crop assumes north
is up in the native 90° export. A live standard 64×48 fixture correctly located
its southwest CommandCenter and returned a matching 161×161 crop. **Broader
terrain/camera calibration is not certified.** Packaged responses retain
`coordinateMappingValidated:false`; the operation remains experimental.

The initial adapter supports terrain XY offset `0,0` and scale `1,1`, as recorded
in `t3Terrain.xml`. Other transforms and mismatched image aspect ratios fail.
Bounds are never silently clipped. Pixel edges round outwards; the response
reports requested bounds, actual covered bounds and the source pixel rectangle.

`size` selects the resolution of the **whole map**, not the final crop. Small
regions contain fewer pixels; use 4096 for more source detail. This is not an
independent close-up camera render. Unit/doodad switches, PNG output, artifact
download/SHA-256, overwrite protection and bounded MCP previews work as for the
full-map export. A failed native export, black/uniform crop, changed source or
hidden-window violation cannot publish a successful region artifact.

Use object search first and pass a rectangle around its returned XY to capture
that location. The fixture's landmark was visually verified; other maps still
require their own acceptance checks.

## Current Terrain viewport

`POST /terrain/capture` or MCP `sc2_capture_terrain` opens a private map copy,
selects the original Terrain module and captures its own D3D9 backbuffer:

```json
{"map":"D:\\MyMap.SC2Map","output":"D:\\Terrain.png"}
```

Omit `map`/`template` to capture the currently open map. `output` is optional;
the response includes an artifact, SHA-256 and download URL. Existing PNGs require
`overwrite:true`. MCP returns the image inline. `.SC2Mod` has no terrain of its own.

This operation preserves the current native viewing angle and Editor overlays;
Editor panels are excluded. `camera`/`time_ms` are cutscene arguments and are
rejected here. `requestedTerrainFrameVerified:true` requires viewport identity,
a detailed image and the hidden desktop invariant. Black/uniform frames fail by
default. `allow_empty:true` can retain an empty diagnostic image without certifying it.

## Cutscene frames and native render boundaries

Load a loose `.SC2Cutscene` with the map/mod's installed dependencies, select a
camera and time, then capture:

```text
/cutscene/open   {"template":"D:\\MyMod.SC2Mod","scene":"D:\\Intro.SC2Cutscene"}
/cutscene/seek   {"camera":"Front Formation Camera","time_ms":990}
/render/capture  {}
```

`/render/capture` also accepts `camera` and `time_ms` to select and capture in one
request. Original Import, Restart and Next Frame commands control the native scene.
The tested Editor advances on a **33 ms** grid; its time indicator reads back at
10 ms resolution. Reports return requested/actual times and the native status.
A short camera name is accepted only for one native menu match; otherwise use its
exact unique menu name. Long seeks can take time.

Pixels are copied before the selected swapchain's `Present`, with MSAA resolve if
needed, readback to system memory and Windows WIC PNG encoding. This is not a
desktop screenshot. The viewport HWND must match the selected frame. Cutscene
capture selects the native 1280×720 preset and disables helpers; its actual PNG
client area on the tested build is **1276×716**.

Black/uniform stills fail with `status:FAILED` (HTTP 422), retaining diagnostics.
`allow_empty:true` does not make an empty image verified.
`requestedCutsceneFrameVerified:true` requires a loaded scene, confirmed camera and
time, matching viewport, detailed pixels and hidden execution. Source scenes and
maps/mods stay unchanged; import opens the private loose file without adding it to
the document.

## MP4 and original cutscene audio

`POST /cutscene/export` or MCP `sc2_export_video` streams original camera frames
into H.264/yuv420p MP4, CRF 18, `faststart`. By default it also records the original
Editor's own audio and encodes **AAC 192 kbit/s**. Set `include_audio:false` for
silent video.

Full scene with hidden autostart:

```json
{"template":"D:\\MyMod.SC2Mod","scene":"D:\\Intro.SC2Cutscene",
 "camera":"Front Formation Camera","output":"D:\\Intro.mp4"}
```

A range of the already loaded scene, with an exclusive end:

```json
{"camera":"Top","start_ms":990,"end_ms":1980,"fps":30,
 "output":"D:\\SelectedRange.mp4"}
```

Without `end_ms`, duration comes from the first enabled Director End Scene, or
from authored elements (`durationSource:authoredElements`). If unknown, specify it.
`fps` is an integer from 1 to 60, default 30. Native times snap to the 33 ms grid;
higher output rates repeat the nearest sample (`repeatedSamples`). Frame count is
`ceil((end-start)*fps/1000)` and encoded duration is frame count/FPS, differing
from the requested range by less than one output frame. Reports include first/last
native times. Timelines up to 600,000 ms are supported.

Rendering advances sequentially and can take longer than playback. Poll
`GET /cutscene/export/status` or cancel using
`POST /cutscene/export/cancel {"job_id":"ID from progress"}`. Both require the token.
Cancellation is checked between frames and before publication. Existing MP4s are
preserved unless `overwrite:true`. A completed file is published atomically only
after frame count/FPS/duration checks, full decoding and decoded image validation.
Authored black transitions remain in place; an entirely empty range is rejected.
`keep_frames:true` retains temporary PNGs. `frameManifest` records times, HWNDs,
pixel statistics and hashes. The MP4 is a downloadable `video/mp4` artifact.

Audio uses a separate native playback pass from scene start through `end_ms`,
preserving sounds that begin before `start_ms`. Only the owned Editor's WASAPI
render buffers are recorded, not system loopback or a microphone. The Editor's
speaker output is silenced. Idle output gaps remain silence. D3D9 state/draw calls
with copied arguments are queued during this pass, on the same invisible render
thread, to avoid delaying the timeline on every cross-thread wait.

`audio.capture` reports timing, actual/idle samples, RMS/peak and native PCM evidence;
AAC is checked after full decoding. `audio.silent:true` reports genuine silence,
not a confirmed audible cue. Capture failures do not substitute unrelated sound.
Actual Editor audio-engine latency is preserved; phoneme onset is not promised
sample-aligned to XML element start. Complex bookmarks/jumps, linked external
scenes and output-device changes require additional validation.

## MCP configuration

```json
{"mcpServers":{"sc2-native":{"command":"D:\\SC2NativeToolkit\\SC2NativeMCP.exe",
 "args":["--work","D:\\SC2NativeToolkit-data"]}}}
```

Tools: `sc2_modules`, `sc2_editor_start`, `sc2_open_document`, `sc2_convert_xml`,
`sc2_compile_all`, `sc2_export_galaxy`, `sc2_diagnostics`, `sc2_cutscene_open`,
`sc2_cutscene_seek`, `sc2_capture_frame`, `sc2_capture_terrain`, `sc2_export_map_image`, `sc2_export_video`.
`sc2_search_objects` and `sc2_capture_map_region` provide saved placement search
and experimental coordinate-region PNGs. `sc2_validate_document` and
`sc2_save_reopen` provide native load/Data checks and serialization comparison.
`sc2_list_map_cameras` exposes saved map-camera metadata (26 tools in total).
Images are returned as MCP image content and PNG artifacts; complete map exports
embed the bounded preview and provide the full PNG as a downloadable artifact. Large Galaxy output
uses the export tool rather than being embedded in MCP text. EOF shuts down the
owned Editor. No unrelated visible Editor is attached or controlled.

## Build and test

Use Python 3.11+, Visual Studio C++ x64 Build Tools and a Windows SDK.
MSVC/SDK paths are discovered with `vswhere`.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\install-mpqcli.ps1
.\build.ps1 -WithVulkan
.\package.ps1 -WithVulkan -Python .\.venv\Scripts\python.exe
.venv\Scripts\python.exe -m unittest discover -s tests
.\scripts\test-native.ps1
.venv\Scripts\python.exe tests\check_packaged_mcp.py
.venv\Scripts\python.exe tests\check_packaged_http.py
```

`mpqcli` is pinned to v0.10.0 and verified by SHA-256. Its executable is bundled
locally/in releases, not tracked as source. The Editor/game assets are not bundled.
`-WithVulkan` fetches the pinned DXVK dependency for parallel hidden rendering.
Omit it from both commands to build a source-only system-D3D9 variant without
downloading DXVK; use a fresh binary directory if one already contains a renderer.

Live tests are opt-in, use private copies and close owned workers. Examples:

```powershell
.venv\Scripts\python.exe tests\live_smoke.py --package `
  --template 'D:\MyMod.SC2Mod' --scope library:810D62ED --work 'D:\FreshCoreTest'
.venv\Scripts\python.exe tests\live_document_validation.py --package `
  --template 'D:\MyMod.SC2Mod' --scope library:810D62ED --missing-dependency `
  --work 'D:\FreshDocumentCheck'
.venv\Scripts\python.exe tests\live_terrain.py --package --autostart `
  --map 'D:\MyMap.SC2Map' --work 'D:\FreshTerrainTest'
.venv\Scripts\python.exe tests\make_terrain_fixture.py `
  --base 'D:\EmptyMap.SC2Map' --output 'D:\PrivateFixtures\Hills.SC2Map'
.venv\Scripts\python.exe tests\live_map_image.py --package --parallel --all-sizes `
  --map 'D:\PrivateFixtures\Hills.SC2Map' --work 'D:\FreshWholeMapTest'
.venv\Scripts\python.exe tests\make_camera_fixture.py `
  --base 'D:\EmptyMap.SC2Map' --output 'D:\PrivateFixtures\Cameras.SC2Map'
.venv\Scripts\python.exe tests\live_map_cameras.py --package `
  --map 'D:\PrivateFixtures\Cameras.SC2Map' --camera-a 2001 --camera-b 2002 `
  --work 'D:\FreshSavedCameraTest'
```

The whole-map fixture contains two hills, four distinct corner buildings, ten
Marines and four doodads. Its opt-in test checks all four visibility combinations
and restoration in one persistent worker, an independent second worker, all four
output sizes, exact native TGA/PNG pixels, exact downloads and output protection.
Disabled models are compared against an independently rendered private copy with
placements removed. A full 4096×3072 placed-model frame is checked against its
empty native reference too. Review the images and southwest crop visually;
detailed-pixel statistics or animation-only frame differences are insufficient.
The current results and remaining water/map coverage are in
[validation history](docs/VALIDATION.md).

The camera fixture builder replaces placements only in a new private copy and
adds two native-format saved cameras. The camera test checks listing before
startup, invalid-ID rejection, A → B → A captures, native parameter readback,
PNG download hashes, source preservation, background observations and subsequent
native trigger compilation. Review the PNGs visually as well. These fixture
builders require the supported native, untransformed terrain component format.

Tests without Editor validate transport, files, arguments and invariants; only
live tests confirm native generation, compilation and rendering. See
[validation history](docs/VALIDATION.md) for exact versions, scenarios and limits.
Never commit maps, scene files, tokens, raw audio, PNG/MP4 captures or runtime state.

## Source layout and lifetime

- `src/`: C++ DLLs, hidden launcher, IPC controller and D3D9 capture.
- `app/sc2native/`: sessions, artifacts, diagnostics, HTTP, MCP and capabilities.
- `app/native_xml_oracle.py`: native XML loading/generation/compilation pipeline.
- `vendor/minhook/`: pinned upstream source and license.
- `tests/`: automated and opt-in live checks.

The installed Editor EXE, source maps/mods and installed dependencies are not
patched. A Windows Job Object binds owned Editor/encoder lifetime to API/MCP.
Logical focus on the private desktop is allowed for original native commands;
user-desktop activation is monitored separately and must stay absent.
The [startup dispatcher](docs/NATIVE_DISPATCH.md) remains inside that owned
worker until it exits. Per-request guards are removed after each handler;
there is no per-request cross-process DLL-hook installation.

Technical references: [D3D9 GetRenderTargetData](https://learn.microsoft.com/en-us/windows/win32/api/d3d9/nf-d3d9-idirect3ddevice9-getrendertargetdata),
[MCP stdio](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports).
