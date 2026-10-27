# Data reflection adapter maintenance

The public operation and its limits are described in [DATA_AUDIT.md](DATA_AUDIT.md).
This note explains why the adapter must not be enabled for an unverified binary.

The adapter applies only to the original x64 Editor 5.0.17.98310, SHA-256
`e561d76903221bdcd4585b9496bba1d2b9c5ae13b8fbe8c8469d213f22823d91`.
The host/controller validate that identity before startup/native requests. The
DLL also checks the original scope/field lookup signatures, module ranges,
catalog identities, pointer readability and traversal bounds. No EXE bytes are
patched. Calls are confined to the exact owned document GUI thread/private
desktop. A different binary needs a separately researched and tested adapter.

The original catalog manager has 109 slots. The dense entry collection includes
overridden historical versions; it is not a list of unique effective objects.
The audit uses the effective symbol-slot lookup, retains each non-null entry,
and verifies its native symbol index against its original ID record. Native
class-default objects are included and explicitly flagged.

An object's original scope descriptor enumerates its field descriptors. The
adapter uses each field's original getter and recurses through its native nested
scope. The getter receives the field, an original object/value reference,
an output value reference, an in/out element index, a variant selector and an
auxiliary index. A value reference occupies two 64-bit words. Arrays follow the
original getter's returned index. `0x2001002b` is normal array termination; a
declared array capacity is not the number of materialized elements. Other
getter failures become explicit coverage gaps.

Native type category 9 identifies a catalog link. The link's original symbol
record supplies the exact target ID, and the effective catalog lookup determines
whether it exists. Explicitly verified adapters also visit ability-command
ability targets and behavior-link arrays. Ability-command arguments remain
unvalidated. Unresolved tokens remain unknown. Generic strings are not guessed
to be links or filenames.

The verified original file-path type family shares a native formatter. Its
interned record contains an original UTF-8 SSO string; an interior path-buffer
view is a different representation and must not be treated as that SSO string.
Native typed paths are checked with the Editor's merged Archive Browser. The
browser is opened with the fixed `browse` command; no caller text is executed.
Preview is disabled, complete sibling lists are cached, matching is case
insensitive, and only file leaves count as present. The browser is cancelled,
not accepted or exported.

Schema 2 also invokes each materialized leaf's original type formatter on the
owned GUI thread. Its output is an original growable UTF-8 SSO string, initialized
with bounded inline storage; any original heap allocation is released with the
same original allocator. Formatter errors, unsupported/no-op struct formatters
and truncation never become successful empty values. Native allocation/read
failures abort publication. Verified numeric types also expose scalar bits,
preserving differences below textual formatter precision. Other raw native
layouts and pointers are not exported. This serializes actor-event strings but
does not turn their contents into verified reference edges.

Pages contain whole objects and an explicit next offset. The transport bound
may shorten a page at an object boundary; it never truncates an object and
reports success. One oversized object or an unbounded/unsupported native
structure fails the request. Python verifies stable catalog/source identity,
exact pagination and complete file-result identity before publishing immutable
JSONL/report artifacts. No cross-document pointer or virtual-file cache survives
between requests.

Validate any adapter change using both real projects/dependencies and private
negative controls: an undefined typed ability/weapon target, an existing model
file and a deliberately absent file. Check exact IDs and field paths, complete
catalog traversal, source hashes, original diagnostic evidence, artifact hashes,
and the absence of visible/foreground windows and physical input.
