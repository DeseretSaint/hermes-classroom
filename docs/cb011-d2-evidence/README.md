# CB-011-D2 evidence — final approval is reachable from the live probe

Backend: isolated test home, `hermes serve --isolated` on `127.0.0.1:44219`, `wire_version` 6,
agent half linked at `.worktrees/t_6fb0b580`. Course under test had a complete lesson set
(4 objectives, 4 validated lessons) seeded through the shipped pipeline with only the two LLM
seams faked (`FakeLLM`), the same seam `tests/test_generation.py` uses; every RPC below went over
the real HTTP wire.

## Before (`git show 68816ad^:scripts/cb011-parent-probe.py approve`)

See `cb011-d2-before-refusal.log`:

```
REFUSED parent.final.approve VALIDATION_FAILED: RPC request violates cb.rpc at <root>:
        'expected_revision' is a required property {"path": "<root>"}
```

## After (`scripts/cb011-parent-probe.py approve`)

See `cb011-d2-approve.log` and the full envelope trace `cb011-d2-approve-trace.json`
(`expected_revision: 1` on the `parent.final.approve` call):

```
ok  library.list
ok  parent.final.approve
   revision: 2
   approval: {"state": "active", ...}
   export: {"ready": true, "blocked_reason": null}
ok  parent.export
   files: [12 files across parent_guide / learner_page / answer_guide]
   artifacts: [pack 8871 B, pdf 7352 B, export 8871 B]
ok  artifact.get (x3)
```

The approval row read back from the store:

```
crs_60369f196bb44cf2abfadc54d8a2a477|active|sha256:3629c6e3...|2026-11-06T16:42:10.516480+00:00
```

## Why the revision comes from `library.list`

`course.outline` returns `revision: 0` by design (opening an outline must never move state), so
fencing on it produced `STALE_REVISION` against an enrollment at revision 2. `library.list` is
where the studio's parent-course rows get their `revision`; the probe now reads the same field and
retries once on `STALE_REVISION`.

## Desktop

The same call in `desktop/plugin.js` (`StudioExportPanel`) also omitted the fence. It now passes
the `revision` prop as `expectedRevision`, refreshes on a stale refusal and adopts the returned
revision. A live screenshot of that button is **not** included: the shared CDP window on `:9337`
renders no route at all (even `#/artifacts` shows the session list) both before and after this
change, so there was no honest way to capture the panel without restarting another profile's
Electron process.
