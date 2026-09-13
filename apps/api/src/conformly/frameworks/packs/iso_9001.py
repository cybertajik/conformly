"""ISO 9001:2015 Quality Management System (QMS) Pre-Audit Pack Definition.

Covers all addressable subclauses of ISO 9001:2015 Clauses 4–10:

  Clause 4 — Context of the Organization (4.1, 4.2, 4.3, 4.4)
  Clause 5 — Leadership (5.1.1, 5.1.2, 5.2.1, 5.2.2, 5.3)
  Clause 6 — Planning (6.1.1, 6.1.2, 6.2.1, 6.2.2, 6.3)
  Clause 7 — Support (7.1.1–7.1.6, 7.2, 7.3, 7.4, 7.5.1–7.5.3)
  Clause 8 — Operation (8.1, 8.2.1–8.2.4, 8.3.1–8.3.6, 8.4.1–8.4.3, 8.5.1–8.5.6, 8.6, 8.7)
  Clause 9 — Performance Evaluation (9.1.1–9.1.3, 9.2.1–9.2.2, 9.3.1–9.3.3)
  Clause 10 — Improvement (10.1, 10.2.1–10.2.2, 10.3)

Content rights:
  ISO 9001:2015 is a proprietary standard (copyright ISO/TC 176/SC 2). This pack provides an
  original, proprietary pre-audit readiness taxonomy and implementation guidance authored by
  Conformly. Clause references and titles are used as structural anchors only; no verbatim ISO
  standard text is reproduced or sold. Legal/IP counsel review is required prior to production
  customer issuance.

Decision provenance: ADR D-059 — Product Owner admitted ISO 9001 to Module A Beta, 2026-09-13.
"""

from conformly.frameworks.models import (
    CoverageDisposition,
    MappingType,
    SourceRequirementType,
)
from conformly.frameworks.packs.types import (
    FrameworkPackDefinition,
    PackControlDefinition,
    PackCoverageDefinition,
    PackEvidenceDefinition,
    PackMappingDefinition,
    PackSourceRequirementDefinition,
)

# ---------------------------------------------------------------------------
# Authority and rights metadata
# ---------------------------------------------------------------------------

QMS_AUTHORITY = "International Organization for Standardization (ISO) / TC 176/SC 2"
QMS_EDITION = "ISO 9001:2015 (incorporating Technical Corrigendum 1:2009 errata, confirmed 2021)"
QMS_RIGHTS = (
    "Copyright ISO/TC 176/SC 2. Clause references and structural titles are used as identification "
    "anchors only. Implementation guidance, evidence specifications, and operational procedures are "
    "original works authored by Conformly and do not reproduce proprietary standard text verbatim."
)
QMS_URL = "https://www.iso.org/standard/62085.html"

# ---------------------------------------------------------------------------
# Clause data: (subclause_id, title, description, category, cadence)
#   subclause_id  — maps to control identifier QMS-{id.replace('.', '-')}
#   description   — Conformly-authored summary of the subclause requirement
# ---------------------------------------------------------------------------

