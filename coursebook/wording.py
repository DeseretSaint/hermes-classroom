"""Content-word overlap: one tokenizer for the two deterministic word rules.

Two gates in this package compare authored prose by its *content* words, not by exact
containment: the answer-leak paraphrase scan (``generation.assert_no_answer_leak``) and the
rubric-to-checklist coverage rule (``rubrics.rubric_item_coverage_problems``). Both need the
same answer to "which words in this sentence carry meaning?", so the tokenizer lives here once
instead of being re-invented in each gate.

What it is deliberately not:

* it is not a lemmatizer. A short, fixed suffix strip folds the forms a lesson author actually
  writes (``simmered`` -> ``simmer``, ``steps`` -> ``step``), nothing more;
* it is not a parser. A spaced script is a bag of words; a CJK run is a bag of character
  bigrams (a Japanese phrase has no spaces to split on);
* it never decides a verdict. Each gate owns its own threshold and its own refusal text.

A paraphrase is never *proof* that a string is the answer. The leak scan treats overlap as a
refusal because a false refusal costs one repair pass, while a shipped key costs the check; the
coverage rule treats overlap as permission because it only fires on checks whose items a learner
ticks, and the validator still reads the lesson afterwards.
"""

from __future__ import annotations

import re

#: Function words carry no topic. They are excluded from both rules: "the water is at a gentle
#: simmer" and "the answer is ..." share ``the``/``is`` with almost any sentence, and a matcher
#: that counts them would flag every page and cover every rubric criterion.
CONTENT_STOPWORDS: frozenset[str] = frozenset(
    """
    a about above after again against all also am an and any are as at be because been before
    being below between both but by can cannot could did do does doing down during each either
    else every few for from further had has have having he her here hers herself him himself his
    how i if in into is it its itself just least less let like made make many may me might more
    most much must my myself neither no nor not now of off on once one only or other ought our
    ours ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up upon us very was
    we were what when where which while who whom why will with within would you your yours
    yourself yourselves
    this that these those
    """.split()
)

#: Letters only, any script: digits and punctuation are not words. ``[^\W\d_]`` keeps Unicode
#: letters (Japanese, accented Latin) and drops ``_`` and digits.
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

#: A clause boundary. Overlap at the *sentence* level, not the page level: "simmer" in one
#: sentence and "gentle" three sentences later is not a paraphrase of "gentle simmer".
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;:])\s+|\n+")

#: A CJK character. A run of these is one unspaced word; it is compared by bigram.
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")

_SUFFIXES = ("ing", "ed", "es", "s")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(str(text or "")))


def _stem(word: str) -> str:
    """Fold the inflections a lesson actually writes; leave anything else alone."""
    if len(word) > 5 and word.endswith("ly"):
        # "simmer gently" and "a gentle simmer" are the same instruction: the adverb and the
        # adjective share a stem, and the answer-leak scan has to see that.
        return word[:-2]
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    if len(word) > 5 and word.endswith("le"):
        return word[:-2]
    if len(word) > 4 and word.endswith("e"):
        return word[:-1]
    return word


def _cjk_keys(run: str) -> set[str]:
    if len(run) < 2:
        return set()
    return {run[index : index + 2] for index in range(len(run) - 1)}


def content_words(text: str) -> set[str]:
    """The content keys of ``text``: stems for spaced scripts, bigrams for CJK runs."""
    keys: set[str] = set()
    for raw in _WORD.findall(str(text or "").casefold()):
        if _CJK.search(raw):
            keys |= _cjk_keys(raw)
            continue
        if len(raw) < 3 or raw in CONTENT_STOPWORDS:
            continue
        keys.add(_stem(raw))
    return keys


def content_sequence(text: str) -> list[str]:
    """Content keys in reading order, for the sliding-window paraphrase test.

    Stopwords are dropped before the window is sized, so only the words that carry meaning take
    up window slots; grammar cannot separate a key's own words.
    """
    sequence: list[str] = []
    for raw in _WORD.findall(str(text or "").casefold()):
        if _CJK.search(raw):
            continue  # A paraphrase across an unspaced script is not something this fold can see.
        if len(raw) < 3 or raw in CONTENT_STOPWORDS:
            continue
        sequence.append(_stem(raw))
    return sequence


def paraphrases(
    secret: str,
    surfaces: list[str],
    *,
    threshold: float = 0.8,
) -> bool:
    """True when a clause of ``surfaces`` restates ``secret`` in another word order.

    The test is a token-set overlap inside a *local* window: a two-word secret must appear as an
    adjacent pair ("gentle simmer" is flagged by "simmer gently"), and a longer secret gets one
    filler word of slack. A page that happens to use "simmer" in one sentence and "gentle" in
    another is not a paraphrase, and neither is "point at the fridge and say cold" a paraphrase
    of "fridge is cold" — a restatement has to put the key's own words next to each other. A
    one-word secret, or a CJK secret, is left to the exact-containment scan: there is no
    word-order restatement of a single token to detect, and an unspaced script has no tokens.
    """
    if has_cjk(secret):
        return False
    wanted = content_words(secret)
    if len(wanted) < 2:
        return False
    slack = 0 if len(wanted) == 2 else 1
    for surface in surfaces:
        for clause in _CLAUSE_SPLIT.split(str(surface or "")):
            sequence = content_sequence(clause)
            window = min(len(sequence), len(wanted) + slack)
            if window < len(wanted):
                continue
            for start in range(0, len(sequence) - window + 1):
                found = set(sequence[start : start + window]) & wanted
                if len(found) / len(wanted) >= threshold:
                    return True
    return False
