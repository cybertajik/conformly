import type { TranslationDictionary } from "../types";



export const es: TranslationDictionary = {

  common: {

    save: "Guardar",

    cancel: "Cancelar",

    delete: "Eliminar",

    confirm: "Confirmar",

    loading: "Cargando...",

    filter: "Filtrar",

    export: "Exportar",

    dismiss: "Descartar",

    back: "Volver",

    close: "Cerrar",

    status: "Estado",

    actions: "Acciones",

    search: "Buscar...",

    refresh: "Actualizar",

    view: "Ver",

    edit: "Editar",

    completed: "Completado",

    inProgress: "En curso",

    pending: "Pendiente",

    optional: "Opcional",

    required: "Obligatorio",

    all: "Todos",

    yes: "Sí",

    no: "No",

  },

  nav: {

    platform: "Plataforma",

    overview: "Resumen",

    onboarding: "Incorporación",

    organization: "Organización",

    frameworks: "Catálogo de Marcos",

    compliance: "Cumplimiento y Evidencias",

    risks: "Registro de Riesgos",

    assets: "Registro de Activos",

    vendors: "Registro de Proveedores",

    preaudit: "Pre-Auditoría",

    trustCenter: "Centro de Confianza",

    lifecycle: "Exportación y Datos",

    members: "Miembros",

    signOut: "Cerrar sesión",

    organizationLabel: "Organización",

  },

  disclaimer: {

    badge: "Aviso",

    title: "Conformly es una plataforma para preparación de auditorías y operaciones de cumplimiento, no un organismo de certificación acreditado.",

    text: "Las evaluaciones de pre-auditoría, puntuaciones de preparación e insignias emitidas por Conformly reflejan verificaciones deterministas y la postura interna; no constituyen certificaciones acreditadas oficiales de terceros.",

  },

  onboarding: {

    title: "Incorporación y Preparación para Auditorías",

    subtitle: "Complete estos hitos fundamentales para preparar a su organización para auditorías de cumplimiento externas.",

    pilotOperational: "Piloto Operativo",

    eyebrow: "Preparación Operativa • Piloto Activo",

    orgSlug: "Identificador de Organización",

    role: "Rol",

    checklistTitle: "Lista de Hitos",

    checklistSubtitle: "Siga y guarde su progreso en las tareas clave de preparación.",

    progressBarLabel: "Progreso de la incorporación",

    stepsCompleted: "{completed} de {total} hitos completados ({percent}%)",

    allMilestonesComplete: "🎉 ¡Todos los hitos de incorporación completados!",

    allMilestonesCompleteSub: "Su organización está totalmente configurada y lista para evaluaciones de pre-auditoría deterministas.",

    resetProgress: "Restablecer progreso",

    markCompleted: "Marcar como completado",

    markIncomplete: "Marcar como pendiente",

    step1Title: "Adoptar un marco de cumplimiento canónico",

    step1Desc: "Seleccione marcos oficiales (ISO/IEC 27001, SOC 2, HIPAA) o defina modelos personalizados.",

    step1Btn: "Ver catálogo",

    step2Title: "Implementar controles y recopilar evidencias",

    step2Desc: "Suba evidencias con cifrado de sobre AES-256-GCM y asocie controles a políticas.",

    step2Btn: "Abrir cumplimiento",

    step3Title: "Ejecutar verificación de pre-auditoría",

    step3Desc: "Ejecute la puntuación determinista, genere manifiestos SHA-256 y emita credenciales de preparación.",

    step3Btn: "Iniciar pre-auditoría",

    step4Title: "Publicar centro de confianza público",

    step4Desc: "Muestre compromisos de seguridad, credenciales verificadas y certificaciones de terceros.",

    step4Btn: "Centro de confianza",

    step5Title: "Configurar canal de denuncias anónimo",

    step5Desc: "Proporcione denuncias confidenciales protegidas por hash PBKDF2 sin registro de direcciones IP.",

    step5Btn: "Portal de denuncias",

    supportTitle: "Servicio y Soporte del Piloto",

    supportSubtitle: "Admisión de seguridad 24/7 • Horario de oficina",

    supportNotice: "Durante el programa piloto, los objetivos representan pautas operativas (no SLAs contractuales). Los SLAs contractuales se implementarán tras seis meses de producción.",

    thSeverity: "Nivel de gravedad",

    thClassification: "Clasificación",

    thResponse: "Objetivo de respuesta",

    thChannel: "Canal de contacto",

    securityRlsTitle: "Seguridad a nivel de fila (RLS)",

    securityRlsDesc: "Aislamiento estricto aplicado en cada consulta SQL a nivel de base de datos.",

    securityAesTitle: "Cifrado AES-256-GCM",

    securityAesDesc: "Clave DEK única por archivo; cero evidencias sin cifrar en reposo.",

    securityWhistleTitle: "Canal anónimo de denuncias",

    securityWhistleDesc: "Claves secretas PBKDF2 sin registro de IP ni telemetría.",

    securityExitTitle: "Salida de datos auditable",

    securityExitDesc: "Ventana de exportación de 30 días, prueba criptográfica de eliminación en 90 días.",

  },

  dashboard: {

    title: "Panel Ejecutivo de Cumplimiento",

    subtitle: "Postura en tiempo real, seguimiento de preparación y salud operativa.",

    readinessScore: "Puntuación de Preparación",

    runPreAuditBtn: "Ejecutar Pre-Auditoría",

    continuousTitle: "Evaluación continua de cumplimiento completada",

    continuousDesc: "{tasks} tarea(s) de remediación creada(s) • {notifications} notificación(es) en cola • {overdue} tarea(s) vencida(s) escalada(s)",

    adminNotice: "Modo de aislamiento de administrador activo. Los expedientes de denuncias y evidencias confidenciales están restringidos.",

  },

  status: {

    loadingTitle: "Cargando Conformly",

    signedOutTitle: "Conformly",

    signedOutDetail: "Operaciones de cumplimiento seguras para preparación de auditorías.",

    signInBtn: "Iniciar sesión",

    expiredTitle: "Sesión caducada",

    expiredDetail: "Inicie sesión de nuevo para continuar.",

    deniedTitle: "Acceso denegado",

    deniedDetail: "Su cuenta no tiene acceso a esta organización.",

    noTenantTitle: "Sin organización disponible",

    noTenantDetail: "Su cuenta no tiene membresía activa. Solicite acceso a un administrador.",

    eyebrow: "Operaciones de cumplimiento seguras",

  },

  language: {

    selectorLabel: "Seleccionar idioma",

  },

  customerDemo: {

    title: "Onboarding y Espacio de Trabajo del Cliente",

    subtitle: "Exploración interactiva sintética de cumplimiento y proceso de incorporación",

    syntheticNotice: "Aviso: Demostración sintética de incorporación de clientes. No constituye asesoramiento legal o de cumplimiento.",

    answersRevision: "Revisión de respuestas",

    selectionRevision: "Revisión de selección",

    companyProfileTitle: "1. Perfil de Organización y Hechos",

    companyProfileSubtitle: "Seleccione un perfil predeterminado o personalice respuestas para evaluar la aplicabilidad",

    fictionalPreset: "Empresa ficticia predeterminada:",

    alphaName: "Alpha (Cloud/UE)",

    alphaDesc: "Carga de trabajo nativa en la nube operando dentro de la Unión Europea",

    betaName: "Beta (No Cloud/Global)",

    betaDesc: "Infraestructura local o híbrida en jurisdicciones globales",

    questionnaireTitle: "Cuestionario de aplicabilidad",

    questionnaireSubtitle: "Hechos deterministas utilizados por el motor de reglas de cumplimiento",

    cloudQuestion: "¿Su organización utiliza infraestructura de nube pública o privada?",

    cloudYes: "Sí",

    cloudNo: "No",

    cloudUnknown: "Desconocido",

    regionQuestion: "Región geográfica principal de operación",

    regionEu: "Unión Europea (UE)",

    regionOther: "Otras jurisdicciones",

    regionUnknown: "Desconocido",

    saveAnswers: "Guardar respuestas",

    saving: "Guardando...",

    answersSaved: "Respuestas guardadas exitosamente como revisión inmutable.",

    unsavedEdits: "Cambios no guardados",

    savedRevisionBadge: "Revisión guardada",

    evaluateTitle: "2. Evaluación de Marcos y Controles",

    evaluateSubtitle: "Calcular aplicabilidad determinista según los hechos guardados",

    selectPackLabel: "Paquete de marco de demostración:",

    evaluateBtn: "Evaluar aplicabilidad",

    evaluating: "Evaluando...",

    saveFirstNotice: "Guarde las respuestas antes de evaluar",

    evaluationResults: "Resultados de la evaluación",

    evaluationResultsSubtitle: "Evaluado contra la revisión de respuestas",

    adoptPackBtn: "Adoptar paquete",

    adopting: "Adoptando...",

    adoptTitle: "Adoptar paquete de demostración",

    adoptSubtitle: "Revise los requisitos, controles y diferencias antes de confirmar la adopción.",

    adoptionIntentInvalidated: "La instantánea de adopción, la selección de candidatos o la sesión ha cambiado. Cierre y vuelva a evaluar.",

    adoptSuccess: "Paquete de demostración adoptado exitosamente.",

    confirmAdopt: "Confirmar adopción",

    packComparisonTitle: "Comparación exacta de paquetes",

    hideComparison: "Ocultar comparación",

    comparePacks: "Comparar paquetes",

    unchangedReqs: "Requisitos sin cambios",

    addedReqs: "+ Añadido en",

    removedReqs: "- Eliminado en",

    exactVersions: "Versiones exactas de requisitos:",

    currentAdoption: "Adopción actual",

    noAdoption: "Aún no se ha adoptado ningún paquete",

    staleNotice: "(Obsoleto: Respuestas actualizadas)",

    ackSyntheticLabel: "Entiendo que este es un marco sintético de demostración y asignación de controles con fines ilustrativos, no asesoramiento legal.",

    ackMissingLabel: "Reconozco que algunos requisitos se evaluaron como NEEDS_INFORMATION debido a hechos faltantes y requerirán más información.",

    statusApplicable: "APLICABLE",

    statusNotApplicable: "NO APLICABLE",

    statusNeedsInfo: "INFORMACIÓN REQUERIDA",

    summaryApplicable: "Aplicable",

    summaryNotApplicable: "No aplicable",

    summaryNeedsInfo: "Info requerida",

    summaryTruthfulNotice: "Recuentos sintéticos basados en hechos guardados. No es una certificación de cumplimiento ni una puntuación de preparación.",

    controlsCount: "reglas",

    controlMapping: "Control común:",

    viewExplanation: "Ver explicación",

    hideExplanation: "Ocultar explicación",

    missingFacts: "Hechos faltantes:",

    noEvaluationYet: "Aún no se ha calculado ninguna evaluación. Haga clic arriba en 'Evaluar aplicabilidad'.",

    reloadWorkspace: "Recargar espacio",

    savedProgress: "Progreso de onboarding",

    stepsSaved: "Hechos guardados",

    historyTitle: "3. Historial de adopción y Registro de auditoría",

    historySubtitle: "Registro inmutable de versiones de paquetes adoptados y resúmenes de verificación",

    historyEmpty: "Aún no se registran adopciones históricas.",

    accessDeniedTitle: "Acceso denegado",

    accessDeniedDetail: "Se requiere rol de Propietario o Administrador de Cumplimiento.",

    conflictTitle: "Conflicto en el espacio de trabajo",

    stepProfile: "1. Perfil empresarial",

    stepEvaluation: "2. Evaluación de reglas",

    stepAdoption: "3. Adopción de paquete",

    nextStep: "Continuar",

    prevStep: "Atrás",

    syntheticDemo: "Demostración sintética",

    evaluationOnly: "Solo evaluación",

    stepperAriaLabel: "Pasos de incorporación del cliente",

    noticeAriaLabel: "Aviso de demostración sintética",

    dismissMessage: "Descartar mensaje",

    errorLabel: "Error",

    noticeLabel: "Aviso",

    successLabel: "Éxito",

    requirementVersion: "Versión del requisito",

    packVersionId: "ID de versión del paquete",

    bundleDigest: "Resumen del paquete",

    adoptedTimestamp: "Marca de tiempo de adopción",

    staleEvaluation: "Evaluación obsoleta",

    stepCompleted: "Completado",

    // MVP-B Control Work & Evidence

    controlWorkTitle: "Trabajo de control y fijación de evidencias",

    controlWorkSubtitle: "Asigne responsables, establezca fechas límite, cargue y fije evidencias cifradas y realice revisiones de idoneidad.",

    initWorkBtn: "Inicializar trabajo de control",

    initializingWork: "Inicializando...",

    initWorkNotice: "Inicialice los elementos de trabajo asignados a los requisitos del paquete adoptado actualmente.",

    noControlWorkYet: "Aún no se han inicializado elementos de control para esta adopción.",

    assignOwnerLabel: "Responsable",

    dueDateLabel: "Fecha límite",

    unassignedOwner: "Sin asignar",

    saveAssignmentBtn: "Actualizar asignación",

    savingAssignment: "Guardando...",

    uploadEvidenceTitle: "Cargar y fijar evidencia escaneada",

    uploadAndLinkBtn: "Cargar y fijar",

    uploadingEvidence: "Cargando y escaneando...",

    selectFileLabel: "Seleccionar archivo de evidencia (máx. 1 MiB)",

    validUntilLabel: "Fecha de validez de la evidencia",

    rationaleLabel: "Justificación de idoneidad",

    rationalePlaceholder: "Describa por qué esta evidencia es adecuada para este control...",

    reuseEvidenceTitle: "Reutilización deliberada de evidencias",

    reuseEvidenceBtn: "Reutilizar revisión",

    reusingEvidence: "Vinculando...",

    selectEvidenceToReuse: "Seleccionar revisión de evidencia existente",

    reviewTitle: "Registrar revisión de idoneidad",

    recordReviewBtn: "Guardar revisión",

    recordingReview: "Guardando...",

    acceptDecision: "Aceptar (Adecuada)",

    rejectDecision: "Rechazar (Inadecuada)",

    reviewDecisionLabel: "Decisión de revisión",

    reviewRationalePlaceholder: "Documente la justificación de la revisión y notas de verificación...",

    historyEventsTitle: "Historial de revisiones de trabajo de control",

    viewHistoryBtn: "Ver historial",

    hideHistoryBtn: "Ocultar historial",

    downloadPinnedFileBtn: "Descargar archivo",

    evidenceValidityAvailable: "Disponible",

    evidenceValidityMissing: "Archivo faltante",

    evidenceValidityNotYetValid: "Aún no válido",

    evidenceValidityExpired: "Vencido",

    evidenceValidityQuarantined: "En cuarentena",

    evidenceValidityUnavailable: "No disponible / Manipulado",

    evidenceValidityUnverified: "Prueba de escaneo no verificada",

    scanStatusScannedAtLink: "Escaneado al vincular",

    scanStatusUnverified: "No verificado",

    reviewStatusPending: "Revisión pendiente",

    reviewStatusAccepted: "Aceptado",

    reviewStatusRejected: "Rechazado",

    workVersionLabel: "Versión",

    staleWorkNotice: "El elemento pertenece a una revisión anterior de respuestas o paquete; las modificaciones están desactivadas.",

    scannerUnavailableNotice: "Escáner antivirus no disponible o verificación fallida; fijación de evidencias bloqueada.",

    eventInitialized: "Trabajo inicializado",

    eventOwnerUpdated: "Asignación actualizada",

    eventEvidenceLinked: "Evidencia vinculada",

    eventEvidenceReviewed: "Idoneidad revisada",

    // MVP-C Human Assessment & Audit Readiness

    assessmentWorkTitle: "Evaluación humana y preparación para auditoría",

    assessmentWorkSubtitle: "Realice evaluaciones humanas según procedimientos sintéticos, gestione hallazgos y subsanaciones, registre reevaluaciones explícitas e inspeccione resúmenes verídicos de preparación.",

    assessmentProcedureTitle: "Procedimiento de evaluación sintética",

    procedureDisclaimer: "Procedimiento de evaluación sintética — Se requiere revisión humana para determinar el cumplimiento.",

    criteriaTitle: "Criterios de evaluación",

    criterionImplementation: "Verificación de implementación",

    criterionEvidence: "Suficiencia de evidencias",

    criterionOperation: "Eficacia operativa",

    resultPass: "Aprobado",

    resultPartial: "Parcial",

    resultFail: "No aprobado",

    resultInsufficientEvidence: "Evidencia insuficiente",

    rationaleInputPlaceholder: "Documente la justificación detallada de la evaluación y notas de verificación...",

    recordAssessmentBtn: "Registrar evaluación humana",

    recordingAssessment: "Registrando evaluación...",

    findingsTitle: "Hallazgos de deficiencias",

    noFindingsYet: "No hay hallazgos de deficiencias registrados para este control.",

    findingSeverity: "Gravedad",

    findingStatus: "Estado",

    findingOwner: "Responsable asignado",

    findingDueDate: "Fecha límite",

    findingRemediationNote: "Nota de progreso de subsanación",

    updateFindingBtn: "Actualizar subsanación",

    updatingFinding: "Guardando...",

    retestTitle: "Registrar reevaluación explícita",

    retestBtn: "Registrar reevaluación",

    recordingRetest: "Registrando reevaluación...",

    selectFindingToResolve: "Seleccionar hallazgo a resolver",

    readinessSummaryTitle: "Resumen verídico de preparación para auditoría",

    summaryTotalControls: "Total de controles",

    summaryPass: "Aprobados",

    summaryUnassessed: "No evaluados",

    summaryBlocked: "Controles bloqueados",

    summaryOpenFindings: "Hallazgos abiertos",

    summaryInRemediation: "En subsanación",

    summaryResolvedFindings: "Hallazgos resueltos",

    summaryStaleAssessment: "Evaluaciones obsoletas",

    summaryReasonCodes: "Motivos de bloqueo",

    statusUnassessed: "NO_EVALUADO",

    statusPass: "APROBADO",

    statusPartial: "PARCIAL",

    statusFail: "NO_APROBADO",

    statusInsufficientEvidence: "EVIDENCIA_INSUFICIENTE",

    statusStale: "EVALUACIÓN_OBSOLETA",

    historyJournalTitle: "Libro de registro inmutable de evaluaciones",

    noHistoryEvents: "No se han registrado eventos de evaluación todavía.",

    selectEvaluation: "-- Seleccionar evaluación --",

    selectFindingToRetest: "-- Seleccionar hallazgo para volver a probar --",

    selectResult: "-- Seleccionar resultado --",

    selectRetestOutcome: "-- Seleccionar resultado de nueva prueba --",

    selectSeverity: "-- Seleccionar gravedad --",

    noUnresolvedFindings: "No hay hallazgos sin resolver para volver a probar.",

    associatedEvidence: "Evidencia asociada",

    evaluationRequirements: "Requisitos de evaluación",

    loadingHistory: "Cargando historial...",

    sessionExpired: "Sesión caducada. Por favor, inicie sesión de nuevo.",

    saveRemediationBtn: "Guardar remediación",

    cancelBtn: "Cancelar",

    severityLow: "BAJO",

    severityMedium: "MEDIO",

    severityHigh: "ALTO",

    severityCritical: "CRÍTICO",

    statusOpen: "ABIERTO",

    statusInRemediation: "EN REMEDIACIÓN",

    statusResolved: "RESUELTO",

    resolvesFinding: "(Resuelve el hallazgo)",

        createFindingCheckbox: "Registrar hallazgo de deficiencia",

evidenceRequiredForPass: "Se requieren pruebas para el resultado Aprobado",

    // MVP-D Pre-audit Workflow & Private Reports
    tabPreaudit: "Preauditoría",
    preauditTitle: "Flujo de preauditoría",
    preauditSubtitle: "Congelar alcance, realizar revisión independiente, certificar preparación para auditoría y generar informes",
    createPreauditBtn: "Nuevo caso de preauditoría",
    freezeScopeBtn: "Congelar alcance",
    submitPreauditReviewBtn: "Enviar para revisión",
    approvePreauditBtn: "Aprobar como propietario",
    cancelPreauditBtn: "Cancelar caso",
    downloadReportBtn: "Descargar archivo de informe",
    preauditLeadLabel: "Líder de cumplimiento",
    preauditReviewerLabel: "Revisor independiente",
    preauditRevisionLabel: "Revisión",
    preauditBlockersTitle: "Bloqueadores de preparación",
    preauditHistoryTitle: "Historial de eventos",
    preauditNoCases: "No hay casos de preauditoría iniciados. Haga clic en 'Nuevo caso de preauditoría' para congelar el alcance.",

    // MVP-E Readiness Verification Lifecycle
    verificationTitle: "Ciclo de vida de verificación de preparación",
    verificationSubtitle: "Gestión de verificaciones sintéticas de preparación, transiciones de estado, proyecciones privadas y eventos de auditoría",
    issueVerificationBtn: "Emitir verificación",
    suspendVerificationBtn: "Suspender verificación",
    revokeVerificationBtn: "Revocar verificación",
    correctVerificationBtn: "Corregir metadatos",
    supersedeVerificationBtn: "Sustituir verificación",
    reconcileVerificationBtn: "Conciliar ciclos de vida",
    viewProjectionBtn: "Ver proyección privada",
    verificationStatusLabel: "Estado persistido",
    verificationEffectiveLabel: "Estado efectivo",
    verificationValidityLabel: "Ventana de validez",
    verificationSyntheticDisclaimer: "RESULTADO DE PRUEBA INTERNA SINTÉTICA PRIVADA - NO ES UNA CERTIFICACIÓN ACREDITADA",
    verificationHistoryTitle: "Historial de verificación",
    verificationLimitationsTitle: "Alcance y limitaciones",
    verificationNoVerifications: "No se ha emitido ninguna verificación de preparación para este caso de preauditoría aprobado.",
    verificationReasonPrompt: "Ingrese el motivo de esta acción:",
    verificationConfirmAction: "Confirmar acción de ciclo de vida", 
    supersedeNewCaseIdLabel: "ID del caso de preauditoria de sustitucion",
    supersedeNewRevisionLabel: "Revision esperada del caso de sustitucion",
    supersedeNewSnapshotIdLabel: "ID de instantanea de sustitucion",
    supersedeNewDigestLabel: "Resumen de instantanea de sustitucion",
    uncertaintyTitle: "Recuperacion de operacion incierta",
    uncertaintyRetryBtn: "Reintentar operacion",
    uncertaintyDismissBtn: "Reconocer y descartar",

  },

  portal: {

    brand: "Portal Conformly",

    navOverview: "Resumen",

    navCompanySetup: "Configuración de empresa",

    navFrameworks: "Marcos disponibles",

    navControlsEvidence: "Controles y evidencias",

    navAssessmentsFindings: "Evaluaciones y hallazgos",
    navPreaudit: "Preauditoría",

    welcomeTitle: "Bienvenido a Conformly Cumplimiento",

    welcomeSubtitle: "Automatización continua de cumplimiento, implementación de controles y preparación para auditorías.",

    tenantLabel: "Organización",

    roleLabel: "Rol",

    quickActionsTitle: "Acciones rápidas",

    nextActionTitle: "Siguiente acción recomendada",

    nextActionSetup: "Complete los datos y perfil de infraestructura de su empresa para evaluar la aplicabilidad.",

    nextActionAdopt: "Evalúe y adopte un paquete de cumplimiento para generar elementos de control.",

    nextActionControls: "Asigne responsables y suba evidencias cifradas para sus controles adoptados.",

    nextActionAssess: "Realice evaluaciones humanas y resuelva hallazgos antes de la auditoría final.",

    actionConfigureSetup: "Configurar empresa",

    actionExploreFrameworks: "Explorar marcos",

    actionManageControls: "Gestionar controles y evidencias",

    actionRunAssessments: "Ejecutar evaluaciones",

    cardFrameworkStatus: "Adopción de marco",

    cardControlsStatus: "Elementos de control",

    cardEvidenceStatus: "Evidencias y verificación",

    cardAssessmentStatus: "Preparación para auditoría",

    noPackAdopted: "Ningún paquete adoptado aún",

    adoptedPack: "Adoptado: {name} (rev. {rev})",

    stalePackWarning: "La adopción está desactualizada debido a nuevas respuestas. Se requiere reevaluación.",

    controlsCountLabel: "Total de controles",

    evidenceItemsLabel: "Enlaces de evidencia",

    reviewsPendingLabel: "Revisiones pendientes",

    findingsSummaryLabel: "Estado de hallazgos",

    openFindingsCount: "Hallazgos abiertos",

    setupTitle: "Configuración de empresa y perfil de hechos",

    setupSubtitle: "Proporcione hechos verificados de la organización para determinar la aplicabilidad.",

    saveSetupBtn: "Guardar respuestas",

    savingSetupBtn: "Guardando respuestas...",

    setupSavedSuccess: "Datos de la empresa guardados correctamente.",

    unsavedChangesBadge: "Cambios no guardados",

    validationErrorsNotice: "Por favor, corrija los errores de validación a continuación antes de continuar.",

    companyCodeRequired: "La selección del perfil de empresa es obligatoria.",

    cloudUsageRequired: "Debe especificar el uso de infraestructura en la nube (Sí o No).",

    operatingRegionRequired: "Debe seleccionar la región operativa principal (UE u Otra).",

    frameworksTitle: "Marcos y paquetes disponibles",

    frameworksSubtitle: "Paquetes de cumplimiento con versión fija, reglas automatizadas y adopción formal.",

    controlsTitle: "Controles y evidencias cifradas",

    controlsSubtitle: "Siga el estado de trabajo, asigne responsables y suba evidencias escaneadas.",

    assessmentsTitle: "Evaluaciones humanas y hallazgos",

    assessmentsSubtitle: "Evalúe procedimientos, registre hallazgos de auditoría y realice reevaluaciones.",
    preauditSubtitle: "Congelación de alcance, certificación de revisor independiente e informes privados de preparación",

    backToOverview: "Volver al resumen",

    truthfulNotice: "Estado verídico: todas las métricas reflejan datos reales sin puntuaciones simuladas.",

    menuToggle: "Alternar menú de navegación",

    signOut: "Cerrar sesión",

    breadcrumbHome: "Portal",

    skipToContent: "Saltar al contenido principal",

    navAriaLabel: "Navegación del portal",

    unsavedChangesGuidance: "Tiene cambios no guardados en los datos de la empresa. Haga clic en Guardar respuestas para persistir.",

    validateBtn: "Validar",

    evaluatingUsesSavedAnswers: "Tiene cambios no guardados en la Configuración de la empresa. La evaluación utilizará las respuestas guardadas.",

    statusNotInitialized: "NO INICIALIZADO",

    statusInProgress: "EN CURSO",

    statusUnassessed: "NO EVALUADO",

    statusAuditReady: "LISTO PARA AUDITORÍA",

    statusFindings: "HALLAZGOS",

    statusPinned: "VINCULADO",

    statusNone: "NINGUNO",

    statusUnavailable: "NO DISPONIBLE",

    statusAllPassed: "TODOS APROBADOS",

    statusStale: "OBSOLETO",

    statusAdopted: "ADOPTADO",

    statusDenied: "ACCESO DENEGADO",

    statusBlocked: "BLOQUEADO",

    evidenceLinksLabel: "{count} enlaces vinculados",

    assessmentProgressDetail: "{pass} aprobados · {findings} hallazgos abiertos · {unassessed} sin evaluar",

    notAssessed: "No evaluado",

    refreshOverview: "Actualizar resumen",

    retryLoading: "Reintentar carga",

    loadingHistory: "Cargando historial...",

    noHistory: "No se registró historial.",

    noEvidenceLinked: "Aún no hay evidencia vinculada.",

    retestOutcome: "Resultado de reevaluación",

    noUnresolvedFindings: "No hay hallazgos no resueltos elegibles para reevaluación.",

    retestCriteria: "Criterios de reevaluación",

    retestRationale: "Justificación de verificación de reevaluación",

    openStatus: "ABIERTO",

    discardDraftConfirm: "¿Tiene cambios no guardados en la configuración de la empresa. Descartar estos cambios y cambiar de vista?",

    discardAndLeave: "Descartar cambios",

    stayOnPage: "Permanecer en la vista",

    keepDraftsNotice: "Borrador conservado en memoria",

    navOrganization: "Organización",

    orgTitle: "Organización y Estructura",

    orgSubtitle: "Gestione entidades legales, unidades de negocio, ubicaciones, directorio de miembros y planes activos.",

    legalEntitiesTitle: "Entidades Legales",

    legalEntitiesSubtitle: "Entidades corporativas y legales registradas.",

    createEntityBtn: "Crear Entidad Legal",

    creatingEntityBtn: "Creando Entidad Legal...",

    entityNameLabel: "Nombre de la entidad legal",

    regNumberLabel: "Número de registro",

    countryLabel: "Código de país (2 letras)",

    primaryEntityLabel: "Establecer como entidad principal",

    primaryBadge: "Principal",

    noEntitiesYet: "No hay entidades legales definidas. Cree su primera entidad arriba.",

    businessUnitsTitle: "Unidades de Negocio",

    businessUnitsSubtitle: "Divisiones operativas y departamentos vinculados a una entidad legal.",

    createUnitBtn: "Crear Unidad de Negocio",

    creatingUnitBtn: "Creando Unidad de Negocio...",

    unitNameLabel: "Nombre de la unidad de negocio",

    unitCodeLabel: "Código de unidad",

    selectEntityPrompt: "Seleccione una entidad legal...",

    noUnitsYet: "No hay unidades de negocio definidas bajo esta entidad.",

    locationsTitle: "Ubicaciones",

    locationsSubtitle: "Oficinas, centros de datos e instalaciones operativas.",

    createLocationBtn: "Crear Ubicación",

    creatingLocationBtn: "Creando Ubicación...",

    locationNameLabel: "Nombre de la ubicación",

    cityLabel: "Ciudad",

    addressLabel: "Dirección",

    noLocationsYet: "No hay ubicaciones definidas bajo esta entidad.",

    membersTitle: "Directorio de Miembros y Accesos",

    membersSubtitle: "Directorio de solo lectura de membresías, roles y estado del inquilino.",

    membersDenied: "Acceso denegado: falta la capacidad membership:read.",

    noMembersYet: "No se devolvieron miembros del directorio.",

    entitlementsTitle: "Plan Activo y Derechos",

    entitlementsSubtitle: "Vista de solo lectura del plan, módulos habilitados y límites de capacidad.",

    entitlementsDenied: "Acceso denegado: falta la capacidad entitlement:read.",

    planLabel: "Plan Actual",

    maxMembersLabel: "Límite de miembros",

    storageLimitLabel: "Límite de almacenamiento",

    modulesLabel: "Módulos habilitados",

    allowedFrameworksLabel: "Marcos permitidos",

    versionInspectorTitle: "Inspector de Versiones del Marco",

    versionInspectorSubtitle: "Comparación determinista de versiones sintéticas, requisitos y pines de versión.",

    compareVersionsBtn: "Comparar Versiones",

    currentVersionBadge: "Versión actualmente adoptada",

    candidateVersionBadge: "Versión candidata del marco",

    addedRequirements: "Requisitos añadidos",

    removedRequirements: "Requisitos eliminados",

    unchangedRequirements: "Requisitos sin cambios",

    changedPins: "Pines de versión modificados",

    rulePinLabel: "Pin de regla",

    controlPinLabel: "Pin de control",

    bundleDigestLabel: "Resumen del paquete",

    adoptionHistoryTitle: "Historial inmutable de adopción",

    noAdoptionHistory: "No hay adopciones previas registradas para este inquilino.",



    loadingEntities: "Cargando entidades legales...",

    loadingUnits: "Cargando unidades de negocio...",

    loadingLocations: "Cargando ubicaciones...",

    refreshOrgBtn: "Actualizar organización",

    refreshingOrgBtn: "Actualizando...",

    addEntityHeading: "Agregar entidad legal",

    addUnitHeading: "Agregar unidad de negocio",

    addLocationHeading: "Agregar ubicación",

    selectLegalEntityLabel: "Seleccionar entidad legal:",

    entityCreatedSuccess: "Entidad legal creada con éxito.",

    unitCreatedSuccess: "Unidad de negocio creada con éxito.",

    locationCreatedSuccess: "Ubicación creada con éxito.",

    entityNameRequired: "El nombre de la entidad es obligatorio",

    unitNameRequired: "El nombre de la unidad de negocio es obligatorio",

    locationNameRequired: "El nombre de la ubicación es obligatorio",

    cityRequired: "La ciudad es obligatoria",

    countryTwoLetters: "El código de país debe tener exactamente 2 letras",

    selectEntityRequired: "Por favor seleccione una entidad legal",

    orgManageReadOnlyNotice: "La estructura organizacional es administrada por Propietarios y Administradores. El rol actual tiene acceso de solo lectura.",

    postAmbiguousNotice: "Ocurrió una interrupción de red durante el envío. Es posible que el registro ya haya sido creado en el servidor.",

    checkReconcileBtn: "Verificar y conciliar",

    dismissRetryBtn: "Descartar y reintentar",

    reconciledSuccess: "El registro fue verificado como creado en el servidor.",

    reconcileNotFound: "El registro no fue encontrado en el servidor. Puede reintentar de forma segura.",

    adoptedVersionUnavailable: "La versión del marco adoptada actualmente no está presente en el catálogo. No se puede realizar la comparación.",

    crossPackComparisonNotice: "Los marcos seleccionados pertenecen a familias diferentes. La comparación de actualización no está disponible.",

    crossPackReplacementDisclaimer: "Cambiar a un paquete de marco diferente reemplaza la adopción activa actual tras la confirmación. El esquema físico admite una adopción activa por inquilino con historial inmutable conservado.",

    filterFrameworksPlaceholder: "Filtrar marcos por nombre o versión...",

    adoptedBadge: "Adoptado",

    candidateBadge: "Candidato",

    inconsistentDigestNotice: "Advertencia: Las versiones del marco comparten el mismo ID de versión pero tienen resúmenes diferentes. Los metadatos del manifiesto son inconsistentes.",

    // B03 Work Queue & Control Traceability

    navWorkQueue: "Cola de trabajo",

    workQueueTitle: "Cola de trabajo diaria",

    workQueueSubtitle: "Cola operativa de controles priorizados, tareas de evidencia y hallazgos.",

    refreshQueueBtn: "Actualizar cola",

    refreshingQueueBtn: "Actualizando cola...",

    noFrameworkAdopted: "Ningún paquete de marco adoptado",

    noFrameworkAdoptedDesc: "Por favor adopte un paquete de marco en el catálogo antes de gestionar tareas diarias de cumplimiento.",

    goToFrameworksBtn: "Ir a marcos",

    controlsDeniedNotice: "Acceso denegado a la lista de tareas de control.",

    assessmentDeniedNotice: "Acceso restringido al estado de evaluación (403 Prohibido). Los elementos reflejan únicamente tareas de control.",

    traceabilityTitle: "Trazabilidad de control",

    traceabilitySubtitle: "Trazabilidad completa a nivel de pines para control, evidencia y evaluación.",

    syntheticProvenanceNotice: "Contenido de demostración con procedencia sintética. El estado del servidor y los artefactos de integridad rigen el cumplimiento.",

    closeBtn: "Cerrar",

    openEvidenceBtn: "Abrir espacio de evidencias",

    openAssessmentBtn: "Abrir espacio de evaluación",

    retryAssessmentsBtn: "Reintentar evaluaciones",

    retryControlsBtn: "Reintentar controles",

    staleRefreshWarning: "Error de actualización. Mostrando elementos de trabajo cargados previamente que pueden estar desactualizados.",

    assessmentErrorBanner: "No se pudieron cargar los datos de evaluación.",

    controlsErrorBanner: "No se pudieron cargar los elementos de trabajo de control.",

    envelopeMismatchNotice: "Se detectó un contexto de adopción de marco incompatible entre controles y evaluaciones.",

    navTargetNotFound: "El elemento solicitado no se encontró en la adopción actual.",

      envelopeMismatchSelection: "Revisión de selección incompatible entre controles y evaluaciones.",

      envelopeMismatchAnswer: "Revisión de respuesta incompatible entre controles y evaluaciones.",

      allWorkPartial: "Todas las tareas ({count} - Parcial)",

      allWorkUnavailable: "Todas las tareas (No disponible)",

      assessmentNeededUnknown: "Evaluación necesaria (Desconocido)",

      openFindingsUnknown: "Hallazgos abiertos (Desconocido)",

      dismissBtn: "Descartar",

    // B04 Operations: Policies, Risks, Assets, Vendors

    navOperations: "Operaciones",

    operationsTitle: "Operaciones y Registros de Gobernanza",

    operationsSubtitle: "Gestione políticas corporativas, evaluaciones y tratamientos de riesgo, activos y proveedores.",

    tabPolicies: "Políticas",

    tabRisks: "Riesgos",

    tabAssets: "Activos",

    tabVendors: "Proveedores",

    tabTasks: "Tareas",

    tabReviews: "Centro de revisión",

    tabJobs: "Estado del trabajo",

    tabTraining: "Capacitación y LMS",

    trainingAssignmentsTitle: "Asignaciones de capacitación",

    trainingCoursesTitle: "Referencias del catálogo de cursos",

    trainingCompletionsTitle: "Finalizaciones verificadas",

    trainingPartnerStatus: "Integración LMS simulada (verificación de contrato local)",

    registerCourseBtn: "Registrar referencia de curso",

    assignTrainingBtn: "Asignar capacitación",

    operationsDeniedNotice: "Acceso denegado (403). No tiene permiso para consultar este registro.",

    operationsReadOnlyNotice: "Modo de sólo lectura. Puede consultar los registros pero no modificarlos.",

    refreshOperationsBtn: "Actualizar registro",

    refreshingOperationsBtn: "Actualizando...",

    conflictReloadNotice: "Conflicto detectado (409): El registro ha sido modificado. Su borrador se ha conservado.",

    conflictReloadBtn: "Recargar versión del servidor",

    uncertainCreateNotice: "Conexión interrumpida durante la creación. Verifique el servidor antes de reintentar.",

    reconcileNotice: "Reconciliación: Registro coincidente encontrado en el servidor.",

    noRecordSelected: "Seleccione un registro de la lista o cree una nueva entrada.",

    createRecordBtn: "Nuevo registro",

    saveDraftBtn: "Guardar borrador",

    submitReviewBtn: "Enviar a revisión",

    approvePolicyBtn: "Aprobar política",

    publishPolicyBtn: "Publicar política",

    archivePolicyBtn: "Archivar política",

    acknowledgePolicyBtn: "Confirmar lectura",

    acknowledgedBadge: "Confirmado",

    revisionsHistoryTitle: "Historial de revisiones",

    policyOwnerCannotApproveNotice: "Aprobación independiente de 2 personas requerida: El autor no puede aprobar su propia política.",

    treatmentsTitle: "Tratamientos de riesgo",

    addTreatmentBtn: "Añadir tratamiento",

    reviewRecordBtn: "Registrar revisión",

    statusActive: "Activo",

    statusDraft: "Borrador",

    statusInReview: "En revisión",

    statusApproved: "Aprobado",

    statusPublished: "Publicado",

    statusArchived: "Archivado",

    },

};