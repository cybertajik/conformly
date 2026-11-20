import type { TranslationDictionary } from "../types";



export const fr: TranslationDictionary = {

  common: {

    save: "Enregistrer",

    cancel: "Annuler",

    delete: "Supprimer",

    confirm: "Confirmer",

    loading: "Chargement...",

    filter: "Filtrer",

    export: "Exporter",

    dismiss: "Ignorer",

    back: "Retour",

    close: "Fermer",

    status: "Statut",

    actions: "Actions",

    search: "Rechercher...",

    refresh: "Actualiser",

    view: "Afficher",

    edit: "Modifier",

    completed: "Terminé",

    inProgress: "En cours",

    pending: "En attente",

    optional: "Facultatif",

    required: "Obligatoire",

    all: "Tous",

    yes: "Oui",

    no: "Non",

  },

  nav: {

    platform: "Plateforme",

    overview: "Vue d'ensemble",

    onboarding: "Intégration",

    organization: "Organisation",

    frameworks: "Référentiels",

    compliance: "Conformité & Preuves",

    risks: "Registre des risques",

    assets: "Registre des actifs",

    vendors: "Registre des tiers",

    preaudit: "Pré-Audit",

    trustCenter: "Centre de confiance",

    lifecycle: "Export & Cycle de vie",

    members: "Membres",

    signOut: "Déconnexion",

    organizationLabel: "Organisation",

  },

  disclaimer: {

    badge: "Avis",

    title: "Conformly est une plateforme de préparation aux audits et d'opérations de conformité, et non un organisme de certification accrédité.",

    text: "Les évaluations pré-audit, les scores de préparation et les badges émis par Conformly reflètent des vérifications déterministes et une posture interne ; ils ne constituent pas des certifications tierces accréditées officielles.",

  },

  onboarding: {

    title: "Intégration et Préparation aux Audits",

    subtitle: "Complétez ces jalons fondamentaux pour préparer votre organisation aux audits de conformité externes.",

    pilotOperational: "Pilote Opérationnel",

    eyebrow: "Préparation Opérationnelle • Pilote Actif",

    orgSlug: "Identifiant Organisation",

    role: "Rôle",

    checklistTitle: "Liste des Jalons",

    checklistSubtitle: "Suivez et enregistrez votre progression dans la préparation aux audits.",

    progressBarLabel: "Progression de l'intégration",

    stepsCompleted: "{completed} sur {total} jalons terminés ({percent}%)",

    allMilestonesComplete: "🎉 Tous les jalons d'intégration sont terminés !",

    allMilestonesCompleteSub: "Votre organisation est entièrement configurée et prête pour les évaluations déterministes de pré-audit.",

    resetProgress: "Réinitialiser la progression",

    markCompleted: "Marquer comme terminé",

    markIncomplete: "Marquer comme en attente",

    step1Title: "Adopter un référentiel de conformité canonique",

    step1Desc: "Sélectionnez des référentiels officiels (ISO/IEC 27001, SOC 2, HIPAA) ou définissez des modèles personnalisés.",

    step1Btn: "Voir le catalogue",

    step2Title: "Mettre en œuvre les contrôles et collecter les preuves",

    step2Desc: "Téléversez des preuves chiffrées par enveloppe AES-256-GCM et reliez les contrôles aux politiques.",

    step2Btn: "Ouvrir la conformité",

    step3Title: "Lancer l'évaluation de pré-audit",

    step3Desc: "Exécutez le calcul déterministe, générez les manifestes d'audit SHA-256 et émettez des badges de préparation.",

    step3Btn: "Démarrer le pré-audit",

    step4Title: "Publier le centre de confiance public",

    step4Desc: "Présentez vos engagements de sécurité, badges vérifiés et certifications tierces.",

    step4Btn: "Centre de confiance",

    step5Title: "Configurer le canal d'alerte anonyme",

    step5Desc: "Fournissez un signalement confidentiel protégé par hachage PBKDF2 sans aucun enregistrement d'adresses IP.",

    step5Btn: "Portail d'alerte",

    supportTitle: "Support Pilote & Prise en Charge",

    supportSubtitle: "Prise en charge sécurité 24/7 • Horaires ouvrés",

    supportNotice: "Pendant le programme pilote, les objectifs de service représentent des directives de réponse opérationnelle (non contractuelles). Les SLAs contractuels seront introduits après 6 mois de production.",

    thSeverity: "Niveau de gravité",

    thClassification: "Classification",

    thResponse: "Objectif de réponse",

    thChannel: "Canal de contact",

    securityRlsTitle: "Sécurité au niveau des lignes (RLS)",

    securityRlsDesc: "Cloisonnement strict au niveau SQL appliqué à chaque requête.",

    securityAesTitle: "Chiffrement AES-256-GCM",

    securityAesDesc: "Clé DEK unique par fichier ; aucune preuve non chiffrée au repos.",

    securityWhistleTitle: "Lanceur d'alerte anonyme",

    securityWhistleDesc: "Clés secrètes PBKDF2 sans aucune journalisation d'IP ou de télémétrie.",

    securityExitTitle: "Sortie de données auditable",

    securityExitDesc: "Fenêtre d'exportation de 30 jours, preuve cryptographique de suppression sous 90 jours.",

  },

  dashboard: {

    title: "Tableau de Bord Exécutif de Conformité",

    subtitle: "Posture en temps réel, suivi de préparation et santé opérationnelle.",

    readinessScore: "Score de Préparation à l'Audit",

    runPreAuditBtn: "Lancer le Pré-Audit",

    continuousTitle: "Évaluation continue de conformité terminée",

    continuousDesc: "{tasks} tâche(s) de remédiation créée(s) • {notifications} notification(s) en file d'attente • {overdue} tâche(s) en retard escaladée(s)",

    adminNotice: "Mode d'isolation administrateur actif. Les dossiers de signalement et preuves restreintes sont soumis à autorisation stricte.",

  },

  status: {

    loadingTitle: "Chargement de Conformly",

    signedOutTitle: "Conformly",

    signedOutDetail: "Opérations de conformité sécurisées pour la préparation aux audits.",

    signInBtn: "Se connecter",

    expiredTitle: "Session expirée",

    expiredDetail: "Veuillez vous reconnecter pour continuer.",

    deniedTitle: "Accès refusé",

    deniedDetail: "Votre compte ne peut pas accéder à cette organisation.",

    noTenantTitle: "Aucune organisation disponible",

    noTenantDetail: "Votre compte n'a pas d'adhésion active. Veuillez contacter un administrateur.",

    eyebrow: "Opérations de conformité sécurisées",

  },

  language: {

    selectorLabel: "Choisir la langue",

  },

  customerDemo: {

    title: "Intégration client et Espace de travail",

    subtitle: "Exploration synthétique et interactive de la conformité",

    syntheticNotice: "Avis : Démonstration synthétique d'intégration client. Ne constitue pas un conseil juridique ou de conformité.",

    answersRevision: "Révision des réponses",

    selectionRevision: "Révision de la sélection",

    companyProfileTitle: "1. Profil d'organisation et Données",

    companyProfileSubtitle: "Sélectionnez un profil modèle ou personnalisez vos réponses pour évaluer l'applicabilité",

    fictionalPreset: "Modèle d'entreprise fictive :",

    alphaName: "Alpha (Cloud/UE)",

    alphaDesc: "Environnement cloud opérant au sein de l'Union européenne",

    betaName: "Beta (Non-Cloud/Mondial)",

    betaDesc: "Infrastructure sur site ou hybride dans des juridictions internationales",

    questionnaireTitle: "Questionnaire d'applicabilité",

    questionnaireSubtitle: "Faits déterministes exploités par le moteur de règles",

    cloudQuestion: "Votre organisation utilise-t-elle une infrastructure cloud publique ou privée ?",

    cloudYes: "Oui",

    cloudNo: "Non",

    cloudUnknown: "Inconnu",

    regionQuestion: "Principale région géographique d'exploitation",

    regionEu: "Union européenne (UE)",

    regionOther: "Autres juridictions",

    regionUnknown: "Inconnu",

    saveAnswers: "Enregistrer les réponses",

    saving: "Enregistrement...",

    answersSaved: "Réponses enregistrées avec succès en tant que révision immuable.",

    unsavedEdits: "Modifications non enregistrées",

    savedRevisionBadge: "Révision enregistrée",

    evaluateTitle: "2. Évaluation du référentiel et Contrôles",

    evaluateSubtitle: "Calculer l'applicabilité déterministe en fonction des faits enregistrés",

    selectPackLabel: "Pack de démonstration :",

    evaluateBtn: "Évaluer l'applicabilité",

    evaluating: "Évaluation en cours...",

    saveFirstNotice: "Enregistrez d'abord les réponses avant d'évaluer",

    evaluationResults: "Résultats de l'évaluation",

    evaluationResultsSubtitle: "Évalué par rapport à la révision des réponses",

    adoptPackBtn: "Adopter le pack",

    adopting: "Adoption en cours...",

    adoptTitle: "Adopter le pack de démonstration",

    adoptSubtitle: "Examinez les exigences, contrôles et écarts avant de confirmer l'adoption.",

    adoptionIntentInvalidated: "L'instantané d'adoption, la sélection du candidat ou la session a changé. Veuillez fermer et réévaluer.",

    adoptSuccess: "Pack de démonstration adopté avec succès.",

    confirmAdopt: "Confirmer l'adoption",

    packComparisonTitle: "Comparaison exacte des packs",

    hideComparison: "Masquer la comparaison",

    comparePacks: "Comparer les packs",

    unchangedReqs: "Exigences inchangées",

    addedReqs: "+ Ajouté dans",

    removedReqs: "- Retiré dans",

    exactVersions: "Versions exactes des exigences :",

    currentAdoption: "Adoption actuelle",

    noAdoption: "Aucun pack adopté pour l'instant",

    staleNotice: "(Obsolète : Réponses mises à jour)",

    ackSyntheticLabel: "Je comprends qu'il s'agit d'un référentiel synthétique de démonstration à des fins d'illustration, et non d'un avis juridique.",

    ackMissingLabel: "Je reconnais que certaines exigences ont le statut NEEDS_INFORMATION en raison de faits manquants et nécessitent des informations supplémentaires.",

    statusApplicable: "APPLICABLE",

    statusNotApplicable: "NON APPLICABLE",

    statusNeedsInfo: "INFORMATION REQUISE",

    summaryApplicable: "Applicable",

    summaryNotApplicable: "Non applicable",

    summaryNeedsInfo: "Info requise",

    summaryTruthfulNotice: "Comptages synthétiques fondés sur les faits enregistrés. Ne constitue pas un score de préparation ou de conformité.",

    controlsCount: "règles",

    controlMapping: "Contrôle commun :",

    viewExplanation: "Voir l'explication",

    hideExplanation: "Masquer l'explication",

    missingFacts: "Faits manquants :",

    noEvaluationYet: "Aucune évaluation calculée. Cliquez ci-dessus sur 'Évaluer l'applicabilité'.",

    reloadWorkspace: "Recharger l'espace",

    savedProgress: "Progression d'intégration",

    stepsSaved: "Faits enregistrés",

    historyTitle: "3. Historique d'adoption et Journal d'audit",

    historySubtitle: "Registre immuable des versions de packs adoptées et des empreintes",

    historyEmpty: "Aucune adoption enregistrée pour l'instant.",

    accessDeniedTitle: "Accès refusé",

    accessDeniedDetail: "Rôle Propriétaire ou Responsable conformité requis.",

    conflictTitle: "Conflit dans l'espace de travail",

    stepProfile: "1. Profil d'entreprise",

    stepEvaluation: "2. Évaluation des règles",

    stepAdoption: "3. Adoption du pack",

    nextStep: "Continuer",

    prevStep: "Retour",

    syntheticDemo: "Démo synthétique",

    evaluationOnly: "Évaluation uniquement",

    stepperAriaLabel: "Étapes d'intégration client",

    noticeAriaLabel: "Avis de démonstration synthétique",

    dismissMessage: "Ignorer le message",

    errorLabel: "Erreur",

    noticeLabel: "Remarque",

    successLabel: "Succès",

    requirementVersion: "Version de l'exigence",

    packVersionId: "ID version du pack",

    bundleDigest: "Condensé du pack",

    adoptedTimestamp: "Horodatage de l'adoption",

    staleEvaluation: "Évaluation obsolète",

    stepCompleted: "Terminé",

    // MVP-B Control Work & Evidence

    controlWorkTitle: "Travaux de contrôle et épinglage des preuves",

    controlWorkSubtitle: "Attribuez des responsables, définissez des échéances, téléchargez des preuves chiffrées et effectuez des examens de pertinence.",

    initWorkBtn: "Initialiser les travaux",

    initializingWork: "Initialisation...",

    initWorkNotice: "Initialisez les éléments de travail associés aux exigences du pack actuellement adopté.",

    noControlWorkYet: "Aucun travail de contrôle initialisé pour cette adoption.",

    assignOwnerLabel: "Responsable",

    dueDateLabel: "Date d'échéance",

    unassignedOwner: "Non attribué",

    saveAssignmentBtn: "Mettre à jour l'attribution",

    savingAssignment: "Enregistrement...",

    uploadEvidenceTitle: "Télécharger et épingler des preuves analysées",

    uploadAndLinkBtn: "Télécharger et épingler",

    uploadingEvidence: "Téléchargement et analyse...",

    selectFileLabel: "Sélectionner un fichier de preuve (max 1 Mo)",

    validUntilLabel: "Date de validité de la preuve",

    rationaleLabel: "Justification de pertinence",

    rationalePlaceholder: "Décrivez pourquoi cette preuve convient à ce contrôle...",

    reuseEvidenceTitle: "Réutilisation délibérée de preuves",

    reuseEvidenceBtn: "Réutiliser la révision",

    reusingEvidence: "Liaison en cours...",

    selectEvidenceToReuse: "Sélectionner une révision de preuve existante",

    reviewTitle: "Enregistrer l'examen de pertinence",

    recordReviewBtn: "Enregistrer l'examen",

    recordingReview: "Enregistrement...",

    acceptDecision: "Accepter (Pertinent)",

    rejectDecision: "Rejeter (Non pertinent)",

    reviewDecisionLabel: "Décision d'examen",

    reviewRationalePlaceholder: "Documenter la justification de l'examen et les notes de vérification...",

    historyEventsTitle: "Historique des révisions du travail de contrôle",

    viewHistoryBtn: "Voir l'historique",

    hideHistoryBtn: "Masquer l'historique",

    downloadPinnedFileBtn: "Télécharger le fichier",

    evidenceValidityAvailable: "Disponible",

    evidenceValidityMissing: "Fichier manquant",

    evidenceValidityNotYetValid: "Pas encore valide",

    evidenceValidityExpired: "Expiré",

    evidenceValidityQuarantined: "En quarantaine",

    evidenceValidityUnavailable: "Indisponible / Altéré",

    evidenceValidityUnverified: "Preuve de scan non vérifiée",

    scanStatusScannedAtLink: "Analysé à la liaison",

    scanStatusUnverified: "Non vérifié",

    reviewStatusPending: "Examen en attente",

    reviewStatusAccepted: "Accepté",

    reviewStatusRejected: "Rejeté",

    workVersionLabel: "Version",

    staleWorkNotice: "Cet élément appartient à une version antérieure des réponses ou du pack ; les modifications sont désactivées.",

    scannerUnavailableNotice: "Scanner antivirus indisponible ou échec de la vérification ; épinglage des preuves bloqué.",

    eventInitialized: "Travail initialisé",

    eventOwnerUpdated: "Attribution mise à jour",

    eventEvidenceLinked: "Preuve liée",

    eventEvidenceReviewed: "Pertinence examinée",

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: "Évaluation humaine et préparation à l'audit",

    assessmentWorkSubtitle: "Effectuez des évaluations humaines selon des procédures synthétiques, gérez les constatations et les corrections, enregistrez des contre-tests explicites et consultez des résumés fiables de préparation.",

    assessmentProcedureTitle: "Procédure d'évaluation synthétique",

    procedureDisclaimer: "Procédure d'évaluation synthétique — Examen humain requis pour la détermination de la conformité.",

    criteriaTitle: "Critères d'évaluation",

    criterionImplementation: "Vérification de la mise en œuvre",

    criterionEvidence: "Suffisance des preuves",

    criterionOperation: "Efficacité opérationnelle",

    resultPass: "Conforme",

    resultPartial: "Partiel",

    resultFail: "Non conforme",

    resultInsufficientEvidence: "Preuves insuffisantes",

    rationaleInputPlaceholder: "Documentez la justification détaillée de l'évaluation et les notes de vérification...",

    recordAssessmentBtn: "Enregistrer l'évaluation humaine",

    recordingAssessment: "Enregistrement de l'évaluation...",

    findingsTitle: "Constatations de défaillances",

    noFindingsYet: "Aucune constatation enregistrée pour ce contrôle.",

    findingSeverity: "Gravité",

    findingStatus: "Statut",

    findingOwner: "Responsable assigné",

    findingDueDate: "Date cible",

    findingRemediationNote: "Note d'avancement de la remédiation",

    updateFindingBtn: "Mettre à jour la remédiation",

    updatingFinding: "Enregistrement...",

    retestTitle: "Enregistrer un contre-test explicite",

    retestBtn: "Enregistrer le contre-test",

    recordingRetest: "Enregistrement du contre-test...",

    selectFindingToResolve: "Sélectionner la constatation à résoudre",

    readinessSummaryTitle: "Résumé fidèle de préparation à l'audit",

    summaryTotalControls: "Total des contrôles",

    summaryPass: "Conformes",

    summaryUnassessed: "Non évalués",

    summaryBlocked: "Contrôles bloqués",

    summaryOpenFindings: "Constatations ouvertes",

    summaryInRemediation: "En cours de remédiation",

    summaryResolvedFindings: "Constatations résolues",

    summaryStaleAssessment: "Évaluations obsolètes",

    summaryReasonCodes: "Motifs de blocage",

    statusUnassessed: "NON_ÉVALUÉ",

    statusPass: "CONFORME",

    statusPartial: "PARTIEL",

    statusFail: "NON_CONFORME",

    statusInsufficientEvidence: "PREUVE_INSUFFISANTE",

    statusStale: "ÉVALUATION_OBSOLÈTE",

    historyJournalTitle: "Journal immuable des évaluations",

    noHistoryEvents: "Aucun événement d'évaluation enregistré pour le moment.",

    selectEvaluation: "-- Sélectionner une évaluation --",

    selectFindingToRetest: "-- Sélectionner une constatation à re-tester --",

    selectResult: "-- Sélectionner un résultat --",

    selectRetestOutcome: "-- Sélectionner le résultat du re-test --",

    selectSeverity: "-- Sélectionner la gravité --",

    noUnresolvedFindings: "Aucune constatation non résolue à re-tester.",

    associatedEvidence: "Preuves associées",

    evaluationRequirements: "Exigences d'évaluation",

    loadingHistory: "Chargement de l'historique...",

    sessionExpired: "Session expirée. Veuillez vous reconnecter.",

    saveRemediationBtn: "Enregistrer la correction",

    cancelBtn: "Annuler",

    severityLow: "FAIBLE",

    severityMedium: "MOYEN",

    severityHigh: "ÉLEVÉ",

    severityCritical: "CRITIQUE",

    statusOpen: "OUVERT",

    statusInRemediation: "EN COURS DE CORRECTION",

    statusResolved: "RÉSOLU",

    resolvesFinding: "(Résout la constatation)",

        createFindingCheckbox: "Enregistrer une constatation de déficience",

evidenceRequiredForPass: "Des preuves sont requises pour un résultat positif",

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: "Pré-audit",
    preauditTitle: "Flux de pré-audit",
    preauditSubtitle: "Geler le périmètre, effectuer un examen indépendant, certifier la préparation et générer des rapports privés",
    createPreauditBtn: "Nouveau cas de pré-audit",
    freezeScopeBtn: "Geler le périmètre",
    submitPreauditReviewBtn: "Soumettre pour examen",
    approvePreauditBtn: "Approbation du propriétaire",
    cancelPreauditBtn: "Annuler le cas",
    downloadReportBtn: "Télécharger l'archive du rapport",
    preauditLeadLabel: "Responsable conformité",
    preauditReviewerLabel: "Examinateur indépendant",
    preauditRevisionLabel: "Révision",
    preauditBlockersTitle: "Bloqueurs de préparation",
    preauditHistoryTitle: "Historique des événements",
    preauditNoCases: "Aucun cas de pré-audit initié. Cliquez sur 'Nouveau cas de pré-audit' pour figer le périmètre.",

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: "Cycle de vie de la vérification de préparation",
    verificationSubtitle: "Gestion des vérifications synthétiques de préparation, transitions d'état, projections privées et événements d'audit",
    issueVerificationBtn: "Délivrer la vérification",
    suspendVerificationBtn: "Suspendre la vérification",
    revokeVerificationBtn: "Révoquer la vérification",
    correctVerificationBtn: "Corriger les métadonnées",
    supersedeVerificationBtn: "Remplacer la vérification",
    reconcileVerificationBtn: "Rapprocher les cycles de vie",
    viewProjectionBtn: "Voir la projection privée",
    verificationStatusLabel: "Statut persistant",
    verificationEffectiveLabel: "État effectif",
    verificationValidityLabel: "Période de validité",
    verificationSyntheticDisclaimer: "RÉSULTAT DE TEST INTERNE SYNTHÉTIQUE PRIVÉ - AUCUNE CERTIFICATION ACCRÉDITÉE",
    verificationHistoryTitle: "Historique de vérification",
    verificationLimitationsTitle: "Périmètre et limitations",
    verificationNoVerifications: "Aucune vérification de préparation délivrée pour ce dossier de pré-audit approuvé.",
    verificationReasonPrompt: "Saisissez le motif de cette action :",
    verificationConfirmAction: "Confirmer l'action de cycle de vie", 
    supersedeNewCaseIdLabel: "ID du cas de pre-audit de remplacement",
    supersedeNewRevisionLabel: "Revision attendue du cas de remplacement",
    supersedeNewSnapshotIdLabel: "ID de l'instantane de remplacement",
    supersedeNewDigestLabel: "Empreinte de l'instantane de remplacement",
    uncertaintyTitle: "Recuperation d'operation incertaine",
    uncertaintyRetryBtn: "Reessayer l'operation",
    uncertaintyDismissBtn: "Acquitter et rejeter",

  },

  portal: {

    brand: "Portail Conformly",

    navOverview: "Vue d'ensemble",

    navCompanySetup: "Configuration entreprise",

    navFrameworks: "Référentiels disponibles",

    navControlsEvidence: "Contrôles et preuves",

    navAssessmentsFindings: "Évaluations et constats",
    navPreaudit: "Pré-audit",

    welcomeTitle: "Bienvenue sur Conformly Conformité",

    welcomeSubtitle: "Automatisation continue de la conformité, mise en œuvre des contrôles et préparation aux audits.",

    tenantLabel: "Organisation",

    roleLabel: "Rôle",

    quickActionsTitle: "Actions rapides",

    nextActionTitle: "Prochaine action recommandée",

    nextActionSetup: "Complétez le profil de votre entreprise pour évaluer l'applicabilité des référentiels.",

    nextActionAdopt: "Évaluez et adoptez un pack de conformité pour générer les éléments de contrôle.",

    nextActionControls: "Assignez des responsables et téléversez des preuves chiffrées pour vos contrôles.",

    nextActionAssess: "Effectuez des évaluations humaines et traitez les constats avant l'audit final.",

    actionConfigureSetup: "Configurer l'entreprise",

    actionExploreFrameworks: "Explorer les référentiels",

    actionManageControls: "Gérer contrôles & preuves",

    actionRunAssessments: "Exécuter les évaluations",

    cardFrameworkStatus: "Adoption du référentiel",

    cardControlsStatus: "Éléments de contrôle",

    cardEvidenceStatus: "Preuves & vérification",

    cardAssessmentStatus: "Préparation à l'audit",

    noPackAdopted: "Aucun pack adopté pour l'instant",

    adoptedPack: "Adopté : {name} (rév. {rev})",

    stalePackWarning: "L'adoption est obsolète suite à des réponses modifiées. Réévaluation requise.",

    controlsCountLabel: "Total des contrôles",

    evidenceItemsLabel: "Liens de preuves",

    reviewsPendingLabel: "Revues en attente",

    findingsSummaryLabel: "État des constats",

    openFindingsCount: "Constats ouverts",

    setupTitle: "Configuration & profil de l'entreprise",

    setupSubtitle: "Fournissez des faits organisationnels vérifiés pour déterminer l'applicabilité.",

    saveSetupBtn: "Enregistrer les réponses",

    savingSetupBtn: "Enregistrement...",

    setupSavedSuccess: "Faits de l'entreprise enregistrés avec succès.",

    unsavedChangesBadge: "Modifications non enregistrées",

    validationErrorsNotice: "Veuillez corriger les erreurs de validation ci-dessous avant de continuer.",

    companyCodeRequired: "La sélection du profil d'entreprise est obligatoire.",

    cloudUsageRequired: "L'utilisation de l'infrastructure cloud doit être spécifiée (Oui ou Non).",

    operatingRegionRequired: "La région opérationnelle principale doit être sélectionnée (UE ou Autre).",

    frameworksTitle: "Référentiels et packs disponibles",

    frameworksSubtitle: "Packs de conformité versionnés, règles d'applicabilité automatisées et adoption formelle.",

    controlsTitle: "Contrôles et preuves chiffrées",

    controlsSubtitle: "Suivez l'état des travaux, assignez des responsables et téléversez des preuves.",

    assessmentsTitle: "Évaluations humaines et constats",

    assessmentsSubtitle: "Évaluez les procédures, enregistrez les constats d'audit et réalisez des retests.",
    preauditSubtitle: "Gel du périmètre, certification d'examinateur indépendant et rapports privés de préparation",

    backToOverview: "Retour à la vue d'ensemble",

    truthfulNotice: "État authentique : toutes les métriques reflètent les données réelles sans scores simulés.",

    menuToggle: "Basculer le menu de navigation",

    signOut: "Se déconnecter",

    breadcrumbHome: "Portail",

    skipToContent: "Passer au contenu principal",

    navAriaLabel: "Navigation du portail",

    unsavedChangesGuidance: "Vous avez des modifications non enregistrées sur les données de l'entreprise. Cliquez sur Enregistrer les réponses pour valider.",

    validateBtn: "Valider",

    evaluatingUsesSavedAnswers: "Vous avez des modifications non enregistrées dans la configuration de l'entreprise. L'évaluation utilisera les réponses enregistrées.",

    statusNotInitialized: "NON INITIALISÉ",

    statusInProgress: "EN COURS",

    statusUnassessed: "NON ÉVALUÉ",

    statusAuditReady: "PRÊT POUR L'AUDIT",

    statusFindings: "CONSTATS",

    statusPinned: "ÉPINGLÉ",

    statusNone: "AUCUN",

    statusUnavailable: "INDISPONIBLE",

    statusAllPassed: "TOUS VALIDÉS",

    statusStale: "OBSOLÈTE",

    statusAdopted: "ADOPTÉ",

    statusDenied: "ACCÈS REFUSÉ",

    statusBlocked: "BLOQUÉ",

    evidenceLinksLabel: "{count} liens de preuves",

    assessmentProgressDetail: "{pass} validé(s) · {findings} constat(s) ouvert(s) · {unassessed} non évalué(s)",

    notAssessed: "Non évalué",

    refreshOverview: "Actualiser la vue d'ensemble",

    retryLoading: "Réessayer le chargement",

    loadingHistory: "Chargement de l'historique...",

    noHistory: "Aucun historique enregistré.",

    noEvidenceLinked: "Aucune preuve liée pour le moment.",

    retestOutcome: "Résultat du retest",

    noUnresolvedFindings: "Aucun constat non résolu éligible au retest.",

    retestCriteria: "Critères d'évaluation du retest",

    retestRationale: "Justification de vérification du retest",

    openStatus: "OUVERT",

    discardDraftConfirm: "Vous avez des modifications non enregistrées dans la configuration entreprise. Abandonner ces modifications et changer de vue ?",

    discardAndLeave: "Abandonner les modifications",

    stayOnPage: "Rester sur la vue",

    keepDraftsNotice: "Brouillon conservé en mémoire",

    navOrganization: "Organisation",

    orgTitle: "Organisation et Structure",

    orgSubtitle: "Gérer les entités juridiques, unités commerciales, emplacements, annuaire des membres et abonnements.",

    legalEntitiesTitle: "Entités Juridiques",

    legalEntitiesSubtitle: "Entités corporatives et juridiques enregistrées.",

    createEntityBtn: "Créer une entité juridique",

    creatingEntityBtn: "Création de l'entité juridique...",

    entityNameLabel: "Nom de l'entité juridique",

    regNumberLabel: "Numéro d'enregistrement",

    countryLabel: "Code pays (2 lettres)",

    primaryEntityLabel: "Définir comme entité juridique principale",

    primaryBadge: "Principal",

    noEntitiesYet: "Aucune entité juridique définie. Créez votre première entité ci-dessus.",

    businessUnitsTitle: "Unités Commerciales",

    businessUnitsSubtitle: "Divisions opérationnelles et départements associés.",

    createUnitBtn: "Créer une unité commerciale",

    creatingUnitBtn: "Création de l'unité commerciale...",

    unitNameLabel: "Nom de l'unité commerciale",

    unitCodeLabel: "Code de l'unité",

    selectEntityPrompt: "Sélectionner une entité juridique...",

    noUnitsYet: "Aucune unité commerciale définie sous cette entité.",

    locationsTitle: "Emplacements",

    locationsSubtitle: "Bureaux, centres de données et installations physiques.",

    createLocationBtn: "Créer un emplacement",

    creatingLocationBtn: "Création de l'emplacement...",

    locationNameLabel: "Nom de l'emplacement",

    cityLabel: "Ville",

    addressLabel: "Adresse",

    noLocationsYet: "Aucun emplacement défini sous cette entité.",

    membersTitle: "Annuaire des Membres et Accès",

    membersSubtitle: "Annuaire serveur en lecture seule des adhésions et rôles du locataire.",

    membersDenied: "Accès refusé : capacité membership:read manquante.",

    noMembersYet: "Aucun membre renvoyé par le service d'annuaire.",

    entitlementsTitle: "Abonnement et Droits Actifs",

    entitlementsSubtitle: "Vue en lecture seule du forfait, des modules activés et des quotas.",

    entitlementsDenied: "Accès refusé : capacité entitlement:read manquante.",

    planLabel: "Forfait Actuel",

    maxMembersLabel: "Limite de membres",

    storageLimitLabel: "Limite de stockage",

    modulesLabel: "Modules activés",

    allowedFrameworksLabel: "Référentiels autorisés",

    versionInspectorTitle: "Inspecteur de Versions de Référentiel",

    versionInspectorSubtitle: "Comparaison déterministe des versions synthétiques, exigences et jalons.",

    compareVersionsBtn: "Comparer les versions",

    currentVersionBadge: "Version actuellement adoptée",

    candidateVersionBadge: "Version candidate du référentiel",

    addedRequirements: "Exigences ajoutées",

    removedRequirements: "Exigences supprimées",

    unchangedRequirements: "Exigences inchangées",

    changedPins: "Jalons de version modifiés",

    rulePinLabel: "Jalon de règle",

    controlPinLabel: "Jalon de contrôle",

    bundleDigestLabel: "Condensé du paquet",

    adoptionHistoryTitle: "Historique immuable d'adoption",

    noAdoptionHistory: "Aucune adoption préalable enregistrée pour ce locataire.",



    loadingEntities: "Chargement des entités juridiques...",

    loadingUnits: "Chargement des unités organisationnelles...",

    loadingLocations: "Chargement des sites...",

    refreshOrgBtn: "Actualiser l'organisation",

    refreshingOrgBtn: "Actualisation...",

    addEntityHeading: "Ajouter une entité juridique",

    addUnitHeading: "Ajouter une unité organisationnelle",

    addLocationHeading: "Ajouter un site",

    selectLegalEntityLabel: "Sélectionner l'entité juridique :",

    entityCreatedSuccess: "Entité juridique créée avec succès.",

    unitCreatedSuccess: "Unité organisationnelle créée avec succès.",

    locationCreatedSuccess: "Site créé avec succès.",

    entityNameRequired: "Le nom de l'entité est requis",

    unitNameRequired: "Le nom de l'unité organisationnelle est requis",

    locationNameRequired: "Le nom du site est requis",

    cityRequired: "La ville est requise",

    countryTwoLetters: "Le code pays doit comporter exactement 2 lettres",

    selectEntityRequired: "Veuillez sélectionner une entité juridique",

    orgManageReadOnlyNotice: "La structure de l'organisation est gérée par les propriétaires et les administrateurs. Votre rôle dispose d'un accès en lecture seule.",

    postAmbiguousNotice: "Une interruption réseau est survenue lors de l'envoi. L'enregistrement a peut-être déjà été créé sur le serveur.",

    checkReconcileBtn: "Vérifier et rapprocher",

    dismissRetryBtn: "Ignorer et réessayer",

    reconciledSuccess: "L'enregistrement a été vérifié sur le serveur.",

    reconcileNotFound: "L'enregistrement n'a pas été trouvé sur le serveur. Vous pouvez réessayer en toute sécurité.",

    adoptedVersionUnavailable: "La version du framework actuellement adoptée n'est pas présente dans le catalogue. La comparaison de versions est impossible.",

    crossPackComparisonNotice: "Les frameworks sélectionnés appartiennent à des familles distinctes. La comparaison de mise à niveau n'est pas disponible.",

    crossPackReplacementDisclaimer: "Le passage à un autre pack de conformité remplace l'adoption active après confirmation. Le schéma de base de données prend en charge une seule adoption active par organisation avec historique immuable préservé.",

    filterFrameworksPlaceholder: "Filtrer les cadres par nom ou version...",

    adoptedBadge: "Adopté",

    candidateBadge: "Candidat",

    inconsistentDigestNotice: "Avertissement : Les versions du framework partagent le même identifiant mais ont des empreintes différentes. Les métadonnées du manifeste sont incohérentes.",

    // B03 Work Queue & Control Traceability

    navWorkQueue: "File de travail",

    workQueueTitle: "File de travail quotidienne",

    workQueueSubtitle: "File opérationnelle des contrôles prioritaires, tâches de preuve et constatations.",

    refreshQueueBtn: "Actualiser la file",

    refreshingQueueBtn: "Actualisation de la file...",

    noFrameworkAdopted: "Aucun pack de référentiel adopté",

    noFrameworkAdoptedDesc: "Veuillez adopter un pack de référentiel dans le catalogue avant de gérer les tâches quotidiennes.",

    goToFrameworksBtn: "Aller aux référentiels",

    controlsDeniedNotice: "Accès refusé à la liste des tâches de contrôle.",

    assessmentDeniedNotice: "Accès restreint au statut d'évaluation (403 Interdit). Les éléments affichés ne reflètent que les tâches de contrôle.",

    traceabilityTitle: "Traçabilité du contrôle",

    traceabilitySubtitle: "Traçabilité complète au niveau des épingles pour contrôles, preuves et évaluations.",

    syntheticProvenanceNotice: "Contenu de démonstration avec provenance synthétique. Le statut du serveur et les artefacts d'intégrité régissent la conformité.",

    closeBtn: "Fermer",

    openEvidenceBtn: "Ouvrir l'espace preuves",

    openAssessmentBtn: "Ouvrir l'espace évaluations",

    retryAssessmentsBtn: "Réessayer les évaluations",

    retryControlsBtn: "Réessayer les contrôles",

    staleRefreshWarning: "Échec de l'actualisation. Affichage des éléments de travail précédemment chargés qui peuvent être obsolètes.",

    assessmentErrorBanner: "Impossible de charger les données d'évaluation.",

    controlsErrorBanner: "Impossible de charger les éléments de travail de contrôle.",

    envelopeMismatchNotice: "Contexte d'adoption du référentiel incompatible détecté entre les contrôles et les évaluations.",

    navTargetNotFound: "L'élément demandé est introuvable dans l'adoption actuelle.",

      envelopeMismatchSelection: "Révision de sélection incompatible entre contrôles et évaluations.",

      envelopeMismatchAnswer: "Révision de réponse incompatible entre contrôles et évaluations.",

      allWorkPartial: "Toutes les tâches ({count} - Partiel)",

      allWorkUnavailable: "Toutes les tâches (Indisponible)",

      assessmentNeededUnknown: "Évaluation requise (Inconnu)",

      openFindingsUnknown: "Constats ouverts (Inconnu)",

      dismissBtn: "Fermer",

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: "Opérations",

    operationsTitle: "Opérations & Registres de gouvernance",

    operationsSubtitle: "Gérez les politiques de l'entreprise, les évaluations des risques, les actifs et les fournisseurs.",

    tabPolicies: "Politiques",

    tabRisks: "Risques",

    tabAssets: "Actifs",

    tabVendors: "Fournisseurs",

    tabTasks: "Tâches",

    tabReviews: "Centre de révision",

    tabJobs: "Statut des tâches",

    tabTraining: "Formation & LMS",

    trainingAssignmentsTitle: "Attributions de formation",

    trainingCoursesTitle: "Références du catalogue de cours",

    trainingCompletionsTitle: "Achèvements vérifiés",

    trainingPartnerStatus: "Intégration LMS simulée (vérification locale du contrat)",

    registerCourseBtn: "Enregistrer une référence de cours",

    assignTrainingBtn: "Attribuer une formation",

    operationsDeniedNotice: "Accès refusé (403). Vous n'avez pas la permission de consulter ce registre.",

    operationsReadOnlyNotice: "Mode lecture seule. Vous pouvez consulter les données mais pas les modifier.",

    refreshOperationsBtn: "Actualiser le registre",

    refreshingOperationsBtn: "Actualisation...",

    conflictReloadNotice: "Conflit détecté (409) : Le document a été modifié. Votre brouillon a été préservé.",

    conflictReloadBtn: "Recharger la version serveur",

    uncertainCreateNotice: "Connexion interrompue lors de la création. Vérifiez le serveur avant de retenter.",

    reconcileNotice: "Rapprochement : Enregistrement correspondant trouvé sur le serveur.",

    noRecordSelected: "Sélectionnez un enregistrement pour afficher ses détails ou créez-en un nouveau.",

    createRecordBtn: "Nouvel enregistrement",

    saveDraftBtn: "Enregistrer brouillon",

    submitReviewBtn: "Soumettre pour examen",

    approvePolicyBtn: "Approuver la politique",

    publishPolicyBtn: "Publier la politique",

    archivePolicyBtn: "Archiver la politique",

    acknowledgePolicyBtn: "Accuser réception",

    acknowledgedBadge: "Reçu et accepté",

    revisionsHistoryTitle: "Historique des révisions",

    policyOwnerCannotApproveNotice: "Double approbation requise : L'auteur ne peut pas approuver sa propre politique.",

    treatmentsTitle: "Traitements du risque",

    addTreatmentBtn: "Ajouter traitement",

    reviewRecordBtn: "Enregistrer révision",

    statusActive: "Actif",

    statusDraft: "Brouillon",

    statusInReview: "En examen",

    statusApproved: "Approuvé",

    statusPublished: "Publié",

    statusArchived: "Archivé",

    },

};