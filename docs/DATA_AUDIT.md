# Original Editor Data audit

`POST /data/audit` and MCP `sc2_audit_data` read the effective Data model of an
owned hidden Editor. All 109 native catalog slots are visited, including empty
catalogs, class defaults, inherited fields, nested structures and arrays.
Loaded map/mod dependencies contribute to the same original effective model.
Overridden historical definitions are not counted as additional effective objects.

The adapter is read-only. It runs on the owned document's GUI thread and uses
the original native field getters. Typed catalog links are resolved against the
original effective catalog entries. Typed virtual file paths are checked in the
original merged Archive Browser, launched with the Editor's `browse` command.
No desktop screenshot, physical input, input-desktop switch, external replacement
Data parser, original EXE modification or attachment to a visible Editor is used.

## Start an audit

```json
{
  "operation": "audit_data",
  "arguments": {"map": "D:/Projects/Example.SC2Map", "limit": 100},
  "timeout_seconds": 14400
}
```

Submit this body to `POST /jobs/submit`, then use the existing job status/wait
routes. MCP supports the same body with `sc2_submit_job`. A synchronous call can
use `POST /data/audit` or `sc2_audit_data` with just the `arguments` object.
Omit `map` to audit the worker's current saved document. `.SC2Mod` is supported.
`limit` bounds summary finding samples to 1–500; it never limits traversal or the
downloadable reports. Use a different `--work` for each independent server.

Progress reports the current catalog and observed object/field counts. The
existing FIFO, cancellation and deadline watchdog apply. A cancelled or failed
native operation never publishes a complete audit and never automatically
replays against another document. Only the owned worker can be discarded.

## Results and coverage

- `catalogTraversalComplete`: every effective object in all native catalogs
  was traversed, with verified pagination and stable original Data sources.
- `referenceAndFileValidationComplete`: false when getters could not be read,
  types remain opaque, a target could not be resolved or paths retain tokens.
- `counts`: objects, field/leaf values, typed links, missing/unknown targets,
  resource occurrences, unique files, missing files and coverage gaps.
- `dataSources`: source names read from the original Data source selector.
- `mapRevision`: SHA-256 of the supplied archive. Both supplied and private
  archives must remain unchanged for a successful report.
- `objectsArtifact`: complete JSONL records with catalog/ID/class, default flag,
  typed references, resource paths and coverage counters/samples.
- `findingsArtifact`: complete JSONL findings; summary samples may be limited.
- `reportArtifact`: downloadable JSON summary, including native diagnostics and
  the hidden-desktop observation. Artifacts use the existing authenticated,
  opaque download IDs and SHA-256 integrity checks.

Missing typed targets/files are findings, not inferred gameplay failures.
Optional references and unused class defaults can legitimately be missing.
`allObservedTypedTargetsPresent` is the strict presence result, including optional
and default-template references. `validationPassed` is false for confirmed new
native Editor errors, true only when coverage, targets and diagnostics are
confirmed clear, otherwise null. Missing optional references alone do not assert
that the map is broken.
Native Messages/Console observations remain separate from Galaxy compilation.

## Boundaries

The traversal samples the original saved Data model's default variant (0).
It does not execute triggers or apply runtime upgrade/player modifications.
`mapRevision` identifies the supplied archive. Version 1.0 additionally records
`projectRevision` and `dependencyManifest`: recursively declared local archives
and the installed CASC build manifest are SHA-256 checked before/after traversal.
The observed native source names must match the recorded identities for
`projectRevisionComplete:true`. Unresolved remote/cache declarations and unmatched
sources remain explicit. Physical native-loader paths and all individual CASC
resource bytes are not independently verified (`nativeResolvedPhysicalPathsVerified:false`).
No automatic cache reuses a report for another revision.

Unclassified-value counts are conservative coverage counters, not error counts;
they also include engine/scalar types without a verified reference visitor.

Opaque native types, ability-command arguments, actor event/message strings,
computed catalog references and unresolved tokens remain visible coverage gaps.
String content is not guessed to be a catalog link or filename.

File presence does not prove binary integrity, correct model animations,
transitive textures/sounds inside a binary, rendering quality or gameplay
semantics. Existing native load diagnostics and separate visual/game tests remain
useful. Unknown or unreadable native diagnostics are never reported as zero
errors.

The reflection adapter is pinned to the verified original x64 Editor build
5.0.17.98310 and checks native lookup signatures and metadata bounds. Installation
paths are discovered/configurable. Other binaries are rejected before native
calls; the code does not guess offsets for another version.

## Indexed queries, incoming uses and comparison (1.0)

A completed audit publishes an additional immutable SQLite index artifact and
`reportId` equal to `reportArtifact.id`. Use `sc2_query_audit`,
`sc2_find_object_uses` and `sc2_compare_audits`, or the corresponding authenticated
`/data/audit/query`, `/data/audit/uses`, `/data/audit/compare` POST endpoints.
Queries do not launch an Editor, work after reopening the artifact store and
check original report/index hashes. Results are bounded and paginated.

See [the version 1 contract](MCP_CONTRACT.md) for arguments, revision guarantees,
inline omission flags and comparison limits. The v0.14 report format has no index;
create a new 1.0 audit before using the new query operations. Historical reports
remain downloadable and are never silently rewritten.

Resource checks use bounded requests of at most 512 paths / 1 MiB encoded input,
with resourcePathsChecked, uniquePaths and resourceBatch progress. Every expected
path must occur exactly once across the complete set of native responses before
audit publication. Cancellation/deadlines remain active between batches.
The original private Archive Browser tree is temporarily redraw-suppressed during
traversal and restored on every exit; no system animation preference is changed.
