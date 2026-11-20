"""Pinned synthetic bundle, requirements, rules, facts and manifest for WP-09 customer demo."""

from __future__ import annotations

import copy
import hashlib
from typing import Any
from uuid import UUID, uuid5

from conformly.catalog_v2.digest import canonical_json
from conformly.catalog_v2.rule_static_validation import (
    FactVersionMetadata,
    validate_rule_ast,
)

# Fixed namespace UUID for WP-09 synthetic objects
DEMO_NAMESPACE = UUID("8574955f-5f63-4d37-926a-3c114c9041f3")

# Pack identities
PACK_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-customer-onboarding")
PACK_VERSION_V1_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-version-v1")
PACK_VERSION_V2_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-version-v2")

# Source identities
PUBLISHER_ID = uuid5(DEMO_NAMESPACE, "wp09-publisher-synthetic")
SOURCE_ID = uuid5(DEMO_NAMESPACE, "wp09-source-synthetic-baseline")
SOURCE_VERSION_ID = uuid5(DEMO_NAMESPACE, "wp09-source-version-v1")

# Fact definition and version identities
FACT_CLOUD_DEF_ID = uuid5(DEMO_NAMESPACE, "wp09-fact-def-uses-cloud")
FACT_CLOUD_V1_ID = uuid5(DEMO_NAMESPACE, "wp09-fact-ver-uses-cloud-v1")

FACT_REGION_DEF_ID = uuid5(DEMO_NAMESPACE, "wp09-fact-def-operating-region")
FACT_REGION_V1_ID = uuid5(DEMO_NAMESPACE, "wp09-fact-ver-operating-region-v1")

# Requirement identities
REQ_1_ID = uuid5(DEMO_NAMESPACE, "wp09-req-cloud-storage")
REQ_1_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-cloud-storage-v1")

REQ_2_ID = uuid5(DEMO_NAMESPACE, "wp09-req-eu-cloud-processing")
REQ_2_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-eu-cloud-processing-v1")

REQ_3_ID = uuid5(DEMO_NAMESPACE, "wp09-req-hybrid-fallbacks")
REQ_3_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-hybrid-fallbacks-v1")

# Common Control identities
CTRL_1_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-cloud-governance")
CTRL_1_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-cloud-governance-v1")

CTRL_2_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-regional-isolation")
CTRL_2_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-regional-isolation-v1")

CTRL_3_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-hybrid-containment")
CTRL_3_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-hybrid-containment-v1")

# Rule identities
RULE_1_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-uses-cloud")
RULE_1_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-uses-cloud-v1")

RULE_2_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-eu-cloud")
RULE_2_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-eu-cloud-v1")

RULE_3_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-hybrid-resilience")
RULE_3_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-hybrid-resilience-v1")

# Evaluator version identifier
EVALUATOR_VERSION: str = "wp09-synthetic-v1"

FACT_DEFINITIONS_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": str(FACT_CLOUD_DEF_ID),
        "version_id": str(FACT_CLOUD_V1_ID),
        "key": "synthetic_wp09_uses_cloud",
        "label": "Uses Cloud Infrastructure",
        "description": "Indicates whether the organization utilizes public or private cloud services.",
        "value_type": "boolean",
        "scope": "tenant",
    },
    {
        "id": str(FACT_REGION_DEF_ID),
        "version_id": str(FACT_REGION_V1_ID),
        "key": "synthetic_wp09_operating_region",
        "label": "Primary Operating Region",
        "description": "Primary geographical operational jurisdiction.",
        "value_type": "enum",
        "scope": "tenant",
        "enum_options": [
            {"code": "EU", "label": "European Union"},
            {"code": "OTHER", "label": "Other Jurisdictions"},
        ],
    },
]

# Bound and derived FactVersionMetadata from pinned fact definitions
FACT_METADATA: dict[UUID, FactVersionMetadata] = {
    UUID(f["version_id"]): FactVersionMetadata(
        fact_definition_id=UUID(f["id"]),
        value_type=f["value_type"],
        scope_types=frozenset({f["scope"]}),
        enum_codes=frozenset(
            f.get("enum_values", []) or [opt["code"] for opt in f.get("enum_options", [])]
        ),
    )
    for f in FACT_DEFINITIONS_PAYLOAD
}

# Rule AST 1: uses_cloud == True
AST_1: dict[str, Any] = {
    "ast_version": 1,
    "root": {
        "op": "EQUALS",
        "fact_definition_version_id": str(FACT_CLOUD_V1_ID),
        "scope_type": "tenant",
        "value": True,
    },
}

