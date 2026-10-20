# Validation history

All dates below are 2026-10-20. Live tests use the original installed SC2 Editor
5.0.17.98310 on Windows x64. They operate on owned hidden workers and private
copies, never on the user's visible Editor. Results apply to the version and
scenario stated; they do not certify every map, asset, device or Editor build.

User maps, scenes, PNG/MP4 captures, raw PCM, tokens and complete runtime logs are
kept local and are excluded from Git and release assets. Documentation and future
release notes are maintained in English.

## v0.7.0-rc.2: saved object search and experimental map regions

Live Editor testing was explicitly deferred while the user is playing. No new
Editor worker was started for these RC2 checks. Native DLL/controller code is
unchanged from RC1; the added operations are in the Python API/MCP frontend.

Object search reads `Objects` and terrain metadata from a byte-checked private
snapshot using mpqcli. It reports saved XYZ, not sampled terrain elevation or
unsaved/runtime state. Tests exercise filtering, pagination, duplicate IDs across
object kinds, missing coordinates, malformed XML and finite bounds. A generated
XML-only MPQ fixture verifies actual archive reads without starting an Editor;
that fixture is not a renderable game map and is never passed to the Editor.

Region capture privately obtains the original full-map export, validates its
aspect ratio against full saved terrain bounds, then crops pixels with outward
rounding. Synthetic coordinate-gradient tests establish crop math, RGB pixel
identity, origin conversion and source preservation. Stubbed native results
exercise publication rejection for failed native export, black crop, changed
source and visible-worker observation. These are not native rendering evidence.

The native north/up orientation and landmark alignment remain **unvalidated**;
all region results retain `coordinateMappingValidated:false`. Standard XY
offset/scale only is accepted. `size` controls full-map resolution; crops are not
upscaled or rendered by a separate close-up camera. The existing opt-in
`live_map_image.py` now searches the private fixture's southwest CommandCenter
and requests a region around it for later visual calibration.

| Final RC2 check, without Editor | Result |
|---|---|
| Python regression tests | 27 PASS |
| Real generated MPQ search | PASS; original XYZ, filters, pagination, unchanged source; no Editor startup |
| Synthetic region pixels | PASS; exact RGB crop, outward edges, covered bounds, no resampling |
| Region failure cases | PASS; no publication for native failure, black image, source change or visible worker |
| Packaged windowed MCP | PASS; 15 tools; actual archive search call returns expected coordinates; no Editor started |
| Packaged windowed HTTP | PASS; actual archive search, invalid/outside region rejection and existing-output preservation; no Editor started |
| English documentation | Eight JSON examples parse; README and validation report in English |
| Native DLL changes | None; RC1 native binaries reused |
| Native full-map and region render / coordinate landmarks | PENDING; explicitly deferred by user |

Historical RC1/stable live results do not establish RC2 region rendering acceptance.

## v0.7.0-rc.1: experimental original whole-map export

**A completed whole-map image has not been accepted.** The release is a
prerelease; it must not be described as a verified render of relief, units and
doodads. Further live testing was explicitly deferred at the user's request
while they are playing StarCraft II.

Before that deferral, the owned hidden Editor opened a private 64×48 fixture
containing two hills, 14 placed units (four different corner buildings plus
Marines) and four doodads. The original **Data → Export Map Image** dialog was
resolved dynamically and its controls configured/read back: Full bounds, All
quadrants, 90° overhead camera, 2048×1536 dimensions, game lighting, standard
shading, terrain/water/shadows/units/doodads enabled, editor overlays disabled.
The native modeless dialog requires a retained GUI timer/message pump. Its modern
Choose File dialog accepted the exact private TGA destination; the returned
abbreviated path is checked against that full destination.

Submitting the original exporter did not produce a TGA: the Editor exited with
a DirectX `0x88760868` failure. A fresh owned worker then also failed at initial
D3D9 CreateDevice with the same result. Device availability prevented completion;
this does **not** establish whether whole-map export itself will succeed or that
visibility checkbox changes affect rendered model contents. The running game
was not closed, reconfigured or controlled. No rendered fixture image is shipped.

