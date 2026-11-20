import type { TranslationDictionary } from "../types";



export const en: TranslationDictionary = {

  common: {

    save: "Save",

    cancel: "Cancel",

    delete: "Delete",

    confirm: "Confirm",

    loading: "Loading...",

    filter: "Filter",

    export: "Export",

    dismiss: "Dismiss",

    back: "Back",

    close: "Close",

    status: "Status",

    actions: "Actions",

    search: "Search...",

    refresh: "Refresh",

    view: "View",

    edit: "Edit",

    completed: "Completed",

    inProgress: "In Progress",

    pending: "Pending",

    optional: "Optional",

    required: "Required",

    all: "All",

    yes: "Yes",

    no: "No",

  },

  nav: {

    platform: "Platform",

    overview: "Overview",

    onboarding: "Onboarding",

    organization: "Organization",

    frameworks: "Frameworks",

    compliance: "Compliance",

    risks: "Risk Register",

    assets: "Asset Register",

    vendors: "Vendor Register",

    preaudit: "Pre-Audit",

    trustCenter: "Trust Center",

    lifecycle: "Export & Data",

    members: "Members",

    signOut: "Sign out",

    organizationLabel: "Organization",

  },

  disclaimer: {

    badge: "Notice",

    title: "Conformly is an audit-readiness and compliance operations platform, not an accredited certification body.",

    text: "Pre-audit assessments, readiness scores, and Conformly-issued badges reflect deterministic evidence checks and internal readiness posture; they do not constitute official accredited third-party certifications.",

  },

  onboarding: {

    title: "Pre-Audit Readiness Onboarding",

    subtitle: "Complete these foundational milestones to prepare your organization for third-party compliance audits.",

    pilotOperational: "Pilot Operational",

    eyebrow: "Operational Readiness • Active Pilot",

    orgSlug: "Organization Slug",

    role: "Role",

    checklistTitle: "Milestone Checklist",

    checklistSubtitle: "Track and save your progress across key audit preparation tasks.",

    progressBarLabel: "Onboarding completion progress",

    stepsCompleted: "{completed} of {total} milestones completed ({percent}%)",

    allMilestonesComplete: "🎉 All Onboarding Milestones Complete!",

    allMilestonesCompleteSub: "Your organization is fully configured and ready for deterministic pre-audit assessments.",

    resetProgress: "Reset Progress",

    markCompleted: "Mark as Completed",

    markIncomplete: "Mark as Pending",

    step1Title: "Adopt Canonical Compliance Framework",

    step1Desc: "Select official frameworks (ISO/IEC 27001, SOC 2, HIPAA) or define custom overlays.",

    step1Btn: "View Catalog",

    step2Title: "Implement Controls & Collect Evidence",

    step2Desc: "Upload evidence with AES-256-GCM envelope encryption and map controls to policies.",

    step2Btn: "Open Compliance",

    step3Title: "Run Pre-Audit Readiness Check",

    step3Desc: "Execute deterministic scoring, generate SHA-256 audit manifests, and issue readiness credentials.",

    step3Btn: "Start Pre-Audit",

    step4Title: "Publish Public Trust Center",

    step4Desc: "Showcase security commitments, verified readiness credentials, and third-party certifications.",

    step4Btn: "Trust Center",

    step5Title: "Configure Anonymous Whistleblower Channel",

    step5Desc: "Provide confidential reporting protected by PBKDF2 hash tracking and zero IP logging.",

    step5Btn: "Whistleblower Portal",

    supportTitle: "Pilot Service & Support Intake",

    supportSubtitle: "24/7 Security Intake • Business-Hours Operations",

    supportNotice: "During the paid pilot program, service targets represent operational response guidelines (not contractual SLAs). Contractual SLAs are phased in following six months of production telemetry.",

    thSeverity: "Severity Level",

    thClassification: "Classification",

    thResponse: "Response Objective",

    thChannel: "Intake Channel",

    securityRlsTitle: "Row-Level Security",

    securityRlsDesc: "Strict kernel-enforced tenant boundaries on every SQL query.",

    securityAesTitle: "AES-256-GCM Encryption",

    securityAesDesc: "Unique DEK per file; zero unencrypted evidence at rest.",

    securityWhistleTitle: "Anonymous Whistleblower",

    securityWhistleDesc: "PBKDF2 return keys with zero IP address or telemetry logging.",

    securityExitTitle: "Auditable Data Exit",

    securityExitDesc: "30-day export window, 90-day multi-table cryptographic deletion proof.",

  },

  dashboard: {

    title: "Executive Compliance Dashboard",

    subtitle: "Real-time posture, readiness tracking, and operational health.",

    readinessScore: "Audit Readiness Score",

    runPreAuditBtn: "Run Pre-Audit Check",

    continuousTitle: "Continuous Compliance Evaluation Completed",

    continuousDesc: "{tasks} remediation task(s) created • {notifications} notification(s) queued • {overdue} overdue task(s) escalated",

    adminNotice: "Administrator isolation mode active. Confidential whistleblower items and Restricted evidence payloads are authorization-gated.",

  },

  status: {

    loadingTitle: "Loading Conformly",

    signedOutTitle: "Conformly",

    signedOutDetail: "Secure compliance operations for audit readiness.",

    signInBtn: "Sign in",

    expiredTitle: "Session expired",

    expiredDetail: "Sign in again to continue.",

    deniedTitle: "Access denied",

    deniedDetail: "Your account cannot access that tenant.",

    noTenantTitle: "No tenant available",

    noTenantDetail: "Your account has no active Conformly membership. Ask an administrator for access.",

    eyebrow: "Secure compliance operations",

  },

  language: {

    selectorLabel: "Select language",

  },

  customerDemo: {

    title: "Customer Onboarding and Workspace",

    subtitle: "Interactive synthetic compliance exploration and onboarding journey",

    syntheticNotice: "Notice: Synthetic customer onboarding demonstration. Not legal or compliance advice.",

    answersRevision: "Answers Revision",

    selectionRevision: "Selection Revision",

    companyProfileTitle: "1. Organization Profile and Facts",

    companyProfileSubtitle: "Select a profile preset or customize answers to evaluate rule applicability",

    fictionalPreset: "Fictional Company Preset:",

    alphaName: "Alpha (Cloud/EU)",

    alphaDesc: "Cloud-native workload operating within the European Union",

    betaName: "Beta (Non-Cloud/Global)",

    betaDesc: "On-premises/hybrid infrastructure across global jurisdictions",

    questionnaireTitle: "Applicability Questionnaire",

    questionnaireSubtitle: "Deterministic facts utilized by compliance rules engine",

    cloudQuestion: "Does your organization utilize public or private cloud infrastructure?",

    cloudYes: "Yes",

    cloudNo: "No",

    cloudUnknown: "Unknown",

    regionQuestion: "Primary geographic region of operation",

    regionEu: "European Union (EU)",

    regionOther: "Other Jurisdictions",

    regionUnknown: "Unknown",

    saveAnswers: "Save Answers",

    saving: "Saving...",

    answersSaved: "Answers saved successfully as immutable revision.",

    unsavedEdits: "Unsaved changes",

    savedRevisionBadge: "Saved Revision",

    evaluateTitle: "2. Framework Evaluation and Controls",

    evaluateSubtitle: "Compute deterministic requirement applicability based on persisted facts",

    selectPackLabel: "Demo Framework Pack:",

    evaluateBtn: "Evaluate Applicability",

    evaluating: "Evaluating...",

    saveFirstNotice: "Save answers first before evaluating",

    evaluationResults: "Evaluation Results",

    evaluationResultsSubtitle: "Evaluated against Answer Revision",

    adoptPackBtn: "Adopt Pack",

    adopting: "Adopting...",

    adoptTitle: "Adopt Demo Pack",

    adoptSubtitle: "Review pack requirements, controls, and differences before confirming adoption.",

    adoptionIntentInvalidated: "The adoption snapshot, candidate selection, or session has changed. Please close and re-evaluate.",

    adoptSuccess: "Demo pack adopted successfully.",

    confirmAdopt: "Confirm Adoption",

    packComparisonTitle: "Exact Pack Comparison",

    hideComparison: "Hide Comparison",

    comparePacks: "Compare Packs",

    unchangedReqs: "Unchanged requirements",

    addedReqs: "+ Added in",

    removedReqs: "- Removed in",

    exactVersions: "Exact Requirement Versions:",

    currentAdoption: "Current Adoption",

    noAdoption: "No Pack Adopted Yet",

    staleNotice: "(Stale: Answers Updated)",

    ackSyntheticLabel: "I understand this is a synthetic demonstration framework and control mapping for demonstration purposes only, not legal or regulatory advice.",

    ackMissingLabel: "I acknowledge that some requirements evaluated to NEEDS_INFORMATION due to missing organization facts and will require further information.",

    statusApplicable: "APPLICABLE",

    statusNotApplicable: "NOT APPLICABLE",

    statusNeedsInfo: "NEEDS INFORMATION",

    summaryApplicable: "Applicable",

    summaryNotApplicable: "Not Applicable",

    summaryNeedsInfo: "Needs Information",

    summaryTruthfulNotice: "Synthetic outcome counts based on saved profile facts. Not a compliance certification or readiness score.",

    controlsCount: "rules",

    controlMapping: "Common Control:",

    viewExplanation: "View Explanation",

    hideExplanation: "Hide Explanation",

    missingFacts: "Missing facts:",

    noEvaluationYet: "No evaluation computed yet. Click 'Evaluate Applicability' above.",

    reloadWorkspace: "Reload Workspace",

    savedProgress: "Onboarding Progress",

    stepsSaved: "Facts Saved",

    historyTitle: "3. Adoption History and Audit Trail",

    historySubtitle: "Immutable ledger of adopted framework versions and digests",

    historyEmpty: "No historical adoptions recorded yet.",

    accessDeniedTitle: "Access Denied",

    accessDeniedDetail: "Whole-tenant Owner or Compliance Manager role required.",

    conflictTitle: "Workspace Conflict",

    stepProfile: "1. Company Profile",

    stepEvaluation: "2. Rule Evaluation",

    stepAdoption: "3. Pack Adoption",

    nextStep: "Continue",

    prevStep: "Back",

    syntheticDemo: "Synthetic Demo",

    evaluationOnly: "Evaluation Only",

    stepperAriaLabel: "Customer onboarding steps",

    noticeAriaLabel: "Synthetic demo notice",

    dismissMessage: "Dismiss message",

    errorLabel: "Error",

    noticeLabel: "Notice",

    successLabel: "Success",

    requirementVersion: "Requirement Version",

    packVersionId: "Pack Version ID",

    bundleDigest: "Bundle Digest",

    adoptedTimestamp: "Adopted Timestamp",

    staleEvaluation: "Stale Evaluation",

    stepCompleted: "Completed",

    // MVP-B Control Work & Evidence

    controlWorkTitle: "Control Work & Evidence Pinning",

    controlWorkSubtitle: "Assign control owners, set target due dates, upload and pin encrypted evidence, and conduct suitability reviews.",

    initWorkBtn: "Initialize Control Work",

    initializingWork: "Initializing...",

    initWorkNotice: "Initialize work items mapped to the currently adopted pack requirements.",

    noControlWorkYet: "No control work items initialized yet for this adoption.",

    assignOwnerLabel: "Owner",

    dueDateLabel: "Target Due Date",

    unassignedOwner: "Unassigned",

    saveAssignmentBtn: "Update Assignment",

    savingAssignment: "Saving...",

    uploadEvidenceTitle: "Upload & Pin Scanned Evidence",

    uploadAndLinkBtn: "Upload & Pin",

    uploadingEvidence: "Uploading & scanning...",

    selectFileLabel: "Select Evidence File (max 1 MiB)",

    validUntilLabel: "Evidence Validity Date",

    rationaleLabel: "Suitability Rationale",

    rationalePlaceholder: "Describe why this evidence is suitable for this control...",

    reuseEvidenceTitle: "Deliberate Evidence Reuse",

    reuseEvidenceBtn: "Reuse Revision",

    reusingEvidence: "Linking...",

    selectEvidenceToReuse: "Select Existing Evidence Revision",

    reviewTitle: "Record Suitability Review",

    recordReviewBtn: "Save Review",

    recordingReview: "Saving...",

    acceptDecision: "Accept (Suitable)",

    rejectDecision: "Reject (Unsuitable)",

    reviewDecisionLabel: "Review Decision",

    reviewRationalePlaceholder: "Document review rationale and verification notes...",

    historyEventsTitle: "Control Work Revision History",

    viewHistoryBtn: "View History",

    hideHistoryBtn: "Hide History",

    downloadPinnedFileBtn: "Download File",

    evidenceValidityAvailable: "Available",

    evidenceValidityMissing: "Missing File",

    evidenceValidityNotYetValid: "Not Yet Valid",

    evidenceValidityExpired: "Expired",

    evidenceValidityQuarantined: "Quarantined",

    evidenceValidityUnavailable: "Unavailable / Tampered",

    evidenceValidityUnverified: "Unverified Scan Proof",

    scanStatusScannedAtLink: "Scanned at Link",

    scanStatusUnverified: "Unverified",

    reviewStatusPending: "Pending Review",

    reviewStatusAccepted: "Accepted",

    reviewStatusRejected: "Rejected",

    workVersionLabel: "Version",

    staleWorkNotice: "Work item belongs to a prior answers or pack revision; mutations are disabled.",

    scannerUnavailableNotice: "Antivirus scanner unavailable or verification failed; evidence pinning blocked.",

    eventInitialized: "Work Initialized",

    eventOwnerUpdated: "Assignment Updated",

    eventEvidenceLinked: "Evidence Linked",

    eventEvidenceReviewed: "Suitability Reviewed",

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: "Human Assessment & Audit Readiness",

    assessmentWorkSubtitle: "Conduct human assessments against synthetic procedures, manage findings and remediation, record explicit retests, and inspect truthful readiness summaries.",

    assessmentProcedureTitle: "Synthetic Evaluation Procedure",

    procedureDisclaimer: "Synthetic Evaluation Procedure — Human review required for compliance determination.",

    criteriaTitle: "Evaluation Criteria",

    criterionImplementation: "Implementation Verification",

    criterionEvidence: "Evidence Sufficiency",

    criterionOperation: "Operational Effectiveness",

    resultPass: "Pass",

    resultPartial: "Partial",

    resultFail: "Fail",

    resultInsufficientEvidence: "Insufficient Evidence",

    rationaleInputPlaceholder: "Document detailed assessment rationale and verification notes...",

    recordAssessmentBtn: "Record Human Assessment",

    recordingAssessment: "Recording Assessment...",

    findingsTitle: "Deficiency Findings",

    noFindingsYet: "No deficiency findings recorded for this control.",

    findingSeverity: "Severity",

    findingStatus: "Status",

    findingOwner: "Assigned Owner",

    findingDueDate: "Target Date",

    findingRemediationNote: "Remediation Progress Note",

    updateFindingBtn: "Update Remediation",

    updatingFinding: "Saving...",

    retestTitle: "Record Explicit Retest",

    retestBtn: "Record Retest",

    recordingRetest: "Recording Retest...",

    selectFindingToResolve: "Select Finding to Resolve",

    readinessSummaryTitle: "Truthful Audit Readiness Summary",

    summaryTotalControls: "Total Controls",

    summaryPass: "Passed",

    summaryUnassessed: "Unassessed",

    summaryBlocked: "Blocked Controls",

    summaryOpenFindings: "Open Findings",

    summaryInRemediation: "In Remediation",

    summaryResolvedFindings: "Resolved Findings",

    summaryStaleAssessment: "Stale Assessments",

    summaryReasonCodes: "Block Reasons",

    statusUnassessed: "UNASSESSED",

    statusPass: "PASS",

    statusPartial: "PARTIAL",

    statusFail: "FAIL",

    statusInsufficientEvidence: "INSUFFICIENT_EVIDENCE",

    statusStale: "STALE_ASSESSMENT",

    historyJournalTitle: "Immutable Assessment Journal",

    noHistoryEvents: "No assessment events recorded yet.",

    selectEvaluation: "-- Select evaluation --",

    selectFindingToRetest: "-- Select finding to retest --",

    selectResult: "-- Select result --",

    selectRetestOutcome: "-- Select retest outcome --",

    selectSeverity: "-- Select severity --",

    noUnresolvedFindings: "No unresolved findings to retest.",

    associatedEvidence: "Associated Evidence",

    evaluationRequirements: "Evaluation Requirements",

    loadingHistory: "Loading history...",

    sessionExpired: "Session expired. Please sign in again.",

    saveRemediationBtn: "Save Remediation",

    cancelBtn: "Cancel",

    severityLow: "LOW",

    severityMedium: "MEDIUM",

    severityHigh: "HIGH",

    severityCritical: "CRITICAL",

    statusOpen: "OPEN",

    statusInRemediation: "IN REMEDIATION",

    statusResolved: "RESOLVED",

    resolvesFinding: "(Resolves Finding)",

        createFindingCheckbox: "Record Deficiency Finding",

evidenceRequiredForPass: "At least one evidence link must be selected for PASS",

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: "Pre-audit",
    preauditTitle: "Pre-audit Workflow",
    preauditSubtitle: "Freeze scope, conduct independent review, certify audit readiness, and generate private reports",
    createPreauditBtn: "New Pre-audit Case",
    freezeScopeBtn: "Freeze Scope",
    submitPreauditReviewBtn: "Submit for Review",
    approvePreauditBtn: "Owner Approve",
    cancelPreauditBtn: "Cancel Case",
    downloadReportBtn: "Download Report Archive",
    preauditLeadLabel: "Compliance Lead",
    preauditReviewerLabel: "Independent Reviewer",
    preauditRevisionLabel: "Revision",
    preauditBlockersTitle: "Readiness Blockers",
    preauditHistoryTitle: "Event History",
    preauditNoCases: "No pre-audit cases initiated. Click 'New Pre-audit Case' to freeze current scope and assign reviewers.",

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: "Readiness Verification Lifecycle",
    verificationSubtitle: "Manage synthetic readiness verifications, status transitions, private projections, and audit events",
    issueVerificationBtn: "Issue Verification",
    suspendVerificationBtn: "Suspend Verification",
    revokeVerificationBtn: "Revoke Verification",
    correctVerificationBtn: "Correct Metadata",
    supersedeVerificationBtn: "Supersede Verification",
    reconcileVerificationBtn: "Reconcile Lifecycles",
    viewProjectionBtn: "View Private Projection",
    verificationStatusLabel: "Persisted Status",
    verificationEffectiveLabel: "Effective State",
    verificationValidityLabel: "Validity Window",
    verificationSyntheticDisclaimer: "PRIVATE SYNTHETIC INTERNAL TEST RESULT - NOT AN ACCREDITED CERTIFICATION",
    verificationHistoryTitle: "Verification History",
    verificationLimitationsTitle: "Scope & Limitations",
    verificationNoVerifications: "No readiness verification issued for this approved pre-audit case.",
    verificationReasonPrompt: "Enter reason for this action:",
    verificationConfirmAction: "Confirm Lifecycle Action", 
    supersedeNewCaseIdLabel: "Replacement Pre-audit Case ID",
    supersedeNewRevisionLabel: "Expected Replacement Case Revision",
    supersedeNewSnapshotIdLabel: "Replacement Snapshot ID",
    supersedeNewDigestLabel: "Replacement Snapshot Digest",
    uncertaintyTitle: "Uncertain Operation Recovery",
    uncertaintyRetryBtn: "Retry Operation",
    uncertaintyDismissBtn: "Acknowledge and Dismiss",

  },

  portal: {

    brand: "Conformly Portal",

    navOverview: "Overview",

    navCompanySetup: "Company Setup",

    navFrameworks: "Available Frameworks",

    navControlsEvidence: "Controls & Evidence",

    navAssessmentsFindings: "Assessments & Findings",
    navPreaudit: "Pre-audit",

    welcomeTitle: "Welcome to Conformly Compliance",

    welcomeSubtitle: "Continuous compliance automation, control implementation, and audit readiness.",

    tenantLabel: "Organization",

    roleLabel: "Role",

    quickActionsTitle: "Quick Actions",

    nextActionTitle: "Recommended Next Action",

    nextActionSetup: "Complete your company facts and infrastructure profile to evaluate framework applicability.",

    nextActionAdopt: "Evaluate and adopt a compliance framework pack to generate control work items.",

    nextActionControls: "Assign owners and upload encrypted evidence for your adopted controls.",

    nextActionAssess: "Perform human assessments and resolve findings before the final audit.",

    actionConfigureSetup: "Configure Company Setup",

    actionExploreFrameworks: "Explore Framework Packs",

    actionManageControls: "Manage Controls & Evidence",

    actionRunAssessments: "Run Assessment Procedures",

    cardFrameworkStatus: "Framework Adoption",

    cardControlsStatus: "Control Work Items",

    cardEvidenceStatus: "Evidence & Verification",

    cardAssessmentStatus: "Audit Readiness",

    noPackAdopted: "No pack adopted yet",

    adoptedPack: "Adopted: {name} (rev {rev})",

    stalePackWarning: "Adoption is stale due to updated company answers. Retest or re-evaluate required.",

    controlsCountLabel: "Total Controls",

    evidenceItemsLabel: "Evidence Links",

    reviewsPendingLabel: "Pending Reviews",

    findingsSummaryLabel: "Findings Status",

    openFindingsCount: "Open Findings",

    setupTitle: "Company Setup & Fact Profile",

    setupSubtitle: "Provide verified organizational facts to determine framework and control applicability.",

    saveSetupBtn: "Save Answers",

    savingSetupBtn: "Saving Answers...",

    setupSavedSuccess: "Company facts saved successfully.",

    unsavedChangesBadge: "Unsaved Changes",

    validationErrorsNotice: "Please fix the validation errors below before proceeding.",

    companyCodeRequired: "Company profile selection is required.",

    cloudUsageRequired: "Cloud infrastructure usage must be specified (Yes or No).",

    operatingRegionRequired: "Primary operating region must be selected (EU or Other).",

    frameworksTitle: "Available Frameworks & Packs",

    frameworksSubtitle: "Version-pinned compliance packs, automated applicability rules, and formal adoption.",

    controlsTitle: "Controls & Encrypted Evidence",

    controlsSubtitle: "Track work status, assign control owners, upload scanned evidence, and conduct reviews.",

    assessmentsTitle: "Human Assessments & Findings",

    assessmentsSubtitle: "Evaluate procedures, record audit findings, manage remediation, and perform retests.",
    preauditSubtitle: "Scope freezing, independent reviewer certification, and private readiness reports",

    backToOverview: "Back to Overview",

    truthfulNotice: "Truthful state: all metrics reflect actual recorded data without simulated completion scores.",

    menuToggle: "Toggle navigation menu",

    signOut: "Sign out",

    breadcrumbHome: "Portal",

    skipToContent: "Skip to main content",

    navAriaLabel: "Portal Navigation",

    unsavedChangesGuidance: "You have unsaved changes to your company facts. Click Save Answers to persist.",

    validateBtn: "Validate",

    evaluatingUsesSavedAnswers: "You have unsaved changes in Company Setup. Evaluating will use saved answers.",

    statusNotInitialized: "NOT INITIALIZED",

    statusInProgress: "IN PROGRESS",

    statusUnassessed: "UNASSESSED",

    statusAuditReady: "AUDIT READY",

    statusFindings: "FINDINGS",

    statusPinned: "PINNED",

    statusNone: "NONE",

    statusUnavailable: "UNAVAILABLE",

    statusAllPassed: "ALL PASSED",

    statusStale: "STALE",

    statusAdopted: "ADOPTED",

    statusDenied: "ACCESS DENIED",

    statusBlocked: "BLOCKED",

    evidenceLinksLabel: "{count} links pinned",

    assessmentProgressDetail: "{pass} passed · {findings} open findings · {unassessed} unassessed",

    notAssessed: "Not assessed",

    refreshOverview: "Refresh overview",

    retryLoading: "Retry loading",

    loadingHistory: "Loading history...",

    noHistory: "No history recorded.",

    noEvidenceLinked: "No evidence linked yet.",

    retestOutcome: "Retest Outcome",

    noUnresolvedFindings: "No unresolved findings eligible for retest.",

    retestCriteria: "Retest Evaluation Criteria",

    retestRationale: "Retest Verification Rationale",

    openStatus: "OPEN",

    discardDraftConfirm: "You have unsaved changes in Company Setup. Discard these changes and switch views?",

    discardAndLeave: "Discard changes",

    stayOnPage: "Stay on view",

    keepDraftsNotice: "Draft preserved in memory",

    navOrganization: "Organization",

    orgTitle: "Organization & Structure",

    orgSubtitle: "Manage legal entities, business units, locations, inspect member access directory, and review active plan entitlements.",

    legalEntitiesTitle: "Legal Entities",

    legalEntitiesSubtitle: "Registered corporate and legal entities.",

    createEntityBtn: "Create Legal Entity",

    creatingEntityBtn: "Creating Legal Entity...",

    entityNameLabel: "Legal Entity Name",

    regNumberLabel: "Registration Number",

    countryLabel: "Country (2-letter code)",

    primaryEntityLabel: "Set as primary legal entity",

    primaryBadge: "Primary",

    noEntitiesYet: "No legal entities defined yet. Create your first entity above.",

    businessUnitsTitle: "Business Units",

    businessUnitsSubtitle: "Operational divisions and departments grouped under a legal entity.",

    createUnitBtn: "Create Business Unit",

    creatingUnitBtn: "Creating Business Unit...",

    unitNameLabel: "Business Unit Name",

    unitCodeLabel: "Unit Code",

    selectEntityPrompt: "Select a Legal Entity...",

    noUnitsYet: "No business units defined under this entity yet.",

    locationsTitle: "Locations",

    locationsSubtitle: "Offices, data centers, and physical operating facilities.",

    createLocationBtn: "Create Location",

    creatingLocationBtn: "Creating Location...",

    locationNameLabel: "Location Name",

    cityLabel: "City",

    addressLabel: "Address",

    noLocationsYet: "No locations defined under this entity yet.",

    membersTitle: "People & Access Directory",

    membersSubtitle: "Read-only server directory of authenticated tenant memberships, roles, and status.",

    membersDenied: "Access Denied: You lack membership:read capability to view the member directory.",

    noMembersYet: "No members returned by directory service.",

    entitlementsTitle: "Active Plan & Entitlements",

    entitlementsSubtitle: "Read-only subscription plan tiers, enabled modules, and capacity quotas.",

    entitlementsDenied: "Access Denied: You lack entitlement:read capability to inspect tenant entitlements.",

    planLabel: "Current Plan",

    maxMembersLabel: "Member Limit",

    storageLimitLabel: "Storage Limit",

    modulesLabel: "Enabled Modules",

    allowedFrameworksLabel: "Allowed Frameworks",

    versionInspectorTitle: "Framework Version Inspector",

    versionInspectorSubtitle: "Deterministic comparison of synthetic framework pack versions, requirements, version pins, and adoption history.",

    compareVersionsBtn: "Compare Versions",

    currentVersionBadge: "Currently Adopted Version",

    candidateVersionBadge: "Candidate Framework Version",

    addedRequirements: "Added Requirements",

    removedRequirements: "Removed Requirements",

    unchangedRequirements: "Unchanged Requirements",

    changedPins: "Changed Version Pins",

    rulePinLabel: "Rule Pin",

    controlPinLabel: "Control Pin",

    bundleDigestLabel: "Bundle Digest",

    adoptionHistoryTitle: "Immutable Adoption History",

    noAdoptionHistory: "No previous adoptions recorded for this tenant.",



    loadingEntities: "Loading legal entities...",

    loadingUnits: "Loading business units...",

    loadingLocations: "Loading locations...",

    refreshOrgBtn: "Refresh Organization",

    refreshingOrgBtn: "Refreshing...",

    addEntityHeading: "Add Legal Entity",

    addUnitHeading: "Add Business Unit",

    addLocationHeading: "Add Location",

    selectLegalEntityLabel: "Select Legal Entity:",

    entityCreatedSuccess: "Legal Entity created successfully.",

    unitCreatedSuccess: "Business Unit created successfully.",

    locationCreatedSuccess: "Location created successfully.",

    entityNameRequired: "Entity name is required",

    unitNameRequired: "Business Unit name is required",

    locationNameRequired: "Location name is required",

    cityRequired: "City is required",

    countryTwoLetters: "Country must be exactly 2 letters",

    selectEntityRequired: "Please select a Legal Entity",

    orgManageReadOnlyNotice: "Organization structure is managed by Owners and Administrators. Current role has read-only access.",

    postAmbiguousNotice: "Network interruption occurred during submission. The record may have already been created on the server.",

    checkReconcileBtn: "Check & Reconcile",

    dismissRetryBtn: "Dismiss & Retry",

    reconciledSuccess: "Record was verified as created on the server.",

    reconcileNotFound: "Record was not found on the server. You may safely retry.",

    adoptedVersionUnavailable: "The currently adopted framework version is not present in the catalog manifest. Version comparison cannot be performed.",

    crossPackComparisonNotice: "Selected frameworks belong to different framework families. Version upgrade diffing is unavailable across different frameworks.",

    crossPackReplacementDisclaimer: "Switching to a different framework pack replaces the current active adoption upon confirmation. Physical schema supports one current adoption per tenant with preserved immutable history.",

    filterFrameworksPlaceholder: "Filter frameworks by name or version...",

    adoptedBadge: "Adopted",

    candidateBadge: "Candidate",

    inconsistentDigestNotice: "Warning: Framework versions share the same version ID but have differing bundle digests. Manifest metadata is inconsistent.",

    // B03 Work Queue & Control Traceability

    navWorkQueue: "Work Queue",

    workQueueTitle: "Daily Work Queue",

    workQueueSubtitle: "Operational queue of prioritized controls, evidence tasks, and findings.",

    refreshQueueBtn: "Refresh Queue",

    refreshingQueueBtn: "Refreshing Queue...",

    noFrameworkAdopted: "No Framework Pack Adopted",

    noFrameworkAdoptedDesc: "Please adopt a framework pack in the Frameworks catalog before managing daily compliance tasks and evidence.",

    goToFrameworksBtn: "Go to Frameworks",

    controlsDeniedNotice: "Access forbidden to control work list.",

    assessmentDeniedNotice: "Access restricted to assessment status (403 Forbidden). Displayed items reflect control tasks only.",

    traceabilityTitle: "Control Traceability",

    traceabilitySubtitle: "Complete pin-level traceability for control, evidence, and assessment.",

    syntheticProvenanceNotice: "Demonstration baseline content with synthetic provenance. Server status and pinned integrity artifacts govern compliance.",

    closeBtn: "Close",

    openEvidenceBtn: "Open Evidence Workspace",

    openAssessmentBtn: "Open Assessment Workspace",

    retryAssessmentsBtn: "Retry Assessments",

    retryControlsBtn: "Retry Controls",

    staleRefreshWarning: "Refresh failed. Showing previously loaded work items which may be out of date.",

    assessmentErrorBanner: "Assessment data could not be loaded.",

    controlsErrorBanner: "Control work items could not be loaded.",

    envelopeMismatchNotice: "Incompatible framework adoption context detected between controls and assessments.",

    navTargetNotFound: "Requested item was not found in the current adoption.",

      envelopeMismatchSelection: "Incompatible selection revision between controls and assessments.",

      envelopeMismatchAnswer: "Incompatible answer revision between controls and assessments.",

      allWorkPartial: "All Work ({count} - Partial)",

      allWorkUnavailable: "All Work (Unavailable)",

      assessmentNeededUnknown: "Assessment Needed (Unknown)",

      openFindingsUnknown: "Open Findings (Unknown)",

      dismissBtn: "Dismiss",

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: "Operations",

    operationsTitle: "Operations & Governance Registers",

    operationsSubtitle: "Manage organizational policies, risk assessments & treatments, asset inventories, and vendor compliance.",

    tabPolicies: "Policies",

    tabRisks: "Risks",

    tabAssets: "Assets",

    tabVendors: "Vendors",

    tabTasks: "Tasks",

    tabReviews: "Review Hub",

    tabJobs: "Job Status",

    tabTraining: "Training & LMS",

    trainingAssignmentsTitle: "Training Assignments",

    trainingCoursesTitle: "Course Catalog References",

    trainingCompletionsTitle: "Verified Completions",

    trainingPartnerStatus: "Simulated LMS Integration (Local Contract Verification)",

    registerCourseBtn: "Register Course Reference",

    assignTrainingBtn: "Assign Training",

    operationsDeniedNotice: "Access restricted (403 Forbidden). You do not have permission to view this operational register.",

    operationsReadOnlyNotice: "Read-only mode. You have view access to operational records, but cannot submit modifications.",

    refreshOperationsBtn: "Refresh Register",

    refreshingOperationsBtn: "Refreshing...",

    conflictReloadNotice: "Conflict detected (409): The record has been modified by another user. Your draft has been preserved. Review changes and reconcile.",

    conflictReloadBtn: "Reload Server Version",

    uncertainCreateNotice: "Network connection was interrupted during record creation. Status uncertain: check server records before retrying to prevent duplicates.",

    reconcileNotice: "Reconciliation: Matching record found on server.",

    noRecordSelected: "Select a record from the list to view details and manage lifecycle actions, or create a new entry.",

    createRecordBtn: "New Record",

    saveDraftBtn: "Save Draft",

    submitReviewBtn: "Submit for Review",

    approvePolicyBtn: "Approve Policy",

    publishPolicyBtn: "Publish Policy",

    archivePolicyBtn: "Archive Policy",

    acknowledgePolicyBtn: "Acknowledge Policy",

    acknowledgedBadge: "Acknowledged",

    revisionsHistoryTitle: "Revision History",

    policyOwnerCannotApproveNotice: "Independent 2-person approval required: Policy owner/author cannot approve their own policy.",

    treatmentsTitle: "Risk Treatments",

    addTreatmentBtn: "Add Treatment",

    reviewRecordBtn: "Record Review",

    statusActive: "Active",

    statusDraft: "Draft",

    statusInReview: "In Review",

    statusApproved: "Approved",

    statusPublished: "Published",

    statusArchived: "Archived",

    },

};