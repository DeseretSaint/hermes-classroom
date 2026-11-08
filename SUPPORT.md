# Support

Coursebook is a contest candidate, not a published product. Read this before asking for help; it
tells you what is known to be missing so a report does not spend time rediscovering it.

## First, check the documents that answer most questions

| Question | Read |
| --- | --- |
| How do I install, enable and verify it? | `docs/INSTALL.md` |
| Why does a route or pane look empty? | `docs/INSTALL.md` §11 (troubleshooting) |
| What is implemented, and what is only proved by tests? | `README.md` §Status and §Limitations |
| What is measured, on which commit? | `docs/RELEASE-EVIDENCE.md` |
| What does it send, and where? | `docs/PRIVACY_EGRESS.md` |
| Why is the catalog entry not installable? | `docs/SUBMISSION.md` §0 and §1 |

Known limitations that are working as designed, so they are not bugs: the desktop route needs a
window that reaches a backend (one gateway per host, CB-QA-09); the auxiliary open-response grader
lane is disabled (CB-QA-11); reminders are absent; research runs only inside plan jobs; and no
license has been chosen yet, so redistribution is not permitted.

## Opening an issue

Use the issue templates in `.github/ISSUE_TEMPLATE/`. A useful bug report carries:

- the commit (`git rev-parse HEAD`) and the `desktop/plugin.js` sha256 (`sha256sum desktop/plugin.js`);
- the Hermes Agent version and whether the Desktop half was enabled;
- the exact action, the exact error text, and whether the backend answered `health.get`;
- whether it reproduces on a clean `HERMES_HOME`.

Do not paste API keys, learner data, or a course database. Redact paths and labels.

## Security problems

Do not open a public issue. Follow `SECURITY.md`.

## What is not supported

- Older commits and unmerged branches.
- Installing from the public catalog: the entry is withheld and no pull request is open.
- Redistribution: the repository has no license.
- Requests for efficacy, mastery, child-safety or COPPA claims. Coursebook makes none of them and
  will not add one without evidence.
