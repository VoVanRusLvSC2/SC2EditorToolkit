For a complete effective-catalog traversal, use the separate [Data audit](DATA_AUDIT.md) operation. The individual-object operations below retain their narrower scopes.

# Original Editor Data, associations and resource checks

These operations use the original Data workspace in the server's owned hidden
Editor. They are not an independent XML inheritance engine. Supply a saved map
or mod with its installed dependencies, or reuse the current private document.
The normal Editor, mouse, keyboard and input desktop are not controlled.

## Read Data

`POST /data/read` or `sc2_read_data`:

```json
{"map":"C:/Maps/Demo.SC2Map","catalog":"Unit","object_id":"Marine","field_limit":100}
```

Supported source catalogs are `Unit`, `Model`, `Actor`, `Abil`, `Behavior`,
`Effect`, `Sound`, `Texture`, `Weapon`, `Validator`, `Upgrade`, and `Requirement`.
Selection requires an exact raw internal ID, a unique original catalog entry
and corroborating original XML. Localized display-name equality is insufficient.
Some native UI changes are committed from the Editor's outer idle loop, so
selection, XML and field observations use separate owned-thread requests.

Visible list-view cell strings can be clipped to the column width. The API
therefore obtains complete fields/values with original **Copy As Text**, captured
through a process-private clipboard in the owned Editor. Native Win32/OLE
clipboard hooks remain private to that process and never forward clipboard
operations to the user's system clipboard. If private isolation cannot be
installed, Copy is not invoked. If full serialization, headers and row counts
cannot be confirmed, `complete` is false; clipped strings are not presented as
verified complete values.

Fields preserve original formatting, arrays and object columns. Values are
strings, not guessed Python numeric types. Basic-label and structure indicators
are retained in `displayField`; `field` exposes the raw key without those display
decorations. The original Editor supplies inherited/default/overridden values.
The observed object source is returned, but per-field source provenance is not
inferred. The original source filter is set to All Data; `dataSpace` reports the
current native Data Space (normally Default Space). An arbitrary Data Space
selector is not exposed. `field_offset`/`field_limit` paginate the response; the immutable
`dataArtifact` contains the complete captured report. `include_xml=true` also
returns the original XML view text, which can include the whole selected catalog.
XML view text is not advertised as a flattened effective-value export.

## Find associated objects

`POST /data/links` or `sc2_data_links` accepts the same exact source identity,
plus optional `query`, `offset`, and `limit`:

```json
{"catalog":"Unit","object_id":"Marine","query":"GuassRifle","limit":100}
```

The response includes the original Object Explorer tree and catalog-qualified
`relatedObjects` where the raw native label explicitly exposes an ID. For
example the same ID can occur in Effect and Weapon catalogs and remains two
distinct objects. Unknown group types/IDs remain unknown. These are the native
Explorer's associations; direction, direct versus transitive edges and exhaustive
global usage coverage are not inferred. The source catalog list above may be
narrower than the target catalogs mentioned by Explorer.

## Check main Model file availability

`POST /data/resources` or `sc2_check_resources`:

```json
{"catalog":"Model","object_id":"Marine"}
```

The adapter uses the original non-raw field serializer to resolve native Model
path tokens. It selects only that original Model field, opens its native Browse
dialog and checks the merged **Archive Browser** tree against the complete
resolved path. Native path components and selection/OK readback must match;
clipped list cells and a guessed token substitution are insufficient. File
dialogs are cancelled and their closure is confirmed without saving values.
Cold native module/browser initialization can take minutes; reuse the worker
and use job status rather than a short client-side network timeout.

`resourceValidationPassed=true` means this scoped **main Model file presence
check**, with readable clean native operation diagnostics. Confirmed absence
returns false and `resourceErrors` with `MAIN_MODEL_FILE_MISSING`, separately
from actual Messages/Console errors. Unreadable diagnostics, unresolved paths,
unsupported catalogs or unconfirmed browser readback remain incomplete/unknown.
Inspect `resourceScope`, `assetLookup`, `assetNative` and `assetDiagnostics`.

This command does not certify model binary integrity, nested textures,
animations/sounds, every unused map asset, actor events or runtime behavior.
Other source catalogs remain readable through `/data/read` and `/data/links`,
but their resource availability is not advertised as implemented.

A missing model can render a checker placeholder with no Console error. A
nonblack frame is therefore not used as evidence that a file exists. Automatic
Data-to-Cutscenes preview is excluded from this operation; `previewRequested`
is false. Existing explicit cutscene/terrain capture APIs remain separate.
The resource operation does not replace the worker's current cutscene.

These Data menu/control paths are build-specific, with the same verified binary
guard as the toolkit. English Data menu matching is required by this adapter;
other UI localizations and Editor builds need separate validation.
