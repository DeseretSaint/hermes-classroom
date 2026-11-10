# CP-021 — Discover / Workshop (R-DISC) copy and state inventory

Card body: `docs/concept-parity/cards/CP-021.md` (this card section starts line 34).
Spec: `SPEC-V3.md` §5.2 (lines 408–460), §3.10 (289), §3.11 (297–320), §6 (647–678).
Deck: `COPY.md` §3 (lines 91–123).

Deck rows used: 29 screen-specific + the 4 shared `nav.*` rows.

## Regions

| region | string | copy id | deck row | value | status |
|---|---|---|---|---|---|
| D1 | Home / Courses / Workshop / Parent Studio | `nav.home`, `nav.courses`, `nav.workshop`, `nav.parent` | 52–55 | deck (`DESTINATIONS`) | ok — labels equal `desktop/src/00-header.js:129-136` |
| D2 | Discover | `discover.title` | 95 | deck | **conflict — GAP-08** |
| D2 | Packs you can learn from, already on this device. | `discover.sub` | 96 | deck | ok |
| D3 | Discover | `discover.tab.discover` | 97 | deck | ok |
| D3 | Library | `discover.tab.library` | 98 | deck | ok |
| D3 | Provenance | `discover.tab.provenance` | 99 | deck | ok |
| D4 | {pack title} | `discover.feature.title` | 100 | `field:pack.inspect.manifest.title` | ok |
| D4 | {pack subtitle} | `discover.feature.body` | 101 | `field:pack.inspect.manifest.subtitle` | ok |
| D4 | Preview this pack | `discover.feature.primary` | 102 | deck | **conflict — GAP-10** |
| D4 (empty) | No packs on this device / A pack file you add shows up here. / Import a pack | `discover.empty.title`, `.body`, `.action` | 110–112 | deck | ok |
| D4 (rejected) | This pack did not pass its checks / Open Provenance to see what was recorded for each file. / Open Provenance | `discover.rejected.title`, `.body`, `.action` | 121–123 | deck | ok |
| D6 | All packs | `discover.shelf.title` | 103 | deck | ok |
| D6 | {n} packs | `discover.shelf.count` | 104 | `field:pack.list.total` (filter `installed`) | ok |
| D7 | {pack title} (card title) | **GAP-07** | — | **no row, and no list field** | **gap** |
| D7 | {subject label} (card line 2) | `home.card.subject` | 69 | CP-005 `library_item.subject_label` + `world_brief.subject_domain` + `library_item.recipe` | ok — the shared card-subject row; §6 line 656 assigns it to DISC |
| D7 | {n} sections (card line 3) | `discover.card.meta` | 105 | `computed:sum(objectives[].sections[])` over `pack.inspect.manifest.objectives[].sections[]` | ok |
| D7 | Files checked | `discover.card.trust.integrity` | 106 | `field:pack.inspect.trust.labels` contains `integrity_verified` | ok |
| D7 | Automated checks passed | `discover.card.trust.checks` | 107 | …`automated_checks_passed` | ok |
| D7 | Human review recorded | `discover.card.trust.human` | 108 | …`human_review_recorded` | ok |
| D7 | Support assessed by a model | `discover.card.trust.model` | 109 | …`model_assessed_support` | ok |
| D8 | — (fox `point`, `aria-hidden`) | — | — | — | ok, no copy |
| D9 | {pack title} did not pass its checks. | `discover.rejected.banner` | 120 | `field:pack.inspect.manifest.title` + `pack.inspect.trust.labels` | ok |

## States (SPEC §5.2 lines 438–445)

| state | copy ids | status |
|---|---|---|
| default | feature.title/body/primary, card.meta, card.trust.* | ok (+GAP-07, GAP-08, GAP-10) |
| empty | discover.empty.title/body/action | ok |
| loading | discover.loading (113) | ok — "Reading your workshop." |
| error | discover.error.title/body/action (114–116) | ok |
| offline | discover.offline.title/body/action (117–119) | ok |
| rejected | discover.rejected.title/body/action/banner (121–123, 120) | ok |

Overflow: the grid scrolls inside its frame and has no extra string; the count row (`discover.shelf.count`)
is the only "more" signal. The deck has no overflow row for this screen and the spec does not ask for one.

## GAPS

- **GAP-07 — the pack card title has no row and no list field.** D7's card must show the pack title
  (SPEC line 429 lists D7 ids and none is a title). `pack.list.items[]` (`$defs.pack_list_item`,
  `contracts/rpc.v24.json`) carries `pack_id`, `pack_version`, `source`, `state`, `recipe`,
  `license`, `file_count`, `content_hash`, `installed_at` — **no `title`**. The only title field is
  `pack.inspect.manifest.title`, which is a per-pack `pack.inspect` call. A maker will either
  invent the title or issue N+1 calls. Proposal in `GAPS.md`.
- **GAP-08 — heading conflict.** CP-021 line 35 says the heading is "Discover your next world";
  `discover.title` (line 95) is "Discover" and its cap is 16 (the body string is 24 characters).
  The deck wins; the body should be corrected before dispatch.
- **GAP-09 — "outcome" is not a field.** CP-021 lines 35–36 say the banner carries "the real
  featured pack title **and outcome** as DOM text". The deck's banner body is
  `discover.feature.body` = `pack.inspect.manifest.subtitle` (101). No contract field is named
  "outcome" in `pack-manifest.v2.json` (`subtitle`, `content_notes`, `safety_notes`,
  `accessibility_notes`, `level_label`, `recipe`, `trust`). A maker reading "outcome" will invent a
  learning-outcome line.
- **GAP-10 — primary label conflict.** CP-021 line 37 says the one primary is `Preview`;
  `discover.feature.primary` (102) is "Preview this pack". Deck wins.

## Body/copy conflicts to correct before this card starts

1. Line 35: "Discover your next world" → `discover.title` "Discover" (95).
2. Lines 35–36: drop "outcome", or name it as the pack subtitle (101).
3. Line 37: `Preview` → "Preview this pack" (102).
4. Line 42–43: "subject chip plus real structure ("6 sections") plus trust label" already matches
   `home.card.subject` (69) + `discover.card.meta` (105) + the four trust rows (106–109) — no change.

No other string in the card body lacks a source. The "no stars, no review counts, no Life" rule is
`COPY.md` §7 (275–283) and needs no row of its own.