QMS_CLAUSES: list[tuple[str, str, str, str, str]] = [
    # ── Clause 4: Context ────────────────────────────────────────────────────
    (
        "4.1",
        "Understanding the Organization and Its Context",
        "Determine and monitor external and internal issues relevant to QMS purpose, strategic "
        "direction, and intended outcomes. Include changes in regulatory environment, market "
        "position, and organizational capabilities.",
        "Context of the Organization",
        "Annual review",
    ),
    (
        "4.2",
        "Understanding the Needs and Expectations of Interested Parties",
        "Identify interested parties relevant to the QMS and determine their relevant requirements. "
        "Monitor and review information about interested parties and their relevant requirements.",
        "Context of the Organization",
        "Annual review",
    ),
    (
        "4.3",
        "Determining the Scope of the QMS",
        "Determine the boundaries and applicability of the QMS, considering external/internal "
        "issues, interested party requirements, and organization's products and services. "
        "Document and maintain the scope as documented information.",
        "Context of the Organization",
        "Annual review",
    ),
    (
        "4.4",
        "Quality Management System and Its Processes",
        "Establish, implement, maintain, and continually improve the QMS and its processes. "
        "Determine process inputs/outputs, sequence, interactions, criteria, resources, "
        "responsibilities, risks, opportunities, and improvements.",
        "Context of the Organization",
        "Continuous",
    ),
    # ── Clause 5: Leadership ─────────────────────────────────────────────────
    (
        "5.1.1",
        "Leadership and Commitment — General",
        "Top management shall take accountability for the effectiveness of the QMS, ensure "
        "quality policy and objectives are compatible with strategic direction, promote the "
        "process approach and risk-based thinking, and ensure the QMS achieves its intended results.",
        "Leadership & Commitment",
        "Annual review",
    ),
    (
        "5.1.2",
        "Leadership and Commitment — Customer Focus",
        "Top management shall demonstrate leadership and commitment with respect to customer focus: "
        "ensure customer and legal/regulatory requirements are determined and met; risks affecting "
        "conformity of products/services are addressed; and enhancing customer satisfaction remains a focus.",
        "Leadership & Commitment",
        "Annual review",
    ),
    (
        "5.2.1",
        "Establishing the Quality Policy",
        "Top management shall establish, implement, and maintain a quality policy that is appropriate "
        "to organization purpose and context, provides a framework for quality objectives, includes "
        "a commitment to satisfy applicable requirements, and includes a commitment to continual improvement.",
        "Quality Policy",
        "Annual review",
    ),
    (
        "5.2.2",
        "Communicating the Quality Policy",
        "The quality policy shall be available as documented information, communicated, understood, "
        "and applied within the organization, and be available to relevant interested parties as appropriate.",
        "Quality Policy",
        "Annual review",
    ),
    (
        "5.3",
        "Organizational Roles, Responsibilities and Authorities",
        "Top management shall assign, communicate, and ensure the responsibility and authority for "
        "relevant roles. Specifically, assign responsibility for ensuring QMS conformity, reporting "
        "on QMS performance including opportunities for improvement, and ensuring customer focus.",
        "Leadership & Commitment",
        "Annual review",
    ),
    # ── Clause 6: Planning ───────────────────────────────────────────────────
    (
        "6.1.1",
        "Actions to Address Risks and Opportunities — Determination",
        "Consider context issues and interested party requirements and determine risks and "
        "opportunities that need to be addressed to ensure QMS achieves intended results, "
        "enhance desirable effects, prevent/reduce undesired effects, and achieve improvement.",
        "Planning",
        "Annual review",
    ),
    (
        "6.1.2",
        "Actions to Address Risks and Opportunities — Actions",
        "Plan actions to address risks and opportunities, integrate actions into QMS processes, "
        "evaluate effectiveness of those actions. Actions shall be proportionate to potential "
        "impact on product/service conformity.",
        "Planning",
        "Annual review",
    ),
    (
        "6.2.1",
        "Quality Objectives and Planning — Establishing Objectives",
        "Establish quality objectives at relevant functions, levels, and processes. Objectives "
        "shall be consistent with quality policy, measurable, take into account applicable "
        "requirements, be monitored, communicated, and updated as appropriate.",
        "Planning",
        "Annual review",
    ),
    (
        "6.2.2",
        "Quality Objectives and Planning — Planning Actions",
        "Determine what will be done, what resources will be required, who will be responsible, "
        "when it will be completed, and how results will be evaluated when planning how to achieve "
        "quality objectives.",
        "Planning",
        "Annual review",
    ),
    (
        "6.3",
        "Planning of Changes",
        "When the organization determines the need for changes to the QMS, carry out the changes "
        "in a planned manner, considering the purpose and potential consequences of changes, "
        "QMS integrity, resource availability, and allocation/reallocation of responsibilities.",
        "Planning",
        "As needed",
    ),
    # ── Clause 7: Support ────────────────────────────────────────────────────
    (
        "7.1.1",
        "Resources — General",
        "Determine and provide the resources needed for the establishment, implementation, "
        "maintenance, and continual improvement of the QMS, considering capabilities and constraints "
        "of existing internal resources and the need for external resources.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.1.2",
        "Resources — People",
        "Determine and provide the persons necessary for the effective implementation of the QMS "
        "and for the operation and control of its processes.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.1.3",
        "Resources — Infrastructure",
        "Determine, provide, and maintain infrastructure for the operation of QMS processes to "
        "achieve conformity of products and services. Infrastructure includes buildings, utilities, "
        "IT hardware/software, transportation, and information and communication technology.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.1.4",
        "Resources — Environment for the Operation of Processes",
        "Determine, provide, and maintain the environment necessary for operation of QMS processes "
        "and conformity. Environment encompasses social, psychological, and physical factors "
        "(e.g., non-discriminatory, calm, temperature, hygiene, noise).",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.1.5",
        "Resources — Monitoring and Measuring Resources",
        "Determine and provide monitoring and measuring resources for verifying product/service "
        "conformity. Ensure resources are suitable, maintained, and retained as documented "
        "information for calibration/verification evidence.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.1.6",
        "Resources — Organizational Knowledge",
        "Determine, maintain, and make available knowledge necessary for operation of QMS processes "
        "and to achieve conformity. Consider current knowledge base, assess changing needs and "
        "trends, and acquire and retain necessary additional knowledge.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.2",
        "Competence",
        "Determine necessary competence of persons doing work affecting quality performance, "
        "ensure persons are competent based on appropriate education/training/experience, "
        "take actions to acquire necessary competence, and retain documented information as evidence.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.3",
        "Awareness",
        "Ensure persons doing work under organization control are aware of the quality policy, "
        "relevant quality objectives, their contribution to QMS effectiveness, and the implications "
        "of not conforming with QMS requirements.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.4",
        "Communication",
        "Determine internal and external communications relevant to the QMS including: what to "
        "communicate, when to communicate, with whom to communicate, how to communicate, "
        "and who communicates.",
        "Support & Resources",
        "Annual review",
    ),
    (
        "7.5.1",
        "Documented Information — General",
        "The QMS shall include documented information required by ISO 9001:2015 and documented "
        "information determined to be necessary for the effectiveness of the QMS.",
        "Documented Information",
        "Continuous",
    ),
    (
        "7.5.2",
        "Creating and Updating Documented Information",
        "When creating and updating documented information, ensure appropriate identification "
        "and description, format and media, and review/approval for suitability and adequacy.",
        "Documented Information",
        "Continuous",
    ),
    (
        "7.5.3",
        "Control of Documented Information",
        "Documented information required by QMS shall be controlled to ensure availability and "
        "suitability for use where and when needed, and adequately protected. Address distribution, "
        "access, retrieval, use, storage, preservation, version control, retention, and disposition.",
        "Documented Information",
        "Continuous",
    ),
    # ── Clause 8: Operation ──────────────────────────────────────────────────
    (
        "8.1",
        "Operational Planning and Control",
        "Plan, implement, control, monitor, and review processes needed to meet product/service "
        "provision requirements and implement the actions from Clause 6. Establish criteria for "
        "processes and conformity of products/services, control processes per criteria, retain "
        "documented information to demonstrate processes as planned and product/service conformity.",
        "Operation",
        "Continuous",
    ),
    (
        "8.2.1",
        "Requirements for Products and Services — Customer Communication",
        "Establish processes for communicating with customers on: product/service information, "
        "enquiries, contracts, order handling including amendments, customer feedback including "
        "complaints, handling/controlling customer property, and specific requirements for "
        "contingency actions.",
        "Operation",
        "Continuous",
    ),
    (
        "8.2.2",
        "Requirements for Products and Services — Determining Requirements",
        "Determine requirements for products and services offered to customers, including "
        "applicable statutory and regulatory requirements, and requirements considered necessary "
        "by the organization.",
        "Operation",
        "As needed",
    ),
    (
        "8.2.3",
        "Requirements for Products and Services — Review of Requirements",
        "Ensure the organization has ability to meet requirements before committing to supply. "
        "Conduct reviews prior to commitment, retain documented information on results and "
        "new/changed requirements, and ensure relevant persons are made aware of changes.",
        "Operation",
        "As needed",
    ),
    (
        "8.2.4",
        "Requirements for Products and Services — Changes to Requirements",
        "Ensure documented information is amended and relevant persons are made aware of changed "
        "requirements when requirements for products and services are changed.",
        "Operation",
        "As needed",
    ),
    (
        "8.3.1",
        "Design and Development — General",
        "Establish, implement, and maintain a design and development process appropriate to ensure "
        "the subsequent provision of products and services.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.3.2",
        "Design and Development — Planning",
        "Determine stages and controls for design and development: nature, duration, complexity, "
        "process stages, review/verification/validation activities, responsibilities and authorities, "
        "internal and external resources, interfaces, involvement of customers/users/other parties, "
        "requirements for subsequent provision, required level of control, documented information.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.3.3",
        "Design and Development — Inputs",
        "Determine requirements essential for the specific types of products and services being "
        "designed/developed: functional and performance requirements, applicable statutory/regulatory, "
        "standards and codes of practice, potential failure consequences. Resolve conflicts.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.3.4",
        "Design and Development — Controls",
        "Apply controls during design and development to ensure: results are defined; reviews are "
        "performed to evaluate the ability to meet requirements; verification is performed; "
        "validation is performed; problems are resolved before proceeding. Retain documented information.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.3.5",
        "Design and Development — Outputs",
        "Ensure design and development outputs: meet input requirements, are adequate for the "
        "subsequent processes for provision, include or reference monitoring and measuring "
        "requirements, specify product and service characteristics essential for intended purpose.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.3.6",
        "Design and Development — Changes",
        "Identify, review, and control changes made during or subsequent to design and development "
        "to ensure no adverse impact on conformity. Retain documented information on changes, "
        "review results, authorization, actions taken to prevent adverse impacts.",
        "Design & Development",
        "As needed",
    ),
    (
        "8.4.1",
        "Control of Externally Provided Processes — General",
        "Ensure externally provided processes, products, and services conform to requirements. "
        "Determine controls for external provision when: external provider's products/services "
        "are incorporated into own, products/services are provided directly to customer on behalf, "
        "or process/part of process is provided as result of decision to outsource.",
        "External Providers",
        "Annual review",
    ),
    (
        "8.4.2",
        "Control of Externally Provided Processes — Type and Extent of Control",
        "Ensure externally provided processes, products and services do not adversely affect "
        "organization's ability to deliver conforming products/services. Communicate requirements "
        "for processes/products/services/methods/equipment/competence, and verification/validation.",
        "External Providers",
        "Annual review",
    ),
    (
        "8.4.3",
        "Control of Externally Provided Processes — Information for External Providers",
        "Communicate to external providers requirements for: processes/products/services, "
        "approval of products/services/methods/processes/equipment, competence including required "
        "personnel qualifications, interactions with organization, control and monitoring of "
        "external provider performance, verification activities.",
        "External Providers",
        "Annual review",
    ),
    (
        "8.5.1",
        "Production and Service Provision — Control",
        "Implement production and service provision under controlled conditions including: "
        "availability of documented information, suitable monitoring/measuring resources, "
        "suitable infrastructure and environment, competent persons, validation and periodic "
        "revalidation of processes, implementation of actions to prevent human error, "
        "implementation of release/delivery/post-delivery activities.",
        "Production & Service Provision",
        "Continuous",
    ),
    (
        "8.5.2",
        "Production and Service Provision — Identification and Traceability",
        "Use suitable means to identify outputs when necessary to ensure conformity. Identify "
        "the status of outputs with respect to monitoring and measurement requirements throughout "
        "production and service provision. Control unique identification of output when traceability "
        "is a requirement and retain documented information.",
        "Production & Service Provision",
        "Continuous",
    ),
    (
        "8.5.3",
        "Production and Service Provision — Property Belonging to Customers or External Providers",
        "Exercise care with property belonging to customers or external providers while under "
        "organization control or being used. Identify, verify, protect, and safeguard customer/ "
        "external provider property. Report loss, damage, or unsuitability and retain documented information.",
        "Production & Service Provision",
        "Continuous",
    ),
    (
        "8.5.4",
        "Production and Service Provision — Preservation",
        "Preserve outputs during production and service provision to ensure conformity. Preservation "
        "includes identification, handling, contamination control, packaging, storage, transmission/ "
        "transportation, and protection.",
        "Production & Service Provision",
        "Continuous",
    ),
    (
        "8.5.5",
        "Production and Service Provision — Post-Delivery Activities",
        "Meet requirements for post-delivery activities associated with products and services. "
        "Consider statutory/regulatory requirements, potential consequences, nature/use/intended "
        "lifetime, customer requirements, and customer feedback.",
        "Production & Service Provision",
        "As needed",
    ),
    (
        "8.5.6",
        "Production and Service Provision — Control of Changes",
        "Review and control unplanned changes for production or service provision to ensure "
        "continuing conformity. Retain documented information describing results of change review, "
        "authorizing persons, and necessary actions.",
        "Production & Service Provision",
        "As needed",
    ),
    (
        "8.6",
        "Release of Products and Services",
        "Implement planned arrangements, at appropriate stages, to verify that product/service "
        "requirements have been met. Release shall not proceed until planned arrangements are "
        "satisfactorily completed or approved by relevant authority. Retain documented information "
        "on release including conformity evidence and traceability to authorizing persons.",
        "Operation",
        "Continuous",
    ),
    (
        "8.7",
        "Control of Nonconforming Outputs",
        "Ensure outputs not conforming to their requirements are identified and controlled to "
        "prevent unintended use or delivery. Take appropriate action based on the nature of the "
        "nonconformity and its effect on conformity. Retain documented information on nonconformities, "
        "actions taken, concessions obtained, and identification of authorizing persons.",
        "Operation",
        "As needed",
    ),
    # ── Clause 9: Performance Evaluation ─────────────────────────────────────
    (
        "9.1.1",
        "Monitoring, Measurement, Analysis and Evaluation — General",
        "Determine what needs to be monitored and measured, methods for monitoring/measurement/ "
        "analysis/evaluation, when monitoring/measuring shall be performed, and when results "
        "shall be analyzed/evaluated. Evaluate performance and effectiveness. Retain documented information.",
        "Performance Evaluation",
        "Quarterly",
    ),
    (
        "9.1.2",
        "Monitoring, Measurement, Analysis and Evaluation — Customer Satisfaction",
        "Monitor customers' perceptions of the degree to which their needs and expectations have "
        "been fulfilled. Determine methods for obtaining, monitoring, and reviewing this information. "
        "Examples include customer surveys, feedback, meetings, warranty claims, dealer reports.",
        "Performance Evaluation",
        "Quarterly",
    ),
    (
        "9.1.3",
        "Monitoring, Measurement, Analysis and Evaluation — Analysis and Evaluation",
        "Analyze and evaluate appropriate data and information arising from monitoring and "
        "measurement. Use results to evaluate conformity of products/services, degree of customer "
        "satisfaction, QMS performance/effectiveness, planning effectiveness, risk/opportunity actions, "
        "external provider performance, and improvement needs.",
        "Performance Evaluation",
        "Quarterly",
    ),
    (
        "9.2.1",
        "Internal Audit — Programme",
        "Conduct internal audits at planned intervals to provide information on whether the QMS "
        "conforms to organization's requirements and ISO 9001 requirements, and is effectively "
        "implemented and maintained. Establish, implement, and maintain an audit programme "
        "including frequency, methods, responsibilities, planning requirements, and reporting.",
        "Performance Evaluation",
        "Annual",
    ),
    (
        "9.2.2",
        "Internal Audit — Conduct",
        "Define audit criteria and scope for each audit, select auditors ensuring objectivity "
        "and impartiality, ensure results are reported to relevant management, take timely "
        "corrections and corrective actions without undue delay. Retain documented information "
        "as evidence of audit programme implementation and audit results.",
        "Performance Evaluation",
        "Annual",
    ),
    (
        "9.3.1",
        "Management Review — General",
        "Top management shall review the organization's QMS at planned intervals to ensure "
        "its continuing suitability, adequacy, effectiveness, and alignment with strategic direction.",
        "Performance Evaluation",
        "Annual",
    ),
    (
        "9.3.2",
        "Management Review — Inputs",
        "Plan and carry out management review considering: status of actions from previous reviews; "
        "changes in external/internal issues relevant to QMS; information on QMS performance/effectiveness "
        "(trends in customer satisfaction, quality objective achievement, process performance/conformity, "
        "nonconformities/corrective actions, monitoring/measurement/audit results, external provider performance); "
        "resource adequacy; effectiveness of risk/opportunity actions; opportunities for improvement.",
        "Performance Evaluation",
        "Annual",
    ),
    (
        "9.3.3",
        "Management Review — Outputs",
        "Outputs of management review shall include decisions and actions related to: opportunities "
        "for improvement; any need for changes to the QMS; resource needs. Retain documented "
        "information as evidence of management review results.",
        "Performance Evaluation",
        "Annual",
    ),
    # ── Clause 10: Improvement ───────────────────────────────────────────────
    (
        "10.1",
        "Improvement — General",
        "Determine and select opportunities for improvement and implement necessary actions to "
        "meet customer requirements and enhance customer satisfaction. Include improving products/ "
        "services, correcting/preventing/reducing undesired effects, and improving QMS performance "
        "and effectiveness.",
        "Improvement",
        "Continuous",
    ),
    (
        "10.2.1",
        "Nonconformity and Corrective Action — Responding",
        "When a nonconformity occurs: react to nonconformity and take action to control/correct "
        "and deal with consequences; evaluate need to eliminate cause(s) to prevent recurrence/ "
        "occurrence elsewhere; implement actions needed; review effectiveness; update risks/ "
        "opportunities if necessary; make changes to QMS if necessary.",
        "Improvement",
        "As needed",
    ),
    (
        "10.2.2",
        "Nonconformity and Corrective Action — Documented Information",
        "Retain documented information as evidence of the nature of nonconformities and actions "
        "taken, and results of corrective actions.",
        "Improvement",
        "As needed",
    ),
    (
        "10.3",
        "Continual Improvement",
        "Continually improve the suitability, adequacy, and effectiveness of the QMS. Consider "
        "results of analysis and evaluation, and outputs of management review, to determine if "
        "there are needs or opportunities that shall be addressed as part of continual improvement.",
        "Improvement",
        "Continuous",
    ),
]

