"""Authoritative definitions for Tier A compliance framework packs.

Includes complete requirements, controls, implementation guidance, evidence requests,
and applicability criteria for:
1. ISO/IEC 27001:2022 ISMS Pre-Audit Readiness (iso-27001 v2022)
2. EU GDPR & German BDSG Privacy Operations (gdpr-bdsg v2024)
3. NIST Cybersecurity Framework 2.0 (nist-csf v2.0)
4. CIS Critical Security Controls v8 IG1 (cis-controls-ig1 v8.0)
5. Minimum Viable Secure Product v2.0 (mvsp v2.0)
6. ISO 9001:2015 Quality Management System (iso-9001 v2015) — admitted per ADR D-059
7. California Consumer Privacy Act & CPRA (us-ca-ccpa-cpra v2023) — admitted per ADR D-060
8. Saudi Arabia Personal Data Protection Law (sa-pdpl v2023) — admitted per ADR D-060
9. Japan Act on the Protection of Personal Information (jp-appi v2022) — admitted per ADR D-060
10. Australia Privacy Act 1988 & APPs (au-privacy-act v1988) — admitted per ADR D-060
11. CISA Cross-Sector Cybersecurity Performance Goals (cisa-cpg v1.0.1) — admitted per ADR D-061
12. Australian Essential Eight Maturity Level 1 (au-essential-eight-l1 v2023) — admitted per ADR D-061
13. UK GDPR & Data Protection Act 2018 (uk-gdpr-dpa v2021) — admitted per ADR D-061
14. Swiss Federal Act on Data Protection nFADP (ch-fadp v2023) — admitted per ADR D-061
15. UAE Personal Data Protection Law (ae-pdpl v2021) — admitted per ADR D-062
16. Oman Personal Data Protection Law (om-pdpl v2022) — admitted per ADR D-062
17. Jordan Personal Data Protection Law (jo-pdpl v2023) — admitted per ADR D-062
18. Morocco Personal Data Protection Law 09-08 (ma-cndp-0908 v2009) — admitted per ADR D-062
19. Virginia Consumer Data Protection Act (us-va-vcdpa v2023) — admitted per ADR D-063
20. Colorado Privacy Act (us-co-cpa v2023) — admitted per ADR D-063
21. Connecticut Data Privacy Act (us-ct-ctdpa v2023) — admitted per ADR D-063
22. Texas Data Privacy and Security Act (us-tx-tdpsa v2024) — admitted per ADR D-063
23. Utah Consumer Privacy Act (us-ut-ucpa v2023) — admitted per ADR D-063
24. France Data Protection Act (fr-cnil-gdpr v2019) — admitted per ADR D-064
25. Spain Data Protection Act LOPDGDD (es-aepd-lopdgdd v2018) — admitted per ADR D-064
26. Italy Personal Data Protection Code (it-garante-privacy v2018) — admitted per ADR D-064
27. Netherlands GDPR Implementation Act UAVG (nl-ap-uavg v2018) — admitted per ADR D-064
28. Ireland Data Protection Act 2018 (ie-dpc-dpa v2018) — admitted per ADR D-064
29. Austria Data Protection Act DSG (at-dsb-dsg v2018) — admitted per ADR D-064
30. Poland Personal Data Protection Act UODO/RODO (pl-uodo-rodo v2018) — admitted per ADR D-064
"""

from conformly.frameworks.packs import (
    AE_PDPL_PACK,
    AT_DSB_DSG_PACK,
    AU_ESSENTIAL_EIGHT_L1_PACK,
    AU_PRIVACY_ACT_PACK,
    CH_FADP_PACK,
    CIS_CONTROLS_IG1_PACK,
    CISA_CPG_PACK,
    ES_AEPD_LOPDGDD_PACK,
    FR_CNIL_GDPR_PACK,
    GDPR_BDSG_PACK,
    IE_DPC_DPA_PACK,
    ISO_9001_PACK,
    ISO_20000_1_PACK,
    ISO_22301_PACK,
    ISO_27001_PACK,
    ISO_27017_PACK,
    ISO_27018_PACK,
    ISO_27701_PACK,
    IT_GARANTE_PRIVACY_PACK,
    JO_PDPL_PACK,
    JP_APPI_PACK,
    MA_CNDP_0908_PACK,
    MODULE_B_DRAFT_PACKS,
    MODULE_B_PACKS,
    MVSP_PACK,
    NIST_CSF_PACK,
    NL_AP_UAVG_PACK,
    OM_PDPL_PACK,
    OWNER_DECISION_DRAFT_PACKS,
    PL_UODO_RODO_PACK,
    SA_PDPL_PACK,
    SOC_1_PACK,
    SOC_2_PACK,
    SOC_3_PACK,
    TIER_A_PACKS,
    UK_GDPR_DPA_PACK,
    US_CA_CCPA_CPRA_PACK,
    US_CO_CPA_PACK,
    US_CT_CTDPA_PACK,
    US_TX_TDPSA_PACK,
    US_UT_UCPA_PACK,
    US_VA_VCDPA_PACK,
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
MODULE_B_FRAMEWORK_PACKS: list[FrameworkPackDefinition] = MODULE_B_PACKS

__all__ = [
    "PackControlDefinition",
    "PackSourceRequirementDefinition",
    "PackMappingDefinition",
    "PackEvidenceDefinition",
    "PackCoverageDefinition",
    "FrameworkPackDefinition",
    "TIER_A_FRAMEWORK_PACKS",
    "MODULE_B_FRAMEWORK_PACKS",
    "MODULE_B_PACKS",
    "MODULE_B_DRAFT_PACKS",
    "ISO_27001_PACK",
    "GDPR_BDSG_PACK",
    "NIST_CSF_PACK",
    "CIS_CONTROLS_IG1_PACK",
    "MVSP_PACK",
    "ISO_9001_PACK",
    "US_CA_CCPA_CPRA_PACK",
    "SA_PDPL_PACK",
    "JP_APPI_PACK",
    "AU_PRIVACY_ACT_PACK",
    "CISA_CPG_PACK",
    "AU_ESSENTIAL_EIGHT_L1_PACK",
    "UK_GDPR_DPA_PACK",
    "CH_FADP_PACK",
    "AE_PDPL_PACK",
    "OM_PDPL_PACK",
    "JO_PDPL_PACK",
    "MA_CNDP_0908_PACK",
    "US_VA_VCDPA_PACK",
    "US_CO_CPA_PACK",
    "US_CT_CTDPA_PACK",
    "US_TX_TDPSA_PACK",
    "US_UT_UCPA_PACK",
    "FR_CNIL_GDPR_PACK",
    "ES_AEPD_LOPDGDD_PACK",
    "IT_GARANTE_PRIVACY_PACK",
    "NL_AP_UAVG_PACK",
    "IE_DPC_DPA_PACK",
    "AT_DSB_DSG_PACK",
    "PL_UODO_RODO_PACK",
    "SOC_2_PACK",
    "SOC_1_PACK",
    "ISO_27701_PACK",
    "ISO_27017_PACK",
    "SOC_3_PACK",
    "ISO_27018_PACK",
    "ISO_22301_PACK",
    "ISO_20000_1_PACK",
    "OWNER_DECISION_DRAFT_PACKS",
]
