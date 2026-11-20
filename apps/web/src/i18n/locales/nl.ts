import type { TranslationDictionary } from "../types";



export const nl: TranslationDictionary = {

  common: {

    save: "Opslaan",

    cancel: "Annuleren",

    delete: "Verwijderen",

    confirm: "Bevestigen",

    loading: "Laden...",

    filter: "Filteren",

    export: "Exporteren",

    dismiss: "Sluiten",

    back: "Terug",

    close: "Sluiten",

    status: "Status",

    actions: "Acties",

    search: "Zoeken...",

    refresh: "Vernieuwen",

    view: "Weergeven",

    edit: "Bewerken",

    completed: "Voltooid",

    inProgress: "In behandeling",

    pending: "In afwachting",

    optional: "Optioneel",

    required: "Vereist",

    all: "Alle",

    yes: "Ja",

    no: "Nee",

  },

  nav: {

    platform: "Platform",

    overview: "Overzicht",

    onboarding: "Onboarding",

    organization: "Organisatie",

    frameworks: "Framework-catalogus",

    compliance: "Compliance & Bewijslast",

    risks: "Risicoregister",

    assets: "Assetregister",

    vendors: "Leveranciersregister",

    preaudit: "Pre-Audit",

    trustCenter: "Trust Center & Profiel",

    lifecycle: "Export & Levenscyclus",

    members: "Leden",

    signOut: "Afmelden",

    organizationLabel: "Organisatie",

  },

  disclaimer: {

    badge: "Kennisgeving",

    title: "Conformly is een platform voor audit-gereedheid en compliance-activiteiten, geen geaccrediteerde certificeringsinstantie.",

    text: "Pre-audit beoordelingen, gereedheidsscores en door Conformly verstrekte badges weerspiegelen deterministische verificaties en interne gereedheid; ze vormen geen officiële geaccrediteerde certificeringen van derden.",

  },

  onboarding: {

    title: "Pre-Audit Gereedheid Onboarding",

    subtitle: "Voltooi deze fundamentele mijlpalen om uw organisatie voor te bereiden op externe compliance-audits.",

    pilotOperational: "Pilot Operationeel",

    eyebrow: "Operationele Gereedheid • Actieve Pilot",

    orgSlug: "Organisatiecode",

    role: "Rol",

    checklistTitle: "Mijlpalen Checklist",

    checklistSubtitle: "Volg en bewaar uw voortgang bij cruciale auditvoorbereidingstaken.",

    progressBarLabel: "Voortgang van onboarding",

    stepsCompleted: "{completed} van {total} mijlpalen voltooid ({percent}%)",

    allMilestonesComplete: "🎉 Alle onboarding-mijlpalen voltooid!",

    allMilestonesCompleteSub: "Uw organisatie is volledig geconfigureerd en gereed voor deterministische pre-audit beoordelingen.",

    resetProgress: "Voortgang resetten",

    markCompleted: "Markeren als voltooid",

    markIncomplete: "Markeren als in afwachting",

    step1Title: "Kanoniek compliance-framework overnemen",

    step1Desc: "Selecteer officiële frameworks (ISO/IEC 27001, SOC 2, HIPAA) of definieer aangepaste overlays.",

    step1Btn: "Catalogus bekijken",

    step2Title: "Beheersmaatregelen implementeren & bewijs verzamelen",

    step2Desc: "Upload bewijsmateriaal met AES-256-GCM envelopversleuteling en koppel beheersmaatregelen aan beleid.",

    step2Btn: "Compliance openen",

    step3Title: "Pre-audit gereedheidscontrole uitvoeren",

    step3Desc: "Voer deterministische scoring uit, genereer SHA-256 auditmanifesten en verstrek gereedheidsbewijzen.",

    step3Btn: "Start Pre-Audit",

    step4Title: "Openbaar Trust Center publiceren",

    step4Desc: "Toon beveiligingsverplichtingen, geverifieerde gereedheidsbadges en certificeringen van derden.",

    step4Btn: "Trust Center",

    step5Title: "Anoniem klokkenluiderskanaal configureren",

    step5Desc: "Bied vertrouwelijke meldingen beveiligd met PBKDF2-hash-tracking en zonder registratie van IP-adressen.",

    step5Btn: "Klokkenluidersportaal",

    supportTitle: "Pilot Service & Ondersteuning",

    supportSubtitle: "24/7 Beveiligingsinname • Kantooruren Operatie",

    supportNotice: "Tijdens het pilotprogramma vertegenwoordigen servicedoelstellingen operationele richtlijnen (geen contractuele SLA's). Contractuele SLA's volgen na zes maanden productie.",

    thSeverity: "Ernstniveau",

    thClassification: "Classificatie",

    thResponse: "Reactiedoel",

    thChannel: "Innamekanaal",

    securityRlsTitle: "Row-Level Security (RLS)",

    securityRlsDesc: "Strikte scheiding op database-niveau afgedwongen bij elke SQL-query.",

    securityAesTitle: "AES-256-GCM Versleuteling",

    securityAesDesc: "Unieke DEK per bestand; geen onversleuteld bewijsmateriaal in rust.",

    securityWhistleTitle: "Anonieme Klokkenluider",

    securityWhistleDesc: "PBKDF2-retoursleutels zonder registratie van IP-adressen of telemetrie.",

    securityExitTitle: "Auditeerbare Gegevensexit",

    securityExitDesc: "30 dagen exportvenster, 90 dagen cryptografisch verwijderingsbewijs.",

  },

  dashboard: {

    title: "Executive Compliance Dashboard",

    subtitle: "Realtime houding, gereedheidstracking en operationele gezondheid.",

    readinessScore: "Audit-Gereedheidsscore",

    runPreAuditBtn: "Voer Pre-Audit Controle Uit",

    continuousTitle: "Continue Compliance Evaluatie Voltooid",

    continuousDesc: "{tasks} hersteltaak/taken aangemaakt • {notifications} melding(en) in wachtrij • {overdue} achterstallige taak/taken geëscaleerd",

    adminNotice: "Beheerdersisolatiemodus actief. Vertrouwelijke klokkenluidersdossiers en beperkte bewijzen zijn afgeschermd.",

  },

  status: {

    loadingTitle: "Conformly laden",

    signedOutTitle: "Conformly",

    signedOutDetail: "Veilige compliance-operaties voor audit-gereedheid.",

    signInBtn: "Inloggen",

    expiredTitle: "Sessie verlopen",

    expiredDetail: "Log opnieuw in om door te gaan.",

    deniedTitle: "Toegang geweigerd",

    deniedDetail: "Uw account heeft geen toegang tot deze organisatie.",

    noTenantTitle: "Geen organisatie beschikbaar",

    noTenantDetail: "Uw account heeft geen actief lidmaatschap. Neem contact op met een beheerder.",

    eyebrow: "Veilige compliance-operaties",

  },

  language: {

    selectorLabel: "Selecteer taal",

  },

  customerDemo: {

    title: "Klant-Onboarding en Werkruimte",

    subtitle: "Interactieve synthetische complianceverkenning en onboardingtraject",

    syntheticNotice: "Kennisgeving: Synthetische demonstratie van klant-onboarding. Geen juridisch of compliance-advies.",

    answersRevision: "Antwoord-revisie",

    selectionRevision: "Selectie-revisie",

    companyProfileTitle: "1. Organisatieprofiel en Feiten",

    companyProfileSubtitle: "Selecteer een profielvoorinstelling of pas antwoorden aan om de toepasbaarheid te toetsen",

    fictionalPreset: "Fictieve bedrijfsvoorinstelling:",

    alphaName: "Alpha (Cloud/EU)",

    alphaDesc: "Cloud-native werklast actief binnen de Europese Unie",

    betaName: "Beta (Niet-Cloud/Globaal)",

    betaDesc: "Lokale of hybride infrastructuur in wereldwijde jurisdicties",

    questionnaireTitle: "Toepasbaarheidsvragenlijst",

    questionnaireSubtitle: "Deterministische feiten gebruikt door de compliance-regelmotor",

    cloudQuestion: "Maakt uw organisatie gebruik van openbare of private cloudinfrastructuur?",

    cloudYes: "Ja",

    cloudNo: "Nee",

    cloudUnknown: "Onbekend",

    regionQuestion: "Belangrijkste geografische regio van activiteit",

    regionEu: "Europese Unie (EU)",

    regionOther: "Andere jurisdicties",

    regionUnknown: "Onbekend",

    saveAnswers: "Antwoorden opslaan",

    saving: "Bezig met opslaan...",

    answersSaved: "Antwoorden succesvol opgeslagen als onveranderlijke revisie.",

    unsavedEdits: "Niet-opgeslagen wijzigingen",

    savedRevisionBadge: "Opgeslagen revisie",

    evaluateTitle: "2. Raamwerkevaluatie en Beheersmaatregelen",

    evaluateSubtitle: "Bereken deterministische toepasbaarheid op basis van opgeslagen feiten",

    selectPackLabel: "Demo-raamwerkpakket:",

    evaluateBtn: "Toepasbaarheid evalueren",

    evaluating: "Bezig met evalueren...",

    saveFirstNotice: "Sla eerst de antwoorden op alvorens te evalueren",

    evaluationResults: "Evaluatieresultaten",

    evaluationResultsSubtitle: "Geëvalueerd tegen antwoord-revisie",

    adoptPackBtn: "Pakket adopteren",

    adopting: "Bezig met adopteren...",

    adoptTitle: "Demo-pakket adopteren",

    adoptSubtitle: "Controleer vereisten, beheersmaatregelen en verschillen alvorens de adoptie te bevestigen.",

    adoptionIntentInvalidated: "De adoptie-momentopname, kandidaatselectie of sessie is gewijzigd. Sluit dit venster en evalueer opnieuw.",

    adoptSuccess: "Demo-pakket succesvol geadopteerd.",

    confirmAdopt: "Adoptie bevestigen",

    packComparisonTitle: "Exacte pakketvergelijking",

    hideComparison: "Vergelijking verbergen",

    comparePacks: "Pakketten vergelijken",

    unchangedReqs: "Onveranderde vereisten",

    addedReqs: "+ Toegevoegd in",

    removedReqs: "- Verwijderd in",

    exactVersions: "Exacte versies van vereisten:",

    currentAdoption: "Huidige adoptie",

    noAdoption: "Nog geen pakket geadopteerd",

    staleNotice: "(Verouderd: Antwoorden bijgewerkt)",

    ackSyntheticLabel: "Ik begrijp dat dit een synthetisch demonstratieraamwerk en beheersmaatregelkoppeling is ter illustratie, geen juridisch advies.",

    ackMissingLabel: "Ik bevestig dat sommige vereisten de status NEEDS_INFORMATION hebben gekregen door ontbrekende feiten en verdere gegevens vereisen.",

    statusApplicable: "TOEPASBAAR",

    statusNotApplicable: "NIET TOEPASBAAR",

    statusNeedsInfo: "INFORMATIE VEREIST",

    summaryApplicable: "Toepasbaar",

    summaryNotApplicable: "Niet toepasbaar",

    summaryNeedsInfo: "Info vereist",

    summaryTruthfulNotice: "Synthetische uitkomsttellingen op basis van opgeslagen feiten. Geen compliance-certificering of gereedheidsscore.",

    controlsCount: "regels",

    controlMapping: "Gemeenschappelijke beheersmaatregel:",

    viewExplanation: "Toelichting bekijken",

    hideExplanation: "Toelichting verbergen",

    missingFacts: "Ontbrekende feiten:",

    noEvaluationYet: "Nog geen evaluatie berekend. Klik hierboven op 'Toepasbaarheid evalueren'.",

    reloadWorkspace: "Werkruimte herladen",

    savedProgress: "Onboarding-voortgang",

    stepsSaved: "Feiten opgeslagen",

    historyTitle: "3. Adoptiegeschiedenis en Auditspoor",

    historySubtitle: "Onveranderlijk logboek van geadopteerde pakketversies en controlesommen",

    historyEmpty: "Nog geen historische adopties geregistreerd.",

    accessDeniedTitle: "Toegang geweigerd",

    accessDeniedDetail: "Rol Tenant-Eigenaar of Compliance-Manager vereist.",

    conflictTitle: "Werkruimteconflict",

    stepProfile: "1. Bedrijfsprofiel",

    stepEvaluation: "2. Regelevaluatie",

    stepAdoption: "3. Pakketadoptie",

    nextStep: "Volgende",

    prevStep: "Vorige",

    syntheticDemo: "Synthetische demo",

    evaluationOnly: "Alleen evaluatie",

    stepperAriaLabel: "Klant onboarding stappen",

    noticeAriaLabel: "Kennisgeving synthetische demo",

    dismissMessage: "Bericht sluiten",

    errorLabel: "Fout",

    noticeLabel: "Opmerking",

    successLabel: "Succes",

    requirementVersion: "Vereisteversie",

    packVersionId: "Pakketversie-ID",

    bundleDigest: "Pakket-digest",

    adoptedTimestamp: "Tijdstempel van overname",

    staleEvaluation: "Verouderde evaluatie",

    stepCompleted: "Voltooid",

    // MVP-B Control Work & Evidence

    controlWorkTitle: "Controlewerkzaamheden & bewijsvastlegging",

    controlWorkSubtitle: "Wijs eigenaren toe, stel streefdata in, upload en pin versleuteld bewijsmateriaal en voer geschiktheidsbeoordelingen uit.",

    initWorkBtn: "Controlewerk initialiseren",

    initializingWork: "Initialiseren...",

    initWorkNotice: "Initialiseer werkitems die zijn gekoppeld aan de vereisten van het geadopteerde pakket.",

    noControlWorkYet: "Nog geen controlewerkzaamheden geïnitialiseerd voor deze adoptie.",

    assignOwnerLabel: "Eigenaar",

    dueDateLabel: "Streefdatum",

    unassignedOwner: "Niet toegewezen",

    saveAssignmentBtn: "Toewijzing bijwerken",

    savingAssignment: "Opslaan...",

    uploadEvidenceTitle: "Gescand bewijs uploaden & vastleggen",

    uploadAndLinkBtn: "Uploaden & vastleggen",

    uploadingEvidence: "Uploaden en scannen...",

    selectFileLabel: "Selecteer bewijsbestand (max 1 MiB)",

    validUntilLabel: "Geldigheidsdatum van bewijs",

    rationaleLabel: "Geschiktheidsmotivering",

    rationalePlaceholder: "Beschrijf waarom dit bewijs geschikt is voor deze controle...",

    reuseEvidenceTitle: "Doelbewust hergebruik van bewijs",

    reuseEvidenceBtn: "Revisie hergebruiken",

    reusingEvidence: "Koppelen...",

    selectEvidenceToReuse: "Selecteer bestaande bewijsrevisie",

    reviewTitle: "Geschiktheidsbeoordeling registreren",

    recordReviewBtn: "Beoordeling opslaan",

    recordingReview: "Opslaan...",

    acceptDecision: "Accepteren (Geschikt)",

    rejectDecision: "Afwijzen (Ongeschikt)",

    reviewDecisionLabel: "Beoordelingsbeslissing",

    reviewRationalePlaceholder: "Documenteer de beoordelingsmotivering en verificatienotities...",

    historyEventsTitle: "Revisiegeschiedenis van controlewerk",

    viewHistoryBtn: "Geschiedenis bekijken",

    hideHistoryBtn: "Geschiedenis verbergen",

    downloadPinnedFileBtn: "Bestand downloaden",

    evidenceValidityAvailable: "Beschikbaar",

    evidenceValidityMissing: "Ontbrekend bestand",

    evidenceValidityNotYetValid: "Nog niet geldig",

    evidenceValidityExpired: "Verlopen",

    evidenceValidityQuarantined: "In quarantaine",

    evidenceValidityUnavailable: "Niet beschikbaar / Gemanipuleerd",

    evidenceValidityUnverified: "Ongeverifieerd scanbewijs",

    scanStatusScannedAtLink: "Gescand bij koppeling",

    scanStatusUnverified: "Ongeverifieerd",

    reviewStatusPending: "In afwachting van beoordeling",

    reviewStatusAccepted: "Geaccepteerd",

    reviewStatusRejected: "Afgewezen",

    workVersionLabel: "Versie",

    staleWorkNotice: "Werkitem hoort bij een eerdere antwoord- of pakketrevisie; wijzigingen zijn uitgeschakeld.",

    scannerUnavailableNotice: "Antivirusscanner niet beschikbaar of verificatie mislukt; bewijsvastlegging geblokkeerd.",

    eventInitialized: "Werk geïnitialiseerd",

    eventOwnerUpdated: "Toewijzing bijgewerkt",

    eventEvidenceLinked: "Bewijs gekoppeld",

    eventEvidenceReviewed: "Geschiktheid beoordeeld",

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: "Menselijke beoordeling en auditgereedheid",

    assessmentWorkSubtitle: "Voer menselijke beoordelingen uit tegen synthetische procedures, beheer bevindingen en herstel, leg expliciete hertests vast en inspecteer waarheidsgetrouwe gereedheidsoverzichten.",

    assessmentProcedureTitle: "Synthetische evaluatieprocedure",

    procedureDisclaimer: "Synthetische evaluatieprocedure — Menselijke controle vereist voor nalevingsbepaling.",

    criteriaTitle: "Evaluatiecriteria",

    criterionImplementation: "Verificatie van implementatie",

    criterionEvidence: "Toereikendheid van bewijs",

    criterionOperation: "Operationele effectiviteit",

    resultPass: "Geslaagd",

    resultPartial: "Gedeeltelijk",

    resultFail: "Niet geslaagd",

    resultInsufficientEvidence: "Onvoldoende bewijs",

    rationaleInputPlaceholder: "Documenteer gedetailleerde beoordelingsmotivering en verificatienotities...",

    recordAssessmentBtn: "Menselijke beoordeling vastleggen",

    recordingAssessment: "Beoordeling vastleggen...",

    findingsTitle: "Tekortkomingen en bevindingen",

    noFindingsYet: "Geen tekortkomingen vastgelegd voor deze beheersmaatregel.",

    findingSeverity: "Ernst",

    findingStatus: "Status",

    findingOwner: "Toegewezen eigenaar",

    findingDueDate: "Streefdatum",

    findingRemediationNote: "Voortgangsnotitie herstel",

    updateFindingBtn: "Herstel bijwerken",

    updatingFinding: "Opslaan...",

    retestTitle: "Expliciete hertest vastleggen",

    retestBtn: "Hertest vastleggen",

    recordingRetest: "Hertest vastleggen...",

    selectFindingToResolve: "Te herstellen bevinding selecteren",

    readinessSummaryTitle: "Waarheidsgetrouw auditgereedheidsoverzicht",

    summaryTotalControls: "Totaal beheersmaatregelen",

    summaryPass: "Geslaagd",

    summaryUnassessed: "Niet beoordeeld",

    summaryBlocked: "Geblokkeerde maatregelen",

    summaryOpenFindings: "Openstaande bevindingen",

    summaryInRemediation: "In herstel",

    summaryResolvedFindings: "Opgeloste bevindingen",

    summaryStaleAssessment: "Verouderde beoordelingen",

    summaryReasonCodes: "Blokkeringsredenen",

    statusUnassessed: "NIET_BEOORDEELD",

    statusPass: "GESLAAGD",

    statusPartial: "GEDEELTELIJK",

    statusFail: "NIET_GESLAAGD",

    statusInsufficientEvidence: "ONVOLDOENDE_BEWIJS",

    statusStale: "VEROUDERDE_BEOORDELING",

    historyJournalTitle: "Onveranderlijk beoordelingsjournaal",

    noHistoryEvents: "Nog geen beoordelingsgebeurtenissen geregistreerd.",

    selectEvaluation: "-- Selecteer evaluatie --",

    selectFindingToRetest: "-- Selecteer bevinding om opnieuw te testen --",

    selectResult: "-- Selecteer resultaat --",

    selectRetestOutcome: "-- Selecteer resultaat hertest --",

    selectSeverity: "-- Selecteer ernst --",

    noUnresolvedFindings: "Geen onopgeloste bevindingen om opnieuw te testen.",

    associatedEvidence: "Bijbehorend bewijs",

    evaluationRequirements: "Evaluatievereisten",

    loadingHistory: "Geschiedenis laden...",

    sessionExpired: "Sessie verlopen. Log opnieuw in.",

    saveRemediationBtn: "Herstel opslaan",

    cancelBtn: "Annuleren",

    severityLow: "LAAG",

    severityMedium: "GEMIDDELD",

    severityHigh: "HOOG",

    severityCritical: "KRITIEK",

    statusOpen: "OPEN",

    statusInRemediation: "IN HERSTEL",

    statusResolved: "OPGELOST",

    resolvesFinding: "(Lost bevinding op)",

        createFindingCheckbox: "Tekortkomingsbevinding vastleggen",

evidenceRequiredForPass: "Bewijs is vereist voor het resultaat Voldoende",

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: "Pre-audit",
    preauditTitle: "Pre-audit Workflow",
    preauditSubtitle: "Scope bevriezen, onafhankelijke beoordeling uitvoeren, auditgereedheid certificeren en rapporten genereren",
    createPreauditBtn: "Nieuwe pre-audit case",
    freezeScopeBtn: "Scope bevriezen",
    submitPreauditReviewBtn: "Indienen voor beoordeling",
    approvePreauditBtn: "Eigenaar goedkeuren",
    cancelPreauditBtn: "Case annuleren",
    downloadReportBtn: "Rapportarchief downloaden",
    preauditLeadLabel: "Compliance-leider",
    preauditReviewerLabel: "Onafhankelijke beoordelaar",
    preauditRevisionLabel: "Revisie",
    preauditBlockersTitle: "Gereedheidsblokkades",
    preauditHistoryTitle: "Gebeurtenisgeschiedenis",
    preauditNoCases: "Geen pre-audit cases gestart. Klik op 'Nieuwe pre-audit case' om de scope te bevriezen.",

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: "Levenscyclus van gereedheidsverificatie",
    verificationSubtitle: "Beheer van synthetische gereedheidsverificaties, statusovergangen, privéprojecties en auditgebeurtenissen",
    issueVerificationBtn: "Verificatie uitgeven",
    suspendVerificationBtn: "Verificatie opschorten",
    revokeVerificationBtn: "Verificatie intrekken",
    correctVerificationBtn: "Metagegevens corrigeren",
    supersedeVerificationBtn: "Verificatie vervangen",
    reconcileVerificationBtn: "Levenscycli afstemmen",
    viewProjectionBtn: "Privéprojectie bekijken",
    verificationStatusLabel: "Opgeslagen status",
    verificationEffectiveLabel: "Effectieve status",
    verificationValidityLabel: "Geldigheidstermijn",
    verificationSyntheticDisclaimer: "PRIVÉ SYNTHETISCH INTERN TESTRESULTAAT - GEEN GEACCREDITEERDE CERTIFICERING",
    verificationHistoryTitle: "Verificatiegeschiedenis",
    verificationLimitationsTitle: "Reikwijdte & beperkingen",
    verificationNoVerifications: "Geen gereedheidsverificatie uitgegeven voor dit goedgekeurde pre-auditdossier.",
    verificationReasonPrompt: "Voer reden in voor deze actie:",
    verificationConfirmAction: "Levenscyclusactie bevestigen", 
    supersedeNewCaseIdLabel: "Vervangende pre-audit zaak-ID",
    supersedeNewRevisionLabel: "Verwachte revisie van vervangende zaak",
    supersedeNewSnapshotIdLabel: "Vervangende snapshot-ID",
    supersedeNewDigestLabel: "Vervangende snapshot-digest",
    uncertaintyTitle: "Herstel van onzekere operatie",
    uncertaintyRetryBtn: "Operatie opnieuw proberen",
    uncertaintyDismissBtn: "Bevestigen en sluiten",

  },

  portal: {

    brand: "Conformly Portaal",

    navOverview: "Overzicht",

    navCompanySetup: "Bedrijfsinstellingen",

    navFrameworks: "Beschikbare kaders",

    navControlsEvidence: "Beheersmaatregelen & bewijs",

    navAssessmentsFindings: "Beoordelingen & bevindingen",
    navPreaudit: "Pre-audit",

    welcomeTitle: "Welkom bij Conformly Naleving",

    welcomeSubtitle: "Continue compliance-automatisering, implementatie van beheersmaatregelen en auditgereedheid.",

    tenantLabel: "Organisatie",

    roleLabel: "Rol",

    quickActionsTitle: "Snelle acties",

    nextActionTitle: "Aanbevolen volgende actie",

    nextActionSetup: "Vul uw bedrijfsfeiten en infrastructuurprofiel in om toepasbaarheid te beoordelen.",

    nextActionAdopt: "Beoordeel en adopteer een compliance-pakket om beheerstaken te genereren.",

    nextActionControls: "Wijs eigenaren toe en upload versleuteld bewijs voor uw beheersmaatregelen.",

    nextActionAssess: "Voer menselijke beoordelingen uit en los bevindingen op voor de definitieve audit.",

    actionConfigureSetup: "Bedrijfsinstellingen configureren",

    actionExploreFrameworks: "Kaders verkennen",

    actionManageControls: "Beheersmaatregelen beheren",

    actionRunAssessments: "Beoordelingen uitvoeren",

    cardFrameworkStatus: "Kaderadoptie",

    cardControlsStatus: "Beheerstaken",

    cardEvidenceStatus: "Bewijs & verificatie",

    cardAssessmentStatus: "Auditgereedheid",

    noPackAdopted: "Nog geen pakket geadopteerd",

    adoptedPack: "Geadopteerd: {name} (rev. {rev})",

    stalePackWarning: "De adoptie is verouderd door gewijzigde antwoorden. Herbeoordeling vereist.",

    controlsCountLabel: "Totaal beheersmaatregelen",

    evidenceItemsLabel: "Bewijskoppelingen",

    reviewsPendingLabel: "Openstaande beoordelingen",

    findingsSummaryLabel: "Status bevindingen",

    openFindingsCount: "Open bevindingen",

    setupTitle: "Bedrijfsinstellingen & feitenprofiel",

    setupSubtitle: "Geef geverifieerde bedrijfsfeiten op om de toepasbaarheid van kaders te bepalen.",

    saveSetupBtn: "Antwoorden opslaan",

    savingSetupBtn: "Antwoorden worden opgeslagen...",

    setupSavedSuccess: "Bedrijfsfeiten succesvol opgeslagen.",

    unsavedChangesBadge: "Niet-opgeslagen wijzigingen",

    validationErrorsNotice: "Corrigeer de onderstaande validatiefouten voordat u verdergaat.",

    companyCodeRequired: "Selectie van bedrijfsprofiel is verplicht.",

    cloudUsageRequired: "Gebruik van cloudinfrastructuur moet worden opgegeven (Ja of Nee).",

    operatingRegionRequired: "Primaire operationele regio moet worden geselecteerd (EU of Overig).",

    frameworksTitle: "Beschikbare kaders & pakketten",

    frameworksSubtitle: "Compliance-pakketten met vaste versie, automatische regels en formele adoptie.",

    controlsTitle: "Beheersmaatregelen & versleuteld bewijs",

    controlsSubtitle: "Volg de werkstatus, wijs eigenaren toe en upload gescand bewijsmateriaal.",

    assessmentsTitle: "Menselijke beoordelingen & bevindingen",

    assessmentsSubtitle: "Beoordeel procedures, leg auditbevindingen vast en voer hertesten uit.",
    preauditSubtitle: "Scope bevriezen, onafhankelijke beoordelaarscertificering en private gereedheidsrapporten",

    backToOverview: "Terug naar overzicht",

    truthfulNotice: "Waarheidsgetrouwe status: alle cijfers weerspiegelen werkelijke gegevens zonder gesimuleerde scores.",

    menuToggle: "Navigatiemenu in-/uitschakelen",

    signOut: "Afmelden",

    breadcrumbHome: "Portaal",

    skipToContent: "Naar hoofdinhoud gaan",

    navAriaLabel: "Portaalnavigatie",

    unsavedChangesGuidance: "U heeft niet-opgeslagen wijzigingen in uw bedrijfsgegevens. Klik op Antwoorden opslaan om op te slaan.",

    validateBtn: "Valideren",

    evaluatingUsesSavedAnswers: "U heeft niet-opgeslagen wijzigingen in Bedrijfsinstellingen. Evaluatie gebruikt opgeslagen antwoorden.",

    statusNotInitialized: "NIET GEÏNITIALISEERD",

    statusInProgress: "IN BEHANDELING",

    statusUnassessed: "NIET BEOORDEELD",

    statusAuditReady: "AUDITGEREED",

    statusFindings: "BEVINDINGEN",

    statusPinned: "GEKOPPELD",

    statusNone: "GEEN",

    statusUnavailable: "NIET BESCHIKBAAR",

    statusAllPassed: "ALLES VOLDAAN",

    statusStale: "VEROUDERD",

    statusAdopted: "GEADOPTEERD",

    statusDenied: "TOEGANG GEWEIGERD",

    statusBlocked: "GEBLOKKEERD",

    evidenceLinksLabel: "{count} gekoppelde bewijsverwijzingen",

    assessmentProgressDetail: "{pass} voldaan · {findings} open bevindingen · {unassessed} niet beoordeeld",

    notAssessed: "Niet beoordeeld",

    refreshOverview: "Overzicht vernieuwen",

    retryLoading: "Opnieuw laden",

    loadingHistory: "Geschiedenis laden...",

    noHistory: "Geen geschiedenis vastgelegd.",

    noEvidenceLinked: "Nog geen bewijsmateriaal gekoppeld.",

    retestOutcome: "Hertestresultaat",

    noUnresolvedFindings: "Geen openstaande bevindingen die in aanmerking komen voor hertest.",

    retestCriteria: "Hertestbeoordelingscriteria",

    retestRationale: "Verificatieverantwoording voor hertest",

    openStatus: "OPEN",

    discardDraftConfirm: "U heeft niet-opgeslagen wijzigingen in de bedrijfsinstellingen. Deze wijzigingen negeren en naar een andere weergave overschakelen?",

    discardAndLeave: "Wijzigingen negeren",

    stayOnPage: "Op weergave blijven",

    keepDraftsNotice: "Concept bewaard in geheugen",

    navOrganization: "Organisatie",

    orgTitle: "Organisatie & Structuur",

    orgSubtitle: "Beheer juridische entiteiten, bedrijfseenheden, locaties, leden en actieve abonnementen.",

    legalEntitiesTitle: "Juridische Entiteiten",

    legalEntitiesSubtitle: "Geregistreerde vennootschappelijke en juridische entiteiten.",

    createEntityBtn: "Juridische entiteit aanmaken",

    creatingEntityBtn: "Juridische entiteit aanmaken...",

    entityNameLabel: "Naam van juridische entiteit",

    regNumberLabel: "Registratienummer",

    countryLabel: "Landcode (2 letters)",

    primaryEntityLabel: "Instellen als primaire entiteit",

    primaryBadge: "Primair",

    noEntitiesYet: "Nog geen juridische entiteiten gedefinieerd. Maak hierboven uw eerste entiteit aan.",

    businessUnitsTitle: "Bedrijfseenheden",

    businessUnitsSubtitle: "Operationele afdelingen en divisies gekoppeld aan een entiteit.",

    createUnitBtn: "Bedrijfseenheid aanmaken",

    creatingUnitBtn: "Bedrijfseenheid aanmaken...",

    unitNameLabel: "Naam van bedrijfseenheid",

    unitCodeLabel: "Afdelingscode",

    selectEntityPrompt: "Selecteer een juridische entiteit...",

    noUnitsYet: "Nog geen bedrijfseenheden gedefinieerd onder deze entiteit.",

    locationsTitle: "Locaties",

    locationsSubtitle: "Kantoren, datacenters en fysieke faciliteiten.",

    createLocationBtn: "Locatie aanmaken",

    creatingLocationBtn: "Locatie aanmaken...",

    locationNameLabel: "Locatienaam",

    cityLabel: "Stad",

    addressLabel: "Adres",

    noLocationsYet: "Nog geen locaties gedefinieerd onder deze entiteit.",

    membersTitle: "Leden & Toegangsgids",

    membersSubtitle: "Alleen-lezen servermap met lidmaatschappen, rollen en status van de tenant.",

    membersDenied: "Toegang geweigerd: bevoegdheid membership:read ontbreekt.",

    noMembersYet: "Geen leden gevonden in de gids.",

    entitlementsTitle: "Actief Plan & Rechten",

    entitlementsSubtitle: "Alleen-lezen overzicht van abonnement, actieve modules en limieten.",

    entitlementsDenied: "Toegang geweigerd: bevoegdheid entitlement:read ontbreekt.",

    planLabel: "Huidig Plan",

    maxMembersLabel: "Ledenlimiet",

    storageLimitLabel: "Opslaglimiet",

    modulesLabel: "Ingeschakelde modules",

    allowedFrameworksLabel: "Toegestane frameworks",

    versionInspectorTitle: "Framework Versie-inspecteur",

    versionInspectorSubtitle: "Deterministische vergelijking van synthetische versies, vereisten en versie-pins.",

    compareVersionsBtn: "Versies vergelijken",

    currentVersionBadge: "Momenteel overgenomen versie",

    candidateVersionBadge: "Kandidaat-frameworkversie",

    addedRequirements: "Toegevoegde vereisten",

    removedRequirements: "Verwijderde vereisten",

    unchangedRequirements: "Ongewijzigde vereisten",

    changedPins: "Gewijzigde versie-pins",

    rulePinLabel: "Regel-pin",

    controlPinLabel: "Controle-pin",

    bundleDigestLabel: "Pakket-digest",

    adoptionHistoryTitle: "Onveranderlijke overnamegeschiedenis",

    noAdoptionHistory: "Geen eerdere overnames geregistreerd voor deze tenant.",



    loadingEntities: "Juridische entiteiten laden...",

    loadingUnits: "Bedrijfsonderdelen laden...",

    loadingLocations: "Locaties laden...",

    refreshOrgBtn: "Organisatie vernieuwen",

    refreshingOrgBtn: "Vernieuwen...",

    addEntityHeading: "Juridische entiteit toevoegen",

    addUnitHeading: "Bedrijfsonderdeel toevoegen",

    addLocationHeading: "Locatie toevoegen",

    selectLegalEntityLabel: "Selecteer juridische entiteit:",

    entityCreatedSuccess: "Juridische entiteit succesvol aangemaakt.",

    unitCreatedSuccess: "Bedrijfsonderdeel succesvol aangemaakt.",

    locationCreatedSuccess: "Locatie succesvol aangemaakt.",

    entityNameRequired: "Naam van juridische entiteit is verplicht",

    unitNameRequired: "Naam van bedrijfsonderdeel is verplicht",

    locationNameRequired: "Naam van locatie is verplicht",

    cityRequired: "Stad is verplicht",

    countryTwoLetters: "Landcode moet uit precies 2 letters bestaan",

    selectEntityRequired: "Selecteer een juridische entiteit",

    orgManageReadOnlyNotice: "De organisatiestructuur wordt beheerd door Eigenaren en Beheerders. De huidige rol heeft alleen-lezen toegang.",

    postAmbiguousNotice: "Er is een netwerkfout opgetreden tijdens het verzenden. Het record is mogelijk al aangemaakt op de server.",

    checkReconcileBtn: "Controleren & afstemmen",

    dismissRetryBtn: "Negeren & opnieuw proberen",

    reconciledSuccess: "Record is geverifieerd op de server.",

    reconcileNotFound: "Record is niet gevonden op de server. U kunt het veilig opnieuw proberen.",

    adoptedVersionUnavailable: "De momenteel overgenomen framework-versie is niet aanwezig in het catalogusmanifest. Versievergelijking kan niet worden uitgevoerd.",

    crossPackComparisonNotice: "Geselecteerde frameworks behoren tot verschillende framework-families. Upgrade-vergelijking is niet beschikbaar.",

    crossPackReplacementDisclaimer: "Overschakelen naar een ander frameworkpakket vervangt na bevestiging de huidige actieve adoptie. Het databaseschema ondersteunt één actieve adoptie per tenant met behoud van de onveranderlijke geschiedenis.",

    filterFrameworksPlaceholder: "Frameworks filteren op naam of versie...",

    adoptedBadge: "Geadopteerd",

    candidateBadge: "Kandidaat",

    inconsistentDigestNotice: "Waarschuwing: Framework-versies delen dezelfde versie-ID maar hebben verschillende digests. Manifest-metadata is inconsistent.",

    // B03 Work Queue & Control Traceability

    navWorkQueue: "Werkwachtrij",

    workQueueTitle: "Dagelijkse werkwachtrij",

    workQueueSubtitle: "Operationele wachtrij van geprioriteerde beheersmaatregelen, bewijstaken en bevindingen.",

    refreshQueueBtn: "Wachtrij vernieuwen",

    refreshingQueueBtn: "Wachtrij wordt vernieuwd...",

    noFrameworkAdopted: "Geen frameworkpakket overgenomen",

    noFrameworkAdoptedDesc: "Neem eerst een frameworkpakket over in de catalogus voordat u dagelijkse taken beheert.",

    goToFrameworksBtn: "Naar frameworks",

    controlsDeniedNotice: "Toegang tot controlelijst geweigerd.",

    assessmentDeniedNotice: "Toegang tot beoordelingsstatus beperkt (403 Verboden). Weergegeven items tonen alleen controletaken.",

    traceabilityTitle: "Herleidbaarheid van beheersmaatregelen",

    traceabilitySubtitle: "Volledige pin-herleidbaarheid voor controles, bewijsstukken en beoordelingen.",

    syntheticProvenanceNotice: "Demonstratie-inhoud met synthetische herkomst. Serverstatus en integriteitsartefacten bepalen naleving.",

    closeBtn: "Sluiten",

    openEvidenceBtn: "Bewijswerkruimte openen",

    openAssessmentBtn: "Beoordelingswerkruimte openen",

    retryAssessmentsBtn: "Beoordelingen opnieuw proberen",

    retryControlsBtn: "Controles opnieuw proberen",

    staleRefreshWarning: "Vernieuwen mislukt. Eerder geladen werkitems worden weergegeven die mogelijk verouderd zijn.",

    assessmentErrorBanner: "Beoordelingsgegevens konden niet worden geladen.",

    controlsErrorBanner: "Controle-werkitems konden niet worden geladen.",

    envelopeMismatchNotice: "Incompatibele framework-adoptiecontext gedetecteerd tussen controles en beoordelingen.",

    navTargetNotFound: "Gevraagd item is niet gevonden in de huidige adoptie.",

      envelopeMismatchSelection: "Incompatibele selectierevisie tussen beheersmaatregelen en beoordelingen.",

      envelopeMismatchAnswer: "Incompatibele antwoordrevisie tussen beheersmaatregelen en beoordelingen.",

      allWorkPartial: "Alle taken ({count} - Gedeeltelijk)",

      allWorkUnavailable: "Alle taken (Niet beschikbaar)",

      assessmentNeededUnknown: "Beoordeling vereist (Onbekend)",

      openFindingsUnknown: "Openstaande bevindingen (Onbekend)",

      dismissBtn: "Sluiten",

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: "Operaties",

    operationsTitle: "Operaties & Governance Registers",

    operationsSubtitle: "Beheer bedrijfsbeleid, risicobeoordelingen en -behandelingen, activa en leveranciers.",

    tabPolicies: "Beleid",

    tabRisks: "Risico's",

    tabAssets: "Activa",

    tabVendors: "Leveranciers",

    tabTasks: "Taken",

    tabReviews: "Beoordelingshub",

    tabJobs: "Taakstatus",

    tabTraining: "Training & LMS",

    trainingAssignmentsTitle: "Trainingstoewijzingen",

    trainingCoursesTitle: "Cursuscatalogusreferenties",

    trainingCompletionsTitle: "Geverifieerde voltooiingen",

    trainingPartnerStatus: "Gesimuleerde LMS-integratie (lokale contractverificatie)",

    registerCourseBtn: "Cursusreferentie registreren",

    assignTrainingBtn: "Training toewijzen",

    operationsDeniedNotice: "Toegang geweigerd (403). U heeft geen toestemming om dit register te bekijken.",

    operationsReadOnlyNotice: "Alleen-lezen modus. U kunt records inzien, maar geen wijzigingen opslaan.",

    refreshOperationsBtn: "Register vernieuwen",

    refreshingOperationsBtn: "Vernieuwen...",

    conflictReloadNotice: "Conflict gedetecteerd (409): Het record is elders aangepast. Uw concept is bewaard gebleven.",

    conflictReloadBtn: "Serverversie herladen",

    uncertainCreateNotice: "Verbinding onderbroken tijdens aanmaken. Controleer de server voordat u opnieuw probeert.",

    reconcileNotice: "Afstemming: Overeenkomend record gevonden op de server.",

    noRecordSelected: "Selecteer een record uit de lijst of maak een nieuw item aan.",

    createRecordBtn: "Nieuw record",

    saveDraftBtn: "Concept opslaan",

    submitReviewBtn: "Indienen voor beoordeling",

    approvePolicyBtn: "Beleid goedkeuren",

    publishPolicyBtn: "Beleid publiceren",

    archivePolicyBtn: "Beleid archiveren",

    acknowledgePolicyBtn: "Beleid bevestigen",

    acknowledgedBadge: "Bevestigd",

    revisionsHistoryTitle: "Revisiegeschiedenis",

    policyOwnerCannotApproveNotice: "Onafhankelijke goedkeuring vereist: Auteur kan eigen beleid niet goedkeuren.",

    treatmentsTitle: "Risicobehandelingen",

    addTreatmentBtn: "Behandeling toevoegen",

    reviewRecordBtn: "Beoordeling vastleggen",

    statusActive: "Actief",

    statusDraft: "Concept",

    statusInReview: "In beoordeling",

    statusApproved: "Goedgekeurd",

    statusPublished: "Gepubliceerd",

    statusArchived: "Gearchiveerd",

    },

};

