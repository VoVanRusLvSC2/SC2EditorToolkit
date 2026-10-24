# Version 1 MCP and HTTP contract

SC2 Editor Toolkit 1.0 targets Windows x64, an interactive user session and the
original 5.0.17.98310 x64 Editor. Installation discovery is portable; an unsupported
binary fails before launch. Every server owns one hidden Editor on a private
desktop. Independent servers need independent work directories and ports/tokens.
No physical mouse/keyboard input or desktop switching is used. User-visible
Editors are never attached to or controlled.

## Install and preflight

Extract the complete release ZIP to a writable directory. Check SHA256SUMS before
running; keep the EXEs together with the supplied notices and documentation.
For stdio MCP, configure `SC2NativeMCP.exe` with `--work` and an absolute writable
directory. Use `--editor` or `SC2_EDITOR_PATH` only when discovery is ambiguous.
No developer workstation paths are required. Install FFmpeg and ffprobe on PATH
for MP4, or set SC2_FFMPEG / SC2_FFPROBE.

Run `sc2_doctor`, authenticated `POST /doctor {}`, or:

```powershell
.\SC2NativeAPI.exe doctor --work "D:\ToolkitWork" --response "D:\doctor.json"
```

The windowed executable writes the report instead of opening a console. Preflight
checks the original Editor hash, matching bundled native components against the
embedded version/protocol/hash manifest, the renderer package, writable storage,
interactive desktop and optional media tools. It does not launch an Editor.
`graphicsReady:null` means a GPU device has not been tested. Submit a
`check_document` job and a render on a private map for a live readiness check.

## Tool contracts and errors

`tools/list` advertises a separate input schema for every tool, a common result
envelope and read-only/destructive/open-world annotations. Unexpected arguments,
missing requirements, invalid types, nonfinite numbers and unsupported nested job
arguments fail before admission. No coercion of string booleans is performed. Export tools advertise their possible
overwrite behavior; existing output files still require explicit overwrite=true.
The HTTP POST operations enforce the same contracts. Existing legacy payload
fields remain; additive contract metadata is available from `sc2_modules`.

Every tool result has `outcome`: `completed`, `incomplete`, `failed`, `pending`,
or `cancelled`. This is execution/coverage metadata, not a claim that a map is
semantically correct. Job `SUCCEEDED` means its operation returned: inspect
`result.outcome`, `nativeCompilePassed`, `validationPassed`, native diagnostics
and coverage separately. Unknown/unreadable diagnostics never become zero errors.
Native generation and original compiler success remain separate observations.

Failures include `errorInfo` with `code`, `message`, `nextStep` and
`automaticRetry:false`. Version 1 codes include INVALID_ARGUMENT, NOT_FOUND,
FILE_NOT_FOUND, OUTPUT_EXISTS, WORKER_BUSY, GRAPHICS_UNAVAILABLE, STORAGE_FULL and
OPERATION_FAILED. Native controller failures also include an evidence directory and compact native
status/error fields when available. Exact native details remain in the original evidence; generic
failures are never guessed into a more specific diagnosis.

## Long operations and recovery

Use sc2_submit_job / POST /jobs/submit for audits, video, map export and checks;
poll/wait in bounded intervals. Cancellation, execution deadlines, persisted
history and fresh-worker recovery are supported. Restart marks unfinished work
INTERRUPTED; requests are never automatically replayed. A client disconnect alone
does not cancel a queued job. Work artifacts may remain after cancellation.

MCP currently supports protocol negotiation for 2024-11-05, 2025-03-26 and
2025-06-18. API contract 1 preserves named fields and meanings within 1.x;
new optional fields/tools may be added. Breaking changes require a major version.
Native protocol 15 requires the complete matching package and a restarted worker.

## Audit workflow

1. Submit `audit_data` with `map` and wait for completion.
2. Keep `reportId` (identical to `reportArtifact.id`). It is scoped to that server's
   persistent artifact store, not a filename or an ID from another server.
3. Read `sc2_query_audit` with report_id, section=objects/findings, exact catalog /
   object_id or kind/finding_status filters, offset and limit (maximum 500).
4. Use `sc2_find_object_uses` with report_id, target_catalog and target_id for
   incoming typed native Data links. Catalog matching ignores case; target IDs
   retain exact native identity. Returns source object and original field path.
5. Use `sc2_compare_audits` with before_report_id and after_report_id. Findings
   are compared as a multiset; object observations report additions, removals and
   modifications. Filter/paginate instead of downloading entire large JSONL files.

HTTP equivalents: POST /data/audit/query, /data/audit/uses, /data/audit/compare.
These operations do not launch an Editor. Original observations remain immutable
and SHA-256 checked, including after server restart. Queries provide a bounded
inline page; unusually large payloads have explicit payloadOmitted flags and
retain their identity and original full JSONL artifact references.

Incoming uses exclude actor event/message strings, trigger references and
computed/runtime links. Object comparison covers recorded references/resources
and coverage counters; it is not a complete scalar effective-value diff.
Missing files are aggregate findings: object-filtered finding pages select
directly identified findings; consult the aggregate samples or object resource
observations for file occurrences. These limitations are deliberate and explicit.

## Revision guarantees and stable scope

Audit manifests hash the source, recursively declared local dependency archives
and installed CASC build manifest before/after traversal. Changes abort publication.
The manifest is matched to observed original Data source names. Unresolved remote
cache declarations, unmatched sources and incomplete metadata remain explicit.
`projectRevisionComplete` applies to this recorded archive/build identity scope;
physical resolution paths inside the native loader and every CASC resource byte
are not independently verified. No automatic audit cache is used.

Stable core: original loading/generation/compilation, exact Galaxy export, native
diagnostics and private save/reopen, saved-object queries, native full-map export,
saved camera capture, cutscene PNG/H.264/AAC export and bounded Data observations.
Coordinate-region cropping stays experimental (`coordinateMappingValidated:false`).
Game simulation, trigger cinematic playback and exhaustive runtime Data semantics
are outside the 1.0 contract. Each limitation must remain visible to MCP clients.

Audio-enabled video exports prime the selected original renderer before the
real-time PCM pass. Native timeline/mixer synchronization checks remain enforced;
a starved graphics/audio device returns an error instead of publishing an
unconfirmed MP4. Render scheduling and storage resources still matter under load.