# Rule AST 2: uses_cloud == True AND operating_region == 'EU'
AST_2: dict[str, Any] = {
    "ast_version": 1,
    "root": {
        "op": "ALL",
        "children": [
            {
                "op": "EQUALS",
                "fact_definition_version_id": str(FACT_CLOUD_V1_ID),
                "scope_type": "tenant",
                "value": True,
            },
            {
                "op": "EQUALS",
                "fact_definition_version_id": str(FACT_REGION_V1_ID),
                "scope_type": "tenant",
                "value": "EU",
            },
        ],
    },
}

# Rule AST 3: NOT(uses_cloud == True) OR operating_region == 'OTHER'
AST_3: dict[str, Any] = {
    "ast_version": 1,
    "root": {
        "op": "ANY",
        "children": [
            {
                "op": "NOT",
                "child": {
                    "op": "EQUALS",
                    "fact_definition_version_id": str(FACT_CLOUD_V1_ID),
                    "scope_type": "tenant",
                    "value": True,
                },
            },
            {
                "op": "EQUALS",
                "fact_definition_version_id": str(FACT_REGION_V1_ID),
                "scope_type": "tenant",
                "value": "OTHER",
            },
        ],
    },
}

SOURCE_PROVENANCE_DISCLAIMER: str = "Synthetic demonstration source and control mappings for onboarding demonstration only. Not legal or regulatory text."

REQ_1_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_1_ID),
    "version_id": str(REQ_1_VER_ID),
    "identifier": "SYNTH-REQ-001",
    "title": "Synthetic Cloud Architecture Governance",
    "description": "Applies when organisation uses cloud infrastructure.",
    "rule_id": str(RULE_1_ID),
    "rule_version_id": str(RULE_1_VER_ID),
    "rule_ast": AST_1,
    "control_id": str(CTRL_1_ID),
    "control_version_id": str(CTRL_1_VER_ID),
    "control_identifier": "SYNTH-CTRL-001",
    "control_title": "Cloud Configuration & Access Baseline",
}

REQ_2_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_2_ID),
    "version_id": str(REQ_2_VER_ID),
    "identifier": "SYNTH-REQ-002",
    "title": "Synthetic EU Regional Data Isolation",
    "description": "Applies when organisation uses cloud infrastructure AND operates in EU region.",
    "rule_id": str(RULE_2_ID),
    "rule_version_id": str(RULE_2_VER_ID),
    "rule_ast": AST_2,
    "control_id": str(CTRL_2_ID),
    "control_version_id": str(CTRL_2_VER_ID),
    "control_identifier": "SYNTH-CTRL-002",
    "control_title": "Sovereign Boundary Encryption & Residency",
}

REQ_3_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_3_ID),
    "version_id": str(REQ_3_VER_ID),
    "identifier": "SYNTH-REQ-003",
    "title": "Synthetic Hybrid or Non-EU Resilience Rule",
    "description": "Applies when organisation does not use cloud or operates outside EU.",
    "rule_id": str(RULE_3_ID),
    "rule_version_id": str(RULE_3_VER_ID),
    "rule_ast": AST_3,
    "control_id": str(CTRL_3_ID),
    "control_version_id": str(CTRL_3_VER_ID),
    "control_identifier": "SYNTH-CTRL-003",
    "control_title": "Boundary Containment & Alternative Architecture",
}

# Fixed synthetic bundles with exact executable ASTs and fact definitions bound
BUNDLE_V1_PAYLOAD: dict[str, Any] = {
    "pack_id": str(PACK_ID),
    "pack_version_id": str(PACK_VERSION_V1_ID),
    "version": "1.0.0",
    "name": "Synthetic Customer Baseline Pack",
    "description": "Synthetic customer onboarding baseline requirements and rules (demonstration only, non-legal)",
    "publisher_id": str(PUBLISHER_ID),
    "source_id": str(SOURCE_ID),
    "source_version_id": str(SOURCE_VERSION_ID),
    "source_provenance_disclaimer": SOURCE_PROVENANCE_DISCLAIMER,
    "fact_definitions": FACT_DEFINITIONS_PAYLOAD,
    "requirements": [
        REQ_1_PAYLOAD,
        REQ_2_PAYLOAD,
    ],
}

