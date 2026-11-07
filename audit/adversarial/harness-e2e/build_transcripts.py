"""Author the recorded model transcripts the H-40 harness replays (blueprint v2 shape).

The transcript is the *fake* half of the proof: hand-authored course content, stored as JSON and
replayed through the real pipeline. Nothing here talks to a provider or the network.

Blueprint v2 changed the authored document shape (units + objectives + check_plan instead of
sections), so the H-09 transcripts cannot be replayed verbatim; this builder emits the same three
scenarios in the v2 shape. Re-run it to regenerate ``transcripts/*.json``:

    python3 audit/adversarial/harness-e2e/build_transcripts.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRANSCRIPTS = HERE / "transcripts"

#: Scenario content. Each entry authors the blueprint (units/objectives/check_plan) and one lesson
#: body per objective. The replay engine takes every schema-required field it can from the live
#: request payload (rubric profile, capability policy, plan_schema constant) and the authored
#: content from here, so a prompt/schema rename does not silently invalidate the transcript.
SCENARIOS: dict[str, dict] = {
    "bicycle_single": {
        "scenario": {
            "name": "bicycle_single",
            "title": "Replace a bicycle inner tube",
            "goal": "Walk me through replacing the inner tube on my road bike and checking the "
                    "brakes before I ride it today.",
            "recipe": "one_off",
            "scope": "single",
            "locale": "en-US",
            "level": "beginner",
            "subject_domain": "repair",
        },
        "research": {
            "url": "https://example.invalid/recorded/bicycle-inner-tube",
            "title": "Recorded page: replacing a clincher inner tube",
            "content": "A recorded page used only so the research seam returns a source. It states "
                       "that the tyre must be fully deflated, the bead seated by hand, and the "
                       "brake quick-release closed before riding.",
        },
        "shape": {
            "weeks": 1,
            "sessions_per_week": 1,
            "learner_outcome": "The learner replaces the inner tube and confirms the brakes by hand.",
            "units": [
                {
                    "ordinal": 1,
                    "title": "Remove the wheel, replace the tube, check the brakes",
                    "goal": "Get the rear wheel off, fit a sound tube, and prove the brakes work.",
                    "prereq_unit_ordinals": [],
                    "target_lessons": 1,
                }
            ],
            "objectives": [
                {
                    "ordinal": 1,
                    "unit_ref": 1,
                    "title": "Remove the rear wheel, replace the inner tube and check the brakes",
                    "evidence_target": "procedure",
                    "evidence_criteria": [
                        "Removes and refits the wheel without forcing the bead",
                        "States the one condition that makes the repair unsafe to ride",
                    ],
                }
            ],
            "check_plan": [{"objective_ref": 1, "kind": "verification", "evidence_target": "procedure"}],
        },
        "lessons": {
            "Remove the rear wheel, replace the inner tube and check the brakes": {
                "intent": "Talk the learner through the repair and confirm each step was done.",
                "practice": "Deflate the tyre fully, open the brake quick-release, and lift the "
                            "wheel out of the dropouts without levering the bead.",
                "criterion": "Seat the new tube by hand, inflate in small steps, and close the "
                             "quick-release before you spin the wheel.",
                "explanation": "A tube that is pinched under the bead fails on the first ride; the "
                               "hand-check of the bead is the step that catches it.",
                "example_steps": ["Deflate fully", "Lift the wheel out", "Seat the tube by hand"],
                "check_prompt": "Tick each step only after you have actually done it.",
                "reference_answer": "Every listed step performed and checked by hand",
                "accepted_answers": ["all listed steps ticked honestly"],
                "items": [
                    {"id": "item_1", "label": "Deflated the tyre and released the brake"},
                    {"id": "item_2", "label": "Refitted the wheel without forcing the bead"},
                    {"id": "item_3", "label": "Checked the brakes by hand before riding"},
                ],
            }
        },
    },
    "music_short": {
        "scenario": {
            "name": "music_short",
            "title": "Intervals, triads and the circle of fifths",
            "goal": "Understand intervals, triads and the circle of fifths well enough to analyse "
                    "a pop song.",
            "recipe": "committed",
            "scope": "short",
            "locale": "en-US",
            "level": "beginner",
            "subject_domain": "general",
        },
        "research": {
            "url": "https://example.invalid/recorded/music-intervals",
            "title": "Recorded page: intervals and triads",
            "content": "A recorded page used only so the research seam returns a source. It names "
                       "the semitone counts of the common intervals and the major/minor triad "
                       "recipes.",
        },
        "shape": {
            "weeks": 3,
            "sessions_per_week": 2,
            "learner_outcome": "The learner names intervals and triads and uses the circle of "
                               "fifths to analyse a pop song.",
            "units": [
                {
                    "ordinal": 1,
                    "title": "Intervals on the keyboard",
                    "goal": "Name an interval from its semitone count and sound.",
                    "prereq_unit_ordinals": [],
                    "target_lessons": 2,
                },
                {
                    "ordinal": 2,
                    "title": "Triads and the circle of fifths",
                    "goal": "Build a triad from the circle and use it on a real song.",
                    "prereq_unit_ordinals": [1],
                    "target_lessons": 2,
                },
            ],
            "objectives": [
                {
                    "ordinal": 1,
                    "unit_ref": 1,
                    "title": "Count the semitones in a major third and a perfect fifth",
                    "evidence_target": "recall",
                    "evidence_criteria": ["States the semitone count for each interval"],
                },
                {
                    "ordinal": 2,
                    "unit_ref": 1,
                    "title": "Distinguish the two common thirds by sound",
                    "evidence_target": "discrimination",
                    "evidence_criteria": ["Names which third was played and why"],
                },
                {
                    "ordinal": 3,
                    "unit_ref": 2,
                    "title": "Build a major and a minor triad from a root note",
                    "evidence_target": "comprehension",
                    "evidence_criteria": ["Spells both triads from one root"],
                },
                {
                    "ordinal": 4,
                    "unit_ref": 2,
                    "title": "Use the circle of fifths to name the chords in a pop song",
                    "evidence_target": "transfer",
                    "evidence_criteria": ["Maps the song's chords onto the circle and names the key"],
                },
            ],
            "check_plan": [
                {"objective_ref": 1, "kind": "quiz", "evidence_target": "recall"},
                {"objective_ref": 2, "kind": "quiz", "evidence_target": "discrimination"},
                {"objective_ref": 3, "kind": "quiz", "evidence_target": "comprehension"},
                {"objective_ref": 4, "kind": "quiz", "evidence_target": "transfer"},
            ],
        },
        "lessons": {
            "Count the semitones in a major third and a perfect fifth": {
                "intent": "Teach the semitone count and check recall of the two numbers.",
                "practice": "Start on C, count four semitones to E, and say the interval name out "
                            "loud before you play it.",
                "criterion": "From C, the fifth note arrives after the same four-semitone step plus three more.",
                "explanation": "Counting semitones turns an interval from a feeling into a number "
                               "you can check at the keyboard.",
                "example_steps": ["Start on C", "Count four semitones", "Name the interval"],
                "check_prompt": "How many semitones are in a perfect fifth?",
                "reference_answer": "seven",
                "accepted_answers": ["7"],
                "items": None,
            },
            "Distinguish the two common thirds by sound": {
                "intent": "Teach the sound difference and check the learner can name it.",
                "practice": "Play C to E, then C to E flat, and hum each interval back before "
                            "naming it.",
                "criterion": "The darker, lower interval is the one whose middle note is flattened; "
                             "name it before checking the keys.",
                "explanation": "The third decides whether a triad sounds major or minor, so the ear "
                               "has to hear the difference before the theory helps.",
                "example_steps": ["Play C to E", "Play C to E flat", "Name each third"],
                "check_prompt": "Which interval is three semitones wide?",
                "reference_answer": "minor third",
                "accepted_answers": ["a minor third"],
                "items": None,
            },
            "Build a major and a minor triad from a root note": {
                "intent": "Teach the triad recipes and check both spellings.",
                "practice": "From C, stack a major third and a perfect fifth for the major triad, "
                            "then lower the middle note for the minor.",
                "criterion": "Both triads share the root and fifth; lowering the middle note is "
                             "the whole difference.",
                "explanation": "Both triads share the root and fifth; only the third moves, which "
                               "is why the third carries the quality.",
                "example_steps": ["Stack root, third, fifth", "Lower the third", "Compare the two"],
                "check_prompt": "Which note is the third of a C minor triad?",
                "reference_answer": "E flat",
                "accepted_answers": ["Eb", "E-flat"],
                "items": None,
            },
            "Use the circle of fifths to name the chords in a pop song": {
                "intent": "Teach the circle as a song-analysis tool and check one mapping.",
                "practice": "Write the song's chords, find each root on the circle, and mark the "
                            "home chord before naming the key.",
                "criterion": "The home chord is the one the song resolves to; name it before the key.",
                "explanation": "The circle shows which chords belong together, so a song's chord "
                               "list becomes a key and a set of functions.",
                "example_steps": ["List the chords", "Place the roots", "Name the key"],
                "check_prompt": "A song uses C, G, A minor and F. Which key is it in?",
                "reference_answer": "C major",
                "accepted_answers": ["the key of C major"],
                "items": None,
            },
        },
    },
    "soldering_full": {
        "scenario": {
            "name": "soldering_full",
            "title": "Through-hole soldering for a first repair",
            "goal": "Prepare for a first soldering repair on a through-hole PCB: safety, component "
                    "placement, joints, inspection and desoldering.",
            "recipe": "committed",
            "scope": "full",
            "locale": "en-US",
            "level": "beginner",
            "subject_domain": "technical_procedure",
        },
        "research": {
            "url": "https://example.invalid/recorded/through-hole-soldering",
            "title": "Recorded page: through-hole soldering",
            "content": "A recorded page used only so the research seam returns a source. It states "
                       "that joints are heated pad and lead together, solder is fed in after the "
                       "joint reaches temperature, and a shiny fillet is the inspection criterion.",
        },
        "shape": {
            "weeks": 12,
            "sessions_per_week": 2,
            "learner_outcome": "The learner solders, inspects and reworks a through-hole board "
                               "without lifting a pad.",
            "units": [
                {"ordinal": 1, "title": "Safety and the iron",
                 "goal": "Set up a safe bench and a controlled iron.", "prereq_unit_ordinals": [],
                 "target_lessons": 2},
                {"ordinal": 2, "title": "Components and the board",
                 "goal": "Read component values and inspect pads.", "prereq_unit_ordinals": [1],
                 "target_lessons": 2},
                {"ordinal": 3, "title": "Through-hole insertion",
                 "goal": "Form leads and seat a part flush.", "prereq_unit_ordinals": [2],
                 "target_lessons": 2},
                {"ordinal": 4, "title": "Soldering a joint",
                 "goal": "Heat and feed solder into a sound joint.", "prereq_unit_ordinals": [3],
                 "target_lessons": 2},
                {"ordinal": 5, "title": "Inspection and rework",
                 "goal": "Judge a joint and fix a bridge.", "prereq_unit_ordinals": [4],
                 "target_lessons": 2},
                {"ordinal": 6, "title": "Desoldering and final check",
                 "goal": "Remove a part without damage and prove continuity.",
                 "prereq_unit_ordinals": [5], "target_lessons": 2},
            ],
            "objectives": [
                {"ordinal": 1, "unit_ref": 1, "title": "Name the three burn and fume hazards at the bench",
                 "evidence_target": "recall", "evidence_criteria": ["Names iron, fume and eye hazards"]},
                {"ordinal": 2, "unit_ref": 1, "title": "Set an iron to the temperature a leaded joint needs",
                 "evidence_target": "procedure", "evidence_criteria": ["States the setting and why"]},
                {"ordinal": 3, "unit_ref": 2, "title": "Read a resistor value from its colour bands",
                 "evidence_target": "comprehension", "evidence_criteria": ["Decodes a four-band value"]},
                {"ordinal": 4, "unit_ref": 2, "title": "Inspect a pad for lift before inserting a part",
                 "evidence_target": "discrimination", "evidence_criteria": ["Tells a sound pad from a lifted one"]},
                {"ordinal": 5, "unit_ref": 3, "title": "Form a lead so the part seats flush",
                 "evidence_target": "procedure", "evidence_criteria": ["Bends and seats without forcing"]},
                {"ordinal": 6, "unit_ref": 3, "title": "Insert a part in the right orientation",
                 "evidence_target": "comprehension", "evidence_criteria": ["Matches polarity marking to the board"]},
                {"ordinal": 7, "unit_ref": 4, "title": "Heat the pad and lead together before feeding solder",
                 "evidence_target": "procedure", "evidence_criteria": ["Describes the heat order"]},
                {"ordinal": 8, "unit_ref": 4, "title": "Recognise a cold joint from its surface",
                 "evidence_target": "discrimination", "evidence_criteria": ["Contrasts dull and shiny fillets"]},
                {"ordinal": 9, "unit_ref": 5, "title": "Inspect a finished joint against the fillet criterion",
                 "evidence_target": "transfer", "evidence_criteria": ["Applies the criterion to a photo"]},
                {"ordinal": 10, "unit_ref": 5, "title": "Wick a solder bridge without lifting the pad",
                 "evidence_target": "procedure", "evidence_criteria": ["States the wick and heat order"]},
                {"ordinal": 11, "unit_ref": 6, "title": "Desolder a two-lead part without overheating it",
                 "evidence_target": "procedure", "evidence_criteria": ["Alternates heat and adds fresh solder"]},
                {"ordinal": 12, "unit_ref": 6, "title": "Prove continuity with a meter after rework",
                 "evidence_target": "transfer", "evidence_criteria": ["Chooses the continuity setting and reads it"]},
            ],
            "check_plan": [
                {"objective_ref": ordinal, "kind": "quiz", "evidence_target": target}
                for ordinal, target in enumerate(
                    ["recall", "procedure", "comprehension", "discrimination", "procedure",
                     "comprehension", "procedure", "discrimination", "transfer", "procedure",
                     "procedure", "transfer"], start=1)
            ],
        },
        "lessons": {
            "Name the three burn and fume hazards at the bench": {
                "intent": "Name the hazards before touching the iron.",
                "practice": "Point at the iron, the fume path and your eyes, and name the hazard "
                            "each one creates.",
                "criterion": "The three hazards are the hot iron, the solder fumes and flying "
                             "clippings near the eyes.",
                "explanation": "Naming the hazard is what makes the bench rules stick when you are "
                               "concentrating on the joint.",
                "example_steps": ["Point at the iron", "Point at the fume path", "Name the eye risk"],
                "check_prompt": "Which hazard do solder fumes mainly create?",
                "reference_answer": "respiratory irritation",
                "accepted_answers": ["breathing irritation", "lung irritation"],
                "items": None,
            },
            "Set an iron to the temperature a leaded joint needs": {
                "intent": "Teach the temperature setting for leaded solder.",
                "practice": "Set the station, wait for the display to settle, and tin the tip "
                            "before the first joint.",
                "criterion": "Leaded solder wants a moderate setting; hotter burns the flux before "
                             "the joint forms.",
                "explanation": "Temperature is a time control: too cold means a longer touch and a "
                               "colder joint.",
                "example_steps": ["Set the dial", "Wait for the display", "Tin the tip"],
                "check_prompt": "What temperature range suits leaded solder?",
                "reference_answer": "320 to 350 degrees Celsius",
                "accepted_answers": ["320-350 C", "320 to 350 C"],
                "items": None,
            },
            "Read a resistor value from its colour bands": {
                "intent": "Teach the four-band code.",
                "practice": "Read the bands left to right, then multiply by the third band before "
                            "you trust the value.",
                "criterion": "Brown, black, red, gold is ten times one hundred, so one thousand "
                             "ohms at five percent.",
                "explanation": "The code is positional, so reading order matters more than colour "
                               "memory.",
                "example_steps": ["Read band one", "Read band two", "Apply the multiplier"],
                "check_prompt": "What is brown-black-red-gold?",
                "reference_answer": "1k ohm at 5 percent",
                "accepted_answers": ["1000 ohm", "1 kOhm"],
                "items": None,
            },
            "Inspect a pad for lift before inserting a part": {
                "intent": "Teach pad inspection.",
                "practice": "Look at the pad edge against the board and press gently with a "
                            "toothpick before you insert anything.",
                "criterion": "A sound pad sits flat on the board; a lifted pad shows a shadow line "
                             "and gives under light pressure.",
                "explanation": "A lifted pad turns a one-minute joint into a board repair, so it is "
                               "checked before heat.",
                "example_steps": ["Light the pad edge", "Press gently", "Compare to a sound pad"],
                "check_prompt": "What does a lifted pad do under light pressure?",
                "reference_answer": "it moves",
                "accepted_answers": ["moves", "it shifts"],
                "items": None,
            },
            "Form a lead so the part seats flush": {
                "intent": "Teach lead forming.",
                "practice": "Bend the lead with pliers at the board thickness and let the part drop "
                            "flush without pushing it.",
                "criterion": "The body sits flat with the lead bent between the body and the pad.",
                "explanation": "A part that stands off the board strains its joints every time the "
                               "board flexes.",
                "example_steps": ["Measure the board", "Bend with pliers", "Drop the part"],
                "check_prompt": "Which side of the board should the bent lead sit on?",
                "reference_answer": "the solder side",
                "accepted_answers": ["the underside"],
                "items": None,
            },
            "Insert a part in the right orientation": {
                "intent": "Teach polarity against the board marking.",
                "practice": "Find the marking on the part and match it to the board's own marking "
                            "before you bend anything.",
                "criterion": "The part's marking and the board's marking face the same way.",
                "explanation": "Orientation errors survive soldering and only show up when the "
                               "circuit does not work.",
                "example_steps": ["Read the part", "Read the board", "Align them"],
                "check_prompt": "Which feature decides the part's orientation?",
                "reference_answer": "the stripe on the part",
                "accepted_answers": ["the part's own stripe"],
                "items": None,
            },
            "Heat the pad and lead together before feeding solder": {
                "intent": "Teach the heat order.",
                "practice": "Touch the tip to the pad and the lead at once, count two seconds, then "
                            "feed solder into the joint, not the tip.",
                "criterion": "The joint reaches temperature first; solder follows the heat.",
                "explanation": "Solder fed onto the tip makes a cold joint that looks finished and "
                               "fails later.",
                "example_steps": ["Touch pad and lead", "Wait for heat", "Feed into the joint"],
                "check_prompt": "Where does the solder go?",
                "reference_answer": "into the heated joint",
                "accepted_answers": ["heated joint"],
                "items": None,
            },
            "Recognise a cold joint from its surface": {
                "intent": "Teach visual discrimination.",
                "practice": "Compare a grainy joint with a bright fillet and say which one moved "
                            "while it cooled.",
                "criterion": "A cold joint has a grainy, matte surface; a sound fillet is bright and concave.",
                "explanation": "Surface is the cheapest inspection you have, and it is read before "
                               "power is applied.",
                "example_steps": ["Look at the surface", "Compare to a fillet", "Name the cold one"],
                "check_prompt": "What does a cold joint look like?",
                "reference_answer": "dull and lumpy",
                "accepted_answers": ["dull", "lumpy and dull"],
                "items": None,
            },
            "Inspect a finished joint against the fillet criterion": {
                "intent": "Apply the criterion to a real joint.",
                "practice": "Judge each joint on the board against the fillet criterion and mark "
                            "the ones that need rework.",
                "criterion": "A sound joint is shiny, concave and covers the pad without a ball.",
                "explanation": "Applying one criterion to many joints is the skill; the criterion "
                               "itself does not change.",
                "example_steps": ["Pick a joint", "Compare to the criterion", "Mark rework"],
                "check_prompt": "Which joint needs rework?",
                "reference_answer": "the balled joint",
                "accepted_answers": ["the one with a ball", "the ball"],
                "items": None,
            },
            "Wick a solder bridge without lifting the pad": {
                "intent": "Teach bridge removal.",
                "practice": "Add flux, lay the wick over the bridge, and heat the wick until the "
                            "solder flows into it before lifting.",
                "criterion": "Heat through the wick and stop as soon as the bridge disappears.",
                "explanation": "Pulling the wick while the solder is solid is how pads lift.",
                "example_steps": ["Add flux", "Lay the wick", "Heat until the bridge flows"],
                "check_prompt": "When do you lift the wick?",
                "reference_answer": "after the solder flows into it",
                "accepted_answers": ["after the bridge disappears", "once the solder flows"],
                "items": None,
            },
            "Desolder a two-lead part without overheating it": {
                "intent": "Teach desoldering a part.",
                "practice": "Add fresh solder to each joint, alternate heat between the leads, and "
                            "pull gently once both are molten.",
                "criterion": "Fresh solder and alternating heat keep the part and the pads alive.",
                "explanation": "Old solder has lost its flux, so adding fresh solder is what makes "
                               "removal quick.",
                "example_steps": ["Add fresh solder", "Alternate the heat", "Pull gently"],
                "check_prompt": "Why add fresh solder before desoldering?",
                "reference_answer": "to restore the flux",
                "accepted_answers": ["fresh flux", "it restores flux"],
                "items": None,
            },
            "Prove continuity with a meter after rework": {
                "intent": "Teach the final electrical check.",
                "practice": "Set the meter to continuity, probe the two ends of the repaired path, "
                            "and confirm the beep before power.",
                "criterion": "Continuity between the intended points proves the repair conducts.",
                "explanation": "A joint can look right and still be open; the meter is the check "
                               "the eye cannot make.",
                "example_steps": ["Set continuity", "Probe both ends", "Confirm the beep"],
                "check_prompt": "Which meter setting proves the repair conducts?",
                "reference_answer": "the continuity setting",
                "accepted_answers": ["continuity mode"],
                "items": None,
            },
        },
    },
}


def _json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _normalise(text: str) -> str:
    """The same shape the pipeline compares with: lowercase, punctuation collapsed."""
    cleaned = "".join(char.lower() if char.isalnum() or char.isspace() else " " for char in text)
    return " ".join(cleaned.split())


def _leaks(title: str, shape_objective: dict, lesson: dict) -> list[str]:
    """Answers that appear in the learner-facing narrative this transcript would produce.

    The pipeline refuses such a lesson (``assert_no_answer_leak``). Catching it here keeps the
    recording honest instead of discovering it as a product failure at replay time.
    """
    narrative = " \n".join(
        str(value)
        for value in (
            title,
            lesson.get("intent"),
            lesson.get("practice"),
            lesson.get("criterion"),
            lesson.get("explanation"),
            " ".join(lesson.get("example_steps") or []),
        )
    )
    haystack = _normalise(narrative)
    answers = [lesson.get("reference_answer")] + list(lesson.get("accepted_answers") or [])
    return [
        str(answer)
        for answer in answers
        if answer and _normalise(str(answer)) and _normalise(str(answer)) in haystack
    ]


def build(name: str) -> dict:
    authored = SCENARIOS[name]
    shape = authored["shape"]
    lessons = authored["lessons"]
    titles = [str(objective["title"]) for objective in shape["objectives"]]
    missing = [title for title in titles if title not in lessons]
    if missing:
        raise SystemExit(f"{name}: no lesson authored for {missing}")
    extra = [title for title in lessons if title not in titles]
    if extra:
        raise SystemExit(f"{name}: lesson authored for unknown objective(s) {extra}")
    for objective in shape["objectives"]:
        title = str(objective["title"])
        leaked = _leaks(title, objective, lessons[title])
        if leaked:
            raise SystemExit(f"{name}: lesson {title!r} announces its own answer(s) {leaked}")
    return {
        "transcript_version": "h40/blueprint-v2",
        "scenario": authored["scenario"],
        "research": authored["research"],
        "shape": shape,
        "lessons": lessons,
    }


def main() -> int:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    for name in SCENARIOS:
        path = TRANSCRIPTS / f"{name}.json"
        path.write_text(_json(build(name)) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(HERE.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
