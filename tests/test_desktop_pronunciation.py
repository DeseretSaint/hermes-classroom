"""The pronunciation practice loop is one surface in the lesson, and it never invents a score.

The runtime plugin is one ESM file with no build step, so these tests load the shipped module. The
placement tests render it through ``react-dom/server`` (the same harness the lesson-view tests
use); the interaction tests mount the exported ``PronunciationStudio`` in jsdom with a stub
``@hermes/plugin-sdk``, a fake ``MediaRecorder`` and a fake ``ctx.rest`` so Record -> Stop ->
Compare can actually run.

What this proves: the surface is seated only on a block with an authored narration transcript, the
reference is loaded through the one media route and never autoplays, the take is sent only after
the explicit Record/Stop, and every state the backend can answer with (assessed, empty,
unavailable, refusal, transport failure) renders its own honest copy. What it does NOT prove: that
a real microphone or a real recogniser is present on this machine — the live window run is the
separate evidence for that.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.test_desktop_lesson_views import (
    COMPLETE_BLOCKS,
    SDK_STUB,
    _desktop_node_modules,
    block,
    document,
)

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_JS = ROOT / "desktop" / "plugin.js"

NARRATION_MEDIA = {
    "kind": "audio",
    "role": "narration",
    "artifact_id": "art_0123456789abcdef",
    "purpose": "Reference pronunciation of the target phrase",
    "text_equivalent": "こんにちは。今日はいい天気ですね。",
    "label": "Model phrase",
    "degraded": False,
    "reason": None,
}

VISUAL_MEDIA = {
    "kind": "visual",
    "role": "illustration",
    "artifact_id": "art_visual000000000",
    "purpose": "Context image",
    "text_equivalent": "Two people greeting each other.",
    "label": "Illustration",
    "degraded": False,
    "reason": None,
}


def renumbered(blocks: list[dict]) -> list[dict]:
    """The same blocks, with the narration child placed on the practice block."""
    out = []
    for entry in blocks:
        copy = dict(entry)
        if copy["role"] == "practice":
            copy = dict(copy, media=[NARRATION_MEDIA], check_id="chk_0123456789abcdef")
        out.append(copy)
    return out


SSR_HARNESS = """
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { LessonDocumentView } from './plugin.js'

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))
const index = {}
for (const source of payload.sources || []) index[source.source_id] = source
const html = renderToStaticMarkup(
  React.createElement(LessonDocumentView, {
    document: payload.document,
    view: payload.view,
    sources: index,
    checkSlot: null,
    pronunciation: payload.pronunciation
  })
)
process.stdout.write(html)
"""

DOM_HARNESS = r"""
import React, { act } from 'react'
import { JSDOM } from 'jsdom'

const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://127.0.0.1/',
  pretendToBeVisual: true
})
globalThis.window = dom.window
globalThis.document = dom.window.document
globalThis.HTMLElement = dom.window.HTMLElement
globalThis.Node = dom.window.Node
globalThis.Event = dom.window.Event
globalThis.IS_REACT_ACT_ENVIRONMENT = true

const fs = await import('node:fs')
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'))

// A deterministic take: four bytes of webm-shaped data. No microphone is opened, and the bytes
// never leave this process except through the fake ctx.rest recorded below.
class FakeRecorder {
  static isTypeSupported() { return true }
  constructor(stream, options) {
    this.stream = stream
    this.mimeType = (options && options.mimeType) || 'audio/webm'
    this.state = 'inactive'
    FakeRecorder.last = this
  }
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    if (this.ondataavailable) this.ondataavailable({ data: new dom.window.Blob([new Uint8Array([26, 69, 223, 163])], { type: this.mimeType }) })
    if (this.onstop) this.onstop()
  }
}
class FakeFileReader {
  readAsDataURL() {
    this.result = 'data:audio/webm;base64,GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYEC'
    setTimeout(() => { if (this.onload) this.onload() }, 0)
  }
}
const fakeStream = { getTracks: () => [{ stop: () => {} }] }
Object.defineProperty(dom.window.navigator, 'mediaDevices', {
  configurable: true,
  value: { getUserMedia: async () => fakeStream }
})
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: dom.window.navigator })
globalThis.MediaRecorder = payload.noRecorder ? undefined : FakeRecorder
globalThis.FileReader = FakeFileReader