BUNDLE_V2_PAYLOAD: dict[str, Any] = {
    "pack_id": str(PACK_ID),
    "pack_version_id": str(PACK_VERSION_V2_ID),
    "version": "2.0.0",
    "name": "Synthetic Customer Extended Pack",
    "description": "Synthetic customer onboarding extended requirements and rules (demonstration only, non-legal)",
    "publisher_id": str(PUBLISHER_ID),
    "source_id": str(SOURCE_ID),
    "source_version_id": str(SOURCE_VERSION_ID),
    "source_provenance_disclaimer": SOURCE_PROVENANCE_DISCLAIMER,
    "fact_definitions": FACT_DEFINITIONS_PAYLOAD,
    "requirements": [
        REQ_1_PAYLOAD,
        REQ_2_PAYLOAD,
        REQ_3_PAYLOAD,
    ],
}

# Canonical digests pinned in code
BUNDLE_V1_DIGEST: str = "acc8f821be6ae61ece7961683af39c343d14854d8092494ac6410eb33d14e197"
BUNDLE_V2_DIGEST: str = "8b2273b87ba78008ea5d4f0032fcbfc531711c1770d70e6da98e837fd6a0e0cb"

# -----------------------------------------------------------------------------
# Pack 2: Synthetic Service Resilience Pack (invented demonstration pack)
# -----------------------------------------------------------------------------

PACK_2_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-service-resilience")
PACK_2_VERSION_V1_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-resilience-version-v1")
PACK_2_VERSION_V2_ID = uuid5(DEMO_NAMESPACE, "wp09-pack-resilience-version-v2")

SOURCE_2_ID = uuid5(DEMO_NAMESPACE, "wp09-source-synthetic-resilience")
SOURCE_2_VERSION_V1_ID = uuid5(DEMO_NAMESPACE, "wp09-source-resilience-version-v1")
SOURCE_2_VERSION_V2_ID = uuid5(DEMO_NAMESPACE, "wp09-source-resilience-version-v2")

SOURCE_2_PROVENANCE_DISCLAIMER: str = (
    "Synthetic service resilience demonstration source and control mappings for "
    "onboarding demonstration only. Not legal or regulatory text."
)

# Controls for Pack 2
# CTRL_1_ID / CTRL_1_VER_ID is SHARED with Pack 1 ("Cloud Configuration & Access Baseline")
CTRL_4_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-resilience-failover")
CTRL_4_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-resilience-failover-v1")

CTRL_5_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-backup-integrity")
CTRL_5_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-backup-integrity-v1")

CTRL_6_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-capacity-monitoring")
CTRL_6_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-ctrl-version-capacity-monitoring-v1")

# Rules for Pack 2
RULE_4_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-resilience-failover")
RULE_4_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-resilience-failover-v1")

RULE_5_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-backup-dr")
RULE_5_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-backup-dr-v1")

RULE_6_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-capacity-scale")
RULE_6_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-rule-version-capacity-scale-v1")

# Requirements for Pack 2
REQ_4_ID = uuid5(DEMO_NAMESPACE, "wp09-req-resilience-cloud-governance")
REQ_4_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-resilience-cloud-governance-v1")

REQ_5_ID = uuid5(DEMO_NAMESPACE, "wp09-req-failover-redundancy")
REQ_5_VER_1_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-failover-redundancy-v1")
REQ_5_VER_2_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-failover-redundancy-v2")

REQ_7_ID = uuid5(DEMO_NAMESPACE, "wp09-req-legacy-backup-dr")
REQ_7_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-legacy-backup-dr-v1")

REQ_6_ID = uuid5(DEMO_NAMESPACE, "wp09-req-continuous-capacity")
REQ_6_VER_ID = uuid5(DEMO_NAMESPACE, "wp09-req-version-continuous-capacity-v1")

REQ_4_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_4_ID),
    "version_id": str(REQ_4_VER_ID),
    "identifier": "SYNTH-RES-001",
    "title": "Synthetic Resilience Cloud Baseline",
    "description": "Requires verified cloud governance baseline for service resilience.",
    "rule_id": str(RULE_6_ID),
    "rule_version_id": str(RULE_6_VER_ID),
    "rule_ast": AST_1,
    "control_id": str(CTRL_1_ID),
    "control_version_id": str(CTRL_1_VER_ID),
    "control_identifier": "SYNTH-CTRL-001",
    "control_title": "Cloud Configuration & Access Baseline",
}

