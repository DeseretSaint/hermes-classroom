# X post — draft

Everything below is measured on the tree named at the bottom. Nothing here claims a capability that
`docs/ACCEPTANCE-RUN.md` does not record.

## Post (≤ 280)

> Hermes Coursebook, built on @NousResearch Hermes: give it a topic, it plans a course, teaches it in
> lessons, and checks you with evidence attached — "first try, no hints" or "override, not
> independent evidence". Four surfaces: Home, Courses, Workshop, Parent Studio. 38s demo.
> hermes-classroom

## Thread, if you want the receipts (each ≤ 280)

1. **The claim.** A course is not a chat log. It has a plan with validation, sections with
   objectives, lessons, and checks whose answers carry provenance: hinted, first try, or overridden.
   The UI says which, per check, and counts "independent evidence" instead of a completion bar.
2. **What the demo shows.** Home → Courses (14 on this profile, Review due first) → the L0 Japanese
   course (*Tell everyday affection from a direct romantic declaration*, section 2 of 4) → the check,
   with the learner's own saved lesson text under it.
3. **What it deliberately doesn't show.** In this build the check's answer field is bound to a live
   lesson chat, and the screen says so in its own words — *"This lesson is no longer connected to its
   chat, so Submit is off."* Starting a run leaves the plugin for the session surface. That is a real
   limitation and it is in the acceptance record, not hidden behind a cut.
4. **The receipts.** Release tree `172b61aa` (+ `82a0866a` copy fix, `15e1301d` proofs, `2c001e7a`
   packets), `desktop/plugin.js` `98400108…c395`, re-buildable from its own `desktop/src`. Every demo
   frame names the module it came from.

## Notes before posting

- Replace `hermes-classroom` with whatever repo or handle you want the post to name.
- The demo file is `docs/launch/captures/film/coursebook-demo.mp4` (38.0 s, 1920×1080, under the 90 s
  limit).
- `docs/SUBMISSION.md` still names release tree `b9f4a19`; that line predates all of this work.
  `docs/ACCEPTANCE-RUN.md` is the current record and names the tree and module the demo was captured
  on.
