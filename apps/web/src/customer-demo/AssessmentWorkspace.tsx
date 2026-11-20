import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { UnauthorizedError } from "./api";
import {
  fetchAssessmentHistory,
  fetchAssessmentWorkList,
  fetchProcedure,
  recordAssessment,
  recordRetest,
  updateFinding,
} from "./assessment-api";
import {
  AssessmentCreatePayload,
  AssessmentEvent,
  AssessmentFinding,
  AssessmentResult,
  AssessmentWorkItem,
  CriterionResult,
  CriterionResultItem,
  FindingPatchPayload,
  FindingSeverity,
  Procedure,
  ReadinessSummary,
  RetestCreatePayload,
} from "./assessment-types";
import { fetchControlWorkList, fetchOwnerDirectory } from "./control-evidence-api";
import { AssessmentReportPanel } from "./AssessmentReportPanel";
import { ControlWorkItem, OwnerDirectoryItem } from "./control-evidence-types";
import "./modern-workspace.css";

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
        let curr: unknown = en;
        for (const p of parts) {
          if (curr && typeof curr === "object" && p in curr) {
            curr = (curr as Record<string, unknown>)[p];
          } else {
            curr = undefined;
            break;
          }
        }
        let text = typeof curr === "string" ? curr : parts[parts.length - 1];
        if (params) {
          for (const [k, v] of Object.entries(params)) {
            text = text.replace(`{${k}}`, String(v));
          }
        }
        return text;
      },
    };
  }
}

