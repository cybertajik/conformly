export type SupportedLocale = "en" | "de" | "fr" | "nl" | "es";



export interface LocaleInfo {

  code: SupportedLocale;

  label: string;

  nativeLabel: string;

  flag: string;

}



export const SUPPORTED_LOCALES: Record<SupportedLocale, LocaleInfo> = {

  en: { code: "en", label: "English", nativeLabel: "English", flag: "🇬🇧" },

  de: { code: "de", label: "German", nativeLabel: "Deutsch", flag: "🇩🇪" },

  fr: { code: "fr", label: "French", nativeLabel: "Français", flag: "🇫🇷" },

  nl: { code: "nl", label: "Dutch", nativeLabel: "Nederlands", flag: "🇳🇱" },

  es: { code: "es", label: "Spanish", nativeLabel: "Español", flag: "🇪🇸" },

};



export interface TranslationDictionary {

  common: {

    save: string;

    cancel: string;

    delete: string;

    confirm: string;

    loading: string;

    filter: string;

    export: string;

    dismiss: string;

    back: string;

    close: string;

    status: string;

    actions: string;

    search: string;

    refresh: string;

    view: string;

    edit: string;

    completed: string;

    inProgress: string;

    pending: string;

    optional: string;

    required: string;

    all: string;

    yes: string;

    no: string;

  };

  nav: {

    platform: string;

    overview: string;

    onboarding: string;

    organization: string;

    frameworks: string;

    compliance: string;

    risks: string;

    assets: string;

    vendors: string;

    preaudit: string;

    trustCenter: string;

    lifecycle: string;

    members: string;

    signOut: string;

    organizationLabel: string;

  };

  disclaimer: {

    badge: string;

    title: string;

    text: string;

  };

  onboarding: {

    title: string;

    subtitle: string;

    pilotOperational: string;

    eyebrow: string;

    orgSlug: string;

    role: string;

    checklistTitle: string;

    checklistSubtitle: string;

    progressBarLabel: string;

    stepsCompleted: string;

    allMilestonesComplete: string;

    allMilestonesCompleteSub: string;

    resetProgress: string;

    markCompleted: string;

    markIncomplete: string;

    step1Title: string;

    step1Desc: string;

    step1Btn: string;

    step2Title: string;

    step2Desc: string;

    step2Btn: string;

    step3Title: string;

    step3Desc: string;

    step3Btn: string;

    step4Title: string;

    step4Desc: string;

    step4Btn: string;

    step5Title: string;

    step5Desc: string;

    step5Btn: string;

    supportTitle: string;

    supportSubtitle: string;

    supportNotice: string;

    thSeverity: string;

    thClassification: string;

    thResponse: string;

    thChannel: string;

    securityRlsTitle: string;

    securityRlsDesc: string;

    securityAesTitle: string;

    securityAesDesc: string;

    securityWhistleTitle: string;

    securityWhistleDesc: string;

    securityExitTitle: string;

    securityExitDesc: string;

  };

  dashboard: {

    title: string;

    subtitle: string;

    readinessScore: string;

    runPreAuditBtn: string;

    continuousTitle: string;

    continuousDesc: string;

    adminNotice: string;

  };

  status: {

    loadingTitle: string;

    signedOutTitle: string;

    signedOutDetail: string;

    signInBtn: string;

    expiredTitle: string;

    expiredDetail: string;

    deniedTitle: string;

    deniedDetail: string;

    noTenantTitle: string;

    noTenantDetail: string;

    eyebrow: string;

  };

  language: {

    selectorLabel: string;

  };

