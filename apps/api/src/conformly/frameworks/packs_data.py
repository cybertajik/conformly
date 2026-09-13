"""Authoritative definitions for Tier A initial compliance framework packs.

Includes complete requirements, controls, implementation guidance, evidence requests,
and applicability criteria for:
1. ISO/IEC 27001:2022 ISMS Pre-Audit Readiness (iso-27001 v2022)
2. EU GDPR & German BDSG Privacy Operations (gdpr-bdsg v2024)
3. NIST Cybersecurity Framework 2.0 (nist-csf v2.0)
4. CIS Critical Security Controls v8 IG1 (cis-controls-ig1 v8.0)
5. Minimum Viable Secure Product v2.0 (mvsp v2.0)
6. ISO 9001:2015 Quality Management System (iso-9001 v2015) — admitted per ADR D-059, 2026-09-13
"""

from conformly.frameworks.packs import (
    CIS_CONTROLS_IG1_PACK,
    GDPR_BDSG_PACK,
    ISO_9001_PACK,
    ISO_27001_PACK,
    MVSP_PACK,
    NIST_CSF_PACK,
    OWNER_DECISION_DRAFT_PACKS,
    TIER_A_PACKS,
)
from conformly.frameworks.packs.types import (
    FrameworkPackDefinition,
    PackControlDefinition,
    PackCoverageDefinition,
    PackEvidenceDefinition,
    PackMappingDefinition,
    PackSourceRequirementDefinition,
)

TIER_A_FRAMEWORK_PACKS: list[FrameworkPackDefinition] = TIER_A_PACKS

__all__ = [
    "PackControlDefinition",
    "PackSourceRequirementDefinition",
    "PackMappingDefinition",
    "PackEvidenceDefinition",
    "PackCoverageDefinition",
    "FrameworkPackDefinition",
    "TIER_A_FRAMEWORK_PACKS",
    "ISO_27001_PACK",
    "GDPR_BDSG_PACK",
    "NIST_CSF_PACK",
    "CIS_CONTROLS_IG1_PACK",
    "MVSP_PACK",
    "ISO_9001_PACK",
    "OWNER_DECISION_DRAFT_PACKS",
]
