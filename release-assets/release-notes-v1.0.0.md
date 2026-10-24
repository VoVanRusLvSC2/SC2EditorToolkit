# SC2 Editor Toolkit 1.0.0

Stable MCP/HTTP automation for the original StarCraft II Editor, scoped to the
verified original 5.0.17.98310 x64 binary on an interactive Windows x64 session.
Portable installation discovery and explicit selection are supported. The
toolkit owns hidden private Editor instances; it does not attach to a user's
visible Editor, inject physical mouse/keyboard input or switch desktops.

## New for 1.0

- Separate validated input schemas for all 31 MCP tools and the corresponding
  HTTP operations, result envelopes, tool annotations and structured error codes
  with actionable next steps. Long operations use the existing persisted FIFO
  job queue, progress, cancellation, deadlines and fresh-worker recovery.
- Immutable indexed audit queries by report ID, with exact object/catalog and
  finding filters, pagination, bounded inline results and full exact artifacts.
- Incoming original typed Data references: find which recorded objects use a
  target catalog/object and return their native field paths.
- Audit comparison: added/removed findings and added/removed/modified recorded
  object observations, with project/adapter identities and bounded pages.
- Project revision manifests: pre/post hashes of recursively declared local
  dependencies plus the installed CASC build manifest, matched to observed
  native Data source names. Unresolved/cache/physical-path guarantees remain
  explicit instead of being silently treated as verified.
- Original header-only DocumentInfo dependency metadata is recognized as empty;
  unclosed or otherwise malformed XML remains incomplete. This fixes a false
  incomplete project manifest on the tested Nydus dependencies.
- Read-only installation preflight through sc2_doctor, POST /doctor or the
  windowed API executable's doctor command. Checks original Editor identity,
  embedded native component version/protocol/hashes, renderer package, writable
  storage, desktop and optional FFmpeg/ffprobe. GPU readiness requires a live test.
- Bounded native resource batches with progress and temporary private-tree
  redraw/scroll settings restored after traversal. Renderer warmup before
  original audio recording retains strict audio/timeline confirmation.
- English setup/contracts/acceptance documentation and a reproducible allowlisted
  release packager that checks frozen toolkit code against committed source.

## Existing original Editor operations

Native Triggers XML to Galaxy generation and original compilation, exact Galaxy
export, separate Messages/Console diagnostics, private native save/close/reopen
and component comparison, saved object search, original full-map rendering with
independent unit/doodad filters, saved map cameras, cutscene PNG and H.264/AAC MP4.
Independent servers use separate work directories, tokens and owned Editors.

## Acceptance and limits

See docs/V1_ACCEPTANCE.md for the final-package measurements and private Nydus
checks, and docs/MCP_CONTRACT.md for installation and supported guarantees.
No private maps, logs, captures, machine paths or tokens are included in the ZIP.

This release does not claim exhaustive runtime Data correctness. Opaque actor
strings, computed/trigger references, resource binary integrity and transitive
binary dependencies remain outside typed reference/file presence checks. Object
audit comparison is not a complete scalar effective-value diff. Coordinate-region
cropping remains experimental. Game simulation and trigger cinematic playback
are outside the Editor toolkit's stable scope.

Upgrade the complete package and restart its server. Native protocol remains 15;
API/MCP contract is version 1. Unexpected arguments are now rejected, so clients
should use each advertised tool schema. Prior releases remain available.

Original project author and owner: VoVanRusLvSC2. Uses the existing SC2 Native
Toolkit Attribution License 1.0; preserve the required author/repository credit.
