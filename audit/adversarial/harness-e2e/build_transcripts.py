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
            # CP-015 item 15: the plan states its own typed exit. Authored here, not synthesised,
            # so a rebuild of the recording carries the same declaration the rules read.
            "exit_performance": "performance",
            "terminal_performance": "Replace the inner tube on a road bike and check that the "
                                    "tyre holds air before riding.",
            # H-195: the plan states its own arc and starting assumptions. Authored here, not
            # synthesised, so the recorded plan is a plan the rules would accept.
            "through_line": (
                "One repair from start to finish: the wheel comes off, the tube goes in, the "
                "bead is checked by hand, and the brakes are proved before the ride."
            ),
            "prerequisite_assumptions": [
                "The learner has a floor pump, a tyre lever and a spare tube of the right size.",
                "The learner can already identify the brake quick-release on this bike.",
            ],
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
            "exit_performance": "knowledge",
            "terminal_performance": "Read intervals, triads and the circle of fifths, and explain "
                                    "how a chord is built.",
            # H-195: the arc the units build and the standing the learner starts from.
            "through_line": (
                "Each unit turns a sound into a number and then a number into a name: semitones "
                "first, then the thirds, then the triads, then the circle that places every "
                "chord of one real song."
            ),
            "prerequisite_assumptions": [
                "The learner can find middle C on a keyboard or piano app.",
                "The learner has no formal theory training and is not assumed to read music.",
            ],
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
                    # S3: one review slot. The committed plan must schedule at least one review
                    # for its four owner sections.
                    "target_lessons": 3,
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
            # The soldering fixture's research is a *recorded result set*: six pages that were
            # really fetched through the host extract seam (see the transcript's research.pages).
            # This builder must not author page bytes for it, so it preserves the recorded block
            # that is already on disk instead of writing a placeholder over it.
            "preserve_recorded_result_set": True,
        },
        "shape": {
            "weeks": 12,
            "sessions_per_week": 2,
            "learner_outcome": "The learner solders, inspects and reworks a through-hole board "
                               "without lifting a pad.",
            "exit_performance": "performance",
            "terminal_performance": "Build and inspect a through-hole joint, then desolder a part "
                                    "and prove continuity with a meter.",
            # H-195: the arc every unit serves and the standing the learner starts from. The
            # bench safety unit comes first because every later unit assumes a controlled iron.
            "through_line": (
                "One board taken from a safe bench to a proved repair: name the hazards, set the "
                "iron, read the part, seat it, form the joint, inspect it, rework what fails, and "
                "prove continuity before power."
            ),
            "prerequisite_assumptions": [
                "The learner has a temperature-controlled iron, leaded solder, flux and a meter.",
                "The learner has not soldered before and is not assumed to know any bench rule.",
            ],
            "units": [
                {"ordinal": 1, "title": "Safety and the iron",
                 "goal": "Set up a safe bench and a controlled iron.", "prereq_unit_ordinals": [],
                 "target_lessons": 2},
                {"ordinal": 2, "title": "Components and the board",
                 "goal": "Read component values and inspect pads.", "prereq_unit_ordinals": [1],
                 "target_lessons": 2},
                {"ordinal": 3, "title": "Through-hole insertion",
                 "goal": "Form leads and seat a part flush.", "prereq_unit_ordinals": [2],
                 "target_lessons": 3},
                {"ordinal": 4, "title": "Soldering a joint",
                 "goal": "Heat and feed solder into a sound joint.", "prereq_unit_ordinals": [3],
                 "target_lessons": 3},
                {"ordinal": 5, "title": "Inspection and rework",
                 "goal": "Judge a joint and fix a bridge.", "prereq_unit_ordinals": [4],
                 "target_lessons": 3},
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
            # A procedure is measured by a confirmation checklist of the acts, not by a question
            # about them (CP-015g/D1-F1, `CHECK_KIND_BY_TARGET`). The five procedure objectives
            # therefore carry `verification`; the knowledge objectives keep their quiz.
            "check_plan": [
                {"objective_ref": ordinal, "kind": "verification" if target == "procedure" else "quiz",
                 "evidence_target": target}
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


#: The one claim per scenario that the recorded plan grounds in a fetched page. GEN-1 refuses an
#: independent outcome when every objective is `unverified` and no claim verdict links to the
#: ledger, so a recording that wants to exercise `independently_validated` must cite. The quote is
#: copied verbatim from the page the scenario's research pass actually supplies (and must survive
#: `_fit_source_brief`'s 400-character floor); the replay maps `source_url` to the live ledger id.
GROUNDING: dict[str, dict] = {
    "bicycle_single": {
        "objective_ordinal": 1,
        "source_url": "https://example.invalid/recorded/bicycle-inner-tube",
        "quote": "the tyre must be fully deflated, the bead seated by hand, and the brake "
                 "quick-release closed before riding",
    },
    "music_short": {
        "objective_ordinal": 1,
        "source_url": "https://example.invalid/recorded/music-intervals",
        "quote": "It names the semitone counts of the common intervals and the major/minor triad "
                 "recipes.",
    },
    "soldering_full": {
        "objective_ordinal": 9,
        "source_url": "https://physicslabs.colorado.edu/courses/phys-3330/resources/soldering/",
        "quote": "A good solder joint is shiny, smooth, and volcano-shaped — it wets both the pad "
                 "and the component lead completely.",
    },
}


#: Authored short text, one entry per lesson field. A provider authored with the guided-writing
#: contract writes a compressed *sentence*; the replay engine used to synthesise one with a 2/3
#: word-boundary prefix, and that is the clipped ending D8 recorded and H-46 refuses. These are
#: hand-authored complete sentences that drop detail and add no claim atom; H-46b regenerated the
#: packet against them rather than teaching the synthesiser to imitate a provider.
SHORTS: dict[str, dict[str, str]] = {
    "Remove the rear wheel, replace the inner tube and check the brakes": {
        "practice_short": "Deflate the tyre fully and lift the wheel out of the dropouts.",
        "criterion_short": "Seat the new tube by hand and inflate it in small steps.",
        "explanation_short": "A tube that is pinched under the bead fails on the first ride.",
    },
    "Build a major and a minor triad from a root note": {
        "practice_short": "From C, stack a major third and a perfect fifth.",
        "criterion_short": "Both triads share the root and fifth.",
        "explanation_short": "Only the third moves.",
    },
    "Count the semitones in a major third and a perfect fifth": {
        "practice_short": "Start on C and count four semitones to E.",
        "criterion_short": "From C, the fifth note arrives after a four-semitone step.",
        "explanation_short": "Counting semitones turns an interval into a number you can check.",
    },
    "Distinguish the two common thirds by sound": {
        "practice_short": "Play C to E, then C to E flat.",
        "criterion_short": "The darker, lower interval is the one whose middle note is flattened.",
        "explanation_short": "The third decides whether a triad sounds major or minor.",
    },
    "Use the circle of fifths to name the chords in a pop song": {
        "practice_short": "Write the song's chords and find each root on the circle.",
        "criterion_short": "Name the home chord before the key.",
        "explanation_short": "The circle shows which chords belong together.",
    },
    "Name the three burn and fume hazards at the bench": {
        "practice_short": "Point at the iron, the fume path and your eyes.",
        "criterion_short": "The three hazards are the hot iron, the solder fumes and flying clippings.",
        "explanation_short": "Naming the hazard is what makes the bench rules stick.",
    },
    "Set an iron to the temperature a leaded joint needs": {
        "practice_short": "Set the station and wait for the display to settle.",
        "criterion_short": "Leaded solder wants a moderate setting.",
        "explanation_short": "Temperature is a time control.",
    },
    "Read a resistor value from its colour bands": {
        "practice_short": "Read the bands left to right.",
        "criterion_short": "Brown, black, red, gold is ten times one hundred.",
        "explanation_short": "The code is positional.",
    },
    "Inspect a pad for lift before inserting a part": {
        "practice_short": "Look at the pad edge against the board.",
        "criterion_short": "A sound pad sits flat on the board.",
        "explanation_short": "A lifted pad turns a one-minute joint into a board repair.",
    },
    "Form a lead so the part seats flush": {
        "practice_short": "Bend the lead with pliers at the board thickness.",
        "criterion_short": "The body sits flat with the lead bent.",
        "explanation_short": "A part that stands off the board strains its joints.",
    },
    "Insert a part in the right orientation": {
        "practice_short": "Find the marking on the part and match it to the board's own marking.",
        "criterion_short": "Both markings face the same way.",
        "explanation_short": "Orientation errors survive soldering.",
    },
    "Heat the pad and lead together before feeding solder": {
        "practice_short": "Touch the tip to the pad and the lead at once.",
        "criterion_short": "The joint reaches temperature first.",
        "explanation_short": "Solder fed onto the tip makes a cold joint.",
    },
    "Recognise a cold joint from its surface": {
        "practice_short": "Compare a grainy joint with a bright fillet.",
        "criterion_short": "A cold joint has a grainy, matte surface.",
        "explanation_short": "Surface is the cheapest inspection you have.",
    },
    "Inspect a finished joint against the fillet criterion": {
        "practice_short": "Judge each joint on the board against the fillet criterion.",
        "criterion_short": "A sound joint is shiny, concave and covers the pad.",
        "explanation_short": "Applying one criterion to many joints is the skill.",
    },
    "Prove continuity with a meter after rework": {
        "practice_short": "Set the meter to continuity and probe the two ends.",
        "criterion_short": "Continuity proves the repair conducts.",
        "explanation_short": "A joint can look right and still be open.",
    },
    "Desolder a two-lead part without overheating it": {
        "practice_short": "Add fresh solder to each joint and alternate heat between the leads.",
        "criterion_short": "Fresh solder and alternating heat keep the pads alive.",
        "explanation_short": "Old solder has lost its flux.",
    },
    "Wick a solder bridge without lifting the pad": {
        "practice_short": "Add flux and lay the wick over the bridge.",
        "criterion_short": "Heat through the wick and stop.",
        "explanation_short": "Pulling the wick while the solder is solid lifts pads.",
    },
}


#: H-195 depth for each recorded lesson: a lesson-specific heading pair, one authored sentence on
#: why the step matters and one second example or counterexample. The replay writes
#: ``<practice>. <why>`` as the model segment and ``<criterion>. <counter>`` as the guided one, so
#: the recorded lesson meets the deterministic teaching floor on its own text instead of leaving
#: the floor to be lowered for a fixture. Every sentence here is authored; nothing is synthesised
#: from the plain fields, and ``build()`` refuses a lesson with no entry.
LESSON_DEPTH: dict[str, dict] = {
    "Remove the rear wheel, replace the inner tube and check the brakes": {
        "headings": ("Release the wheel before the tube", "Seat the bead, then check the brakes"),
        "why": (
            "The wheel comes off before the tube is touched, and the bead is the part that "
            "decides whether the repair holds."
        ),
        "counter": (
            "Forcing the bead with a lever marks the tyre, and a marked bead seats unevenly, so "
            "the hand check stays the last step."
        ),
    },
    "Count the semitones in a major third and a perfect fifth": {
        "headings": ("Count from the start note", "Check the count at the keyboard"),
        "why": (
            "Every interval you name in this course is a semitone count, so this number is the "
            "unit the rest of the course measures with."
        ),
        "counter": (
            "If you count from the wrong start note the number still adds up, which is why you "
            "say the start note and the interval together."
        ),
    },
    "Distinguish the two common thirds by sound": {
        "headings": ("Hear the two thirds", "Name it before you look"),
        "why": (
            "The two thirds are the whole difference between a major and a minor sound, so the "
            "ear is trained before the letters are."
        ),
        "counter": (
            "Naming the interval before you look at the keys keeps the ear honest; naming it "
            "after is just reading the keys."
        ),
    },
    "Build a major and a minor triad from a root note": {
        "headings": ("Stack both triads from one root", "Lower the third, keep the fifth"),
        "why": (
            "A triad is the chord you will find in every song analysis later, so the recipe is "
            "learned on one root first."
        ),
        "counter": (
            "Changing the root moves the whole triad, but the third still decides the quality; "
            "build it from G to hear the same shape."
        ),
    },
    "Use the circle of fifths to name the chords in a pop song": {
        "headings": ("Find each root on the circle", "Name the home chord first"),
        "why": (
            "The circle is the map from chords to a key, and the home chord is the landmark you "
            "find first on that map."
        ),
        "counter": (
            "A song that never settles on its home chord is still analysable, because the circle "
            "still shows the neighbouring chords it borrows from."
        ),
    },
    "Name the three burn and fume hazards at the bench": {
        "headings": ("Point at each hazard", "Name the hazard before the iron"),
        "why": (
            "Every rule on this bench exists to answer one of these three hazards, so you name "
            "them before you pick up the iron."
        ),
        "counter": (
            "A hazard you cannot name is one you walk into while you are watching the joint, "
            "which is why the naming is its own habit."
        ),
    },
    "Set an iron to the temperature a leaded joint needs": {
        "headings": ("Set and tin before the first joint", "Hotter is not faster"),
        "why": (
            "The setting decides how long the iron sits on a joint, and a long touch is what "
            "damages pads and parts at the bench."
        ),
        "counter": (
            "Turning the station hotter to work faster burns the flux first, and a joint with no "
            "flux goes cold even at temperature."
        ),
    },
    "Read a resistor value from its colour bands": {
        "headings": ("Read the bands left to right", "Check the multiplier band"),
        "why": (
            "Reading the code is how you know a part's value without trusting a label or a "
            "drawer."
        ),
        "counter": (
            "Read from the wrong end and the multiplier lands on the wrong band, so the reading "
            "always starts at the band nearest the end of the body."
        ),
    },
    "Inspect a pad for lift before inserting a part": {
        "headings": ("Press the pad edge lightly", "A lifted pad shows a shadow line"),
        "why": (
            "A pad is the only thing holding the joint to the board, so its condition is checked "
            "before any heat goes near it."
        ),
        "counter": (
            "Pressing harder on a lifted pad tears it away completely, so the toothpick test is "
            "light and stops at the first give."
        ),
    },
    "Form a lead so the part seats flush": {
        "headings": ("Bend the lead at board thickness", "The lead carries the gap"),
        "why": (
            "The bend has to happen before soldering, because a lead bent while the joint is "
            "solid pulls on the pad."
        ),
        "counter": (
            "Holding a part down with pliers while it cools still leaves it standing off the "
            "board later, so the lead carries the gap, not the tool."
        ),
    },
    "Insert a part in the right orientation": {
        "headings": ("Match the two markings", "Solder does not fix a reversed part"),
        "why": (
            "The marking is the only thing on the part that says which way the circuit expects "
            "it, and solder does not fix a reversed part."
        ),
        "counter": (
            "A reversed part can pass a visual check and still fail on power, which is why the "
            "markings are matched before anything is bent."
        ),
    },
    "Heat the pad and lead together before feeding solder": {
        "headings": ("Heat the joint, then feed solder", "Solder on the tip looks joined"),
        "why": (
            "The heat has to reach the joint before the solder is offered, or the solder sits on "
            "top of a cold surface."
        ),
        "counter": (
            "Solder fed onto the tip runs down hot and looks joined, and the same joint fails a "
            "continuity check once it has cooled to room temperature."
        ),
    },
    "Recognise a cold joint from its surface": {
        "headings": ("Compare grainy with bright", "Rework the grainy ones first"),
        "why": (
            "Most cold joints are readable without a meter, and the surface is the first "
            "inspection you can do at your own bench."
        ),
        "counter": (
            "A bright joint can still be cold under the surface, so the grainy ones are the ones "
            "you rework before testing the rest."
        ),
    },
    "Inspect a finished joint against the fillet criterion": {
        "headings": ("Judge every joint by one criterion", "A balled joint is a fail"),
        "why": (
            "One criterion applied to every joint is what keeps the inspection consistent, "
            "instead of judging each joint on how it feels."
        ),
        "counter": (
            "A balled joint is the clearest fail and the easiest to under-call, because it looks "
            "like extra solder rather than a bad joint."
        ),
    },
    "Wick a solder bridge without lifting the pad": {
        "headings": ("Lay the wick over the bridge", "Lift only after the solder flows"),
        "why": (
            "A bridge connects two points the circuit keeps apart, so it is removed before power "
            "is ever applied."
        ),
        "counter": (
            "Lifting the wick early leaves solder behind and pulls on a solid joint, so the wick "
            "comes up only after the solder has flowed into it."
        ),
    },
    "Desolder a two-lead part without overheating it": {
        "headings": ("Add fresh solder to each joint", "Alternate the heat"),
        "why": (
            "Fresh solder restores the flux that makes the old joint flow, so removal stays quick "
            "instead of holding heat on the pads."
        ),
        "counter": (
            "Holding heat on one lead while the other is still solid lifts pads and cooks the "
            "part, so the heat alternates."
        ),
    },
    "Prove continuity with a meter after rework": {
        "headings": ("Probe the ends of the repaired path", "Continuity across the wrong points"),
        "why": (
            "The meter answers the one question the eye cannot: does the repair conduct from one "
            "intended point to the other."
        ),
        "counter": (
            "Continuity across the wrong two points proves nothing, so the probes go on the ends "
            "of the repaired path, not on the nearest metal."
        ),
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


def _research_block(name: str, authored: dict) -> dict:
    """The transcript's research recording, authored or preserved as recorded.

    A scenario whose pages were really fetched declares ``preserve_recorded_result_set``: its
    recording lives in the transcript on disk (real bytes from the host extract seam) and this
    builder must never replace it with authored text. The failure mode is loud — a missing
    recording is an error, not a silently different fixture.
    """
    research = authored["research"]
    if not research.get("preserve_recorded_result_set"):
        return research
    path = TRANSCRIPTS / f"{name}.json"
    recorded = {}
    if path.exists():
        recorded = json.loads(path.read_text(encoding="utf-8")).get("research") or {}
    if not recorded.get("pages"):
        raise SystemExit(
            f"{name}: the recorded research result set is missing from {path.name}; refetch the "
            "pages through the host extract seam and rebuild the recording before regenerating"
        )
    return recorded


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
        short = SHORTS.get(title)
        if short is None:
            raise SystemExit(f"{name}: no authored short for lesson {title!r}")
        depth = LESSON_DEPTH.get(title)
        if depth is None:
            raise SystemExit(f"{name}: no authored depth (headings/why/counter) for {title!r}")
        lessons[title].update(short)
        lessons[title].update(depth)
        # A procedure objective is evidenced by a confirmation checklist of the acts the lesson
        # already teaches (`example_steps`). Derive the items here, once, so a rebuild of the
        # recording cannot silently regress to the quiz that the product now refuses as the
        # measure of a procedure. Lessons that author their own item wording keep it.
        recording = lessons[title]
        if objective["evidence_target"] == "procedure" and not recording.get("items"):
            steps = [str(step) for step in recording.get("example_steps") or [] if str(step).strip()]
            if steps:
                recording["items"] = [
                    {"id": f"step-{index + 1}", "label": step}
                    for index, step in enumerate(steps[:5])
                ]
        # H-195: the recorded lesson has to clear the deterministic teaching floor on its own
        # words, so the builder refuses a transcript that would only pass a lowered floor.
        prose = (
            len(lessons[title]["practice"]) + len(lessons[title]["why"]) + 2
            + len(lessons[title]["criterion"]) + len(lessons[title]["counter"]) + 2
        )
        if prose < 400:
            raise SystemExit(f"{name}: lesson {title!r} authors {prose} teaching characters < 400")
        leaked = _leaks(title, objective, lessons[title])
        if leaked:
            raise SystemExit(f"{name}: lesson {title!r} announces its own answer(s) {leaked}")
    return {
        "transcript_version": "h40/blueprint-v2",
        "scenario": authored["scenario"],
        "research": _research_block(name, authored),
        "shape": shape,
        "lessons": lessons,
        "grounding": GROUNDING[name],
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
