"""Deterministic, versioned applicability evaluation rules engine for compliance frameworks.

Evaluates tenant operational facts and regulatory profiles to deterministically determine
whether controls are APPLICABLE, NOT_APPLICABLE, SCOPED_OUT, or REVIEW_REQUIRED with
auditable statutory and technical justifications.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from conformly.audit.models import AuditActorType, AuditOutcome
from conformly.audit.service import record_audit_event
from conformly.authz.policy import Principal, TenantContext, authorize
from conformly.authz.roles import Capability
from conformly.frameworks.models import (
    CanonicalControl,
    OverlayApplicability,
    TenantApplicabilityProfile,
    TenantControlOverlay,
    TenantFrameworkAdoption,
)

EVALUATOR_VERSION: str = "2026.09.beta-1"

# ---------------------------------------------------------------------------
# Stable Target Identifiers for Declarative Rules
# ---------------------------------------------------------------------------

PHYSICAL_OFFICE_PERIMETER_CONTROLS = frozenset(
    {
        "A.7.1",
        "ISO-A.7.1",
    }
)

DATACENTER_FACILITY_CONTROLS = frozenset(
    {
        "MVSP-4.1",
        "MVSP-4-1",
        "MVSP-1.6",
        "MVSP-1-6",
    }
)

SPECIAL_CATEGORY_DATA_CONTROLS = frozenset(
    {
        "BDSG-SEC-22",
        "GDPR-ART-9",
    }
)

DPO_APPOINTMENT_CONTROLS = frozenset(
    {
        "BDSG-SEC-38",
        "GDPR-ART-37",
    }
)

INTERNATIONAL_TRANSFER_CONTROLS = frozenset(
    {
        "GDPR-ART-44",
        "GDPR-ART-45",
        "GDPR-ART-46",
        "GDPR-ART-47",
        "GDPR-ART-48",
        "GDPR-ART-49",
    }
)

SUBPROCESSOR_SPECIFIC_CONTROLS = frozenset(
    {
        "GDPR-ART-28",
    }
)

GENERAL_SUPPLIER_CONTROLS = frozenset(
    {
        "A.5.19",
        "A.5.20",
        "A.5.21",
        "A.5.22",
        "A.5.23",
        "ISO-A.5.19",
        "ISO-A.5.20",
        "ISO-A.5.21",
        "ISO-A.5.22",
        "ISO-A.5.23",
        "GV.SC-01",
        "NIST-GV-SC-01",
        "CIS-15.1",
        "CIS-15-1",
        "MVSP-1.2",
        "MVSP-1-2",
        "MVSP-1.7",
        "MVSP-1-7",
    }
)

# QMS Design & Development controls — Clause 8.3.x
# Only applicable when organization performs design and/or development activities.
QMS_DESIGN_AND_DEVELOPMENT_CONTROLS = frozenset(
    {
        "QMS-8-3-1",
        "QMS-8-3-2",
        "QMS-8-3-3",
        "QMS-8-3-4",
        "QMS-8-3-5",
        "QMS-8-3-6",
    }
)

# QMS External Provider controls — Clause 8.4.x
# Only applicable when organization uses external providers, outsources processes,
# or provides externally sourced products/services to customers.
QMS_EXTERNAL_PROVIDER_CONTROLS = frozenset(
    {
        "QMS-8-4-1",
        "QMS-8-4-2",
        "QMS-8-4-3",
    }
)

# QMS Post-Delivery Activities control — Clause 8.5.5
# Only applicable when organization has defined post-delivery obligations.
QMS_POST_DELIVERY_CONTROLS = frozenset(
    {
        "QMS-8-5-5",
    }
)


# ---------------------------------------------------------------------------
# Profile & Contradiction Models
# ---------------------------------------------------------------------------


class TenantProfileContext(BaseModel):
    """Profile parameters informing deterministic framework control applicability."""

    # Role & Architecture
    entity_role: Literal["controller", "processor", "both"] | None = Field(
        default="both",
        description="Role under GDPR / privacy regulations (Controller, Processor, or Both).",
    )
    deployment_model: Literal["cloud_saas", "hybrid", "on_premise"] | None = Field(
        default="cloud_saas",
        description="Architecture and deployment model.",
    )

    # Headcount and DPO Triggers (§ 38 BDSG / Art 37 GDPR)
    employee_count: int | None = Field(
        default=25,
        ge=1,
        description="Total employee headcount.",
    )
    automated_processing_personnel_count: int | None = Field(
        default=None,
        description="Number of persons constantly employed in automated data processing (§ 38(1) sent. 1 BDSG).",
    )
    requires_dpia: bool | None = Field(
        default=False,
        description="Whether processing operations require a DPIA under Art. 35 GDPR (§ 38(1) sent. 2 BDSG).",
    )
    processes_data_commercially_for_transfer_or_market_research: bool | None = Field(
        default=False,
        description="Whether data is processed commercially for transfer, scoring, or market/opinion research (§ 38(1) sent. 2 BDSG).",
    )
    regular_systematic_monitoring_large_scale: bool | None = Field(
        default=False,
        description="Core activities requiring regular and systematic monitoring of data subjects on a large scale (Art. 37(1)(b) GDPR).",
    )
    large_scale_special_category_processing: bool | None = Field(
        default=False,
        description="Core activities consisting of large-scale processing of special category data (Art. 37(1)(c) GDPR).",
    )

    # Personal & Special Category Data
    processes_personal_data: bool | None = Field(
        default=True,
        description="Whether tenant systems collect or process personal data.",
    )
    processes_special_category_data: bool | None = Field(
        default=False,
        description="Self-reported indicator: special categories of personal data processed (Art. 9 GDPR / § 22 BDSG).",
    )
    processes_health_or_biometric_data: bool | None = Field(
        default=False,
        description="Operational fact: health, medical, or biometric authentication data processed.",
    )
    processes_criminal_or_judicial_data: bool | None = Field(
        default=False,
        description="Operational fact: criminal convictions or offenses processed.",
    )
    special_category_evidence_indicators: bool | None = Field(
        default=False,
        description="Audit/discovery fact: whether data repositories or whistleblower files contain special-category data.",
    )

    # Physical Environment & Infrastructure
    has_physical_offices: bool | None = Field(
        default=True,
        description="Whether organization operates physical offices vs 100% remote.",
    )
    operates_own_datacenter: bool | None = Field(
        default=False,
        description="Whether organization operates own server rooms/datacenters vs public cloud.",
    )
    uses_cloud_infrastructure: bool | None = Field(
        default=True,
        description="Whether organization utilizes multi-tenant public cloud infrastructure (AWS/GCP/Azure).",
    )

    # Suppliers vs Subprocessors
    uses_subprocessors: bool | None = Field(
        default=True,
        description="Whether third-party personal-data sub-processors are engaged (Art. 28 GDPR).",
    )
    uses_suppliers: bool | None = Field(
        default=True,
        description="Whether third-party IT, hardware, cloud, software, or professional service suppliers are engaged.",
    )

    # International Transfers & Third Countries
    involves_international_transfers: bool | None = Field(
        default=False,
        description="Self-reported indicator: personal data transferred outside EEA.",
    )
    has_third_country_remote_access: bool | None = Field(
        default=False,
        description="Operational fact: personal data accessible remotely by personnel/support outside EEA.",
    )
    has_third_country_onward_transfers: bool | None = Field(
        default=False,
        description="Operational fact: subprocessors transfer or replicate personal data outside EEA.",
    )

    # QMS — ISO 9001:2015 operational scope fields
    performs_design_and_development: bool | None = Field(
        default=False,
        description=(
            "Whether the organization performs design and/or development activities within scope. "
            "Determines applicability of ISO 9001:2015 Clause 8.3 controls (QMS-8-3-x). "
            "Default False (conservative: service-only organizations commonly exclude Clause 8.3)."
        ),
    )
    has_external_providers: bool | None = Field(
        default=True,
        description=(
            "Whether the organization uses external providers, outsources any QMS processes, "
            "or provides externally sourced products/services to customers. "
            "Determines applicability of ISO 9001:2015 Clause 8.4 controls (QMS-8-4-x). "
            "Default True (most organizations engage at least some external providers)."
        ),
    )
    has_post_delivery_activities: bool | None = Field(
        default=None,
        description=(
            "Whether the organization has defined post-delivery obligations such as warranty support, "
            "maintenance, field service, or final disposal. "
            "Determines applicability of ISO 9001:2015 Clause 8.5.5 (QMS-8-5-5). "
            "Default None (requires explicit confirmation per organization)."
        ),
    )

    # Sources & Evidentiary Metadata
    sources: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of profile field names to verifiable data source citations or discovery mechanisms.",
    )


@dataclass(frozen=True, slots=True)
class ProfileContradiction:
    rule_id: str
    summary: str
    affected_controls: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "summary": self.summary,
            "affected_controls": self.affected_controls,
        }


def detect_profile_contradictions(profile: TenantProfileContext) -> list[ProfileContradiction]:
    """Detect contradictory answers or incompatible operational facts."""
    contradictions: list[ProfileContradiction] = []

    # 1. Special Category Contradiction:
    # Self-reported False, but affirmative operational health/biometrics or evidence indicators present
    if profile.processes_special_category_data is False:
        conflicting_indicators: list[str] = []
        if profile.processes_health_or_biometric_data is True:
            conflicting_indicators.append("processes_health_or_biometric_data=True")
        if profile.processes_criminal_or_judicial_data is True:
            conflicting_indicators.append("processes_criminal_or_judicial_data=True")
        if profile.special_category_evidence_indicators is True:
            conflicting_indicators.append("special_category_evidence_indicators=True")

        if conflicting_indicators:
            contradictions.append(
                ProfileContradiction(
                    rule_id="CONTRADICTION_SPECIAL_CATEGORY_REPORTED_ABSENCE",
                    summary=(
                        f"Self-reported absence of special-category processing contradicts affirmative "
                        f"operational facts: {', '.join(conflicting_indicators)}."
                    ),
                    affected_controls=sorted(list(SPECIAL_CATEGORY_DATA_CONTROLS)),
                )
            )

    # 2. International Transfer Contradiction:
    # Self-reported False, but remote access or subprocessor onward transfer outside EEA is True
    if profile.involves_international_transfers is False:
        conflicting_transfers: list[str] = []
        if profile.has_third_country_remote_access is True:
            conflicting_transfers.append("has_third_country_remote_access=True")
        if profile.has_third_country_onward_transfers is True:
            conflicting_transfers.append("has_third_country_onward_transfers=True")

        if conflicting_transfers:
            contradictions.append(
                ProfileContradiction(
                    rule_id="CONTRADICTION_INTERNATIONAL_TRANSFERS_REPORTED_ABSENCE",
                    summary=(
                        f"Claimed absence of international transfers contradicts affirmative non-EEA "
                        f"remote access or subprocessor onward transfers: {', '.join(conflicting_transfers)}."
                    ),
                    affected_controls=sorted(list(INTERNATIONAL_TRANSFER_CONTROLS)),
                )
            )

    # 3. Personal Data Processing Contradiction:
    # Self-reported False, but subprocessors or special categories are True
    if profile.processes_personal_data is False:
        conflicting_personal: list[str] = []
        if (
            profile.processes_special_category_data is True
            or profile.processes_health_or_biometric_data is True
        ):
            conflicting_personal.append("processes_special_category_data=True")
        if profile.uses_subprocessors is True:
            conflicting_personal.append("uses_subprocessors=True")

        if conflicting_personal:
            contradictions.append(
                ProfileContradiction(
                    rule_id="CONTRADICTION_PERSONAL_DATA_REPORTED_ABSENCE",
                    summary=(
                        f"Claimed absence of personal data processing contradicts affirmative personal data facts: "
                        f"{', '.join(conflicting_personal)}."
                    ),
                    affected_controls=["GDPR-*", "BDSG-*"],
                )
            )

    return contradictions


# ---------------------------------------------------------------------------
# Declarative Evaluator Rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApplicabilityEvaluation:
    applicability: OverlayApplicability
    justification: str
    evaluator_version: str = EVALUATOR_VERSION


def evaluate_control_applicability(
    control: CanonicalControl,
    profile: TenantProfileContext,
    *,
    contradictions: list[ProfileContradiction] | None = None,
) -> ApplicabilityEvaluation:
    """Deterministically evaluate applicability using stable requirement IDs and declarative rules."""
    ident = control.identifier.upper()
    active_contradictions = (
        contradictions if contradictions is not None else detect_profile_contradictions(profile)
    )
    contradiction_by_rule = {c.rule_id: c for c in active_contradictions}

    # -----------------------------------------------------------------------
    # Rule 1: Physical Office Perimeter Access (A.7.1)
    # -----------------------------------------------------------------------
    if ident in PHYSICAL_OFFICE_PERIMETER_CONTROLS:
        if profile.has_physical_offices is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Physical office operations status is unconfirmed; "
                    "cannot determine physical perimeter scope without verified office facility status."
                ),
            )
        if not profile.has_physical_offices:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.SCOPED_OUT,
                justification=(
                    "Scoped out: Organization operates as a 100% distributed remote team with no physical "
                    "office facilities; physical perimeter access safeguards are excluded from ISMS operational scope. "
                    "Note: Endpoint and teleworking safeguards remain applicable."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification="Applicable: Organization operates physical office facilities requiring perimeter access security.",
        )

    # -----------------------------------------------------------------------
    # Rule 2: Physical Datacenter Operations & Inherited Cloud Assurance (MVSP-4.1)
    # -----------------------------------------------------------------------
    if ident in DATACENTER_FACILITY_CONTROLS:
        if profile.operates_own_datacenter is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Datacenter hosting model is unconfirmed; "
                    "cannot determine direct vs. inherited physical infrastructure controls."
                ),
            )
        if not profile.operates_own_datacenter:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Production systems are 100% hosted in multi-tenant public cloud infrastructure; "
                    "physical datacenter security controls are inherited from certified cloud providers (AWS/GCP/Azure). "
                    "Assurance must be verified via vendor certifications (SOC 2 / ISO 27001)."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification="Applicable: Organization owns and operates on-premises datacenter/server room infrastructure.",
        )

    # -----------------------------------------------------------------------
    # Rule 3: Special Categories of Personal Data (§ 22 BDSG, Art. 9 GDPR)
    # -----------------------------------------------------------------------
    if ident in SPECIAL_CATEGORY_DATA_CONTROLS:
        # Check for contradiction first
        if "CONTRADICTION_SPECIAL_CATEGORY_REPORTED_ABSENCE" in contradiction_by_rule:
            c = contradiction_by_rule["CONTRADICTION_SPECIAL_CATEGORY_REPORTED_ABSENCE"]
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=f"Review required: Contradictory profile facts detected. {c.summary}",
            )
        if profile.processes_special_category_data is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Special category processing status is unconfirmed; "
                    "cannot exempt without verified processing inventory."
                ),
            )
        if not profile.processes_special_category_data:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization does not process special categories of personal data "
                    "(health, biometric, racial/ethnic, or political data) under Art. 9 GDPR or § 22 BDSG."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification=(
                "Applicable: Organization processes special categories of personal data "
                "subject to heightened statutory safeguards under Art. 9 GDPR and § 22 BDSG."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 4: Mandatory DPO Designation (§ 38 BDSG, Art. 37 GDPR)
    # Evaluates headcount, DPIA triggers, and commercial transfer activities
    # -----------------------------------------------------------------------
    if ident in DPO_APPOINTMENT_CONTROLS:
        # 1. Affirmative triggers (any trigger makes it APPLICABLE)
        if profile.requires_dpia is True:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    "Applicable: Compulsory DPO designation under § 38(1) sent. 2 BDSG / Art. 35 GDPR: "
                    "processing operations require a Data Protection Impact Assessment (DPIA) regardless of headcount."
                ),
            )
        if profile.processes_data_commercially_for_transfer_or_market_research is True:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    "Applicable: Compulsory DPO designation under § 38(1) sent. 2 BDSG: "
                    "organization processes personal data commercially for the purpose of transfer, scoring, or market/opinion research."
                ),
            )
        if profile.regular_systematic_monitoring_large_scale is True:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    "Applicable: Compulsory DPO designation under Art. 37(1)(b) GDPR: "
                    "core activities require regular and systematic monitoring of data subjects on a large scale."
                ),
            )
        if profile.large_scale_special_category_processing is True:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    "Applicable: Compulsory DPO designation under Art. 37(1)(c) GDPR: "
                    "core activities consist of large-scale processing of special categories of personal data."
                ),
            )

        # 2. Automated processing personnel count
        effective_headcount = (
            profile.automated_processing_personnel_count
            if profile.automated_processing_personnel_count is not None
            else profile.employee_count
        )

        if effective_headcount is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Automated processing personnel headcount is unconfirmed; "
                    "statutory DPO designation threshold cannot be determined."
                ),
            )

        if effective_headcount >= 20:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    f"Applicable: Organization constantly employs {effective_headcount} persons in automated data processing, "
                    "meeting the statutory threshold of 20 persons mandated for compulsory DPO designation under § 38(1) sent. 1 BDSG."
                ),
            )

        # 3. Headcount < 20 and no affirmative triggers
        # Check if triggers are explicitly unknown (None)
        if (
            profile.requires_dpia is None
            or profile.processes_data_commercially_for_transfer_or_market_research is None
        ):
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Headcount is under 20, but statutory DPO appointment triggers "
                    "(DPIA requirement, commercial transfer) are unconfirmed."
                ),
            )

        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.NOT_APPLICABLE,
            justification=(
                f"Not applicable: Organization constantly employs {effective_headcount} persons in automated data processing, "
                "which is below the statutory threshold of 20 persons mandated for compulsory DPO designation under § 38 BDSG, "
                "and no supplementary triggers (DPIA, large-scale monitoring, or commercial transfer) apply."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 5: Cross-Border International Data Transfers (GDPR Chapter V / Arts. 44-49)
    # -----------------------------------------------------------------------
    if ident in INTERNATIONAL_TRANSFER_CONTROLS:
        if "CONTRADICTION_INTERNATIONAL_TRANSFERS_REPORTED_ABSENCE" in contradiction_by_rule:
            c = contradiction_by_rule["CONTRADICTION_INTERNATIONAL_TRANSFERS_REPORTED_ABSENCE"]
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=f"Review required: Contradictory profile facts detected. {c.summary}",
            )
        if profile.involves_international_transfers is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: International data transfer and remote access status is unconfirmed; "
                    "cannot evaluate Chapter V requirements without verified data flow inventory."
                ),
            )
        if (
            profile.involves_international_transfers
            or profile.has_third_country_remote_access
            or profile.has_third_country_onward_transfers
        ):
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.APPLICABLE,
                justification=(
                    "Applicable: Personal data is transferred or accessible outside the European Economic Area (EEA), "
                    "requiring Chapter V transfer mechanisms (adequacy decision, Standard Contractual Clauses, or BCRs)."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.NOT_APPLICABLE,
            justification=(
                "Not applicable: Personal data is strictly stored, processed, and maintained within the European Economic Area (EEA); "
                "no third-country transfers, non-EEA remote access, or cross-border mechanisms are required."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 6: Third-Party Personal Data Subprocessors (GDPR Art. 28)
    # -----------------------------------------------------------------------
    if ident in SUBPROCESSOR_SPECIFIC_CONTROLS:
        if profile.uses_subprocessors is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification="Review required: Engagement of personal data sub-processors is unconfirmed.",
            )
        if not profile.uses_subprocessors:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization does not engage third-party sub-processors or external data vendors "
                    "for customer data processing under Art. 28 GDPR."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification="Applicable: Organization engages third-party sub-processors subject to Art. 28 GDPR data processing agreements.",
        )

    # -----------------------------------------------------------------------
    # Rule 7: General Supplier & Supply Chain Security (ISO A.5.19-23, NIST GV.SC-01, CIS 15, MVSP 1.2)
    # CRITICAL: Suppliers are NOT synonymous with personal-data subprocessors!
    # -----------------------------------------------------------------------
    if ident in GENERAL_SUPPLIER_CONTROLS:
        if profile.uses_suppliers is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification="Review required: Third-party supplier and IT vendor engagement is unconfirmed.",
            )
        if not profile.uses_suppliers:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization operates without any third-party IT, cloud, hardware, "
                    "software, or professional service suppliers."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification=(
                "Applicable: Organization engages third-party hardware, software, cloud, or professional service suppliers; "
                "supply chain security management applies regardless of whether personal data subprocessors are engaged."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 8: General Personal Data Scope (GDPR and BDSG controls)
    # -----------------------------------------------------------------------
    if ident.startswith("GDPR-") or ident.startswith("BDSG-"):
        if "CONTRADICTION_PERSONAL_DATA_REPORTED_ABSENCE" in contradiction_by_rule:
            c = contradiction_by_rule["CONTRADICTION_PERSONAL_DATA_REPORTED_ABSENCE"]
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=f"Review required: Contradictory profile facts detected. {c.summary}",
            )
        if profile.processes_personal_data is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification="Review required: Personal data processing boundary is unconfirmed.",
            )
        if not profile.processes_personal_data:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification="Not applicable: Organization does not collect or process personal data in the evaluated system boundary.",
            )

    # -----------------------------------------------------------------------
    # Rule 9: QMS Design & Development scope (ISO 9001 Clause 8.3)
    # Applies only when tenant performs design and/or development activities.
    # -----------------------------------------------------------------------
    if ident in QMS_DESIGN_AND_DEVELOPMENT_CONTROLS:
        if profile.performs_design_and_development is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Design and development scope is unconfirmed; "
                    "cannot determine Clause 8.3 applicability without explicit confirmation of "
                    "whether the organization performs D&D activities within the QMS boundary."
                ),
            )
        if not profile.performs_design_and_development:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization does not perform design and/or development "
                    "activities within the declared QMS scope; ISO 9001:2015 Clause 8.3 "
                    "(Design and Development) controls are excluded from scope. "
                    "If D&D activities are introduced, this exclusion must be reviewed."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification=(
                "Applicable: Organization performs design and/or development activities within "
                "QMS scope; ISO 9001:2015 Clause 8.3 Design and Development controls apply."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 10: QMS External Providers scope (ISO 9001 Clause 8.4)
    # Applies when tenant uses external providers or outsources any QMS processes.
    # -----------------------------------------------------------------------
    if ident in QMS_EXTERNAL_PROVIDER_CONTROLS:
        if profile.has_external_providers is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: External provider engagement status is unconfirmed; "
                    "cannot determine Clause 8.4 applicability without verified procurement inventory."
                ),
            )
        if not profile.has_external_providers:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization does not use external providers, outsource any "
                    "QMS processes, or provide externally sourced products/services to customers; "
                    "ISO 9001:2015 Clause 8.4 (Control of Externally Provided Processes) controls "
                    "are excluded from scope."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification=(
                "Applicable: Organization engages external providers or outsources QMS processes; "
                "ISO 9001:2015 Clause 8.4 External Provider controls apply."
            ),
        )

    # -----------------------------------------------------------------------
    # Rule 11: QMS Post-Delivery Activities scope (ISO 9001 Clause 8.5.5)
    # -----------------------------------------------------------------------
    if ident in QMS_POST_DELIVERY_CONTROLS:
        if profile.has_post_delivery_activities is None:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.REVIEW_REQUIRED,
                justification=(
                    "Review required: Post-delivery activity status is unconfirmed; "
                    "cannot determine Clause 8.5.5 applicability without confirmation of "
                    "whether the organization has warranty, maintenance, or disposal obligations."
                ),
            )
        if not profile.has_post_delivery_activities:
            return ApplicabilityEvaluation(
                applicability=OverlayApplicability.NOT_APPLICABLE,
                justification=(
                    "Not applicable: Organization has no defined post-delivery obligations "
                    "(warranty support, maintenance, field service, or disposal); "
                    "ISO 9001:2015 Clause 8.5.5 Post-Delivery Activities is excluded from scope."
                ),
            )
        return ApplicabilityEvaluation(
            applicability=OverlayApplicability.APPLICABLE,
            justification=(
                "Applicable: Organization has defined post-delivery obligations; "
                "ISO 9001:2015 Clause 8.5.5 Post-Delivery Activities controls apply."
            ),
        )

    # Default: Canonical controls are active and applicable within operational boundary
    return ApplicabilityEvaluation(
        applicability=OverlayApplicability.APPLICABLE,
        justification="Applicable: Standard requirement active within tenant operational boundary.",
    )


# ---------------------------------------------------------------------------
# Batch Adoption Evaluation & Persistence
# ---------------------------------------------------------------------------


def evaluate_and_apply_adoption_applicability(
    session: Session,
    *,
    tenant_id: UUID,
    adoption_id: UUID,
    profile: TenantProfileContext,
    principal: Principal,
    request_id: str,
    tenant_context: TenantContext | None = None,
) -> list[TenantControlOverlay]:
    """Evaluate applicability for all controls of an adopted framework and persist profile and overlays."""
    # 1. Authorize if TenantContext provided
    if tenant_context is not None:
        authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)

    adoption = session.get(TenantFrameworkAdoption, adoption_id)
    if not adoption or adoption.tenant_id != tenant_id:
        raise ValueError(f"adoption {adoption_id} not found for tenant {tenant_id}")

    # 2. Detect contradictions
    contradictions = detect_profile_contradictions(profile)

    # 3. Query all canonical controls belonging to the adopted version
    controls = session.scalars(
        select(CanonicalControl)
        .where(CanonicalControl.framework_version_id == adoption.framework_version_id)
        .order_by(CanonicalControl.sort_order)
    ).all()

    # 4. Existing overlays map to track changes
    existing_overlays = session.scalars(
        select(TenantControlOverlay).where(
            TenantControlOverlay.tenant_id == tenant_id,
            TenantControlOverlay.adoption_id == adoption_id,
        )
    ).all()
    overlay_by_ctrl: dict[UUID, TenantControlOverlay] = {
        o.canonical_control_id: o for o in existing_overlays
    }

    result_overlays: list[TenantControlOverlay] = []
    updated_count = 0
    created_count = 0

    newly_applicable: list[str] = []
    newly_excluded: list[str] = []
    newly_review_required: list[str] = []

    for ctrl in controls:
        evaluation = evaluate_control_applicability(ctrl, profile, contradictions=contradictions)
        existing = overlay_by_ctrl.get(ctrl.id)

        if existing:
            prev_app = existing.applicability
            new_app = evaluation.applicability

            if prev_app != new_app:
                if new_app == OverlayApplicability.APPLICABLE:
                    newly_applicable.append(ctrl.identifier)
                elif new_app in (
                    OverlayApplicability.NOT_APPLICABLE,
                    OverlayApplicability.SCOPED_OUT,
                ):
                    newly_excluded.append(ctrl.identifier)
                elif new_app == OverlayApplicability.REVIEW_REQUIRED:
                    newly_review_required.append(ctrl.identifier)

            existing.applicability = evaluation.applicability
            existing.justification = evaluation.justification
            result_overlays.append(existing)
            updated_count += 1
        else:
            new_overlay = TenantControlOverlay(
                tenant_id=tenant_id,
                adoption_id=adoption_id,
                canonical_control_id=ctrl.id,
                applicability=evaluation.applicability,
                justification=evaluation.justification,
                created_by_user_id=principal.user_id,
            )
            session.add(new_overlay)
            result_overlays.append(new_overlay)
            created_count += 1

    session.flush()

    # 5. Persist TenantApplicabilityProfile
    summary = {
        "total_controls": len(controls),
        "applicable_count": sum(
            1 for o in result_overlays if o.applicability == OverlayApplicability.APPLICABLE
        ),
        "not_applicable_count": sum(
            1 for o in result_overlays if o.applicability == OverlayApplicability.NOT_APPLICABLE
        ),
        "scoped_out_count": sum(
            1 for o in result_overlays if o.applicability == OverlayApplicability.SCOPED_OUT
        ),
        "review_required_count": sum(
            1 for o in result_overlays if o.applicability == OverlayApplicability.REVIEW_REQUIRED
        ),
        "contradictions_count": len(contradictions),
        "changes_detected": len(newly_applicable)
        + len(newly_excluded)
        + len(newly_review_required),
    }

    profile_record = TenantApplicabilityProfile(
        tenant_id=tenant_id,
        adoption_id=adoption_id,
        evaluator_version=EVALUATOR_VERSION,
        profile_answers_json=profile.model_dump_json(),
        sources_json=json.dumps(profile.sources),
        contradictions_json=json.dumps([c.to_dict() for c in contradictions]),
        evaluation_summary_json=json.dumps(summary),
        evaluated_by_user_id=principal.user_id,
        review_status="NEEDS_REVIEW"
        if (summary["review_required_count"] > 0 or len(contradictions) > 0)
        else "EVALUATED",
    )
    session.add(profile_record)

    # 6. Update adoption impact summary
    impact_data = {
        "evaluator_version": EVALUATOR_VERSION,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "summary": summary,
        "newly_applicable": newly_applicable,
        "newly_excluded": newly_excluded,
        "newly_review_required": newly_review_required,
    }
    adoption.impact_summary_json = json.dumps(impact_data)
    session.flush()

    # 7. Audit Event
    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="framework_adoption.applicability_evaluated",
        resource_type="tenant_framework_adoption",
        resource_id=str(adoption_id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "version_id": str(adoption.framework_version_id),
            "evaluator_version": EVALUATOR_VERSION,
            "count": created_count + updated_count,
            "status": "evaluated",
            "profile_id": str(profile_record.id),
        },
        occurred_at=datetime.now(UTC),
    )

    if newly_applicable or newly_excluded or newly_review_required:
        record_audit_event(
            session,
            tenant_id=tenant_id,
            actor_type=AuditActorType.USER,
            actor_id=principal.user_id,
            action="framework_adoption.applicability_scope_changed",
            resource_type="tenant_framework_adoption",
            resource_id=str(adoption_id),
            request_id=request_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "version_id": str(adoption.framework_version_id),
                "count": len(newly_applicable) + len(newly_excluded) + len(newly_review_required),
                "status": "scope_changed",
            },
            occurred_at=datetime.now(UTC),
        )

    return result_overlays


def override_control_applicability(
    session: Session,
    *,
    tenant_id: UUID,
    adoption_id: UUID,
    control_id: UUID,
    applicability: OverlayApplicability,
    justification: str,
    principal: Principal,
    tenant_context: TenantContext,
    request_id: str,
) -> TenantControlOverlay:
    """Manually override a control's applicability with required auditable justification and role check."""
    authorize(principal, tenant_context, Capability.FRAMEWORK_MANAGE)

    adoption = session.get(TenantFrameworkAdoption, adoption_id)
    if not adoption or adoption.tenant_id != tenant_id:
        raise ValueError(f"adoption {adoption_id} not found for tenant {tenant_id}")

    control = session.get(CanonicalControl, control_id)
    if not control or control.framework_version_id != adoption.framework_version_id:
        raise ValueError(f"control {control_id} not found for adoption {adoption_id}")

    # Exclusions require substantive auditable justification
    if applicability in (OverlayApplicability.NOT_APPLICABLE, OverlayApplicability.SCOPED_OUT):
        if not justification or len(justification.strip()) < 10:
            raise ValueError(
                "Exclusion requires an auditable justification of at least 10 characters."
            )

    existing = session.scalar(
        select(TenantControlOverlay).where(
            TenantControlOverlay.tenant_id == tenant_id,
            TenantControlOverlay.adoption_id == adoption_id,
            TenantControlOverlay.canonical_control_id == control_id,
        )
    )

    if existing:
        previous_applicability = existing.applicability
        existing.applicability = applicability
        existing.justification = justification
        overlay = existing
    else:
        previous_applicability = None
        overlay = TenantControlOverlay(
            tenant_id=tenant_id,
            adoption_id=adoption_id,
            canonical_control_id=control_id,
            applicability=applicability,
            justification=justification,
            created_by_user_id=principal.user_id,
        )
        session.add(overlay)

    session.flush()

    record_audit_event(
        session,
        tenant_id=tenant_id,
        actor_type=AuditActorType.USER,
        actor_id=principal.user_id,
        action="framework_adoption.control_applicability_overridden",
        resource_type="tenant_control_overlay",
        resource_id=str(overlay.id),
        request_id=request_id,
        outcome=AuditOutcome.SUCCESS,
        metadata={
            "control_id": str(control_id),
            "control_identifier": control.identifier,
            "previous_applicability": str(previous_applicability)
            if previous_applicability
            else None,
            "applicability": str(applicability),
            "status": "overridden",
        },
        occurred_at=datetime.now(UTC),
    )

    return overlay
