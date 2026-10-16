"""Modular definitions for Conformly compliance framework packs.

Tier A packs (30 total — all active per Module A decisions):
  1. ISO/IEC 27001:2022 ISMS Pre-Audit
  2. EU GDPR & German BDSG Privacy Operations
  3. NIST Cybersecurity Framework 2.0
  4. CIS Critical Security Controls v8 IG1
  5. Minimum Viable Secure Product v2.0
  6. ISO 9001:2015 Quality Management System (admitted per ADR D-059)
  7. California Consumer Privacy Act & CPRA (admitted per ADR D-060)
  8. Saudi Arabia Personal Data Protection Law (admitted per ADR D-060)
  9. Japan Act on the Protection of Personal Information (admitted per ADR D-060)
  10. Australia Privacy Act 1988 & APPs (admitted per ADR D-060)
  11. CISA Cross-Sector Cybersecurity Performance Goals (admitted per ADR D-061)
  12. Australian Essential Eight Maturity Level 1 (admitted per ADR D-061)
  13. UK GDPR & Data Protection Act 2018 (admitted per ADR D-061)
  14. Swiss Federal Act on Data Protection nFADP (admitted per ADR D-061)
  15. UAE Personal Data Protection Law (admitted per ADR D-062)
  16. Oman Personal Data Protection Law (admitted per ADR D-062)
  17. Jordan Personal Data Protection Law (admitted per ADR D-062)
  18. Morocco Personal Data Protection Law 09-08 (admitted per ADR D-062)
  19. Virginia Consumer Data Protection Act VCDPA (admitted per ADR D-063)
  20. Colorado Privacy Act CPA (admitted per ADR D-063)
  21. Connecticut Data Privacy Act CTDPA (admitted per ADR D-063)
  22. Texas Data Privacy and Security Act TDPSA (admitted per ADR D-063)
  23. Utah Consumer Privacy Act UCPA (admitted per ADR D-063)
  24. France Data Protection Act (admitted per ADR D-064)
  25. Spain Data Protection Act LOPDGDD (admitted per ADR D-064)
  26. Italy Personal Data Protection Code (admitted per ADR D-064)
  27. Netherlands GDPR Implementation Act UAVG (admitted per ADR D-064)
  28. Ireland Data Protection Act 2018 (admitted per ADR D-064)
  29. Austria Data Protection Act DSG (admitted per ADR D-064)
  30. Poland Personal Data Protection Act UODO/RODO (admitted per ADR D-064)
"""

