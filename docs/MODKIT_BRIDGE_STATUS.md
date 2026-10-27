# Current bridge contract — 1.0.0

The stable integration has 31 MCP tools, API contract 1 and native protocol 15.

Development 1.1.0-rc.1 retains the tool names and API contract, requires native
protocol 16, and adds explicit Terrain camera parameters plus effective field
value snapshots and indexed field comparison. Updating this toolkit does not
automatically replace a separate ModKit integration's installed package.
It adds precise tool schemas/errors, installation preflight, indexed native Data
audit queries, incoming typed object uses, audit comparison and project dependency
revision manifests. [Setup and contract](MCP_CONTRACT.md), [final acceptance](V1_ACCEPTANCE.md).
The following sections retain dated implementation history.

v0.14.0-rc.1 adds a full traversal of all original effective catalogs and typed catalog/file checks. Coverage gaps and optional missing identities remain explicit. See [Data audit](DATA_AUDIT.md). The current complete native package uses protocol 15; restart owned workers after upgrading.

# ModKit / original Editor bridge status

v0.13.0-rc.1 adds a per-server FIFO job API, cancellation/deadlines and fresh-worker
recovery; immutable revision-bound native reports; original effective Data fields,
Object Explorer associations and main Model file checks in the original Archive
Browser. There are now 26 MCP tools. See
[jobs and reports](JOBS_AND_REPORTS.md) and [Data and resources](DATA_AND_RESOURCES.md).
Protocol 14 was the matching native package for v0.13.0-rc.1.

v0.12.0-rc.1 completes the native whole-map visibility filters, with independent
model readback, all four category combinations/restoration, a second owned worker
and full-resolution model acceptance. See [map export](MAP_EXPORT.md).
That release used protocol 13. Water-specific
acceptance and broader asset/dependency coverage remain separate.

The v0.11.0-rc.1 update removed the fixed installation path and adds Editor discovery,
`editor_path`, `SC2_EDITOR_PATH` and CLI `--editor`. It validates the supported
original binary and uses selected-file identity throughout native operations.
That release used protocol 12; v0.13.0-rc.1 used protocol 14.
See [presentation readiness](PRESENTATION_READINESS.md) for dated parallel-worker
and native media evidence, plus the remaining feature limits.

The v0.10.0-rc.1 change adds pinned Vulkan offscreen rendering for a separate owned
Editor, following the SC2GameToolkit approach. See
[parallel instances](PARALLEL_INSTANCES.md) for startup selection and isolation.
The v0.9.2-rc.1 change replaces the Win32 126 setup dependency with initialization
inside the owned Editor GUI thread. Native XML generation/compilation, recovery,
Nydus compilation and selected cutscene frames have passed live checks again.
No new MCP tool is added. Upgrade all native components and restart the owned
worker; versioned dispatch rejects incompatible components. See [startup dispatch](NATIVE_DISPATCH.md)
and [dated validation history](VALIDATION.md). Earlier rendering limitations in
the table below remain in force.

Assessment of the existing toolkit against the five-point integration plan,
updated 2026-10-24. ModKit remains responsible for fast previews, terrain operations,
measurements and authoring. This toolkit supplies evidence from an owned hidden
original Editor. The original assessment used 15 MCP tools. The subsequent
implementation of items 2 and 5 adds exactly two tools (17 total):
`sc2_validate_document` and `sc2_save_reopen`.
Saved-camera listing adds `sc2_list_map_cameras` (18 total); selecting a saved
camera extends the existing `sc2_capture_terrain` tool.

| Plan item | Current status | Remaining acceptance work |
|---|---|---|
| 1. Original GUI triggers → Galaxy → Compile All → diagnostics/script | Implemented and live-tested on Nydus v54 with installed dependencies. Native generation and compilation passed with zero compiler errors. Galaxy file and HTTP download matched exactly: 342,851 bytes. | A broader map/dependency matrix, invalid-source cases and explicit Trigger Reviser integration tests. A successful native compile is not a gameplay test. |
| 2. Map/Data load errors with message type, related ID and new/old separation | Implemented as operation-scoped native observations. Private archive load and original Data opening retain before/after snapshots, output mutations, new errors/warnings and old baselines. Text classification and explicit IDs are returned when available. | Broader localized/native failure-format coverage. This collects what the Editor actually reports; opening Data is not an exhaustive engine validator. Silent invalid references are not certified. Unreadable, truncated or ambiguous output remains unknown. |
| 3. Reliable original map image with terrain, water, units and doodads | Partial, with successful visual evidence. Original full-map export of the corrected fixture shows textured ground, both hills, four corner buildings, ten Marines and four doodads at 1024×768. | Water-specific acceptance and broader map/dependency coverage. Category exclusion is corrected through original model setter/getter readback; painted checkbox state is insufficient. The first generated test fixture omitted native Objects registration/preloads; correcting that private fixture made placements visible without changing renderer/API code. |
| 4. Real local-area capture with native camera controls | Saved camera selection remains supported. Development 1.1 additionally accepts explicit target XYZ, pitch/yaw/roll, distance and FOV through the original Camera Editor, commits the view and reads it again before renderer capture. Full-map cropping and cutscene cameras remain separate. | Arbitrary viewport resolution and broader map/UI coverage. This is static editor placement state; Galaxy-trigger playback requires the game. |
| 5. Native Editor save → reopen → diagnostics/component differences | Implemented. Original File/Save As serializes a private copy, File/Close removes that document, then original File/Open reads the saved archive. Per-phase diagnostics and exact enumerated MPQ member comparisons include locales, metadata and optional bounded text diffs. | Broader map/dependency and Editor-version coverage. Only confirmed commands, complete component reads, stable hashes and known-clear new diagnostics permit publishing a verified saved archive. Failure after saving still retains the save comparison report. |