# ---------------------------------------------------------------------------
# Design & Development applicability marker
# Controls in Clause 8.3 are conditionally applicable only when the tenant
# performs design and/or development activities.
# ---------------------------------------------------------------------------

DESIGN_AND_DEVELOPMENT_SUBCLAUSES: frozenset[str] = frozenset(
    {"8.3.1", "8.3.2", "8.3.3", "8.3.4", "8.3.5", "8.3.6"}
)

# External provider controls (8.4.x) are conditionally applicable when the
# tenant uses external providers, outsources processes, or resells external
# products/services.
EXTERNAL_PROVIDER_SUBCLAUSES: frozenset[str] = frozenset({"8.4.1", "8.4.2", "8.4.3"})

# Post-delivery activities (8.5.5) conditional on having post-delivery obligations.
POST_DELIVERY_SUBCLAUSES: frozenset[str] = frozenset({"8.5.5"})

# ---------------------------------------------------------------------------
# Build all lists from clause data
# ---------------------------------------------------------------------------

ISO_9001_CONTROLS: list[PackControlDefinition] = []
ISO_9001_SOURCE_REQS: list[PackSourceRequirementDefinition] = []
ISO_9001_MAPPINGS: list[PackMappingDefinition] = []
ISO_9001_EVIDENCE: list[PackEvidenceDefinition] = []
ISO_9001_COVERAGE: list[PackCoverageDefinition] = []

