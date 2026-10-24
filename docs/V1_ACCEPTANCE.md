# 1.0.0 release acceptance

Release acceptance is recorded here after testing the final package. Private maps,
captures, tokens, machine paths and raw native logs are excluded from the repository.
The stable contract and supported scope are defined in MCP_CONTRACT.md.

## Release gates

- Precise input validation for every MCP/HTTP operation; structured result/error
  contract, initialized stdio and frozen executable checks.
- Immutable indexed audit queries, exact incoming typed references, paginated
  findings/object comparison and negative/tampered/cross-store controls.
- Map plus local dependency/build manifests with pre/post revision checks and
  explicit unresolved physical/cache/resource-byte guarantees.
- Final-package Nydus original native compilation, full Data traversal, new audit
  queries and comparison; original source preservation and hidden-worker monitoring.
- Repeated private native open/save/reopen/compile/export/render workflows,
  cancellation/deadline recovery, independent instances and shutdown checks.
- English setup, scoped compatibility, installation preflight and checksummed ZIP.

Pending live measurements are not acceptance evidence. Dated historical evidence
remains in VALIDATION.md and PRESENTATION_READINESS.md.

## Recorded 1.0 checks — 2026-10-24

These results use original Editor 5.0.17.98310 x64 on the tested Windows/GPU
configuration. Private source archives, logs and captures are retained locally;
they are not included in the source repository or public package.

| Check | Observed result |
| --- | --- |
| Python regression | 113 tests passed, including header-only dependency metadata versus malformed XML |
| Native regression | 7 suites passed, including owned TreeView settings restoration on exceptions |
| Frozen HTTP validation/authentication | Passed |
| Frozen windowed MCP stdio | Initialization, listing and calls passed; 31 tools, per-tool input schemas and common output envelope |
| Fresh ZIP installation | Doctor and actual MCP stdio passed from a path containing spaces and Unicode; no Editor launched by preflight |
| Source/bundle consistency | Embedded frozen toolkit code, native component manifests, renderer and archive helper verified against the release inputs |
| Two concurrent hidden Editors | Distinct PIDs/instance IDs, 6 native conversions, 0 compiler errors; one instance still compiled after the other stopped |
| Instance isolation | Cross-server token and artifact requests rejected; exact Galaxy downloads verified |
| Native lifecycle | Private save, close, disk reopen, component comparison and localized content passed |
| Data effective values | Inherited Marine LifeMax 45 and private override 73 read from native Data; original object explorer and Abil/Effect/Sound reads passed |
| Negative diagnostics | Malformed Data and missing dependency produced original Editor failures; a following healthy document passed |
| Deadline/recovery | A one-second job deadline stopped only its owned worker; the fresh worker completed the next healthy check |
| Full-map filters | Native PNG at 512 horizontal pixels; four unit/doodad combinations and restoration in one persistent document, compared with semantic landmarks and visually reviewed |
| Original pixels | Native TGA-to-PNG pixels and downloaded artifact bytes matched |
| Water fixture | A pre-existing campaign map exported through the original Editor; terrain, trees, placed objects and water surfaces visually reviewed |
| Media | Native Nydus cutscene PNG plus non-silent H.264/AAC MP4 decoded successfully during another worker's compilation; audio/timeline delta about 56 ms |
| Input isolation | No physical input injection or desktop-switch API; no owned visible windows or foreground samples on the user desktop |

The map-filter run observed the user's input desktop changing to the screen saver.
The toolkit did not switch it. The parallel run observed the screen-saver desktop
throughout. Other simultaneous owned tests ended during parallel testing; a
decreased global process count is not evidence of controlling existing Editors.
Each run separately confirmed that its own workers closed and source archives
remained unchanged.

## Final native Nydus audit and restart acceptance

The original Nydus audit completed with the original Editor and real local
dependencies. It remains immutable, including its original false-incomplete
dependency-metadata result. After fixing header-only DocumentInfo parsing, the
same source, dependency and build hashes were revalidated without repeating
unchanged native getter/resource observations. A separate proof records the
corrected complete manifest. Native component bytes are identical between both
packages. The added-Model fixture completed its entire native audit using the
final fixed package, including correct pre/post dependency manifests.
The supplied Nydus mod and each private document remained unchanged.

| Measurement | Observed result |
| --- | --- |
| Original catalog coverage | 109 / 109 |
| Original effective objects / native getter visits | 50,129 / 7,367,409 |
| Getter failures | 0 in both audits |
| Original typed catalog references | 103,197 |
| Original unique resource paths | 26,041; 22,592 present, 3,449 absent |
| New native Editor errors | 0; confirmed clear in both audits |
| Declared project identities | Source, two local authored dependencies and installed build manifest verified before/after |
| Incoming references | Original Unit/Marine WeaponArray[0].Link to Weapon/GuassRifle confirmed |
| Audit queries | Exact object lookup, bounded missing-resource pages and self-comparison passed |
| Changed-project comparison | Exactly one added Model/ToolkitV100MissingModel; added findings, changed revision and matching Editor adapter confirmed |
| Restarted frozen MCP | 31 tools; all three saved-audit operations passed on the real native reports after HTTP shutdown; no Editor started |
| Invalid MCP requests | Unknown report and extra argument rejected with typed errors |
| Shutdown | Both native audits' owned worker/server closed; baseline Editors preserved |

Both reports deliberately retain `validationPassed:null`: absent optional targets,
unresolved typed targets and unclassified values are findings/coverage gaps,
not an exhaustive game-correctness certificate. The earlier one-hour acceptance
harness was cancelled without publishing a complete report; the final harness
uses the product's four-hour full-audit execution budget.

All listed release gates passed within the supported scope. The public package
contains the reviewed code, English documentation and checksummed allowlisted
files; private maps, reports, captures and credentials remain excluded.

## Supported interpretation

The stable contract describes tested operations, not exhaustive game correctness.
Typed Data references and merged Archive Browser presence checks do not resolve
opaque actor strings, trigger/runtime/computed references, nested binary
dependencies or resource binary integrity. Audit comparisons cover recorded
references, resources and coverage counters, not every effective scalar value.

Project revision completeness concerns declared local archive hashes and the
installed build manifest matched to observed native source names. Native-resolved
physical cache paths and individual CASC resource bytes remain unverified.
Coordinate-region cropping remains experimental. The final filter matrix above
does not certify all output sizes, GPUs, maps or water types.

Reproduction entry points: `tests/live_editor_workflows.py`,
`tests/live_map_image.py`, `tests/live_parallel_workers.py`,
`tests/live_audit_acceptance.py`, `tests/live_saved_audit_mcp.py`, and
`tests/live_resource_traversal.py`. Supply private fixtures explicitly; these
tests are opt-in and never attach to an existing Editor.
