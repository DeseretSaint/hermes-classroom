"""CB-024 proof: cb.rpc v4 pack reads and cb.projection against the real pack lifecycle.

`tests/test_contracts.py` proves the contract set is coherent; it cannot prove that

* an installed pack really produces a contract-shaped ``pack.list`` row,
* ``pack.inspect`` really re-hashes adopted content and reports drift honestly,
* the ``revision`` a list row reports is the one ``pack.delete`` fences on, or
* the frozen projection vectors match ``coursebook.pack_flow``,

because all of that lives on the CB-010 pack-lifecycle branch. This module closes the gap: it
installs the bundled demo packs through the real staging grant, adoption and import path, reads the
library index and ``packs`` rows, and validates every composed payload against ``rpc.v4.json``.

Run it in a worktree that contains the CB-010 pack lifecycle:

    python3 -m unittest scripts.proof_contract_v4 -v

Without that backend the module skips with an explicit reason instead of pretending to pass. It is a
proof, not a gate: `tests/test_contracts.py` is the gate that must pass everywhere.
"""

from __future__ import annotations

# This module is branch-dependent by design: it imports the CB-010 pack lifecycle, so static
# analysis on a branch without it reports unresolved imports.
# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportPossiblyUnboundVariable=false, reportGeneralTypeIssues=false

import shutil
import tempfile
import unittest
from pathlib import Path

from coursebook import contracts

try:  # The pack lifecycle and its fixtures live on Lattice's branch.
    from coursebook import archive, db, pack_flow, packs
    from tests.kernel_support import KernelCase

    _PACK_FLOW_AVAILABLE = True
    _PACK_FLOW_WHY = ""
except ImportError as exc:  # pragma: no cover - depends on the branch being checked out
    _PACK_FLOW_AVAILABLE = False
    _PACK_FLOW_WHY = (
        "needs the CB-010 pack lifecycle (coursebook/pack_flow.py, coursebook/archive.py, "
        f"tests/kernel_support.py): {exc}"
    )

    class KernelCase(unittest.TestCase):  # type: ignore[no-redef]
        """Placeholder so the module imports (and skips honestly) where the lifecycle is absent."""


ROOT = Path(__file__).resolve().parent.parent
JAPANESE = ROOT / "bundled" / "packs" / "japanese-affection-context-l0"
PARENT = ROOT / "bundled" / "packs" / "parent-measurement-practice"


