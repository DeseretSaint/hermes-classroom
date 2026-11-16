"""VQ-008 — the kit judge must pass the shipped kits and fail a broken claim.

The rule this file enforces: `--check` passing means nothing if the judge cannot fail. Each mutation
below breaks one load-bearing claim in a **throwaway copy** of `workshop_manual/kit.json` (or
`field_atlas/kit.json`), runs the real judge against that copy, and requires a non-zero exit.

Fixture hygiene (t_3dca7b5a): the copy, not the worktree, is what gets mutated. A run killed at any
instant — a supervisor timeout, a SIGKILL — can only leave a mutant in a temp directory, because the
shipped manifest is never opened for writing. That matters because a mutant left on disk is adopted
by the next run as its baseline: `kit["subject_cues"] = ["generic classroom", "stock photo"]` (see
`test_replaced_subject_cues_fails`) then survives every later run and `--check` reports
`workshop_manual: subject_cues drifted from the grammar table` about a committed blob that was
never broken. A worker who trusts that output "fixes" a manifest that was never wrong.

As a second line of defence, `setUpClass` refuses to start when a shipped kit file already differs
from `git show HEAD:<path>` — the signature of a kill from an older checkout, or of an uncommitted
edit. Judging it would be a claim failure about bytes nobody committed, so the class says the
worktree is dirty instead (matching `scripts/validate-plugin.sh`, which refuses to gate HEAD on a
dirty tree). `VQ008_ALLOW_DIRTY_KITS=1` opts in to judging local edits on purpose.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "vq008-kits.py"
KITS = ROOT / "assets" / "visual-kits"
KIT = KITS / "workshop_manual" / "kit.json"
GRAMMAR = "workshop_manual"

KIT_REL = "assets/visual-kits/workshop_manual/kit.json"
LOG_REL = "assets/visual-kits/workshop_manual/generation.json"
FALLBACK_KIT_REL = "assets/visual-kits/field_atlas/kit.json"

#: A mutation fixture may not touch a file it cannot restore; if an author wants to judge an
#: uncommitted manifest on purpose, this opts the guard out. Otherwise a dirty shipped file is a
#: loud error, never a claim verdict.
ALLOW_DIRTY_KITS = os.environ.get("VQ008_ALLOW_DIRTY_KITS", "") not in ("", "0")


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT
    )


def head_blob(rel: str, root: Path = ROOT) -> bytes | None:
    """The committed bytes for `rel`, or None when there is no git baseline to compare against."""
    try:
        out = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True)
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def _summary(blob: bytes) -> str:
    return f"{len(blob)}B sha256 {hashlib.sha256(blob).hexdigest()[:12]}"


def assert_pristine(rels: list[str], root: Path = ROOT, allow_dirty: bool | None = None) -> None:
    """Refuse to judge a worktree a killed run may have poisoned.

    Compares the shipped bytes with the commit. Equal (or no git baseline at all — an export has
    none) is fine; anything else is stated plainly, with the restore command, because the failure
    a dirty manifest produces downstream is a phantom claim failure.
    """
    if (ALLOW_DIRTY_KITS if allow_dirty is None else allow_dirty):
        return
    dirty = []
    for rel in rels:
        head = head_blob(rel, root=root)
        if head is None:
            continue
        disk_path = root / rel
        disk = disk_path.read_bytes() if disk_path.exists() else b""
        if disk != head:
            dirty.append(f"  {rel}: on disk {_summary(disk)}, HEAD {_summary(head)}")
    if dirty:
        raise AssertionError(
            "the worktree is dirty: a shipped kit file differs from HEAD. A killed mutation "
            "fixture leaves exactly this, and judging it reports a claim failure about bytes "
            "nobody committed.\n" + "\n".join(dirty) +
            "\nRestore with `git checkout -- <path>`, or set VQ008_ALLOW_DIRTY_KITS=1 to judge "
            "local edits on purpose."
        )


def judged_rels() -> list[str]:
    """Every manifest `--check` reads: the eight grammars' `kit.json` and the seven sidecars.

    `test_every_grammar_passes` claims all eight pass, so the guard has to cover all eight: a
    dirty manifest anywhere in that set turns the acceptance run into a verdict on uncommitted
    bytes. Derived from the judge's own grammar table, never hand-listed.
    """
    from coursebook.world import GRAMMARS

    rels = []
    for grammar in sorted(GRAMMARS):
        rels.append(f"assets/visual-kits/{grammar}/kit.json")
        sidecar = f"assets/visual-kits/{grammar}/generation.json"
        if (ROOT / sidecar).exists():
            rels.append(sidecar)
    return rels


class KitSandbox:
    """A throwaway `--kit-root`: the only tree the mutation tests are allowed to write.

    The shipped kit directory is copied once per judge class and the copy's `kit.json` /
    `generation.json` are reset between tests, so each mutation starts from the committed bytes
    and no test can see another's mutant. Nothing here ever opens the worktree for writing.

    `root` (or `VQ008_SANDBOX_ROOT`, used by the kill regression test) pins the temp directory so a
    parent process can watch the mutant land and SIGKILL the runner mid-mutation.
    """

    def __init__(self, grammar: str, root: str | Path | None = None) -> None:
        self.grammar = grammar
        self.source = KITS / grammar
        pinned = root if root is not None else os.environ.get("VQ008_SANDBOX_ROOT")
        self.root = (Path(pinned) if pinned
                     else Path(tempfile.mkdtemp(prefix=f"vq008-{grammar}-")))
        self.root.mkdir(parents=True, exist_ok=True)
        self.dir = self.root / grammar
        shutil.copytree(self.source, self.dir, dirs_exist_ok=True)
        self.kit = self.dir / "kit.json"
        self._baseline = {p: p.read_bytes() for p in self.dir.iterdir() if p.is_file()}
        self.pristine = self.kit.read_text()

    def reset(self) -> None:
        for path, blob in self._baseline.items():
            path.write_bytes(blob)

    def write_kit(self, kit: dict) -> None:
        self.kit.write_text(json.dumps(kit))

    def check(self, *args: str) -> subprocess.CompletedProcess:
        return run("--kit-root", str(self.root), *args)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


class KitJudge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Before anything is copied or judged: is every manifest HEAD commits still that commit?
        # (`--check` judges all eight grammars, so the guard covers all eight, sidecars included.)
        assert_pristine(judged_rels())
        cls.original = KIT.read_text()
        cls.sandbox = KitSandbox(GRAMMAR)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.close()

    def setUp(self):
        self.sandbox.reset()

    def tearDown(self):
        self.sandbox.reset()
        self.assertEqual(
            self.sandbox.kit.read_text(), self.original,
            "the sandbox no longer holds the shipped manifest — a mutant outlived its test",
        )

    def _check(self) -> subprocess.CompletedProcess:
        return self.sandbox.check("--check-one", GRAMMAR)

    def test_every_grammar_passes(self):
        # The shipped tree, not a copy: this is the acceptance claim, so it must read the bytes
        # the worktree actually ships (setUpClass has already proved they are HEAD's).
        out = run("--check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("8 grammars", out.stdout)
        self.assertIn("every claim re-derived", out.stdout)

    def test_tampered_hash_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["hero"][0]["sha256"] = "0" * 64
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("sha256 is stale", out.stdout)

    def test_pack_cover_fallback_fails(self):
        kit = json.loads(self.original)
        kit["fallbacks"]["cover"] = ["course-master", "pack-cover"]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("forbidden step", out.stdout)

    def test_grammar_drift_fails(self):
        kit = json.loads(self.original)
        kit["palette"]["ochre"] = "#000000"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("palette drifted from the grammar table", out.stdout)

    def test_inverted_cannot_do_fails(self):
        # `cannot_do` is the card's safety fence and lives in the grammar table. A manifest that
        # inverts it into permission is a false safety promise, not a copy edit.
        kit = json.loads(self.original)
        kit["cannot_do"] = "art may show a torque value as authority"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("cannot_do drifted from the grammar table", out.stdout)

    def test_widened_illustration_role_fails(self):
        kit = json.loads(self.original)
        kit["illustration_role"] = "orientation only; may show measurements and procedures"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("illustration_role drifted from the grammar table", out.stdout)

    def test_replaced_subject_cues_fails(self):
        kit = json.loads(self.original)
        kit["subject_cues"] = ["generic classroom", "stock photo"]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("subject_cues drifted from the grammar table", out.stdout)

    def test_provider_free_false_fails(self):
        # A kit that needs an image provider is not the provider-free artifact this card ships.
        kit = json.loads(self.original)
        kit["provider_free"] = False
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("provider_free is not true", out.stdout)

    def test_wrong_art_bible_fails(self):
        kit = json.loads(self.original)
        kit["art_bible"] = "docs/launch/ART-BIBLE.md"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("art_bible is", out.stdout)

    def test_faked_cover_ratio_fails(self):
        kit = json.loads(self.original)
        master = [p for p in kit["roles"]["cover"] if "derived_from" not in p][0]
        master["provenance"]["source_frame"]["ratios"]["natural_vs_shipped"] = 9.99
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("cover ratio natural_vs_shipped", out.stdout)

    def test_stale_kernel_pin_fails(self):
        # The kernel claims are content-addressed against plates this card does not own, so they go
        # stale whenever the kernel moves (VQ-006 re-authored the vignette to 2688x1428). A re-pin is
        # only worth anything if the judge still refuses a wrong one.
        kit = json.loads(self.original)
        row = [r for r in kit["kernel"]["assets"]
               if r["path"] == "assets/material/vignette-parchment.webp"][0]
        row["sha256"] = "0" * 64
        row["size"] = [96, 96]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("kernel assets/material/vignette-parchment.webp sha256 is stale", out.stdout)
        self.assertIn("kernel assets/material/vignette-parchment.webp size is stale", out.stdout)

    def test_placeholder_name_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "section/placeholder.png"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("missing", out.stdout)

    def test_faked_quiet_field_fails(self):
        # The quiet-field block is a measurement, so --check must re-measure the band from the
        # shipped pixels instead of reading the numbers the manifest reports.
        kit = json.loads(self.original)
        qf = kit["roles"]["hero"][0]["provenance"]["measured"]["quiet_field"]
        for key in list(qf):
            if isinstance(qf[key], (int, float)) and not isinstance(qf[key], bool):
                qf[key] = 0
        qf["best_contrast"] = 99
        qf["contrast_p5_on_cream"] = 99
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("quiet field", out.stdout)

    def test_faked_derived_cover_derivation_fails(self):
        # The 4:5 row nests `derived_from` and is derived from the master's own crop. A sentence
        # naming a frame that was never used must fail, not sail through as untested prose.
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["derivation"] = (
            "centre crop of the cover-3x2 natural 40000x30000 frame to 2x2, resized to 640x800"
        )
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 derivation does not state the crop actually taken", out.stdout)

    def test_derived_crop_must_match_master_crop(self):
        kit = json.loads(self.original)
        derived = [p for p in kit["roles"]["cover"] if "derived_from" in p][0]
        derived["provenance"]["source_frame"]["frame"] = [40000, 30000]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("4:5 row names frame", out.stdout)

    def test_missing_resolution_fails(self):
        # build_cb_assets.py reads resolution[role].source for a full-bleed plate and stops when
        # it is absent, so a kit without it is not loadable and must not pass acceptance.
        kit = json.loads(self.original)
        del kit["resolution"]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("no resolution block", out.stdout)

    def test_stale_generation_log_pin_fails(self):
        kit = json.loads(self.original)
        kit["generation_log"]["rows"] = kit["generation_log"]["rows"] + 1
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("generation_log row count is stale", out.stdout)

    def test_kernel_reference_as_role_fails(self):
        # A shared-kernel row is a reference into one kernel. Mounting it as a role would hand a
        # loader an out-of-kit path it cannot open; the judge must refuse that shape.
        kit = json.loads(self.original)
        kit["roles"]["frame"] = [dict(kit["kernel"]["assets"][0])]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("loader vocabulary", out.stdout)

    def test_role_path_outside_kit_fails(self):
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["path"] = "../../../assets/objects/clock.webp"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("resolves outside its own kit directory", out.stdout)

    def test_missing_kernel_refs_fails(self):
        kit = json.loads(self.original)
        del kit["kernel"]["assets"]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("kernel.assets is missing", out.stdout)

    def test_kit_id_mismatch_fails(self):
        kit = json.loads(self.original)
        kit["kit_id"] = "workshop_manual@9"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("is not workshop_manual@1", out.stdout)

    def test_duplicate_asset_id_fails(self):
        # VQ-004's loader refuses a repeated roles[].id (kit_duplicate_asset). A manifest the
        # product refuses must not pass the acceptance run.
        kit = json.loads(self.original)
        kit["roles"]["section"][0]["id"] = kit["roles"]["hero"][0]["id"]
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("declared twice", out.stdout)
        self.assertIn("kit_duplicate_asset", out.stdout)

    def test_stale_ocr_policy_fails(self):
        # The limitation sentence now states measured recall. A kit that keeps the old, weaker
        # wording (or any other drift) must not pass: the policy is carried verbatim, not prose.
        kit = json.loads(self.original)
        kit["ocr_policy"]["limitation"] = "painted pseudo-lettering is not readable enough for OCR"
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("ocr_policy drifted", out.stdout)

    def test_accepted_row_without_vision_fails(self):
        # The recorded vision pass is the primary textless control, so an accepted attempt with
        # no verdict behind it is a broken claim — the sidecar pin is kept consistent so this
        # fails on the verdict, not on a stale hash. The sidecar lives in the sandbox too: a kill
        # during this test used to leave the shipped generation.json mutated, which the next run
        # reported as `generation_log sha256 is stale`.
        log = self.sandbox.dir / "generation.json"
        rows = json.loads(log.read_text())
        accepted = [r for r in rows if r.get("verdict") == "accepted"]
        self.assertTrue(accepted, "the shipped kit has no accepted row to mutate")
        del accepted[0]["vision"]
        log.write_text(json.dumps(rows))
        kit = json.loads(self.original)
        kit["generation_log"]["sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
        kit["generation_log"]["rows"] = len(rows)
        self.sandbox.write_kit(kit)
        out = self._check()
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn("records no vision verdict", out.stdout)


class FieldAtlasJudge(unittest.TestCase):
    """`field_atlas` keeps its own approved shape, but a display-kit loader only reads `roles`, so
    its role vocabulary and duplicate-id rule are judged exactly like the seven."""

    KIT = KITS / "field_atlas" / "kit.json"

    @classmethod
    def setUpClass(cls):
        assert_pristine(judged_rels())
        cls.original = cls.KIT.read_text()
        cls.sandbox = KitSandbox("field_atlas")

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.close()

    def setUp(self):
        self.sandbox.reset()

    def tearDown(self):
        self.sandbox.reset()
        self.assertEqual(self.sandbox.kit.read_text(), self.original,
                         "field_atlas sandbox not restored")

    def _mutate_and_check(self, mutate, expect: str) -> None:
        kit = json.loads(self.original)
        mutate(kit)
        self.sandbox.write_kit(kit)
        out = self.sandbox.check("--check-one", "field_atlas")
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn(expect, out.stdout)

    def test_unknown_role_fails(self):
        def mutate(kit):
            kit["roles"]["wallpaper"] = [dict(kit["roles"]["hero"][0])]
        self._mutate_and_check(mutate, "loader vocabulary")

    def test_duplicate_asset_id_fails(self):
        def mutate(kit):
            kit["roles"]["fox"][0]["id"] = kit["roles"]["hero"][0]["id"]
        self._mutate_and_check(mutate, "declared twice")

    def test_row_without_a_source_fails(self):
        # The exemption above only relaxes *which* source word is acceptable; a row with no source
        # at all is still a broken claim and must be refused.
        def mutate(kit):
            kit["roles"]["home_ground"][0]["source"] = ""
        self._mutate_and_check(mutate, "row declares no source")


class LoaderVocabulary(unittest.TestCase):
    """The judge's role vocabulary must be the one trunk's readers actually mount.

    `home_ground` joined `field_atlas@3` when the owner-approved Home ground became a kit role, and
    the Home stage backdrop is painted from it (`desktop/plugin.js` role
    `kit.home_ground.home-ground`, asserted by
    `test_desktop_home_scene_geometry.test_the_stage_backdrop_is_the_home_ground_plate`). The judge
    kept a copy of the VQ-004 branch's display-only tuple and refused the manifest the product
    ships. Rather than trust either list, this test derives the vocabulary from the consumer: the
    roles `build_cb_assets.py` emits and the roles the shipped kit manifest records.
    """

    @staticmethod
    def _judge():
        import importlib.util

        spec = importlib.util.spec_from_file_location("vq008_kits", SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load the judge from {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _build_full_roles() -> tuple[str, ...]:
        """`KIT_FULL_ROLES` from the builder's own source, read without importing PIL/venv code."""
        import ast

        tree = ast.parse((ROOT / "scripts" / "build_cb_assets.py").read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "KIT_FULL_ROLES":
                return tuple(role for role, _quality in ast.literal_eval(node.value))
        raise AssertionError("build_cb_assets.py declares no KIT_FULL_ROLES")

    def test_the_vocabulary_covers_every_role_the_build_mounts(self):
        roles = set(self._judge().KIT_ROLES)
        built = set(self._build_full_roles())
        self.assertIn("home_ground", built,
                      "the builder no longer mounts the Home ground; re-decide the vocabulary")
        self.assertLessEqual(built, roles, f"{built - roles} is mounted by the build but refused "
                                           f"by the judge")

    def test_the_vocabulary_covers_every_shipped_kit_role(self):
        manifest = json.loads((ROOT / "assets" / "kit" / "manifest.json").read_text(encoding="utf-8"))
        shipped = {str(row.get("kit_role") or "") for row in manifest} - {""}
        self.assertIn("home_ground", shipped,
                      "the shipped manifest records no home_ground plate")
        self.assertLessEqual(shipped, set(self._judge().KIT_ROLES),
                             f"{shipped - set(self._judge().KIT_ROLES)} ships but the judge refuses it")

    def test_the_home_stage_backdrop_names_the_role(self):
        # The surface, not a comment: the desktop plugin resolves the ground under this role name.
        plugin = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
        self.assertIn('"role": "kit.home_ground.home-ground"', plugin)


class FixtureHygiene(unittest.TestCase):
    """The mutation fixtures must not be able to poison a worktree (t_3dca7b5a).

    Acceptance: kill a run mid-suite (SIGKILL), re-run — the suite is green or says the worktree is
    dirty, never a false claim failure. Both halves are exercised here: the kill test SIGKILLs a
    real fixture test while its mutant is on disk and requires the shipped bytes to be untouched;
    the guard test requires a dirty shipped manifest to be reported as dirty, in those words.
    """

    SHIPPED = [KIT_REL, LOG_REL, FALLBACK_KIT_REL]

    @classmethod
    def setUpClass(cls):
        # On an already-poisoned worktree this class has nothing to prove: the kill test would
        # be killed by the guard in the child it spawns and read as "the kill window was missed".
        # Say the worktree is dirty instead, like the judge classes do.
        assert_pristine(judged_rels())

    def test_a_killed_mutation_leaves_the_shipped_kits_untouched(self):
        before = {rel: (ROOT / rel).read_bytes() for rel in self.SHIPPED}
        sandbox_root = Path(tempfile.mkdtemp(prefix="vq008-kill-"))
        self.addCleanup(shutil.rmtree, sandbox_root, True)
        env = dict(os.environ, VQ008_SANDBOX_ROOT=str(sandbox_root))
        proc = subprocess.Popen(
            [sys.executable, "-m", "unittest",
             "tests.test_vq008_kits.KitJudge.test_replaced_subject_cues_fails"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        mutant = sandbox_root / GRAMMAR / "kit.json"
        try:
            deadline = time.time() + 120
            landed = False
            while time.time() < deadline:
                if mutant.exists():
                    try:
                        if json.loads(mutant.read_text()).get("subject_cues") == [
                            "generic classroom", "stock photo"
                        ]:
                            landed = True
                            break
                    except ValueError:
                        pass
                if proc.poll() is not None:
                    break
                time.sleep(0.01)
            self.assertTrue(landed, "the fixture never wrote its mutant; the kill window was missed")
            os.killpg(proc.pid, signal.SIGKILL)  # exactly what a supervisor timeout does
            proc.communicate(timeout=30)
            self.assertEqual(proc.returncode, -signal.SIGKILL)
            self.assertTrue(mutant.exists(), "the kill did not land mid-mutation")
        finally:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate(timeout=30)
        after = {rel: (ROOT / rel).read_bytes() for rel in self.SHIPPED}
        self.assertEqual(
            before, after,
            "a SIGKILLed mutation test wrote the shipped kit tree — the next run would adopt the "
            "mutant as its baseline",
        )

    def test_the_guard_reports_a_dirty_shipped_kit(self):
        tmp = Path(tempfile.mkdtemp(prefix="vq008-guard-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        shipped = json.loads(KIT.read_text())
        target = tmp / KIT_REL
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(shipped, indent=2) + "\n")
        git = ["git", "-c", "user.email=qa@coursebook.local", "-c", "user.name=qa"]
        for argv in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "shipped kit"]):
            subprocess.run(git + argv, cwd=tmp, check=True, capture_output=True)
        assert_pristine([KIT_REL], root=tmp)  # clean: no error
        target.write_text(json.dumps({**shipped, "subject_cues": ["generic classroom", "stock photo"]}))
        with self.assertRaises(AssertionError) as caught:
            assert_pristine([KIT_REL], root=tmp)
        message = str(caught.exception)
        self.assertIn(KIT_REL, message)
        self.assertIn("differs from HEAD", message)
        self.assertIn("worktree is dirty", message)
        self.assertIn("git checkout --", message)
        assert_pristine([KIT_REL], root=tmp, allow_dirty=True)  # explicit opt-in judges the edit


if __name__ == "__main__":
    unittest.main()
