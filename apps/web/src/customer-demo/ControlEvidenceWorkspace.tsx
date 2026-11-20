import React, { FC, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { en } from "../i18n/locales/en";
import { UnauthorizedError } from "./api";
import {
  createEvidence,
  createReuseLink,
  createReview,
  downloadPinnedFile,
  fetchControlWorkList,
  fetchOwnerDirectory,
  fetchWorkHistory,
  initializeControlWork,
  patchControlWork,
  ServiceUnavailableError,
  uploadEvidenceFile,
} from "./control-evidence-api";
import {
  ControlWorkItem,
  OwnerDirectoryItem,
  WorkEvent,
} from "./control-evidence-types";
import "./modern-workspace.css";

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

export interface ControlEvidenceWorkspaceProps {
  tenantId: string;
  token: string;
  adoptionId?: string;
  selectionRevision: number;
  answerRevision: number;
  hasUnsavedParentEdits: boolean;
  isAdoptionStale: boolean;
  userRole?: string;
  onSessionExpired?: () => void;
  onDataChange?: () => void;
  navTarget?: { workId: string; targetTab?: string; nonce: number; tenantId?: string; adoptionId?: string } | null;
}

export const ControlEvidenceWorkspace: FC<ControlEvidenceWorkspaceProps> = ({
  tenantId,
  token,
  adoptionId,
  selectionRevision,
  answerRevision,
  hasUnsavedParentEdits,
  isAdoptionStale,
  userRole,
  onSessionExpired,
  onDataChange,
  navTarget,
}) => {
  void userRole;
  const { t } = useSafeTranslation();

  // State
  const [resolvedAdoptionId, setResolvedAdoptionId] = useState<string | null>(adoptionId ?? null);
  const [workItems, setWorkItems] = useState<ControlWorkItem[]>([]);
  const [owners, setOwners] = useState<OwnerDirectoryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [initializing, setInitializing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [scannerUnavailable, setScannerUnavailable] = useState<boolean>(false);
  const [targetNotFoundWorkId, setTargetNotFoundWorkId] = useState<string | null>(null);
  const lastHandledNavNonceRef = useRef<number>(0);
  const loadedSuccessfullyRef = useRef<boolean>(false);

  // Form states per work item
  const [selectedOwners, setSelectedOwners] = useState<Record<string, string>>({});
  const [dueDates, setDueDates] = useState<Record<string, string>>({});
  const [savingAssignmentId, setSavingAssignmentId] = useState<string | null>(null);

  // Upload modal state
  const [uploadModalWorkId, setUploadModalWorkId] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileValidUntil, setFileValidUntil] = useState<string>("");
  const [uploadRationale, setUploadRationale] = useState<string>("");
  const [uploading, setUploading] = useState<boolean>(false);

  // Reuse modal state
  const [reuseModalWorkId, setReuseModalWorkId] = useState<string | null>(null);
  const [selectedReuseTarget, setSelectedReuseTarget] = useState<string>("");
  const [reuseRationale, setReuseRationale] = useState<string>("");
  const [reusing, setReusing] = useState<boolean>(false);

  // Review modal state
  const [reviewModalLink, setReviewModalLink] = useState<{ workId: string; linkId: string; currentWorkVer: number } | null>(null);
  const [reviewDecision, setReviewDecision] = useState<"ACCEPTED" | "REJECTED">("ACCEPTED");
  const [reviewRationale, setReviewRationale] = useState<string>("");
  const [reviewing, setReviewing] = useState<boolean>(false);

  // History state
  const [historyWorkId, setHistoryWorkId] = useState<string | null>(null);
  const [historyEvents, setHistoryEvents] = useState<WorkEvent[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Navigation target focus effect
  useEffect(() => {
    if (!navTarget) return;
    if (navTarget.tenantId && navTarget.tenantId !== tenantId) return;
    if (adoptionId && navTarget.adoptionId && navTarget.adoptionId !== "current" && adoptionId !== "current" && navTarget.adoptionId !== adoptionId) return;
    if (loading) return;
    if (navTarget.nonce === lastHandledNavNonceRef.current) return;

    const exists = workItems.some((w) => w.id === navTarget.workId);
    if (exists) {
      lastHandledNavNonceRef.current = navTarget.nonce;
      setTimeout(() => {
        setTargetNotFoundWorkId(null);
      }, 0);

      setTimeout(() => {
        const targetEl = document.querySelector(`[data-testid="control-card-${navTarget.workId}"]`);
        if (targetEl) {
          if (typeof targetEl.scrollIntoView === "function") { targetEl.scrollIntoView({ behavior: "smooth", block: "center" }); }
          if (navTarget.targetTab === "evidence") {
            const uploadBtn = targetEl.querySelector<HTMLButtonElement>(`[data-testid="open-upload-modal-btn-${navTarget.workId}"]`);
            uploadBtn?.focus();
          } else {
            const ownerSelect = targetEl.querySelector<HTMLSelectElement>(`[data-testid="owner-select-${navTarget.workId}"]`);
            ownerSelect?.focus();
          }
        }
      }, 50);
    } else if (loadedSuccessfullyRef.current && !errorMessage) {
      // Authoritative not-found ONLY after settled successful load without errors
      lastHandledNavNonceRef.current = navTarget.nonce;
      setTimeout(() => {
        setTargetNotFoundWorkId(navTarget.workId);
      }, 0);
    }
  }, [navTarget, workItems, loading, errorMessage, tenantId, adoptionId]);

  useEffect(() => {
    loadedSuccessfullyRef.current = false;
    setTimeout(() => setTargetNotFoundWorkId(null), 0);
  }, [tenantId, adoptionId]);

  // Load initial work and owner directory
  const loadData = useCallback(async () => {
    if (!tenantId || !token) return;
    setLoading(true);
    setErrorMessage(null);
    setScannerUnavailable(false);

    abortControllerRef.current?.abort();
    const ac = new AbortController();
    abortControllerRef.current = ac;

    try {
      const [workRes, ownerRes] = await Promise.all([
        fetchControlWorkList(tenantId, token, adoptionId, ac.signal),
        fetchOwnerDirectory(tenantId, token, ac.signal),
      ]);

      if (!ac.signal.aborted) {
        loadedSuccessfullyRef.current = true;
        if (workRes.adoption_id) {
          setResolvedAdoptionId(workRes.adoption_id);
        }
        setWorkItems(workRes.items || []);
        setOwners(ownerRes.items || []);

        // Seed initial form values
        const initialOwners: Record<string, string> = {};
        const initialDates: Record<string, string> = {};
        for (const item of workRes.items || []) {
          initialOwners[item.id] = item.owner_user_id || "";
          initialDates[item.id] = item.due_date || "";
        }
        setSelectedOwners(initialOwners);
        setDueDates(initialDates);
      }
    } catch (err: unknown) {
      if (!ac.signal.aborted) {
        loadedSuccessfullyRef.current = false;
        if (err instanceof UnauthorizedError) {
          onSessionExpired?.();
        }
        const msg = err instanceof Error ? err.message : "Failed to load control work";
        setErrorMessage(msg);
      }
    } finally {
      if (!ac.signal.aborted) {
        setLoading(false);
      }
    }
  }, [tenantId, token, adoptionId, onSessionExpired]);

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
    };
  }, [loadData]);

  // Handle Initialize Work
  const handleInitialize = async () => {
    if (initializing || hasUnsavedParentEdits || isAdoptionStale) return;
    const targetAdoptId = resolvedAdoptionId || adoptionId;
    if (!targetAdoptId) {
      setErrorMessage("No adopted pack found to initialize work items for.");
      return;
    }
    setInitializing(true);
    setErrorMessage(null);

    const opId = crypto.randomUUID();
    try {
      const res = await initializeControlWork(tenantId, token, {
        operation_id: opId,
        adoption_id: targetAdoptId,
        expected_selection_revision: selectionRevision,
        expected_answer_revision: answerRevision,
      });
      setWorkItems(res.items || []);
      onDataChange?.();

      const initialOwners: Record<string, string> = {};
      const initialDates: Record<string, string> = {};
      for (const item of res.items || []) {
        initialOwners[item.id] = item.owner_user_id || "";
        initialDates[item.id] = item.due_date || "";
      }
      setSelectedOwners(initialOwners);
      setDueDates(initialDates);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Initialization failed";
      setErrorMessage(msg);
    } finally {
      setInitializing(false);
    }
  };

  // Handle Update Assignment
  const handleUpdateAssignment = async (workItem: ControlWorkItem) => {
    if (savingAssignmentId || hasUnsavedParentEdits || isAdoptionStale) return;
    setSavingAssignmentId(workItem.id);
    setErrorMessage(null);

    const opId = crypto.randomUUID();
    const ownerVal = selectedOwners[workItem.id] || null;
    const dueVal = dueDates[workItem.id] || null;

    try {
      const receipt = await patchControlWork(tenantId, token, workItem.id, {
        operation_id: opId,
        expected_selection_revision: selectionRevision,
        expected_answer_revision: answerRevision,
        expected_work_version: workItem.version,
        owner_user_id: ownerVal,
        due_date: dueVal,
      });

      setWorkItems((prev) =>
        prev.map((it) => (it.id === workItem.id ? receipt.current_work : it))
      );
      onDataChange?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update assignment";
      setErrorMessage(msg);
    } finally {
      setSavingAssignmentId(null);
    }
  };

  // Handle Upload & Pin Evidence
  const handleUploadAndPin = async (workItem: ControlWorkItem) => {
    if (!selectedFile || !uploadRationale.trim() || uploading) return;
    setUploading(true);
    setErrorMessage(null);
    setScannerUnavailable(false);

    try {
      // Step 1: Upload multipart to /v1/tenants/{tenant_id}/files
      const fileRes = await uploadEvidenceFile(tenantId, token, selectedFile);

      // Step 2: Create & Pin Evidence to Work
      const opId = crypto.randomUUID();
      const validUntilIso = fileValidUntil
        ? new Date(fileValidUntil).toISOString()
        : null;

      const receipt = await createEvidence(tenantId, token, workItem.id, {
        operation_id: opId,
        expected_selection_revision: selectionRevision,
        expected_answer_revision: answerRevision,
        expected_work_version: workItem.version,
        file_id: fileRes.id,
        valid_until: validUntilIso,
        rationale: uploadRationale.trim(),
      });

      setWorkItems((prev) =>
        prev.map((it) => (it.id === workItem.id ? receipt.current_work : it))
      );

      onDataChange?.();
      // Reset modal state
      setUploadModalWorkId(null);
      setSelectedFile(null);
      setFileValidUntil("");
      setUploadRationale("");
    } catch (err: unknown) {
      if (err instanceof ServiceUnavailableError) {
        setScannerUnavailable(true);
      }
      const msg = err instanceof Error ? err.message : "Evidence upload/pinning failed";
      setErrorMessage(msg);
    } finally {
      setUploading(false);
    }
  };

  // Available revisions for deliberate reuse across other work items
  const reusableEvidenceOptions = useMemo(() => {
    const list: Array<{
      key: string;
      evidenceId: string;
      revisionNumber: number;
      digest: string;
      filename: string;
      sourceTitle: string;
    }> = [];

    const seen = new Set<string>();
    for (const item of workItems) {
      for (const link of item.links) {
        const k = `${link.evidence_id}:${link.revision_number}:${link.digest}`;
        if (!seen.has(k)) {
          seen.add(k);
          list.push({
            key: k,
            evidenceId: link.evidence_id,
            revisionNumber: link.revision_number,
            digest: link.digest,
            filename: link.filename,
            sourceTitle: item.title,
          });
        }
      }
    }
    return list;
  }, [workItems]);

  // Handle Deliberate Reuse
  const handleReuse = async (workItem: ControlWorkItem) => {
    if (!selectedReuseTarget || !reuseRationale.trim() || reusing) return;
    setReusing(true);
    setErrorMessage(null);

    const [evId, revNumStr, digest] = selectedReuseTarget.split(":");
    const opId = crypto.randomUUID();

    try {
      const receipt = await createReuseLink(tenantId, token, workItem.id, {
        operation_id: opId,
        expected_selection_revision: selectionRevision,
        expected_answer_revision: answerRevision,
        expected_work_version: workItem.version,
        evidence_id: evId,
        evidence_revision_number: parseInt(revNumStr, 10),
        evidence_revision_digest: digest,
        rationale: reuseRationale.trim(),
      });

      setWorkItems((prev) =>
        prev.map((it) => (it.id === workItem.id ? receipt.current_work : it))
      );

      onDataChange?.();
      // Reset modal
      setReuseModalWorkId(null);
      setSelectedReuseTarget("");
      setReuseRationale("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Evidence reuse failed";
      setErrorMessage(msg);
    } finally {
      setReusing(false);
    }
  };

  // Handle Review
  const handleReview = async () => {
    if (!reviewModalLink || !reviewRationale.trim() || reviewing) return;
    setReviewing(true);
    setErrorMessage(null);

    const { workId, linkId, currentWorkVer } = reviewModalLink;
    const opId = crypto.randomUUID();

    try {
      const receipt = await createReview(tenantId, token, workId, linkId, {
        operation_id: opId,
        expected_selection_revision: selectionRevision,
        expected_answer_revision: answerRevision,
        expected_work_version: currentWorkVer,
        decision: reviewDecision,
        rationale: reviewRationale.trim(),
      });

      setWorkItems((prev) =>
        prev.map((it) => (it.id === workId ? receipt.current_work : it))
      );

      onDataChange?.();
      setReviewModalLink(null);
      setReviewRationale("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Review submission failed";
      setErrorMessage(msg);
    } finally {
      setReviewing(false);
    }
  };

  // Handle Toggle History
  const handleToggleHistory = async (workId: string) => {
    if (historyWorkId === workId) {
      setHistoryWorkId(null);
      setHistoryEvents([]);
      return;
    }

    setHistoryWorkId(workId);
    setLoadingHistory(true);
    try {
      const res = await fetchWorkHistory(tenantId, token, workId);
      setHistoryEvents(res.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load history";
      setErrorMessage(msg);
    } finally {
      setLoadingHistory(false);
    }
  };

  // Handle File Download
  const handleDownloadFile = async (
    workId: string,
    linkId: string,
    fileId: string,
    filename: string,
  ) => {
    try {
      const blob = await downloadPinnedFile(tenantId, token, workId, linkId, fileId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || "evidence.bin";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Download failed";
      setErrorMessage(msg);
    }
  };

  const mutationsDisabled = hasUnsavedParentEdits || isAdoptionStale;

  const renderValidityBadge = (validity: string) => {
    let cls = "mw-badge-validity-available";
    let label = t("customerDemo.evidenceValidityAvailable");
    if (validity === "MISSING") {
      cls = "mw-badge-validity-missing";
      label = t("customerDemo.evidenceValidityMissing");
    } else if (validity === "NOT_YET_VALID") {
      cls = "mw-badge-validity-not-yet";
      label = t("customerDemo.evidenceValidityNotYetValid");
    } else if (validity === "EXPIRED") {
      cls = "mw-badge-validity-expired";
      label = t("customerDemo.evidenceValidityExpired");
    } else if (validity === "QUARANTINED") {
      cls = "mw-badge-validity-quarantined";
      label = t("customerDemo.evidenceValidityQuarantined");
    } else if (validity === "UNAVAILABLE") {
      cls = "mw-badge-validity-unavailable";
      label = t("customerDemo.evidenceValidityUnavailable");
    } else if (validity === "UNVERIFIED") {
      cls = "mw-badge-validity-unverified";
      label = t("customerDemo.evidenceValidityUnverified");
    }
    return <span className={`mw-badge-validity ${cls}`}>{label}</span>;
  };

  const renderScanBadge = (scanStatus?: string) => {
    if (scanStatus === "SCANNED_AT_LINK") {
      return (
        <span className="mw-badge-scan mw-badge-scan-clean" data-testid="scan-status-badge">
          {t("customerDemo.scanStatusScannedAtLink")}
        </span>
      );
    }
    return (
      <span className="mw-badge-scan mw-badge-scan-unverified" data-testid="scan-status-badge">
        {t("customerDemo.scanStatusUnverified")}
      </span>
    );
  };

  const renderReviewBadge = (review: string) => {
    let cls = "mw-badge-review-pending";
    let label = t("customerDemo.reviewStatusPending");
    if (review === "ACCEPTED") {
      cls = "mw-badge-review-accepted";
      label = t("customerDemo.reviewStatusAccepted");
    } else if (review === "REJECTED") {
      cls = "mw-badge-review-rejected";
      label = t("customerDemo.reviewStatusRejected");
    }
    return <span className={`mw-badge-review ${cls}`}>{label}</span>;
  };

  if (loading) {
    return (
      <div className="mw-card mw-control-work-loading" data-testid="control-work-loading">
        <p>{t("customerDemo.saving")}</p>
      </div>
    );
  }

  return (
    <section
      className="mw-control-work-section"
      aria-labelledby="control-work-heading"
      data-testid="control-evidence-workspace"
    >
      <div className="mw-card-header">
        <div>
          <h2 id="control-work-heading" className="mw-card-title">
            {t("customerDemo.controlWorkTitle")}
          </h2>
          <p className="mw-card-subtitle">
            {t("customerDemo.controlWorkSubtitle")}
          </p>
        </div>

        {workItems.length === 0 && (
          <button
            type="button"
            className="mw-btn mw-btn-primary btn-primary"
            onClick={handleInitialize}
            disabled={initializing || mutationsDisabled}
            data-testid="init-control-work-btn"
          >
            {initializing ? t("customerDemo.initializingWork") : t("customerDemo.initWorkBtn")}
          </button>
        )}
      </div>

      {mutationsDisabled && (
        <div className="mw-warning-notice" role="alert" data-testid="stale-work-warning">
          <strong>&bull; {t("customerDemo.noticeLabel")}:</strong> {t("customerDemo.staleWorkNotice")}
        </div>
      )}

      {scannerUnavailable && (
        <div className="mw-error-notice" role="alert" data-testid="scanner-unavailable-alert">
          <strong>&bull; {t("customerDemo.errorLabel")}:</strong> {t("customerDemo.scannerUnavailableNotice")}
        </div>
      )}

      {errorMessage && !scannerUnavailable && (
        <div className="mw-error-notice" role="alert" data-testid="evidence-error-alert">
          {errorMessage}
        </div>
      )}

      {targetNotFoundWorkId && (
        <div className="mw-warning-notice" role="status" data-testid="control-nav-target-not-found" style={{ marginBottom: "1rem" }}>
          <span>{t("portal.navTargetNotFound") || "Requested item was not found in the current adoption."} ({targetNotFoundWorkId})</span>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="dismiss-control-nav-target-btn"
            onClick={() => setTargetNotFoundWorkId(null)}
            style={{ marginLeft: "0.5rem", fontSize: "0.75rem", padding: "0.15rem 0.4rem" }}
          >
            {t("portal.dismissBtn") || t("portal.closeBtn") || "Dismiss"}
          </button>
        </div>
      )}

      {workItems.length === 0 ? (
        <div className="mw-empty-work-card" data-testid="empty-work-notice">
          <p>{t("customerDemo.noControlWorkYet")}</p>
          <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-tertiary)" }}>
            {t("customerDemo.initWorkNotice")}
          </p>
        </div>
      ) : (
        <div className="mw-control-cards-grid" data-testid="control-cards-container">
          {workItems.map((item) => (
            <article
              key={item.id}
              className="mw-control-card"
              data-testid={`control-card-${item.id}`}
            >
              {/* Card Header */}
              <div className="mw-control-header">
                <div>
                  <h3 className="mw-control-title">{item.title}</h3>
                  <div className="mw-control-provenance">
                    <span>{item.provenance} (Pack v{item.pack_version})</span>
                    <span className="mw-work-version-badge">
                      {t("customerDemo.workVersionLabel")} {item.version}
                    </span>
                  </div>
                </div>
              </div>

              {/* Requirement Applicability Badges */}
              <div className="mw-req-results-badges">
                {item.requirement_results.map((rr) => {
                  let badgeCls = "badge-applicable";
                  let statusText = t("customerDemo.statusApplicable");
                  if (rr.result === "NOT_APPLICABLE") {
                    badgeCls = "badge-not-applicable";
                    statusText = t("customerDemo.statusNotApplicable");
                  } else if (rr.result === "NEEDS_INFORMATION") {
                    badgeCls = "badge-needs-info";
                    statusText = t("customerDemo.statusNeedsInfo");
                  }
                  return (
                    <span
                      key={rr.requirement_id}
                      className={`mw-status-pill ${badgeCls}`}
                      title={rr.requirement_title}
                    >
                      {rr.requirement_identifier}: {statusText}
                    </span>
                  );
                })}
              </div>

              {/* Owner and Target Due Date Assignment */}
              <div className="mw-assignment-bar">
                <div className="mw-assignment-field">
                  <label htmlFor={`owner-select-${item.id}`}>
                    {t("customerDemo.assignOwnerLabel")}:
                  </label>
                  <select
                    id={`owner-select-${item.id}`}
                    value={selectedOwners[item.id] ?? ""}
                    onChange={(e) =>
                      setSelectedOwners((prev) => ({
                        ...prev,
                        [item.id]: e.target.value,
                      }))
                    }
                    disabled={mutationsDisabled || savingAssignmentId === item.id}
                    data-testid={`owner-select-${item.id}`}
                  >
                    <option value="">{t("customerDemo.unassignedOwner")}</option>
                    {owners.map((o) => (
                      <option key={o.user_id} value={o.user_id}>
                        {o.display_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="mw-assignment-field">
                  <label htmlFor={`due-date-${item.id}`}>
                    {t("customerDemo.dueDateLabel")}:
                  </label>
                  <input
                    id={`due-date-${item.id}`}
                    type="date"
                    value={dueDates[item.id] ?? ""}
                    onChange={(e) =>
                      setDueDates((prev) => ({
                        ...prev,
                        [item.id]: e.target.value,
                      }))
                    }
                    disabled={mutationsDisabled || savingAssignmentId === item.id}
                    data-testid={`due-date-${item.id}`}
                  />
                </div>

                <button
                  type="button"
                  className="mw-btn mw-btn-secondary btn-secondary"
                  onClick={() => handleUpdateAssignment(item)}
                  disabled={mutationsDisabled || savingAssignmentId === item.id}
                  data-testid={`save-assignment-btn-${item.id}`}
                >
                  {savingAssignmentId === item.id
                    ? t("customerDemo.savingAssignment")
                    : t("customerDemo.saveAssignmentBtn")}
                </button>
              </div>

              {/* Evidence Links Section */}
              <div className="mw-evidence-links-container">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                  <h4 style={{ fontSize: "0.875rem", fontWeight: 600, margin: 0, minWidth: 0, overflowWrap: "break-word" }}>
                    {t("customerDemo.controlWorkTitle")} ({item.links.length})
                  </h4>

                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary btn-secondary"
                      onClick={() => setReuseModalWorkId(item.id)}
                      disabled={mutationsDisabled || reusableEvidenceOptions.length === 0}
                      data-testid={`open-reuse-modal-btn-${item.id}`}
                      style={{ padding: "0.25rem 0.625rem", fontSize: "0.75rem" }}
                    >
                      {t("customerDemo.reuseEvidenceBtn")}
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary btn-primary"
                      onClick={() => setUploadModalWorkId(item.id)}
                      disabled={mutationsDisabled}
                      data-testid={`open-upload-modal-btn-${item.id}`}
                      style={{ padding: "0.25rem 0.625rem", fontSize: "0.75rem" }}
                    >
                      {t("customerDemo.uploadAndLinkBtn")}
                    </button>
                  </div>
                </div>

                {item.links.length === 0 ? (
                  <p style={{ fontSize: "0.8125rem", color: "var(--mw-text-tertiary)", margin: "0.5rem 0 0" }}>
                    {t("portal.noEvidenceLinked")}
                  </p>
                ) : (
                  <div className="mw-evidence-items-list">
                    {item.links.map((link) => (
                      <div
                        key={link.id}
                        className="mw-evidence-item-card"
                        data-testid={`evidence-link-${link.id}`}
                      >
                        <div className="mw-evidence-item-header">
                          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <span style={{ fontWeight: 600 }}>{link.filename}</span>
                            <span style={{ fontSize: "0.75rem", color: "var(--mw-text-secondary)" }}>
                              ({Math.round(link.file_size / 1024)} KiB &bull; {link.classification})
                            </span>
                          </div>

                          <div style={{ display: "flex", alignItems: "center", gap: "0.375rem", flexWrap: "wrap" }}>
                            {renderValidityBadge(link.validity)}
                            {renderScanBadge(link.scan_status)}
                            {renderReviewBadge(link.review)}
                          </div>
                        </div>

                        <div className="mw-evidence-revision-pin">
                          <code>
                            Pinned Rev {link.revision_number} &bull; SHA256: {link.digest.substring(0, 16)}...
                          </code>
                        </div>

                        <p className="mw-evidence-rationale">
                          &ldquo;{link.rationale}&rdquo;
                        </p>

                        <div className="mw-evidence-actions-bar">
                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary btn-secondary"
                            onClick={() =>
                              handleDownloadFile(
                                item.id,
                                link.id,
                                link.file_ids[0],
                                link.filename,
                              )
                            }
                            data-testid={`download-file-btn-${link.id}`}
                            style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                          >
                            {t("customerDemo.downloadPinnedFileBtn")}
                          </button>

                          <button
                            type="button"
                            className="mw-btn mw-btn-secondary btn-secondary"
                            onClick={() => {
                              setReviewModalLink({
                                workId: item.id,
                                linkId: link.id,
                                currentWorkVer: item.version,
                              });
                              setReviewDecision("ACCEPTED");
                              setReviewRationale("");
                            }}
                            disabled={mutationsDisabled}
                            data-testid={`review-link-btn-${link.id}`}
                            style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                          >
                            {t("customerDemo.reviewTitle")}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* History Toggle */}
              <div style={{ marginTop: "1rem", borderTop: "1px solid var(--mw-border-subtle)", paddingTop: "0.75rem" }}>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary btn-secondary"
                  onClick={() => handleToggleHistory(item.id)}
                  data-testid={`toggle-history-btn-${item.id}`}
                  style={{ padding: "0.25rem 0.625rem", fontSize: "0.75rem" }}
                >
                  {historyWorkId === item.id
                    ? t("customerDemo.hideHistoryBtn")
                    : t("customerDemo.viewHistoryBtn")}
                </button>

                {historyWorkId === item.id && (
                  <div className="mw-history-panel" data-testid={`history-panel-${item.id}`}>
                    <h5 style={{ margin: "0.5rem 0", fontSize: "0.8125rem", fontWeight: 600 }}>
                      {t("customerDemo.historyEventsTitle")}
                    </h5>
                    {loadingHistory ? (
                      <p style={{ fontSize: "0.75rem", color: "var(--mw-text-secondary)" }}>{t("portal.loadingHistory")}</p>
                    ) : historyEvents.length === 0 ? (
                      <p style={{ fontSize: "0.75rem", color: "var(--mw-text-tertiary)" }}>{t("portal.noHistory")}</p>
                    ) : (
                      <ol className="mw-history-timeline">
                        {historyEvents.map((ev) => (
                          <li key={ev.revision} className="mw-history-event-item">
                            <span className="mw-history-rev-tag">Rev {ev.revision}</span>
                            <span className="mw-history-type-tag">{ev.type}</span>
                            {ev.decision && (
                              <span className={`mw-history-decision-tag ${ev.decision.toLowerCase()}`}>
                                {ev.decision}
                              </span>
                            )}
                            <span className="mw-history-time">
                              {new Date(ev.time).toLocaleString()}
                            </span>
                          </li>
                        ))}
                      </ol>
                    )}
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {/* Upload Modal */}
      {uploadModalWorkId && (
        <div className="mw-modal-overlay" role="dialog" aria-modal="true" data-testid="upload-evidence-modal">
          <div className="mw-modal-content">
            <h3 style={{ margin: "0 0 1rem", fontSize: "1.125rem" }}>
              {t("customerDemo.uploadEvidenceTitle")}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label className="mw-question-label" htmlFor="upload-file-input">
                  {t("customerDemo.selectFileLabel")}
                </label>
                <input
                  id="upload-file-input"
                  type="file"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  data-testid="evidence-file-input"
                />
              </div>

              <div>
                <label className="mw-question-label" htmlFor="upload-valid-until">
                  {t("customerDemo.validUntilLabel")}
                </label>
                <input
                  id="upload-valid-until"
                  type="date"
                  value={fileValidUntil}
                  onChange={(e) => setFileValidUntil(e.target.value)}
                  data-testid="evidence-valid-until-input"
                />
              </div>

              <div>
                <label className="mw-question-label" htmlFor="upload-rationale-input">
                  {t("customerDemo.rationaleLabel")}
                </label>
                <textarea
                  id="upload-rationale-input"
                  rows={3}
                  value={uploadRationale}
                  onChange={(e) => setUploadRationale(e.target.value)}
                  placeholder={t("customerDemo.rationalePlaceholder")}
                  className="mw-textarea"
                  data-testid="evidence-rationale-input"
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
              <button
                type="button"
                className="mw-btn mw-btn-secondary btn-secondary"
                onClick={() => {
                  setUploadModalWorkId(null);
                  setSelectedFile(null);
                  setUploadRationale("");
                }}
                disabled={uploading}
              >{t("customerDemo.cancelBtn")}</button>
              <button
                type="button"
                className="mw-btn mw-btn-primary btn-primary"
                onClick={() => {
                  const targetWork = workItems.find((w) => w.id === uploadModalWorkId);
                  if (targetWork) handleUploadAndPin(targetWork);
                }}
                disabled={!selectedFile || !uploadRationale.trim() || uploading}
                data-testid="submit-evidence-upload-btn"
              >
                {uploading ? t("customerDemo.uploadingEvidence") : t("customerDemo.uploadAndLinkBtn")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deliberate Reuse Modal */}
      {reuseModalWorkId && (
        <div className="mw-modal-overlay" role="dialog" aria-modal="true" data-testid="reuse-evidence-modal">
          <div className="mw-modal-content">
            <h3 style={{ margin: "0 0 1rem", fontSize: "1.125rem" }}>
              {t("customerDemo.reuseEvidenceTitle")}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label className="mw-question-label" htmlFor="reuse-select-target">
                  {t("customerDemo.selectEvidenceToReuse")}
                </label>
                <select
                  id="reuse-select-target"
                  value={selectedReuseTarget}
                  onChange={(e) => setSelectedReuseTarget(e.target.value)}
                  className="mw-select"
                  data-testid="reuse-target-select"
                >
                  <option value="">-- Choose existing revision --</option>
                  {reusableEvidenceOptions.map((opt) => (
                    <option key={opt.key} value={opt.key}>
                      {opt.filename} (Rev {opt.revisionNumber}) - From: {opt.sourceTitle}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mw-question-label" htmlFor="reuse-rationale-input">
                  {t("customerDemo.rationaleLabel")}
                </label>
                <textarea
                  id="reuse-rationale-input"
                  rows={3}
                  value={reuseRationale}
                  onChange={(e) => setReuseRationale(e.target.value)}
                  placeholder={t("customerDemo.rationalePlaceholder")}
                  className="mw-textarea"
                  data-testid="reuse-rationale-input"
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
              <button
                type="button"
                className="mw-btn mw-btn-secondary btn-secondary"
                onClick={() => {
                  setReuseModalWorkId(null);
                  setSelectedReuseTarget("");
                  setReuseRationale("");
                }}
                disabled={reusing}
              >{t("customerDemo.cancelBtn")}</button>
              <button
                type="button"
                className="mw-btn mw-btn-primary btn-primary"
                onClick={() => {
                  const targetWork = workItems.find((w) => w.id === reuseModalWorkId);
                  if (targetWork) handleReuse(targetWork);
                }}
                disabled={!selectedReuseTarget || !reuseRationale.trim() || reusing}
                data-testid="submit-reuse-btn"
              >
                {reusing ? t("customerDemo.reusingEvidence") : t("customerDemo.reuseEvidenceBtn")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Review Modal */}
      {reviewModalLink && (
        <div className="mw-modal-overlay" role="dialog" aria-modal="true" data-testid="review-evidence-modal">
          <div className="mw-modal-content">
            <h3 style={{ margin: "0 0 1rem", fontSize: "1.125rem" }}>
              {t("customerDemo.reviewTitle")}
            </h3>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label className="mw-question-label" htmlFor="review-decision-select">
                  {t("customerDemo.reviewDecisionLabel")}
                </label>
                <select
                  id="review-decision-select"
                  value={reviewDecision}
                  onChange={(e) => setReviewDecision(e.target.value as "ACCEPTED" | "REJECTED")}
                  className="mw-select"
                  data-testid="review-decision-select"
                >
                  <option value="ACCEPTED">{t("customerDemo.acceptDecision")}</option>
                  <option value="REJECTED">{t("customerDemo.rejectDecision")}</option>
                </select>
              </div>

              <div>
                <label className="mw-question-label" htmlFor="review-rationale-input">
                  {t("customerDemo.rationaleLabel")}
                </label>
                <textarea
                  id="review-rationale-input"
                  rows={3}
                  value={reviewRationale}
                  onChange={(e) => setReviewRationale(e.target.value)}
                  placeholder={t("customerDemo.reviewRationalePlaceholder")}
                  className="mw-textarea"
                  data-testid="review-rationale-input"
                />
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "1.5rem" }}>
              <button
                type="button"
                className="mw-btn mw-btn-secondary btn-secondary"
                onClick={() => {
                  setReviewModalLink(null);
                  setReviewRationale("");
                }}
                disabled={reviewing}
              >{t("customerDemo.cancelBtn")}</button>
              <button
                type="button"
                className="mw-btn mw-btn-primary btn-primary"
                onClick={handleReview}
                disabled={!reviewRationale.trim() || reviewing}
                data-testid="submit-review-btn"
              >
                {reviewing ? t("customerDemo.recordingReview") : t("customerDemo.recordReviewBtn")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
