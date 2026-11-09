"""Shared HTTP RPC helpers for the H-210-R2 pack round-trip evidence run (merged tree df052ea)."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRATCH = Path("/home/deseretsaint/.hermes/profiles/lattice/cache/scratch/h210r2")
ROOT = Path("/home/deseretsaint/Projects/hermes-classroom/.worktrees/t_a7761dfc")


class Client:
    def __init__(self, base: str, token: str) -> None:
        self.base = base
        self.token = token
        self._wire = 0

    def http(self, method: str, path: str, body: dict | None = None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def fetch(self, path: str):
        """Raw GET of a download handle: (status, content-type, bytes)."""
        request = urllib.request.Request(
            f"{self.base}{path}",
            headers={"Authorization": f"Bearer {self.token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.headers.get("Content-Type"), response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type"), exc.read()

    def wire_version(self) -> int:
        status, runtime = self.http("GET", "/api/plugins/coursebook/runtime?profile=")
        self._wire = int((runtime or {}).get("wire_version") or 0)
        return self._wire

    def rpc(self, method: str, payload: dict, *, idempotency_key: str | None = None,
            expected_revision: int | None = None) -> dict:
        body = {
            "contract": "cb.rpc",
            "contract_version": self._wire,
            "method": method,
            "operation_id": f"h210r2-{method.replace('.', '-')}-{time.time_ns()}",
            "payload": payload,
        }
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        if expected_revision is not None:
            body["expected_revision"] = expected_revision
        status, response = self.http("POST", "/api/plugins/coursebook/rpc?profile=", body)
        return {"http": status, **response}


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def page_report(client: Client, enrollment_id: str) -> dict:
    """Read every lesson page through the contract and count teaching/media/check segments."""
    outline = client.rpc("course.outline", {"enrollment_id": enrollment_id})
    objectives = (outline.get("result") or {}).get("objectives") or []
    pages = []
    totals = {"teaching": 0, "media": 0, "check_prompt": 0}
    media_segments = []
    for objective in objectives:
        page = client.rpc(
            "lesson.page",
            {"enrollment_id": enrollment_id, "objective_id": objective["objective_id"]},
        )
        result = page.get("result") or {}
        segments = result.get("segments") or []
        kinds = {}
        for segment in segments:
            kind = str(segment.get("kind"))
            kinds[kind] = kinds.get(kind, 0) + 1
            if kind in totals:
                totals[kind] += 1
            if kind == "media":
                media_segments.append({
                    "objective_id": objective["objective_id"],
                    "artifact_id": segment.get("artifact_id"),
                    "path": segment.get("path") or segment.get("media_path"),
                    "caption": segment.get("caption"),
                    "segment_id": segment.get("segment_id") or segment.get("id"),
                })
        pages.append({
            "objective_id": objective["objective_id"],
            "title": objective.get("title"),
            "segments": len(segments),
            "kinds": kinds,
            "ok": page.get("ok"),
            "error": (page.get("error") or {}).get("code"),
        })
    return {
        "outline_total": (outline.get("result") or {}).get("total"),
        "objectives": len(objectives),
        "segment_totals": totals,
        "media_segments": media_segments,
        "media_artifact_ids": [item["artifact_id"] for item in media_segments if item.get("artifact_id")],
        "pages": pages,
    }
