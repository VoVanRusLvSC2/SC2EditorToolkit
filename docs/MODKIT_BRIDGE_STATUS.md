# ModKit / original Editor bridge status

Assessment of the existing toolkit against the five-point integration plan,
2026-10-20. ModKit remains responsible for fast previews, terrain operations,
measurements and authoring. This toolkit supplies evidence from an owned hidden
original Editor. No additional MCP methods were implemented in this validation
session; the tool count remains 15.

| Plan item | Current status | Remaining acceptance work |
|---|---|---|
| 1. Original GUI triggers → Galaxy → Compile All → diagnostics/script | Implemented and live-tested on Nydus v54 with installed dependencies. Native generation and compilation passed with zero compiler errors. Galaxy file and HTTP download matched exactly: 342,851 bytes. | A broader map/dependency matrix, invalid-source cases and explicit Trigger Reviser integration tests. A successful native compile is not a gameplay test. |
| 2. Map/Data load errors with message type, related ID and new/old separation | Partial. Messages/Console and compiler diagnostics are read separately; unreadable or truncated logs remain unknown. | Per-operation baselines/deltas, native load failure capture, classification of missing models/dependencies/inheritance/actor conflicts and related IDs when present. Do not mistake a current empty log for a tested failure-detection matrix. |
| 3. Reliable original map image with terrain, water, units and doodads | Partial, with successful visual evidence. Original full-map export of the corrected fixture shows textured ground, both hills, four corner buildings, ten Marines and four doodads at 1024×768. | Water acceptance, category-exclusion correction and broader map/dependency coverage. The first generated test fixture omitted native Objects registration/preloads; correcting that private fixture made placements visible without changing renderer/API code. |
| 4. Real local-area capture with native camera controls | Not implemented. Current region capture is an unscaled crop of the original full-map image; cutscene cameras are separate. | Native Terrain target coordinates, distance, angle and resolution; actual camera state readback and a matching render. Keep full-image cropping as a separate operation. |
| 5. Native Editor save → reopen → diagnostics/component differences | Not implemented as an operation. Current loading and capture use private copies. | Save the private copy through the original Editor, reopen it, collect operation-specific diagnostics and optionally return component hashes/diffs. Copying/repacking an archive is not native Editor saving. |

## Existing supporting behavior

- A persistent owned Editor process is reused across requests in an API/MCP
  session. Windows remain on its private desktop, with an invisible technical
  renderer. The installed executable file stays unchanged; physical mouse and
  keyboard input is untouched.
- Requests are serialized with a busy lock. There is no general queued-job API.
  MP4 export alone has job identity, progress and cancellation. General queueing,
  progress, cooperative cancellation and deadlines remain future work.
- Requests/manifests retain document identities and source hashes, but there is
  no single map-revision token consistently attached to every operation.
- Native request timeout handling keeps callbacks alive until an in-progress
  handler completes; it is not a general safe-abort protocol.
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

Prioritize item 1's broader verification plus items 2 and 5 for generator
reliability. Finish item 3's visual acceptance next; implement item 4 as an actual
camera operation rather than relabeling the current crop. A gameplay/ability
test harness is a separate later task.