The new API/MCP operation remains fail-closed: settings readback alone cannot
publish a successful artifact. It requires original export completion, full file
decoding, expected width, detailed pixels, unchanged source and the hidden-window
invariant. RGB TGA pixels are losslessly encoded as PNG. A preview is bounded to
1280 pixels. Detailed-pixel statistics cannot establish that every model exists.
`tests/live_map_image.py` is the opt-in automated check for the next permitted
live session, followed by visual review of hills and all corner landmarks.

Checks completed without starting an Editor for the final RC binaries:

| Check | Result |
|---|---|
| Native Windows x64 build | PASS; bridge/controller, hidden host, bootstrap and capture controller |
| Python tests | 20 PASS, including rejection of unconfirmed/black/visible-worker exports |
| Native C++ tests | Both readiness captions and exact/abbreviated export paths PASS |
| Native TGA → PNG conversion | Test pixels identical; original file unchanged; bounded preview |
| Packaged MCP | Initialize/tools/list/capabilities PASS; 13 tools; no Editor started |
| Packaged HTTP | Health/auth/capabilities/export argument validation/overwrite rejection PASS; no Editor started |
| Public instructions | English README, validation report and GitHub release notes |
| Final whole-map rendering / unit and doodad pixel acceptance | PENDING; live test deferred by user |

Historical native generation, video/audio and Terrain viewport results below
apply to their stated versions and do not substitute for this pending whole-map
render test. These RC tests do not establish a new native rendering regression
result for the final packaged binaries.

## v0.6.0: Triggers readiness and Terrain viewport

Final windowed API/MCP executables were tested.

| Check | Result |
|---|---|
| Original `-modtrigger` startup | PASS; `readyModule=Triggers`, no Terrain window at readiness |
| One `/terrain/capture` request with a map, without `/editor/start` | PASS; hidden autostart, original Terrain module, PNG |
| Terrain capture and repeat | PASS; 1297×868, 1,125,796 nonblack pixels, 130 luminance bins, viewport identity confirmed |
| Visual inspection | PASS; textured test Agria ground, not a black image |
| PNG artifact download | PASS; SHA-256 matches local file |
| Existing PNG without overwrite | Rejected; existing file preserved |
| Nydus native generation and Compile All after Triggers startup | PASS; 341,732 Galaxy bytes, 0 compiler errors |
| Nydus Messages/Console in that session | Readable complete log, no entries |
| Galaxy export, download and overwrite protection | PASS; exact native bytes |
| Nydus audio regression | PASS; original quiet range, private Marine_Ready cue, Top/Front ranges, cancellation |
| AAC versus original Editor PCM | Correlation 0.999275; timing delta 0.632 ms on a 10 ms comparison grid |
| MP4/AAC decoding | PASS; 5 + 40 + 15 + 15 frames, each file fully decoded |
| Packaged Terrain desktop observation | 3,003 samples; 0 visible windows, foreground samples or desktop changes |
| Packaged audio desktop observation | 2,302 samples; same zero counts |
| Source files | SHA-256 unchanged |
| Shutdown | All owned workers closed; pre-existing user Editor remained running |
| Tests without Editor | 17 Python tests and C++ caption/readiness regression suite PASS |
| Packaged MCP | stdio initialize/tools/list/capabilities PASS; 12 tools |

A separate source test also confirmed Triggers-only readiness, repeated Terrain
captures and downloads. Startup using the saved Terrain module passed separately.
Readiness checks the exact document name, enabled/visible workspace, absence of
Activity/startup failures, and a live process. Generation and compilation were not
replaced by another emitter/compiler.

At v0.6.0 Terrain capture represented the current native viewport, not a complete
overhead map export or named map camera control. The test map had no placed
objects, so that test established ground rendering only. A `.SC2Map` is required;
a `.SC2Mod` has no surface of its own. Terrain loading took several minutes.
The controller keeps hooks alive until a pending native handler finishes, even
when its initial SendMessage timeout has elapsed.

## v0.5.0: original native cutscene audio

