"""Coursebook agent-half package (skeleton).

The backend's authority chain is:

    contracts/*.json  ->  coursebook.contracts  ->  coursebook.api / db / jobs / packs

Contract files are the single authority for enums, payload shapes and error codes. Nothing in
this package may redeclare them: read them through :mod:`coursebook.contracts`.

Phase boundary: this package currently contains the frozen seams only. Feature bodies are
implemented by the owning specialist named in ``docs/WORK_PACKAGES.md``.
"""

from __future__ import annotations

__all__ = ["api", "contracts", "db", "hooks", "jobs", "packs"]

__version__ = "0.1.0"

#: Name used for ``plugins.plugin_storage.plugin_db()`` and the plugin-data directory.
PACKAGE_ID = "coursebook"
