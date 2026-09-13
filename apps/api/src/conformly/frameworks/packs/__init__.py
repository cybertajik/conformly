"""Modular definitions for Conformly compliance framework packs.

Tier A packs (6 total — all REQUIRED_BETA per Module A decision):
  1. ISO/IEC 27001:2022 ISMS Pre-Audit
  2. EU GDPR & German BDSG Privacy Operations
  3. NIST Cybersecurity Framework 2.0
  4. CIS Critical Security Controls v8 IG1
  5. Minimum Viable Secure Product v2.0
  6. ISO 9001:2015 Quality Management System (admitted per ADR D-059, 2026-09-13)
"""

from conformly.frameworks.packs.cis_controls_ig1 import CIS_CONTROLS_IG1_PACK
from conformly.frameworks.packs.gdpr_bdsg import GDPR_BDSG_PACK
from conformly.frameworks.packs.iso_9001 import ISO_9001_PACK
from conformly.frameworks.packs.iso_27001 import ISO_27001_PACK
from conformly.frameworks.packs.mvsp import MVSP_PACK
from conformly.frameworks.packs.nist_csf import NIST_CSF_PACK
from conformly.frameworks.packs.owner_decision_drafts import OWNER_DECISION_DRAFT_PACKS

TIER_A_PACKS = [
    ISO_27001_PACK,
    GDPR_BDSG_PACK,
    NIST_CSF_PACK,
    CIS_CONTROLS_IG1_PACK,
    MVSP_PACK,
    ISO_9001_PACK,
]

__all__ = [
    "TIER_A_PACKS",
    "ISO_27001_PACK",
    "GDPR_BDSG_PACK",
    "NIST_CSF_PACK",
    "CIS_CONTROLS_IG1_PACK",
    "MVSP_PACK",
    "ISO_9001_PACK",
    "OWNER_DECISION_DRAFT_PACKS",
]
