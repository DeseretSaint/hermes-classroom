"""Declared, source-audited frequency inventories for language courses (H-89).

The rule this module enforces is narrow and deterministic: a plan may only name vocabulary
items that are present in a declared, hash-pinned frequency inventory, and it must take them
in ascending rank order. The module never generates a list, never estimates coverage, and
never upgrades a rank into a comprehension claim.

Why there is no bundled third-party list
----------------------------------------
The source audit (``docs/FREQUENCY-INVENTORY.md``) found no list that can be shipped under
acceptable terms in this repository today:

* the BCCWJ word list is CC BY-NC-SA 3.0 and free only for research/education use;
* Matsushita's General Learners' Vocabulary List is BCCWJ-derived with no open licence;
* wordfreq's data is CC BY-SA 4.0 with named corpora but no readings or part-of-speech per
  row, and a mixed modality that cannot be declared as one corpus;
* hermitdave/FrequencyWords content is CC BY-SA 4.0 from OpenSubtitles 2018, with
  whitespace-derived rows that are not morphological segmentation for Japanese;
* JMdict carries readings and part-of-speech under CC BY-SA 4.0, but its ``nf`` buckets are
  newspaper-only and the share-alike obligation cannot be met by an unlicensed repository.

The plugin repository carries no outbound licence (``README.md`` says so explicitly), so the
implementation ships an import seam only. The one bundled document is a synthetic fixture in
``tests/fixtures/frequency/`` that states that no corpus was consulted.

Contract and checks
-------------------
The document shape is frozen in ``contracts/frequency-inventory.v1.json``. Beyond the JSON
Schema, this module refuses (as typed :class:`FrequencyInventoryError` reasons) duplicate or
non-contiguous ranks, bands that do not partition ranks 1..N, a row whose band does not
contain its rank, and a ``content_hash`` that does not match the shipped rows. Those are
properties a schema cannot express and are exactly the ones a hand-edited import gets wrong.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from . import contracts

__all__ = [
    "BUNDLEABLE_LICENCES",
    "CONTRACT_ID",
    "FREQUENCY_NOTE",
    "FrequencyInventoryError",
    "GRAMMAR_PARTS_OF_SPEECH",
    "Inventory",
    "InventorySelection",
    "SELECTION_STATUSES",
    "WARNING_UNAVAILABLE",
    "bundle_eligible",
    "load_inventory",
    "load_inventory_file",
    "plan_vocabulary_reasons",
    "resolve_inventory",
    "rows_content_hash",
    "selection_from_brief",
]

CONTRACT_ID = "cb.frequency_inventory"

#: Ranks are corpus- and modality-specific. This sentence travels with every plan block so a
#: model or a client cannot present a band as a comprehension percentage.
FREQUENCY_NOTE = (
    "Frequency ranks are corpus- and modality-specific. They are not a comprehension "
    "percentage and do not establish that a learner knows a share of the language."
)

#: Grammatical high-frequency items. They are taught as grammar in context, never as
#: vocabulary cards (H-88's brief says the same; this set is the deterministic enforcement).
GRAMMAR_PARTS_OF_SPEECH = frozenset({"particle", "copula", "auxiliary", "conjunction"})

#: Licences under which a bundled inventory is permitted. The repository itself has no
#: outbound licence yet, so this gate is a necessary condition, not a sufficiency claim.
BUNDLEABLE_LICENCES = frozenset({"CC0-1.0", "public-domain", "CC-BY-4.0", "CC-BY-SA-4.0"})

SELECTION_STATUSES = ("inventory", "unverified", "not_applicable")

#: The typed reason code a caller reads when no inventory could be resolved. It is a reason,
#: not a silent fallback: the plan still authors from research, but every vocabulary target
#: is absent and the set is labelled unverified.
WARNING_UNAVAILABLE = "frequency_inventory_unavailable"


class FrequencyInventoryError(ValueError):
    """A declared inventory is malformed, mismatched or fails its own integrity hash.

    Callers translate this into a typed job rejection. It is deliberately distinct from the
    unavailable path: absence is a warning, a corrupt declared artifact is refused.
    """

    def __init__(self, reasons: str | Iterable[str]) -> None:
        if isinstance(reasons, str):
            reasons = [reasons]
        self.reasons = [str(reason) for reason in reasons]
        super().__init__("; ".join(self.reasons))


def _canonical_rows(rows: Sequence[dict[str, Any]]) -> str:
    return json.dumps(
        [dict(row) for row in rows],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def rows_content_hash(rows: Sequence[dict[str, Any]]) -> str:
    """``sha256:<hex>`` over the canonical JSON of the rows exactly as shipped."""
    digest = hashlib.sha256(_canonical_rows(rows).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class Inventory:
    """A validated, immutable frequency inventory."""

    document: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    by_rank: dict[int, dict[str, Any]]
    bands: dict[str, dict[str, Any]]

    @property
    def language(self) -> str:
        return str(self.document["language"])

    @property
    def inventory_id(self) -> str:
        return str(self.document["inventory_id"])

    @property
    def source_id(self) -> str:
        return str(self.document["source_id"])

    @property
    def source_url(self) -> str:
        return str(self.document["source_url"])

    @property
    def licence(self) -> str:
        return str(self.document["licence"])

    @property
    def licence_url(self) -> str:
        return str(self.document["licence_url"])

    @property
    def attribution(self) -> str:
        return str(self.document["attribution"])

    @property
    def redistribution(self) -> str:
        return str(self.document["redistribution"])

    @property
    def modality(self) -> str:
        return str(self.document["modality"])

    @property
    def tokenization(self) -> str:
        return str(self.document["tokenization"])

    @property
    def scope_note(self) -> str:
        return str(self.document["scope_note"])

    @property
    def content_hash(self) -> str:
        return str(self.document["content_hash"])

    def band_rows(self, band_id: str) -> tuple[dict[str, Any], ...]:
        return tuple(row for row in self.rows if row["band"] == band_id)


@dataclass(frozen=True)
class InventorySelection:
    """One declared band of an inventory, split into vocabulary and grammar rows."""

    inventory: Inventory
    band: dict[str, Any]

    @property
    def rows(self) -> tuple[dict[str, Any], ...]:
        return self.inventory.band_rows(str(self.band["id"]))

    @property
    def content_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            row for row in self.rows if row["part_of_speech"] not in GRAMMAR_PARTS_OF_SPEECH
        )

    @property
    def grammar_rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            row for row in self.rows if row["part_of_speech"] in GRAMMAR_PARTS_OF_SPEECH
        )

    @property
    def band_id(self) -> str:
        return str(self.band["id"])

    def prompt_block(self) -> dict[str, Any]:
        """The block the plan author and the independent validator both receive."""
        inventory = self.inventory
        return {
            "status": "inventory",
            "inventory_id": inventory.inventory_id,
            "language": inventory.language,
            "source_id": inventory.source_id,
            "source_url": inventory.source_url,
            "licence": inventory.licence,
            "licence_url": inventory.licence_url,
            "attribution": inventory.attribution,
            "modality": inventory.modality,
            "tokenization": inventory.tokenization,
            "content_hash": inventory.content_hash,
            "scope_note": inventory.scope_note,
            "band": {
                "id": self.band_id,
                "from_rank": int(self.band["from_rank"]),
                "to_rank": int(self.band["to_rank"]),
            },
            "note": FREQUENCY_NOTE,
            "content_items": [_row_brief(row) for row in self.content_rows],
            "grammar_items": [_row_brief(row) for row in self.grammar_rows],
        }

    def result_block(self, objectives: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        """The job-result block. ``items`` is the items the plan actually named, in order."""
        inventory = self.inventory
        return {
            "status": "inventory",
            "reason": None,
            "inventory_id": inventory.inventory_id,
            "source_id": inventory.source_id,
            "source_url": inventory.source_url,
            "licence": inventory.licence,
            "licence_url": inventory.licence_url,
            "attribution": inventory.attribution,
            "modality": inventory.modality,
            "tokenization": inventory.tokenization,
            "content_hash": inventory.content_hash,
            "scope_note": inventory.scope_note,
            "band": {
                "id": self.band_id,
                "from_rank": int(self.band["from_rank"]),
                "to_rank": int(self.band["to_rank"]),
            },
            "note": FREQUENCY_NOTE,
            "items": _declared_items(objectives, self),
        }


def _row_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": int(row["rank"]),
        "lemma": str(row["lemma"]),
        "reading": str(row["reading"]),
        "part_of_speech": str(row["part_of_speech"]),
    }


def _declared_items(
    objectives: Sequence[dict[str, Any]], selection: InventorySelection
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for objective in objectives:
        ordinal = int(objective.get("ordinal", 0) or 0)
        for lemma in objective.get("target_items") or []:
            row = _lookup(selection, str(lemma))
            if row is None:
                continue
            items.append(
                {
                    "objective_ordinal": ordinal,
                    "rank": int(row["rank"]),
                    "lemma": str(row["lemma"]),
                    "reading": str(row["reading"]),
                    "part_of_speech": str(row["part_of_speech"]),
                }
            )
    return items


def _lookup(selection: InventorySelection, lemma: str) -> dict[str, Any] | None:
    for row in selection.rows:
        if str(row["lemma"]) == lemma:
            return row
    return None


def _primary_language(tag: str) -> str:
    return str(tag or "").split("-")[0].lower()


def load_inventory(document: dict[str, Any]) -> Inventory:
    """Validate a declared inventory document and return it, or refuse with typed reasons."""
    if not isinstance(document, dict):
        raise FrequencyInventoryError("inventory document must be a JSON object")
    try:
        contracts.validate(CONTRACT_ID, document, what="frequency inventory")
    except contracts.ContractError as exc:
        raise FrequencyInventoryError(str(exc)) from exc

    reasons: list[str] = []
    rows = [dict(row) for row in document["rows"]]
    reasons.extend(_row_and_band_reasons(document, rows))
    if reasons:
        raise FrequencyInventoryError(reasons)

    declared_hash = str(document["content_hash"])
    computed = rows_content_hash(rows)
    if computed != declared_hash:
        raise FrequencyInventoryError(
            f"content_hash {declared_hash} does not match the shipped rows ({computed}); "
            "the inventory was edited after it was hashed"
        )

    ordered = tuple(sorted(rows, key=lambda row: int(row["rank"])))
    bands = {str(band["id"]): dict(band) for band in document["bands"]}
    return Inventory(
        document=dict(document),
        rows=ordered,
        by_rank={int(row["rank"]): row for row in ordered},
        bands=bands,
    )


def _row_and_band_reasons(document: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    bands = [dict(band) for band in document.get("bands") or []]
    band_ids = [str(band["id"]) for band in bands]
    if len(set(band_ids)) != len(band_ids):
        reasons.append("band ids must be unique")
    ordered_bands = sorted(bands, key=lambda band: int(band["from_rank"]))
    expected_from = 1
    for band in ordered_bands:
        from_rank = int(band["from_rank"])
        to_rank = int(band["to_rank"])
        if from_rank > to_rank:
            reasons.append(f"band {band['id']!r} starts at {from_rank} but ends at {to_rank}")
        if from_rank != expected_from:
            reasons.append(
                f"band {band['id']!r} starts at rank {from_rank}; bands must partition ranks "
                f"contiguously and the next band must start at {expected_from}"
            )
        expected_from = to_rank + 1
    if rows and expected_from != len(rows) + 1:
        reasons.append(
            f"bands cover ranks 1..{expected_from - 1} but the inventory has {len(rows)} row(s)"
        )

    ranks = [int(row["rank"]) for row in rows]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        duplicates = sorted({rank for rank in ranks if ranks.count(rank) > 1})
        if duplicates:
            reasons.append(f"duplicate rank(s): {duplicates}")
        missing = sorted(set(range(1, len(ranks) + 1)) - set(ranks))
        if missing:
            reasons.append(f"ranks must be contiguous from 1; missing {missing[:10]}")
    band_by_id = {str(band["id"]): band for band in bands}
    for row in rows:
        band_id = str(row["band"])
        band = band_by_id.get(band_id)
        if band is None:
            reasons.append(f"row rank {row['rank']} names undeclared band {band_id!r}")
            continue
        rank = int(row["rank"])
        if not int(band["from_rank"]) <= rank <= int(band["to_rank"]):
            reasons.append(
                f"row rank {rank} is outside band {band_id!r} "
                f"({band['from_rank']}..{band['to_rank']})"
            )
    return reasons


def load_inventory_file(path: str | Path) -> Inventory:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise FrequencyInventoryError(f"cannot read frequency inventory {path}: {exc}") from exc
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FrequencyInventoryError(f"frequency inventory {path} is not valid JSON: {exc}") from exc
    return load_inventory(document)


def bundle_eligible(inventory: Inventory) -> bool:
    """Whether the declared terms permit shipping this list with the plugin."""
    return (
        inventory.redistribution == "allowed"
        and inventory.licence in BUNDLEABLE_LICENCES
    )


def _select_band(inventory: Inventory, band_id: str | None) -> dict[str, Any]:
    if band_id:
        band = inventory.bands.get(str(band_id))
        if band is None:
            raise FrequencyInventoryError(
                f"band {band_id!r} is not declared by inventory {inventory.inventory_id!r}; "
                f"declared bands: {sorted(inventory.bands)}"
            )
        return dict(band)
    if len(inventory.bands) == 1:
        return dict(next(iter(inventory.bands.values())))
    raise FrequencyInventoryError(
        f"inventory {inventory.inventory_id!r} declares {len(inventory.bands)} bands; "
        "the brief must name one"
    )


def select_inventory(
    inventory: Inventory, *, band_id: str | None = None, language: str | None = None
) -> InventorySelection:
    """Select one band for one language. A mismatch is refused, never coerced."""
    if language:
        declared = _primary_language(inventory.language)
        requested = _primary_language(language)
        if declared != requested:
            raise FrequencyInventoryError(
                f"inventory {inventory.inventory_id!r} is for language {declared!r}, "
                f"but the course declares {requested!r}"
            )
    return InventorySelection(inventory=inventory, band=_select_band(inventory, band_id))


def selection_from_brief(
    brief: dict[str, Any],
    *,
    locale: str | None,
    subject_domain: str | None,
    curriculum_domain: str | None = None,
) -> tuple[InventorySelection | None, dict[str, Any]]:
    """Resolve the brief's declared inventory, or return the typed unavailable status.

    ``brief["frequency_inventory"]`` is either

    * ``{"path": "/abs/or/relative.json", "root": "/optional/base", "band": "band-core"}`` or
    * ``{"document": {...}, "band": "band-core"}`` (used by packs and tests).

    The second element always says what happened. ``status`` is ``not_applicable`` for a
    non-language course, ``inventory`` when a list was resolved, and ``unverified`` with
    reason ``frequency_inventory_unavailable`` when none could be.
    """
    domain = curriculum_domain if curriculum_domain is not None else subject_domain
    if str(domain or "").strip().lower() != "language":
        return None, {
            "status": "not_applicable",
            "reason": None,
            "detail": "the course is not a language course; no vocabulary inventory applies",
        }

    spec = brief.get("frequency_inventory") if isinstance(brief, dict) else None
    if not spec:
        return None, {
            "status": "unverified",
            "reason": WARNING_UNAVAILABLE,
            "detail": "the brief declares no frequency inventory for this language course",
        }
    if not isinstance(spec, dict):
        raise FrequencyInventoryError(
            "brief.frequency_inventory must be an object with 'path' or 'document'"
        )
    band_id = spec.get("band")
    if "document" in spec:
        inventory = load_inventory(spec["document"])
    elif "path" in spec:
        path = Path(str(spec["path"])).expanduser()
        if not path.is_absolute():
            root = spec.get("root")
            if not root:
                raise FrequencyInventoryError(
                    "a relative frequency_inventory.path requires an explicit 'root'"
                )
            path = Path(str(root)).expanduser() / path
        if not path.exists():
            return None, {
                "status": "unverified",
                "reason": WARNING_UNAVAILABLE,
                "detail": f"declared frequency inventory is missing: {path}",
            }
        inventory = load_inventory_file(path)
    else:
        raise FrequencyInventoryError(
            "brief.frequency_inventory must carry a 'path' or an inline 'document'"
        )

    selection = select_inventory(inventory, band_id=band_id, language=locale)
    return selection, {
        "status": "inventory",
        "reason": None,
        "detail": f"using {inventory.inventory_id} band {selection.band_id}",
    }


def unavailable_prompt_block(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "unverified",
        "reason": status.get("reason"),
        "detail": status.get("detail"),
        "note": (
            "No frequency inventory is available for this language course. Do not declare "
            "target_items, do not state a frequency rank, and do not state any word-count or "
            "coverage percentage. Teach the vocabulary set as unverified. " + FREQUENCY_NOTE
        ),
    }


def plan_vocabulary_reasons(
    objectives: Sequence[dict[str, Any]], selection: InventorySelection | None
) -> list[str]:
    """Deterministic vocabulary-sequence rules, as reasons the plan is refused.

    They are cheap on purpose. The independent validator still judges usefulness and
    grouping; this function only proves the mechanical properties the card names: nothing
    duplicated, nothing outside the declared band, nothing grammatical presented as a word
    card, and the vocabulary that is present is the band's opening items in rank order.
    """
    reasons: list[str] = []
    declared: list[tuple[int, str, dict[str, Any]]] = []
    seen: dict[str, int] = {}

    for objective in objectives:
        ordinal = int(objective.get("ordinal", 0) or 0)
        raw_items = objective.get("target_items")
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            reasons.append(f"objective {ordinal} target_items must be an array of lemmas")
            continue
        for value in raw_items:
            lemma = str(value)
            if selection is None:
                reasons.append(
                    f"objective {ordinal} declares target item {lemma!r} but no frequency "
                    "inventory is available; the vocabulary set must stay unverified"
                )
                continue
            row = _lookup(selection, lemma)
            if row is None:
                out_of_band = _find_elsewhere(selection.inventory, lemma)
                if out_of_band is not None:
                    reasons.append(
                        f"objective {ordinal} target item {lemma!r} is in band "
                        f"{out_of_band['band']!r}, not the declared band {selection.band_id!r}"
                    )
                else:
                    reasons.append(
                        f"objective {ordinal} target item {lemma!r} is not in inventory "
                        f"{selection.inventory.inventory_id!r}"
                    )
                continue
            if row["part_of_speech"] in GRAMMAR_PARTS_OF_SPEECH:
                reasons.append(
                    f"objective {ordinal} target item {lemma!r} is a "
                    f"{row['part_of_speech']}; function words are grammar objectives, not "
                    "vocabulary cards"
                )
                continue
            if lemma in seen:
                reasons.append(
                    f"target item {lemma!r} appears in objectives {seen[lemma]} and {ordinal}"
                )
                continue
            seen[lemma] = ordinal
            declared.append((ordinal, lemma, row))

    if selection is None:
        return reasons

    if not declared and selection.content_rows:
        reasons.append(
            f"no objective declares a vocabulary target from band {selection.band_id!r}; "
            "a language course must name its opening vocabulary"
        )
        return reasons

    content = selection.content_rows
    expected_ranks = [int(row["rank"]) for row in content[: len(declared)]]
    declared_ranks = [int(row[2]["rank"]) for row in declared]
    if declared_ranks != expected_ranks:
        if declared_ranks != sorted(declared_ranks):
            reasons.append(
                "vocabulary targets are not in ascending frequency rank across objectives: "
                f"{declared_ranks}"
            )
        else:
            missing = [rank for rank in expected_ranks if rank not in set(declared_ranks)]
            reasons.append(
                "vocabulary targets must be the opening items of the declared band in rank "
                f"order; declared ranks {declared_ranks} are not the prefix {expected_ranks} "
                f"(missing {missing[:10]})"
            )
    return reasons


def _find_elsewhere(inventory: Inventory, lemma: str) -> dict[str, Any] | None:
    for row in inventory.rows:
        if str(row["lemma"]) == lemma:
            return row
    return None
