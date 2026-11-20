import React, { FC, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {

  adoptEvaluation,

  ConflictError,

  evaluateAnswers,

  fetchWorkspace,

  ForbiddenError,

  saveAnswers,

  UnauthorizedError,

} from "./api";

import { ModernWorkspaceShell } from "./ModernWorkspaceShell";

import { ControlEvidenceWorkspace } from "./ControlEvidenceWorkspace";

import { AssessmentWorkspace } from "./AssessmentWorkspace";

import { OrganizationWorkspaceV2 } from "./OrganizationWorkspaceV2";

import { OperationsWorkspace } from "./OperationsWorkspace";

import { FrameworkVersionInspector } from "./FrameworkVersionInspector";

import { WorkQueue } from "./WorkQueue";

import { PreAuditWorkspace } from "./PreAuditWorkspace";

import { isPreauditEnabled } from "./preaudit-api";

import { fetchControlWorkList } from "./control-evidence-api";

import { fetchAssessmentWorkList } from "./assessment-api";

import type { WorkListResponse } from "./control-evidence-types";

import type { AssessmentWorkListResponse } from "./assessment-types";

import { useTranslation } from "../i18n/I18nContext";

import { en } from "../i18n/locales/en";



function useSafeTranslation() {

  try {

    const ctx = useTranslation();

    return { ...ctx, isAvailable: true };

  } catch {

    return {

      isAvailable: false,

      locale: "en" as const,

      setLocale: () => {},

      t: (key: string, params?: Record<string, string | number>) => {

        const parts = key.split(".");

        let val: unknown = en;

        for (const part of parts) {

          if (val && typeof val === "object" && part in val) {

            val = (val as Record<string, unknown>)[part];

          } else {

            return key;

          }

        }

        if (typeof val === "string" && params) {

          return val.replace(/\{([^{}]+)\}/g, (_, k) =>

            params[k] !== undefined ? String(params[k]) : `{${k}}`

          );

        }

        return typeof val === "string" ? val : key;

      },

    };

  }

}

import {

  CompanyCode,

  DemoPack,

  DemoPackRequirement,

  ExplanationTreeNode,

  RegionChoice,

  RequirementEvaluationResult,

  TriState,

  WorkspaceData,

} from "./types";

import "./modern-workspace.css";



export type PortalView =

  | "overview"

  | "work_queue"

  | "company_setup"

  | "frameworks"

  | "controls_evidence"

  | "assessments_findings"

  | "organization"

  | "operations"

  | "preaudit";



export interface NavigationTarget {

  workId: string;

  findingId?: string;

  targetTab?: "control" | "evidence" | "assessment" | "finding";

  nonce: number;

  tenantId?: string;

  adoptionId?: string;

}







export interface CustomerDemoWorkspaceProps {

  tenantId: string;

  token: string;

  userRole?: string;

  userId?: string;

  onSessionExpired?: () => void;

  activePortalView?: PortalView;

  onNavigateView?: (view: PortalView) => void;

  hideShellHeader?: boolean;

  showValidationErrors?: boolean;

}



export const CustomerDemoWorkspace: FC<CustomerDemoWorkspaceProps> = ({

  tenantId,

  token,

  userRole,

  userId,

  onSessionExpired,

  activePortalView,

  onNavigateView,

  hideShellHeader,

  showValidationErrors,

}) => {

  void hideShellHeader;

  void showValidationErrors;

  const { t } = useSafeTranslation();

  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);

  const [loading, setLoading] = useState<boolean>(true);

  const [error, setError] = useState<{ message: string; isConflict?: boolean; isDenied?: boolean } | null>(null);



  // Active step in stepper: 1 = Profile & Facts, 2 = Rule Evaluation, 3 = Adoption & History

  const [activeStep, setActiveStep] = useState<number>(1);

  const [validationErrors, setValidationErrors] = useState<{

    companyCode?: string;

    cloudUsage?: string;

    operatingRegion?: string;

  }>({});



  const handleValidateInputs = () => {

    const errs: { cloudUsage?: string; operatingRegion?: string } = {};

    if (cloudUsage === "unknown") {

      errs.cloudUsage = t("portal.cloudUsageRequired");

    }

    if (operatingRegion === "unknown") {

      errs.operatingRegion = t("portal.operatingRegionRequired");

    }

    setValidationErrors(errs);

  };



  // Accessible functional navigation between onboarding steps

  const handleStepChange = (step: number) => {

    setActiveStep(step);

    if (step === 1) {

      profileSectionRef.current?.focus();

      if (typeof profileSectionRef.current?.scrollIntoView === "function") {

        profileSectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });

      }

    } else if (step === 2) {

      evalSectionRef.current?.focus();

      if (typeof evalSectionRef.current?.scrollIntoView === "function") {

        evalSectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });

      }

    } else if (step === 3) {

      historySectionRef.current?.focus();

      if (typeof historySectionRef.current?.scrollIntoView === "function") {

        historySectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });

      }

    }

  };







  // Form states

  const [companyCode, setCompanyCode] = useState<CompanyCode>("ALPHA");

  const [cloudUsage, setCloudUsage] = useState<TriState>("yes");

  const [operatingRegion, setOperatingRegion] = useState<RegionChoice>("EU");



  // Pack selection & comparison

  const [selectedPackVersionId, setSelectedPackVersionId] = useState<string>("");

  const [showComparison, setShowComparison] = useState<boolean>(false);



  // In-flight action states

  const [saving, setSaving] = useState<boolean>(false);

  const [evaluating, setEvaluating] = useState<boolean>(false);

  const [adopting, setAdopting] = useState<boolean>(false);

  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);



  // Adoption modal & frozen intent

  const [adoptModalOpen, setAdoptModalOpen] = useState<boolean>(false);

  const [frozenAdoptionIntent, setFrozenAdoptionIntent] = useState<{

    tenantId: string;

    sessionEpoch: number;

    candidatePackVersionId: string;

    evaluationId: string;

    bundleDigest: string;

    evaluationDigest: string;

    answerRevision: number;

    selectionRevision: number;

  } | null>(null);

  

  const [ackSynthetic, setAckSynthetic] = useState<boolean>(false);
  const [ackMissing, setAckMissing] = useState<boolean>(false);

  const [contextSession, setContextSession] = useState<{
    tenantId: string;
    token: string;
    epoch: number;
  }>({ tenantId, token, epoch: 1 });

  const isContextStale = contextSession.tenantId !== tenantId || contextSession.token !== token;
  if (isContextStale) {
    setContextSession({
      tenantId,
      token,
      epoch: contextSession.epoch + 1,
    });
    setAdoptModalOpen(false);
    setFrozenAdoptionIntent(null);
    setAckSynthetic(false);
    setAckMissing(false);
  }

  const [controlWorkList, setControlWorkList] = useState<WorkListResponse | null>(null);

  const [assessmentWorkList, setAssessmentWorkList] = useState<AssessmentWorkListResponse | null>(null);

  const [metricsLoading, setMetricsLoading] = useState<boolean>(false);

  const [metricsControlsError, setMetricsControlsError] = useState<string | null>(null);

  const [metricsAssessmentsError, setMetricsAssessmentsError] = useState<string | null>(null);

  // Component/Session epoch and isolated operation generation tracking (P1)
  const sessionEpochRef = useRef<number>(1);



  const loadGenRef = useRef<number>(0);

  const saveGenRef = useRef<number>(0);

  const evalGenRef = useRef<number>(0);

  const adoptGenRef = useRef<number>(0);



  const activeTenantRef = useRef<string>(tenantId);

  const activeLoadControllerRef = useRef<AbortController | null>(null);

  const activeMutationControllerRef = useRef<AbortController | null>(null);



  const metricsGenRef = useRef<number>(0);

  const activeMetricsAbortRef = useRef<AbortController | null>(null);

  const selectedPackRef = useRef(workspace?.selected_pack);

  useEffect(() => {

    selectedPackRef.current = workspace?.selected_pack;

  }, [workspace?.selected_pack]);



  const [metricsEpoch, setMetricsEpoch] = useState<number>(0);



  const activeControlWorkList = workspace?.selected_pack ? controlWorkList : null;

  const activeAssessmentWorkList = workspace?.selected_pack ? assessmentWorkList : null;



  const loadOverviewMetrics = useCallback(

    async (overrideSignal?: AbortSignal) => {

      await Promise.resolve();

      const currentPack = selectedPackRef.current;

      if (!currentPack) {

        setControlWorkList(null);

        setAssessmentWorkList(null);

        setMetricsControlsError(null);

        setMetricsAssessmentsError(null);

        setMetricsLoading(false);

        return;

      }



      if (activeMetricsAbortRef.current && !overrideSignal) {

        activeMetricsAbortRef.current.abort();

      }

      const ac = overrideSignal ? null : new AbortController();

      if (ac) activeMetricsAbortRef.current = ac;

      const signal = overrideSignal || ac?.signal;



      const currentGen = ++metricsGenRef.current;

      const currentTenant = tenantId;

      const currentToken = token;

      const currentRevision = currentPack.selection_revision;



      setMetricsLoading(true);



      try {

        const [ctrlRes, assessRes] = await Promise.allSettled([

          fetchControlWorkList(currentTenant, currentToken, undefined, signal),

          fetchAssessmentWorkList(currentTenant, currentToken, signal),

        ]);



        if (

          signal?.aborted ||

          currentGen !== metricsGenRef.current ||

          activeTenantRef.current !== currentTenant ||

          currentTenant !== tenantId ||

          currentToken !== token ||

          selectedPackRef.current?.selection_revision !== currentRevision

        ) {

          return;

        }



        if (ctrlRes.status === "fulfilled") {

          setControlWorkList(ctrlRes.value);

          setMetricsControlsError(null);

        } else {

          setControlWorkList(null);

          const err = ctrlRes.reason;

          const status = err?.status || (err instanceof UnauthorizedError ? 401 : undefined);

          setMetricsControlsError(status === 403 ? t("portal.statusDenied") : t("portal.statusUnavailable"));

        }



        if (assessRes.status === "fulfilled") {

          setAssessmentWorkList(assessRes.value);

          setMetricsAssessmentsError(null);

        } else {

          setAssessmentWorkList(null);

          const err = assessRes.reason;

          const status = err?.status || (err instanceof UnauthorizedError ? 401 : undefined);

          setMetricsAssessmentsError(status === 403 ? t("portal.statusDenied") : t("portal.statusUnavailable"));

        }

      } finally {

        if (currentGen === metricsGenRef.current) {

          setMetricsLoading(false);

        }

      }

    },

    [tenantId, token, t]

  );



  const loadOverviewMetricsRef = useRef(loadOverviewMetrics);

  useEffect(() => {

    loadOverviewMetricsRef.current = loadOverviewMetrics;

  }, [loadOverviewMetrics]);



  const handleChildDataChange = useCallback(() => {

    setMetricsEpoch((e) => e + 1);

    void loadOverviewMetricsRef.current();

  }, []);



  const [evidenceNavTarget, setEvidenceNavTarget] = useState<NavigationTarget | null>(null);

  const [assessmentNavTarget, setAssessmentNavTarget] = useState<NavigationTarget | null>(null);



  useEffect(() => {

    setTimeout(() => {

      setEvidenceNavTarget(null);

      setAssessmentNavTarget(null);

    }, 0);

  }, [tenantId, workspace?.selected_pack?.evaluation_id]);



  const handleNavigateToControl = useCallback((workId: string) => {

    setEvidenceNavTarget({

      workId,

      targetTab: "control",

      nonce: Date.now(),

      tenantId,

      adoptionId: controlWorkList?.adoption_id || "current",

    });

    onNavigateView?.("controls_evidence");

  }, [onNavigateView, tenantId, controlWorkList?.adoption_id]);



  const handleNavigateToEvidence = useCallback((workId: string) => {

    setEvidenceNavTarget({

      workId,

      targetTab: "evidence",

      nonce: Date.now(),

      tenantId,

      adoptionId: controlWorkList?.adoption_id || "current",

    });

    onNavigateView?.("controls_evidence");

  }, [onNavigateView, tenantId, controlWorkList?.adoption_id]);



  const handleNavigateToAssessment = useCallback((workId: string, findingId?: string) => {

    setAssessmentNavTarget({

      workId,

      findingId,

      targetTab: findingId ? "finding" : "assessment",

      nonce: Date.now(),

      tenantId,

      adoptionId: controlWorkList?.adoption_id || "current",

    });

    onNavigateView?.("assessments_findings");

  }, [onNavigateView, tenantId, controlWorkList?.adoption_id]);



  const selectedPackVersion = workspace?.selected_pack?.pack_version_id;

  const selectionRevision = workspace?.selected_pack?.selection_revision;



  useEffect(() => {

    let ignore = false;

    void (async () => {

      await Promise.resolve();

      if (ignore) return;

      if (selectedPackVersion) {

        void loadOverviewMetricsRef.current();

      } else {

        setControlWorkList(null);

        setAssessmentWorkList(null);

        setMetricsControlsError(null);

        setMetricsAssessmentsError(null);

        setMetricsLoading(false);

      }

    })();

    return () => {

      ignore = true;

      if (activeMetricsAbortRef.current) {

        activeMetricsAbortRef.current.abort();

      }

    };

  }, [selectedPackVersion, selectionRevision]);



  // Auto-refresh metrics on return to overview

  const prevActivePortalViewRef = useRef<PortalView | undefined>(activePortalView);

  useEffect(() => {

    if (activePortalView === "overview" && prevActivePortalViewRef.current !== "overview") {

      void loadOverviewMetricsRef.current();

    }

    prevActivePortalViewRef.current = activePortalView;

  }, [activePortalView]);

  const wasModalOpenRef = useRef<boolean>(false);



  // Accessible modal focus transfer, trap, and restoration

  useEffect(() => {

    if (adoptModalOpen) {

      wasModalOpenRef.current = true;

      const timer = setTimeout(() => {

        const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(

          'input[type="checkbox"], button:not([disabled])'

        );

        firstFocusable?.focus();

      }, 0);

      return () => clearTimeout(timer);

    } else if (wasModalOpenRef.current && openerRef.current) {

      wasModalOpenRef.current = false;

      openerRef.current.focus();

    }

  }, [adoptModalOpen]);



  const handleModalKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {

    if (e.key === "Escape") {

      if (!adopting) {

        e.stopPropagation();

        setAdoptModalOpen(false);

      }

      return;

    }

    if (e.key === "Tab") {

      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(

        'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])'

      );

      if (!focusables || focusables.length === 0) return;

      const first = focusables[0];

      const last = focusables[focusables.length - 1];

      if (e.shiftKey && document.activeElement === first) {

        e.preventDefault();

        last.focus();

      } else if (!e.shiftKey && document.activeElement === last) {

        e.preventDefault();

        first.focus();

      }

    }

  };







  // Accessible navigation and focus restoration refs

  const profileSectionRef = useRef<HTMLElement | null>(null);

  const evalSectionRef = useRef<HTMLElement | null>(null);

  const historySectionRef = useRef<HTMLElement | null>(null);

  const openerRef = useRef<HTMLButtonElement | null>(null);

  const dialogRef = useRef<HTMLDivElement | null>(null);



  const loadData = useCallback(

    async (signal?: AbortSignal, syncForm: boolean = true) => {

      const currentLoadGen = ++loadGenRef.current;

      const currentTenant = tenantId;

      const currentEpoch = sessionEpochRef.current;

      setLoading(true);

      setError(null);



      try {

        const data = await fetchWorkspace(currentTenant, token, signal);

        if (

          signal?.aborted ||

          currentLoadGen !== loadGenRef.current ||

          activeTenantRef.current !== currentTenant ||

          sessionEpochRef.current !== currentEpoch

        ) {

          return;

        }



        setWorkspace(data);



        // Sync form with current answers if requested

        if (syncForm && data.answers) {

          const code = (data.answers.company_code as CompanyCode) || "ALPHA";

          setCompanyCode(code);

          const rawFacts = data.answers.answers || {};



          // Look up fact definition IDs from manifest

          const cloudFact = data.manifest?.fact_definitions?.find(

            (f) => f.key === "synthetic_wp09_uses_cloud"

          );

          const cloudVal =

            rawFacts["synthetic_wp09_uses_cloud"] ??

            (cloudFact ? (rawFacts[cloudFact.version_id] ?? rawFacts[cloudFact.id]) : undefined);



          const regFact = data.manifest?.fact_definitions?.find(

            (f) => f.key === "synthetic_wp09_operating_region"

          );

          const regVal =

            rawFacts["synthetic_wp09_operating_region"] ??

            (regFact ? (rawFacts[regFact.version_id] ?? rawFacts[regFact.id]) : undefined);



          setCloudUsage(cloudVal === true ? "yes" : cloudVal === false ? "no" : "unknown");

          setOperatingRegion(regVal === "EU" ? "EU" : regVal === "OTHER" ? "OTHER" : "unknown");

        }



        // Set default pack version if not set yet, without resetting unsaved user edits

        if (data.manifest?.packs?.length > 0) {

          setSelectedPackVersionId((prev) => prev || data.latest_evaluation?.pack_version_id || data.manifest.packs[0].pack_version_id);

        }

        void loadOverviewMetricsRef.current(signal);

      } catch (err: unknown) {

        if (

          signal?.aborted ||

          currentLoadGen !== loadGenRef.current ||

          activeTenantRef.current !== currentTenant ||

          sessionEpochRef.current !== currentEpoch

        ) {

          return;

        }



        if (err instanceof UnauthorizedError || (err as { status?: number })?.status === 401) {

          setWorkspace(null);

          onSessionExpired?.();

          return;

        }



        if (err instanceof ForbiddenError) {

          setError({

            message: err.detail || "Access denied: Whole-tenant Owner or Compliance Manager required.",

            isDenied: true,

          });

        } else if (err instanceof ConflictError) {

          setError({

            message: err.detail || (err instanceof Error ? err.message : null) || "Workspace state conflict. Please reload.",

            isConflict: true,

          });

        } else {

          setError({

            message: (err instanceof Error ? err.message : null) || "Failed to load customer onboarding demo.",

          });

        }

      } finally {

        if (

          currentLoadGen === loadGenRef.current &&

          activeTenantRef.current === currentTenant &&

          sessionEpochRef.current === currentEpoch

        ) {

          setLoading(false);

        }

      }

    },

    [tenantId, token, onSessionExpired, setCompanyCode, setCloudUsage, setOperatingRegion]

  );



  const loadDataRef = useRef(loadData);

  useEffect(() => {

    loadDataRef.current = loadData;

  }, [loadData]);



  // Synchronously abort in-flight requests on tenant switch, token change, or unmount

  useEffect(() => {
    sessionEpochRef.current = contextSession.epoch;
    const epoch = contextSession.epoch;
    activeTenantRef.current = tenantId;



    if (activeLoadControllerRef.current) {

      activeLoadControllerRef.current.abort();

    }

    if (activeMutationControllerRef.current) {

      activeMutationControllerRef.current.abort();

    }



    const controller = new AbortController();

    activeLoadControllerRef.current = controller;

    const epochRef = sessionEpochRef;



    void (async () => {

      await Promise.resolve();

      if (epochRef.current !== epoch) return;

      setSaving(false);

      setEvaluating(false);

      setAdopting(false);

      setError(null);

      setActionSuccessMsg(null);

      await loadDataRef.current(controller.signal);

    })();



    return () => {

      epochRef.current++;

      controller.abort();

      if (activeMutationControllerRef.current) {

        activeMutationControllerRef.current.abort();

      }

      setAdoptModalOpen(false);

      setFrozenAdoptionIntent(null);

      setAckSynthetic(false);

      setAckMissing(false);

    };

  }, [tenantId, token, contextSession.epoch]);



  // Handle company preset selection

  const handleCompanyChange = (code: CompanyCode) => {

    setCompanyCode(code);

    if (code === "ALPHA") {

      setCloudUsage("yes");

      setOperatingRegion("EU");

    } else {

      setCloudUsage("no");

      setOperatingRegion("OTHER");

    }

  };



  // Determine if there are unsaved edits compared to persisted answers

  const hasUnsavedChanges = useMemo(() => {

    if (!workspace?.answers) return companyCode !== "ALPHA" || cloudUsage !== "yes" || operatingRegion !== "EU";

    const rawFacts = workspace.answers.answers || {};

    const cloudFact = workspace.manifest?.fact_definitions?.find(

      (f) => f.key === "synthetic_wp09_uses_cloud"

    );

    const cloudVal =

      rawFacts["synthetic_wp09_uses_cloud"] ??

      (cloudFact ? (rawFacts[cloudFact.version_id] ?? rawFacts[cloudFact.id]) : undefined);



    const regFact = workspace.manifest?.fact_definitions?.find(

      (f) => f.key === "synthetic_wp09_operating_region"

    );

    const regVal =

      rawFacts["synthetic_wp09_operating_region"] ??

      (regFact ? (rawFacts[regFact.version_id] ?? rawFacts[regFact.id]) : undefined);



    const savedCloud = cloudVal === true ? "yes" : cloudVal === false ? "no" : "unknown";

    const savedRegion = regVal === "EU" ? "EU" : regVal === "OTHER" ? "OTHER" : "unknown";

    const savedCompany = (workspace.answers.company_code as CompanyCode) || "ALPHA";



    return companyCode !== savedCompany || cloudUsage !== savedCloud || operatingRegion !== savedRegion;

  }, [workspace, companyCode, cloudUsage, operatingRegion]);



  // Handle save answers

  const handleSave = async () => {

    if (!workspace || saving || evaluating || adopting) return;

    const saveId = ++saveGenRef.current;

    const currentTenant = tenantId;

    const currentEpoch = sessionEpochRef.current;



    if (activeMutationControllerRef.current) {

      activeMutationControllerRef.current.abort();

    }

    const controller = new AbortController();

    activeMutationControllerRef.current = controller;



    setAdoptModalOpen(false);

    setFrozenAdoptionIntent(null);

    setAckSynthetic(false);

    setAckMissing(false);

    setSaving(true);

    setError(null);

    setActionSuccessMsg(null);



    const usesCloudBool = cloudUsage === "yes" ? true : cloudUsage === "no" ? false : null;

    const regionEnum = operatingRegion === "EU" ? "EU" : operatingRegion === "OTHER" ? "OTHER" : null;



    try {

      await saveAnswers(

        currentTenant,

        token,

        {

          expected_revision: workspace.current_revision,

          company_code: companyCode,

          answers: {

            synthetic_wp09_uses_cloud: usesCloudBool,

            synthetic_wp09_operating_region: regionEnum,

          },

        },

        controller.signal

      );



      if (

        controller.signal.aborted ||

        saveId !== saveGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch

      ) {

        return;

      }



      setActionSuccessMsg(t("customerDemo.answersSaved"));

      await loadData(undefined, true);

    } catch (err: unknown) {

      if (

        controller.signal.aborted ||

        saveId !== saveGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch

      ) {

        return;

      }



      if (err instanceof UnauthorizedError || (err as { status?: number })?.status === 401) {

        setWorkspace(null);

        setAdoptModalOpen(false);

        setFrozenAdoptionIntent(null);

        setAckSynthetic(false);

        setAckMissing(false);

        onSessionExpired?.();

        return;

      }



      const isConflict =

        err instanceof ConflictError ||

        (err as { status?: number })?.status === 409 ||

        (err instanceof Error && /conflict/i.test(err.message));



      if (isConflict) {

        setError({

          message: (err as { detail?: string })?.detail || (err instanceof Error ? err.message : null) || "Conflict: Workspace was modified elsewhere. Please reload and retry.",

          isConflict: true,

        });

      } else {

        setError({ message: err instanceof Error ? err.message : "Failed to save answers." });

      }

    } finally {

      if (

        saveId === saveGenRef.current &&

        activeTenantRef.current === currentTenant &&

        sessionEpochRef.current === currentEpoch

      ) {

        setSaving(false);

      }

    }

  };



  const handlePackChange = (newPackVersionId: string) => {

    if (saving || evaluating || adopting) return;

    setSelectedPackVersionId(newPackVersionId);

    if (adoptModalOpen) {

      setAdoptModalOpen(false);

      setFrozenAdoptionIntent(null);

      setAckSynthetic(false);

      setAckMissing(false);

    }

  };



  // Handle evaluate answers against selected pack

  const handleEvaluate = async () => {

    if (!workspace || !selectedPackVersionId || saving || evaluating || adopting) return;

    const evalId = ++evalGenRef.current;

    const currentTenant = tenantId;

    const currentEpoch = sessionEpochRef.current;

    const candidateId = selectedPackVersionId;



    if (activeMutationControllerRef.current) {

      activeMutationControllerRef.current.abort();

    }

    const controller = new AbortController();

    activeMutationControllerRef.current = controller;



    setEvaluating(true);

    setError(null);

    setActionSuccessMsg(null);



    try {

      await evaluateAnswers(

        currentTenant,

        token,

        {

          expected_revision: workspace.current_revision,

          pack_version_id: candidateId,

        },

        controller.signal

      );



      if (

        controller.signal.aborted ||

        evalId !== evalGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch ||

        candidateId !== selectedPackVersionId

      ) {

        return;

      }



      setActionSuccessMsg("Applicability evaluated successfully.");

      await loadData(undefined, false);

      // Automatically advance to Step 2 results view if on step 1

      setActiveStep(2);

    } catch (err: unknown) {

      if (

        controller.signal.aborted ||

        evalId !== evalGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch ||

        candidateId !== selectedPackVersionId

      ) {

        return;

      }



      if (err instanceof UnauthorizedError || (err as { status?: number })?.status === 401) {

        setWorkspace(null);

        setAdoptModalOpen(false);

        setFrozenAdoptionIntent(null);

        setAckSynthetic(false);

        setAckMissing(false);

        onSessionExpired?.();

        return;

      }



      if (err instanceof ConflictError) {

        setError({

          message: err.detail || (err instanceof Error ? err.message : null) || "Conflict: Workspace revision changed. Please reload.",

          isConflict: true,

        });

      } else {

        setError({ message: err instanceof Error ? err.message : "Failed to evaluate answers." });

      }

    } finally {

      if (

        evalId === evalGenRef.current &&

        activeTenantRef.current === currentTenant &&

        sessionEpochRef.current === currentEpoch

      ) {

        setEvaluating(false);

      }

    }

  };



  const handleOpenAdoptModal = () => {

    if (!workspace || !usableEvaluation || saving || evaluating || adopting) return;

    setFrozenAdoptionIntent({

      tenantId,

      sessionEpoch: contextSession.epoch,

      candidatePackVersionId: selectedPackVersionId,

      evaluationId: usableEvaluation.id,

      bundleDigest: usableEvaluation.bundle_digest,

      evaluationDigest: usableEvaluation.content_digest,

      answerRevision: usableEvaluation.answer_revision,

      selectionRevision: workspace.selection_revision,

    });

    setAckSynthetic(false);

    setAckMissing(false);

    setAdoptModalOpen(true);

  };



  // Handle adoption submission

  const handleAdopt = async () => {

    if (

      !workspace ||

      !usableEvaluation ||

      !frozenAdoptionIntent ||

      saving ||

      evaluating ||

      adopting

    ) return;

    const adoptId = ++adoptGenRef.current;

    const currentTenant = tenantId;

    const currentEpoch = sessionEpochRef.current;

    const intent = frozenAdoptionIntent;



    if (
      isContextStale ||
      intent.tenantId !== currentTenant ||

      intent.sessionEpoch !== currentEpoch ||

      intent.candidatePackVersionId !== selectedPackVersionId ||

      intent.evaluationId !== usableEvaluation.id ||

      intent.bundleDigest !== usableEvaluation.bundle_digest ||

      intent.evaluationDigest !== usableEvaluation.content_digest ||

      intent.answerRevision !== workspace.current_revision ||

      intent.selectionRevision !== workspace.selection_revision

    ) {

      setAdoptModalOpen(false);

      setFrozenAdoptionIntent(null);

      setAckSynthetic(false);

      setAckMissing(false);

      setError({ message: "Candidate selection, evaluation snapshot, or session changed. Please review and retry." });

      return;

    }



    if (activeMutationControllerRef.current) {

      activeMutationControllerRef.current.abort();

    }

    const controller = new AbortController();

    activeMutationControllerRef.current = controller;



    setAdopting(true);

    setError(null);

    setActionSuccessMsg(null);



    try {

      await adoptEvaluation(

        currentTenant,

        token,

        {

          expected_revision: intent.answerRevision,

          evaluation_id: intent.evaluationId,

          pack_version_id: intent.candidatePackVersionId,

          acknowledge_synthetic: ackSynthetic,

          acknowledge_missing_information: ackMissing,

        },

        controller.signal

      );



      if (

        controller.signal.aborted ||

        adoptId !== adoptGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch

      ) {

        return;

      }



      setAdoptModalOpen(false);

      setFrozenAdoptionIntent(null);

      setAckSynthetic(false);

      setAckMissing(false);

      setActionSuccessMsg(t("customerDemo.adoptSuccess"));

      await loadData(undefined, false);

      // Advance to Step 3 adoption & history review

      setActiveStep(3);

    } catch (err: unknown) {

      if (

        controller.signal.aborted ||

        adoptId !== adoptGenRef.current ||

        activeTenantRef.current !== currentTenant ||

        sessionEpochRef.current !== currentEpoch

      ) {

        return;

      }



      if (err instanceof UnauthorizedError || (err as { status?: number })?.status === 401) {

        setWorkspace(null);

        setAdoptModalOpen(false);

        setFrozenAdoptionIntent(null);

        setAckSynthetic(false);

        setAckMissing(false);

        onSessionExpired?.();

        return;

      }



      if (err instanceof ConflictError) {

        setError({

          message: err.detail || (err instanceof Error ? err.message : null) || "Conflict: Evaluation was modified. Please reload.",

          isConflict: true,

        });

      } else {

        setError({ message: err instanceof Error ? err.message : "Failed to adopt pack." });

      }

    } finally {

      if (

        adoptId === adoptGenRef.current &&

        activeTenantRef.current === currentTenant &&

        sessionEpochRef.current === currentEpoch

      ) {

        setAdopting(false);

      }

    }

  };



  const manifest = workspace?.manifest;

  const packs = useMemo(() => manifest?.packs ?? [], [manifest]);

  const latestEval = workspace?.latest_evaluation;

  const selectedPack = workspace?.selected_pack;



  const usableEvaluation =

    latestEval &&

    latestEval.pack_version_id === selectedPackVersionId &&

    latestEval.answer_revision === workspace?.current_revision

      ? latestEval

      : null;



  const isModalIntentValid = Boolean(
    !isContextStale &&
    adoptModalOpen &&
    frozenAdoptionIntent &&
    frozenAdoptionIntent.tenantId === tenantId &&
    frozenAdoptionIntent.sessionEpoch === contextSession.epoch &&

    frozenAdoptionIntent.candidatePackVersionId === selectedPackVersionId &&

    usableEvaluation &&

    frozenAdoptionIntent.evaluationId === usableEvaluation.id &&

    frozenAdoptionIntent.bundleDigest === usableEvaluation.bundle_digest &&

    frozenAdoptionIntent.evaluationDigest === usableEvaluation.content_digest &&

    frozenAdoptionIntent.answerRevision === workspace?.current_revision &&

    frozenAdoptionIntent.selectionRevision === workspace?.selection_revision

  );



  // Truthful counts summary (NEVER percentages or compliance scores)

  const outcomeCounts = useMemo(() => {

    const evalToUse = usableEvaluation || latestEval;

    if (!evalToUse?.results) {

      return { applicable: 0, notApplicable: 0, needsInfo: 0, total: 0 };

    }

    let applicable = 0;

    let notApplicable = 0;

    let needsInfo = 0;

    for (const r of evalToUse.results) {

      if (r.result === "APPLICABLE") applicable++;

      else if (r.result === "NOT_APPLICABLE") notApplicable++;

      else if (r.result === "NEEDS_INFORMATION") needsInfo++;

    }

    return {

      applicable,

      notApplicable,

      needsInfo,

      total: evalToUse.results.length,

    };

  }, [usableEvaluation, latestEval]);



  // Group packs by pack_id with local filter support within the finite manifest

  const [packFilterQuery, setPackFilterQuery] = useState("");



  const filteredPacks = useMemo(() => {

    const q = packFilterQuery.trim().toLowerCase();

    if (!q) return packs;

    return packs.filter((p) =>

      p.name.toLowerCase().includes(q) ||

      p.version.toLowerCase().includes(q) ||

      p.pack_id.toLowerCase().includes(q)

    );

  }, [packs, packFilterQuery]);



  const groupedPacks = useMemo(() => {

    const map = new Map<string, { pack_id: string; name: string; versions: DemoPack[] }>();

    for (const p of filteredPacks) {

      let g = map.get(p.pack_id);

      if (!g) {

        const baseName = p.name.replace(/ (Baseline|Extended|v[0-9.]+|Pack.*)$/i, "").trim() || p.name;

        g = { pack_id: p.pack_id, name: baseName, versions: [] };

        map.set(p.pack_id, g);

      }

      g.versions.push(p);

    }



    if (selectedPackVersionId && !filteredPacks.some((p) => p.pack_version_id === selectedPackVersionId)) {

      const selectedP = packs.find((p) => p.pack_version_id === selectedPackVersionId);

      if (selectedP) {

        let g = map.get(selectedP.pack_id);

        if (!g) {

          const baseName = selectedP.name.replace(/ (Baseline|Extended|v[0-9.]+|Pack.*)$/i, "").trim() || selectedP.name;

          g = { pack_id: selectedP.pack_id, name: `${baseName} (Current Selection - Filtered)`, versions: [] };

          map.set(selectedP.pack_id, g);

        }

        g.versions.push({

          ...selectedP,

          name: `${selectedP.name} [selected - filtered]`,

        });

      }

    }



    return Array.from(map.values());

  }, [filteredPacks, selectedPackVersionId, packs]);



  const isCrossPackReplacement = useMemo(() => {

    if (!workspace?.selected_pack || !selectedPackVersionId) return false;

    const adoptedPack = packs.find((p) => p.pack_version_id === workspace.selected_pack?.pack_version_id);

    const candidatePack = packs.find((p) => p.pack_version_id === selectedPackVersionId);

    if (!adoptedPack || !candidatePack) return false;

    return adoptedPack.pack_id !== candidatePack.pack_id;

  }, [workspace, selectedPackVersionId, packs]);



  const hasMissingInfoInEvaluation = useMemo(() => {

    const evalToUse = usableEvaluation || latestEval;

    if (!evalToUse?.results) return false;

    return evalToUse.results.some((r) => r.result === "NEEDS_INFORMATION");

  }, [usableEvaluation, latestEval]);



  // Map of requirements by requirement_id for control information

  const packRequirementsMap = useMemo(() => {

    const map = new Map<string, DemoPackRequirement>();

    const currentPack = packs.find((p) => p.pack_version_id === (latestEval?.pack_version_id || selectedPackVersionId));

    if (currentPack) {

      for (const req of currentPack.requirements) {

        map.set(req.id, req);

      }

    }

    return map;

  }, [packs, latestEval, selectedPackVersionId]);



  if (loading && !workspace) {

    return (

      <div className="modern-workspace-root" style={{ padding: "4rem 2rem", textAlign: "center" }} data-testid="loading-state">

        <div style={{ fontSize: "1.125rem", color: "var(--mw-text-secondary, #6e6e73)", fontWeight: 500 }}>

          {t("common.loading") || "Loading Customer Onboarding Demo..."}

        </div>

      </div>

    );

  }



  if (error?.isDenied) {

    return (

      <div className="modern-workspace-root" data-testid="access-denied-state">

        <div className="mw-alert mw-alert-error" style={{ padding: "2rem", flexDirection: "column", gap: "0.5rem" }}>

          <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700 }}>

            {t("customerDemo.accessDeniedTitle")}

          </h2>

          <p style={{ margin: 0 }}>{error.message}</p>

        </div>

      </div>

    );

  }



  // If rendered as a dedicated view inside CustomerDemoPortal

  if (activePortalView) {

    return (

      <div className="modern-workspace-root" data-testid={`portal-view-container-${activePortalView}`}>

        {/* Alerts */}

        {error && (

          <div className="mw-alert mw-alert-error" data-testid="error-alert" style={{ marginBottom: "1.25rem" }}>

            <div>

              <strong>{t("customerDemo.errorLabel")}: </strong>

              <span>{error.message}</span>

            </div>

            {error.isConflict && (

              <button

                type="button"

                className="mw-btn mw-btn-secondary"

                onClick={() => void loadData()}

                style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem", minHeight: "auto" }}

              >

                {t("customerDemo.reloadWorkspace")}

              </button>

            )}

          </div>

        )}



        {actionSuccessMsg && (

          <div className="mw-alert mw-alert-success" data-testid="success-alert" style={{ marginBottom: "1.25rem" }}>

            <div>

              <strong>{t("customerDemo.successLabel")}: </strong>

              <span>{actionSuccessMsg}</span>

            </div>

            <button

              type="button"

              onClick={() => setActionSuccessMsg(null)}

              style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", fontWeight: 600 }}

              aria-label={t("customerDemo.dismissMessage")}

            >

              &times;

            </button>

          </div>

        )}



        {/* ── View 1: Overview ── */}

        {activePortalView === "overview" && (

          <div className="portal-overview-grid" data-testid="portal-overview-view">

            <div className="portal-welcome-card">

              <div className="portal-welcome-info">

                <h2 className="portal-welcome-title">{t("portal.welcomeTitle")}</h2>

                <p className="portal-welcome-desc">{t("portal.welcomeSubtitle")}</p>

              </div>

              <div className="portal-welcome-badges" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>

                <span className="portal-badge" data-testid="overview-tenant-badge">

                  {workspace?.tenant_id.slice(0, 8)}...

                </span>

                <span className="portal-badge role" data-testid="overview-role-badge">

                  {userRole || "owner"}

                </span>

                <button

                  type="button"

                  className="portal-btn portal-btn-secondary portal-refresh-btn"

                  onClick={() => void loadOverviewMetrics()}

                  disabled={metricsLoading}

                  data-testid="portal-refresh-metrics-btn"

                  aria-label={t("portal.refreshOverview")}

                >

                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">

                    <polyline points="23 4 23 10 17 10" />

                    <polyline points="1 20 1 14 7 14" />

                    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />

                  </svg>

                  <span>{t("portal.refreshOverview")}</span>

                </button>

              </div>

            </div>



            <div className="portal-metrics-row">

              <div className="portal-metric-card" data-testid="metric-framework-card">

                <div className="portal-metric-header">

                  <span className="portal-metric-title">{t("portal.cardFrameworkStatus")}</span>

                  <span className={`portal-metric-status-tag ${selectedPack ? (selectedPack.is_stale ? "stale" : "active") : "empty"}`}>

                    {selectedPack ? (selectedPack.is_stale ? t("portal.statusStale") : t("portal.statusAdopted")) : t("portal.statusNone")}

                  </span>

                </div>

                <div className="portal-metric-value">

                  {selectedPack ? `Rev ${selectedPack.selection_revision}` : "—"}

                </div>

                <p className="portal-metric-subtext">

                  {selectedPack

                    ? (selectedPack.is_stale ? t("portal.stalePackWarning") : `Pack: ${selectedPack.pack_version_id.slice(0, 12)}...`)

                    : t("portal.noPackAdopted")}

                </p>

              </div>



              <div className="portal-metric-card" data-testid="metric-controls-card">

                <div className="portal-metric-header">

                  <span className="portal-metric-title">{t("portal.cardControlsStatus")}</span>

                  <span className={`portal-metric-status-tag ${metricsControlsError ? "error" : activeControlWorkList && activeControlWorkList.total > 0 ? "active" : ""}`}>

                    {metricsLoading

                      ? "..."

                      : metricsControlsError

                      ? metricsControlsError

                      : selectedPack

                      ? (activeControlWorkList ? (activeControlWorkList.total > 0 ? t("portal.statusInProgress") : t("portal.statusNotInitialized")) : t("portal.statusNotInitialized"))

                      : t("portal.statusNotInitialized")}

                  </span>

                </div>

                <div className="portal-metric-value">

                  {metricsLoading ? "..." : metricsControlsError ? "!" : selectedPack ? (activeControlWorkList ? activeControlWorkList.total : 0) : 0}

                </div>

                <p className="portal-metric-subtext">

                  {metricsControlsError ? (

                    <span>

                      {metricsControlsError}

                      <button type="button" className="portal-retry-link" onClick={() => void loadOverviewMetrics()}>

                        {t("portal.retryLoading")}

                      </button>

                    </span>

                  ) : selectedPack ? (

                    activeControlWorkList ? `${activeControlWorkList.total} ${t("portal.controlsCountLabel")}` : t("portal.noPackAdopted")

                  ) : (

                    t("portal.noPackAdopted")

                  )}

                </p>

              </div>



              {(() => {

                const totalPinnedEvidence = activeControlWorkList

                  ? activeControlWorkList.items.reduce((acc, it) => acc + (it.links ? it.links.length : 0), 0)

                  : null;

                return (

                  <div className="portal-metric-card" data-testid="metric-evidence-card">

                    <div className="portal-metric-header">

                      <span className="portal-metric-title">{t("portal.cardEvidenceStatus")}</span>

                      <span className={`portal-metric-status-tag ${metricsControlsError ? "error" : totalPinnedEvidence !== null && totalPinnedEvidence > 0 ? "active" : ""}`}>

                        {metricsLoading

                          ? "..."

                          : metricsControlsError

                          ? metricsControlsError

                          : selectedPack

                          ? (totalPinnedEvidence !== null ? (totalPinnedEvidence > 0 ? t("portal.statusPinned") : t("portal.statusNone")) : t("portal.statusNone"))

                          : t("portal.statusNone")}

                      </span>

                    </div>

                    <div className="portal-metric-value">

                      {metricsLoading ? "..." : metricsControlsError ? "!" : selectedPack ? (totalPinnedEvidence !== null ? totalPinnedEvidence : "—") : "—"}

                    </div>

                    <p className="portal-metric-subtext">

                      {metricsControlsError ? (

                        <span>

                          {metricsControlsError}

                          <button type="button" className="portal-retry-link" onClick={() => void loadOverviewMetrics()}>

                            {t("portal.retryLoading")}

                          </button>

                        </span>

                      ) : selectedPack ? (

                        totalPinnedEvidence !== null ? t("portal.evidenceLinksLabel", { count: totalPinnedEvidence }) : t("portal.noPackAdopted")

                      ) : (

                        t("portal.noPackAdopted")

                      )}

                    </p>

                  </div>

                );

              })()}



              {(() => {

                const summ = activeAssessmentWorkList?.summary;

                const isAllPass = Boolean(summ && summ.total_controls > 0 && summ.pass_count === summ.total_controls && summ.open_findings === 0);

                const hasFindings = Boolean(summ && summ.open_findings > 0);

                const isUnassessed = Boolean(!summ || summ.total_controls === 0 || summ.unassessed === summ.total_controls);



                return (

                  <div className="portal-metric-card" data-testid="metric-assessments-card">

                    <div className="portal-metric-header">

                      <span className="portal-metric-title">{t("portal.cardAssessmentStatus")}</span>

                      <span className={`portal-metric-status-tag ${metricsAssessmentsError ? "error" : isAllPass ? "active" : selectedPack?.is_stale ? "stale" : ""}`}>

                        {metricsLoading

                          ? "..."

                          : metricsAssessmentsError

                          ? metricsAssessmentsError

                          : selectedPack

                          ? (summ

                              ? (hasFindings ? t("portal.statusFindings") : isAllPass ? t("portal.statusAllPassed") : isUnassessed ? t("portal.statusUnassessed") : t("portal.statusInProgress"))

                              : t("portal.statusUnassessed"))

                          : t("portal.statusUnassessed")}

                      </span>

                    </div>

                    <div className="portal-metric-value">

                      {metricsLoading ? "..." : metricsAssessmentsError ? "!" : selectedPack ? (summ ? `${summ.pass_count} / ${summ.total_controls}` : "—") : "—"}

                    </div>

                    <p className="portal-metric-subtext">

                      {metricsAssessmentsError ? (

                        <span>

                          {metricsAssessmentsError}

                          <button type="button" className="portal-retry-link" onClick={() => void loadOverviewMetrics()}>

                            {t("portal.retryLoading")}

                          </button>

                        </span>

                      ) : selectedPack ? (

                        summ

                          ? t("portal.assessmentProgressDetail", { pass: summ.pass_count, findings: summ.open_findings, unassessed: summ.unassessed })

                          : t("portal.notAssessed")

                      ) : (

                        t("portal.noPackAdopted")

                      )}

                    </p>

                  </div>

                );

              })()}

            </div>



            <div className="portal-next-action-card" data-testid="portal-next-action-banner">

              <div className="portal-next-action-content">

                <div className="portal-next-action-label">{t("portal.nextActionTitle")}</div>

                <p className="portal-next-action-text">

                  {!workspace?.answers

                    ? t("portal.nextActionSetup")

                    : !selectedPack

                    ? t("portal.nextActionAdopt")

                    : t("portal.nextActionControls")}

                </p>

              </div>

              <button

                type="button"

                className="portal-btn portal-btn-primary"

                onClick={() => {

                  if (!workspace?.answers) onNavigateView?.("company_setup");

                  else if (!selectedPack) onNavigateView?.("frameworks");

                  else onNavigateView?.("controls_evidence");

                }}

                data-testid="next-action-btn"

              >

                {!workspace?.answers

                  ? t("portal.actionConfigureSetup")

                  : !selectedPack

                  ? t("portal.actionExploreFrameworks")

                  : t("portal.actionManageControls")}

              </button>

            </div>



            <div className="portal-actions-grid">

              <button

                type="button"

                className="portal-action-card"

                onClick={() => onNavigateView?.("work_queue")}

                data-testid="card-go-work-queue"

              >

                <div className="portal-action-card-header">

                  <div className="portal-action-icon-wrap">

                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>

                  </div>

                  <div>

                    <h3 className="portal-action-card-title">{t("portal.navWorkQueue")}</h3>

                    <p className="portal-action-card-desc">{t("portal.workQueueSubtitle")}</p>

                  </div>

                </div>

                <span className="portal-btn portal-btn-secondary" style={{ alignSelf: "flex-start" }}>

                  {t("portal.navWorkQueue")} &rarr;

                </span>

              </button>



              <button

                type="button"

                className="portal-action-card"

                onClick={() => onNavigateView?.("company_setup")}

                data-testid="card-go-company-setup"

              >

                <div className="portal-action-card-header">

                  <div className="portal-action-icon-wrap">

                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5"/></svg>

                  </div>

                  <div>

                    <h3 className="portal-action-card-title">{t("portal.navCompanySetup")}</h3>

                    <p className="portal-action-card-desc">{t("portal.setupSubtitle")}</p>

                  </div>

                </div>

                <span className="portal-btn portal-btn-secondary" style={{ alignSelf: "flex-start" }}>

                  {t("portal.actionConfigureSetup")} &rarr;

                </span>

              </button>



              <button

                type="button"

                className="portal-action-card"

                onClick={() => onNavigateView?.("frameworks")}

                data-testid="card-go-frameworks"

              >

                <div className="portal-action-card-header">

                  <div className="portal-action-icon-wrap">

                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>

                  </div>

                  <div>

                    <h3 className="portal-action-card-title">{t("portal.navFrameworks")}</h3>

                    <p className="portal-action-card-desc">{t("portal.frameworksSubtitle")}</p>

                  </div>

                </div>

                <span className="portal-btn portal-btn-secondary" style={{ alignSelf: "flex-start" }}>

                  {t("portal.actionExploreFrameworks")} &rarr;

                </span>

              </button>



              <button

                type="button"

                className="portal-action-card"

                onClick={() => onNavigateView?.("controls_evidence")}

                data-testid="card-go-controls"

              >

                <div className="portal-action-card-header">

                  <div className="portal-action-icon-wrap">

                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/></svg>

                  </div>

                  <div>

                    <h3 className="portal-action-card-title">{t("portal.navControlsEvidence")}</h3>

                    <p className="portal-action-card-desc">{t("portal.controlsSubtitle")}</p>

                  </div>

                </div>

                <span className="portal-btn portal-btn-secondary" style={{ alignSelf: "flex-start" }}>

                  {t("portal.actionManageControls")} &rarr;

                </span>

              </button>



              <button

                type="button"

                className="portal-action-card"

                onClick={() => onNavigateView?.("assessments_findings")}

                data-testid="card-go-assessments"

              >

                <div className="portal-action-card-header">

                  <div className="portal-action-icon-wrap">

                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/></svg>

                  </div>

                  <div>

                    <h3 className="portal-action-card-title">{t("portal.navAssessmentsFindings")}</h3>

                    <p className="portal-action-card-desc">{t("portal.assessmentsSubtitle")}</p>

                  </div>

                </div>

                <span className="portal-btn portal-btn-secondary" style={{ alignSelf: "flex-start" }}>

                  {t("portal.actionRunAssessments")} &rarr;

                </span>

              </button>

            </div>



            <div className="portal-truthful-disclaimer">

              {t("portal.truthfulNotice")}

            </div>

          </div>

        )}



        {/* ── View 2: Company Setup ── */}

        {activePortalView === "company_setup" && (

          <div className="portal-setup-view" data-testid="portal-setup-view">

            {hasUnsavedChanges && (

              <div className="portal-form-banner warning" data-testid="unsaved-changes-banner" style={{ marginBottom: "1rem" }}>

                <span>&bull;</span>

                <strong>{t("portal.unsavedChangesBadge")}:</strong>

                <span>{t("portal.unsavedChangesGuidance")}</span>

              </div>

            )}

            <section

              ref={profileSectionRef}

              tabIndex={-1}

              className="mw-card active-step-panel"

              aria-labelledby="card-profile-title"

              data-testid="profile-section"

            >

              <div className="mw-card-header">

                <h2 id="card-profile-title" className="mw-card-title">

                  {t("customerDemo.companyProfileTitle")}

                </h2>

                <p className="mw-card-subtitle">

                  {t("customerDemo.companyProfileSubtitle")}

                </p>

              </div>



              <div style={{ marginBottom: "1.25rem" }}>

                <label className="mw-question-label">

                  {t("customerDemo.fictionalPreset")}

                </label>

                <div className="mw-presets-grid">

                  <button

                    type="button"

                    className={`mw-preset-btn ${companyCode === "ALPHA" ? "active btn-primary" : "btn-secondary"}`}

                    onClick={() => handleCompanyChange("ALPHA")}

                    data-testid="company-alpha-btn"

                  >

                    <span className="mw-preset-name">{t("customerDemo.alphaName")}</span>

                    <span className="mw-preset-desc">{t("customerDemo.alphaDesc")}</span>

                  </button>

                  <button

                    type="button"

                    className={`mw-preset-btn ${companyCode === "BETA" ? "active btn-primary" : "btn-secondary"}`}

                    onClick={() => handleCompanyChange("BETA")}

                    data-testid="company-beta-btn"

                  >

                    <span className="mw-preset-name">{t("customerDemo.betaName")}</span>

                    <span className="mw-preset-desc">{t("customerDemo.betaDesc")}</span>

                  </button>

                </div>

              </div>



              <div style={{ marginBottom: "1rem" }}>

                <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.25rem" }}>

                  {t("customerDemo.questionnaireTitle")}

                </h3>

                <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-secondary)", margin: 0 }}>

                  {t("customerDemo.questionnaireSubtitle")}

                </p>

              </div>



              <div className="mw-question-group">

                <label className="mw-question-label">

                  {t("customerDemo.cloudQuestion")}

                </label>

                <div className="mw-radio-options">

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="cloudUsage"

                      value="yes"

                      checked={cloudUsage === "yes"}

                      onChange={() => setCloudUsage("yes")}

                      data-testid="cloud-yes"

                    />

                    <span>{t("customerDemo.cloudYes")}</span>

                  </label>

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="cloudUsage"

                      value="no"

                      checked={cloudUsage === "no"}

                      onChange={() => setCloudUsage("no")}

                      data-testid="cloud-no"

                    />

                    <span>{t("customerDemo.cloudNo")}</span>

                  </label>

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="cloudUsage"

                      value="unknown"

                      checked={cloudUsage === "unknown"}

                      onChange={() => setCloudUsage("unknown")}

                      data-testid="cloud-unknown"

                    />

                    <span>{t("customerDemo.cloudUnknown")}</span>

                  </label>

                </div>

                {(validationErrors.cloudUsage || (showValidationErrors && cloudUsage === "unknown")) && (

                  <div

                    className="portal-error-message"

                    role="alert"

                    data-testid="cloud-usage-error"

                    style={{ color: "var(--mw-error-text, #ff3b30)", fontSize: "0.8125rem", marginTop: "0.375rem", display: "flex", alignItems: "center", gap: "4px" }}

                  >

                    <span>&bull;</span> {t("portal.cloudUsageRequired")}

                  </div>

                )}

              </div>



              <div className="mw-question-group">

                <label className="mw-question-label">

                  {t("customerDemo.regionQuestion")}

                </label>

                <div className="mw-radio-options">

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="operatingRegion"

                      value="EU"

                      checked={operatingRegion === "EU"}

                      onChange={() => setOperatingRegion("EU")}

                      data-testid="region-eu"

                    />

                    <span>{t("customerDemo.regionEu")}</span>

                  </label>

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="operatingRegion"

                      value="OTHER"

                      checked={operatingRegion === "OTHER"}

                      onChange={() => setOperatingRegion("OTHER")}

                      data-testid="region-other"

                    />

                    <span>{t("customerDemo.regionOther")}</span>

                  </label>

                  <label className="mw-radio-label">

                    <input

                      type="radio"

                      name="operatingRegion"

                      value="unknown"

                      checked={operatingRegion === "unknown"}

                      onChange={() => setOperatingRegion("unknown")}

                      data-testid="region-unknown"

                    />

                    <span>{t("customerDemo.regionUnknown")}</span>

                  </label>

                </div>

                {(validationErrors.operatingRegion || (showValidationErrors && operatingRegion === "unknown")) && (

                  <div

                    className="portal-error-message"

                    role="alert"

                    data-testid="operating-region-error"

                    style={{ color: "var(--mw-error-text, #ff3b30)", fontSize: "0.8125rem", marginTop: "0.375rem", display: "flex", alignItems: "center", gap: "4px" }}

                  >

                    <span>&bull;</span> {t("portal.operatingRegionRequired")}

                  </div>

                )}

              </div>



              <div className="mw-card-actions" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>

                <button

                  type="button"

                  className="mw-btn mw-btn-primary btn-primary"

                  onClick={handleSave}

                  disabled={saving}

                  data-testid="save-answers-btn"

                >

                  {saving ? t("customerDemo.saving") : t("customerDemo.saveAnswersBtn")}

                </button>

                <button

                  type="button"

                  className="mw-btn mw-btn-secondary btn-secondary"

                  onClick={handleValidateInputs}

                  data-testid="validate-setup-btn"

                >

                  {t("portal.validateBtn")}

                </button>

              </div>

            </section>

          </div>

        )}



        {/* ── View 3: Available Frameworks / Packs ── */}

        {activePortalView === "frameworks" && (

          <div className="portal-frameworks-view" data-testid="portal-frameworks-view">

            {hasUnsavedChanges && (

              <div className="portal-form-banner warning" data-testid="unsaved-changes-banner" style={{ marginBottom: "1rem" }}>

                <span>&bull;</span>

                <strong>{t("portal.unsavedChangesBadge")}:</strong>

                <span>{t("portal.evaluatingUsesSavedAnswers")}</span>

              </div>

            )}

            <section

              ref={evalSectionRef}

              tabIndex={-1}

              className="mw-card active-step-panel"

              aria-labelledby="card-eval-title"

              data-testid="eval-section"

            >

              <div className="mw-card-header">

                <h2 id="card-eval-title" className="mw-card-title">

                  {t("customerDemo.ruleEvalTitle")}

                </h2>

                <p className="mw-card-subtitle">

                  {t("customerDemo.ruleEvalSubtitle")}

                </p>

              </div>



              <div style={{ marginBottom: "1.25rem" }}>

                <label htmlFor="pack-select" className="mw-question-label">

                  {t("customerDemo.selectPack")}

                </label>

                <div style={{ marginBottom: "0.5rem" }}>

                  <input

                    type="text"

                    className="mw-input"

                    placeholder={t("portal.filterFrameworksPlaceholder")}

                    value={packFilterQuery}

                    onChange={(e) => setPackFilterQuery(e.target.value)}

                    data-testid="pack-filter-input"

                    style={{ width: "100%", maxWidth: "360px", fontSize: "0.85rem" }}

                  />

                </div>

                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>

                  <select

                    id="pack-select"

                    className="mw-select"

                    value={selectedPackVersionId}

                    onChange={(e) => handlePackChange(e.target.value)}

                    disabled={saving || evaluating || adopting}

                    data-testid="pack-select"

                    style={{ flex: 1, minWidth: "240px" }}

                  >

                    {groupedPacks.map((g) => (

                      <optgroup key={g.pack_id} label={g.name}>

                        {g.versions.map((p) => (

                          <option key={p.pack_version_id} value={p.pack_version_id}>

                            {p.name} (v{p.version}) &mdash; {p.requirement_count} requirements {workspace?.selected_pack?.pack_version_id === p.pack_version_id ? `[${t("portal.adoptedBadge")}]` : `[${t("portal.candidateBadge")}]`}

                          </option>

                        ))}

                      </optgroup>

                    ))}

                  </select>

                  <button

                    type="button"

                    className="mw-btn mw-btn-secondary btn-secondary"

                    onClick={() => setShowComparison((prev) => !prev)}

                    data-testid="compare-packs-btn"

                  >

                    {showComparison ? t("customerDemo.hideComparison") : t("customerDemo.comparePacks")}

                  </button>

                </div>

              </div>



              {showComparison && workspace && (

                <div style={{ marginTop: "1rem" }}>

                  <FrameworkVersionInspector

                    workspace={workspace}

                    selectedCandidateVersionId={selectedPackVersionId}

                    onSelectCandidateVersion={handlePackChange}

                    userRole={userRole}

                  />

                </div>

              )}



              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>

                <button

                  type="button"

                  className="mw-btn mw-btn-primary btn-primary"

                  onClick={handleEvaluate}

                  disabled={evaluating || (workspace?.current_revision ?? 0) === 0}

                  data-testid="evaluate-btn"

                >

                  {evaluating ? t("customerDemo.evaluating") : t("customerDemo.evaluateBtn")}

                </button>

                {(workspace?.current_revision ?? 0) === 0 && (

                  <span style={{ fontSize: "0.75rem", color: "var(--mw-text-secondary)" }}>

                    {t("customerDemo.saveFirstNotice")}

                  </span>

                )}

              </div>



              {latestEval ? (

                <div>

                  <div className="mw-outcomes-summary" data-testid="outcomes-summary-bar">

                    <div className="mw-outcomes-metrics">

                      <span className="mw-outcome-metric applicable">

                        &bull; {t("customerDemo.summaryApplicable")}: {outcomeCounts.applicable}

                      </span>

                      <span className="mw-outcome-metric not-applicable">

                        &bull; {t("customerDemo.summaryNotApplicable")}: {outcomeCounts.notApplicable}

                      </span>

                      <span className="mw-outcome-metric needs-info">

                        &bull; {t("customerDemo.summaryNeedsInfo")}: {outcomeCounts.needsInfo}

                      </span>

                    </div>



                    <button

                      type="button"

                      ref={openerRef}

                      className="mw-btn mw-btn-primary btn-primary"

                      onClick={handleOpenAdoptModal}

                      disabled={!usableEvaluation || saving || evaluating || adopting}

                      data-testid="open-adopt-modal-btn"

                    >

                      {t("customerDemo.adoptPackBtn")}

                    </button>

                  </div>



                  <div className="mw-truthful-disclaimer">

                    {t("customerDemo.summaryTruthfulNotice")}

                  </div>



                  {latestEval && latestEval.pack_version_id !== selectedPackVersionId && (

                    <div

                      role="status"

                      className="mw-notice-banner"

                      data-testid="evaluation-mismatch-notice"

                      style={{ background: "#fff5f5", borderColor: "#dc3545", color: "#721c24", margin: "1rem 0" }}

                    >

                      <strong>Evaluation Mismatch: </strong>

                      The displayed evaluation belongs to another framework pack. Please evaluate the selected candidate to review applicability and adopt.

                    </div>

                  )}



                  <div style={{ marginTop: "1rem" }}>

                    <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, margin: "0 0 0.75rem" }}>

                      {t("customerDemo.evaluationResults")} ({t("customerDemo.answersRevision")} {latestEval.answer_revision})

                    </h3>



                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>

                      {latestEval.results.map((res) => (

                        <RequirementResultCard

                          key={res.requirement_id}

                          result={res}

                          controlDetail={packRequirementsMap.get(res.requirement_id)}

                        />

                      ))}

                    </div>

                  </div>

                </div>

              ) : (

                <div style={{ textAlign: "center", padding: "2rem", color: "var(--mw-text-secondary)", background: "var(--mw-surface-secondary)", borderRadius: "var(--mw-radius-md)", border: "1px dashed var(--mw-border)" }}>

                  <p style={{ margin: 0, fontSize: "0.875rem" }}>

                    {t("customerDemo.noEvaluationYet")}

                  </p>

                </div>

              )}

            </section>



            {/* Adoption History */}

            <section

              ref={historySectionRef}

              tabIndex={-1}

              className="mw-history-card active-step-panel"

              aria-labelledby="history-title"

              data-testid="adoption-history-section"

              style={{ marginTop: "1.5rem" }}

            >

              <h2 id="history-title" style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.25rem" }}>

                {t("customerDemo.historyTitle")}

              </h2>

              <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-secondary)", margin: 0 }}>

                {t("customerDemo.historySubtitle")}

              </p>



              {workspace?.history_summary && workspace.history_summary.length > 0 ? (

                <div className="mw-history-table-wrapper">

                  <table className="mw-history-table">

                    <thead>

                      <tr>

                        <th>{t("customerDemo.selectionRevision")}</th>

                        <th>{t("customerDemo.packVersionId")}</th>

                        <th>{t("customerDemo.bundleDigest")}</th>

                        <th>{t("customerDemo.adoptedTimestamp")}</th>

                      </tr>

                    </thead>

                    <tbody>

                      {workspace.history_summary.map((h) => (

                        <tr key={`${h.selection_revision}-${h.bundle_digest}`}>

                          <td><strong>rev {h.selection_revision}</strong></td>

                          <td><code>{h.pack_version_id}</code></td>

                          <td className="mw-digest-code"><code>{h.bundle_digest}</code></td>

                          <td>{new Date(h.created_at).toLocaleString()}</td>

                        </tr>

                      ))}

                    </tbody>

                  </table>

                </div>

              ) : (

                <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-tertiary)", marginTop: "0.75rem" }}>

                  {t("customerDemo.historyEmpty")}

                </p>

              )}

            </section>



            {workspace && (

              <div style={{ marginTop: "1.5rem" }}>

                <FrameworkVersionInspector

                  workspace={workspace}

                  selectedCandidateVersionId={selectedPackVersionId}

                  onSelectCandidateVersion={handlePackChange}

                  userRole={userRole}

                />

              </div>

            )}

          </div>

        )}



        {/* ── View 4: Controls & Evidence (Kept mounted to preserve in-flight user drafts) ── */}

        {workspace?.selected_pack ? (

          <div

            className="portal-controls-view"

            data-testid="portal-controls-view"

            style={{ display: activePortalView === "controls_evidence" ? "block" : "none" }}

          >

            <ControlEvidenceWorkspace

              tenantId={tenantId}

              token={token}

              selectionRevision={workspace.selected_pack.selection_revision}

              answerRevision={workspace.current_revision}

              hasUnsavedParentEdits={hasUnsavedChanges}

              isAdoptionStale={workspace.selected_pack.is_stale}

              userRole={userRole}

              onSessionExpired={onSessionExpired}

              onDataChange={handleChildDataChange}

              navTarget={evidenceNavTarget}

            />

          </div>

        ) : activePortalView === "controls_evidence" ? (

          <div className="portal-controls-view" data-testid="portal-controls-view">

            <div style={{ textAlign: "center", padding: "3rem 2rem", background: "var(--mw-surface, #fff)", borderRadius: "var(--mw-radius-lg, 16px)", border: "1px dashed var(--mw-border, #d2d2d7)" }} data-testid="controls-unadopted-empty">

              <h3 style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.5rem" }}>

                {t("portal.noPackAdopted")}

              </h3>

              <p style={{ color: "var(--mw-text-secondary, #6e6e73)", fontSize: "0.875rem", margin: "0 0 1.25rem" }}>

                {t("portal.nextActionAdopt")}

              </p>

              <button

                type="button"

                className="mw-btn mw-btn-primary btn-primary"

                onClick={() => onNavigateView?.("frameworks")}

                data-testid="empty-go-frameworks-btn"

              >

                {t("portal.actionExploreFrameworks")} &rarr;

              </button>

            </div>

          </div>

        ) : null}



        {/* ── View 5: Assessments & Findings (Kept mounted to preserve in-flight user drafts) ── */}

        {workspace?.selected_pack ? (

          <div

            className="portal-assessments-view"

            data-testid="portal-assessments-view"

            style={{ display: activePortalView === "assessments_findings" ? "block" : "none" }}

          >

            <AssessmentWorkspace

              tenantId={tenantId}

              token={token}

              actorId={userId}

              adoptionId={controlWorkList?.adoption_id || "current"}

              selectionRevision={workspace.selected_pack.selection_revision}

              answerRevision={workspace.current_revision}

              hasUnsavedParentEdits={hasUnsavedChanges}

              isAdoptionStale={workspace.selected_pack.is_stale}

              userRole={userRole}

              onSessionExpired={onSessionExpired}

              onDataChange={handleChildDataChange}

              refreshEpoch={metricsEpoch}

              isActiveView={activePortalView === "assessments_findings"}

              navTarget={assessmentNavTarget}

            />

          </div>

        ) : activePortalView === "assessments_findings" ? (

          <div className="portal-assessments-view" data-testid="portal-assessments-view">

            <div style={{ textAlign: "center", padding: "3rem 2rem", background: "var(--mw-surface, #fff)", borderRadius: "var(--mw-radius-lg, 16px)", border: "1px dashed var(--mw-border, #d2d2d7)" }} data-testid="assessments-unadopted-empty">

              <h3 style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.5rem" }}>

                {t("portal.noPackAdopted")}

              </h3>

              <p style={{ color: "var(--mw-text-secondary, #6e6e73)", fontSize: "0.875rem", margin: "0 0 1.25rem" }}>

                {t("portal.nextActionAdopt")}

              </p>

              <button

                type="button"

                className="mw-btn mw-btn-primary btn-primary"

                onClick={() => onNavigateView?.("frameworks")}

                data-testid="empty-assessments-go-frameworks-btn"

              >

                {t("portal.actionExploreFrameworks")} &rarr;

              </button>

            </div>

          </div>

        ) : null}



        {/* ── View 6: Organization & Structure (Kept mounted to preserve in-flight form entries) ── */}

        <div

          className="portal-organization-view"

          data-testid="portal-organization-view"

          style={{ display: activePortalView === "organization" ? "block" : "none" }}

        >

          <OrganizationWorkspaceV2

            tenantId={tenantId}

            token={token}

            userRole={userRole}

            onSessionExpired={onSessionExpired}

          />

        </div>



        {/* ── View 8: Operations Registers (Policies, Risks, Assets, Vendors) ── */}

        <div

          className="portal-operations-view"

          data-testid="portal-operations-view"

          style={{ display: activePortalView === "operations" ? "block" : "none" }}

        >

          <OperationsWorkspace

            tenantId={tenantId}

            token={token}

            userRole={userRole}

            currentUserId={userId || ""}

            onSessionExpired={onSessionExpired}

          />

        </div>



        {/* ── View 7: Daily Work Queue (Kept mounted to preserve in-flight filter/search entries) ── */}

        <div

          className="portal-work-queue-view"

          data-testid="portal-work-queue-view"

          style={{ display: activePortalView === "work_queue" ? "block" : "none" }}

        >

          <WorkQueue

            tenantId={tenantId}

            token={token}

            adoptionId={workspace?.selected_pack ? (controlWorkList?.adoption_id || "current") : null}

            selectionRevision={workspace?.selected_pack?.selection_revision}

            answerRevision={workspace?.current_revision}

            refreshEpoch={metricsEpoch}

            isActiveView={activePortalView === "work_queue"}

            onNavigateToControl={handleNavigateToControl}

            onNavigateToEvidence={handleNavigateToEvidence}

            onNavigateToAssessment={handleNavigateToAssessment}

            onNavigateToFrameworks={() => {

              onNavigateView?.("frameworks");

            }}

            onSessionExpired={onSessionExpired}

          />

        </div>

        {/* ── View 8: Pre-audit Portal Workspace (MVP-D) ── */}

        {isPreauditEnabled() && (
          <div
            className="portal-preaudit-view"
            data-testid="portal-preaudit-view"
            style={{ display: activePortalView === "preaudit" ? "block" : "none" }}
          >
            <PreAuditWorkspace
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              currentUserId={userId || ""}
              adoptionId={workspace?.selected_pack ? (controlWorkList?.adoption_id || "current") : ""}
              activeView={activePortalView}
              onSessionExpired={onSessionExpired}
              onNavigateToWork={(workId, targetTab) => {
                if (targetTab === "control") {
                  handleNavigateToControl(workId);
                } else if (targetTab === "evidence") {
                  handleNavigateToEvidence(workId);
                } else if (targetTab === "assessment") {
                  handleNavigateToAssessment(workId);
                }
              }}
            />
          </div>
        )}



        {/* Adoption Modal in Portal Views */}

        {adoptModalOpen && (usableEvaluation || latestEval) && (

          <div

            className="mw-modal-overlay"

            role="dialog"

            aria-modal="true"

            aria-labelledby="adopt-modal-title"

            data-testid="adopt-pack-modal"

            onKeyDown={handleModalKeyDown}

          >

            <div ref={dialogRef} tabIndex={-1} className="mw-modal-dialog">

              <h3 id="adopt-modal-title" className="mw-modal-title">

                {t("customerDemo.adoptTitle")}

              </h3>

              <p className="mw-modal-subtitle">

                {t("customerDemo.adoptSubtitle")}

              </p>



              <div

                style={{

                  background: "var(--mw-surface-secondary)",

                  padding: "0.875rem 1rem",

                  borderRadius: "var(--mw-radius-md)",

                  marginBottom: "1.25rem",

                  fontSize: "0.8125rem",

                  border: "1px solid var(--mw-border-subtle)",

                }}

              >

                <strong>{t("customerDemo.exactVersions")}</strong>

                <div style={{ fontSize: "0.8rem", color: "var(--mw-text-secondary)", marginTop: "0.25rem" }}>

                  Candidate Pack Version ID: <code>{frozenAdoptionIntent?.candidatePackVersionId || selectedPackVersionId}</code>

                </div>

                <div style={{ fontSize: "0.8rem", color: "var(--mw-text-secondary)", marginBottom: "0.5rem" }}>

                  Bundle Digest: <code>{(frozenAdoptionIntent?.bundleDigest || (usableEvaluation || latestEval)?.bundle_digest)?.slice(0, 16)}...</code>

                </div>

                <ul style={{ paddingLeft: "1rem", margin: "0.5rem 0 0" }}>

                  {(usableEvaluation || latestEval)?.results.map((r) => (

                    <li key={r.requirement_id} style={{ marginBottom: "0.25rem" }}>

                      <code>{r.identifier}</code> ({r.title}) - Version: <code>{r.requirement_version_id}</code> -{" "}

                      <strong>{r.result}</strong>

                    </li>

                  ))}

                </ul>

              </div>



              {isCrossPackReplacement && (

                <div

                  role="status"

                  className="mw-notice-banner"

                  data-testid="cross-pack-replacement-warning"

                  style={{ background: "#e8f4f8", borderColor: "#17a2b8", color: "#0c5460", marginBottom: "1rem" }}

                >

                  <strong>Cross-Pack Replacement: </strong>

                  {t("portal.crossPackReplacementDisclaimer")}

                </div>

              )}



              {!isModalIntentValid && (
                <div
                  role="alert"
                  className="mw-notice-banner"
                  data-testid="adoption-intent-invalidated-notice"
                  style={{ background: "#fff3cd", borderColor: "#ffeeba", color: "#856404", marginBottom: "1rem" }}
                >
                  {t("customerDemo.adoptionIntentInvalidated")}
                </div>
              )}

              <div style={{ marginBottom: "0.75rem" }}>

                <label className="mw-checkbox-label">

                  <input

                    type="checkbox"

                    checked={ackSynthetic}

                    onChange={(e) => setAckSynthetic(e.target.checked)}

                    data-testid="ack-synthetic-checkbox"

                  />

                  <span>{t("customerDemo.ackSyntheticLabel")}</span>

                </label>

              </div>



              {hasMissingInfoInEvaluation && (

                <div style={{ marginBottom: "1rem" }}>

                  <label className="mw-checkbox-label" style={{ color: "var(--mw-warning-text)" }}>

                    <input

                      type="checkbox"

                      checked={ackMissing}

                      onChange={(e) => setAckMissing(e.target.checked)}

                      data-testid="ack-missing-checkbox"

                    />

                    <span>{t("customerDemo.ackMissingLabel")}</span>

                  </label>

                </div>

              )}



              <div className="mw-modal-actions">

                <button

                  type="button"

                  className="mw-btn mw-btn-secondary btn-secondary"

                  onClick={() => setAdoptModalOpen(false)}

                  disabled={adopting}

                >

                  {t("common.cancel") || "Cancel"}

                </button>

                <button

                  type="button"

                  className="mw-btn mw-btn-primary btn-primary"

                  onClick={handleAdopt}

                  disabled={adopting || !isModalIntentValid || !ackSynthetic || (hasMissingInfoInEvaluation && !ackMissing)}

                  data-testid="confirm-adopt-btn"

                >

                  {adopting ? t("customerDemo.adopting") : t("customerDemo.confirmAdopt")}

                </button>

              </div>

            </div>

          </div>

        )}

      </div>

    );

  }



  return (

    <ModernWorkspaceShell

      title={t("customerDemo.title")}

      subtitle={t("customerDemo.subtitle")}

      disclaimer={manifest?.disclaimer}

      currentRevision={workspace?.current_revision ?? 0}

      selectionRevision={workspace?.selection_revision ?? 0}

      hasUnsavedChanges={hasUnsavedChanges}

      selectedPackSummary={selectedPack}

      isEvaluationCurrent={Boolean(latestEval && latestEval.answer_revision === (workspace?.current_revision ?? 0) && !hasUnsavedChanges)}

      isEvaluationStale={Boolean(latestEval && latestEval.answer_revision < (workspace?.current_revision ?? 0))}

      activeStep={activeStep}

      onStepChange={handleStepChange}

    >

      {/* Alert Notices */}

      {error && (

        <div className="mw-alert mw-alert-error" data-testid="error-alert">

          <div>

            <strong>{t("customerDemo.errorLabel")}: </strong>

            <span>{error.message}</span>

          </div>

          {error.isConflict && (

            <button

              type="button"

              className="mw-btn mw-btn-secondary"

              onClick={() => void loadData()}

              style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem", minHeight: "auto" }}

            >

              {t("customerDemo.reloadWorkspace")}

            </button>

          )}

        </div>

      )}



      {actionSuccessMsg && (

        <div className="mw-alert mw-alert-success" data-testid="success-alert">

          <div>

            <strong>{t("customerDemo.successLabel")}: </strong>

            <span>{actionSuccessMsg}</span>

          </div>

          <button

            type="button"

            onClick={() => setActionSuccessMsg(null)}

            style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", fontWeight: 600 }}

            aria-label={t("customerDemo.dismissMessage")}

          >

            &times;

          </button>

        </div>

      )}



      {/* Main Grid: Form Left, Evaluation/Adoption Right */}

      <div className="mw-grid">

        {/* Left Column: Organization Profile & Facts */}

        <section

          ref={profileSectionRef}

          tabIndex={-1}

          className={`mw-card ${activeStep === 1 ? "active-step-panel" : ""}`}

          aria-labelledby="card-profile-title"

          data-testid="profile-section"

        >

          <div className="mw-card-header">

            <h2 id="card-profile-title" className="mw-card-title">

              {t("customerDemo.companyProfileTitle")}

            </h2>

            <p className="mw-card-subtitle">

              {t("customerDemo.companyProfileSubtitle")}

            </p>

          </div>



          {/* Company Preset Selection */}

          <div style={{ marginBottom: "1.25rem" }}>

            <label className="mw-question-label">

              {t("customerDemo.fictionalPreset")}

            </label>

            <div className="mw-presets-grid">

              <button

                type="button"

                className={`mw-preset-btn ${companyCode === "ALPHA" ? "active btn-primary" : "btn-secondary"}`}

                onClick={() => handleCompanyChange("ALPHA")}

                data-testid="company-alpha-btn"

              >

                <span className="mw-preset-name">{t("customerDemo.alphaName")}</span>

                <span className="mw-preset-desc">{t("customerDemo.alphaDesc")}</span>

              </button>

              <button

                type="button"

                className={`mw-preset-btn ${companyCode === "BETA" ? "active btn-primary" : "btn-secondary"}`}

                onClick={() => handleCompanyChange("BETA")}

                data-testid="company-beta-btn"

              >

                <span className="mw-preset-name">{t("customerDemo.betaName")}</span>

                <span className="mw-preset-desc">{t("customerDemo.betaDesc")}</span>

              </button>

            </div>

          </div>



          {/* Questionnaire Header */}

          <div style={{ marginBottom: "1rem" }}>

            <h3 style={{ fontSize: "1rem", fontWeight: 600, margin: "0 0 0.25rem" }}>

              {t("customerDemo.questionnaireTitle")}

            </h3>

            <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-secondary)", margin: 0 }}>

              {t("customerDemo.questionnaireSubtitle")}

            </p>

          </div>



          {/* Question 1: Uses Cloud */}

          <div className="mw-question-group">

            <label className="mw-question-label">

              {t("customerDemo.cloudQuestion")}

            </label>

            <div className="mw-radio-options">

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="cloudUsage"

                  value="yes"

                  checked={cloudUsage === "yes"}

                  onChange={() => setCloudUsage("yes")}

                  data-testid="cloud-yes"

                />

                <span>{t("customerDemo.cloudYes")}</span>

              </label>

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="cloudUsage"

                  value="no"

                  checked={cloudUsage === "no"}

                  onChange={() => setCloudUsage("no")}

                  data-testid="cloud-no"

                />

                <span>{t("customerDemo.cloudNo")}</span>

              </label>

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="cloudUsage"

                  value="unknown"

                  checked={cloudUsage === "unknown"}

                  onChange={() => setCloudUsage("unknown")}

                  data-testid="cloud-unknown"

                />

                <span>{t("customerDemo.cloudUnknown")}</span>

              </label>

            </div>

            {(validationErrors.cloudUsage || (showValidationErrors && cloudUsage === "unknown")) && (

              <div

                className="portal-error-message"

                role="alert"

                data-testid="cloud-usage-error"

                style={{ color: "var(--mw-error-text, #ff3b30)", fontSize: "0.8125rem", marginTop: "0.375rem", display: "flex", alignItems: "center", gap: "4px" }}

              >

                <span>&bull;</span> {t("portal.cloudUsageRequired")}

              </div>

            )}

          </div>



          {/* Question 2: Operating Region */}

          <div className="mw-question-group">

            <label className="mw-question-label">

              {t("customerDemo.regionQuestion")}

            </label>

            <div className="mw-radio-options">

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="operatingRegion"

                  value="EU"

                  checked={operatingRegion === "EU"}

                  onChange={() => setOperatingRegion("EU")}

                  data-testid="region-eu"

                />

                <span>{t("customerDemo.regionEu")}</span>

              </label>

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="operatingRegion"

                  value="OTHER"

                  checked={operatingRegion === "OTHER"}

                  onChange={() => setOperatingRegion("OTHER")}

                  data-testid="region-other"

                />

                <span>{t("customerDemo.regionOther")}</span>

              </label>

              <label className="mw-radio-label">

                <input

                  type="radio"

                  name="operatingRegion"

                  value="unknown"

                  checked={operatingRegion === "unknown"}

                  onChange={() => setOperatingRegion("unknown")}

                  data-testid="region-unknown"

                />

                <span>{t("customerDemo.regionUnknown")}</span>

              </label>

            </div>

            {(validationErrors.operatingRegion || (showValidationErrors && operatingRegion === "unknown")) && (

              <div

                className="portal-error-message"

                role="alert"

                data-testid="operating-region-error"

                style={{ color: "var(--mw-error-text, #ff3b30)", fontSize: "0.8125rem", marginTop: "0.375rem", display: "flex", alignItems: "center", gap: "4px" }}

              >

                <span>&bull;</span> {t("portal.operatingRegionRequired")}

              </div>

            )}

          </div>



          {/* Save Answers Action Bar */}

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem", marginTop: "1.5rem" }}>

            <button

              type="button"

              className="mw-btn mw-btn-primary btn-primary"

              onClick={handleSave}

              disabled={saving}

              data-testid="save-answers-btn"

            >

              {saving ? t("customerDemo.saving") : t("customerDemo.saveAnswers")}

            </button>

            <button

              type="button"

              className="mw-btn mw-btn-secondary btn-secondary"

              onClick={handleValidateInputs}

              data-testid="validate-setup-btn"

              style={{ marginLeft: "0.5rem" }}

            >

              Validate

            </button>



            {hasUnsavedChanges ? (

              <span className="mw-unsaved-badge">

                {t("customerDemo.unsavedEdits")}

              </span>

            ) : (

              <span style={{ fontSize: "0.75rem", color: "var(--mw-applicable-text)", fontWeight: 500 }}>

                &bull; {t("customerDemo.stepsSaved")} (rev {workspace?.current_revision ?? 0})

              </span>

            )}

          </div>

        </section>



        {/* Right Column: Pack Evaluation & Adoption */}

        <section

          ref={evalSectionRef}

          tabIndex={-1}

          className={`mw-card ${activeStep === 2 ? "active-step-panel" : ""}`}

          aria-labelledby="card-eval-title"

          data-testid="evaluation-section"

        >

          <div className="mw-card-header">

            <h2 id="card-eval-title" className="mw-card-title">

              {t("customerDemo.evaluateTitle")}

            </h2>

            <p className="mw-card-subtitle">

              {t("customerDemo.evaluateSubtitle")}

            </p>

          </div>



          {/* Pack Selection & Compare Button */}

          <div style={{ marginBottom: "1.25rem" }}>

            <label htmlFor="pack-version-select" className="mw-question-label">

              {t("customerDemo.selectPackLabel")}

            </label>

            <div style={{ marginBottom: "0.5rem" }}>

              <input

                type="text"

                className="mw-input"

                placeholder={t("portal.filterFrameworksPlaceholder")}

                value={packFilterQuery}

                onChange={(e) => setPackFilterQuery(e.target.value)}

                data-testid="pack-filter-input-standalone"

                style={{ width: "100%", maxWidth: "360px", fontSize: "0.85rem" }}

              />

            </div>

            <div className="mw-pack-select-row">

              <select

                id="pack-version-select"

                className="mw-pack-select-input"

                value={selectedPackVersionId}

                onChange={(e) => handlePackChange(e.target.value)}

                disabled={saving || evaluating || adopting}

                data-testid="pack-select"

              >

                {groupedPacks.map((g) => (

                  <optgroup key={g.pack_id} label={g.name}>

                    {g.versions.map((p) => (

                      <option key={p.pack_version_id} value={p.pack_version_id}>

                        {p.name} ({p.version}) - {p.requirement_count} {t("customerDemo.controlsCount")} {workspace?.selected_pack?.pack_version_id === p.pack_version_id ? `[${t("portal.adoptedBadge")}]` : `[${t("portal.candidateBadge")}]`}

                      </option>

                    ))}

                  </optgroup>

                ))}

              </select>



              <button

                type="button"

                className="mw-btn mw-btn-secondary btn-secondary"

                onClick={() => setShowComparison((prev) => !prev)}

                data-testid="compare-packs-btn"

              >

                {showComparison ? t("customerDemo.hideComparison") : t("customerDemo.comparePacks")}

              </button>

            </div>

          </div>



          {/* Pack Comparison via FrameworkVersionInspector */}

          {showComparison && workspace && (

            <div style={{ marginTop: "1rem", marginBottom: "1.25rem" }}>

              <FrameworkVersionInspector

                workspace={workspace}

                selectedCandidateVersionId={selectedPackVersionId}

                onSelectCandidateVersion={handlePackChange}

                userRole={userRole}

              />

            </div>

          )}



          {/* Evaluate Action Bar */}

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.25rem", flexWrap: "wrap" }}>

            <button

              type="button"

              className="mw-btn mw-btn-primary btn-primary"

              onClick={handleEvaluate}

              disabled={evaluating || (workspace?.current_revision ?? 0) === 0}

              data-testid="evaluate-btn"

            >

              {evaluating ? t("customerDemo.evaluating") : t("customerDemo.evaluateBtn")}

            </button>

            {(workspace?.current_revision ?? 0) === 0 && (

              <span style={{ fontSize: "0.75rem", color: "var(--mw-text-secondary)" }}>

                {t("customerDemo.saveFirstNotice")}

              </span>

            )}

          </div>



          {/* Evaluation Results & Truthful Status Summary */}

          {latestEval ? (

            <div>

              {/* Truthful Outcomes Summary Bar */}

              <div className="mw-outcomes-summary" data-testid="outcomes-summary-bar">

                <div className="mw-outcomes-metrics">

                  <span className="mw-outcome-metric applicable">

                    &bull; {t("customerDemo.summaryApplicable")}: {outcomeCounts.applicable}

                  </span>

                  <span className="mw-outcome-metric not-applicable">

                    &bull; {t("customerDemo.summaryNotApplicable")}: {outcomeCounts.notApplicable}

                  </span>

                  <span className="mw-outcome-metric needs-info">

                    &bull; {t("customerDemo.summaryNeedsInfo")}: {outcomeCounts.needsInfo}

                  </span>

                </div>



                <button

                  type="button"

                  ref={openerRef}

                  className="mw-btn mw-btn-primary btn-primary"

                  onClick={handleOpenAdoptModal}

                  disabled={!usableEvaluation || saving || evaluating || adopting}

                  data-testid="open-adopt-modal-btn"

                >

                  {t("customerDemo.adoptPackBtn")}

                </button>

              </div>



              <div className="mw-truthful-disclaimer">

                {t("customerDemo.summaryTruthfulNotice")}

              </div>



              {latestEval && latestEval.pack_version_id !== selectedPackVersionId && (

                <div

                  role="status"

                  className="mw-notice-banner"

                  data-testid="evaluation-mismatch-notice"

                  style={{ background: "#fff5f5", borderColor: "#dc3545", color: "#721c24", margin: "1rem 0" }}

                >

                  <strong>Evaluation Mismatch: </strong>

                  The displayed evaluation belongs to another framework pack. Please evaluate the selected candidate to review applicability and adopt.

                </div>

              )}



              <div style={{ marginTop: "1rem" }}>

                <h3 style={{ fontSize: "0.9375rem", fontWeight: 600, margin: "0 0 0.75rem" }}>

                  {t("customerDemo.evaluationResults")} ({t("customerDemo.answersRevision")} {latestEval.answer_revision})

                </h3>



                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>

                  {latestEval.results.map((res) => (

                    <RequirementResultCard

                      key={res.requirement_id}

                      result={res}

                      controlDetail={packRequirementsMap.get(res.requirement_id)}

                    />

                  ))}

                </div>

              </div>

            </div>

          ) : (

            <div style={{ textAlign: "center", padding: "2rem", color: "var(--mw-text-secondary)", background: "var(--mw-surface-secondary)", borderRadius: "var(--mw-radius-md)", border: "1px dashed var(--mw-border)" }}>

              <p style={{ margin: 0, fontSize: "0.875rem" }}>

                {t("customerDemo.noEvaluationYet")}

              </p>

            </div>

          )}

        </section>

      </div>



      {/* Section 3: Immutable Adoption History */}

      <section

        ref={historySectionRef}

        tabIndex={-1}

        className={`mw-history-card ${activeStep === 3 ? "active-step-panel" : ""}`}

        aria-labelledby="history-title"

        data-testid="adoption-history-section"

      >

        <h2 id="history-title" style={{ fontSize: "1.125rem", fontWeight: 600, margin: "0 0 0.25rem" }}>

          {t("customerDemo.historyTitle")}

        </h2>

        <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-secondary)", margin: 0 }}>

          {t("customerDemo.historySubtitle")}

        </p>



        {workspace?.history_summary && workspace.history_summary.length > 0 ? (

          <div className="mw-history-table-wrapper">

            <table className="mw-history-table">

              <thead>

                <tr>

                  <th>{t("customerDemo.selectionRevision")}</th>

                  <th>{t("customerDemo.packVersionId")}</th>

                  <th>{t("customerDemo.bundleDigest")}</th>

                  <th>{t("customerDemo.adoptedTimestamp")}</th>

                </tr>

              </thead>

              <tbody>

                {workspace.history_summary.map((h) => (

                  <tr key={`${h.selection_revision}-${h.bundle_digest}`}>

                    <td><strong>rev {h.selection_revision}</strong></td>

                    <td><code>{h.pack_version_id}</code></td>

                    <td className="mw-digest-code"><code>{h.bundle_digest}</code></td>

                    <td>{new Date(h.created_at).toLocaleString()}</td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        ) : (

          <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-tertiary)", marginTop: "0.75rem" }}>

            {t("customerDemo.historyEmpty")}

          </p>

        )}

      </section>



      {/* Section 4: MVP-B Control Work & Encrypted Evidence Pinning */}

      {workspace?.selected_pack && (

        <ControlEvidenceWorkspace

          tenantId={tenantId}

          token={token}

          selectionRevision={workspace.selected_pack.selection_revision}

          answerRevision={workspace.current_revision}

          hasUnsavedParentEdits={hasUnsavedChanges}

          isAdoptionStale={workspace.selected_pack.is_stale}

          userRole={userRole}

          onSessionExpired={onSessionExpired}

          onDataChange={loadOverviewMetrics}

        />

      )}



      {/* Section 5: MVP-C Human Assessment, Findings, Retest & Audit Readiness */}

      {workspace?.selected_pack && (

        <AssessmentWorkspace

          tenantId={tenantId}

          token={token}

          actorId={userId}

          selectionRevision={workspace.selected_pack.selection_revision}

          answerRevision={workspace.current_revision}

          hasUnsavedParentEdits={hasUnsavedChanges}

          isAdoptionStale={workspace.selected_pack.is_stale}

          userRole={userRole}

          onSessionExpired={onSessionExpired}

          onDataChange={loadOverviewMetrics}

        />

      )}



      {/* Adoption Modal with Exact Requirement-Version Comparison (R9) */}

      {adoptModalOpen && (usableEvaluation || latestEval) && (

        <div

          className="mw-modal-overlay"

          role="dialog"

          aria-modal="true"

          aria-labelledby="adopt-modal-title"

          data-testid="adopt-pack-modal"

          onKeyDown={handleModalKeyDown}

        >

          <div ref={dialogRef} tabIndex={-1} className="mw-modal-dialog">

            <h3 id="adopt-modal-title" className="mw-modal-title">

              {t("customerDemo.adoptTitle")}

            </h3>

            <p className="mw-modal-subtitle">

              {t("customerDemo.adoptSubtitle")}

            </p>



            {/* Exact requirement-version IDs comparison in modal (R9) */}

            <div

              style={{

                background: "var(--mw-surface-secondary)",

                padding: "0.875rem 1rem",

                borderRadius: "var(--mw-radius-md)",

                marginBottom: "1.25rem",

                fontSize: "0.8125rem",

                border: "1px solid var(--mw-border-subtle)",

              }}

            >

              <strong>{t("customerDemo.exactVersions")}</strong>

              <div style={{ fontSize: "0.8rem", color: "var(--mw-text-secondary)", marginTop: "0.25rem" }}>

                Candidate Pack Version ID: <code>{frozenAdoptionIntent?.candidatePackVersionId || selectedPackVersionId}</code>

              </div>

              <div style={{ fontSize: "0.8rem", color: "var(--mw-text-secondary)", marginBottom: "0.5rem" }}>

                Bundle Digest: <code>{(frozenAdoptionIntent?.bundleDigest || (usableEvaluation || latestEval)?.bundle_digest)?.slice(0, 16)}...</code>

              </div>

              <ul style={{ paddingLeft: "1rem", margin: "0.5rem 0 0" }}>

                {(usableEvaluation || latestEval)?.results.map((r) => (

                  <li key={r.requirement_id} style={{ marginBottom: "0.25rem" }}>

                    <code>{r.identifier}</code> ({r.title}) - Version: <code>{r.requirement_version_id}</code> -{" "}

                    <strong>{r.result}</strong>

                  </li>

                ))}

              </ul>

            </div>



            {isCrossPackReplacement && (

              <div

                role="status"

                className="mw-notice-banner"

                data-testid="cross-pack-replacement-warning"

                style={{ background: "#e8f4f8", borderColor: "#17a2b8", color: "#0c5460", marginBottom: "1rem" }}

              >

                <strong>Cross-Pack Replacement: </strong>

                {t("portal.crossPackReplacementDisclaimer")}

              </div>

            )}



            {/* Checkbox 1: Synthetic acknowledgement */}

            {!isModalIntentValid && (
              <div
                role="alert"
                className="mw-notice-banner"
                data-testid="adoption-intent-invalidated-notice"
                style={{ background: "#fff3cd", borderColor: "#ffeeba", color: "#856404", marginBottom: "1rem" }}
              >
                {t("customerDemo.adoptionIntentInvalidated")}
              </div>
            )}

            <div style={{ marginBottom: "0.75rem" }}>

              <label className="mw-checkbox-label">

                <input

                  type="checkbox"

                  checked={ackSynthetic}

                  onChange={(e) => setAckSynthetic(e.target.checked)}

                  data-testid="ack-synthetic-checkbox"

                />

                <span>{t("customerDemo.ackSyntheticLabel")}</span>

              </label>

            </div>



            {/* Checkbox 2: Missing information acknowledgement if needed */}

            {hasMissingInfoInEvaluation && (

              <div style={{ marginBottom: "1rem" }}>

                <label className="mw-checkbox-label" style={{ color: "var(--mw-warning-text)" }}>

                  <input

                    type="checkbox"

                    checked={ackMissing}

                    onChange={(e) => setAckMissing(e.target.checked)}

                    data-testid="ack-missing-checkbox"

                  />

                  <span>{t("customerDemo.ackMissingLabel")}</span>

                </label>

              </div>

            )}



            <div className="mw-modal-actions">

              <button

                type="button"

                className="mw-btn mw-btn-secondary btn-secondary"

                onClick={() => setAdoptModalOpen(false)}

                disabled={adopting}

              >

                {t("common.cancel") || "Cancel"}

              </button>

              <button

                type="button"

                className="mw-btn mw-btn-primary btn-primary"

                onClick={handleAdopt}

                disabled={adopting || !isModalIntentValid || !ackSynthetic || (hasMissingInfoInEvaluation && !ackMissing)}

                data-testid="confirm-adopt-btn"

              >

                {adopting ? t("customerDemo.adopting") : t("customerDemo.confirmAdopt")}

              </button>

            </div>

          </div>

        </div>

      )}

    </ModernWorkspaceShell>

  );

};