const mod = await import('./plugin.js')
const calls = []
const responses = payload.responses || {}

const fakeRest = async (path, options) => {
  const method = (options && options.method) || 'GET'
  calls.push({ path, method, body: options && options.body })
  let base = String(path).split('?')[0]
  // A single-home host scopes reads with ?profile=; the fake answers the same either way.
  const match = Object.keys(responses).find((key) => base === key || String(path).startsWith(key))
  if (!match) throw new Error('unexpected rest path ' + path)
  const value = responses[match]
  if (value && value.__throw) throw new Error(value.__throw)
  return value
}

mod.default.register({
  rest: fakeRest,
  register: () => {},
  onDispose: () => {}
})

const { createRoot } = await import('react-dom/client')
const root = createRoot(document.getElementById('root'))
const props = {
  enrolled: {
    enrollmentId: 'enr_0123456789abcdef',
    objectiveId: 'obj_0123456789abcdef',
    revision: 7,
    locale: 'ja',
    block: { id: 'blk_practice01', headline: 'Try it', source_ids: ['src_affection01'], media: [payload.media] },
    media: payload.media,
    implemented: new Set(['pronunciation.attempt', 'notebook.save']),
    onSaved: () => { calls.push({ path: '__onSaved__' }) }
  }
}

const flush = async (ms = 30) => {
  await act(async () => { await new Promise((done) => setTimeout(done, ms)) })
}
const byText = (text) =>
  [...document.querySelectorAll('button')].find((node) => (node.textContent || '').trim() === text) || null
const click = async (node) => {
  if (!node) {
    process.stderr.write('HTML-AT-FAILURE:' + document.getElementById('root').innerHTML)
    throw new Error('button not found')
  }
  await act(async () => { node.dispatchEvent(new dom.window.MouseEvent('click', { bubbles: true })) })
  await flush()
}

await act(async () => { root.render(React.createElement(mod.PronunciationStudio, props.enrolled)) })
await flush()

const read = () => {
  const root = document.getElementById('root')
  const section = document.querySelector('[data-cb-pronunciation]')
  const errorNode = document.querySelector('[data-cb-pronunciation-error]')
  const resultNode = document.querySelector('[data-cb-pronunciation-result]')
  const record = byText('Record') || byText('Record again')
  const saveButton = byText('Save result to notebook') || byText('Saved to notebook')
  return {
    html: root.innerHTML,
    phase: section ? section.getAttribute('data-cb-pronunciation-phase') : null,
    availability: section ? section.getAttribute('data-cb-pronunciation-availability') : null,
    disclosure: (document.querySelector('[data-cb-pronunciation-disclosure]') || {}).textContent || null,
    recordLabel: record ? (record.textContent || '').trim() : null,
    recordDisabled: record ? record.hasAttribute('disabled') : null,
    stop: Boolean(byText('Stop')),
    listen: Boolean(byText('Listen')),
    deleteButton: Boolean(byText('Delete take and result') || byText('Delete take')),
    saveLabel: saveButton ? (saveButton.textContent || '').trim() : null,
    errorNode: errorNode ? { code: errorNode.getAttribute('data-cb-pronunciation-error') } : null,
    resultNode: resultNode ? { status: resultNode.getAttribute('data-cb-pronunciation-result') } : null,
    verdictNode: (() => {
      const node = document.querySelector('[data-cb-pronunciation-verdict]')
      return node ? node.getAttribute('data-cb-pronunciation-verdict') : null
    })(),
    confidenceNode: (() => {
      const node = document.querySelector('[data-cb-pronunciation-confidence]')
      return node ? node.getAttribute('data-cb-pronunciation-confidence') : null
    })(),
    matchedNode: (() => {
      const node = document.querySelector('[data-cb-pronunciation-matched]')
      return node ? node.getAttribute('data-cb-pronunciation-matched') : null
    })(),
    provenanceNode: (document.querySelector('[data-cb-pronunciation-provenance]') || {}).textContent || null,
    audioNodes: document.querySelectorAll('audio').length,
    autoplay: document.querySelector('audio') ? document.querySelector('audio').hasAttribute('autoplay') : null
  }
}

const recordButton = () => byText('Record') || byText('Record again')
const saveButtonEl = () => byText('Save result to notebook') || byText('Saved to notebook')
const deleteButtonEl = () => byText('Delete take and result') || byText('Delete take')