from conformly.frameworks.packs.ae_pdpl import AE_PDPL_PACK
from conformly.frameworks.packs.at_dsb_dsg import AT_DSB_DSG_PACK
from conformly.frameworks.packs.au_essential_eight_l1 import AU_ESSENTIAL_EIGHT_L1_PACK
from conformly.frameworks.packs.au_privacy_act import AU_PRIVACY_ACT_PACK
from conformly.frameworks.packs.ch_fadp import CH_FADP_PACK
from conformly.frameworks.packs.cis_controls_ig1 import CIS_CONTROLS_IG1_PACK
from conformly.frameworks.packs.cisa_cpg import CISA_CPG_PACK
from conformly.frameworks.packs.es_aepd_lopdgdd import ES_AEPD_LOPDGDD_PACK
from conformly.frameworks.packs.fr_cnil_gdpr import FR_CNIL_GDPR_PACK
from conformly.frameworks.packs.gdpr_bdsg import GDPR_BDSG_PACK
from conformly.frameworks.packs.ie_dpc_dpa import IE_DPC_DPA_PACK
from conformly.frameworks.packs.iso_9001 import ISO_9001_PACK
from conformly.frameworks.packs.iso_20000_1 import ISO_20000_1_PACK
from conformly.frameworks.packs.iso_22301 import ISO_22301_PACK
from conformly.frameworks.packs.iso_27001 import ISO_27001_PACK
from conformly.frameworks.packs.iso_27017 import ISO_27017_PACK
from conformly.frameworks.packs.iso_27018 import ISO_27018_PACK
from conformly.frameworks.packs.iso_27701 import ISO_27701_PACK
from conformly.frameworks.packs.it_garante_privacy import IT_GARANTE_PRIVACY_PACK
from conformly.frameworks.packs.jo_pdpl import JO_PDPL_PACK
from conformly.frameworks.packs.jp_appi import JP_APPI_PACK
from conformly.frameworks.packs.ma_cndp_0908 import MA_CNDP_0908_PACK
from conformly.frameworks.packs.mvsp import MVSP_PACK
from conformly.frameworks.packs.nist_csf import NIST_CSF_PACK
from conformly.frameworks.packs.nl_ap_uavg import NL_AP_UAVG_PACK
from conformly.frameworks.packs.om_pdpl import OM_PDPL_PACK
from conformly.frameworks.packs.owner_decision_drafts import OWNER_DECISION_DRAFT_PACKS
from conformly.frameworks.packs.pl_uodo_rodo import PL_UODO_RODO_PACK
from conformly.frameworks.packs.sa_pdpl import SA_PDPL_PACK
from conformly.frameworks.packs.soc_1 import SOC_1_PACK
from conformly.frameworks.packs.soc_2 import SOC_2_PACK
from conformly.frameworks.packs.soc_3 import SOC_3_PACK
from conformly.frameworks.packs.uk_gdpr_dpa import UK_GDPR_DPA_PACK
from conformly.frameworks.packs.us_ca_ccpa_cpra import US_CA_CCPA_CPRA_PACK
from conformly.frameworks.packs.us_co_cpa import US_CO_CPA_PACK
from conformly.frameworks.packs.us_ct_ctdpa import US_CT_CTDPA_PACK
from conformly.frameworks.packs.us_tx_tdpsa import US_TX_TDPSA_PACK
from conformly.frameworks.packs.us_ut_ucpa import US_UT_UCPA_PACK
from conformly.frameworks.packs.us_va_vcdpa import US_VA_VCDPA_PACK

TIER_A_PACKS = [
    ISO_27001_PACK,
    GDPR_BDSG_PACK,
    NIST_CSF_PACK,
    CIS_CONTROLS_IG1_PACK,
    MVSP_PACK,
    ISO_9001_PACK,
    US_CA_CCPA_CPRA_PACK,
    SA_PDPL_PACK,
    JP_APPI_PACK,
    AU_PRIVACY_ACT_PACK,
    CISA_CPG_PACK,
    AU_ESSENTIAL_EIGHT_L1_PACK,
    UK_GDPR_DPA_PACK,
    CH_FADP_PACK,
    AE_PDPL_PACK,
    OM_PDPL_PACK,
    JO_PDPL_PACK,
    MA_CNDP_0908_PACK,
    US_VA_VCDPA_PACK,
    US_CO_CPA_PACK,
    US_CT_CTDPA_PACK,
    US_TX_TDPSA_PACK,
    US_UT_UCPA_PACK,
    FR_CNIL_GDPR_PACK,
    ES_AEPD_LOPDGDD_PACK,
    IT_GARANTE_PRIVACY_PACK,
    NL_AP_UAVG_PACK,
    IE_DPC_DPA_PACK,
    AT_DSB_DSG_PACK,
    PL_UODO_RODO_PACK,
]

MODULE_B_DRAFT_PACKS = [
    SOC_2_PACK,
    SOC_1_PACK,
    ISO_27701_PACK,
    ISO_27017_PACK,
    SOC_3_PACK,
    ISO_27018_PACK,
    ISO_22301_PACK,
    ISO_20000_1_PACK,
]

MODULE_B_PACKS = MODULE_B_DRAFT_PACKS

__all__ = [
    "TIER_A_PACKS",
    "MODULE_B_DRAFT_PACKS",
    "MODULE_B_PACKS",
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
