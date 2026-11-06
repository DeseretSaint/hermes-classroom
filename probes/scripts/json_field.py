#!/usr/bin/env python3
"""Print one top-level JSON field from a file: json_field.py <field> <path>."""
from __future__ import annotations

import json
import sys

try:
    print(json.load(open(sys.argv[2], encoding="utf-8")).get(sys.argv[1], ""))
except Exception:
    print("unreadable")