@unittest.skipUnless(_PACK_FLOW_AVAILABLE, _PACK_FLOW_WHY)
class V4PackReadProof(KernelCase):
    def setUp(self) -> None:
        super().setUp()
        self.work = Path(tempfile.mkdtemp(prefix="coursebook-proof-v4-"))
        self.addCleanup(shutil.rmtree, self.work, True)

    # ── real install, through the real import path ──────────────────────
    def install(self, source: Path = JAPANESE, *, name: str = "pack.zip", mode: str = "fresh") -> dict:
        manifest, files = archive.read_directory(source)
        destination = self.work / name
        archive.write_archive(destination, manifest, files)
        staged_id = pack_flow.grant_local_file(destination)
        return self.ok("pack.import", {"staged_id": staged_id, "mode": mode})["result"]

    # ── the documented mapping, composed here because the handler is Lattice's ──
    def pack_list(self, *, state_filter: str = "all", limit: int = 100) -> dict:
        with db.read() as read:
            rows = {
                (row["pack_id"], row["version"]): row
                for row in read.execute("SELECT * FROM packs")
            }
        items = []
        for record in pack_flow.library().list():
            manifest = packs.load_manifest(Path(str(record["directory"])) / packs.root_file())
            row = rows.get((str(record["pack_id"]), str(record["version"])))
            items.append(
                {
                    "pack_id": str(record["pack_id"]),
                    "pack_version": str(record["version"]),
                    "content_hash": str(record["manifest_hash"]),
                    "recipe": str(manifest["recipe"]),
                    "source": str(record["source"]),
                    "state": str(row["state"]) if row is not None else str(record.get("state") or "installed"),
                    "revision": int(row["revision"]) if row is not None else int(record.get("revision") or 0),
                    "installed_at": str(record["installed_at"]),
                    "file_count": len(manifest["files"]),
                    "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
                    "license": manifest["license"],
                }
            )
        matched = [item for item in items if state_filter == "all" or item["state"] == state_filter]
        matched.sort(key=lambda item: (item["installed_at"], item["pack_id"], item["pack_version"]), reverse=True)
        return {
            "items": matched[:limit],
            "total": len(matched),
            "truncated": len(matched) > limit,
            "applied_filter": state_filter,
        }

    def pack_inspect(self, pack_id: str, version: str) -> dict:
        record = next(
            (
                item
                for item in pack_flow.library().list()
                if str(item["pack_id"]) == pack_id and str(item["version"]) == version
            ),
            None,
        )
        if record is None:
            raise LookupError(f"pack {pack_id} {version} is not in the library")
        directory = Path(str(record["directory"]))
        hashes_match = True
        try:
            # The library read verifies every declared file and raises on drift. A pane must not
            # die because one file drifted, so the handler reports drift instead of raising.
            manifest, files = pack_flow.library().read(pack_id, version)
        except archive.PackRejected:
            manifest = packs.load_manifest(directory / packs.root_file())
            files = {}
            hashes_match = False
            for entry in manifest["files"]:
                target = directory / str(entry["path"])
                files[str(entry["path"])] = target.read_bytes() if target.is_file() else b""
        declared = {str(entry["path"]): entry for entry in manifest["files"]}
        hashes_match = hashes_match and packs.content_hash(manifest) == str(record["manifest_hash"]) and all(
            packs.file_sha256(files[path]) == str(entry["sha256"])
            and len(files[path]) == int(entry["bytes"])
            for path, entry in declared.items()
        )
        preview = packs.preview(
            manifest,
            integrity={
                "hashes_match": hashes_match,
                "file_count": len(manifest["files"]),
                "expanded_bytes": sum(int(entry["bytes"]) for entry in manifest["files"]),
            },
            automated_checks_passed=True,
        )
        row = next(item for item in self.pack_list()["items"] if item["pack_id"] == pack_id)
        return {
            "pack": row,
            "manifest": preview["manifest"],
            "integrity": preview["integrity"],
            "trust": preview["trust"],
        }

    def assert_contract_clean(self) -> None:
        self.assertEqual(contracts.audit_contracts(), [])
        self.assertEqual(contracts.WIRE_CONTRACT_VERSION, 4)
        self.assertEqual(contracts.contract_version("cb.rpc"), 4)
        self.assertEqual(contracts.contract_version("cb.db"), 2)
        self.assertEqual(contracts.contract_version("cb.errors"), 2)
        self.assertEqual(contracts.contract_version("cb.projection"), 1)

    # ── pack.list ──────────────────────────────────────────────────────
    def test_pack_list_reports_installed_packs_as_contract_rows(self) -> None:
        self.assert_contract_clean()
        japanese = self.install()
        parent = self.install(PARENT, name="parent.zip")
        response = self.pack_list()
        contracts.validate_response_payload("pack.list", response)
        self.assertEqual(response["total"], 2)
        by_id = {item["pack_id"]: item for item in response["items"]}
        self.assertEqual(by_id[japanese["pack_id"]]["recipe"], "casual")
        self.assertEqual(by_id[parent["pack_id"]]["recipe"], "parent")
        for item in response["items"]:
            self.assertEqual(item["state"], "installed")
            self.assertEqual(item["revision"], 0)
            self.assertGreater(item["file_count"], 0)
            self.assertGreater(item["expanded_bytes"], 0)
            self.assertNotIn("directory", item)
        # A row carries the same hash the import recorded, so export can be checked against it.
        manifest = packs.load_manifest(JAPANESE / packs.root_file())
        self.assertEqual(
            by_id[manifest["pack_id"]]["content_hash"], manifest["content_hash"]
        )
        self.assertRegex(by_id[manifest["pack_id"]]["content_hash"], r"^sha256:[a-f0-9]{64}$")

    def test_pack_list_sees_a_pack_that_library_list_cannot(self) -> None:
        # The gap CB-010 reported: library.list enumerates enrollments, so a pack that was adopted
        # but never cut into a course is invisible. Adoption without an import is a real state — an
        # import that adopted, then failed its database transaction, leaves exactly this.
        manifest, files = archive.read_directory(JAPANESE)
        destination = self.work / "adopted-only.zip"
        archive.write_archive(destination, manifest, files)
        staged = pack_flow.staging().stage(pack_flow.grant_local_file(destination))
        pack_flow.validate_and_audit(staged)
        pack_flow.library().adopt(staged, source="local")

        enrolled = int(
            self.scalar("SELECT COUNT(*) FROM courses JOIN enrollments ON enrollments.course_id = courses.id")
        )
        self.assertEqual(enrolled, 0)
        self.assertEqual(int(self.scalar("SELECT COUNT(*) FROM packs")), 0)
        response = self.pack_list()
        contracts.validate_response_payload("pack.list", response)
        self.assertEqual(response["total"], 1, "an installed pack must stay visible with no enrollment")
        self.assertEqual(response["items"][0]["pack_id"], manifest["pack_id"])
        # No kernel row yet: the index's own state and revision are the honest fallback.
        self.assertEqual(response["items"][0]["state"], "installed")
        self.assertEqual(response["items"][0]["revision"], 0)

    def test_pack_list_filters_and_bounds_without_hiding_the_total(self) -> None:
        self.install()
        self.install(PARENT, name="parent.zip")
        limited = self.pack_list(limit=1)
        contracts.validate_response_payload("pack.list", limited)
        self.assertEqual(len(limited["items"]), 1)
        self.assertEqual(limited["total"], 2)
        self.assertTrue(limited["truncated"])
        empty = self.pack_list(state_filter="frozen")
        contracts.validate_response_payload("pack.list", empty)
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["total"], 0)
        self.assertFalse(empty["truncated"])

    def test_pack_list_revision_is_the_fence_pack_delete_uses(self) -> None:
        installed = self.install()
        row = next(item for item in self.pack_list()["items"] if item["pack_id"] == installed["pack_id"])
        preview = self.ok(
            "pack.delete",
            {"pack_id": installed["pack_id"], "dry_run": True},
            expected_revision=row["revision"],
            idempotency_key="proof-v4-delete-preview",
        )["result"]
        self.ok(
            "pack.delete",
            {
                "pack_id": installed["pack_id"],
                "dry_run": False,
                "data_scope_hash": preview["data_scope"]["scope_hash"],
            },
            expected_revision=row["revision"],
            idempotency_key="proof-v4-delete-confirm",
        )
        frozen = next(item for item in self.pack_list(state_filter="frozen")["items"])
        contracts.validate_response_payload("pack.list", self.pack_list(state_filter="frozen"))
        self.assertEqual(frozen["state"], "frozen")
        self.assertEqual(frozen["revision"], row["revision"] + 1, "the list must show the fence's new value")

    # ── pack.inspect ───────────────────────────────────────────────────
    def test_pack_inspect_returns_manifest_integrity_and_trust(self) -> None:
        installed = self.install()
        inspection = self.pack_inspect(installed["pack_id"], self.pack_list()["items"][0]["pack_version"])
        contracts.validate_response_payload("pack.inspect", inspection)
        self.assertTrue(inspection["integrity"]["hashes_match"])
        self.assertEqual(inspection["integrity"]["file_count"], inspection["pack"]["file_count"])
        self.assertEqual(inspection["integrity"]["expanded_bytes"], inspection["pack"]["expanded_bytes"])
        self.assertIn("integrity_verified", inspection["trust"]["labels"])
        self.assertIn("automated_checks_passed", inspection["trust"]["labels"])
        self.assertNotIn("human_review_recorded", inspection["trust"]["labels"])
        self.assertEqual(inspection["manifest"]["content_hash"], inspection["pack"]["content_hash"])
        self.assertNotIn("directory", inspection["pack"])

    def test_pack_inspect_reports_content_drift_instead_of_raising(self) -> None:
        installed = self.install()
        version = self.pack_list()["items"][0]["pack_version"]
        record = next(item for item in pack_flow.library().list() if item["pack_id"] == installed["pack_id"])
        manifest = packs.load_manifest(Path(str(record["directory"])) / packs.root_file())
        target = Path(str(record["directory"])) / str(manifest["files"][0]["path"])
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"drift")
            drifted = self.pack_inspect(installed["pack_id"], version)
            contracts.validate_response_payload("pack.inspect", drifted)
            self.assertFalse(drifted["integrity"]["hashes_match"])
            self.assertNotIn("integrity_verified", drifted["trust"]["labels"])
        finally:
            target.write_bytes(original)
        restored = self.pack_inspect(installed["pack_id"], version)
        self.assertTrue(restored["integrity"]["hashes_match"])

    # ── cb.projection conformance ──────────────────────────────────────
    def test_projection_matches_every_frozen_vector(self) -> None:
        document = contracts.contract("cb.projection")
        checked = 0
        for example in document["examples"]:
            if example.get("divergence"):
                continue  # pinned separately, below
            with self.subTest(example=example["name"]):
                actual = pack_flow.check_spec_from_pack_check(example["check"], recipe=example["recipe"])
                expectation = example["expect"]
                if expectation["kind"] == "spec":
                    contracts.validate_definition("cb.projection", "check_spec", actual)
                    self.assertEqual(actual, expectation["spec"])
                else:
                    self.assertIsNone(actual)
                checked += 1
        self.assertGreaterEqual(checked, 10, "the passing vector set must not shrink")

    def test_projection_divergences_are_pinned_to_their_documented_shape(self) -> None:
        """The two open importer divergences, asserted exactly.

        The contract is the authority. Until Lattice applies it, this test proves the gap is the
        documented one and nothing worse. When the importer is fixed these assertions flip, which
        is the signal to empty ``x-known-divergences`` and delete this test.
        """
        document = contracts.contract("cb.projection")
        empty_alternatives = next(
            item for item in document["examples"] if item.get("divergence") == "empty-alternatives"
        )
        declared_failed = next(
            item for item in document["examples"] if item.get("divergence") == "declared-audit-failed"
        )

        withheld = pack_flow.check_spec_from_pack_check(empty_alternatives["check"], recipe="one_off")
        self.assertIsNone(withheld, "empty-alternatives appears fixed: update cb.projection")
        passed, problems = pack_flow.audit_check_for_import(empty_alternatives["check"])
        self.assertFalse(passed)
        self.assertEqual(problems, ["accepted alternatives do not add an accepted form"])

        graded = pack_flow.check_spec_from_pack_check(declared_failed["check"], recipe="casual")
        self.assertIsNotNone(graded, "declared-audit-failed appears fixed: update cb.projection")
        contracts.validate_definition("cb.projection", "check_spec", graded)
        self.assertEqual(graded["audit_state"], "passed")
        self.assertEqual(graded["declared_audit_state"], "failed")

    def test_objective_criteria_matches_the_frozen_vectors(self) -> None:
        for example in contracts.contract("cb.projection")["objective_examples"]:
            with self.subTest(example=example["name"]):
                actual = pack_flow.objective_criteria(example["objective"], recipe=example["recipe"])
                self.assertEqual(actual, example["expect"])
                for criterion in actual:
                    contracts.validate_definition("cb.projection", "objective_criterion", criterion)

    def test_bundled_demo_packs_project_every_check(self) -> None:
        for source in (JAPANESE, PARENT):
            manifest = packs.load_manifest(source / packs.root_file())
            with self.subTest(pack_id=manifest["pack_id"]):
                for objective in manifest["objectives"]:
                    criteria = pack_flow.objective_criteria(objective, recipe=manifest["recipe"])
                    contracts.validate_definition("cb.projection", "objective_criterion", criteria[0])
                    self.assertEqual(criteria[0]["id"], "pack_objective")
                    by_check = {str(check["check_id"]): check for check in objective["checks"]}
                    graded = {entry["id"]: entry for entry in criteria if "check_spec" in entry}
                    withheld = {entry["id"]: entry for entry in criteria if entry.get("check_spec_withheld")}
                    self.assertEqual(set(graded) | set(withheld), set(by_check))
                    for entry in graded.values():
                        contracts.validate_definition("cb.projection", "check_spec", entry["check_spec"])
                    for entry in withheld.values():
                        contracts.validate_definition("cb.projection", "objective_criterion", entry)
                    if manifest["recipe"] == "parent":
                        self.assertEqual(graded, {}, "a parent pack must never yield a graded check")
                    else:
                        for check_id in withheld:
                            # No demo check may be withheld for any reason other than the
                            # documented empty-alternatives divergence.
                            alternatives = [
                                str(item)
                                for item in by_check[check_id].get("accepted_alternatives") or []
                                if str(item).strip()
                            ]
                            self.assertEqual(
                                alternatives,
                                [],
                                f"{check_id} withheld by a rule other than the documented divergence",
                            )

    def test_bundled_japanese_pack_objective_is_ungradable_until_the_divergence_is_fixed(self) -> None:
        """Demo falsification: the shipped demo pack has a check the shipped importer withholds.

        `chk-register-transfer-1` declares `accepted_alternatives: []`; the importer's vacuous
        `all(...)` withholds it, so `objective_criteria` writes no spec and `check.open` refuses
        with `objective_not_checkable`. When `empty-alternatives` is fixed this test flips, which is
        the signal to delete it and clear the divergence from `cb.projection`.
        """
        objective_ordinal = 4
        manifest = packs.load_manifest(JAPANESE / packs.root_file())
        withheld = [
            str(objective["objective_id"])
            for objective in manifest["objectives"]
            if any(
                entry.get("check_spec_withheld")
                for entry in pack_flow.objective_criteria(objective, recipe="casual")
            )
        ]
        self.assertEqual(withheld, ["obj-register-transfer"], "the demo pack's ungradable set changed")

        installed = self.install()
        objective_id = self.scalar(
            "SELECT id FROM objectives WHERE plan_id ="
            " (SELECT id FROM plans WHERE course_id = ?) ORDER BY ordinal LIMIT 1 OFFSET ?",
            (installed["course_id"], objective_ordinal - 1),
        )
        self.assertIsNotNone(objective_id)
        response = self.dispatch(
            "check.open",
            {"enrollment_id": installed["enrollment_id"], "objective_id": objective_id},
            expected_revision=0,
        )
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "VALIDATION_FAILED")
        self.assertEqual(response["error"]["details"]["reason"], "objective_not_checkable")


if __name__ == "__main__":
    unittest.main()