for _idx, (_subclause, _title, _desc, _category, _cadence) in enumerate(QMS_CLAUSES, start=1):
    _ctrl_id = f"QMS-{_subclause.replace('.', '-')}"
    _src_ref = f"ISO 9001:2015 Clause {_subclause}"

    # ── applicability_criteria ────────────────────────────────────────────
    _criteria: dict = {}
    if _subclause in DESIGN_AND_DEVELOPMENT_SUBCLAUSES:
        _criteria["requires_design_and_development"] = True
    if _subclause in EXTERNAL_PROVIDER_SUBCLAUSES:
        _criteria["requires_external_providers"] = True
    if _subclause in POST_DELIVERY_SUBCLAUSES:
        _criteria["requires_post_delivery_activities"] = True

    # ── guidance ─────────────────────────────────────────────────────────
    _dd_note = (
        "\n\n> **Applicability:** Applies only if the organization performs "
        "design and/or development activities (see Clause 8.3 applicability rules)."
        if _subclause in DESIGN_AND_DEVELOPMENT_SUBCLAUSES
        else ""
    )
    _ep_note = (
        "\n\n> **Applicability:** Applies only if the organization uses external "
        "providers, outsources processes, or provides externally sourced products/services "
        "to customers (see Clause 8.4 applicability rules)."
        if _subclause in EXTERNAL_PROVIDER_SUBCLAUSES
        else ""
    )
    _pd_note = (
        "\n\n> **Applicability:** Applies when the organization has defined post-delivery "
        "obligations (e.g., warranty support, maintenance, recycling, final disposal)."
        if _subclause in POST_DELIVERY_SUBCLAUSES
        else ""
    )

    # Map categories to suitable evidence types and confidentiality
    if _category == "Documented Information":
        _evid_type = "DOCUMENT"
        _confid = "Internal"
        _obs_period = None
        _validity = 365
        _review_cadence = 365
    elif _category == "Performance Evaluation":
        _evid_type = "RECORD"
        _confid = "Internal"
        _obs_period = 90
        _validity = 365
        _review_cadence = 90
    elif _category == "Improvement":
        _evid_type = "RECORD"
        _confid = "Internal"
        _obs_period = None
        _validity = 365
        _review_cadence = 180
    elif _category in ("Operation", "Production & Service Provision", "Design & Development"):
        _evid_type = "RECORD"
        _confid = "Internal"
        _obs_period = 90 if "Continuous" in _cadence else None
        _validity = 365
        _review_cadence = 180
    else:
        _evid_type = "DOCUMENT"
        _confid = "Internal"
        _obs_period = None
        _validity = 365
        _review_cadence = 365

    _guidance = (
        f"**Implementation Guidance:** Implement and maintain operational QMS procedures "
        f"for {_title}. Document the approach, assign responsibility, and ensure processes "
        f"are periodically reviewed for continued effectiveness.\n\n"
        f"**Evidence Requests:**\n"
        f"- Documented procedure or process description for {_src_ref}\n"
        f"- Records demonstrating the process is implemented and maintained\n"
        f"- Review/audit findings related to this requirement\n\n"
        f"**Review Cadence:** {_cadence}\n"
        f"**Policy Reference:** Quality Management System Manual / {_category} Procedure\n"
        f"**Audit Procedure:** Review documented information for existence and adequacy; "
        f"interview process owners; examine objective evidence of implementation "
        f"(records, data, outputs)." + _dd_note + _ep_note + _pd_note
    )

    ISO_9001_CONTROLS.append(
        PackControlDefinition(
            identifier=_ctrl_id,
            title=_title,
            description=_desc,
            category=_category,
            guidance=_guidance,
            sort_order=_idx * 10,
            applicability_criteria=_criteria if _criteria else {},
        )
    )

    ISO_9001_SOURCE_REQS.append(
        PackSourceRequirementDefinition(
            source_reference=_src_ref,
            title=_title,
            requirement_type=SourceRequirementType.CLAUSE,
            source_authority=QMS_AUTHORITY,
            edition_or_amendment=QMS_EDITION,
            source_text=_desc,
            content_rights=QMS_RIGHTS,
            source_url=QMS_URL,
            conformly_guidance=_guidance,
            assessment_procedure=(
                f"Review documented information and records for {_src_ref}; "
                f"confirm process owner assignment; evaluate objective evidence of implementation."
            ),
            default_owner_role="Quality Manager",
            review_cadence=_cadence,
            sort_order=_idx * 10,
        )
    )

    ISO_9001_MAPPINGS.append(
        PackMappingDefinition(
            source_reference=_src_ref,
            control_identifier=_ctrl_id,
            mapping_type=MappingType.SATISFIES,
            rationale=f"QMS control {_ctrl_id} directly satisfies {_src_ref}.",
        )
    )

    ISO_9001_EVIDENCE.append(
        PackEvidenceDefinition(
            identifier=f"EVID-QMS-{_subclause.replace('.', '-')}",
            title=f"Evidence: {_title}",
            description=(
                f"Documented information or operational records demonstrating conformity with "
                f"{_src_ref}. May include: quality manual section, procedure document, "
                f"completed records, audit reports, or management review minutes."
            ),
            evidence_type=_evid_type,
            control_identifier=_ctrl_id,
            source_reference=_src_ref,
            original_file_required=False,
            observation_period_days=_obs_period,
            validity_period_days=_validity,
            review_cadence_days=_review_cadence,
            confidentiality_level=_confid,
            suggested_storage_format="PDF or DOCX",
        )
    )

    ISO_9001_COVERAGE.append(
        PackCoverageDefinition(
            source_reference=_src_ref,
            disposition=CoverageDisposition.IMPLEMENTED,
            rationale=(
                f"Clause {_subclause} fully covered by canonical control {_ctrl_id} "
                f"with structured evidence specification and implementation guidance."
            ),
        )
    )

