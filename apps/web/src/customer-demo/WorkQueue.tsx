import React, { FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { fetchAssessmentWorkList } from "./assessment-api";
import { AssessmentWorkItem, AssessmentWorkListResponse } from "./assessment-types";
import { ForbiddenError, UnauthorizedError } from "./api";
import { fetchControlWorkList } from "./control-evidence-api";
import { ControlWorkItem, WorkListResponse } from "./control-evidence-types";
import { ControlTraceabilityPanel } from "./ControlTraceabilityPanel";
import {
  buildWorkQueueItems,
  filterAndSortWorkQueue,
  getWorkQueueBucketCounts,
  WorkQueueBucket,
  WorkQueueFilters,
} from "./work-queue";
import "./modern-workspace.css";

export interface WorkQueueProps {
  tenantId: string;
  token: string;
  adoptionId?: string | null;
  selectionRevision?: number;
  answerRevision?: number;
  isActiveView?: boolean;
  refreshEpoch?: number;
  onNavigateToControl?: (workId: string) => void;
  onNavigateToEvidence?: (workId: string) => void;
  onNavigateToAssessment?: (workId: string, findingId?: string) => void;
  onNavigateToFrameworks?: () => void;
  onSessionExpired?: () => void;
  asOfDateStr?: string;
}

export const WorkQueue: FC<WorkQueueProps> = ({
  tenantId,
  token,
  adoptionId,
  selectionRevision,
  answerRevision,
  isActiveView,
  refreshEpoch,
  onNavigateToControl,
  onNavigateToEvidence,
  onNavigateToAssessment,
  onNavigateToFrameworks,
  onSessionExpired,
  asOfDateStr,
}) => {
  const { t } = useTranslation();

  void selectionRevision;

  void answerRevision;

  // Primary data states
  const [controls, setControls] = useState<ControlWorkItem[]>([]);
  const [assessments, setAssessments] = useState<AssessmentWorkItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [controlsError, setControlsError] = useState<string | null>(null);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [isAssessmentDenied, setIsAssessmentDenied] = useState<boolean>(false);
  const [isAssessmentUnavailable, setIsAssessmentUnavailable] = useState<boolean>(false);
  const [isStaleRefresh, setIsStaleRefresh] = useState<boolean>(false);
  const [selectedTraceWorkId, setSelectedTraceWorkId] = useState<string | null>(null);

  // Filters state
  const [activeBucket, setActiveBucket] = useState<WorkQueueBucket>("all");
  const [ownerFilter, setOwnerFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Refs for race fencing
  const sessionGenRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const prevIsActiveViewRef = useRef<boolean>(Boolean(isActiveView));
  const prevRefreshEpochRef = useRef<number | undefined>(refreshEpoch);
  const controlsRef = useRef<ControlWorkItem[]>(controls);
  useEffect(() => {
    controlsRef.current = controls;
  }, [controls]);

  const tenantIdRef = useRef(tenantId);
  useEffect(() => {
    tenantIdRef.current = tenantId;
  }, [tenantId]);

  const tokenRef = useRef(token);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  const handleUnauthorized = useCallback(() => {
    setControls([]);
    setAssessments([]);
    onSessionExpiredRef.current?.();
  }, []);

  const loadData = useCallback(
    async (isManualRefresh = false) => {
      if (!adoptionId) {
        setControls([]);
        setAssessments([]);
        setIsLoading(false);
        setIsRefreshing(false);
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const ac = new AbortController();
      abortControllerRef.current = ac;
      const currentSessionGen = ++sessionGenRef.current;

      if (isManualRefresh) {
        setIsRefreshing(true);
      } else {
        setIsLoading(true);
      }
      setControlsError(null);
      setAssessmentError(null);
      setIsAssessmentDenied(false);
      setIsStaleRefresh(false);

      const targetTenantId = tenantId;
      const targetToken = token;
      const targetAdoptionId = adoptionId;
      const targetSelectionRevision = selectionRevision;
      const targetAnswerRevision = answerRevision;

      let controlsFetchFailed = false;
      let assessmentsFetchFailed = false;

      const pControls = fetchControlWorkList(
        targetTenantId,
        targetToken,
        targetAdoptionId && targetAdoptionId !== "current" ? targetAdoptionId : undefined,
        ac.signal
      )
        .then((res: WorkListResponse) => {
          if (sessionGenRef.current !== currentSessionGen || ac.signal.aborted) return null;
          if (!res || typeof res !== "object" || !Array.isArray(res.items)) {
            throw new Error("Invalid controls response format");
          }
          if (!res.tenant_id || res.tenant_id !== targetTenantId) {
            throw new Error("Tenant context mismatch in controls response");
          }
          if (targetAdoptionId && targetAdoptionId !== "current") {
            if (res.adoption_id !== targetAdoptionId) {
              throw new Error("Adoption context mismatch in controls response");
            }
          }
          if (typeof res.selection_revision !== "number" || !Number.isInteger(res.selection_revision) || res.selection_revision < 0) {
            throw new Error("Invalid or missing selection_revision in controls response");
          }
          if (typeof res.answer_revision !== "number" || !Number.isInteger(res.answer_revision) || res.answer_revision < 0) {
            throw new Error("Invalid or missing answer_revision in controls response");
          }
          if (targetSelectionRevision !== undefined && res.selection_revision !== targetSelectionRevision) {
            throw new Error("Selection revision mismatch in controls response");
          }
          if (targetAnswerRevision !== undefined && res.answer_revision !== targetAnswerRevision) {
            throw new Error("Answer revision mismatch in controls response");
          }
          return res;
        })
        .catch((err: unknown) => {
          if (sessionGenRef.current !== currentSessionGen || ac.signal.aborted) return null;
          controlsFetchFailed = true;
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return null;
          }
          if (err instanceof ForbiddenError) {
            setControlsError(t("portal.controlsDeniedNotice") || "Access forbidden to control work list.");
          } else {
            setControlsError(err instanceof Error ? err.message : (t("portal.controlsErrorBanner") || "Failed to load controls"));
          }
          return null;
        });

      const pAssessments = fetchAssessmentWorkList(targetTenantId, targetToken, ac.signal)
        .then((res: AssessmentWorkListResponse) => {
          if (sessionGenRef.current !== currentSessionGen || ac.signal.aborted) return null;
          if (!res || typeof res !== "object" || !Array.isArray(res.items)) {
            throw new Error("Invalid assessments response format");
          }
          if (!res.tenant_id || res.tenant_id !== targetTenantId) {
            throw new Error("Tenant context mismatch in assessments response");
          }
          if (targetAdoptionId && targetAdoptionId !== "current") {
            if (res.adoption_id !== targetAdoptionId) {
              throw new Error("Adoption context mismatch in assessments response");
            }
          }
          if (typeof res.selection_revision !== "number" || !Number.isInteger(res.selection_revision) || res.selection_revision < 0) {
            throw new Error("Invalid or missing selection_revision in assessments response");
          }
          if (typeof res.answer_revision !== "number" || !Number.isInteger(res.answer_revision) || res.answer_revision < 0) {
            throw new Error("Invalid or missing answer_revision in assessments response");
          }
          if (targetSelectionRevision !== undefined && res.selection_revision !== targetSelectionRevision) {
            throw new Error("Selection revision mismatch in assessments response");
          }
          if (targetAnswerRevision !== undefined && res.answer_revision !== targetAnswerRevision) {
            throw new Error("Answer revision mismatch in assessments response");
          }
          return res;
        })
        .catch((err: unknown) => {
          if (sessionGenRef.current !== currentSessionGen || ac.signal.aborted) return null;
          assessmentsFetchFailed = true;
          if (err instanceof UnauthorizedError) {
            handleUnauthorized();
            return null;
          }
          if (err instanceof ForbiddenError) {
            setIsAssessmentDenied(true);
            setAssessmentError(t("portal.assessmentDeniedNotice") || "Access restricted to assessment status (403 Forbidden). Displayed items reflect control tasks only.");
          } else {
            setAssessmentError(err instanceof Error ? err.message : (t("portal.assessmentErrorBanner") || "Failed to load assessments"));
          }
          return null;
        });

      const [ctrlRes, assessRes] = await Promise.all([pControls, pAssessments]);

      if (sessionGenRef.current === currentSessionGen && !ac.signal.aborted) {
        if (ctrlRes) {
          setControls(ctrlRes.items || []);
        } else if (controlsFetchFailed) {
          if (isManualRefresh && controlsRef.current.length > 0) {
            setIsStaleRefresh(true);
          } else {
            setControls([]);
          }
        }

        if (assessRes) {
          // Envelope compatibility check between pair:
          if (ctrlRes && ctrlRes.adoption_id && assessRes.adoption_id && ctrlRes.adoption_id !== assessRes.adoption_id) {
            setIsAssessmentUnavailable(true);
            setAssessmentError(t("portal.envelopeMismatchNotice") || "Incompatible adoption context between controls and assessments.");
            setAssessments([]);
          } else if (
            ctrlRes &&
            typeof ctrlRes.selection_revision === "number" &&
            typeof assessRes.selection_revision === "number" &&
            ctrlRes.selection_revision !== assessRes.selection_revision
          ) {
            setIsAssessmentUnavailable(true);
            setAssessmentError(t("portal.envelopeMismatchSelection") || "Incompatible selection revision between controls and assessments.");
            setAssessments([]);
          } else if (
            ctrlRes &&
            typeof ctrlRes.answer_revision === "number" &&
            typeof assessRes.answer_revision === "number" &&
            ctrlRes.answer_revision !== assessRes.answer_revision
          ) {
            setIsAssessmentUnavailable(true);
            setAssessmentError(t("portal.envelopeMismatchAnswer") || "Incompatible answer revision between controls and assessments.");
            setAssessments([]);
          } else {
            setAssessments(assessRes.items || []);
            setIsAssessmentUnavailable(false);
          }
        } else if (assessmentsFetchFailed) {
          setIsAssessmentUnavailable(true);
          setAssessments([]);
        }

        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [adoptionId, tenantId, token, selectionRevision, answerRevision, handleUnauthorized, t]
  );

  const loadDataRef = useRef(loadData);
  useEffect(() => {
    loadDataRef.current = loadData;
  }, [loadData]);

  const prevContextRef = useRef({ tenantId, adoptionId, selectionRevision, answerRevision });
  useEffect(() => {
    const ctx = prevContextRef.current;
    if (
      ctx.tenantId !== tenantId ||
      ctx.adoptionId !== adoptionId ||
      ctx.selectionRevision !== selectionRevision ||
      ctx.answerRevision !== answerRevision
    ) {
      prevContextRef.current = { tenantId, adoptionId, selectionRevision, answerRevision };
      setControls([]);
      setAssessments([]);
      setControlsError(null);
      setAssessmentError(null);
      setIsAssessmentUnavailable(false);
      setIsAssessmentDenied(false);
      setIsStaleRefresh(false);
    }
  }, [tenantId, adoptionId, selectionRevision, answerRevision]);

  useEffect(() => {
    let isCancelled = false;
    void Promise.resolve().then(() => {
      if (!isCancelled) {
        void loadDataRef.current(false);
      }
    });
    return () => {
      isCancelled = true;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [adoptionId, tenantId, token, selectionRevision, answerRevision]);

  useEffect(() => {
    const becameActive = Boolean(isActiveView && !prevIsActiveViewRef.current);
    const epochBumped = Boolean(refreshEpoch !== undefined && refreshEpoch !== prevRefreshEpochRef.current);
    prevIsActiveViewRef.current = Boolean(isActiveView);
    prevRefreshEpochRef.current = refreshEpoch;

    if (becameActive || (epochBumped && refreshEpoch! > 0 && isActiveView)) {
      void loadDataRef.current(false);
    }
  }, [isActiveView, refreshEpoch]);

  // Transform raw items using pure selector
  const allQueueItems = useMemo(() => {
    return buildWorkQueueItems(controls, assessments, asOfDateStr);
  }, [controls, assessments, asOfDateStr]);

  const isAssessmentAvailable = !isAssessmentUnavailable && !isAssessmentDenied && !assessmentError;
  const isControlsAvailable = !controlsError;

  // Bucket counts
  const bucketCounts = useMemo(() => {
    return getWorkQueueBucketCounts(
      allQueueItems,
      controls.length,
      isAssessmentAvailable,
      isControlsAvailable
    );
  }, [allQueueItems, controls.length, isAssessmentAvailable, isControlsAvailable]);

  // Distinct owners for filtering
  const distinctOwners = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of allQueueItems) {
      if (item.ownerUserId) {
        map.set(item.ownerUserId, item.ownerDisplayName || item.ownerUserId);
      }
    }
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [allQueueItems]);

  // Filtered & sorted queue items
  const filteredItems = useMemo(() => {
    const filters: WorkQueueFilters = {
      bucket: activeBucket,
      owner: ownerFilter,
      search: searchQuery,
    };
    return filterAndSortWorkQueue(allQueueItems, filters, asOfDateStr);
  }, [allQueueItems, activeBucket, ownerFilter, searchQuery, asOfDateStr]);

  // Active control for traceability inspection
  const selectedControl = useMemo(() => {
    if (!selectedTraceWorkId) return null;
    return controls.find((c) => c.id === selectedTraceWorkId) || null;
  }, [selectedTraceWorkId, controls]);

  const selectedAssessment = useMemo(() => {
    if (!selectedTraceWorkId) return null;
    return assessments.find((a) => a.work_id === selectedTraceWorkId) || null;
  }, [selectedTraceWorkId, assessments]);

  // State 1: No Framework Pack Adopted
  if (!adoptionId) {
    return (
      <div className="mw-workspace-root" data-testid="work-queue-no-adoption">
        <header className="mw-section-header">
          <h1 className="mw-section-title" data-testid="work-queue-title">
            {t("portal.workQueueTitle") || "Daily Work Queue"}
          </h1>
          <p className="mw-section-subtitle">
            {t("portal.workQueueSubtitle") || "Operational queue of prioritized controls, evidence tasks, and findings."}
          </p>
        </header>
        <div
          role="status"
          className="mw-card"
          style={{ padding: "2rem", textAlign: "center", marginTop: "1rem" }}
          data-testid="no-adoption-prompt"
        >
          <h2 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>
            {t("portal.noFrameworkAdopted") || "No Framework Pack Adopted"}
          </h2>
          <p style={{ color: "#666", marginBottom: "1rem" }}>
            {t("portal.noFrameworkAdoptedDesc") ||
              "Please adopt a framework pack in the Frameworks catalog before managing daily compliance tasks and evidence."}
          </p>
          {onNavigateToFrameworks && (
            <button
              type="button"
              className="mw-btn mw-btn-primary"
              data-testid="nav-to-frameworks-btn"
              onClick={onNavigateToFrameworks}
            >
              {t("portal.goToFrameworksBtn") || "Go to Frameworks"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-workspace-root" data-testid="work-queue-workspace">
      {/* Header */}
      <header
        className="mw-section-header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h1 className="mw-section-title" data-testid="work-queue-title">
            {t("portal.workQueueTitle") || "Daily Work Queue"}
          </h1>
          <p className="mw-section-subtitle">
            {t("portal.workQueueSubtitle") || "Operational queue of prioritized controls, evidence tasks, and findings."}
          </p>
        </div>
        <button
          type="button"
          className="mw-btn mw-btn-secondary"
          data-testid="refresh-work-queue-btn"
          onClick={() => void loadData(true)}
          disabled={isRefreshing || isLoading}
        >
          {isRefreshing ? t("portal.refreshingQueueBtn") || "Refreshing Queue..." : t("portal.refreshQueueBtn") || "Refresh Queue"}
        </button>
      </header>

      {/* Error / Partial Warnings */}
      {controlsError && (
        <div
          role="alert"
          className="mw-notice-banner"
          data-testid="controls-error-banner"
          style={{ borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
            <span>{controlsError}</span>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-controls-btn"
              onClick={() => void loadData(true)}
              style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
            >
              {t("portal.retryControlsBtn") || "Retry Controls"}
            </button>
          </div>
        </div>
      )}

      {isAssessmentDenied && (
        <div
          role="status"
          data-testid="partial-results-notice"
          className="mw-notice-banner"
          style={{ borderColor: "#ff9500", background: "#fffdf5", color: "#856404", marginBottom: "1rem" }}
        >
          <strong>Partial Results Notice: </strong>
          {assessmentError || "Assessment data is restricted (403 Forbidden). Displayed items reflect control tasks only."}
        </div>
      )}

      {assessmentError && !isAssessmentDenied && (
        <div
          role="alert"
          className="mw-notice-banner"
          data-testid="assessment-error-banner"
          style={{ borderColor: "#ff9500", background: "#fffdf5", color: "#856404", marginBottom: "1rem" }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
            <span>{assessmentError}</span>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-assessments-btn"
              onClick={() => void loadData(true)}
              style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
            >
              {t("portal.retryAssessmentsBtn") || "Retry Assessments"}
            </button>
          </div>
        </div>
      )}

      {isStaleRefresh && (
        <div
          role="status"
          className="mw-notice-banner"
          data-testid="stale-refresh-warning"
          style={{ borderColor: "#ff9500", background: "#fffdf5", color: "#856404", marginBottom: "1rem" }}
        >
          <strong>{t("portal.staleRefreshWarning") || "Refresh failed. Showing previously loaded work items which may be out of date."}</strong>
        </div>
      )}

      {/* Selected Control Traceability Panel Modal / Inline */}
      {selectedControl && (
        <ControlTraceabilityPanel
          control={selectedControl}
          assessment={selectedAssessment}
          onNavigateToEvidence={onNavigateToEvidence}
          onNavigateToAssessment={onNavigateToAssessment}
          onClose={() => setSelectedTraceWorkId(null)}
        />
      )}

      {/* Operational Bucket Pills Header */}
      <section aria-label="Operational Filters" style={{ marginBottom: "1.25rem" }}>
        <div
          data-testid="work-queue-bucket-bar"
          style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}
        >
          <button
            type="button"
            className={`mw-btn ${activeBucket === "all" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-all-btn"
            onClick={() => setActiveBucket("all")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            All Work ({!isControlsAvailable ? "Unavailable" : !isAssessmentAvailable ? `${bucketCounts.totalItems} (Partial)` : bucketCounts.totalItems})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "overdue" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-overdue-btn"
            onClick={() => setActiveBucket("overdue")}
            style={{
              fontSize: "0.8rem",
              padding: "0.35rem 0.75rem",
              borderColor: bucketCounts.overdue > 0 ? "#dc3545" : undefined,
              color: activeBucket === "overdue" ? "#fff" : bucketCounts.overdue > 0 ? "#dc3545" : undefined,
            }}
          >
            Overdue ({bucketCounts.overdue})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "due_today" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-due-today-btn"
            onClick={() => setActiveBucket("due_today")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            Due Today ({bucketCounts.dueToday})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "unassigned" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-unassigned-btn"
            onClick={() => setActiveBucket("unassigned")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            Unassigned ({bucketCounts.unassigned})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "evidence_attention" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-evidence-btn"
            onClick={() => setActiveBucket("evidence_attention")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            Evidence Attention ({bucketCounts.evidenceAttention})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "assessment_needed" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-assessment-btn"
            onClick={() => setActiveBucket("assessment_needed")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            Assessment Needed ({bucketCounts.assessmentNeeded !== null ? bucketCounts.assessmentNeeded : "Unknown"})
          </button>
          <button
            type="button"
            className={`mw-btn ${activeBucket === "open_findings" ? "mw-btn-primary" : "mw-btn-secondary"}`}
            data-testid="bucket-findings-btn"
            onClick={() => setActiveBucket("open_findings")}
            style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
          >
            Open Findings ({bucketCounts.openFindings !== null ? bucketCounts.openFindings : "Unknown"})
          </button>
        </div>
      </section>

      {/* Filter & Search Bar */}
      <div
        className="mw-card"
        style={{
          padding: "0.75rem",
          marginBottom: "1.25rem",
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          alignItems: "center",
        }}
      >
        <div style={{ flex: "1 1 240px" }}>
          <label htmlFor="queue-search-input" style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
            Search Controls & Findings
          </label>
          <input
            id="queue-search-input"
            data-testid="queue-search-input"
            type="text"
            className="mw-input"
            placeholder="Search by title, ID, owner, severity..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div style={{ minWidth: "180px" }}>
          <label htmlFor="queue-owner-select" style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.2rem" }}>
            Filter by Owner
          </label>
          <select
            id="queue-owner-select"
            data-testid="queue-owner-select"
            className="mw-input"
            value={ownerFilter}
            onChange={(e) => setOwnerFilter(e.target.value)}
          >
            <option value="all">All Owners</option>
            <option value="unassigned">Unassigned Only</option>
            {distinctOwners.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>

        {(ownerFilter !== "all" || searchQuery || activeBucket !== "all") && (
          <div style={{ alignSelf: "flex-end", marginBottom: "0.2rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="clear-filters-btn"
              onClick={() => {
                setOwnerFilter("all");
                setSearchQuery("");
                setActiveBucket("all");
              }}
              style={{ fontSize: "0.8rem", padding: "0.35rem 0.6rem" }}
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* Queue Items List */}
      <section className="mw-card" data-testid="queue-items-section" aria-labelledby="queue-list-heading">
        <div className="mw-card-header">
          <h2 id="queue-list-heading" className="mw-card-title" style={{ fontSize: "1rem" }}>
            Prioritized Work Items ({filteredItems.length} of {allQueueItems.length})
          </h2>
          <p className="mw-card-subtitle" style={{ fontSize: "0.8rem" }}>
            Distinct controls: {bucketCounts.distinctControls} | Operational sorting: overdue first, then upcoming dates.
          </p>
        </div>

        <div className="mw-card-body">
          {isLoading ? (
            <div role="status" className="mw-loading-indicator" data-testid="queue-loading">
              Loading work queue...
            </div>
          ) : !isStaleRefresh && controlsError ? (
            <div
              role="status"
              data-testid="queue-controls-unavailable"
              style={{ padding: "2rem", textAlign: "center", color: "#666" }}
            >
              <p>{controlsError}</p>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="retry-controls-btn"
                onClick={() => void loadData(true)}
                style={{ marginTop: "0.5rem" }}
              >
                {t("portal.retryControlsBtn") || "Retry Controls"}
              </button>
            </div>
          ) : (activeBucket === "open_findings" || activeBucket === "assessment_needed") && !isAssessmentAvailable ? (
            <div
              role="status"
              data-testid="queue-assessment-unavailable"
              style={{ padding: "2rem", textAlign: "center", color: "#666" }}
            >
              <p>{assessmentError || "Assessment and finding status is currently unavailable."}</p>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="retry-assessments-btn"
                onClick={() => void loadData(true)}
                style={{ marginTop: "0.5rem" }}
              >
                {t("portal.retryAssessmentsBtn") || "Retry Assessments"}
              </button>
            </div>
          ) : filteredItems.length === 0 ? (
            <div
              role="status"
              data-testid="queue-empty-state"
              style={{ padding: "2rem", textAlign: "center", color: "#666" }}
            >
              {allQueueItems.length === 0 ? (
                <p>No work items found in this framework adoption.</p>
              ) : (
                <p>No work items match the current filter criteria.</p>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {filteredItems.map((item) => (
                <div
                  key={item.id}
                  data-testid={`queue-row-${item.id}`}
                  style={{
                    padding: "0.75rem",
                    borderRadius: "6px",
                    border: item.isOverdue
                      ? "1px solid #dc3545"
                      : item.isDueToday
                      ? "1px solid #ff9500"
                      : "1px solid var(--mw-border-color, #e0e0e0)",
                    background: item.isOverdue
                      ? "rgba(220, 53, 69, 0.02)"
                      : item.isDueToday
                      ? "rgba(255, 149, 0, 0.02)"
                      : "#ffffff",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.25rem" }}>
                        <span
                          style={{
                            fontSize: "0.7rem",
                            padding: "0.15rem 0.35rem",
                            borderRadius: "4px",
                            fontWeight: 700,
                            background: item.kind === "finding" ? "rgba(220, 53, 69, 0.1)" : "rgba(0, 102, 204, 0.1)",
                            color: item.kind === "finding" ? "#721c24" : "var(--mw-primary, #0066cc)",
                          }}
                        >
                          {item.kind.toUpperCase()}
                        </span>
                        <span style={{ fontSize: "0.8rem", fontWeight: 700 }}>{item.controlId}</span>
                        {item.findingSeverity && (
                          <span
                            style={{
                              fontSize: "0.7rem",
                              padding: "0.1rem 0.35rem",
                              borderRadius: "4px",
                              fontWeight: 700,
                              background: item.findingSeverity === "CRITICAL" || item.findingSeverity === "HIGH" ? "rgba(220, 53, 69, 0.15)" : "rgba(255, 149, 0, 0.15)",
                              color: item.findingSeverity === "CRITICAL" || item.findingSeverity === "HIGH" ? "#721c24" : "#856404",
                            }}
                          >
                            {item.findingSeverity}
                          </span>
                        )}
                      </div>
                      <h3 style={{ fontSize: "0.95rem", fontWeight: 600, margin: 0 }}>
                        {item.controlTitle}
                      </h3>
                    </div>

                    {/* Operational Badges */}
                    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                      {item.isOverdue && (
                        <span
                          data-testid={`badge-overdue-${item.id}`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: "4px", background: "#dc3545", color: "#fff", fontWeight: 700 }}
                        >
                          OVERDUE
                        </span>
                      )}
                      {item.isDueToday && (
                        <span
                          data-testid={`badge-due-today-${item.id}`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: "4px", background: "#ff9500", color: "#fff", fontWeight: 700 }}
                        >
                          DUE TODAY
                        </span>
                      )}
                      {item.evidenceAttention && (
                        <span
                          data-testid={`badge-evidence-${item.id}`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: "4px", background: "rgba(255, 149, 0, 0.15)", color: "#856404", fontWeight: 600 }}
                        >
                          Evidence Attention
                        </span>
                      )}
                      {item.assessmentNeeded && (
                        <span
                          data-testid={`badge-assessment-${item.id}`}
                          style={{ fontSize: "0.7rem", padding: "0.15rem 0.4rem", borderRadius: "4px", background: "rgba(0, 102, 204, 0.15)", color: "var(--mw-primary, #0066cc)", fontWeight: 600 }}
                        >
                          Assessment Needed
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Metadata Row & Shortcuts */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      flexWrap: "wrap",
                      gap: "0.5rem",
                      fontSize: "0.8rem",
                      borderTop: "1px solid rgba(0,0,0,0.04)",
                      paddingTop: "0.4rem",
                    }}
                  >
                    <div style={{ display: "flex", gap: "1rem", color: "#666" }}>
                      <span>
                        Owner: <strong>{item.ownerDisplayName || "Unassigned"}</strong>
                      </span>
                      <span>
                        Due Date: <strong>{item.dueDate || "None"}</strong>
                      </span>
                      <span>
                        Status: <strong data-testid={`status-${item.id}`}>{item.status}</strong>
                      </span>
                    </div>

                    <div style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid={`trace-btn-${item.id}`}
                        onClick={() => setSelectedTraceWorkId(item.workId)}
                        style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                      >
                        Traceability
                      </button>
                      {onNavigateToControl && (
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid={`control-btn-${item.id}`}
                          onClick={() => onNavigateToControl(item.workId)}
                          style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        >
                          Control
                        </button>
                      )}
                      {onNavigateToEvidence && (
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid={`evidence-btn-${item.id}`}
                          onClick={() => onNavigateToEvidence(item.workId)}
                          style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        >
                          Evidence
                        </button>
                      )}
                      {onNavigateToAssessment && (
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid={`assessment-btn-${item.id}`}
                          onClick={() => onNavigateToAssessment(item.workId, item.findingId)}
                          style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem" }}
                        >
                          Assessment
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
};