interface RequirementResultCardProps {

  result: RequirementEvaluationResult;

  controlDetail?: DemoPackRequirement;

}



const RequirementResultCard: FC<RequirementResultCardProps> = ({ result, controlDetail }) => {

  const { t } = useSafeTranslation();

  const [expanded, setExpanded] = useState<boolean>(false);



  const badgeClass =

    result.result === "APPLICABLE"

      ? "applicable"

      : result.result === "NOT_APPLICABLE"

      ? "not-applicable"

      : "needs-info";



  return (

    <div

      className="mw-req-card"

      data-testid={`req-card-${result.identifier}`}

    >

      <div className="mw-req-header">

        <div>

          <span className="mw-req-id">{result.identifier}</span>

          <span className="mw-req-title">{result.title}</span>

        </div>

        <span className={`mw-req-badge ${badgeClass}`}>

          {result.result}

        </span>

      </div>



      {/* Common Control Mapping */}

      {controlDetail && (

        <div className="mw-control-info">

          <span>{t("customerDemo.controlMapping")} </span>

          <span className="mw-control-id">{controlDetail.control_identifier}</span>

          <span> &mdash; {controlDetail.control_title}</span>

        </div>

      )}



      <div className="mw-req-meta">

        <span>{t("customerDemo.requirementVersion")}: <code>{result.requirement_version_id?.slice(0, 8) ?? ""}...</code></span>

        <button

          type="button"

          className="mw-explanation-toggle"

          onClick={() => setExpanded((prev) => !prev)}

          data-testid={`toggle-explanation-${result.identifier}`}

        >

          {expanded ? t("customerDemo.hideExplanation") : t("customerDemo.viewExplanation")}

        </button>

      </div>



      {expanded && (

        <div

          className="mw-explanation-box"

          data-testid={`explanation-tree-${result.identifier}`}

        >

          <ExplanationTreeView node={result.explanation_tree} />

        </div>

      )}

    </div>

  );

};



interface ExplanationTreeViewProps {

  node: ExplanationTreeNode;

}



const ExplanationTreeView: FC<ExplanationTreeViewProps> = ({ node }) => {

  const { t } = useSafeTranslation();

  const badgeClass =

    node.result === "APPLICABLE"

      ? "applicable"

      : node.result === "NOT_APPLICABLE"

      ? "not-applicable"

      : "needs-info";



  return (

    <div className="mw-explanation-node">

      <div className="mw-explanation-row">

        <code className="mw-op-badge">{node.op}</code>

        <span>{node.message}</span>

        <span className={`mw-req-badge ${badgeClass}`} style={{ fontSize: "0.625rem", padding: "0.1rem 0.4rem" }}>

          {node.result}

        </span>

      </div>



      {node.missing_fact_version_ids && node.missing_fact_version_ids.length > 0 && (

        <div className="mw-missing-facts">

          {t("customerDemo.missingFacts")}: {node.missing_fact_version_ids.join(", ")}

        </div>

      )}



      {node.children && node.children.length > 0 && (

        <div>

          {node.children.map((child, i) => (

            <ExplanationTreeView key={child.path || i} node={child} />

          ))}

        </div>

      )}

    </div>

  );

};