REQ_5_V1_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_5_ID),
    "version_id": str(REQ_5_VER_1_ID),
    "identifier": "SYNTH-RES-002",
    "title": "Synthetic Regional Failover Strategy",
    "description": "Requires automated service failover across regional zones.",
    "rule_id": str(RULE_4_ID),
    "rule_version_id": str(RULE_4_VER_ID),
    "rule_ast": AST_2,
    "control_id": str(CTRL_4_ID),
    "control_version_id": str(CTRL_4_VER_ID),
    "control_identifier": "SYNTH-CTRL-004",
    "control_title": "Automated Service Failover & Redundancy",
}

REQ_5_V2_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_5_ID),
    "version_id": str(REQ_5_VER_2_ID),
    "identifier": "SYNTH-RES-002",
    "title": "Synthetic Multi-Region Failover Architecture",
    "description": "Updated resilience requirement for active-active redundancy.",
    "rule_id": str(RULE_4_ID),
    "rule_version_id": str(RULE_4_VER_ID),
    "rule_ast": AST_2,
    "control_id": str(CTRL_4_ID),
    "control_version_id": str(CTRL_4_VER_ID),
    "control_identifier": "SYNTH-CTRL-004",
    "control_title": "Automated Service Failover & Redundancy",
}

REQ_7_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_7_ID),
    "version_id": str(REQ_7_VER_ID),
    "identifier": "SYNTH-RES-003",
    "title": "Synthetic Legacy Disaster Recovery Standard",
    "description": "Requires periodic backup snapshots and off-site containment.",
    "rule_id": str(RULE_5_ID),
    "rule_version_id": str(RULE_5_VER_ID),
    "rule_ast": AST_3,
    "control_id": str(CTRL_5_ID),
    "control_version_id": str(CTRL_5_VER_ID),
    "control_identifier": "SYNTH-CTRL-005",
    "control_title": "Immutable Backup & Restoration Assurance",
}

REQ_6_PAYLOAD: dict[str, Any] = {
    "id": str(REQ_6_ID),
    "version_id": str(REQ_6_VER_ID),
    "identifier": "SYNTH-RES-004",
    "title": "Synthetic Continuous Capacity & Monitoring",
    "description": "Requires automated load shedding and capacity containment.",
    "rule_id": str(RULE_6_ID),
    "rule_version_id": str(RULE_6_VER_ID),
    "rule_ast": AST_1,
    "control_id": str(CTRL_6_ID),
    "control_version_id": str(CTRL_6_VER_ID),
    "control_identifier": "SYNTH-CTRL-006",
    "control_title": "Continuous Capacity & Degradation Containment",
}

BUNDLE_2_V1_PAYLOAD: dict[str, Any] = {
    "pack_id": str(PACK_2_ID),
    "pack_version_id": str(PACK_2_VERSION_V1_ID),
    "version": "1.0.0",
    "name": "Synthetic Service Resilience Baseline Pack",
    "description": "Synthetic service resilience baseline requirements and rules (demonstration only, non-legal)",
    "publisher_id": str(PUBLISHER_ID),
    "source_id": str(SOURCE_2_ID),
    "source_version_id": str(SOURCE_2_VERSION_V1_ID),
    "source_provenance_disclaimer": SOURCE_2_PROVENANCE_DISCLAIMER,
    "fact_definitions": FACT_DEFINITIONS_PAYLOAD,
    "requirements": [
        REQ_4_PAYLOAD,
        REQ_5_V1_PAYLOAD,
        REQ_7_PAYLOAD,
    ],
}

BUNDLE_2_V2_PAYLOAD: dict[str, Any] = {
    "pack_id": str(PACK_2_ID),
    "pack_version_id": str(PACK_2_VERSION_V2_ID),
    "version": "2.0.0",
    "name": "Synthetic Service Resilience Extended Pack",
    "description": "Synthetic service resilience extended requirements and rules (demonstration only, non-legal)",
    "publisher_id": str(PUBLISHER_ID),
    "source_id": str(SOURCE_2_ID),
    "source_version_id": str(SOURCE_2_VERSION_V2_ID),
    "source_provenance_disclaimer": SOURCE_2_PROVENANCE_DISCLAIMER,
    "fact_definitions": FACT_DEFINITIONS_PAYLOAD,
    "requirements": [
        REQ_4_PAYLOAD,
        REQ_5_V2_PAYLOAD,
        REQ_6_PAYLOAD,
    ],
}

