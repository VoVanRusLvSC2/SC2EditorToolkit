# Multi-version hidden Editor: plan and implementation

The existing hidden-host, bootstrap, parallel-instance and input-isolation design
is documented in [PARALLEL_INSTANCES.md](PARALLEL_INSTANCES.md) and
[NATIVE_DISPATCH.md](NATIVE_DISPATCH.md). This change removes its single-build
startup restriction without treating startup as approval of arbitrary native ABIs.

## Implemented layers

1. **Portable admission.** Require an AMD64 `SC2Editor_x64.exe` with Editor
   resource identity. Known original SHA-256 fingerprints are accepted directly.
   Unlisted builds are verified by Windows Authenticode and the Blizzard signer,
   with no UI and no online revocation fetch. Neither admission path compares a
   new build number against a fixed numeric allowlist.
2. **Read-only inspector.** `HiddenEditorHost.exe --inspect-portable-editor <exe>`
   checks the same signature/role policy without creating a process or desktop.
   The API verifies its returned fingerprint against its own streaming hash.
3. **Owned startup.** Preserve suspended creation, private desktop, singleton and
   Recent Files isolation, input/cursor protection, and original-file binding.
   The host reports the actual selected fingerprint/version; the API refuses a
   fingerprint that changes during startup. User-visible Editors are not attached.
4. **Portable GUI operations.** Menu/control discovery, source generation,
   compilation, private save/reopen and viewport capture use original Editor
   operations and runtime confirmation. A changed UI reports a failed/unconfirmed
   operation rather than silently choosing another window or guessing a result.
5. **Independent native-offset capabilities.** Complete Data reflection and native
   full-map filter control remain tied to an exact verified executable profile.
   Python checks capability flags before IPC. The DLL independently hashes its
   current image before these operations and refuses error 160 on an unverified
   profile. Signature trust or a matching version string does not grant offsets.
6. **One build manifest.** `profiles/editor_builds.json` generates matching Python
   and C++ profile tables. Source builds and packaging check that generated files
   are current. The frozen package verifier checks identity modules as well as
   native binary hashes. No installed path or user name is part of the profiles.

## Current capability matrix

| Executable | Startup/UI policy | Native offsets |
| --- | --- | --- |
| 5.0.17.98310, original pinned fingerprint | Historical native acceptance retained | Verified original adapter |
| 5.0.17.98745, original pinned fingerprint | Portable path; live startup/save/generation/compile/viewport checks passed | Disabled pending a separately validated adapter |
| Unlisted original Blizzard-signed x64 Editor | Accepted automatically; live UI confirmation required | Disabled |
| Game, launcher, x86, unsigned or wrong-publisher executable | Refused before Editor launch | Disabled |

`/doctor` exposes the selected `originalEditor` profile/capability details.
Live startup returns `editorInfo`. `/modules` states
`startupVersionAllowlistRequired: false`; its known build list is not a numeric
startup restriction. `NATIVE_ADAPTER_UNAVAILABLE` is distinct from startup failure.

## Evidence and limits

On 5.0.17.98745, the owned worker opened a private map, natively saved it,
generated Galaxy and compiled it without errors, then captured a nonblack Terrain
viewport. Python and direct DLL requests both refused unverified Data-offset
calls. Observation recorded zero visible owned windows and foreground samples;
the source was unchanged and the worker closed.

The same 98745 executable also passed the strict Authenticode-only inspector,
without relying on its profile entry. An archived original 5.0.15.96883 executable
passed that unlisted-file identity path; it was not launched with a mismatched
newer installation. Future-version unit fixtures exercise the no-allowlist path
and prevent a copied version string from inheriting offsets.

These checks do not certify every future UI, renderer, locale or ABI. A complete
installed asset/dependency set is still required. A switch to another graphics
API or incompatible GUI can require a new portable adapter. Unsupported offset
features are not silently replaced with an approximate renderer or Data model.
The 98310 full-audit and full-map acceptance remains its historical baseline;
those operations were not enabled or claimed on 98745.

## Maintaining support

New signed Editor builds do **not** require a fingerprint entry merely to start.
To add a known identity or a researched native adapter, edit the manifest and run
`python tools/generate_editor_profiles.py`. Adding a hash or toggling a capability
is not native ABI validation: port/check its functions, layouts, model identity
and source preservation before enabling native-offset features.

Keep the complete matching package, restart owned workers when upgrading, and
retain startup evidence for a failed probe. API contract 1, native protocol 16
and the existing 31 MCP tool names are unchanged.
