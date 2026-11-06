# Privacy and egress

Disclosure is per operation, not one generic "your model provider" sentence. This document
states what each Coursebook operation can send, where it goes, and which parts exist today.

Read the status column first. Coursebook 0.1.0 sends nothing. There is no lesson chat, no
planning, no grading, no research, no media generation and no export, so there is no path that
could send anything. The rows below describe the contract the feature work must meet, not
capabilities you can use today.

## Egress inventory for 0.1.0

| Operation | Destination | What would be sent | Status |
| --- | --- | --- | --- |
| Install and load | local only | Nothing. The package is read from disk | Working |
| Pane health check | local backend | Nothing. `ctx.rest` to `/api/plugins/coursebook/health` inside Hermes | Working |
| `coursebook_status` tool | local only | Nothing. Reads local health and returns JSON to the agent | Working |
| Lesson chat | selected chat provider, plus any configured external memory provider | Lesson context, the learner message, the objective and the pending check | Not implemented |
| Planning and grading | auxiliary provider route configured for the profile | Objective, rubric, the attempt text, prior evidence summary | Not implemented; the route is gated on a latency and invalid-output probe |
| Research | configured search and fetch services, and the named sites themselves | The research query; later fetches request specific pages | Not implemented |
| Image and speech | the configured image or text-to-speech provider | The visual spec or the text to be spoken | Not implemented |
| Community export | nowhere. Export is a local file and performs no upload | Only the reviewed pack files | Not implemented |
| Parent mode planning | auxiliary provider, through backend jobs | Parent brief, sources, plan content | Not implemented |

The plugin registers three chat lifecycle hooks (`pre_llm_call`, `post_llm_call`,
`post_tool_call`). In 0.1.0 they are declared no-ops that return `None`: they read nothing,
store nothing and forward nothing.

## Local persistence

When the backend kernel lands, state lives in profile-scoped SQLite at:

```
$HERMES_HOME/plugin-data/coursebook/data.db
```

Not inside the plugin directory, because removing the plugin deletes that directory. The path is
resolved per call so a profile switch cannot reuse another profile's handle.

Hermes itself keeps session transcripts, logs and usage records under `$HERMES_HOME`. Those are
host behavior, not Coursebook behavior. Coursebook does not read them for policy decisions and
does not copy them into packs.

"Local" describes storage. It does not mean the model runs locally. Inference goes to whichever
provider the Hermes profile is configured to use.

## What Coursebook refuses by design

- No external-memory sync of schoolwork through Coursebook's own paths. If a host-level
  integration would sync it anyway, the preflight surfaces that integration and states that
  Coursebook cannot disable it.
- Parent observations are stored as `parent_reported` and are never merged with automated
  mastery. Parent reflections are excluded from community export by construction, not by a
  promise to strip personal data afterwards.
- No request for names, birthdates, school identifiers or full schoolwork by default. Pasted
  material is offered redaction, and the provider is disclosed before any upload.
- Parent planning uses backend jobs rather than persistent child-related chats where possible,
  which avoids unnecessary transcript and memory retention.
- A pack is untrusted data. Its prose never becomes policy, and it cannot carry executable code,
  tool calls or learning history.
- No telemetry and no usage reporting. Coursebook stores no credentials, declares no
  `requires_env`, and has no `config_schema`.

## Parent and child boundary

Parent mode means a parent prepares a lesson for a child. Children do not chat with Coursebook,
and Coursebook does not assess a child. Activity planning carries a setting-appropriate safety
checklist (heat, sharp objects, small parts, allergies, water, roads, tools) and suggests content
prerequisites only. It does not suggest disability, giftedness, attention or developmental
diagnoses.

There is no COPPA compliance claim and no child safety certification. Those are not things a
plugin can grant itself, and Coursebook does not claim them.

## Retention and deletion

`contracts/db.v1.json` contains the deletion policy the kernel must implement: deleting a course
removes its dependent rows, and exported packs never include learner events. In 0.1.0 no schema
exists, so there is nothing to retain and nothing to delete. Retention controls ship with the
migrations, not before them. Owner: Cinder.

## Open item

The auxiliary grader route is not assumed. If the measured path cannot meet the deadline and the
invalid-output path, grading ships with the route that can, and this document is updated before
the demo. Owner: Atlas.