BUNDLE_2_V1_DIGEST: str = "9e348609c13459281ab8f9d9e8aac7bafa8f1510ffaf9949d07b38cab9cf38b4"
BUNDLE_2_V2_DIGEST: str = "ee82e0b3717ed2d7a25983dc0bc8985fa560efe89dc7b42f22893287c1dee5f4"

# Finite registry sets
REGISTERED_PACK_VERSIONS: frozenset[UUID] = frozenset({
    PACK_VERSION_V1_ID,
    PACK_VERSION_V2_ID,
    PACK_2_VERSION_V1_ID,
    PACK_2_VERSION_V2_ID,
})

REGISTERED_PACK_IDS: frozenset[UUID] = frozenset({
    PACK_ID,
    PACK_2_ID,
})

# Mapping from requirement version ID to (rule_version_id, AST)
RULE_MAP: dict[UUID, tuple[UUID, dict[str, Any]]] = {
    REQ_1_VER_ID: (RULE_1_VER_ID, AST_1),
    REQ_2_VER_ID: (RULE_2_VER_ID, AST_2),
    REQ_3_VER_ID: (RULE_3_VER_ID, AST_3),
    REQ_4_VER_ID: (RULE_6_VER_ID, AST_1),
    REQ_5_VER_1_ID: (RULE_4_VER_ID, AST_2),
    REQ_5_VER_2_ID: (RULE_4_VER_ID, AST_2),
    REQ_7_VER_ID: (RULE_5_VER_ID, AST_3),
    REQ_6_VER_ID: (RULE_6_VER_ID, AST_1),
}


def is_registered_pack_version(pack_version_id: UUID) -> bool:
    """Return True if pack version UUID exists in finite registry."""
    return pack_version_id in REGISTERED_PACK_VERSIONS


def _verify_fixtures() -> None:
    # 1. Verify ASTs statically against FactVersionMetadata
    validate_rule_ast(canonical_json(AST_1).encode("utf-8"), FACT_METADATA, [FACT_CLOUD_V1_ID])
    validate_rule_ast(
        canonical_json(AST_2).encode("utf-8"), FACT_METADATA, [FACT_CLOUD_V1_ID, FACT_REGION_V1_ID]
    )
    validate_rule_ast(
        canonical_json(AST_3).encode("utf-8"), FACT_METADATA, [FACT_CLOUD_V1_ID, FACT_REGION_V1_ID]
    )

    # 2. Verify complete linkage across all registered bundles
    all_reqs = (
        BUNDLE_V1_PAYLOAD["requirements"]
        + [REQ_3_PAYLOAD]
        + BUNDLE_2_V1_PAYLOAD["requirements"]
        + [REQ_5_V2_PAYLOAD, REQ_6_PAYLOAD]
    )
    for req in all_reqs:
        r_vid = UUID(req["version_id"])
        if r_vid not in RULE_MAP:
            raise RuntimeError(f"Missing rule map for requirement version {r_vid}")
        mapped_rule_vid, mapped_ast = RULE_MAP[r_vid]
        if str(mapped_rule_vid) != req["rule_version_id"]:
            raise RuntimeError(f"Rule version mismatch in fixture linkage for {r_vid}")
        if req["rule_ast"] != mapped_ast:
            raise RuntimeError(f"Rule AST mismatch in fixture linkage for {r_vid}")

    # 3. Verify bundle digests
    d1 = hashlib.sha256(canonical_json(BUNDLE_V1_PAYLOAD).encode("utf-8")).hexdigest()
    d2 = hashlib.sha256(canonical_json(BUNDLE_V2_PAYLOAD).encode("utf-8")).hexdigest()
    d2_1 = hashlib.sha256(canonical_json(BUNDLE_2_V1_PAYLOAD).encode("utf-8")).hexdigest()
    d2_2 = hashlib.sha256(canonical_json(BUNDLE_2_V2_PAYLOAD).encode("utf-8")).hexdigest()

    if d1 != BUNDLE_V1_DIGEST or d2 != BUNDLE_V2_DIGEST:
        raise RuntimeError("Customer demo fixture digests corrupted for Pack 1")
    if d2_1 != BUNDLE_2_V1_DIGEST or d2_2 != BUNDLE_2_V2_DIGEST:
        raise RuntimeError("Customer demo fixture digests corrupted for Pack 2")


_verify_fixtures()


