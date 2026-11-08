# Security policy

## Supported versions

Coursebook ships as a Hermes Desktop plugin from this repository. There is no published release
yet: the catalog entry is withheld and no tag exists, so only the commit currently pinned by
`catalog/coursebook.yaml` is supported for security reports. Older commits are not maintained.

## Reporting a vulnerability

Do not open a public issue for a security problem. Use GitHub's private vulnerability reporting on
`https://github.com/DeseretSaint/hermes-classroom` (Security → Report a vulnerability), or contact
the maintainer through the repository owner account. This repository is private during the contest
period, so the advisory path is the only one that stays confidential; if it is unavailable to you,
say so in a plain issue that contains no exploit detail and the maintainer will open a private
channel.

Please include: the commit you tested, the Hermes Agent version, the exact command or UI path, what
you expected, what happened, and the smallest reproduction you have. Do not include real learner
data, credentials, or provider keys in a report.

## What is in scope

- The plugin's agent half (`coursebook/`), hooks, tools and RPC surface.
- The Desktop half (`desktop/plugin.js`) and its routes, panes and media rendering.
- The frozen contracts in `contracts/` where a consumer could be misled by a response.
- Anything that lets a learner see a reference answer for an open check, cross a profile's data
  boundary, or make Coursebook send schoolwork to a host it did not disclose.

## What is not in scope

- The Hermes host itself, its gateway binding, or its plugin loader. Report those to the Hermes
  Agent project.
- Model output quality. Coursebook bounds and records model work; it does not claim a model is
  correct, and an unhelpful lesson is not a vulnerability.
- The known limitations listed in `README.md` and the catalog entry's `known_issues`, including the
  one-gateway-per-host recording constraint (CB-QA-09) and the disabled auxiliary grader lane
  (CB-QA-11).

## Disclosure

The maintainer will acknowledge a report, confirm the affected commits, and coordinate a fix and a
disclosure date with you. No bounty is offered. This policy does not promise a response time.
