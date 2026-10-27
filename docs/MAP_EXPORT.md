# Native whole-map export and object filters

The toolkit uses the installed original Editor's **Export Map Image** command.
It selects Full bounds, all quadrants, a 90-degree overhead view and custom view
options. The resulting native TGA pixels are losslessly encoded as RGB PNG.
It does not take a desktop screenshot, assemble tiles or remove models from an
already rendered image. Source archives are opened as owned private copies.

## API example

Start `SC2NativeAPI.exe serve --work <private-work-directory> --port 0`.
Read that directory's `api-info.json` for the local URL and authentication token.
Editor installation discovery is automatic; `--editor`, `SC2_EDITOR_PATH` and
the request's `editor_path` are available for explicit installation selection.

Send JSON to `POST /terrain/export` with the `X-SC2-Token` header:

```json
{
  "map": "C:/Maps/Demo.SC2Map",
  "size": 2048,
  "include_units": true,
  "include_doodads": true,
  "output": "C:/Exports/Demo.png"
}
```

`size` is the horizontal pixel count: 512, 1024, 2048 or 4096. Native map aspect
ratio determines the height. Both category filters default to `true` and require
JSON booleans. Each can be disabled independently. Omit `map` in subsequent
requests to reuse the current private document. Existing output files are
preserved unless `overwrite:true` is supplied. A cold native module load can
take minutes; the server reports `busy` while the synchronous operation runs.

A successful response has `status:MAP_IMAGE_EXPORTED`, `wholeMapVerified:true`,
`objectFiltersVerified:true`, image dimensions and an authenticated artifact
download URL. Its `native.terrainExport` includes `filtersConfirmed`,
`customOptions`, `actualUnits` and `actualDoodads`. These are checked against the
request before publication. Unknown/mismatched native settings, unsupported
native adapters, black/uniform output and user-desktop visibility failures do
not publish an apparently successful PNG.

The same operation is available through the existing
`sc2_export_map_image` MCP tool. No additional MCP tools are required.

## Explicit Terrain camera (1.1)

Use `POST /terrain/capture` or the existing `sc2_capture_terrain` with:

```json
{
  "map": "D:/Projects/Example.SC2Map",
  "terrain_camera": {
    "x": 32, "y": 24, "z": 8.5,
    "pitch": 56, "yaw": 180, "roll": 0,
    "distance": 34, "fov": 27.8
  }
}
```

All eight fields are explicit finite numbers. Angles and FOV are degrees; XYZ
is the native camera target, not the camera eye position. This selector is
mutually exclusive with `map_camera_id`. It uses the original Camera Editor's
Set Game Camera command on the owned private desktop, commits the view and reads
Get Game Camera again in a fresh dialog before publishing a renderer PNG.
Clamped/mismatched settings fail numeric verification. It does not alter the
source archive, send physical input, create a saved camera or execute triggers.
The image resolution is the original native viewport resolution, returned in
the response; arbitrary output resolution is not currently exposed.

This operation is a perspective viewport capture. Use `sc2_export_map_image`
for the separate complete overhead image at 512/1024/2048/4096 pixels wide. A
`capture_map_region` rectangle remains a crop of that complete overhead export;
it is not used for custom-camera captures.

## Native visibility filters

The visibility filters control native unit and doodad models. They do not delete
placements from a map. Terrain effects such as Hatchery creep may remain when
unit models are hidden. The export represents the Editor's current placement
state; it does not execute Galaxy triggers or create runtime-spawned units.
Models and materials require the map's normal installed dependencies, as in the
original Editor.

`POST /objects/search` / `sc2_search_objects` is a separate read-only operation
over saved `Objects` XML. It supports case-insensitive ID/type/name queries,
`kinds`, `owner`, inclusive XY `bounds`, `offset` and `limit` (maximum 500).
It returns original saved XYZ, counts and pagination; it requires no Editor.
Search pagination does not change which models the image exporter renders.

Coordinate-region capture remains a crop of the native full-map image, with
its own explicit coordinate-calibration status. It is not a movable native
Terrain camera. Saved map cameras use `sc2_list_map_cameras` and
`sc2_capture_terrain` with `map_camera_id` instead.

## Reproducing acceptance checks

Generate a fresh private fixture using `tests/make_terrain_fixture.py`, then run:

```powershell
python tests/live_map_image.py --package --map <private-fixture.SC2Map> --work <fresh-private-output> --parallel --all-sizes
```

The opt-in test exports all four unit/doodad combinations and restores both
categories in one persistent worker. It independently exports a private copy
with the placements removed and compares known building/doodad regions against
that reference. It also checks independent workers, native TGA/PNG pixel identity,
all supported sizes, exact downloads, output preservation, typed invalid
arguments, saved-object filters, native compilation and exact Galaxy export.
Review the images for all four distinct corner buildings, hills, doodads,
category exclusion and the southwest crop before recording visual acceptance.

Only this toolkit's owned hidden processes are controlled or stopped. No mouse
or keyboard input is injected and the input desktop is not switched.
See [validation](VALIDATION.md) for the actual tested build, device and results.

## Native adapter maintenance

The Editor build is SHA-verified before startup. Protocol 13 requires a matching
host, bootstrap, controller, bridge and renderer capture bundle; restart workers
when upgrading. Installation paths are discovered, not tied to one machine.

The flag tree's painted checkboxes are separate from its renderer flag model.
The build-specific adapter calls the original model setter/getter on the owned
GUI thread. It verifies function signatures, the live tree HWND, reciprocal
callback/context identity and its fixed row profile before making a call.
Its bounded read-only model lookup is local to that worker, records no memory
dumps and retains no pointers after the dialog closes. A failed adapter
verification rejects the export; checkbox-only success is not a fallback.
