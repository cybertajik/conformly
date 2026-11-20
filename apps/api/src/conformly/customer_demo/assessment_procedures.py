"""Synthetic Assessment Procedures for MVP-C Customer Demo."""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid5

from conformly.catalog_v2.digest import canonical_json
from conformly.customer_demo.fixture import DEMO_NAMESPACE

SYNTHETIC_PROCEDURE_VERSION = "1.0.0"
SYNTHETIC_PROCEDURE_DISCLAIMER = (
    "Synthetic demonstration assessment procedure only. "
    "Not an ISO or accredited certification audit procedure."
)

REQUIRED_CRITERIA: list[dict[str, Any]] = [
    {
        "id": "implementation",
        "title": "Control Implementation",
        "description": "Human confirms the synthetic control is implemented.",
        "sequence": 1,
    },
    {
        "id": "evidence",
        "title": "Evidence Inspection",
        "description": "Human inspects the selected exact evidence revisions.",
        "sequence": 2,
    },
    {
        "id": "operation",
        "title": "Operational Testing",
        "description": "Human records how operation was tested in this synthetic scenario.",
        "sequence": 3,
    },
]

REQUIRED_CRITERION_IDS = {c["id"] for c in REQUIRED_CRITERIA}


def compute_procedure_digest(
    procedure_id: UUID,
    version: str,
    control_version_id: UUID,
    disclaimer: str,
    criteria: list[dict[str, Any]],
) -> str:
    """Compute deterministic SHA-256 digest of procedure payload using canonical_json."""
    payload = {
        "control_version_id": str(control_version_id).lower(),
        "criteria": [
            {
                "description": c["description"],
                "id": c["id"],
                "sequence": c["sequence"],
                "title": c["title"],
            }
            for c in criteria
        ],
        "disclaimer": disclaimer,
        "id": str(procedure_id).lower(),
        "version": version,
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def get_procedure_for_control_version(control_version_id: UUID) -> dict[str, Any]:
    """Return synthetic assessment procedure for a specific demo control version."""
    cv_str = str(control_version_id).lower()
    proc_id = uuid5(DEMO_NAMESPACE, f"mvp-c-procedure:{cv_str}:v1")
    version = SYNTHETIC_PROCEDURE_VERSION
    disclaimer = SYNTHETIC_PROCEDURE_DISCLAIMER
    digest = compute_procedure_digest(
        proc_id,
        version,
        control_version_id,
        disclaimer,
        REQUIRED_CRITERIA,
    )
    return {
        "id": proc_id,
        "version": version,
        "digest": digest,
        "disclaimer": disclaimer,
        "control_version_id": control_version_id,
        "criteria": [dict(c) for c in REQUIRED_CRITERIA],
    }
