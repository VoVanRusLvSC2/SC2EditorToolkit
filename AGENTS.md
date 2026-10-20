Keep all editor automation inside the owned hidden worker; never attach to or
control the user's visible editor. Do not send mouse/keyboard input and never
switch the input desktop. Logical focus inside the SC2Native private desktop is
allowed; the technical render window on the input desktop must stay invisible.

Native generation and native compilation are distinct checks. Only the original
Editor's confirmed compiler result may be reported as native compilation.
Keep compiler diagnostics separate from Messages/Console logs. Unknown/unreadable
logs must be reported as unknown, not as zero errors.

Resolve GUI elements by Library/Type/Id and ownership. Never choose the first
same-name variable or first preset with script value null/true/false. Do not
change user XML, mods, dependencies, previous releases or the installed EXE.

Do not commit tokens, runtime state, user maps/mods, native binaries, test
captures containing user content or local machine paths. Live tests are opt-in
and must use owned private copies. Shut down owned workers after testing.
