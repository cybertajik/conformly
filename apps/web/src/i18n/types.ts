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
}
