"""Helper utilities to read and query the canonical Module A Beta Release Manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"
_CACHED_MANIFEST: dict[str, Any] | None = None


def get_release_manifest() -> dict[str, Any]:
    """Load and return the parsed Module A Beta Release Manifest."""
    global _CACHED_MANIFEST
    if _CACHED_MANIFEST is None:
        if _MANIFEST_PATH.exists():
            with open(_MANIFEST_PATH, encoding="utf-8") as f:
                _CACHED_MANIFEST = json.load(f)
        else:
            _CACHED_MANIFEST = {"packs": []}
    return _CACHED_MANIFEST


def get_all_pack_manifests() -> list[dict[str, Any]]:
    """Retrieve all pack entries from the release manifest."""
    return list(get_release_manifest().get("packs", []))


def get_required_beta_pack_ids() -> list[str]:
    """Retrieve pack IDs of all packs flagged as REQUIRED for beta inclusion."""
    return [
        p["pack_id"]
        for p in get_all_pack_manifests()
        if p.get("required_for_beta_status") in ("REQUIRED_BETA", "REQUIRED")
        or p.get("beta_inclusion") == "REQUIRED"
    ]


def get_pack_manifest_by_id(pack_id: str) -> dict[str, Any] | None:
    """Retrieve the manifest pack record matching a given pack_id or framework slug."""
    manifest = get_release_manifest()
    clean_id = pack_id.strip().lower()
    for pack in manifest.get("packs", []):
        if pack.get("pack_id", "").lower() == clean_id:
            return cast(dict[str, Any], pack)
    return None