def get_bundle_by_version_id(pack_version_id: UUID) -> dict[str, Any]:
    """Retrieve deep-copied bundle definition by pack version UUID."""
    if pack_version_id == PACK_VERSION_V1_ID:
        return copy.deepcopy(BUNDLE_V1_PAYLOAD)
    if pack_version_id == PACK_VERSION_V2_ID:
        return copy.deepcopy(BUNDLE_V2_PAYLOAD)
    if pack_version_id == PACK_2_VERSION_V1_ID:
        return copy.deepcopy(BUNDLE_2_V1_PAYLOAD)
    if pack_version_id == PACK_2_VERSION_V2_ID:
        return copy.deepcopy(BUNDLE_2_V2_PAYLOAD)
    raise ValueError(f"Unknown customer demo pack version ID: {pack_version_id}")


def get_bundle_digest(pack_version_id: UUID) -> str:
    """Retrieve canonical bundle digest by pack version UUID."""
    if pack_version_id == PACK_VERSION_V1_ID:
        return BUNDLE_V1_DIGEST
    if pack_version_id == PACK_VERSION_V2_ID:
        return BUNDLE_V2_DIGEST
    if pack_version_id == PACK_2_VERSION_V1_ID:
        return BUNDLE_2_V1_DIGEST
    if pack_version_id == PACK_2_VERSION_V2_ID:
        return BUNDLE_2_V2_DIGEST
    raise ValueError(f"Unknown customer demo pack version ID: {pack_version_id}")


def get_demo_manifest() -> dict[str, Any]:
    """Return fixed customer demo manifest with deep-copied metadata, packs, facts and disclaimers."""
    manifest = {
        "disclaimer": "This onboarding journey uses synthetic demonstration frameworks and controls for onboarding demonstration only. Not legal or compliance advice.",
        "source_provenance_disclaimer": SOURCE_PROVENANCE_DISCLAIMER,
        "evaluator_version": EVALUATOR_VERSION,
        "companies": [
            {"code": "ALPHA", "display_name": "Fictional Alpha (Cloud-First)"},
            {"code": "BETA", "display_name": "Fictional Beta (Hybrid/Regional)"},
        ],
        "fact_definitions": FACT_DEFINITIONS_PAYLOAD,
        "packs": [
            {
                "pack_id": str(PACK_ID),
                "pack_version_id": str(PACK_VERSION_V1_ID),
                "version": "1.0.0",
                "name": BUNDLE_V1_PAYLOAD["name"],
                "description": BUNDLE_V1_PAYLOAD["description"],
                "bundle_digest": BUNDLE_V1_DIGEST,
                "requirement_count": len(BUNDLE_V1_PAYLOAD["requirements"]),
                "requirements": BUNDLE_V1_PAYLOAD["requirements"],
            },
            {
                "pack_id": str(PACK_ID),
                "pack_version_id": str(PACK_VERSION_V2_ID),
                "version": "2.0.0",
                "name": BUNDLE_V2_PAYLOAD["name"],
                "description": BUNDLE_V2_PAYLOAD["description"],
                "bundle_digest": BUNDLE_V2_DIGEST,
                "requirement_count": len(BUNDLE_V2_PAYLOAD["requirements"]),
                "requirements": BUNDLE_V2_PAYLOAD["requirements"],
            },
            {
                "pack_id": str(PACK_2_ID),
                "pack_version_id": str(PACK_2_VERSION_V1_ID),
                "version": "1.0.0",
                "name": BUNDLE_2_V1_PAYLOAD["name"],
                "description": BUNDLE_2_V1_PAYLOAD["description"],
                "bundle_digest": BUNDLE_2_V1_DIGEST,
                "requirement_count": len(BUNDLE_2_V1_PAYLOAD["requirements"]),
                "requirements": BUNDLE_2_V1_PAYLOAD["requirements"],
            },
            {
                "pack_id": str(PACK_2_ID),
                "pack_version_id": str(PACK_2_VERSION_V2_ID),
                "version": "2.0.0",
                "name": BUNDLE_2_V2_PAYLOAD["name"],
                "description": BUNDLE_2_V2_PAYLOAD["description"],
                "bundle_digest": BUNDLE_2_V2_DIGEST,
                "requirement_count": len(BUNDLE_2_V2_PAYLOAD["requirements"]),
                "requirements": BUNDLE_2_V2_PAYLOAD["requirements"],
            },
        ],
    }
    return copy.deepcopy(manifest)