Final windowed API/MCP executables used Nydus v153 Local and its installed
native dependencies, with a private scene copy for the positive sound test.

| Check | Result |
|---|---|
| Original NydusIntroBlue, 990–1320 ms | PASS; 5 frames, 15 FPS, H.264 + AAC |
| Full private Nydus copy with Marine_Ready element starting at 500 ms | PASS; 40 frames, 10 FPS, 4 seconds, audible original cue |
| Top, 990–1980 ms | PASS; 15 frames, 15 FPS, genuine native 3D audio silence at that camera |
| Repeated Front export, same range | PASS; 15 frames; cue started before range and remains audible |
| MP4/AAC full decoding | PASS; detailed video frames |
| AAC versus actual native PCM | Correlation 0.993309; timing delta 2.404 ms on a 10 ms grid |
| Cancellation during audio pass | PASS; cancelled target MP4 not published |
| User desktop visible windows / foreground | 0 / 0; no input injection or SwitchDesktop |
| Source map/mod and scene hashes | Unchanged |
| Worker shutdown | PASS; visible user Editor not targeted |
| Tests without Editor | 15 tests PASS, including native PCM trimming and AAC checks |
| Packaged MCP | stdio PASS; 11 tools |

The original NydusIntroBlue has no explicit Sound tracks and produced genuine
quiet PCM/AAC. A separate private derivative added original Marine_Ready for the
positive test. User XML, mod files and dependencies were not modified. Camera
position affects native 3D sound volume; silence at Top is not proof of missing
audio. The repeated Front range checks a cue that starts before `start_ms`.

Timing follows actual Editor output, including audio-engine latency and the
source recording's quiet intro. A phoneme threshold is not an XML element start.
AAC is compared against the captured native PCM with its QPC clock origin;
sample-accurate phoneme alignment to XML is not claimed.

The earlier source/API test also exported the entire original NydusIntroBlue:
119 frames, 30 FPS, 3.966667 seconds, 1276×716, H.264/yuv420p + AAC 48 kHz stereo,
fully decoded with detailed pixels. The final EXE was separately checked using
the table's range/full-cue/repeat/cancellation scenarios.

Audio is recorded from only the owned Editor's WASAPI render buffers, not system
loopback or a microphone; speaker output is silenced. PCM16, PCM32 and float32 are
supported, with one render stream. Unknown formats/streams or write failures fail
the audio export. Zero-sized packets follow the Windows contract. An unavailable
audio endpoint does not block non-audio operations; audio requests require a ready
tap. Complex jumps/bookmarks, linked scenes, output-device changes and other
Editor builds remain unvalidated. Redundant scene reimports caused native shader
crashes during investigation; the tested pass uses original Restart/Play/Pause,
warm-up and clock confirmations instead.

Local evidence runs: `audio-native-04`, `audio-packaged-01`, final `audio-packaged-04`.

## v0.4.0: native cutscene MP4

Sequential sampling uses the original Editor on a private desktop with separately
installed FFmpeg/ffprobe 8.0. Code: `app/sc2native/video.py` and
`src/cutscene_bridge.inc`.

| Check | Result |
|---|---|
| Automated tests, including real H.264 encoding/full decoding without Editor | 13 PASS |
| Packaged MCP initialize/list/call/EOF | PASS; 11 tools |
| Full NydusIntroBlue, Front Formation Camera | PASS; 0–3965 ms, 119 frames, 30 FPS, 3.966667 seconds |
| Format | H.264/yuv420p, 1276×716, MP4 faststart |
| Top, 990–1980 ms | PASS; 15 frames, 15 FPS, 1 second |
| Packaged API camera/range selection | PASS; 5-frame and 15-frame MP4s |
| Every MP4 fully decoded | PASS |
| Decoded image inspection | Scene models visible; 247 luminance levels in full video |
| Progress endpoint | PASS; frame count increases |
| Cancellation during rendering | PASS; target MP4 not published |
| No overwrite permission | Rejected; previous file preserved |
| Artifact download | SHA-256 matches original MP4 |
| Source scene/mod | SHA-256 unchanged |
| User desktop visible windows and foreground events | 0 in both live tests |
| Input/desktop switching | Not used |
| API shutdown | Owned Editor and FFmpeg terminated |

