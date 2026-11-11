# What a label can and cannot prove

A pack carries trust facts, and they stay separate on purpose. There is no single "safe" or
"verified" badge, because those words would merge four different measurements into one claim.

- `integrity_verified` — the bytes on disk match the hashes in the manifest. It says nothing about
  whether the teaching is good.
- `automated_checks_passed` — the structural and teaching minima this build can test without a
  person passed. It is a machine result.
- `human_review_recorded` — a named person reviewed the pack and their review is on record. This
  pack does not carry it.
- `model_assessed_support` — the sources were read and judged by a model. That is a support finding,
  not an independent validation.

One more word appears inside a check: `audit_state`. A check written `audit_state: "unreviewed"`
means exactly that — **no human review of that check is recorded**. It is the honest default for a
pack whose checks are unreviewed, and it is not a failure. What would be dishonest is reading a
matching hash, or a green automated run, as a human review or as a statement that the content is
true.

So read the labels as a list of separate facts. When a pack page says "Validated", ask which of
these four it means. In Coursebook it means the first two, and the page says so beside the word.
