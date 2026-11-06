#!/usr/bin/env python3
"""Summarise the Sentinel perf runs into one comparison table."""
import json
from pathlib import Path

BASE = Path("docs/sentinel-perf/results")


def load(name):
    path = BASE / name
    return json.loads(path.read_text()) if path.exists() else {"rows": []}


def rows_of(name):
    return {row["id"]: row for row in load(name)["rows"]}


legal = rows_of("raw-legal.json")
baseline = rows_of("raw-baseline.json")
extras_legal = rows_of("extras-legal.json")
extras_over = rows_of("extras-overcap.json")
scroll = rows_of("scroll-index.json")

IDLE = extras_legal["idle-cadence"]["medianFrameMs"]
DROPPED_MS = round(IDLE * 2, 1)


def line(label, left, right):
    print(f"| {label} | {left} | {right} |")


print(f"idle cadence: {IDLE} ms ({extras_legal['idle-cadence']['impliedHz']} Hz); "
      f"dropped-frame threshold = 2x cadence = {DROPPED_MS} ms\n")
print("| metric | baseline (3 obj, short) | long (60 obj, 3,565-word lessons) |")
print("|---|---|---|")
line("cold mount: first-contentful-paint",
     baseline["cold-mount"]["firstContentfulPaintMs"], legal["cold-mount"]["firstContentfulPaintMs"])
line("cold mount: route + rows visible",
     baseline["cold-mount"]["mountMs"], legal["cold-mount"]["mountMs"])
line("course detail render (ms)",
     baseline["course-detail"]["renderMs"], legal["course-detail"]["renderMs"])
line("course detail DOM nodes",
     baseline["course-detail"]["nodes"], legal["course-detail"]["nodes"])
line("textbook index rows", baseline["textbook-index"]["sectionRows"], legal["textbook-index"]["sectionRows"])
line("textbook index DOM nodes", baseline["textbook-index"]["nodes"], legal["textbook-index"]["nodes"])
line("long lesson full render (ms)",
     baseline["lesson-long"]["fullRenderMs"], legal["lesson-long"]["fullRenderMs"])
line("long lesson DOM nodes", baseline["lesson-long"]["nodes"], legal["lesson-long"]["nodes"])
line("long lesson text chars", baseline["lesson-long"]["textChars"], legal["lesson-long"]["textChars"])
line("last objective render (ms)",
     baseline["lesson-last"]["renderMs"], legal["lesson-last"]["renderMs"])
line("rapid nav median content (ms)",
     baseline["rapid-nav"]["medianContentMs"], legal["rapid-nav"]["medianContentMs"])
line("rapid nav p95 content (ms)",
     baseline["rapid-nav"]["p95ContentMs"], legal["rapid-nav"]["p95ContentMs"])
line("rapid nav worst (ms)",
     baseline["rapid-nav"]["worstContentMs"], legal["rapid-nav"]["worstContentMs"])
line("rapid nav frames > 32 ms",
     baseline["rapid-nav"]["over32ms"], legal["rapid-nav"]["over32ms"])
line("rapid nav worst frame (ms)",
     baseline["rapid-nav"]["worstFrameMs"], legal["rapid-nav"]["worstFrameMs"])
line("long lesson scroll worst frame (ms)",
     baseline["scroll-long"]["worstFrameMs"], legal["scroll-long"]["worstFrameMs"])
line("200% text overflow px",
     baseline["text200"]["overflowX"], legal["text200"]["overflowX"])
line("200% text clipped nodes",
     baseline["text200"]["clippedNodes"], legal["text200"]["clippedNodes"])
line("460px overflow px",
     baseline["narrow460"]["overflowX"], legal["narrow460"]["overflowX"])

print("\nlong tasks per step (legal):")
for key in ("course-detail-longtasks", "textbook-index-longtasks", "lesson-long-longtasks",
            "scroll-long-longtasks", "lesson-last-longtasks", "rapid-nav-longtasks"):
    row = legal.get(key, {})
    print(f"- {key}: count={row.get('longTaskCount')} max={row.get('longTaskMaxMs')} ms")

print("\nindex scroll:", json.dumps(scroll.get("scroll-textbook-index-60", {}), indent=2))
print("\nleak:", json.dumps({k: extras_legal.get("leak-repeat-nav", {}).get(k)
                           for k in ("growthMb", "peakMb", "growthPerCycleMb")}, indent=2))
print("leak series:", [s["usedMb"] for s in extras_legal.get("leak-repeat-nav", {}).get("series", [])])
print("\novercap UI:", json.dumps({k: extras_over.get("overcap-ui", {}).get(k)
                                 for k in ("pres", "hasRetry", "shot")}, indent=2))