## Existing supporting behavior

- A persistent owned Editor process is reused across requests in an API/MCP
  session. Windows remain on its private desktop, with an invisible technical
  renderer. The installed executable file stays unchanged; physical mouse and
  keyboard input is untouched.
- Requests use a bounded FIFO queue per server. Status/wait/cancel and execution
  deadlines are exposed over HTTP/MCP. Running aborts discard only the owned
  process after PID/creation-time verification; jobs are never replayed.
- Reports and Data observations include source SHA-256/map revision. The report
  combines load/Data diagnostics, optional save/reopen, native generation,
  compilation and exact Galaxy export. It does not execute gameplay.
- Native request timeout handling retains IPC until a callback completes or
  the owned process exits. An aborted process is not reused for another job.
- Native Data values use original UI serialization or native reflection; individual Explorer relationships are original UI observations, not an
  independently reimplemented inheritance resolver. Main Model file checks do
  not certify every nested texture/animation/sound or runtime actor combination.
- ModKit's existing Data reader was exercised separately on its loaded project:
  it found 12,639 declarations and returned requested declared fields with source
  provenance. Runtime override resolution remained explicitly unknown. This proves
  that existing XML catalog reading works; it does not implement native Data
  load-error classification in this bridge or certify engine-equivalent fields.

## Live evidence from the packaged v0.7.0-rc.2 executables

The original installed Nydus v54 mod and NydusIntroBlue scene were opened through
an owned hidden worker. Front Formation Camera at 990, 1980 and 2970 ms produced
different frames; Top at 1980 ms produced a different view. Visual inspection
showed the scene's Marines and platform, not a black frame. Native compilation
after the scene passed. Compiler errors were zero; Messages/Console was readable,
complete and empty in that session. Galaxy SHA-256:
`ad36611c87c754f9944b978f921e67ee7767f75a277f0a293d98830f2aaff078`.

The scene/mod source hashes remained unchanged. Across 1,584 observations there
were zero visible worker windows, foreground samples or input-desktop changes;
no mouse/keyboard injection or desktop-switch API was used. Owned workers were
closed by the test. User files, exported scripts and images remain local.

The corrected surface fixture's full native image has 786,432 nonblack pixels
and 219 luminance bins. Visual inspection confirmed relief and the placed units
and doodads. The original fixture map stayed unchanged; its first full export
recorded 2,730 samples with zero visible windows, foreground samples or desktop
changes. The fixture does not contain water, so it cannot establish water
rendering acceptance. This evidence applies to the tested map and Editor build.

An additional limitation was observed: `include_units:false` still left the
placed units visible, and disabling both categories still left doodads visible
in the native output, despite matching checkbox readback.
Animation/selection-marker differences also made pixel-difference checks pass;
those differences do not prove that a visibility switch worked. Native category
exclusion is not accepted. Do not rely on it until the adapter is corrected and
visually re-tested. Default export with categories enabled is a separate result.

Saved-object lookup found the southwest CommandCenter at XY (7.68, 6.72). The
coordinate-region operation returned a 161×161 unscaled crop visibly containing
that building. Requested XY bounds were approximately (2.68, 1.72)..(12.68, 11.72),
with outward pixel rounding. This confirms alignment on this fixture only;
packaged responses still retain the experimental coordinate-validation flag.
Across the full map/crop run, 10,429 observations recorded zero visible windows,
foreground samples and desktop changes. The test closed its owned worker.

Prioritize item 1's broader verification and expand the failure matrix for items
2 and 5. Finish item 3's visual acceptance next. Item 4 now supplies original
saved-camera views; development 1.1 adds explicit camera overrides. A
gameplay/ability test harness and trigger-cinematic execution are separate later
tasks. See the dated saved-camera evidence in [validation history](VALIDATION.md).