function getSecureUUID(): string {
  if (typeof crypto !== "undefined") {
    if (typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    if (typeof crypto.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40; // RFC4122 version 4
      bytes[8] = (bytes[8] & 0x3f) | 0x80; // RFC4122 variant 10
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
  }
  throw new Error("Secure random UUID generator unavailable in this environment");
}


interface PendingAssessOp {
  operation_id: string;
  payload: AssessmentCreatePayload;
  definiteError?: boolean;
}

interface PendingFindingOp {
  operation_id: string;
  payload: FindingPatchPayload;
  definiteError?: boolean;
}

interface PendingRetestOp {
  operation_id: string;
  payload: RetestCreatePayload;
  definiteError?: boolean;
}

function areAssessPayloadsEqual(a: AssessmentCreatePayload, b: AssessmentCreatePayload): boolean {
  if (a.result !== b.result || a.rationale !== b.rationale) return false;
  if (a.procedure_digest !== b.procedure_digest) return false;
  if (a.expected_work_version !== b.expected_work_version || a.expected_assessment_revision !== b.expected_assessment_revision) return false;
  if (a.expected_answer_revision !== b.expected_answer_revision || a.expected_selection_revision !== b.expected_selection_revision) return false;
  if (a.evidence_link_ids.length !== b.evidence_link_ids.length || !a.evidence_link_ids.every((id, idx) => id === b.evidence_link_ids[idx])) return false;
  if (a.criterion_results.length !== b.criterion_results.length) return false;
  for (let i = 0; i < a.criterion_results.length; i++) {
    if (a.criterion_results[i].criterion_id !== b.criterion_results[i].criterion_id || a.criterion_results[i].result !== b.criterion_results[i].result) return false;
  }
  const fA = a.finding;
  const fB = b.finding;
  if (Boolean(fA) !== Boolean(fB)) return false;
  if (fA && fB) {
    if (fA.severity !== fB.severity || fA.owner_user_id !== fB.owner_user_id || fA.due_date !== fB.due_date) return false;
  }
  return true;
}

function areFindingPayloadsEqual(a: FindingPatchPayload, b: FindingPatchPayload): boolean {
  return (
    a.severity === b.severity &&
    a.owner_user_id === b.owner_user_id &&
    a.due_date === b.due_date &&
    a.status === b.status &&
    a.remediation_note === b.remediation_note &&
    a.expected_finding_version === b.expected_finding_version &&
    a.expected_assessment_revision === b.expected_assessment_revision &&
    a.expected_work_version === b.expected_work_version &&
    a.expected_answer_revision === b.expected_answer_revision &&
    a.expected_selection_revision === b.expected_selection_revision
  );
}

function areRetestPayloadsEqual(a: RetestCreatePayload, b: RetestCreatePayload): boolean {
  if (a.result !== b.result || a.rationale !== b.rationale) return false;
  if (a.procedure_digest !== b.procedure_digest) return false;
  if (a.expected_work_version !== b.expected_work_version || a.expected_assessment_revision !== b.expected_assessment_revision) return false;
  if (a.expected_answer_revision !== b.expected_answer_revision || a.expected_selection_revision !== b.expected_selection_revision) return false;
  if (a.evidence_link_ids.length !== b.evidence_link_ids.length || !a.evidence_link_ids.every((id, idx) => id === b.evidence_link_ids[idx])) return false;
  if (a.criterion_results.length !== b.criterion_results.length) return false;
  for (let i = 0; i < a.criterion_results.length; i++) {
    if (a.criterion_results[i].criterion_id !== b.criterion_results[i].criterion_id || a.criterion_results[i].result !== b.criterion_results[i].result) return false;
  }
  if (a.findings.length !== b.findings.length) return false;
  for (let i = 0; i < a.findings.length; i++) {
    if (a.findings[i].id !== b.findings[i].id || a.findings[i].expected_version !== b.findings[i].expected_version) return false;
  }
  return true;
}

export interface AssessmentWorkspaceProps {
  tenantId: string;
  token: string;
  adoptionId?: string | null;
  selectionRevision: number;
  answerRevision: number;
  hasUnsavedParentEdits: boolean;
  isAdoptionStale: boolean;
  userRole?: string;
  onSessionExpired?: () => void;
  initialControlWork?: ControlWorkItem[];
  onDataChange?: () => void;
  refreshEpoch?: number;
  isActiveView?: boolean;
  navTarget?: { workId: string; findingId?: string; targetTab?: string; nonce: number; tenantId?: string; adoptionId?: string } | null;
  actorId?: string;
}

export const AssessmentWorkspace: FC<AssessmentWorkspaceProps> = ({
  tenantId,
  token,
  adoptionId,
  selectionRevision,
  answerRevision,
  hasUnsavedParentEdits,
  isAdoptionStale,
  userRole,
  onSessionExpired,
  initialControlWork,
  onDataChange,
  refreshEpoch,
  isActiveView,
  navTarget,
  actorId,
}) => {
  const { t, locale } = useSafeTranslation();

  const [items, setItems] = useState<AssessmentWorkItem[]>([]);
  const [summary, setSummary] = useState<ReadinessSummary | null>(null);
  const [responseContext, setResponseContext] = useState<{
    tenant_id: string;
    adoption_id: string | null;
    answer_revision: number;
    selection_revision: number;
    is_stale: boolean;
  } | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [targetNotFoundWorkId, setTargetNotFoundWorkId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const lastHandledNavNonceRef = useRef<number>(0);
  const loadedSuccessfullyRef = useRef<boolean>(false);

  // Control work map for titles and selectable evidence links
  const [controlWorkMap, setControlWorkMap] = useState<Record<string, ControlWorkItem>>(() => {
    const map: Record<string, ControlWorkItem> = {};
    if (initialControlWork) {
      for (const cw of initialControlWork) {
        map[cw.id] = cw;
      }
    }
    return map;
  });

  // Eligible owners directory
  const [owners, setOwners] = useState<OwnerDirectoryItem[]>([]);

  // Procedure cache per work item
  const [procedures, setProcedures] = useState<Record<string, Procedure>>({});
  const [loadingProc, setLoadingProc] = useState<Record<string, boolean>>({});

  // History state
  const [histories, setHistories] = useState<Record<string, AssessmentEvent[]>>({});
  const [historyOpen, setHistoryOpen] = useState<Record<string, boolean>>({});
  const [loadingHist, setLoadingHist] = useState<Record<string, boolean>>({});

  // Form states per item
  const [activeTab, setActiveTab] = useState<Record<string, "assess" | "findings" | "retest">>({});
  const [selectedResult, setSelectedResult] = useState<Record<string, AssessmentResult | "">>({});
  const [rationale, setRationale] = useState<Record<string, string>>({});
  const [criteriaState, setCriteriaState] = useState<Record<string, Record<string, CriterionResult | "">>>({});
  const [selectedEvidence, setSelectedEvidence] = useState<Record<string, string[]>>({});
  const [submittingAssess, setSubmittingAssess] = useState<Record<string, boolean>>({});

  // Finding creation subform
  const [hasFinding, setHasFinding] = useState<Record<string, boolean>>({});
  const [findingSeverity, setFindingSeverity] = useState<Record<string, FindingSeverity>>({});
  const [findingOwner, setFindingOwner] = useState<Record<string, string>>({});
  const [findingDueDate, setFindingDueDate] = useState<Record<string, string>>({});

  // Finding remediation update form
  const [editingFindingId, setEditingFindingId] = useState<string | null>(null);
  const [remediationNote, setRemediationNote] = useState<string>("");
  const [remediationStatus, setRemediationStatus] = useState<"OPEN" | "IN_REMEDIATION">("IN_REMEDIATION");
  const [remediationOwner, setRemediationOwner] = useState<string>("");
  const [remediationDueDate, setRemediationDueDate] = useState<string>("");
  const [remediationSeverity, setRemediationSeverity] = useState<FindingSeverity>("MEDIUM");
  const [submittingRemediation, setSubmittingRemediation] = useState<boolean>(false);

  // Retest form
  const [retestFindingId, setRetestFindingId] = useState<Record<string, string>>({});
  const [retestRationale, setRetestRationale] = useState<Record<string, string>>({});
  const [retestResult, setRetestResult] = useState<Record<string, AssessmentResult | "">>({});
  const [retestCriteriaState, setRetestCriteriaState] = useState<Record<string, Record<string, CriterionResult | "">>>({});
  const [submittingRetest, setSubmittingRetest] = useState<Record<string, boolean>>({});

  const [retestSelectedEvidence, setRetestSelectedEvidence] = useState<Record<string, string[]>>({});

  // Immutable pending operations preserved for exact network retries
  const pendingAssessRef = useRef<Record<string, PendingAssessOp>>({});
  const pendingFindingRef = useRef<Record<string, PendingFindingOp>>({});
  const pendingRetestRef = useRef<Record<string, PendingRetestOp>>({});

  // Session-generation counter and AbortController to prevent race conditions & leaks
  const sessionGenRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Data epoch counter and AbortController for background refresh fencing
  const dataEpochRef = useRef<number>(0);
  const activeRefreshAbortRef = useRef<AbortController | null>(null);

  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  }, [t]);

  const initialControlWorkRef = useRef(initialControlWork);
  useEffect(() => {
    initialControlWorkRef.current = initialControlWork;
  }, [initialControlWork]);

  const isMutationDisabled = !token || !tenantId || hasUnsavedParentEdits || isAdoptionStale || loading;

  // Centralized 401 session invalidation
  const handleUnauthorized = useCallback(() => {
    sessionGenRef.current += 1;
    dataEpochRef.current += 1;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (activeRefreshAbortRef.current) {
      activeRefreshAbortRef.current.abort();
      activeRefreshAbortRef.current = null;
    }
    setItems([]);
    setSummary(null);
    setResponseContext(null);
    setProcedures({});
    setLoadingProc({});
    setHistories({});
    setHistoryOpen({});
    setLoadingHist({});
    setActiveTab({});
    setSelectedResult({});
    setRationale({});
    setCriteriaState({});
    setSelectedEvidence({});
    setSubmittingAssess({});
    setHasFinding({});
    setFindingSeverity({});
    setFindingOwner({});
    setFindingDueDate({});
    setEditingFindingId(null);
    setRemediationNote("");
    setRemediationStatus("IN_REMEDIATION");
    setRemediationOwner("");
    setRemediationDueDate("");
    setSubmittingRemediation(false);
    setRetestFindingId({});
    setRetestRationale({});
    setRetestResult({});
    setRetestCriteriaState({});
    setRetestSelectedEvidence({});
    setSubmittingRetest({});
    setOwners([]);
    pendingAssessRef.current = {};
    pendingFindingRef.current = {};
    pendingRetestRef.current = {};
    setActionMessage({ type: "error", text: tRef.current("customerDemo.sessionExpired") || "Session expired. Please sign in again." });
    onSessionExpiredRef.current?.();
  }, []);

  // Session load / tenant switch handler
  const loadData = useCallback(async () => {
    sessionGenRef.current += 1;
    const currentGen = sessionGenRef.current;
    dataEpochRef.current += 1;
    if (activeRefreshAbortRef.current) {
      activeRefreshAbortRef.current.abort();
      activeRefreshAbortRef.current = null;
    }

    // Abort pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const ac = new AbortController();
    abortControllerRef.current = ac;

    // Immediately wipe sensitive state
    setItems([]);
    setSummary(null);
    setResponseContext(null);
    setError(null);
    setActionMessage(null);
    setProcedures({});
    setLoadingProc({});
    setHistories({});
    setHistoryOpen({});
    setLoadingHist({});
    setActiveTab({});
    setSelectedResult({});
    setRationale({});
    setCriteriaState({});
    setSelectedEvidence({});
    setSubmittingAssess({});
    setHasFinding({});
    setFindingSeverity({});
    setFindingOwner({});
    setFindingDueDate({});
    setEditingFindingId(null);
    setRemediationNote("");
    setRemediationStatus("IN_REMEDIATION");
    setRemediationOwner("");
    setRemediationDueDate("");
    setSubmittingRemediation(false);
    setRetestFindingId({});
    setRetestRationale({});
    setRetestResult({});
    setRetestCriteriaState({});
    setSubmittingRetest({});
    setControlWorkMap(() => {
      const map: Record<string, ControlWorkItem> = {};
      if (initialControlWorkRef.current) {
        for (const cw of initialControlWorkRef.current) {
          map[cw.id] = cw;
        }
      }
      return map;
    });
    setOwners([]);
    pendingAssessRef.current = {};
    pendingFindingRef.current = {};
    pendingRetestRef.current = {};
    setRetestSelectedEvidence({});

    if (!tenantId || !token) {
      setLoading(false);
      return;
    }

    setLoading(true);

    try {
      const [assessmentRes, controlRes, ownerRes] = await Promise.allSettled([
        fetchAssessmentWorkList(tenantId, token, ac.signal),
        fetchControlWorkList(tenantId, token, undefined, ac.signal),
        fetchOwnerDirectory(tenantId, token, ac.signal),
      ]);

      if (sessionGenRef.current !== currentGen || ac.signal.aborted) {
        return;
      }

      if (assessmentRes.status === "fulfilled") {
        loadedSuccessfullyRef.current = true;
        setItems(assessmentRes.value.items);
        setSummary(assessmentRes.value.summary);
        setResponseContext({
          tenant_id: assessmentRes.value.tenant_id,
          adoption_id: assessmentRes.value.adoption_id,
          answer_revision: assessmentRes.value.answer_revision,
          selection_revision: assessmentRes.value.selection_revision,
          is_stale: assessmentRes.value.is_stale,
        });
      } else {
        loadedSuccessfullyRef.current = false;
        setResponseContext(null);
        loadedSuccessfullyRef.current = false;
        const err = assessmentRes.reason;
        if (err instanceof UnauthorizedError) {
          handleUnauthorized();
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load assessment data");
      }

      if (controlRes.status === "rejected" && controlRes.reason instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (ownerRes.status === "rejected" && ownerRes.reason instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }

      if (controlRes.status === "fulfilled") {
        const map: Record<string, ControlWorkItem> = {};
        for (const cw of controlRes.value.items) {
          map[cw.id] = cw;
        }
        setControlWorkMap(map);
      }

      if (ownerRes.status === "fulfilled") {
        setOwners(ownerRes.value.items);
      }
    } finally {
      if (sessionGenRef.current === currentGen && !ac.signal.aborted) {
        setLoading(false);
      }
    }
  }, [tenantId, token, handleUnauthorized]);

  useEffect(() => {
    let ignore = false;
    void (async () => {
      await Promise.resolve();
      if (!ignore) {
        await loadData();
      }
    })();
    return () => {
      ignore = true;
      abortControllerRef.current?.abort();
      activeRefreshAbortRef.current?.abort();
      dataEpochRef.current += 1;
    };
  }, [loadData]);

  const refreshWorkData = useCallback(async () => {
    if (!tenantId || !token) return;

    if (activeRefreshAbortRef.current) {
      activeRefreshAbortRef.current.abort();
    }
    const ac = new AbortController();
    activeRefreshAbortRef.current = ac;

    const currentGen = sessionGenRef.current;
    const currentTenant = tenantId;
    const currentToken = token;
    const currentSelectionRev = selectionRevision;
    const currentAnswerRev = answerRevision;
    const reqEpoch = ++dataEpochRef.current;
    setIsRefreshing(true);

    try {
      const [assessmentRes, controlRes, ownerRes] = await Promise.allSettled([
        fetchAssessmentWorkList(tenantId, token, ac.signal),
        fetchControlWorkList(tenantId, token, undefined, ac.signal),
        fetchOwnerDirectory(tenantId, token, ac.signal),
      ]);

      if (
        ac.signal.aborted ||
        sessionGenRef.current !== currentGen ||
        dataEpochRef.current !== reqEpoch ||
        tenantId !== currentTenant ||
        token !== currentToken ||
        selectionRevision !== currentSelectionRev ||
        answerRevision !== currentAnswerRev
      ) {
        return;
      }

      if (assessmentRes.status === "fulfilled") {
        loadedSuccessfullyRef.current = true;
        setItems(assessmentRes.value.items);
        setSummary(assessmentRes.value.summary);
        setResponseContext({
          tenant_id: assessmentRes.value.tenant_id,
          adoption_id: assessmentRes.value.adoption_id,
          answer_revision: assessmentRes.value.answer_revision,
          selection_revision: assessmentRes.value.selection_revision,
          is_stale: assessmentRes.value.is_stale,
        });
      }
      if (controlRes.status === "fulfilled") {
        const map: Record<string, ControlWorkItem> = {};
        for (const cw of controlRes.value.items) {
          map[cw.id] = cw;
        }
        setControlWorkMap(map);
      }
      if (ownerRes.status === "fulfilled") {
        setOwners(ownerRes.value.items);
      }
    } catch {
      // Background refresh failure is non-blocking to active user drafts
    } finally {
      if (sessionGenRef.current === currentGen && dataEpochRef.current === reqEpoch) {
        setIsRefreshing(false);
      }
    }
  }, [tenantId, token, selectionRevision, answerRevision]);

  const prevIsActiveViewRef = useRef<boolean | undefined>(isActiveView);
  const prevRefreshEpochRef = useRef<number | undefined>(refreshEpoch);

  useEffect(() => {
    if (!navTarget) return;
    if (navTarget.tenantId && navTarget.tenantId !== tenantId) return;
    if (adoptionId && navTarget.adoptionId && navTarget.adoptionId !== "current" && adoptionId !== "current" && navTarget.adoptionId !== adoptionId) return;
    if (loading || isRefreshing) return;
    if (navTarget.nonce === lastHandledNavNonceRef.current) return;

    const exists = items.some((item) => item.work_id === navTarget.workId);
    if (exists) {
      lastHandledNavNonceRef.current = navTarget.nonce;
      setTimeout(() => {
        setTargetNotFoundWorkId(null);
        if (navTarget.findingId || navTarget.targetTab === "finding" || navTarget.targetTab === "findings") {
          setActiveTab((prev) => ({ ...prev, [navTarget.workId]: "findings" }));
        } else {
          setActiveTab((prev) => ({ ...prev, [navTarget.workId]: "assess" }));
        }
      }, 0);

      setTimeout(() => {
        if (navTarget.findingId) {
          const fRow = document.querySelector(`[data-testid="finding-row-${navTarget.findingId}"]`);
          if (fRow) {
            if (typeof fRow.scrollIntoView === "function") { fRow.scrollIntoView({ behavior: "smooth", block: "center" }); }
            const editBtn = fRow.querySelector<HTMLButtonElement>(`[data-testid="edit-finding-btn-${navTarget.findingId}"]`);
            editBtn?.focus();
            return;
          }
        }
        const cardEl = document.querySelector(`[data-testid="assessment-card-${navTarget.workId}"]`);
        if (cardEl) {
          if (typeof cardEl.scrollIntoView === "function") { cardEl.scrollIntoView({ behavior: "smooth", block: "center" }); }
          const assessTabBtn = cardEl.querySelector<HTMLButtonElement>(`[data-testid="tab-assess-${navTarget.workId}"]`);
          assessTabBtn?.focus();
        }
      }, 50);
    } else if (loadedSuccessfullyRef.current && !error) {
      // Authoritative not-found ONLY after settled successful load without errors
      lastHandledNavNonceRef.current = navTarget.nonce;
      setTimeout(() => {
        setTargetNotFoundWorkId(navTarget.workId);
      }, 0);
    }
  }, [navTarget, items, loading, isRefreshing, error, tenantId, adoptionId]);

  useEffect(() => {
    loadedSuccessfullyRef.current = false;
    setTimeout(() => setTargetNotFoundWorkId(null), 0);
  }, [tenantId, adoptionId]);

  useEffect(() => {
    const becameActive = Boolean(isActiveView && !prevIsActiveViewRef.current);
    const epochBumped = Boolean(refreshEpoch !== undefined && refreshEpoch !== prevRefreshEpochRef.current);
    prevIsActiveViewRef.current = isActiveView;
    prevRefreshEpochRef.current = refreshEpoch;

    if (becameActive || (epochBumped && refreshEpoch! > 0)) {
      void refreshWorkData();
    }
  }, [isActiveView, refreshEpoch, refreshWorkData]);

  const loadProcedureForItem = useCallback(
    async (workId: string) => {
      const currentGen = sessionGenRef.current;
      if (procedures[workId] || loadingProc[workId] || !tenantId || !token) return;
      setLoadingProc((p) => ({ ...p, [workId]: true }));
      try {
        const proc = await fetchProcedure(tenantId, token, workId);
        if (sessionGenRef.current !== currentGen) return;
        setProcedures((p) => ({ ...p, [workId]: proc }));
      } catch (err: unknown) {
        if (sessionGenRef.current !== currentGen) return;
        if (err instanceof UnauthorizedError) {
          handleUnauthorized();
          return;
        }
      } finally {
        if (sessionGenRef.current === currentGen) {
          setLoadingProc((p) => ({ ...p, [workId]: false }));
        }
      }
    },
    [tenantId, token, procedures, loadingProc, handleUnauthorized]
  );

  const toggleHistory = useCallback(
    async (workId: string) => {
      const currentGen = sessionGenRef.current;
      const nextState = !historyOpen[workId];
      setHistoryOpen((prev) => ({ ...prev, [workId]: nextState }));
      if (nextState && !histories[workId] && tenantId && token) {
        setLoadingHist((p) => ({ ...p, [workId]: true }));
        try {
          const hist = await fetchAssessmentHistory(tenantId, token, workId);
          if (sessionGenRef.current !== currentGen) return;
          setHistories((h) => ({ ...h, [workId]: hist.items }));
        } catch (err: unknown) {
          if (sessionGenRef.current !== currentGen) return;
          if (err instanceof UnauthorizedError) {
          handleUnauthorized();
          return;
        }
        } finally {
          if (sessionGenRef.current === currentGen) {
            setLoadingHist((p) => ({ ...p, [workId]: false }));
          }
        }
      }
    },
    [tenantId, token, historyOpen, histories, handleUnauthorized]
  );

  const handleRecordAssessment = async (item: AssessmentWorkItem) => {
    const currentGen = sessionGenRef.current;
    if (isMutationDisabled || sessionGenRef.current !== currentGen) return;

    let proc = procedures[item.work_id];
    if (!proc) {
      try {
        proc = await fetchProcedure(tenantId, token, item.work_id);
        if (sessionGenRef.current !== currentGen) return;
        setProcedures((p) => ({ ...p, [item.work_id]: proc }));
      } catch (err: unknown) {
        if (sessionGenRef.current !== currentGen) return;
        if (err instanceof UnauthorizedError) {
          handleUnauthorized();
          return;
        }
        return;
      }
    }

    const assignedResult = selectedResult[item.work_id];
    if (!assignedResult) {
      setActionMessage({ type: "error", text: "Please select an assessment result" });
      return;
    }

    const itemRationale = (rationale[item.work_id] || "").trim();
    if (!itemRationale) {
      setActionMessage({ type: "error", text: "Assessment rationale cannot be empty" });
      return;
    }

    const cState = criteriaState[item.work_id] || {};
    const unselected = proc.criteria.find((c) => !cState[c.id]);
    if (unselected) {
      setActionMessage({
        type: "error",
        text: `Please evaluate all criteria (criterion '${unselected.title}' is unselected)`,
      });
      return;
    }

    const criterion_results: CriterionResultItem[] = proc.criteria.map((c) => ({
      criterion_id: c.id,
      result: cState[c.id] as CriterionResult,
    }));

    // Evidence links: explicitly chosen (default none)
    const chosenEvidenceLinks = selectedEvidence[item.work_id] ?? [];
    if (assignedResult === "PASS" && chosenEvidenceLinks.length === 0) {
      setActionMessage({
        type: "error",
        text: t("customerDemo.evidenceRequiredForPass") || "At least one evidence link must be selected for PASS",
      });
      return;
    }

    if ((assignedResult === "FAIL" || assignedResult === "PARTIAL") && hasFinding[item.work_id]) {
      const sev = findingSeverity[item.work_id];
      if (!sev) {
        setActionMessage({ type: "error", text: "Finding severity is required" });
        return;
      }
    }

    const candidatePayload: AssessmentCreatePayload = {
      operation_id: "",
      expected_answer_revision: answerRevision,
      expected_selection_revision: selectionRevision,
      expected_work_version: item.work_version,
      expected_assessment_revision: item.assessment_revision,
      procedure_id: proc.id,
      procedure_version: proc.version,
      procedure_digest: proc.digest,
      evidence_link_ids: chosenEvidenceLinks,
      criterion_results,
      result: assignedResult,
      rationale: itemRationale,
    };

    if ((assignedResult === "FAIL" || assignedResult === "PARTIAL") && hasFinding[item.work_id]) {
      candidatePayload.finding = {
        severity: findingSeverity[item.work_id],
        owner_user_id: findingOwner[item.work_id] || null,
        due_date: findingDueDate[item.work_id] || null,
      };
    }

    const existingPending = pendingAssessRef.current[item.work_id];
    let opId: string;
    if (
      existingPending &&
      !existingPending.definiteError &&
      areAssessPayloadsEqual(existingPending.payload, candidatePayload)
    ) {
      opId = existingPending.operation_id;
    } else {
      opId = getSecureUUID();
      candidatePayload.operation_id = opId;
      pendingAssessRef.current[item.work_id] = { operation_id: opId, payload: candidatePayload };
    }
    candidatePayload.operation_id = opId;

    setSubmittingAssess((s) => ({ ...s, [item.work_id]: true }));
    setActionMessage(null);

    try {
      const receipt = await recordAssessment(tenantId, token, item.work_id, candidatePayload);
      if (sessionGenRef.current !== currentGen) return;

      dataEpochRef.current += 1;
      if (activeRefreshAbortRef.current) {
        activeRefreshAbortRef.current.abort();
        activeRefreshAbortRef.current = null;
      }

      // On success, clear the preserved pending operation and reset form
      delete pendingAssessRef.current[item.work_id];
      setItems((prev) => prev.map((it) => (it.work_id === item.work_id ? receipt.current_item : it)));
      setSummary(receipt.summary);
      onDataChange?.();
      setActionMessage({ type: "success", text: t("customerDemo.recordAssessmentBtn") + " - OK" });
      setRationale((r) => ({ ...r, [item.work_id]: "" }));
      setSelectedResult((r) => ({ ...r, [item.work_id]: "" }));
      setCriteriaState((cs) => ({ ...cs, [item.work_id]: {} }));
      setSelectedEvidence((se) => ({ ...se, [item.work_id]: [] }));
      setHasFinding((hf) => ({ ...hf, [item.work_id]: false }));
      setFindingSeverity((fs) => ({ ...fs, [item.work_id]: "LOW" as FindingSeverity }));
      setFindingOwner((fo) => ({ ...fo, [item.work_id]: "" }));
      setFindingDueDate((fd) => ({ ...fd, [item.work_id]: "" }));
    } catch (err: unknown) {
      if (sessionGenRef.current !== currentGen) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (
        err instanceof Error &&
        (err.message.includes("422") ||
          err.message.includes("409") ||
          err.message.includes("Conflict") ||
          err.message.includes("Validation"))
      ) {
        if (pendingAssessRef.current[item.work_id]) {
          pendingAssessRef.current[item.work_id].definiteError = true;
        }
      }
      setActionMessage({ type: "error", text: err instanceof Error ? err.message : "Assessment failed" });
    } finally {
      if (sessionGenRef.current === currentGen) {
        setSubmittingAssess((s) => ({ ...s, [item.work_id]: false }));
      }
    }
  };

  const handleUpdateFinding = async (item: AssessmentWorkItem, finding: AssessmentFinding) => {
    const currentGen = sessionGenRef.current;
    if (isMutationDisabled || sessionGenRef.current !== currentGen) return;

    const trimmedNote = remediationNote.trim();
    if (!trimmedNote) {
      setActionMessage({ type: "error", text: "Remediation note cannot be empty" });
      return;
    }

    const candidatePayload: FindingPatchPayload = {
      operation_id: "",
      expected_answer_revision: answerRevision,
      expected_selection_revision: selectionRevision,
      expected_work_version: item.work_version,
      expected_assessment_revision: item.assessment_revision,
      expected_finding_version: finding.version,
      severity: remediationSeverity || finding.severity,
      owner_user_id: remediationOwner !== "" ? remediationOwner : null,
      due_date: remediationDueDate !== "" ? remediationDueDate : null,
      status: remediationStatus,
      remediation_note: trimmedNote,
    };

    const existingPending = pendingFindingRef.current[finding.id];
    let opId: string;
    if (
      existingPending &&
      !existingPending.definiteError &&
      areFindingPayloadsEqual(existingPending.payload, candidatePayload)
    ) {
      opId = existingPending.operation_id;
    } else {
      opId = getSecureUUID();
      candidatePayload.operation_id = opId;
      pendingFindingRef.current[finding.id] = { operation_id: opId, payload: candidatePayload };
    }
    candidatePayload.operation_id = opId;

    setSubmittingRemediation(true);
    setActionMessage(null);

    try {
      const receipt = await updateFinding(tenantId, token, finding.id, candidatePayload);
      if (sessionGenRef.current !== currentGen) return;

      dataEpochRef.current += 1;
      if (activeRefreshAbortRef.current) {
        activeRefreshAbortRef.current.abort();
        activeRefreshAbortRef.current = null;
      }

      delete pendingFindingRef.current[finding.id];
      setItems((prev) => prev.map((it) => (it.work_id === item.work_id ? receipt.current_item : it)));
      setSummary(receipt.summary);
      onDataChange?.();
      setEditingFindingId(null);
      setRemediationNote("");
      setActionMessage({ type: "success", text: t("customerDemo.updateFindingBtn") + " - OK" });
    } catch (err: unknown) {
      if (sessionGenRef.current !== currentGen) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (
        err instanceof Error &&
        (err.message.includes("422") ||
          err.message.includes("409") ||
          err.message.includes("Conflict") ||
          err.message.includes("Validation"))
      ) {
        if (pendingFindingRef.current[finding.id]) {
          pendingFindingRef.current[finding.id].definiteError = true;
        }
      }
      setActionMessage({ type: "error", text: err instanceof Error ? err.message : "Finding update failed" });
    } finally {
      if (sessionGenRef.current === currentGen) {
        setSubmittingRemediation(false);
      }
    }
  };

  const handleRecordRetest = async (item: AssessmentWorkItem) => {
    const currentGen = sessionGenRef.current;
    if (isMutationDisabled || sessionGenRef.current !== currentGen) return;

    let proc = procedures[item.work_id];
    if (!proc) {
      try {
        proc = await fetchProcedure(tenantId, token, item.work_id);
        if (sessionGenRef.current !== currentGen) return;
        setProcedures((p) => ({ ...p, [item.work_id]: proc }));
      } catch (err: unknown) {
        if (sessionGenRef.current !== currentGen) return;
        if (err instanceof UnauthorizedError) {
          handleUnauthorized();
          return;
        }
        return;
      }
    }

    const unresolvedFindings = item.findings.filter((f) => f.status === "OPEN" || f.status === "IN_REMEDIATION");
    const targetFindingId = retestFindingId[item.work_id];
    const targetFinding = unresolvedFindings.find((f) => f.id === targetFindingId);

    if (!targetFinding) {
      setActionMessage({ type: "error", text: "Please select an unresolved finding to retest" });
      return;
    }

    const assignedResult = retestResult[item.work_id];
    if (!assignedResult) {
      setActionMessage({ type: "error", text: "Please select a retest outcome" });
      return;
    }

    const itemRationale = (retestRationale[item.work_id] || "").trim();
    if (!itemRationale) {
      setActionMessage({ type: "error", text: "Retest rationale cannot be empty" });
      return;
    }

    const cState = retestCriteriaState[item.work_id] || {};
    const unselected = proc.criteria.find((c) => !cState[c.id]);
    if (unselected) {
      setActionMessage({
        type: "error",
        text: `Please evaluate all criteria for retest (criterion '${unselected.title}' is unselected)`,
      });
      return;
    }

    const criterion_results: CriterionResultItem[] = proc.criteria.map((c) => ({
      criterion_id: c.id,
      result: cState[c.id] as CriterionResult,
    }));

    if (assignedResult === "PASS" && criterion_results.some((c) => c.result !== "PASS")) {
      setActionMessage({ type: "error", text: "PASS retest requires all criteria to be PASS" });
      return;
    }
    if (assignedResult === "FAIL" && criterion_results.every((c) => c.result === "PASS")) {
      setActionMessage({ type: "error", text: "FAIL retest requires at least one FAIL criterion" });
      return;
    }

    // Evidence links for retest: explicitly chosen (default none)
    const chosenEvidenceLinks = retestSelectedEvidence[item.work_id] ?? [];
    if (assignedResult === "PASS" && chosenEvidenceLinks.length === 0) {
      setActionMessage({
        type: "error",
        text: t("customerDemo.evidenceRequiredForPass") || "At least one evidence link must be selected for PASS",
      });
      return;
    }

    const candidatePayload: RetestCreatePayload = {
      operation_id: "",
      expected_answer_revision: answerRevision,
      expected_selection_revision: selectionRevision,
      expected_work_version: item.work_version,
      expected_assessment_revision: item.assessment_revision,
      procedure_id: proc.id,
      procedure_version: proc.version,
      procedure_digest: proc.digest,
      evidence_link_ids: chosenEvidenceLinks,
      criterion_results,
      result: assignedResult,
      rationale: itemRationale,
      findings: [{ id: targetFinding.id, expected_version: targetFinding.version }],
    };

    const existingPending = pendingRetestRef.current[item.work_id];
    let opId: string;
    if (
      existingPending &&
      !existingPending.definiteError &&
      areRetestPayloadsEqual(existingPending.payload, candidatePayload)
    ) {
      opId = existingPending.operation_id;
    } else {
      opId = getSecureUUID();
      candidatePayload.operation_id = opId;
      pendingRetestRef.current[item.work_id] = { operation_id: opId, payload: candidatePayload };
    }
    candidatePayload.operation_id = opId;

    setSubmittingRetest((s) => ({ ...s, [item.work_id]: true }));
    setActionMessage(null);

    try {
      const receipt = await recordRetest(tenantId, token, item.work_id, candidatePayload);
      if (sessionGenRef.current !== currentGen) return;

      dataEpochRef.current += 1;
      if (activeRefreshAbortRef.current) {
        activeRefreshAbortRef.current.abort();
        activeRefreshAbortRef.current = null;
      }

      delete pendingRetestRef.current[item.work_id];
      setItems((prev) => prev.map((it) => (it.work_id === item.work_id ? receipt.current_item : it)));
      setSummary(receipt.summary);
      onDataChange?.();
      setActionMessage({ type: "success", text: t("customerDemo.retestBtn") + " - OK" });
      setRetestRationale((r) => ({ ...r, [item.work_id]: "" }));
      setRetestResult((r) => ({ ...r, [item.work_id]: "" }));
      setRetestFindingId((f) => ({ ...f, [item.work_id]: "" }));
      setRetestCriteriaState((cs) => ({ ...cs, [item.work_id]: {} }));
      setRetestSelectedEvidence((se) => ({ ...se, [item.work_id]: [] }));
    } catch (err: unknown) {
      if (sessionGenRef.current !== currentGen) return;
      if (err instanceof UnauthorizedError) {
        handleUnauthorized();
        return;
      }
      if (
        err instanceof Error &&
        (err.message.includes("422") ||
          err.message.includes("409") ||
          err.message.includes("Conflict") ||
          err.message.includes("Validation"))
      ) {
        if (pendingRetestRef.current[item.work_id]) {
          pendingRetestRef.current[item.work_id].definiteError = true;
        }
      }
      setActionMessage({ type: "error", text: err instanceof Error ? err.message : "Retest failed" });
    } finally {
      if (sessionGenRef.current === currentGen) {
        setSubmittingRetest((s) => ({ ...s, [item.work_id]: false }));
      }
    }
  };

  const normalizedRole = (userRole || "").toLowerCase().trim();
  const isReportAdmitted = Boolean(
    normalizedRole === "owner" ||
    normalizedRole === "compliance_manager" ||
    normalizedRole === "compliancemanager" ||
    normalizedRole === "compliance-manager"
  );

  const isContextCurrent =
    Boolean(responseContext) &&
    !loading &&
    !error &&
    !hasUnsavedParentEdits &&
    !isAdoptionStale &&
    !responseContext?.is_stale &&
    responseContext?.tenant_id === tenantId &&
    Boolean(responseContext?.adoption_id) &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(responseContext?.adoption_id || "") &&
    (!adoptionId || adoptionId === "current" || responseContext?.adoption_id === adoptionId) &&
    responseContext?.answer_revision === answerRevision &&
    responseContext?.selection_revision === selectionRevision;

  return (
    <section className="mw-assessment-section" aria-labelledby="assessment-section-title">
      <header className="mw-section-header">
        <h2 id="assessment-section-title" className="mw-section-title">
          {t("customerDemo.assessmentWorkTitle")}
        </h2>
        <p className="mw-section-subtitle">{t("customerDemo.assessmentWorkSubtitle")}</p>
      </header>

      {/* Readiness Summary Card */}
      {summary && (
        <div className="mw-readiness-summary-card" role="region" aria-label={t("customerDemo.readinessSummaryTitle")}>
          <h3 className="mw-summary-title">{t("customerDemo.readinessSummaryTitle")}</h3>
          <div className="mw-summary-grid">
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val">{summary.total_controls}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryTotalControls")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val pass">{summary.pass_count}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryPass")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val unassessed">{summary.unassessed}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryUnassessed")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val blocked">{summary.blocked_control_ids.length}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryBlocked")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val fail">{summary.open_findings}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryOpenFindings")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val blocked">{summary.in_remediation_findings}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryInRemediation")}</div>
            </div>
            <div className="mw-summary-metric">
              <div className="mw-summary-metric-val pass">{summary.resolved_findings}</div>
              <div className="mw-summary-metric-label">{t("customerDemo.summaryResolvedFindings")}</div>
            </div>
          </div>
        </div>
      )}

      {/* Assessment Report Download Panel */}
      <AssessmentReportPanel
        tenantId={isContextCurrent && responseContext ? responseContext.tenant_id : tenantId}
        adoptionId={isContextCurrent && responseContext?.adoption_id ? responseContext.adoption_id : ""}
        answerRevision={isContextCurrent && responseContext ? responseContext.answer_revision : 0}
        selectionRevision={isContextCurrent && responseContext ? responseContext.selection_revision : 0}
        token={token}
        actorId={actorId || ""}
        admitted={isReportAdmitted}
        locale={locale || "en"}
        onSessionExpired={onSessionExpired}
      />

      {hasUnsavedParentEdits && (
        <div className="mw-warning-notice" role="status" data-testid="report-unsaved-parent-warning" style={{ marginBottom: "1rem" }}>
          <span>Report download unavailable while parent changes are unsaved.</span>
        </div>
      )}

      {(isAdoptionStale || responseContext?.is_stale) && (
        <div className="mw-warning-notice" role="status" data-testid="report-stale-adoption-warning" style={{ marginBottom: "1rem" }}>
          <span>Report download unavailable because framework adoption is stale.</span>
        </div>
      )}

      {actionMessage && (
        <div className={`mw-alert-banner ${actionMessage.type}`} role="alert">
          {actionMessage.text}
        </div>
      )}

      {error && (
        <div className="mw-alert-banner error" role="alert">
          {error}
        </div>
      )}

      {targetNotFoundWorkId && (
        <div className="mw-warning-notice" role="status" data-testid="assessment-nav-target-not-found" style={{ marginBottom: "1rem" }}>
          <span>{t("portal.navTargetNotFound") || "Requested item was not found in the current adoption."} ({targetNotFoundWorkId})</span>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="dismiss-assessment-nav-target-btn"
            onClick={() => setTargetNotFoundWorkId(null)}
            style={{ marginLeft: "0.5rem", fontSize: "0.75rem", padding: "0.15rem 0.4rem" }}
          >
            {t("portal.dismissBtn") || t("portal.closeBtn") || "Dismiss"}
          </button>
        </div>
      )}

      {loading ? (
        <div className="mw-loading-indicator" role="status">
          {t("customerDemo.evaluating")}
        </div>
      ) : items.length === 0 ? (
        <p className="mw-empty-text">{t("customerDemo.noControlWorkYet")}</p>
      ) : (
        <div className="mw-assessment-list">
          {items.map((item) => {
            const controlWork = controlWorkMap[item.work_id];
            const displayTitle = controlWork?.title || item.control_version_id;
            const provenance = controlWork?.provenance || "Standard Control";
            const packVersion = controlWork?.pack_version ?? 1;

            const acceptedLinks = (controlWork?.links || []).filter((l) => l.review === "ACCEPTED");
            const currentTab = activeTab[item.work_id] || "assess";
            const proc = procedures[item.work_id] || item.procedure;
            const unresolvedFindings = item.findings.filter(
              (f) => f.status === "OPEN" || f.status === "IN_REMEDIATION"
            );

            return (
              <article
                key={item.work_id}
                className="mw-assessment-card"
                aria-label={`Assessment for ${displayTitle}`}
                data-testid={`assessment-card-${item.work_id}`}
              >
                <header className="mw-card-header">
                  <div>
                    <h3 className="mw-control-title">{displayTitle}</h3>
                    <span className="mw-meta-pill">
                      {provenance} • Pack v{packVersion} • Work v{item.work_version} • Rev {item.assessment_revision}
                    </span>
                  </div>
                  <div>
                    <span className={`mw-assessment-state-badge ${item.primary_state.toLowerCase()}`}>
                      {item.primary_state === "UNASSESSED"
                        ? t("customerDemo.statusUnassessed")
                        : item.primary_state === "PASS"
                        ? t("customerDemo.statusPass")
                        : item.primary_state === "PARTIAL"
                        ? t("customerDemo.statusPartial")
                        : item.primary_state === "FAIL"
                        ? t("customerDemo.statusFail")
                        : item.primary_state === "INSUFFICIENT_EVIDENCE"
                        ? t("customerDemo.statusInsufficientEvidence")
                        : item.primary_state === "STALE_ASSESSMENT"
                        ? t("customerDemo.statusStale")
                        : item.primary_state}
                    </span>
                  </div>
                </header>

                {/* Requirement Results if present */}
                {item.requirement_results && item.requirement_results.length > 0 && (
                  <div className="mw-req-results-box" style={{ margin: "0.5rem 0", fontSize: "0.85rem" }}>
                    <div style={{ fontWeight: 600, color: "#475569" }}>Evaluation Requirements:</div>
                    <ul style={{ margin: "0.25rem 0 0 1rem", padding: 0 }}>
                      {item.requirement_results.map((r, idx) => (
                        <li key={idx}>
                          Requirement {String(r.requirement_id || idx + 1)}:{" "}
                          <strong>{String(r.status || "EVALUATED")}</strong>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Evidence Summary & Selection */}
                <div className="mw-evidence-status-pill" style={{ marginBottom: "0.5rem" }}>
                  {acceptedLinks.length > 0
                    ? `Evidence: ${acceptedLinks.length} accepted file(s)`
                    : "No accepted evidence linked"}
                </div>

                {/* Tab Navigation */}
                <div className="mw-tab-bar" role="tablist">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={currentTab === "assess"}
                    data-testid={`tab-assess-${item.work_id}`}
                    className={`mw-tab-btn ${currentTab === "assess" ? "active" : ""}`}
                    onClick={() => {
                      setActiveTab((prev) => ({ ...prev, [item.work_id]: "assess" }));
                      void loadProcedureForItem(item.work_id);
                    }}
                  >
                    {t("customerDemo.recordAssessmentBtn")}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={currentTab === "findings"}
                    data-testid={`tab-findings-${item.work_id}`}
                    className={`mw-tab-btn ${currentTab === "findings" ? "active" : ""}`}
                    onClick={() => setActiveTab((prev) => ({ ...prev, [item.work_id]: "findings" }))}
                  >
                    {t("customerDemo.findingsTitle")} ({item.findings.length})
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={currentTab === "retest"}
                    data-testid={`tab-retest-${item.work_id}`}
                    className={`mw-tab-btn ${currentTab === "retest" ? "active" : ""}`}
                    onClick={() => {
                      setActiveTab((prev) => ({ ...prev, [item.work_id]: "retest" }));
                      void loadProcedureForItem(item.work_id);
                    }}
                  >
                    {t("customerDemo.retestTitle")}
                  </button>
                  <button
                    type="button"
                    className="mw-tab-btn secondary"
                    onClick={() => void toggleHistory(item.work_id)}
                  >
                    {historyOpen[item.work_id] ? t("customerDemo.hideHistoryBtn") : t("customerDemo.viewHistoryBtn")}
                  </button>
                </div>

                {/* Tab 1: Human Assessment Form */}
                {currentTab === "assess" && (
                  <div className="mw-tab-content">
                    {!proc ? (
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid={`load-procedure-btn-${item.work_id}`}
                        onClick={() => void loadProcedureForItem(item.work_id)}
                        disabled={loadingProc[item.work_id]}
                      >
                        {loadingProc[item.work_id] ? "Loading Procedure..." : t("customerDemo.assessmentProcedureTitle")}
                      </button>
                    ) : (
                      <div className="mw-procedure-box">
                        <h4 className="mw-procedure-title">{t("customerDemo.assessmentProcedureTitle")}</h4>
                        <div className="mw-criteria-list">
                          {proc.criteria.map((c) => (
                            <div key={c.id} className="mw-criterion-row">
                              <div className="mw-criterion-header">
                                <span className="mw-criterion-name">{c.title}</span>
                                <select
                                  aria-label={`Criterion ${c.title}`}
                                  value={criteriaState[item.work_id]?.[c.id] || ""}
                                  disabled={isMutationDisabled}
                                  onChange={(e) =>
                                    setCriteriaState((prev) => ({
                                      ...prev,
                                      [item.work_id]: {
                                        ...(prev[item.work_id] || {}),
                                        [c.id]: e.target.value as CriterionResult,
                                      },
                                    }))
                                  }
                                >
                                  <option value="">{t("customerDemo.selectEvaluation")}</option>
                                  <option value="PASS">{t("customerDemo.resultPass")}</option>
                                  <option value="FAIL">{t("customerDemo.resultFail")}</option>
                                  <option value="INSUFFICIENT_EVIDENCE">{t("customerDemo.resultInsufficientEvidence")}</option>
                                </select>
                              </div>
                              <p className="mw-criterion-desc">{c.description}</p>
                            </div>
                          ))}
                        </div>
                        <div className="mw-procedure-disclaimer">{proc.disclaimer}</div>
                      </div>
                    )}

                    {proc && (
                      <div className="mw-form-group">
                        <label htmlFor={`assess-result-${item.work_id}`}>
                          {t("customerDemo.reviewDecisionLabel") || "Assessment Decision"}
                        </label>
                        <select
                          id={`assess-result-${item.work_id}`}
                          aria-label="Assessment Decision"
                          value={selectedResult[item.work_id] || ""}
                          disabled={isMutationDisabled}
                          onChange={(e) =>
                            setSelectedResult((prev) => ({
                              ...prev,
                              [item.work_id]: e.target.value as AssessmentResult,
                            }))
                          }
                        >
                          <option value="">-- Select result --</option>
                          <option value="PASS">{t("customerDemo.resultPass")}</option>
                          <option value="PARTIAL">{t("customerDemo.resultPartial")}</option>
                          <option value="FAIL">{t("customerDemo.resultFail")}</option>
                          <option value="INSUFFICIENT_EVIDENCE">{t("customerDemo.resultInsufficientEvidence")}</option>
                        </select>

                        {/* Selectable evidence checkboxes */}
                        {acceptedLinks.length > 0 && (
                          <div style={{ marginTop: "0.75rem" }}>
                            <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>Associated Evidence:</span>
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginTop: "0.25rem" }}>
                              {acceptedLinks.map((lnk) => {
                                const now = selectedEvidence[item.work_id] ?? [];
                                const currentChecked = now.includes(lnk.id);
                                return (
                                  <label key={lnk.id} style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <input
                                      type="checkbox"
                                      aria-label={`Evidence ${lnk.filename || lnk.id}`}
                                      checked={currentChecked}
                                      disabled={isMutationDisabled}
                                      onChange={(e) => {
                                        const cur = selectedEvidence[item.work_id] ?? [];
                                        const next = e.target.checked
                                          ? [...cur, lnk.id]
                                          : cur.filter((id) => id !== lnk.id);
                                        setSelectedEvidence((prev) => ({ ...prev, [item.work_id]: next }));
                                      }}
                                    />
                                    {lnk.filename || lnk.id} (rev {lnk.revision_number})
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        <label htmlFor={`assess-rat-${item.work_id}`} style={{ marginTop: "0.75rem" }}>
                          {t("customerDemo.rationaleLabel") || "Assessment Rationale"}
                        </label>
                        <textarea
                          id={`assess-rat-${item.work_id}`}
                          aria-label="Assessment Rationale"
                          className="mw-textarea"
                          rows={3}
                          placeholder={t("customerDemo.rationaleInputPlaceholder")}
                          value={rationale[item.work_id] || ""}
                          disabled={isMutationDisabled}
                          onChange={(e) => setRationale((r) => ({ ...r, [item.work_id]: e.target.value }))}
                        />

                        {/* Finding creation subform for negative results */}
                        {(selectedResult[item.work_id] === "FAIL" || selectedResult[item.work_id] === "PARTIAL") && (
                          <div className="mw-finding-subform">
                            <label className="mw-checkbox-label">
                              <input
                                type="checkbox"
                                aria-label="Record Finding"
                                checked={hasFinding[item.work_id] || false}
                                disabled={isMutationDisabled}
                                onChange={(e) =>
                                  setHasFinding((prev) => ({ ...prev, [item.work_id]: e.target.checked }))
                                }
                              />
                              {t("customerDemo.createFindingCheckbox")}
                            </label>

                            {hasFinding[item.work_id] && (
                              <div className="mw-finding-fields">
                                <label htmlFor={`finding-sev-${item.work_id}`}>
                                  {t("customerDemo.findingSeverity")}
                                </label>
                                <select
                                  id={`finding-sev-${item.work_id}`}
                                  aria-label={t("customerDemo.findingSeverity")}
                                  value={findingSeverity[item.work_id] || ""}
                                  disabled={isMutationDisabled}
                                  onChange={(e) =>
                                    setFindingSeverity((prev) => ({
                                      ...prev,
                                      [item.work_id]: e.target.value as FindingSeverity,
                                    }))
                                  }
                                >
                                  <option value="">{t("customerDemo.selectSeverity")}</option>
                                  <option value="LOW">{t("customerDemo.severityLow")}</option>
                                  <option value="MEDIUM">{t("customerDemo.severityMedium")}</option>
                                  <option value="HIGH">{t("customerDemo.severityHigh")}</option>
                                  <option value="CRITICAL">{t("customerDemo.severityCritical")}</option>
                                </select>

                                <label htmlFor={`finding-owner-${item.work_id}`}>
                                  {t("customerDemo.findingOwner")}
                                </label>
                                <select
                                  id={`finding-owner-${item.work_id}`}
                                  value={findingOwner[item.work_id] || ""}
                                  disabled={isMutationDisabled}
                                  onChange={(e) =>
                                    setFindingOwner((prev) => ({ ...prev, [item.work_id]: e.target.value }))
                                  }
                                >
                                  <option value="">-- Unassigned --</option>
                                  {owners.map((o) => (
                                    <option key={o.user_id} value={o.user_id}>
                                      {o.display_name}
                                    </option>
                                  ))}
                                </select>

                                <label htmlFor={`finding-due-${item.work_id}`}>
                                  {t("customerDemo.findingDueDate")}
                                </label>
                                <input
                                  type="date"
                                  id={`finding-due-${item.work_id}`}
                                  value={findingDueDate[item.work_id] || ""}
                                  disabled={isMutationDisabled}
                                  onChange={(e) =>
                                    setFindingDueDate((prev) => ({ ...prev, [item.work_id]: e.target.value }))
                                  }
                                />
                              </div>
                            )}
                          </div>
                        )}

                        <button
                          type="button"
                          className="mw-btn mw-btn-primary"
                          data-testid={`record-assessment-submit-${item.work_id}`}
                          disabled={
                            isMutationDisabled ||
                            submittingAssess[item.work_id] ||
                            !selectedResult[item.work_id] ||
                            !(rationale[item.work_id] || "").trim() ||
                            proc.criteria.some((c) => !criteriaState[item.work_id]?.[c.id])
                          }
                          onClick={() => void handleRecordAssessment(item)}
                        >
                          {submittingAssess[item.work_id]
                            ? t("customerDemo.recordingAssessment")
                            : t("customerDemo.recordAssessmentBtn")}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Tab 2: Findings & Remediation Management */}
                {currentTab === "findings" && (
                  <div className="mw-tab-content">
                    {item.findings.length === 0 ? (
                      <p className="mw-empty-text">{t("customerDemo.noFindingsYet")}</p>
                    ) : (
                      <div className="mw-findings-table-wrapper">
                        <table className="mw-findings-table">
                          <thead>
                            <tr>
                              <th>{t("customerDemo.findingSeverity")}</th>
                              <th>{t("customerDemo.findingStatus")}</th>
                              <th>{t("customerDemo.findingOwner")}</th>
                              <th>{t("customerDemo.findingDueDate")}</th>
                              <th>Ver</th>
                              <th>Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {item.findings.map((f) => (
                              <tr key={f.id} data-testid={`finding-row-${f.id}`}>
                                <td>
                                  <span className={`mw-severity-badge ${f.severity.toLowerCase()}`}>
                                    {f.severity}
                                  </span>
                                </td>
                                <td>
                                  <span className={`mw-status-badge ${f.status.toLowerCase()}`}>
                                    {f.status}
                                  </span>
                                </td>
                                <td>
                                  {f.owner_display_name ||
                                    owners.find((o) => o.user_id === f.owner_user_id)?.display_name ||
                                    "Unassigned"}
                                </td>
                                <td>{f.due_date || "None"}</td>
                                <td>v{f.version}</td>
                                <td>
                                  {f.status !== "RESOLVED" && (
                                    <button
                                      type="button"
                                      className="mw-btn-sm"
                                      data-testid={`edit-finding-btn-${f.id}`}
                                      disabled={isMutationDisabled}
                                      onClick={() => {
                                        setEditingFindingId(f.id);
                                        setRemediationStatus(f.status === "RESOLVED" ? "IN_REMEDIATION" : f.status);
                                        setRemediationSeverity(f.severity);
                                        setRemediationOwner(f.owner_user_id || "");
                                        setRemediationDueDate(f.due_date || "");
                                        setRemediationNote("");
                                      }}
                                    >
                                      {t("customerDemo.updateFindingBtn")}
                                    </button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {/* Inline Remediation Update Dialog */}
                    {editingFindingId && (
                      <div className="mw-remediation-form" data-testid="remediation-form">
                        <h4>{t("customerDemo.updateFindingBtn")}</h4>
                        <div className="mw-form-group">
                          <label htmlFor="remediation-status">{t("customerDemo.findingStatus")}</label>
                          <select
                            id="remediation-status"
                            value={remediationStatus}
                            disabled={isMutationDisabled}
                            onChange={(e) =>
                              setRemediationStatus(e.target.value as "OPEN" | "IN_REMEDIATION")
                            }
                          >
                            <option value="OPEN">{t("portal.openStatus")}</option>
                            <option value="IN_REMEDIATION">IN_REMEDIATION</option>
                          </select>

                          <label htmlFor="remediation-severity">{t("customerDemo.findingSeverity")}</label>
                          <select
                            id="remediation-severity"
                            value={remediationSeverity}
                            disabled={isMutationDisabled}
                            onChange={(e) => setRemediationSeverity(e.target.value as FindingSeverity)}
                          >
                            <option value="LOW">{t("customerDemo.severityLow")}</option>
                            <option value="MEDIUM">{t("customerDemo.severityMedium")}</option>
                            <option value="HIGH">{t("customerDemo.severityHigh")}</option>
                            <option value="CRITICAL">{t("customerDemo.severityCritical")}</option>
                          </select>

                          <label htmlFor="remediation-owner">{t("customerDemo.findingOwner")}</label>
                          <select
                            id="remediation-owner"
                            value={remediationOwner}
                            disabled={isMutationDisabled}
                            onChange={(e) => setRemediationOwner(e.target.value)}
                          >
                            <option value="">-- Unassigned --</option>
                            {owners.map((o) => (
                              <option key={o.user_id} value={o.user_id}>
                                {o.display_name}
                              </option>
                            ))}
                          </select>

                          <label htmlFor="remediation-due">{t("customerDemo.findingDueDate")}</label>
                          <input
                            type="date"
                            id="remediation-due"
                            value={remediationDueDate}
                            disabled={isMutationDisabled}
                            onChange={(e) => setRemediationDueDate(e.target.value)}
                          />

                          <label htmlFor="remediation-note">{t("customerDemo.findingRemediationNote")}</label>
                          <textarea
                            id="remediation-note"
                            className="mw-textarea"
                            rows={3}
                            placeholder={t("customerDemo.remediationNotePlaceholder")}
                            value={remediationNote}
                            disabled={isMutationDisabled}
                            onChange={(e) => setRemediationNote(e.target.value)}
                          />

                          <div className="mw-form-actions">
                            <button
                              type="button"
                              className="mw-btn mw-btn-primary"
                              data-testid="save-remediation-btn"
                              disabled={isMutationDisabled || submittingRemediation || !remediationNote.trim()}
                              onClick={() => {
                                const target = item.findings.find((f) => f.id === editingFindingId);
                                if (target) {
                                  void handleUpdateFinding(item, target);
                                }
                              }}
                            >
                              {submittingRemediation ? "Saving..." : t("customerDemo.saveRemediationBtn")}
                            </button>
                            <button
                              type="button"
                              className="mw-btn mw-btn-secondary"
                              onClick={() => setEditingFindingId(null)}
                            >{t("customerDemo.cancelBtn")}</button>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Tab 3: Retest Form */}
                {currentTab === "retest" && (
                  <div className="mw-tab-content">
                    {unresolvedFindings.length === 0 ? (
                      <p className="mw-empty-text">{t("portal.noUnresolvedFindings")}</p>
                    ) : (
                      <div className="mw-form-group">
                        <label htmlFor={`retest-finding-select-${item.work_id}`}>
                          {t("customerDemo.selectFindingToResolve")}
                        </label>
                        <select
                          id={`retest-finding-select-${item.work_id}`}
                          aria-label={t("customerDemo.selectFindingToResolve")}
                          value={retestFindingId[item.work_id] || ""}
                          disabled={isMutationDisabled}
                          onChange={(e) =>
                            setRetestFindingId((prev) => ({ ...prev, [item.work_id]: e.target.value }))
                          }
                        >
                          <option value="">-- Select finding to retest --</option>
                          {unresolvedFindings.map((f) => (
                            <option key={f.id} value={f.id}>
                              Finding {f.id.slice(0, 8)} ({f.severity} - {f.status}) v{f.version}
                            </option>
                          ))}
                        </select>

                        {!proc ? (
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary"
                            onClick={() => void loadProcedureForItem(item.work_id)}
                            disabled={loadingProc[item.work_id]}
                          >
                            {loadingProc[item.work_id] ? "Loading Procedure..." : t("customerDemo.assessmentProcedureTitle")}
                          </button>
                        ) : (
                          <div className="mw-procedure-box" style={{ marginTop: "1rem" }}>
                            <h4 className="mw-procedure-title">{t("portal.retestCriteria")}</h4>
                            <div className="mw-criteria-list">
                              {proc.criteria.map((c) => (
                                <div key={c.id} className="mw-criterion-row">
                                  <div className="mw-criterion-header">
                                    <span className="mw-criterion-name">{c.title}</span>
                                    <select
                                      aria-label={`Retest criterion ${c.title}`}
                                      value={retestCriteriaState[item.work_id]?.[c.id] || ""}
                                      disabled={isMutationDisabled}
                                      onChange={(e) =>
                                        setRetestCriteriaState((prev) => ({
                                          ...prev,
                                          [item.work_id]: {
                                            ...(prev[item.work_id] || {}),
                                            [c.id]: e.target.value as CriterionResult,
                                          },
                                        }))
                                      }
                                    >
                                      <option value="">{t("customerDemo.selectEvaluation")}</option>
                                      <option value="PASS">{t("customerDemo.resultPass")}</option>
                                      <option value="FAIL">{t("customerDemo.resultFail")}</option>
                                      <option value="INSUFFICIENT_EVIDENCE">{t("customerDemo.resultInsufficientEvidence")}</option>
                                    </select>
                                  </div>
                                  <p className="mw-criterion-desc">{c.description}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Selectable evidence checkboxes for Retest */}
                        {acceptedLinks.length > 0 && (
                          <div style={{ marginTop: "0.75rem" }}>
                            <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>{t("customerDemo.associatedEvidence")}:</span>
                            <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", marginTop: "0.25rem" }}>
                              {acceptedLinks.map((lnk) => {
                                const cur = retestSelectedEvidence[item.work_id] ?? [];
                                const currentChecked = cur.includes(lnk.id);
                                return (
                                  <label key={lnk.id} style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                    <input
                                      type="checkbox"
                                      aria-label={`Retest evidence ${lnk.filename || lnk.id}`}
                                      checked={currentChecked}
                                      disabled={isMutationDisabled}
                                      onChange={(e) => {
                                        const now = retestSelectedEvidence[item.work_id] ?? [];
                                        const next = e.target.checked
                                          ? [...now, lnk.id]
                                          : now.filter((id) => id !== lnk.id);
                                        setRetestSelectedEvidence((prev) => ({ ...prev, [item.work_id]: next }));
                                      }}
                                    />
                                    {lnk.filename || lnk.id} (rev {lnk.revision_number})
                                  </label>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        <label htmlFor={`retest-res-${item.work_id}`} style={{ marginTop: "0.75rem" }}>
                          {t("portal.retestOutcome")}
                        </label>
                        <select
                          id={`retest-res-${item.work_id}`}
                          aria-label={t("portal.retestOutcome")}
                          value={retestResult[item.work_id] || ""}
                          disabled={isMutationDisabled}
                          onChange={(e) =>
                            setRetestResult((prev) => ({
                              ...prev,
                              [item.work_id]: e.target.value as AssessmentResult,
                            }))
                          }
                        >
                          <option value="">-- Select retest outcome --</option>
                          <option value="PASS">{t("customerDemo.resultPass")} (Resolves Finding)</option>
                          <option value="PARTIAL">{t("customerDemo.resultPartial")}</option>
                          <option value="FAIL">{t("customerDemo.resultFail")}</option>
                          <option value="INSUFFICIENT_EVIDENCE">{t("customerDemo.resultInsufficientEvidence")}</option>
                        </select>

                        <label htmlFor={`retest-rat-${item.work_id}`} style={{ marginTop: "0.75rem" }}>
                          {t("portal.retestRationale")}
                        </label>
                        <textarea
                          id={`retest-rat-${item.work_id}`}
                          aria-label={t("portal.retestRationale")}
                          className="mw-textarea"
                          rows={3}
                          placeholder={t("customerDemo.retestRationalePlaceholder")}
                          value={retestRationale[item.work_id] || ""}
                          disabled={isMutationDisabled}
                          onChange={(e) =>
                            setRetestRationale((r) => ({ ...r, [item.work_id]: e.target.value }))
                          }
                        />

                        <button
                          type="button"
                          className="mw-btn mw-btn-primary"
                          data-testid={`record-retest-submit-${item.work_id}`}
                          disabled={
                            isMutationDisabled ||
                            submittingRetest[item.work_id] ||
                            !retestFindingId[item.work_id] ||
                            !retestResult[item.work_id] ||
                            !(retestRationale[item.work_id] || "").trim() ||
                            !proc ||
                            proc.criteria.some((c) => !retestCriteriaState[item.work_id]?.[c.id])
                          }
                          onClick={() => void handleRecordRetest(item)}
                        >
                          {submittingRetest[item.work_id] ? "Recording..." : t("customerDemo.retestBtn")}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Collapsible History Drawer */}
                {historyOpen[item.work_id] && (
                  <div className="mw-history-drawer" data-testid={`history-drawer-${item.work_id}`}>
                    <h4 className="mw-history-title">{t("customerDemo.historyTitle")}</h4>
                    {loadingHist[item.work_id] ? (
                      <p className="mw-loading-text">{t("portal.loadingHistory")}</p>
                    ) : !histories[item.work_id] || histories[item.work_id].length === 0 ? (
                      <p className="mw-empty-text">{t("customerDemo.noHistoryEvents")}</p>
                    ) : (
                      <ul className="mw-history-timeline">
                        {histories[item.work_id].map((evt) => (
                          <li key={evt.event_id} className="mw-history-event-item">
                            <div className="mw-event-meta">
                              <span className="mw-event-type">{evt.event_type}</span>
                              {evt.result && (
                                <span className={`mw-event-result ${evt.result.toLowerCase()}`}>
                                  {evt.result}
                                </span>
                              )}
                              <span className="mw-event-date">
                                {new Date(evt.created_at).toLocaleString()}
                              </span>
                            </div>
                            <div className="mw-event-details">
                              <span>Work v{evt.observed_work_version}</span> •{" "}
                              <span>Rev {evt.revision}</span>
                              {typeof evt.details?.rationale === "string" && (
                                <p className="mw-event-rationale">"{evt.details.rationale}"</p>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};