const observed = { calls, steps: [] }
const record = (name) => {
  observed.steps.push({ step: name, ...read(), calls: calls.length })
}

record('initial')

if (payload.script !== 'none') {
  const button = recordButton()
  if (!button || button.hasAttribute('disabled')) {
    // A surface that offers no recording adds no step: Record is disabled by design there.
    record('record-not-offered')
  } else if (payload.script === 'record-without-recorder') {
    await click(button)
    record('no-recorder')
  } else {
    await click(button)
    record('recording')
    await click(byText('Stop'))
    record('compared')
    if (saveButtonEl()) {
      await click(saveButtonEl())
      record('saved')
    }
    if (deleteButtonEl()) {
      await click(deleteButtonEl())
      record('deleted')
    }
  }
}

process.stdout.write(JSON.stringify({ observed, html: document.getElementById('root').innerHTML }))
"""


class PronunciationStudioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("node") is None:
            raise unittest.SkipTest("node is required to render a runtime desktop plugin")
        modules = _desktop_node_modules()
        if modules is None:
            raise unittest.SkipTest("react/react-dom are not installed beside the desktop app")
        cls.tmp = tempfile.TemporaryDirectory(prefix="coursebook-pronunciation-")
        root = Path(cls.tmp.name)
        (root / "plugin.js").write_text(PLUGIN_JS.read_text(encoding="utf-8"), encoding="utf-8")
        (root / "ssr.mjs").write_text(SSR_HARNESS, encoding="utf-8")
        (root / "dom.mjs").write_text(DOM_HARNESS, encoding="utf-8")
        node_modules = root / "node_modules"
        node_modules.mkdir()
        for name in ("react", "react-dom", "scheduler", "jsdom"):
            source = modules / name
            if source.is_dir():
                (node_modules / name).symlink_to(source, target_is_directory=True)
        sdk = node_modules / "@hermes" / "plugin-sdk"
        sdk.mkdir(parents=True)
        (sdk / "package.json").write_text(
            json.dumps({"name": "@hermes/plugin-sdk", "type": "module", "main": "index.js"}), encoding="utf-8"
        )
        (sdk / "index.js").write_text(SDK_STUB, encoding="utf-8")
        cls.root = root

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmp"):
            cls.tmp.cleanup()

    # -- placement --------------------------------------------------------------------------
    def render_document(self, view: str, pronunciation: dict | None, blocks: list[dict] | None = None) -> str:
        doc = document(guided=True, blocks=renumbered(blocks or COMPLETE_BLOCKS), check_id="chk_0123456789abcdef")
        doc["views"] = {"textbook": True, "guided": True, "field_quest": True, "field_notes": False}
        payload = {
            "document": doc,
            "view": view,
            "pronunciation": pronunciation,
            "sources": [{"source_id": "src_affection01", "title": "Affection and register — field notes"}],
        }
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "ssr.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        return result.stdout

    def test_the_studio_is_seated_once_on_the_practice_block(self) -> None:
        bundle = {"enrollmentId": "enr_0123456789abcdef", "objectiveId": "obj_0123456789abcdef",
                  "revision": 7, "locale": "ja", "implemented": ["pronunciation.attempt"]}
        html = self.render_document("textbook", bundle)
        self.assertEqual(html.count('data-cb-pronunciation="blk_practice01"'), 1)
        self.assertIn('data-cb-pronunciation-target="こんにちは。今日はいい天気ですね。"', html)
        self.assertIn("Pronunciation practice", html)

    def test_the_studio_appears_in_all_three_views_at_the_same_block(self) -> None:
        bundle = {"enrollmentId": "enr_0123456789abcdef", "objectiveId": "obj_0123456789abcdef",
                  "revision": 7, "locale": "ja", "implemented": ["pronunciation.attempt"]}
        textbook = self.render_document("textbook", bundle)
        self.assertEqual(textbook.count('data-cb-pronunciation="blk_practice01"'), 1)
        # Guided shows one block at a time, so the practice block is the step it is on.
        guided = self.render_document("guided", bundle, blocks=[COMPLETE_BLOCKS[2]])
        self.assertEqual(guided.count('data-cb-pronunciation="blk_practice01"'), 1)
        quest = self.render_document("field_quest", bundle)
        self.assertEqual(quest.count('data-cb-pronunciation="blk_practice01"'), 1)

    def test_no_bundle_no_studio(self) -> None:
        html = self.render_document("textbook", None)
        self.assertNotIn("Pronunciation practice", html)
        self.assertNotIn("data-cb-pronunciation=", html)

    def test_a_block_without_narration_gets_no_studio(self) -> None:
        doc = document(guided=True, blocks=COMPLETE_BLOCKS, check_id="chk_0123456789abcdef")
        practice = dict(COMPLETE_BLOCKS[2], media=[VISUAL_MEDIA])
        doc["blocks"] = [COMPLETE_BLOCKS[0], COMPLETE_BLOCKS[1], practice, COMPLETE_BLOCKS[3]]
        case = self.root / "case.json"
        case.write_text(json.dumps({
            "document": doc, "view": "textbook",
            "pronunciation": {"enrollmentId": "enr_0123456789abcdef", "objectiveId": "obj_0123456789abcdef",
                              "revision": 7, "locale": "ja", "implemented": ["pronunciation.attempt"]},
            "sources": [],
        }), encoding="utf-8")
        result = subprocess.run(["node", str(self.root / "ssr.mjs"), str(case)],
                                cwd=self.root, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertNotIn("Pronunciation practice", result.stdout)

    # -- state and interaction --------------------------------------------------------------
    def run_dom(self, *, responses: dict, script: str = "record-and-stop", no_recorder: bool = False) -> dict:
        payload = {
            "media": NARRATION_MEDIA,
            "responses": responses,
            "script": script,
            "noRecorder": no_recorder,
        }
        case = self.root / "case.json"
        case.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            ["node", str(self.root / "dom.mjs"), str(case)],
            cwd=self.root, capture_output=True, text=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        return json.loads(result.stdout)

    def base_responses(self, availability: dict, attempt: dict | None = None) -> dict:
        responses = {
            "/runtime": {"wire_version": 9, "implemented_methods": ["pronunciation.attempt", "notebook.save"], "single_home_host": False},
            "/pronunciation/status": {"ok": True, **availability},
            "/media/art_0123456789abcdef": {
                "ok": True, "data_url": "data:audio/mpeg;base64,AAAA", "mime": "audio/mpeg",
                "bytes": 4, "label": "Model phrase", "text_equivalent": NARRATION_MEDIA["text_equivalent"],
            },
            "/rpc": {"ok": True, "result": {"entry_id": "nbe_0123456789abcdef", "revision": 8}},
        }
        if attempt is not None:
            responses["/pronunciation/attempt"] = attempt
        return responses

    def test_available_recogniser_discloses_the_local_provider_and_offers_record(self) -> None:
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": True, "local_only": True},
                {"ok": True, "result": {"status": "empty", "recorded": False, "attempt_id": None,
                                        "revision": 7, "reason": "empty_transcript",
                                        "assessment": {"target": NARRATION_MEDIA["text_equivalent"]}}},
            ),
        )
        first = data["observed"]["steps"][0]
        self.assertEqual(first["availability"], "available")
        self.assertIn("coursebook_local_whisper", first["disclosure"])
        self.assertIn("Nothing is uploaded", first["disclosure"])
        self.assertEqual(first["recordLabel"], "Record")
        self.assertFalse(first["recordDisabled"])
        self.assertEqual(first["audioNodes"], 1)
        self.assertFalse(first["autoplay"])

    def test_no_recogniser_is_practice_only_and_recording_stays_off(self) -> None:
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": False,
                 "reason": "stt_dependency_missing", "model_cached": False, "local_only": True}
            ),
        )
        first = data["observed"]["steps"][0]
        self.assertEqual(first["availability"], "unavailable")
        self.assertIn("Practice only, not graded", first["disclosure"])
        self.assertIn("local recogniser is not installed", first["disclosure"])
        self.assertIn('disabled=""', first["html"])

    def test_a_status_failure_is_reported_as_practice_only(self) -> None:
        responses = self.base_responses({"provider": "x", "available": True, "reason": None})
        responses["/pronunciation/status"] = {"__throw": "backend offline"}
        data = self.run_dom(responses=responses)
        first = data["observed"]["steps"][0]
        self.assertEqual(first["availability"], "unavailable")
        self.assertIn("Practice only, not graded", first["disclosure"])
        self.assertIn("could not be read", first["disclosure"])

    def test_the_full_loop_sends_one_explicit_take_and_prints_the_backend_assessment(self) -> None:
        assessment = {
            "transcript": "こんにちは。今日はいい天気ですね。",
            "target": NARRATION_MEDIA["text_equivalent"],
            "locale": "ja", "provider": "coursebook_local_whisper", "model": "small", "language": "ja",
            "unit": "character", "word_accuracy": 0.6667, "phoneme_accuracy": None, "confidence": 0.7526,
            "words": [
                {"expected": "こ", "heard": "こ", "match": True, "confidence": 0.91},
                {"expected": "ん", "heard": "ん", "match": True, "confidence": 0.7},
                {"expected": "に", "heard": "り", "match": False, "confidence": None},
            ],
            "verdict": "close",
            "evidence_class": "model_assessed",
        }
        attempt = {"ok": True, "result": {"status": "assessed", "recorded": True,
                                          "attempt_id": "prn_0123456789abcdef", "revision": 7,
                                          "assessment": assessment, "reason": None}}
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": True, "local_only": True},
                attempt,
            )
        )
        steps = {row["step"]: row for row in data["observed"]["steps"]}
        self.assertEqual(steps["recording"]["phase"], "recording")
        self.assertIsNotNone(steps["recording"]["stop"])
        self.assertEqual(steps["compared"]["phase"], "done")
        self.assertEqual(steps["compared"]["verdictNode"], "close")
        self.assertEqual(steps["compared"]["confidenceNode"], "75%")
        self.assertEqual(steps["compared"]["matchedNode"], "2/3")
        self.assertIn("model_assessed", steps["compared"]["html"])
        self.assertIn("not verified pronunciation and not a graded score", steps["compared"]["provenanceNode"])

        calls = data["observed"]["calls"]
        posts = [call for call in calls if call["path"] == "/pronunciation/attempt"]
        self.assertEqual(len(posts), 1)
        body = posts[0]["body"]
        self.assertEqual(body["enrollment_id"], "enr_0123456789abcdef")
        self.assertEqual(body["objective_id"], "obj_0123456789abcdef")
        self.assertEqual(body["target"], NARRATION_MEDIA["text_equivalent"])
        self.assertEqual(body["locale"], "ja")
        self.assertEqual(body["expected_revision"], 7)
        self.assertTrue(body["audio_data_url"].startswith("data:audio/webm;base64,"))
        self.assertTrue(body["idempotency_key"].startswith("cb-pronunciation-"))
        self.assertEqual(body["attempt_nonce"].split("-")[0], "cb")

        # Save carries the same evidence into the notebook and says the audio was not stored.
        self.assertEqual(steps["saved"]["saveLabel"], "Saved to notebook")
        rpc_calls = [call for call in calls if call["path"] == "/rpc"]
        self.assertEqual(len(rpc_calls), 1)
        saved = rpc_calls[0]["body"]["payload"]
        self.assertEqual(saved["kind"], "personal_note")
        self.assertEqual(saved["tags"], ["pronunciation_practice"])
        self.assertIn("model_assessed", saved["note"])
        self.assertEqual(saved["source_ref"], '{"block":"blk_practice01","artifact":"art_0123456789abcdef","sources":["src_affection01"]}')
        self.assertEqual(steps["deleted"]["phase"], "idle")
        self.assertNotIn("data-cb-pronunciation-result", steps["deleted"]["html"])

    def test_empty_speech_is_practice_only_and_records_nothing(self) -> None:
        attempt = {"ok": True, "result": {"status": "empty", "recorded": False, "attempt_id": None,
                                          "revision": 7, "reason": "empty_transcript",
                                          "assessment": {"target": NARRATION_MEDIA["text_equivalent"], "verdict": "unavailable"}}}
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": True, "local_only": True}, attempt),
        )
        compared = {row["step"]: row for row in data["observed"]["steps"]}["compared"]
        self.assertIn("Practice only, not graded", compared["html"])
        self.assertIn("did not catch any speech", compared["html"])
        self.assertIsNone(compared["verdictNode"])

    def test_an_unavailable_attempt_prints_its_reason_and_no_verdict(self) -> None:
        attempt = {"ok": True, "result": {"status": "unavailable", "recorded": False, "attempt_id": None,
                                          "revision": 7, "reason": "model_unavailable",
                                          "assessment": {"target": NARRATION_MEDIA["text_equivalent"], "verdict": "unavailable"}}}
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": False, "local_only": True}, attempt),
        )
        compared = {row["step"]: row for row in data["observed"]["steps"]}["compared"]
        self.assertIn("Practice only, not graded", compared["html"])
        self.assertIn("local model is not available", compared["html"])

    def test_a_contract_refusal_renders_the_error_code_and_claims_no_evidence(self) -> None:
        attempt = {"ok": False, "error": {"code": "VALIDATION_FAILED", "category": "validation",
                                          "message": "the take is longer than 30 seconds", "retryable": False}}
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": True, "local_only": True}, attempt),
        )
        compared = {row["step"]: row for row in data["observed"]["steps"]}["compared"]
        self.assertEqual(compared["errorNode"].get("code"), "VALIDATION_FAILED")
        self.assertIn("No evidence was recorded", compared["html"])
        self.assertIsNone(compared["resultNode"])

    def test_a_transport_failure_is_host_unavailable_not_a_score(self) -> None:
        responses = self.base_responses(
            {"provider": "coursebook_local_whisper", "model": "small", "available": True,
             "reason": None, "model_cached": True, "local_only": True})
        responses["/pronunciation/attempt"] = {"__throw": "socket closed"}
        data = self.run_dom(responses=responses)
        compared = {row["step"]: row for row in data["observed"]["steps"]}["compared"]
        self.assertEqual(compared["errorNode"].get("code"), "HOST_UNAVAILABLE")

    def test_without_media_recorder_record_says_so_and_opens_no_microphone(self) -> None:
        data = self.run_dom(
            responses=self.base_responses(
                {"provider": "coursebook_local_whisper", "model": "small", "available": True,
                 "reason": None, "model_cached": True, "local_only": True}),
            script="record-without-recorder",
            no_recorder=True,
        )
        step = data["observed"]["steps"][-1]
        self.assertEqual(step["errorNode"].get("code"), "MIC_UNAVAILABLE")
        self.assertIn("no microphone capture", step["html"])
        self.assertFalse(any(call["path"] == "/pronunciation/attempt" for call in data["observed"]["calls"]))

    # -- honesty guards ---------------------------------------------------------------------
    def test_the_desktop_never_recomputes_accuracy_and_never_autoplays(self) -> None:
        source = PLUGIN_JS.read_text(encoding="utf-8")
        self.assertNotIn("word_accuracy", source)
        self.assertNotIn("phoneme_accuracy", source)
        self.assertNotIn("autoplay:", source)
        self.assertNotIn("autoplay=", source)
        self.assertNotIn("'verified pronunciation'", source)
        self.assertIn("Practice only, not graded", source)

    def test_percent_only_prints_a_real_probability(self) -> None:
        case = self.root / "case.json"
        case.write_text(json.dumps({"media": NARRATION_MEDIA, "responses": {}, "script": "none"}), encoding="utf-8")
        script = self.root / "percent.mjs"
        script.write_text(
            "import { pronPercent, pronunciationAvailabilityCopy } from './plugin.js'\n"
            "const out = {\n"
            "  real: pronPercent(0.7526),\n"
            "  zero: pronPercent(0),\n"
            "  over: pronPercent(1.2),\n"
            "  text: pronPercent('85%'),\n"
            "  missing: pronPercent(null),\n"
            "  unavailable: pronunciationAvailabilityCopy({state:'ready', available:false, reason:'ffmpeg_missing'}).text\n"
            "}\n"
            "process.stdout.write(JSON.stringify(out))\n",
            encoding="utf-8",
        )
        result = subprocess.run(["node", str(script)], cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        out = json.loads(result.stdout)
        self.assertEqual(out["real"], "75%")
        self.assertEqual(out["zero"], "0%")
        self.assertIsNone(out["over"])
        self.assertIsNone(out["text"])
        self.assertIsNone(out["missing"])
        self.assertEqual(out["unavailable"], "Practice only, not graded. Recording stays off because the audio decoder is not installed.")


if __name__ == "__main__":
    unittest.main()
