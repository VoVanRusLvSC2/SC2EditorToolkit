# Owned jobs and map reports

All normal HTTP and MCP operations use one bounded FIFO queue per server.
One server owns at most one hidden Editor. Independent servers can run in
parallel; the queue is not a global worker pool. No mouse/keyboard injection,
input-desktop switching or attachment to a normal Editor is used.

## Submit and observe

`POST /jobs/submit` returns HTTP 202 immediately:

```json
{"operation":"check_document","arguments":{"map":"C:/Maps/Demo.SC2Map","save_reopen":true},"timeout_seconds":1800}
```

Use `POST /jobs/status`, `/jobs/wait`, or `/jobs/cancel` with
`{"job_id":"<returned jobId>"}`. Wait accepts `wait_ms` from 0 to 30000.
Authenticated `GET /jobs/<jobId>` is equivalent to status. The same server token
is required for all job operations and artifact downloads. Job IDs from another
server are unknown. MCP exposes `sc2_submit_job`, `sc2_job_status`,
`sc2_job_wait`, and `sc2_job_cancel`.

Existing synchronous routes/tools remain usable; they enqueue and wait for
their own result. They do not bypass already queued work. Video's existing
status/cancel HTTP endpoints remain available out of band.

Statuses: `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `TIMED_OUT`,
`INTERRUPTED`. Success means the operation returned without a `FAILED` status;
an operation's own incomplete/unknown validation fields must still be checked.
Progress reports phases and elapsed time, not invented completion percentages.
The queue permits 32 pending jobs and retains up to 256 recent job records.
Deadlines cover execution, not time waiting in the queue, and accept 1..14400
seconds (default 1800; video export and full Data audits default to 14400).

## Cancellation and recovery

A queued cancellation never starts the operation. Running cancellation or an
expired deadline requests termination of only the server's owned private Editor,
after checking its PID and process creation time. It does not interrupt a native
callback and then reuse that Editor. The native controller retains its IPC until
the callback completes or the owned process exits. The queue waits for the
operation to unwind before running another job.

The cancelled/expired request is never automatically retried. Its partial
private files and any explicitly requested external output may already exist;
cancellation is not a transaction rollback. A following request supplying a map
can start a fresh owned Editor. Requests requiring current in-memory state must
reopen their document first. Recent history is stored privately under the
server work directory. On restart unfinished jobs become `INTERRUPTED`; no job
is replayed automatically.
Recent artifact identities (up to 4096) are persisted as well. Downloads require
the restarted server's new token and still verify exact file hashes. Modified
or removed output is not silently served. Each server requires its own `--work`;
an exclusive work-directory lock prevents two servers from sharing job records,
tokens or exports accidentally. A rejected packaged startup exits without a
desktop error dialog; inspect the unique JSON under `startup-errors` if needed.
A job-history write failure is reported as failure instead of leaving RUNNING
forever; an unpersisted submission is never admitted to execution.

## Revision-bound native report

`POST /editor/check` or `sc2_check_map` accepts `map`, optional
`save_reopen`, `include_diffs`, `scope`, `context_label`, and normal Editor
startup selection. It loads a private archive, opens original Data, collects
per-operation Messages/Console diagnostics, generates Galaxy, invokes the native
compiler and exports exact Galaxy bytes when generation is verified.
`save_reopen=true` additionally uses original serialization, closes/reopens the
private saved archive and compares its components.

The response includes source SHA-256/map revision, original Editor identity,
individual checks and diagnostics, native generation/compilation booleans,
source preservation, elapsed time and an immutable downloadable JSON report.
Compiler errors remain separate from map/Data messages. Unknown/unreadable logs
produce an incomplete result, never a clean bill of health. These checks do not
execute gameplay or prove semantic equivalence of converted GUI triggers.

## Additional private regression cases

Generate fixtures without changing or publishing the input maps:

```powershell
python tests/make_validation_fixtures.py --base C:/Maps/Healthy.SC2Map --output local-tests/validation-cases --water-map C:/Maps/Water.SC2Map
```

The manifest identifies a healthy copy, a Marine LifeMax override (73), an
intentionally missing model, malformed Data XML, an intentionally missing
dependency and optional nonempty original water map. The fixture builder checks
source preservation and refuses guessed dependency-header layouts. Water needs
visual review of an original overhead export; a nonempty component alone is
not proof that water rendered. A different mod/dependency stack must also be
tested separately. Fixture maps, captures and machine-specific evidence remain
private and are excluded from Git and release packages.
