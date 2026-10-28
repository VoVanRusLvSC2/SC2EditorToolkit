# 1.1 field values and Terrain camera acceptance

Field/camera acceptance baseline: **1.1.0-rc.1**, API contract 1, native protocol 16,
31 existing MCP tool names. Tested original Editor: **5.0.17.98310 x64**.
Other Editor binaries remain unsupported until their own adapter is verified.

## rc.2 input isolation

The rc.2 change suppresses hardware cursor operations on wrapped hidden-renderer
D3D9/D3D9Ex devices and rejects startup outside the selected owned Editor before
installing hooks. It does not change Data traversal, protocol or tool names.
The detailed field/resource acceptance below remains the rc.1 baseline and was
not repeated as a full audit for this cursor fix. See [input isolation](INPUT_ISOLATION.md).

## Native effective fields

The final protocol 16 reader traversed all 109 catalogs of the Nydus mod and its
loaded dependencies: **50,129 effective objects and 6,906,851 materialized field
values**. Original getters and type serialization reported **zero errors**.
**2,578,832** numeric/color/vector values additionally included verified original
storage bits. Source/dependency/build revisions were checked before and after;
the declared project manifest was complete within its documented scope.
Runtime player state and gameplay upgrades were not applied.

A preceding protocol 15 development run recorded the same native field model.
The final reader compared original serialized values and typed reference/resource
observations for its 50,125 already-flushed object records. The final reader
independently completed all 50,129 objects; the remaining four were not counted
as baseline comparisons. No opaque pointer addresses were exported.

On separate private healthy/override maps, the original getter serializer read
all 633 materialized Marine fields and agreed with the original Data table's
Copy As Text values. Exactly one field changed: **LifeMax 45 → 73**. Nested weapon
array serialization agreed with the original typed weapon reference. Source
archives remained unchanged.

## Saved values through the frozen MCP

The production index builder stored all **6,906,851** final native field values
in an immutable SQLite acceptance index. The frozen windowed MCP EXE reopened
that store and successfully read:

- Unit/Marine/LifeMax: `45`, exact storage `00d00200`.
- Abil/CAbil/OrderArray[0].Scale: original real32 `1.000000`, storage `0000803f`.
- A bounded field page with the exact total count and next offset.
- A field self-comparison with zero changes and complete value coverage.

No Editor was launched for those queries. This acceptance dataset covers the
complete native field snapshot; it is **not a new resource-validation report**.
Reference/resource finding coverage remains separate from value recording.
A 12 GiB start threshold, 512 MiB running reserve and artifact-copy space checks
protect full audits from filling the work volume. Low-space rejection before
native calls is tested; the doctor reports the full-audit storage requirement.

Unit tests additionally cover changed scalars/nested paths, field filters,
pagination, old-report rejection and incompatible encoding versions.

## Terrain

Two explicit XYZ/pitch/yaw/roll/distance/FOV requests passed original Set Game
Camera, native dialog commit and a second Get Game Camera in a fresh dialog.
All eight parameters matched within the documented native UI tolerances.
The renderer produced distinct nonblack PNGs; visual inspection confirmed the
changed view and roll. A complete overhead map PNG also passed original export
settings/filter readback and image-content checks.

An early candidate changed the dialog controls but cancelled the view change,
producing identical frames. That attempt failed acceptance. The native OK commit
and fresh readback fix passed the independent two-image test. Saved-camera
selection retains its original path; explicit camera requests do not add cameras
to the source archive. Arbitrary viewport resolution is not exposed.

## Scope and regression

122 Python tests and seven native suites passed, including owned-tree and
private-clipboard isolation. Frozen HTTP and 31-tool MCP contract tests passed.
The frozen HTTP package also passed Nydus native generation/compilation and exact
Galaxy download, then opened a private terrain map and captured its explicit
camera frame. Shutdown was confirmed separately after the acceptance harness
used an incorrect cleanup method; that harness error did not invalidate the
recorded native results.

Full native file-presence validation remains covered by the separately recorded
[1.0 acceptance](V1_ACCEPTANCE.md); this change does not replace that adapter.
An intermediate protocol 15 repeat was stopped after the final field reader
superseded it and is **not counted as a successful complete audit**.

All counted native tests used owned private workers/copies. Their observation
reports recorded zero owned visible windows on the user desktop, zero owned
foreground samples, no physical input injection and no desktop-switch API use.
Task-owned Editors were closed after testing. Field-recording success does not
certify actor event semantics, computed links, nested resource binary integrity,
animations or gameplay. Movement/attack/ability/death checks require the game.
