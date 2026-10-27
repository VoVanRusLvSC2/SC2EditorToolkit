# Terrain camera control and original effective field values

This candidate adds explicit native Terrain camera framing and persistent
field-value snapshots to SC2 Editor Toolkit. It uses the original installed
Editor; it does not implement a replacement Data model or renderer.

- Set target XYZ, pitch/yaw/roll, distance and FOV through the original Camera
  Editor. Commit the view, read it back in a fresh dialog and export a renderer
  PNG. Saved cameras and complete overhead map export remain supported.
- Record every materialized effective field in all 109 native catalogs, including
  loaded dependencies, nested members and array elements. Keep original type
  serialization, per-value failures and verified numeric/color/vector bits.
- Query and compare values using the existing audit tools with `section:fields`,
  optional exact catalog/object/field filters and bounded pagination. These
  operations work after the Editor closes. Older reports without field values
  and incompatible value encodings are rejected explicitly.
- Centralize package/native version metadata and preserve the existing 31 MCP
  tool names and API contract 1. Native IPC is now **16**.

## Validation

The final reader traversed Nydus and its loaded dependencies: **50,129 objects,
6,906,851 field values, zero getter/serialization errors**. Exact storage was
recorded for **2,578,832** values. Private native maps confirmed LifeMax **45 → 73**
as the only changed Marine field, matching the original Data UI. The frozen MCP
queried the complete native value index and its self-comparison without launching
an Editor. Explicit camera views produced distinct, visually reviewed PNGs;
complete overhead export also passed.

The frozen HTTP package passed original Nydus compilation and exact Galaxy
download, then captured a private terrain map with explicit camera parameters.
122 Python tests, seven native suites and frozen HTTP/MCP contract checks passed.
See [1.1 acceptance](https://github.com/VoVanRusLvSC2/SC2EditorToolkit/blob/v1.1.0-rc.1/docs/V1_1_ACCEPTANCE.md) for evidence scope and intermediate
attempts that are not counted as passes. Source archives remained unchanged;
counted native observations recorded no owned user-desktop visibility/foreground
events, physical input injection or desktop-switch API use. Owned Editors closed.

## Upgrade and limits

Replace the **complete ZIP package** and restart the API/MCP worker. Full value
audits require at least **12 GiB free** on the selected `--work` volume; storage
is checked before native work and during indexing/copy publication. This is a
prerelease; stable 1.0 remains available. Source code is included in the Git tag.
Installations are discovered/configurable; the verified native adapter currently
supports original Editor **5.0.17.98310 x64**.

Fields describe the saved effective default variant. Runtime upgrades/player
state, actor-event semantics, computed links, nested resource binary integrity
and movement/attack/ability/death behavior require separate checks. File-presence
validation retains its separately documented 1.0 evidence; this candidate does
not claim a new successful full file audit from its stopped development repeat.
Region capture remains an experimental crop of full-map pixels. Explicit cameras
use native viewport resolution; arbitrary output resolution is not exposed.