  customerDemo: {

    title: string;

    subtitle: string;

    syntheticNotice: string;

    answersRevision: string;

    selectionRevision: string;

    companyProfileTitle: string;

    companyProfileSubtitle: string;

    fictionalPreset: string;

    alphaName: string;

    alphaDesc: string;

    betaName: string;

    betaDesc: string;

    questionnaireTitle: string;

    questionnaireSubtitle: string;

    cloudQuestion: string;

    cloudYes: string;

    cloudNo: string;

    cloudUnknown: string;

    regionQuestion: string;

    regionEu: string;

    regionOther: string;

    regionUnknown: string;

    saveAnswers: string;

    saving: string;

    answersSaved: string;

    unsavedEdits: string;

    savedRevisionBadge: string;

    evaluateTitle: string;

    evaluateSubtitle: string;

    selectPackLabel: string;

    evaluateBtn: string;

    evaluating: string;

    saveFirstNotice: string;

    evaluationResults: string;

    evaluationResultsSubtitle: string;

    adoptPackBtn: string;

    adopting: string;

    adoptTitle: string;

    adoptSubtitle: string;

    adoptionIntentInvalidated: string;

    adoptSuccess: string;

    confirmAdopt: string;

    packComparisonTitle: string;

    hideComparison: string;

    comparePacks: string;

    unchangedReqs: string;

    addedReqs: string;

    removedReqs: string;

    exactVersions: string;

    currentAdoption: string;

    noAdoption: string;

    staleNotice: string;

    ackSyntheticLabel: string;

    ackMissingLabel: string;

    statusApplicable: string;

    statusNotApplicable: string;

    statusNeedsInfo: string;

    summaryApplicable: string;

    summaryNotApplicable: string;

    summaryNeedsInfo: string;

    summaryTruthfulNotice: string;

    controlsCount: string;

    controlMapping: string;

    viewExplanation: string;

    hideExplanation: string;

    missingFacts: string;

    noEvaluationYet: string;

    reloadWorkspace: string;

    savedProgress: string;

    stepsSaved: string;

    historyTitle: string;

    historySubtitle: string;

    historyEmpty: string;

    accessDeniedTitle: string;

    accessDeniedDetail: string;

    conflictTitle: string;

    stepProfile: string;

    stepEvaluation: string;

    stepAdoption: string;

    nextStep: string;

    prevStep: string;

    syntheticDemo: string;

    evaluationOnly: string;

    stepperAriaLabel: string;

    noticeAriaLabel: string;

    dismissMessage: string;

    errorLabel: string;

    noticeLabel: string;

    successLabel: string;

    requirementVersion: string;

    packVersionId: string;

    bundleDigest: string;

    adoptedTimestamp: string;

    staleEvaluation: string;

    stepCompleted: string;

    // MVP-B Control Work & Evidence

    controlWorkTitle: string;

    controlWorkSubtitle: string;

    initWorkBtn: string;

    initializingWork: string;

    initWorkNotice: string;

    noControlWorkYet: string;

    assignOwnerLabel: string;

    dueDateLabel: string;

    unassignedOwner: string;

    saveAssignmentBtn: string;

    savingAssignment: string;

    uploadEvidenceTitle: string;

    uploadAndLinkBtn: string;

    uploadingEvidence: string;

    selectFileLabel: string;

    validUntilLabel: string;

    rationaleLabel: string;

    rationalePlaceholder: string;

    reuseEvidenceTitle: string;

    reuseEvidenceBtn: string;

    reusingEvidence: string;

    selectEvidenceToReuse: string;

    reviewTitle: string;

    recordReviewBtn: string;

    recordingReview: string;

    acceptDecision: string;

    rejectDecision: string;

    reviewDecisionLabel: string;

    reviewRationalePlaceholder: string;

    historyEventsTitle: string;

    viewHistoryBtn: string;

    hideHistoryBtn: string;

    downloadPinnedFileBtn: string;

    evidenceValidityAvailable: string;

    evidenceValidityMissing: string;

    evidenceValidityNotYetValid: string;

    evidenceValidityExpired: string;

    evidenceValidityQuarantined: string;

    evidenceValidityUnavailable: string;

    evidenceValidityUnverified: string;

    scanStatusScannedAtLink: string;

    scanStatusUnverified: string;

    reviewStatusPending: string;

    reviewStatusAccepted: string;

    reviewStatusRejected: string;

    workVersionLabel: string;

    staleWorkNotice: string;

    scannerUnavailableNotice: string;

    eventInitialized: string;

    eventOwnerUpdated: string;

    eventEvidenceLinked: string;

    eventEvidenceReviewed: string;

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: string;

    assessmentWorkSubtitle: string;

    assessmentProcedureTitle: string;

    procedureDisclaimer: string;

    criteriaTitle: string;

    criterionImplementation: string;

    criterionEvidence: string;

    criterionOperation: string;

    resultPass: string;

    resultPartial: string;

    resultFail: string;

    resultInsufficientEvidence: string;

    rationaleInputPlaceholder: string;

    recordAssessmentBtn: string;

    recordingAssessment: string;

    findingsTitle: string;

    noFindingsYet: string;

    findingSeverity: string;

    findingStatus: string;

    findingOwner: string;

    findingDueDate: string;

    findingRemediationNote: string;

    updateFindingBtn: string;

    updatingFinding: string;

    retestTitle: string;

    retestBtn: string;

    recordingRetest: string;

    selectFindingToResolve: string;

    readinessSummaryTitle: string;

    summaryTotalControls: string;

    summaryPass: string;

    summaryUnassessed: string;

    summaryBlocked: string;

    summaryOpenFindings: string;

    summaryInRemediation: string;

    summaryResolvedFindings: string;

    summaryStaleAssessment: string;

    summaryReasonCodes: string;

    statusUnassessed: string;

    statusPass: string;

    statusPartial: string;

    statusFail: string;

    statusInsufficientEvidence: string;

    statusStale: string;

    historyJournalTitle: string;

    noHistoryEvents: string;

    selectEvaluation: string;

    selectFindingToRetest: string;

    selectResult: string;

    selectRetestOutcome: string;

    selectSeverity: string;

    noUnresolvedFindings: string;

    associatedEvidence: string;

    evaluationRequirements: string;

    loadingHistory: string;

    sessionExpired: string;

    saveRemediationBtn: string;

    cancelBtn: string;

    severityLow: string;

    severityMedium: string;

    severityHigh: string;

    severityCritical: string;

    statusOpen: string;

    statusInRemediation: string;

    statusResolved: string;

    resolvesFinding: string;

        createFindingCheckbox: string;

evidenceRequiredForPass: string;

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: string;
    preauditTitle: string;
    preauditSubtitle: string;
    createPreauditBtn: string;
    freezeScopeBtn: string;
    submitPreauditReviewBtn: string;
    approvePreauditBtn: string;
    cancelPreauditBtn: string;
    downloadReportBtn: string;
    preauditLeadLabel: string;
    preauditReviewerLabel: string;
    preauditRevisionLabel: string;
    preauditBlockersTitle: string;
    preauditHistoryTitle: string;
    preauditNoCases: string;

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: string;
    verificationSubtitle: string;
    issueVerificationBtn: string;
    suspendVerificationBtn: string;
    revokeVerificationBtn: string;
    correctVerificationBtn: string;
    supersedeVerificationBtn: string;
    reconcileVerificationBtn: string;
    viewProjectionBtn: string;
    verificationStatusLabel: string;
    verificationEffectiveLabel: string;
    verificationValidityLabel: string;
    verificationSyntheticDisclaimer: string;
    verificationHistoryTitle: string;
    verificationLimitationsTitle: string;
    verificationNoVerifications: string;
    verificationReasonPrompt: string;
    verificationConfirmAction: string;
    supersedeNewCaseIdLabel: string;
    supersedeNewRevisionLabel: string;
    supersedeNewSnapshotIdLabel: string;
    supersedeNewDigestLabel: string;
    uncertaintyTitle: string;
    uncertaintyRetryBtn: string;
    uncertaintyDismissBtn: string;

  };

