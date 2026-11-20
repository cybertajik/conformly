import type { TranslationDictionary } from "../types";



export const de: TranslationDictionary = {

  common: {

    save: "Speichern",

    cancel: "Abbrechen",

    delete: "Löschen",

    confirm: "Bestätigen",

    loading: "Wird geladen...",

    filter: "Filtern",

    export: "Exportieren",

    dismiss: "Schließen",

    back: "Zurück",

    close: "Schließen",

    status: "Status",

    actions: "Aktionen",

    search: "Suchen...",

    refresh: "Aktualisieren",

    view: "Anzeigen",

    edit: "Bearbeiten",

    completed: "Abgeschlossen",

    inProgress: "In Bearbeitung",

    pending: "Ausstehend",

    optional: "Optional",

    required: "Erforderlich",

    all: "Alle",

    yes: "Ja",

    no: "Nein",

  },

  nav: {

    platform: "Plattform",

    overview: "Übersicht",

    onboarding: "Onboarding",

    organization: "Organisation",

    frameworks: "Framework-Katalog",

    compliance: "Compliance & Nachweise",

    risks: "Risikoregister",

    assets: "Asset-Register",

    vendors: "Dienstleisterregister",

    preaudit: "Pre-Audit-Prüfung",

    trustCenter: "Trust Center & Profil",

    lifecycle: "Export & Datenlebenszyklus",

    members: "Mitglieder",

    signOut: "Abmelden",

    organizationLabel: "Organisation",

  },

  disclaimer: {

    badge: "Hinweis",

    title: "Conformly ist eine Plattform für Audit-Readiness und Compliance-Betrieb, keine akkreditierte Zertifizierungsstelle.",

    text: "Pre-Audit-Bewertungen, Readiness-Scores und von Conformly ausgestellte Nachweise spiegeln deterministische Nachweisprüfungen und den internen Bereitschaftsstatus wider; sie stellen keine offiziellen akkreditierten Zertifizierungen Dritter dar.",

  },

  onboarding: {

    title: "Pre-Audit Readiness Onboarding",

    subtitle: "Schließen Sie diese grundlegenden Meilensteine ab, um Ihre Organisation auf externe Compliance-Audits vorzubereiten.",

    pilotOperational: "Pilot Betriebsbereit",

    eyebrow: "Betriebsbereitschaft • Aktiver Pilot",

    orgSlug: "Organisations-Kürzel",

    role: "Rolle",

    checklistTitle: "Meilenstein-Checkliste",

    checklistSubtitle: "Verfolgen und speichern Sie Ihren Fortschritt bei wesentlichen Vorbereitungsaufgaben.",

    progressBarLabel: "Fortschritt des Onboardings",

    stepsCompleted: "{completed} von {total} Meilensteinen abgeschlossen ({percent}%)",

    allMilestonesComplete: "🎉 Alle Onboarding-Meilensteine abgeschlossen!",

    allMilestonesCompleteSub: "Ihre Organisation ist vollständig konfiguriert und bereit für deterministische Pre-Audit-Prüfungen.",

    resetProgress: "Fortschritt zurücksetzen",

    markCompleted: "Als erledigt markieren",

    markIncomplete: "Als ausstehend markieren",

    step1Title: "Kanonisches Compliance-Framework übernehmen",

    step1Desc: "Wählen Sie offizielle Frameworks (ISO/IEC 27001, SOC 2, HIPAA) oder erstellen Sie eigene Overlays.",

    step1Btn: "Katalog öffnen",

    step2Title: "Kontrollen umsetzen & Nachweise erfassen",

    step2Desc: "Laden Sie Nachweise mit AES-256-GCM-Umschlagverschlüsselung hoch und verknüpfen Sie Kontrollen mit Richtlinien.",

    step2Btn: "Compliance öffnen",

    step3Title: "Pre-Audit Readiness-Prüfung durchführen",

    step3Desc: "Führen Sie deterministisches Scoring durch, erstellen Sie SHA-256-Audit-Manifeste und erzeugen Sie Readiness-Nachweise.",

    step3Btn: "Pre-Audit starten",

    step4Title: "Öffentliches Trust Center veröffentlichen",

    step4Desc: "Präsentieren Sie Sicherheitszusagen, verifizierte Readiness-Abzeichen und Zertifikate Dritter.",

    step4Btn: "Trust Center",

    step5Title: "Anonymen Hinweisgeberkanal konfigurieren",

    step5Desc: "Ermöglichen Sie vertrauliche Meldungen mit PBKDF2-Hash-Tracking und ohne jegliche IP-Protokollierung.",

    step5Btn: "Hinweisgeberportal",

    supportTitle: "Pilot Service & Support-Annahme",

    supportSubtitle: "24/7 Sicherheitsannahme • Betriebszeiten zu Geschäftszeiten",

    supportNotice: "Während des Pilotprogramms stellen die Serviceziele betriebliche Reaktionsrichtlinien dar (keine vertraglichen SLAs). Vertragliche SLAs werden nach sechs Monaten Produktionsbetrieb eingeführt.",

    thSeverity: "Schweregrad",

    thClassification: "Klassifizierung",

    thResponse: "Reaktionsziel",

    thChannel: "Eingangskanal",

    securityRlsTitle: "Row-Level Security (RLS)",

    securityRlsDesc: "Strikte datenbankseitige Mandantentrennung bei jeder SQL-Abfrage.",

    securityAesTitle: "AES-256-GCM Verschlüsselung",

    securityAesDesc: "Eigener DEK pro Datei; keine unverschlüsselten Nachweise im Ruhezustand.",

    securityWhistleTitle: "Anonymer Hinweisgeber",

    securityWhistleDesc: "PBKDF2-Rückkehrschlüssel ohne Erfassung von IP-Adressen oder Telemetrie.",

    securityExitTitle: "Auditierbarer Datenaustritt",

    securityExitDesc: "30-tägiges Exportfenster, 90-tägiger kryptografischer Löschungsnachweis.",

  },

  dashboard: {

    title: "Executive Compliance Dashboard",

    subtitle: "Echtzeit-Posture, Readiness-Tracking und betriebliche Gesundheit.",

    readinessScore: "Audit-Readiness-Score",

    runPreAuditBtn: "Pre-Audit-Prüfung ausführen",

    continuousTitle: "Kontinuierliche Compliance-Auswertung abgeschlossen",

    continuousDesc: "{tasks} Behebungsaufgabe(n) erstellt • {notifications} Benachrichtigung(en) eingereiht • {overdue} überfällige Aufgabe(n) eskaliert",

    adminNotice: "Administrator-Isolationsmodus aktiv. Vertrauliche Hinweisgeberfälle und Restricted-Nachweise sind zugriffsbeschränkt.",

  },

  status: {

    loadingTitle: "Conformly wird geladen",

    signedOutTitle: "Conformly",

    signedOutDetail: "Sichere Compliance-Operationen für Audit-Readiness.",

    signInBtn: "Anmelden",

    expiredTitle: "Sitzung abgelaufen",

    expiredDetail: "Bitte melden Sie sich erneut an.",

    deniedTitle: "Zugriff verweigert",

    deniedDetail: "Ihr Benutzerkonto hat keinen Zugriff auf diesen Mandanten.",

    noTenantTitle: "Kein Mandant verfügbar",

    noTenantDetail: "Ihr Konto besitzt keine aktive Conformly-Mitgliedschaft. Bitte wenden Sie sich an einen Administrator.",

    eyebrow: "Sichere Compliance-Operationen",

  },

  language: {

    selectorLabel: "Sprache auswählen",

  },

  customerDemo: {

    title: "Kunden-Onboarding und Workspace",

    subtitle: "Interaktive synthetische Compliance-Prüfung und Onboarding-Prozess",

    syntheticNotice: "Hinweis: Synthetische Kunden-Onboarding-Demonstration. Keine Rechts- oder Compliance-Beratung.",

    answersRevision: "Antwort-Revision",

    selectionRevision: "Auswahl-Revision",

    companyProfileTitle: "1. Unternehmensprofil und Fakten",

    companyProfileSubtitle: "Wählen Sie ein Profil oder passen Sie Antworten an, um die Anwendbarkeit zu prüfen",

    fictionalPreset: "Fiktive Unternehmensvorlage:",

    alphaName: "Alpha (Cloud/EU)",

    alphaDesc: "Cloud-native Workloads mit Betrieb in der Europäischen Union",

    betaName: "Beta (Nicht-Cloud/Global)",

    betaDesc: "On-Premises- bzw. Hybrid-Infrastruktur in globalen Regionen",

    questionnaireTitle: "Fragebogen zur Anwendbarkeit",

    questionnaireSubtitle: "Deterministische Fakten für die Compliance-Regel-Engine",

    cloudQuestion: "Nutzt Ihre Organisation öffentliche oder private Cloud-Infrastruktur?",

    cloudYes: "Ja",

    cloudNo: "Nein",

    cloudUnknown: "Unbekannt",

    regionQuestion: "Hauptsächliche Betriebsregion",

    regionEu: "Europäische Union (EU)",

    regionOther: "Andere Rechtsordnungen",

    regionUnknown: "Unbekannt",

    saveAnswers: "Antworten speichern",

    saving: "Wird gespeichert...",

    answersSaved: "Antworten erfolgreich als unveränderliche Revision gespeichert.",

    unsavedEdits: "Ungespeicherte Änderungen",

    savedRevisionBadge: "Gespeicherte Revision",

    evaluateTitle: "2. Framework-Auswertung und Kontrollen",

    evaluateSubtitle: "Deterministische Anwendbarkeit basierend auf gespeicherten Fakten berechnen",

    selectPackLabel: "Demo-Framework-Paket:",

    evaluateBtn: "Anwendbarkeit auswerten",

    evaluating: "Wird ausgewertet...",

    saveFirstNotice: "Bitte speichern Sie die Antworten vor der Auswertung",

    evaluationResults: "Auswertungsergebnisse",

    evaluationResultsSubtitle: "Geprüft gegen Antwort-Revision",

    adoptPackBtn: "Paket übernehmen",

    adopting: "Wird übernommen...",

    adoptTitle: "Demo-Paket übernehmen",

    adoptSubtitle: "Überprüfen Sie Anforderungen, Kontrollen und Unterschiede vor der Übernahme.",

    adoptionIntentInvalidated: "Der Adoptions-Snapshot, die Kandidatenauswahl oder die Sitzung hat sich geändert. Bitte schließen und erneut auswerten.",

    adoptSuccess: "Demo-Paket erfolgreich übernommen.",

    confirmAdopt: "Übernahme bestätigen",

    packComparisonTitle: "Exakter Paketvergleich",

    hideComparison: "Vergleich ausblenden",

    comparePacks: "Pakete vergleichen",

    unchangedReqs: "Unveränderte Anforderungen",

    addedReqs: "+ Hinzugefügt in",

    removedReqs: "- Entfernt in",

    exactVersions: "Exakte Anforderungsversionen:",

    currentAdoption: "Aktuelle Übernahme",

    noAdoption: "Noch kein Paket übernommen",

    staleNotice: "(Veraltet: Antworten aktualisiert)",

    ackSyntheticLabel: "Ich verstehe, dass dies ein synthetisches Demonstrations-Framework und Kontrollmapping nur zu Demonstrationszwecken ist, keine rechtliche Beratung.",

    ackMissingLabel: "Ich bestätige, dass einige Anforderungen wegen fehlender Angaben als NEEDS_INFORMATION eingestuft wurden und weitere Angaben erfordern.",

    statusApplicable: "ANWENDBAR",

    statusNotApplicable: "NICHT ANWENDBAR",

    statusNeedsInfo: "INFORMATION ERFORDERLICH",

    summaryApplicable: "Anwendbar",

    summaryNotApplicable: "Nicht anwendbar",

    summaryNeedsInfo: "Info erforderlich",

    summaryTruthfulNotice: "Synthetische Zählergebnisse basierend auf gespeicherten Fakten. Keine Compliance-Zertifizierung oder Reifegradbewertung.",

    controlsCount: "Regeln",

    controlMapping: "Gemeinsame Kontrolle:",

    viewExplanation: "Erklärung anzeigen",

    hideExplanation: "Erklärung ausblenden",

    missingFacts: "Fehlende Fakten:",

    noEvaluationYet: "Noch keine Auswertung berechnet. Klicken Sie oben auf 'Anwendbarkeit auswerten'.",

    reloadWorkspace: "Workspace neu laden",

    savedProgress: "Onboarding-Fortschritt",

    stepsSaved: "Fakten gespeichert",

    historyTitle: "3. Übernahmehistorie und Prüfpfad",

    historySubtitle: "Unveränderliches Protokoll übernommener Framework-Versionen und Prüfsummen",

    historyEmpty: "Bislang keine Übernahmen verzeichnet.",

    accessDeniedTitle: "Zugriff verweigert",

    accessDeniedDetail: "Rolle Tenant-Eigentümer oder Compliance-Manager erforderlich.",

    conflictTitle: "Workspace-Konflikt",

    stepProfile: "1. Unternehmensprofil",

    stepEvaluation: "2. Regelauswertung",

    stepAdoption: "3. Paketübernahme",

    nextStep: "Weiter",

    prevStep: "Zurück",

    syntheticDemo: "Synthetische Demo",

    evaluationOnly: "Nur Bewertung",

    stepperAriaLabel: "Kunden-Onboarding-Schritte",

    noticeAriaLabel: "Hinweis zur synthetischen Demo",

    dismissMessage: "Meldung schließen",

    errorLabel: "Fehler",

    noticeLabel: "Hinweis",

    successLabel: "Erfolg",

    requirementVersion: "Anforderungsversion",

    packVersionId: "Paketversions-ID",

    bundleDigest: "Paket-Digest",

    adoptedTimestamp: "Übernahmezeitpunkt",

    staleEvaluation: "Veraltete Bewertung",

    stepCompleted: "Abgeschlossen",

    // MVP-B Control Work & Evidence

    controlWorkTitle: "Kontrollarbeiten & Nachweisfixierung",

    controlWorkSubtitle: "Weisen Sie Kontrollinhaber zu, legen Sie Fälligkeitsdaten fest, laden Sie verschlüsselte Nachweise hoch und führen Sie Eignungsprüfungen durch.",

    initWorkBtn: "Kontrollarbeiten initialisieren",

    initializingWork: "Initialisierung...",

    initWorkNotice: "Initialisieren Sie Arbeitselemente, die den Anforderungen des aktuellen Pakets zugeordnet sind.",

    noControlWorkYet: "Noch keine Kontrollarbeiten für diese Übernahme initialisiert.",

    assignOwnerLabel: "Inhaber",

    dueDateLabel: "Zieldatum",

    unassignedOwner: "Nicht zugewiesen",

    saveAssignmentBtn: "Zuweisung aktualisieren",

    savingAssignment: "Speichern...",

    uploadEvidenceTitle: "Gescannte Nachweise hochladen & fixieren",

    uploadAndLinkBtn: "Hochladen & Fixieren",

    uploadingEvidence: "Hochladen & Scannen...",

    selectFileLabel: "Nachweisdatei auswählen (max. 1 MiB)",

    validUntilLabel: "Gültigkeitsdatum des Nachweises",

    rationaleLabel: "Eignungsbegründung",

    rationalePlaceholder: "Beschreiben Sie, warum dieser Nachweis für diese Kontrolle geeignet ist...",

    reuseEvidenceTitle: "Gezielte Nachweiswiederverwendung",

    reuseEvidenceBtn: "Revision wiederverwenden",

    reusingEvidence: "Verknüpfen...",

    selectEvidenceToReuse: "Vorhandene Nachweisrevision auswählen",

    reviewTitle: "Eignungsprüfung aufzeichnen",

    recordReviewBtn: "Prüfung speichern",

    recordingReview: "Speichern...",

    acceptDecision: "Akzeptieren (Geeignet)",

    rejectDecision: "Ablehnen (Ungeeignet)",

    reviewDecisionLabel: "Prüfungsentscheidung",

    reviewRationalePlaceholder: "Begründung und Prüfnotizen dokumentieren...",

    historyEventsTitle: "Revisionsverlauf der Kontrollarbeit",

    viewHistoryBtn: "Verlauf anzeigen",

    hideHistoryBtn: "Verlauf ausblenden",

    downloadPinnedFileBtn: "Datei herunterladen",

    evidenceValidityAvailable: "Verfügbar",

    evidenceValidityMissing: "Fehlende Datei",

    evidenceValidityNotYetValid: "Noch nicht gültig",

    evidenceValidityExpired: "Abgelaufen",

    evidenceValidityQuarantined: "In Quarantäne",

    evidenceValidityUnavailable: "Nicht verfügbar / Manipuliert",

    evidenceValidityUnverified: "Ungeprüfter Scan-Nachweis",

    scanStatusScannedAtLink: "Beim Verknüpfen gescannt",

    scanStatusUnverified: "Ungeprüft",

    reviewStatusPending: "Prüfung ausstehend",

    reviewStatusAccepted: "Akzeptiert",

    reviewStatusRejected: "Abgelehnt",

    workVersionLabel: "Version",

    staleWorkNotice: "Arbeitselement gehört zu einer früheren Antwort- oder Paketversion; Änderungen sind deaktiviert.",

    scannerUnavailableNotice: "Antiviren-Scanner nicht verfügbar oder Prüfung fehlgeschlagen; Nachweisfixierung blockiert.",

    eventInitialized: "Arbeit initialisiert",

    eventOwnerUpdated: "Zuweisung aktualisiert",

    eventEvidenceLinked: "Nachweis verknüpft",

    eventEvidenceReviewed: "Eignung geprüft",

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: "Menschliche Bewertung & Audit-Bereitschaft",

    assessmentWorkSubtitle: "Führen Sie menschliche Bewertungen anhand synthetischer Verfahren durch, verwalten Sie Feststellungen und Behebungen, erfassen Sie explizite Nachtests und prüfen Sie wahrheitsgemäße Bereitschaftszusammenfassungen.",

    assessmentProcedureTitle: "Synthetisches Bewertungsverfahren",

    procedureDisclaimer: "Synthetisches Bewertungsverfahren — Menschliche Überprüfung für die Konformitätsbestimmung erforderlich.",

    criteriaTitle: "Bewertungskriterien",

    criterionImplementation: "Umsetzungsprüfung",

    criterionEvidence: "Nachweisangemessenheit",

    criterionOperation: "Betriebliche Wirksamkeit",

    resultPass: "Bestanden",

    resultPartial: "Teilweise",

    resultFail: "Nicht bestanden",

    resultInsufficientEvidence: "Unzureichender Nachweis",

    rationaleInputPlaceholder: "Detaillierte Bewertungsbegründung und Prüfnotizen dokumentieren...",

    recordAssessmentBtn: "Menschliche Bewertung erfassen",

    recordingAssessment: "Bewertung wird erfasst...",

    findingsTitle: "Mängelfeststellungen",

    noFindingsYet: "Keine Mängelfeststellungen für diese Kontrolle erfasst.",

    findingSeverity: "Schweregrad",

    findingStatus: "Status",

    findingOwner: "Zugewiesener Verantwortlicher",

    findingDueDate: "Zieldatum",

    findingRemediationNote: "Behebungsfortschrittsnotiz",

    updateFindingBtn: "Behebung aktualisieren",

    updatingFinding: "Speichern...",

    retestTitle: "Expliziten Nachtest erfassen",

    retestBtn: "Nachtest erfassen",

    recordingRetest: "Nachtest wird erfasst...",

    selectFindingToResolve: "Zu behebende Feststellung auswählen",

    readinessSummaryTitle: "Wahrheitsgemäße Audit-Bereitschaftsübersicht",

    summaryTotalControls: "Gesamtkontrollen",

    summaryPass: "Bestanden",

    summaryUnassessed: "Unbewertet",

    summaryBlocked: "Blockierte Kontrollen",

    summaryOpenFindings: "Offene Feststellungen",

    summaryInRemediation: "In Behebung",

    summaryResolvedFindings: "Behobene Feststellungen",

    summaryStaleAssessment: "Veraltete Bewertungen",

    summaryReasonCodes: "Blockierungsgründe",

    statusUnassessed: "UNBEWERTET",

    statusPass: "BESTANDEN",

    statusPartial: "TEILWEISE",

    statusFail: "FEHLGESCHLAGEN",

    statusInsufficientEvidence: "UNZUREICHENDER_NACHWEIS",

    statusStale: "VERALTETE_BEWERTUNG",

    historyJournalTitle: "Unveränderliches Bewertungsjournal",

    noHistoryEvents: "Bisher keine Bewertungsereignisse aufgezeichnet.",

    selectEvaluation: "-- Auswertung auswählen --",

    selectFindingToRetest: "-- Feststellung zum Nachtest auswählen --",

    selectResult: "-- Ergebnis auswählen --",

    selectRetestOutcome: "-- Nachtestergebnis auswählen --",

    selectSeverity: "-- Schweregrad auswählen --",

    noUnresolvedFindings: "Keine ungelösten Feststellungen für Nachtest.",

    associatedEvidence: "Zugehörige Nachweise",

    evaluationRequirements: "Bewertungsanforderungen",

    loadingHistory: "Verlauf wird geladen...",

    sessionExpired: "Sitzung abgelaufen. Bitte melden Sie sich erneut an.",

    saveRemediationBtn: "Behebung speichern",

    cancelBtn: "Abbrechen",

    severityLow: "NIEDRIG",

    severityMedium: "MITTEL",

    severityHigh: "HOCH",

    severityCritical: "KRITISCH",

    statusOpen: "OFFEN",

    statusInRemediation: "IN BEHEBUNG",

    statusResolved: "GELÖST",

    resolvesFinding: "(Löst Feststellung)",

        createFindingCheckbox: "Mangelbefund erfassen",

evidenceRequiredForPass: "Nachweise sind für das Ergebnis 'Bestanden' erforderlich",

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: "Pre-Audit",
    preauditTitle: "Pre-Audit-Arbeitsablauf",
    preauditSubtitle: "Geltungsbereich einfrieren, unabhängige Prüfung durchführen, Prüfbereitschaft zertifizieren und Berichte erstellen",
    createPreauditBtn: "Neuer Pre-Audit-Fall",
    freezeScopeBtn: "Umfang einfrieren",
    submitPreauditReviewBtn: "Zur Prüfung einreichen",
    approvePreauditBtn: "Eigentümer-Freigabe",
    cancelPreauditBtn: "Fall abbrechen",
    downloadReportBtn: "Berichtsarchiv herunterladen",
    preauditLeadLabel: "Compliance-Leiter",
    preauditReviewerLabel: "Unabhängiger Prüfer",
    preauditRevisionLabel: "Revision",
    preauditBlockersTitle: "Bereitschaftsblocker",
    preauditHistoryTitle: "Ereignisverlauf",
    preauditNoCases: "Keine Pre-Audit-Fälle initiiert. Klicken Sie auf 'Neuer Pre-Audit-Fall', um den Umfang einzufrieren.",

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: "Bereitschaftsnachweis-Lebenszyklus",
    verificationSubtitle: "Verwaltung synthetischer Bereitschaftsnachweise, Statusübergänge, privater Projektionen und Audit-Ereignisse",
    issueVerificationBtn: "Nachweis ausstellen",
    suspendVerificationBtn: "Nachweis aussetzen",
    revokeVerificationBtn: "Nachweis widerrufen",
    correctVerificationBtn: "Metadaten korrigieren",
    supersedeVerificationBtn: "Nachweis ersetzen",
    reconcileVerificationBtn: "Lebenszyklen abgleichen",
    viewProjectionBtn: "Private Vorschau anzeigen",
    verificationStatusLabel: "Gespeicherter Status",
    verificationEffectiveLabel: "Effektiver Status",
    verificationValidityLabel: "Gültigkeitszeitraum",
    verificationSyntheticDisclaimer: "PRIVATES SYNTHETISCHES INTERNES TESTERGEBNIS - KEINE AKKREDITIERTE ZERTIFIZIERUNG",
    verificationHistoryTitle: "Nachweis-Historie",
    verificationLimitationsTitle: "Geltungsbereich & Einschränkungen",
    verificationNoVerifications: "Für diesen genehmigten Vor-Audit-Fall wurde kein Bereitschaftsnachweis ausgestellt.",
    verificationReasonPrompt: "Geben Sie eine Begründung für diese Aktion ein:",
    verificationConfirmAction: "Lebenszyklus-Aktion bestätigen", 
    supersedeNewCaseIdLabel: "Ersatz-Vor-Audit-Fall-ID",
    supersedeNewRevisionLabel: "Erwartete Revision des Ersatzfalls",
    supersedeNewSnapshotIdLabel: "Ersatz-Snapshot-ID",
    supersedeNewDigestLabel: "Ersatz-Snapshot-Digest",
    uncertaintyTitle: "Wiederherstellung ungewisser Operationen",
    uncertaintyRetryBtn: "Operation wiederholen",
    uncertaintyDismissBtn: "Bestaetigen und Verwerfen",

  },

  portal: {

    brand: "Conformly Portal",

    navOverview: "Übersicht",

    navCompanySetup: "Unternehmenseinrichtung",

    navFrameworks: "Verfügbare Rahmenwerke",

    navControlsEvidence: "Kontrollen & Nachweise",

    navAssessmentsFindings: "Bewertungen & Feststellungen",
    navPreaudit: "Pre-Audit",

    welcomeTitle: "Willkommen bei Conformly Compliance",

    welcomeSubtitle: "Kontinuierliche Compliance-Automatisierung, Kontrollumsetzung und Prüfungsbereitschaft.",

    tenantLabel: "Organisation",

    roleLabel: "Rolle",

    quickActionsTitle: "Schnellaktionen",

    nextActionTitle: "Empfohlene nächste Aktion",

    nextActionSetup: "Vervollständigen Sie Ihre Unternehmensfakten und das Infrastrukturprofil, um die Anwendbarkeit zu prüfen.",

    nextActionAdopt: "Prüfen und übernehmen Sie ein Compliance-Paket, um Kontrollaufgaben zu generieren.",

    nextActionControls: "Weisen Sie Verantwortliche zu und laden Sie verschlüsselte Nachweise für Ihre Kontrollen hoch.",

    nextActionAssess: "Führen Sie menschliche Bewertungen durch und beheben Sie Feststellungen vor dem finalen Audit.",

    actionConfigureSetup: "Einrichtung konfigurieren",

    actionExploreFrameworks: "Pakete erkunden",

    actionManageControls: "Kontrollen & Nachweise verwalten",

    actionRunAssessments: "Bewertungen durchführen",

    cardFrameworkStatus: "Rahmenwerk-Übernahme",

    cardControlsStatus: "Kontrollaufgaben",

    cardEvidenceStatus: "Nachweise & Prüfung",

    cardAssessmentStatus: "Prüfungsbereitschaft",

    noPackAdopted: "Noch kein Paket übernommen",

    adoptedPack: "Übernommen: {name} (Rev. {rev})",

    stalePackWarning: "Die Übernahme ist aufgrund aktualisierter Antworten veraltet. Neue Prüfung erforderlich.",

    controlsCountLabel: "Gesamte Kontrollen",

    evidenceItemsLabel: "Nachweisverknüpfungen",

    reviewsPendingLabel: "Ausstehende Prüfungen",

    findingsSummaryLabel: "Feststellungsstatus",

    openFindingsCount: "Offene Feststellungen",

    setupTitle: "Unternehmenseinrichtung & Faktenprofil",

    setupSubtitle: "Geben Sie verifizierte Unternehmensfakten an, um die Anwendbarkeit von Rahmenwerken zu bestimmen.",

    saveSetupBtn: "Antworten speichern",

    savingSetupBtn: "Antworten werden gespeichert...",

    setupSavedSuccess: "Unternehmensfakten erfolgreich gespeichert.",

    unsavedChangesBadge: "Ungespeicherte Änderungen",

    validationErrorsNotice: "Bitte beheben Sie die nachstehenden Validierungsfehler, bevor Sie fortfahren.",

    companyCodeRequired: "Die Auswahl des Unternehmensprofils ist erforderlich.",

    cloudUsageRequired: "Die Nutzung von Cloud-Infrastruktur muss angegeben werden (Ja oder Nein).",

    operatingRegionRequired: "Die primäre Betriebsregion muss ausgewählt werden (EU oder Andere).",

    frameworksTitle: "Verfügbare Rahmenwerke & Pakete",

    frameworksSubtitle: "Versionsgebundene Compliance-Pakete, automatische Anwendbarkeitsregeln und formelle Übernahme.",

    controlsTitle: "Kontrollen & verschlüsselte Nachweise",

    controlsSubtitle: "Verfolgen Sie den Arbeitsstatus, weisen Sie Verantwortliche zu und laden Sie Nachweise hoch.",

    assessmentsTitle: "Menschliche Bewertungen & Feststellungen",

    assessmentsSubtitle: "Bewerten Sie Verfahren, erfassen Sie Prüffeststellungen und führen Sie Nachtests durch.",
    preauditSubtitle: "Geltungsbereich einfrieren, Bestätigung unabhängiger Prüfer und vertrauliche Bereitschaftsberichte",

    backToOverview: "Zurück zur Übersicht",

    truthfulNotice: "Wahrheitsgemäßer Zustand: Alle Kennzahlen spiegeln tatsächliche Daten ohne simulierte Werte wider.",

    menuToggle: "Navigationsmenü umschalten",

    signOut: "Abmelden",

    breadcrumbHome: "Portal",

    skipToContent: "Zum Hauptinhalt springen",

    navAriaLabel: "Portal-Navigation",

    unsavedChangesGuidance: "Sie haben nicht gespeicherte Änderungen an den Unternehmensdaten. Klicken Sie auf Antworten speichern, um fortzufahren.",

    validateBtn: "Validieren",

    evaluatingUsesSavedAnswers: "Sie haben nicht gespeicherte Änderungen im Unternehmens-Setup. Die Auswertung verwendet die gespeicherten Antworten.",

    statusNotInitialized: "NICHT INITIALISIERT",

    statusInProgress: "IN BEARBEITUNG",

    statusUnassessed: "NICHT BEWERTET",

    statusAuditReady: "AUDIT-BEREIT",

    statusFindings: "FESTSTELLUNGEN",

    statusPinned: "VERKNÜPFT",

    statusNone: "KEINE",

    statusUnavailable: "NICHT VERFÜGBAR",

    statusAllPassed: "ALLE BESTANDEN",

    statusStale: "VERALTET",

    statusAdopted: "ÜBERNOMMEN",

    statusDenied: "ZUGRIFF VERWEIGERT",

    statusBlocked: "BLOCKIERT",

    evidenceLinksLabel: "{count} verknüpfte Nachweise",

    assessmentProgressDetail: "{pass} bestanden · {findings} offene Feststellungen · {unassessed} nicht bewertet",

    notAssessed: "Nicht bewertet",

    refreshOverview: "Übersicht aktualisieren",

    retryLoading: "Erneut laden",

    loadingHistory: "Verlauf wird geladen...",

    noHistory: "Kein Verlauf aufgezeichnet.",

    noEvidenceLinked: "Noch keine Nachweise verknüpft.",

    retestOutcome: "Nachtestergebnis",

    noUnresolvedFindings: "Keine offenen Feststellungen für Nachtest berechtigt.",

    retestCriteria: "Nachtest-Bewertungskriterien",

    retestRationale: "Nachtest-Verifizierungsbegründung",

    openStatus: "OFFEN",

    discardDraftConfirm: "Sie haben ungespeicherte Änderungen in der Unternehmenseinrichtung. Änderungen verwerfen und Ansicht wechseln?",

    discardAndLeave: "Änderungen verwerfen",

    stayOnPage: "Auf Ansicht bleiben",

    keepDraftsNotice: "Entwurf im Speicher behalten",

    navOrganization: "Organisation",

    orgTitle: "Organisation & Struktur",

    orgSubtitle: "Verwalten Sie juristische Einheiten, Geschäftsbereiche, Standorte, Mitglieder und Abonnements.",

    legalEntitiesTitle: "Juristische Personen",

    legalEntitiesSubtitle: "Eingetragene Unternehmens- und Rechtseinheiten.",

    createEntityBtn: "Rechtseinheit erstellen",

    creatingEntityBtn: "Erstelle Rechtseinheit...",

    entityNameLabel: "Name der Rechtseinheit",

    regNumberLabel: "Handelsregisternummer",

    countryLabel: "Ländercode (2 Zeichen)",

    primaryEntityLabel: "Als primäre Rechtseinheit festlegen",

    primaryBadge: "Primär",

    noEntitiesYet: "Noch keine Rechtseinheiten definiert. Erstellen Sie oben Ihre erste Einheit.",

    businessUnitsTitle: "Geschäftsbereiche",

    businessUnitsSubtitle: "Betriebliche Abteilungen und Geschäftsbereiche.",

    createUnitBtn: "Geschäftsbereich erstellen",

    creatingUnitBtn: "Erstelle Geschäftsbereich...",

    unitNameLabel: "Name des Geschäftsbereichs",

    unitCodeLabel: "Bereichskürzel",

    selectEntityPrompt: "Rechtseinheit auswählen...",

    noUnitsYet: "Noch keine Geschäftsbereiche unter dieser Einheit definiert.",

    locationsTitle: "Standorte",

    locationsSubtitle: "Büros, Rechenzentren und Betriebsstandorte.",

    createLocationBtn: "Standort erstellen",

    creatingLocationBtn: "Erstelle Standort...",

    locationNameLabel: "Standortname",

    cityLabel: "Stadt",

    addressLabel: "Adresse",

    noLocationsYet: "Noch keine Standorte unter dieser Einheit definiert.",

    membersTitle: "Mitglieder- & Zugriffsverzeichnis",

    membersSubtitle: "Schreibgeschütztes Serververzeichnis der Mandantenmitglieder und Rollen.",

    membersDenied: "Zugriff verweigert: Fehlende Berechtigung membership:read.",

    noMembersYet: "Keine Mitglieder im Verzeichnis gefunden.",

    entitlementsTitle: "Tarif & Berechtigungen",

    entitlementsSubtitle: "Schreibgeschützte Ansicht von Tarif, Modulen und Kapazitätsgrenzen.",

    entitlementsDenied: "Zugriff verweigert: Fehlende Berechtigung entitlement:read.",

    planLabel: "Aktueller Tarif",

    maxMembersLabel: "Mitgliederlimit",

    storageLimitLabel: "Speicherlimit",

    modulesLabel: "Aktivierte Module",

    allowedFrameworksLabel: "Erlaubte Rahmenwerke",

    versionInspectorTitle: "Framework-Versionsinspektor",

    versionInspectorSubtitle: "Deterministischer Vergleich von Versionen, Anforderungen und Versions-Pins.",

    compareVersionsBtn: "Versionen vergleichen",

    currentVersionBadge: "Aktuell übernommene Version",

    candidateVersionBadge: "Kandidaten-Framework-Version",

    addedRequirements: "Hinzugefügte Anforderungen",

    removedRequirements: "Entfernte Anforderungen",

    unchangedRequirements: "Unveränderte Anforderungen",

    changedPins: "Geänderte Versions-Pins",

    rulePinLabel: "Regel-Pin",

    controlPinLabel: "Kontroll-Pin",

    bundleDigestLabel: "Paket-Prüfsumme",

    adoptionHistoryTitle: "Unveränderliche Übernahmehistorie",

    noAdoptionHistory: "Keine vorherigen Übernahmen für diesen Mandanten aufgezeichnet.",



    loadingEntities: "Juristische Personen werden geladen...",

    loadingUnits: "Geschäftsbereiche werden geladen...",

    loadingLocations: "Standorte werden geladen...",

    refreshOrgBtn: "Organisation aktualisieren",

    refreshingOrgBtn: "Wird aktualisiert...",

    addEntityHeading: "Juristische Person hinzufügen",

    addUnitHeading: "Geschäftsbereich hinzufügen",

    addLocationHeading: "Standort hinzufügen",

    selectLegalEntityLabel: "Juristische Person auswählen:",

    entityCreatedSuccess: "Juristische Person erfolgreich erstellt.",

    unitCreatedSuccess: "Geschäftsbereich erfolgreich erstellt.",

    locationCreatedSuccess: "Standort erfolgreich erstellt.",

    entityNameRequired: "Name der juristischen Person ist erforderlich",

    unitNameRequired: "Name des Geschäftsbereichs ist erforderlich",

    locationNameRequired: "Name des Standorts ist erforderlich",

    cityRequired: "Stadt ist erforderlich",

    countryTwoLetters: "Ländercode muss genau 2 Buchstaben lang sein",

    selectEntityRequired: "Bitte wählen Sie eine juristische Person aus",

    orgManageReadOnlyNotice: "Die Organisationsstruktur wird von Eigentümern und Administratoren verwaltet. Die aktuelle Rolle hat nur Lesezugriff.",

    postAmbiguousNotice: "Während der Übertragung ist eine Netzwerkunterbrechung aufgetreten. Der Datensatz wurde möglicherweise bereits auf dem Server erstellt.",

    checkReconcileBtn: "Prüfen & Abgleichen",

    dismissRetryBtn: "Verwerfen & Wiederholen",

    reconciledSuccess: "Datensatz wurde auf dem Server bestätigt.",

    reconcileNotFound: "Datensatz wurde auf dem Server nicht gefunden. Sie können es sicher erneut versuchen.",

    adoptedVersionUnavailable: "Die derzeit übernommene Framework-Version ist im Katalogmanifest nicht vorhanden. Versionsvergleich kann nicht durchgeführt werden.",

    crossPackComparisonNotice: "Die ausgewählten Frameworks gehören zu unterschiedlichen Framework-Familien. Versions-Upgrade-Vergleich ist nicht verfügbar.",

    crossPackReplacementDisclaimer: "Der Wechsel zu einem anderen Framework-Paket ersetzt nach Bestätigung die aktuell aktive Übernahme. Das Datenbankschema unterstützt eine aktive Übernahme pro Mandant mit unveränderlicher Historie.",

    filterFrameworksPlaceholder: "Frameworks nach Name oder Version filtern...",

    adoptedBadge: "Übernommen",

    candidateBadge: "Kandidat",

    inconsistentDigestNotice: "Warnung: Framework-Versionen teilen dieselbe Versions-ID, weisen jedoch unterschiedliche Bundle-Digests auf. Die Manifest-Metadaten sind inkonsistent.",

    // B03 Work Queue & Control Traceability

    navWorkQueue: "Aufgabenliste",

    workQueueTitle: "Tägliche Aufgabenliste",

    workQueueSubtitle: "Operative Warteschlange prioritärer Kontrollen, Nachweisaufgaben und Feststellungen.",

    refreshQueueBtn: "Aufgaben aktualisieren",

    refreshingQueueBtn: "Warteschlange wird aktualisiert...",

    noFrameworkAdopted: "Kein Framework-Paket übernommen",

    noFrameworkAdoptedDesc: "Bitte übernehmen Sie ein Framework-Paket im Katalog, bevor Sie tägliche Aufgaben verwalten.",

    goToFrameworksBtn: "Zu Frameworks",

    controlsDeniedNotice: "Zugriff auf Kontrollaufgabenliste verweigert.",

    assessmentDeniedNotice: "Zugriff auf Bewertungsstatus eingeschränkt (403 Verboten). Angezeigte Einträge spiegeln nur Kontrollaufgaben wider.",

    traceabilityTitle: "Kontroll-Rückverfolgbarkeit",

    traceabilitySubtitle: "Lückenlose Pin-Rückverfolgbarkeit für Kontrollen, Nachweise und Bewertungen.",

    syntheticProvenanceNotice: "Demonstrationsinhalte mit synthetischer Herkunft. Serverstatus und geprüfte Integritätsartefakte bestimmen die Konformität.",

    closeBtn: "Schließen",

    openEvidenceBtn: "Nachweis-Arbeitsbereich öffnen",

    openAssessmentBtn: "Bewertungs-Arbeitsbereich öffnen",

    retryAssessmentsBtn: "Bewertungen wiederholen",

    retryControlsBtn: "Kontrollen wiederholen",

    staleRefreshWarning: "Aktualisierung fehlgeschlagen. Zuvor geladene Arbeitselemente werden angezeigt, können jedoch veraltet sein.",

    assessmentErrorBanner: "Bewertungsdaten konnten nicht geladen werden.",

    controlsErrorBanner: "Kontrollarbeitselemente konnten nicht geladen werden.",

    envelopeMismatchNotice: "Inkompatibler Rahmenwerk-Adoptionskontext zwischen Kontrollen und Bewertungen erkannt.",

    navTargetNotFound: "Das angeforderte Element wurde in der aktuellen Adoption nicht gefunden.",

      envelopeMismatchSelection: "Inkompatible Auswahlrevision zwischen Kontrollen und Bewertungen.",

      envelopeMismatchAnswer: "Inkompatible Antwortrevision zwischen Kontrollen und Bewertungen.",

      allWorkPartial: "Alle Aufgaben ({count} - Unvollständig)",

      allWorkUnavailable: "Alle Aufgaben (Nicht verfügbar)",

      assessmentNeededUnknown: "Prüfung erforderlich (Unbekannt)",

      openFindingsUnknown: "Offene Feststellungen (Unbekannt)",

      dismissBtn: "Verwerfen",

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: "Betrieb",

    operationsTitle: "Betriebs- & Governance-Register",

    operationsSubtitle: "Verwalten Sie Unternehmensrichtlinien, Risikobewertungen & Behandlungen, Inventare und Lieferanten-Compliance.",

    tabPolicies: "Richtlinien",

    tabRisks: "Risiken",

    tabAssets: "Assets",

    tabVendors: "Lieferanten",

    tabTasks: "Aufgaben",

    tabReviews: "Review-Hub",

    tabJobs: "Job-Status",

    tabTraining: "Schulung & LMS",

    trainingAssignmentsTitle: "Schulungszuweisungen",

    trainingCoursesTitle: "Kurskatalog-Referenzen",

    trainingCompletionsTitle: "Verifizierte Abschlüsse",

    trainingPartnerStatus: "Simulierte LMS-Integration (Lokale Vertragsprüfung)",

    registerCourseBtn: "Kursreferenz registrieren",

    assignTrainingBtn: "Schulung zuweisen",

    operationsDeniedNotice: "Zugriff verweigert (403). Sie verfügen nicht über die Berechtigung für dieses Register.",

    operationsReadOnlyNotice: "Schreibgeschützter Modus. Sie können Datensätze ansehen, aber nicht bearbeiten.",

    refreshOperationsBtn: "Register aktualisieren",

    refreshingOperationsBtn: "Aktualisiere...",

    conflictReloadNotice: "Versionskonflikt (409): Der Datensatz wurde anderweitig geändert. Ihr Entwurf bleibt erhalten.",

    conflictReloadBtn: "Serverversion laden",

    uncertainCreateNotice: "Die Netzwerkverbindung wurde unterbrochen. Bitte Server prüfen, um Duplikate zu vermeiden.",

    reconcileNotice: "Abgleich: Übereinstimmender Datensatz auf dem Server gefunden.",

    noRecordSelected: "Wählen Sie einen Datensatz aus oder erstellen Sie einen neuen Eintrag.",

    createRecordBtn: "Neuer Eintrag",

    saveDraftBtn: "Entwurf speichern",

    submitReviewBtn: "Zur Prüfung einreichen",

    approvePolicyBtn: "Richtlinie genehmigen",

    publishPolicyBtn: "Richtlinie veröffentlichen",

    archivePolicyBtn: "Richtlinie archivieren",

    acknowledgePolicyBtn: "Richtlinie bestätigen",

    acknowledgedBadge: "Bestätigt",

    revisionsHistoryTitle: "Versionsverlauf",

    policyOwnerCannotApproveNotice: "Zwei-Personen-Prinzip: Der Autor kann seine eigene Richtlinie nicht selbst genehmigen.",

    treatmentsTitle: "Risikobehandlungen",

    addTreatmentBtn: "Behandlung hinzufügen",

    reviewRecordBtn: "Überprüfung erfassen",

    statusActive: "Aktiv",

    statusDraft: "Entwurf",

    statusInReview: "In Prüfung",

    statusApproved: "Genehmigt",

    statusPublished: "Veröffentlicht",

    statusArchived: "Archiviert",

    },

};