The full scene was tested through the source API; the final executable separately
passed short ranges, camera selection, decoding, download and cancellation. The
full decoded MP4 was inspected visually, not just by container metadata. It had
110 detailed frames and 9 black frames, retained at their original timeline
positions. v0.4.0 MP4 had no audio. Native time grid is 33 ms; time readback is 10 ms.
Output FPS is constant and higher rates repeat nearest native samples.

Reproduce with `tests/live_video.py --template ... --scene ... --camera ... --work ...`.
`--package --smoke` tests packaged executables on short ranges.

## v0.3.0: native scene camera and time

Both source API and packaged executable passed hidden startup → original Import
Cutscene File → native camera selection → Restart/Next Frame → viewport PNG.

| Check | Result |
|---|---|
| Automated tests | 8 PASS: files, arguments, hidden invariant, diagnostics, MCP |
| Packaged MCP initialize/list/call/EOF | PASS; 10 tools |
| NydusIntroBlue with Nydus dependencies | PASS; loose file, document not modified |
| Front Formation Camera at 990 / 1980 / 2970 ms | PASS; 3 distinct images |
| Top at 1980 ms | PASS; differs from Front |
| Native Camera menu and Scene Time | Selection/time confirmed |
| Source buffer selected by viewport HWND | PASS; sourceWindow matches viewport |
| PNG | 1276×716, helpers off, visually inspected |
| Front at 990 ms | 472,520 nonblack pixels, 240 luminance levels |
| Unknown camera | Rejected, HTTP 400 |
| Initial empty buffer at 0 ms | Rejected, HTTP 422, `emptyFrame:true` |
| User desktop visible windows / foreground | 0 / 0 |
| Input injection / SwitchDesktop | Not used |
| Source scene/mod | SHA-256 unchanged |
| Compile All after scene operations in the same worker | PASS; 0 errors |
| Shutdown | PASS; owned worker closed, user Editor preserved |

`actualTimeMs` comes from Scene Time at 10 ms readback resolution. Original Next
Frame advances 33 ms on the tested build. Warm-up can retry captures at the SAME
paused time; it does not move the timeline to manufacture a nonblack image.
Black/uniform results remain errors by default.

Nydus compilation after the scene returned **341,732 bytes**, SHA-256
`0e06ea0c8a379af32fa5372a2a373353646031282f09b305b38c29de09b16aa3`.
The existing native generation/compiler module remained in use.

Reproduce with `tests/live_cutscene.py --package --compile-after`, plus
`--template`, `--scene`, `--camera`, and `--work`.

## v0.2.0: hidden editor modules, export and MCP

| Check | Result |
|---|---|
| Automated file/diagnostic/MCP tests | 5 PASS |
| Packaged MCP initialize/list/call/EOF | PASS; 9 tools |
| Packaged hidden autostart | PASS |
| Nydus with actual dependencies, original generation and Compile All | PASS; 0 errors |
| Messages/Console readback | Complete readable log, no errors |
| Galaxy export and HTTP download | PASS; exact native bytes |
| No overwrite permission | Rejected; original preserved |
| Original Cutscene module | Command executed in hidden Editor |
| Original next backbuffer capture before Present | PASS; 1024×768 PNG |
| Empty-frame reporting | PASS; `emptyFrame:true`, `nonBlackPixels:0` |
| User desktop visible windows / foreground | 0 / 0 |
| API shutdown | Owned Editor terminated |

Nydus Galaxy: **341,732 bytes**, SHA-256
`0e06ea0c8a379af32fa5372a2a373353646031282f09b305b38c29de09b16aa3`,
byte-identical to the previously checked original Editor result. The modular API
uses that same native XML pipeline.

The v0.2.0 black PNG established render transport only, not a selected scene or
movie frame. Camera/time and viewport selection were future work at that version.
Logical focus within the private desktop was required for the native authored
library and command updates; its events were separated from user foreground.
No physical input was injected.