# ---------------------------------------------------------------------------
# Pack definition
# ---------------------------------------------------------------------------

ISO_9001_PACK = FrameworkPackDefinition(
    slug="iso-9001",
    name="ISO 9001:2015 Quality Management System Pre-Audit Readiness",
    version="v2015",
    description=(
        "Comprehensive pre-audit readiness pack for ISO 9001:2015 Quality Management Systems. "
        "Covers all addressable subclauses of Clauses 4–10: Context (4.x), Leadership (5.x), "
        "Planning (6.x), Support (7.x), Operation (8.x), Performance Evaluation (9.x), and "
        "Improvement (10.x). Includes structured evidence specifications, applicability rules "
        "for Design & Development (Clause 8.3) and External Providers (Clause 8.4), and "
        "deterministic readiness evaluation. Conformly provides original pre-audit guidance "
        "only; no proprietary ISO standard text is reproduced."
    ),
    release_notes=(
        "Initial production release covering all addressable ISO 9001:2015 Clauses 4–10 subclauses. "
        "Design and Development (8.3.x) controls include applicability scope-out rules for "
        "service-only organizations. External provider controls (8.4.x) include applicability "
        "scope-out rules for organizations without outsourced processes or external providers."
    ),
    legal_review_notes=(
        "ISO 9001:2015 is a proprietary standard owned by ISO/TC 176/SC 2. This pack provides an "
        "original Conformly pre-audit readiness taxonomy structured around clause references. "
        "No verbatim ISO standard text has been reproduced. Independent IP counsel review is "
        "required prior to production customer issuance to confirm all control guidance, evidence "
        "descriptions, and implementation procedures do not infringe ISO copyright."
    ),
    approval_notes=(
        "Admitted to Module A Beta per explicit Product Owner decision, 2026-09-13 (ADR D-059). "
        "Engineering complete. Content_state: DRAFT_REVISION_UNDERWAY. "
        "Requires independent legal/IP review and second-person approval before RELEASED state."
    ),
    controls=ISO_9001_CONTROLS,
    source_requirements=ISO_9001_SOURCE_REQS,
    mappings=ISO_9001_MAPPINGS,
    evidence_specifications=ISO_9001_EVIDENCE,
    coverage_ledger=ISO_9001_COVERAGE,
)