  portal: {

    brand: string;

    navOverview: string;

    navCompanySetup: string;

    navFrameworks: string;

    navControlsEvidence: string;

    navAssessmentsFindings: string;
    navPreaudit: string;
    preauditSubtitle: string;

    welcomeTitle: string;

    welcomeSubtitle: string;

    tenantLabel: string;

    roleLabel: string;

    quickActionsTitle: string;

    nextActionTitle: string;

    nextActionSetup: string;

    nextActionAdopt: string;

    nextActionControls: string;

    nextActionAssess: string;

    actionConfigureSetup: string;

    actionExploreFrameworks: string;

    actionManageControls: string;

    actionRunAssessments: string;

    cardFrameworkStatus: string;

    cardControlsStatus: string;

    cardEvidenceStatus: string;

    cardAssessmentStatus: string;

    noPackAdopted: string;

    adoptedPack: string;

    stalePackWarning: string;

    controlsCountLabel: string;

    evidenceItemsLabel: string;

    reviewsPendingLabel: string;

    findingsSummaryLabel: string;

    openFindingsCount: string;

    setupTitle: string;

    setupSubtitle: string;

    saveSetupBtn: string;

    savingSetupBtn: string;

    setupSavedSuccess: string;

    unsavedChangesBadge: string;

    validationErrorsNotice: string;

    companyCodeRequired: string;

    cloudUsageRequired: string;

    operatingRegionRequired: string;

    frameworksTitle: string;

    frameworksSubtitle: string;

    controlsTitle: string;

    controlsSubtitle: string;

    assessmentsTitle: string;

    assessmentsSubtitle: string;

    backToOverview: string;

    truthfulNotice: string;

    menuToggle: string;

    signOut: string;

    breadcrumbHome: string;

    skipToContent: string;

    navAriaLabel: string;

    unsavedChangesGuidance: string;

    validateBtn: string;

    evaluatingUsesSavedAnswers: string;

    statusNotInitialized: string;

    statusInProgress: string;

    statusUnassessed: string;

    statusAuditReady: string;

    statusAllPassed: string;

    statusFindings: string;

    statusPinned: string;

    statusNone: string;

    statusUnavailable: string;

    statusStale: string;

    statusAdopted: string;

    statusDenied: string;

    statusBlocked: string;

    evidenceLinksLabel: string;

    assessmentProgressDetail: string;

    notAssessed: string;

    refreshOverview: string;

    retryLoading: string;

    loadingHistory: string;

    noHistory: string;

    noEvidenceLinked: string;

    retestOutcome: string;

    noUnresolvedFindings: string;

    retestCriteria: string;

    retestRationale: string;

    openStatus: string;

    discardDraftConfirm: string;

    discardAndLeave: string;

    stayOnPage: string;

    keepDraftsNotice: string;

    // B02 Organization & Framework Version Inspector

    navOrganization: string;

    orgTitle: string;

    orgSubtitle: string;

    legalEntitiesTitle: string;

    legalEntitiesSubtitle: string;

    createEntityBtn: string;

    creatingEntityBtn: string;

    entityNameLabel: string;

    regNumberLabel: string;

    countryLabel: string;

    primaryEntityLabel: string;

    primaryBadge: string;

    noEntitiesYet: string;

    businessUnitsTitle: string;

    businessUnitsSubtitle: string;

    createUnitBtn: string;

    creatingUnitBtn: string;

    unitNameLabel: string;

    unitCodeLabel: string;

    selectEntityPrompt: string;

    noUnitsYet: string;

    locationsTitle: string;

    locationsSubtitle: string;

    createLocationBtn: string;

    creatingLocationBtn: string;

    locationNameLabel: string;

    cityLabel: string;

    addressLabel: string;

    noLocationsYet: string;

    membersTitle: string;

    membersSubtitle: string;

    membersDenied: string;

    noMembersYet: string;

    entitlementsTitle: string;

    entitlementsSubtitle: string;

    entitlementsDenied: string;

    planLabel: string;

    maxMembersLabel: string;

    storageLimitLabel: string;

    modulesLabel: string;

    allowedFrameworksLabel: string;

    versionInspectorTitle: string;

    versionInspectorSubtitle: string;

    compareVersionsBtn: string;

    currentVersionBadge: string;

    candidateVersionBadge: string;

    addedRequirements: string;

    removedRequirements: string;

    unchangedRequirements: string;

    changedPins: string;

    rulePinLabel: string;

    controlPinLabel: string;

    bundleDigestLabel: string;

    adoptionHistoryTitle: string;

    noAdoptionHistory: string;

    loadingEntities: string;

    loadingUnits: string;

    loadingLocations: string;

    refreshOrgBtn: string;

    refreshingOrgBtn: string;

    addEntityHeading: string;

    addUnitHeading: string;

    addLocationHeading: string;

    selectLegalEntityLabel: string;

    entityCreatedSuccess: string;

    unitCreatedSuccess: string;

    locationCreatedSuccess: string;

    entityNameRequired: string;

    unitNameRequired: string;

    locationNameRequired: string;

    cityRequired: string;

    countryTwoLetters: string;

    selectEntityRequired: string;

    orgManageReadOnlyNotice: string;

    postAmbiguousNotice: string;

    checkReconcileBtn: string;

    dismissRetryBtn: string;

    reconciledSuccess: string;

    reconcileNotFound: string;

    adoptedVersionUnavailable: string;

    crossPackComparisonNotice: string;

    crossPackReplacementDisclaimer: string;

    filterFrameworksPlaceholder: string;

    adoptedBadge: string;

    candidateBadge: string;

    inconsistentDigestNotice: string;

    // B03 Work Queue & Control Traceability

    navWorkQueue: string;

    workQueueTitle: string;

    workQueueSubtitle: string;

    refreshQueueBtn: string;

    refreshingQueueBtn: string;

    noFrameworkAdopted: string;

    noFrameworkAdoptedDesc: string;

    goToFrameworksBtn: string;

    controlsDeniedNotice: string;

    assessmentDeniedNotice: string;

    traceabilityTitle: string;

    traceabilitySubtitle: string;

    syntheticProvenanceNotice: string;

    closeBtn: string;

    openEvidenceBtn: string;

    openAssessmentBtn: string;

    retryAssessmentsBtn: string;

    retryControlsBtn: string;

    staleRefreshWarning: string;

    assessmentErrorBanner: string;

    controlsErrorBanner: string;

    envelopeMismatchNotice: string;

    navTargetNotFound: string;

    envelopeMismatchSelection: string;

    envelopeMismatchAnswer: string;

    allWorkPartial: string;

    allWorkUnavailable: string;

    assessmentNeededUnknown: string;

    openFindingsUnknown: string;

    dismissBtn: string;

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: string;

    operationsTitle: string;

    operationsSubtitle: string;

    tabPolicies: string;

    tabRisks: string;

    tabAssets: string;

    tabVendors: string;

    tabTasks: string;

    tabReviews: string;

    tabJobs: string;

    tabTraining: string;

    trainingAssignmentsTitle: string;

    trainingCoursesTitle: string;

    trainingCompletionsTitle: string;

    trainingPartnerStatus: string;

    registerCourseBtn: string;

    assignTrainingBtn: string;

    operationsDeniedNotice: string;

    operationsReadOnlyNotice: string;

    refreshOperationsBtn: string;

    refreshingOperationsBtn: string;

    conflictReloadNotice: string;

    conflictReloadBtn: string;

    uncertainCreateNotice: string;

    reconcileNotice: string;

    noRecordSelected: string;

    createRecordBtn: string;

    saveDraftBtn: string;

    submitReviewBtn: string;

    approvePolicyBtn: string;

    publishPolicyBtn: string;

    archivePolicyBtn: string;

    acknowledgePolicyBtn: string;

    acknowledgedBadge: string;

    revisionsHistoryTitle: string;

    policyOwnerCannotApproveNotice: string;

    treatmentsTitle: string;

    addTreatmentBtn: string;

    reviewRecordBtn: string;

    statusActive: string;

    statusDraft: string;

    statusInReview: string;

    statusApproved: string;

    statusPublished: string;

    statusArchived: string;

  };

};



