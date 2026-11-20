/**
 * Conformly Customer Readiness Verification Panel (MVP-E).
 * Renders private synthetic readiness verification lifecycle:
 * - Authenticated token passing and session lifecycle integration
 * - Issuance from approved pre-audit cases
 * - Boundary validity and effective status display
 * - Suspension, revocation, correction, and supersession
 * - Complete operation/context/confirmation/uncertainty ownership
 * - Idempotent reconciliation
 * - Safe allowlisted private projection
 * - Immutable event history
 */

import React, { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { UnauthorizedError } from "./api";
import { PreauditCaseDetail } from "./preaudit-types";
import {
  correctVerification,
  getVerification,
  getVerificationHistory,
  getVerificationProjection,
  issueVerification,
  isVerificationEnabled,
  listVerifications,
  reconcileVerifications,
  revokeVerification,
  supersedeVerification,
  suspendVerification,
} from "./verification-api";
import {
  CorrectVerificationPayload,
  IssueVerificationPayload,
  RevokeVerificationPayload,
  SupersedeVerificationPayload,
  SuspendVerificationPayload,
  VerificationDetail,
  VerificationEventItem,
  VerificationProjection,
} from "./verification-types";
import "./verification-workspace.css";

function getSecureUUID(): string {
  if (typeof crypto !== "undefined") {
    if (typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    if (typeof crypto.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
  }
  throw new Error("Secure random UUID generation is not available");
}

function getErrorMessage(err: unknown, fallback: string): string {
  if (err && typeof err === "object") {
    if ("detail" in err && typeof (err as { detail: unknown }).detail === "string") {
      return (err as { detail: string }).detail;
    }
    if ("message" in err && typeof (err as { message: unknown }).message === "string") {
      return (err as { message: string }).message;
    }
  }
  return fallback;
}

export type UncertainPayload =
  | IssueVerificationPayload
  | SuspendVerificationPayload
  | RevokeVerificationPayload
  | CorrectVerificationPayload
  | SupersedeVerificationPayload
  | Record<string, unknown>;

export interface UncertainOp {
  operationId: string;
  action: "issue" | "suspend" | "revoke" | "correct" | "supersede" | "reconcile";
  payload: UncertainPayload;
  targetVerificationId?: string;
  targetCaseId: string;
  label: string;
  errorText: string;
}

interface FrozenConfirmState {
  action: "suspend" | "revoke" | "correct" | "supersede";
  targetVerificationId: string;
  targetCaseId: string;
  targetRevision: number;
  lifetime: number;
}

export interface ReadinessVerificationPanelProps {
  tenantId: string;
  token: string;
  preauditCase: PreauditCaseDetail;
  isOwner?: boolean;
  userRole?: string;
  currentUserId?: string;
  adoptionId?: string;
  activeView?: string;
  uncertainOps?: UncertainOp[];
  onUncertainOpsChange?: React.Dispatch<React.SetStateAction<UncertainOp[]>>;
  onVerificationChange?: () => void;
  onSessionExpired?: () => void;
}

export const ReadinessVerificationPanel: FC<ReadinessVerificationPanelProps> = ({
  tenantId,
  token,
  preauditCase,
  isOwner = false,
  userRole,
  currentUserId,
  adoptionId,
  activeView,
  uncertainOps: propUncertainOps,
  onUncertainOpsChange,
  onVerificationChange,
  onSessionExpired,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [verification, setVerification] = useState<VerificationDetail | null>(null);
  const [history, setHistory] = useState<VerificationEventItem[]>([]);
  const [projection, setProjection] = useState<VerificationProjection | null>(null);
  const [showProjection, setShowProjection] = useState<boolean>(false);

  // Uncertain operations state across same actor/tenant session (owned by parent or local fallback)
  const [localUncertainOps, setLocalUncertainOps] = useState<UncertainOp[]>([]);
  const uncertainOps = propUncertainOps !== undefined ? propUncertainOps : localUncertainOps;
  const setUncertainOps = onUncertainOpsChange !== undefined ? onUncertainOpsChange : setLocalUncertainOps;
  const [pendingDismissOpId, setPendingDismissOpId] = useState<string | null>(null);

  // Dialog and supersession state
  const [dialogAction, setDialogAction] = useState<"suspend" | "revoke" | "correct" | "supersede" | null>(null);
  const [dialogReason, setDialogReason] = useState<string>("");
  const [frozenConfirm, setFrozenConfirm] = useState<FrozenConfirmState | null>(null);

  // Supersession form fields
  const [supersedeCaseId, setSupersedeCaseId] = useState<string>("");
  const [supersedeRevision, setSupersedeRevision] = useState<string>("1");
  const [supersedeSnapshotId, setSupersedeSnapshotId] = useState<string>("");
  const [supersedeDigest, setSupersedeDigest] = useState<string>("");
  const [supersedeLimitations, setSupersedeLimitations] = useState<string>("");
  const [supersedeNotes, setSupersedeNotes] = useState<string>("");

  // Context lifetime, sequence ordering, and active operation references
  const contextLifetimeRef = useRef<number>(0);
  const requestSeqRef = useRef<number>(0);
  const latestAdmittedSeqRef = useRef<number>(0);
  const activeOpIdRef = useRef<string | null>(null);

  // Active identity boundary for private state ownership (tenant / token / actor)
  const lastIdentityRef = useRef<{
    tenantId: string;
    token: string;
    userRole?: string;
    currentUserId?: string;
  }>({ tenantId, token, userRole, currentUserId });

  const handleApiError = (err: unknown, fallback: string, lifetime: number) => {
    if (lifetime !== contextLifetimeRef.current) return;
    const is401 = err instanceof UnauthorizedError || (err as { status?: number })?.status === 401;
    if (is401) {
      onSessionExpired?.();
      return;
    }
    setError(getErrorMessage(err, fallback));
  };

  const loadVerificationData = async (signal?: AbortSignal) => {
    if (!isVerificationEnabled()) return;
    const thisLifetime = contextLifetimeRef.current;
    const reqSeq = ++requestSeqRef.current;
    setLoading(true);
    setError(null);

    try {
      const listRes = await listVerifications(
        tenantId,
        token,
        signal,
        50,
        0,
        preauditCase.id,
      );
      if (thisLifetime !== contextLifetimeRef.current || reqSeq < latestAdmittedSeqRef.current) return;

      const matching = listRes.verifications.find(
        (v) => v.preaudit_id === preauditCase.id,
      );

      if (matching) {
        const detail = await getVerification(tenantId, matching.id, token, signal);
        if (thisLifetime !== contextLifetimeRef.current || reqSeq < latestAdmittedSeqRef.current) return;

        const hist = await getVerificationHistory(tenantId, matching.id, token, signal);
        if (thisLifetime !== contextLifetimeRef.current || reqSeq < latestAdmittedSeqRef.current) return;

        latestAdmittedSeqRef.current = reqSeq;
        setVerification(detail);
        setHistory(hist.events || []);

        // Exact operation settlement: only settle if an immutable history event matches this exact operation ID
        const historyOpIds = new Set((hist.events || []).map((e) => e.operation_id).filter(Boolean));
        setUncertainOps((prev) =>
          prev.filter((op) => {
            if (op.targetCaseId !== preauditCase.id) return true;
            if (historyOpIds.has(op.operationId)) return false;
            return true;
          }),
        );
      } else {
        latestAdmittedSeqRef.current = reqSeq;
        setVerification(null);
        setHistory([]);
      }
    } catch (err: unknown) {
      if (signal?.aborted || thisLifetime !== contextLifetimeRef.current || reqSeq < latestAdmittedSeqRef.current) return;
      handleApiError(err, "Failed to load readiness verification", thisLifetime);
    } finally {
      if (thisLifetime === contextLifetimeRef.current && reqSeq >= latestAdmittedSeqRef.current) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    if (!isVerificationEnabled()) return;
    const currentLifetime = ++contextLifetimeRef.current;
    activeOpIdRef.current = null;
    setActionLoading(false);
    setLoading(false);
    setVerification(null);
    setHistory([]);
    setProjection(null);
    setShowProjection(false);
    setError(null);
    setDialogAction(null);
    setFrozenConfirm(null);
    setPendingDismissOpId(null);

    // Clear inaccessible private state on tenant / token / actor change
    if (
      lastIdentityRef.current.tenantId !== tenantId ||
      lastIdentityRef.current.token !== token ||
      lastIdentityRef.current.userRole !== userRole ||
      lastIdentityRef.current.currentUserId !== currentUserId
    ) {
      setUncertainOps([]);
      lastIdentityRef.current = { tenantId, token, userRole, currentUserId };
    }

    const abortController = new AbortController();

    const fetchAsync = async () => {
      await Promise.resolve();
      if (currentLifetime !== contextLifetimeRef.current) return;
      await loadVerificationData(abortController.signal);
    };
    void fetchAsync();

    const lifetimeRef = contextLifetimeRef;
    return () => {
      // Increment retirement identity in cleanup on unmount
      lifetimeRef.current++;
      activeOpIdRef.current = null;
      abortController.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    tenantId,
    token,
    userRole,
    currentUserId,
    adoptionId,
    activeView,
    preauditCase.id,
    preauditCase.status,
    preauditCase.revision,
  ]);

  if (!isVerificationEnabled()) {
    return null;
  }

  const handleIssue = async () => {
    if (!isOwner || !preauditCase.current_review_snapshot_id || !preauditCase.current_review_snapshot_digest) {
      return;
    }

    // Prevent fresh-ID resubmission of an already uncertain intent
    const existingUnresolved = uncertainOps.find(
      (o) => o.action === "issue" && o.targetCaseId === preauditCase.id,
    );
    if (existingUnresolved) {
      setError(
        "An issue operation is already pending/uncertain for this case. Please retry the original operation or acknowledge disposal before submitting a new one.",
      );
      return;
    }

    const thisLifetime = contextLifetimeRef.current;
    const opId = getSecureUUID();
    activeOpIdRef.current = opId;
    setActionLoading(true);
    setError(null);
    const payload: IssueVerificationPayload = {
      operation_id: opId,
      preaudit_id: preauditCase.id,
      expected_case_revision: preauditCase.revision,
      snapshot_id: preauditCase.current_review_snapshot_id,
      snapshot_digest: preauditCase.current_review_snapshot_digest,
      limitations: [
        "Private synthetic internal test only",
        "Non-accredited assessment qualification",
      ],
      notes: "Issued by Owner via Verification Workspace",
    };

    try {
      const newV = await issueVerification(tenantId, payload, token);
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      setVerification(newV);
      setUncertainOps((prev) => prev.filter((o) => o.operationId !== opId));
      await loadVerificationData();
      if (thisLifetime !== contextLifetimeRef.current) return;
      onVerificationChange?.();
    } catch (err: unknown) {
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      handleApiError(err, "Failed to issue readiness verification", thisLifetime);
      const is401 = err instanceof UnauthorizedError || (err as { status?: number })?.status === 401;
      if (!is401) {
        setUncertainOps((prev) => [
          ...prev.filter((o) => o.operationId !== opId),
          {
            operationId: opId,
            action: "issue",
            payload,
            targetCaseId: preauditCase.id,
            label: "Issue Verification",
            errorText: getErrorMessage(err, "Network or server failure"),
          },
        ]);
      }
    } finally {
      if (thisLifetime === contextLifetimeRef.current && activeOpIdRef.current === opId) {
        activeOpIdRef.current = null;
        setActionLoading(false);
      }
    }
  };

  const handleToggleProjection = async () => {
    if (!verification) return;
    if (showProjection) {
      setShowProjection(false);
      return;
    }
    const thisLifetime = contextLifetimeRef.current;
    const opId = getSecureUUID();
    activeOpIdRef.current = opId;
    setActionLoading(true);
    setError(null);
    try {
      const proj = await getVerificationProjection(tenantId, verification.id, token);
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      setProjection(proj);
      setShowProjection(true);
    } catch (err: unknown) {
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      handleApiError(err, "Failed to load verification projection", thisLifetime);
    } finally {
      if (thisLifetime === contextLifetimeRef.current && activeOpIdRef.current === opId) {
        activeOpIdRef.current = null;
        setActionLoading(false);
      }
    }
  };

  const handleReconcile = async () => {
    const thisLifetime = contextLifetimeRef.current;
    const opId = getSecureUUID();
    activeOpIdRef.current = opId;
    setActionLoading(true);
    setError(null);
    try {
      await reconcileVerifications(tenantId, {}, token);
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      await loadVerificationData();
      if (thisLifetime !== contextLifetimeRef.current) return;
      onVerificationChange?.();
    } catch (err: unknown) {
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      handleApiError(err, "Failed to reconcile verification lifecycles", thisLifetime);
    } finally {
      if (thisLifetime === contextLifetimeRef.current && activeOpIdRef.current === opId) {
        activeOpIdRef.current = null;
        setActionLoading(false);
      }
    }
  };

  const openActionDialog = (action: "suspend" | "revoke" | "correct" | "supersede") => {
    if (!verification) return;
    setFrozenConfirm({
      action,
      targetVerificationId: verification.id,
      targetCaseId: preauditCase.id,
      targetRevision: verification.revision,
      lifetime: contextLifetimeRef.current,
    });
    setDialogAction(action);
    setDialogReason("");
    setSupersedeCaseId("");
    setSupersedeRevision("1");
    setSupersedeSnapshotId("");
    setSupersedeDigest("");
    setSupersedeLimitations("");
    setSupersedeNotes("");
  };

  const handleConfirmDialogAction = async () => {
    if (!verification || !dialogAction || !frozenConfirm) return;

    // Validate frozen confirmation
    if (
      frozenConfirm.lifetime !== contextLifetimeRef.current ||
      frozenConfirm.targetVerificationId !== verification.id ||
      frozenConfirm.targetRevision !== verification.revision ||
      frozenConfirm.targetCaseId !== preauditCase.id
    ) {
      setError("Confirmation state is stale or context changed");
      setDialogAction(null);
      setFrozenConfirm(null);
      return;
    }

    if (dialogAction !== "supersede" && !dialogReason.trim()) {
      setError("A reason or notes must be provided.");
      return;
    }

    if (dialogAction === "supersede") {
      if (!supersedeCaseId.trim() || !supersedeSnapshotId.trim() || !supersedeDigest.trim()) {
        setError("New pre-audit case ID, snapshot ID, and snapshot digest are required for supersession.");
        return;
      }
    }

    const actionToExecute = dialogAction;
    const targetVerId = verification.id;
    const targetRev = verification.revision;

    // Prevent fresh-ID resubmission of an already uncertain intent
    const existingUnresolved = uncertainOps.find(
      (o) => o.action === actionToExecute && o.targetVerificationId === targetVerId,
    );
    if (existingUnresolved) {
      setError(
        `A ${actionToExecute} operation is already pending/uncertain for this verification. Please retry the original operation or acknowledge disposal before submitting a new one.`,
      );
      setDialogAction(null);
      setFrozenConfirm(null);
      return;
    }

    const thisLifetime = contextLifetimeRef.current;
    const opId = getSecureUUID();
    activeOpIdRef.current = opId;
    setActionLoading(true);
    setError(null);

    let payload:
      | SuspendVerificationPayload
      | RevokeVerificationPayload
      | CorrectVerificationPayload
      | SupersedeVerificationPayload;
    if (actionToExecute === "suspend") {
      payload = {
        operation_id: opId,
        expected_revision: targetRev,
        reason: dialogReason.trim(),
      };
    } else if (actionToExecute === "revoke") {
      payload = {
        operation_id: opId,
        expected_revision: targetRev,
        reason: dialogReason.trim(),
      };
    } else if (actionToExecute === "correct") {
      payload = {
        operation_id: opId,
        expected_revision: targetRev,
        correction_notes: dialogReason.trim(),
      };
    } else if (actionToExecute === "supersede") {
      const parsedRev = parseInt(supersedeRevision, 10);
      payload = {
        operation_id: opId,
        expected_revision: targetRev,
        new_preaudit_id: supersedeCaseId.trim(),
        new_expected_case_revision: isNaN(parsedRev) || parsedRev < 1 ? 1 : parsedRev,
        new_snapshot_id: supersedeSnapshotId.trim(),
        new_snapshot_digest: supersedeDigest.trim(),
        limitations: supersedeLimitations.trim()
          ? supersedeLimitations.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
        notes: supersedeNotes.trim() || undefined,
      };
    } else {
      return;
    }

    try {
      if (actionToExecute === "suspend") {
        await suspendVerification(tenantId, targetVerId, payload as SuspendVerificationPayload, token);
      } else if (actionToExecute === "revoke") {
        await revokeVerification(tenantId, targetVerId, payload as RevokeVerificationPayload, token);
      } else if (actionToExecute === "correct") {
        await correctVerification(tenantId, targetVerId, payload as CorrectVerificationPayload, token);
      } else if (actionToExecute === "supersede") {
        await supersedeVerification(tenantId, targetVerId, payload as SupersedeVerificationPayload, token);
      }

      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      setDialogAction(null);
      setFrozenConfirm(null);
      setDialogReason("");
      setUncertainOps((prev) => prev.filter((o) => o.operationId !== opId));
      await loadVerificationData();
      if (thisLifetime !== contextLifetimeRef.current) return;
      onVerificationChange?.();
    } catch (err: unknown) {
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      setDialogAction(null);
      setFrozenConfirm(null);
      setDialogReason("");
      handleApiError(err, "Lifecycle action failed", thisLifetime);
      const is401 = err instanceof UnauthorizedError || (err as { status?: number })?.status === 401;
      if (!is401) {
        setUncertainOps((prev) => [
          ...prev.filter((o) => o.operationId !== opId),
          {
            operationId: opId,
            action: actionToExecute,
            payload,
            targetVerificationId: targetVerId,
            targetCaseId: preauditCase.id,
            label: `${actionToExecute.toUpperCase()} Verification`,
            errorText: getErrorMessage(err, "Action outcome uncertain"),
          },
        ]);
      }
    } finally {
      if (thisLifetime === contextLifetimeRef.current && activeOpIdRef.current === opId) {
        activeOpIdRef.current = null;
        setActionLoading(false);
      }
    }
  };

  const handleRetryOp = async (op: UncertainOp) => {
    if (op.targetCaseId !== preauditCase.id) {
      setError("Cross-context retry is forbidden. Please navigate to the original pre-audit case to retry this operation.");
      return;
    }

    const thisLifetime = contextLifetimeRef.current;
    const opId = op.operationId;
    activeOpIdRef.current = opId;
    setActionLoading(true);
    setError(null);
    try {
      if (op.action === "issue") {
        await issueVerification(tenantId, op.payload as IssueVerificationPayload, token);
      } else if (op.action === "suspend" && op.targetVerificationId) {
        await suspendVerification(tenantId, op.targetVerificationId, op.payload as SuspendVerificationPayload, token);
      } else if (op.action === "revoke" && op.targetVerificationId) {
        await revokeVerification(tenantId, op.targetVerificationId, op.payload as RevokeVerificationPayload, token);
      } else if (op.action === "correct" && op.targetVerificationId) {
        await correctVerification(tenantId, op.targetVerificationId, op.payload as CorrectVerificationPayload, token);
      } else if (op.action === "supersede" && op.targetVerificationId) {
        await supersedeVerification(tenantId, op.targetVerificationId, op.payload as SupersedeVerificationPayload, token);
      }

      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      setUncertainOps((prev) => prev.filter((o) => o.operationId !== op.operationId));
      await loadVerificationData();
      if (thisLifetime !== contextLifetimeRef.current) return;
      onVerificationChange?.();
    } catch (err: unknown) {
      if (thisLifetime !== contextLifetimeRef.current || activeOpIdRef.current !== opId) return;
      handleApiError(err, "Retry failed", thisLifetime);
    } finally {
      if (thisLifetime === contextLifetimeRef.current && activeOpIdRef.current === opId) {
        activeOpIdRef.current = null;
        setActionLoading(false);
      }
    }
  };

  const handleRequestDismissOp = (opId: string) => {
    setPendingDismissOpId(opId);
  };

  const handleConfirmDismissOp = (opId: string) => {
    setUncertainOps((prev) => prev.filter((o) => o.operationId !== opId));
    setPendingDismissOpId(null);
  };

  const handleCancelDismissOp = () => {
    setPendingDismissOpId(null);
  };

  const getStatusBadgeClass = (statusStr: string) => {
    switch (statusStr) {
      case "ACTIVE":
        return "verification-status-active";
      case "SUSPENDED":
        return "verification-status-suspended";
      case "REVOKED":
        return "verification-status-revoked";
      case "EXPIRED":
        return "verification-status-expired";
      case "SUPERSEDED":
        return "verification-status-superseded";
      default:
        return "verification-status-expired";
    }
  };

  // Only display uncertain ops belonging to the current preaudit case
  const currentCaseUncertainOps = uncertainOps.filter((o) => o.targetCaseId === preauditCase.id);

  return (
    <section className="verification-panel" data-testid="readiness-verification-panel">
      <div className="verification-header">
        <div className="verification-header-titles">
          <h3 className="verification-title">{t("customerDemo.verificationTitle")}</h3>
          <p className="verification-subtitle">{t("customerDemo.verificationSubtitle")}</p>
        </div>
      </div>

      <div className="verification-disclaimer" data-testid="verification-disclaimer">
        <span className="verification-disclaimer-icon">⚠️</span>
        <span>{t("customerDemo.verificationSyntheticDisclaimer")}</span>
      </div>

      {currentCaseUncertainOps.length > 0 && (
        <div
          style={{
            padding: "0.75rem 1rem",
            backgroundColor: "#fffbeb",
            color: "#92400e",
            borderRadius: "6px",
            border: "1px solid #fef3c7",
            fontSize: "0.875rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
          }}
          data-testid="uncertain-ops-banner"
        >
          <strong>{t("customerDemo.uncertaintyTitle")}</strong>
          {currentCaseUncertainOps.map((op) => (
            <div
              key={op.operationId}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "0.25rem",
                padding: "0.25rem 0",
              }}
              data-testid={`uncertain-op-${op.operationId}`}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <span>
                  {op.label}: {op.errorText}
                </span>
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="verification-btn verification-btn-primary"
                    style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                    onClick={() => handleRetryOp(op)}
                    disabled={actionLoading}
                    data-testid={`retry-op-${op.operationId}`}
                  >
                    {t("customerDemo.uncertaintyRetryBtn")}
                  </button>
                  <button
                    type="button"
                    className="verification-btn verification-btn-secondary"
                    style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                    onClick={() => handleRequestDismissOp(op.operationId)}
                    disabled={actionLoading}
                    data-testid={`dismiss-op-${op.operationId}`}
                  >
                    {t("customerDemo.uncertaintyDismissBtn")}
                  </button>
                </div>
              </div>

              {pendingDismissOpId === op.operationId && (
                <div
                  className="disposal-acknowledgement"
                  data-testid={`disposal-acknowledgement-${op.operationId}`}
                  style={{
                    padding: "0.5rem",
                    backgroundColor: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: "4px",
                    marginTop: "0.25rem",
                    fontSize: "0.8125rem",
                  }}
                >
                  <p style={{ margin: "0 0 0.5rem 0", color: "#991b1b" }}>
                    Acknowledged Disposal: This write may have already committed on the server. Disposing this item
                    does not cancel any server changes. Confirm disposal?
                  </p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      className="verification-btn verification-btn-secondary"
                      style={{
                        padding: "0.25rem 0.5rem",
                        fontSize: "0.75rem",
                        backgroundColor: "#dc2626",
                        color: "#fff",
                      }}
                      onClick={() => handleConfirmDismissOp(op.operationId)}
                      data-testid={`confirm-dismiss-${op.operationId}`}
                    >
                      Confirm Disposal
                    </button>
                    <button
                      type="button"
                      className="verification-btn verification-btn-secondary"
                      style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                      onClick={handleCancelDismissOp}
                      data-testid={`cancel-dismiss-${op.operationId}`}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div
          role="alert"
          style={{
            padding: "0.75rem 1rem",
            backgroundColor: "#fef2f2",
            color: "#991b1b",
            borderRadius: "6px",
            border: "1px solid #fecaca",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {loading && !verification && (
        <div className="verification-loading" data-testid="verification-loading">
          <div className="verification-spinner" />
          <span>{t("common.loading")}</span>
        </div>
      )}

      {!loading && !verification && (
        <div className="verification-empty-state" data-testid="verification-empty-state">
          <h4>{t("customerDemo.verificationEmptyTitle")}</h4>
          <p>{t("customerDemo.verificationEmptyDesc")}</p>

          {isOwner && preauditCase.status === "APPROVED" && (
            <div style={{ marginTop: "1rem" }}>
              <button
                type="button"
                className="verification-btn verification-btn-primary"
                onClick={handleIssue}
                disabled={actionLoading}
                data-testid="issue-verification-btn"
              >
                {actionLoading ? t("common.loading") : t("customerDemo.issueVerificationBtn")}
              </button>
            </div>
          )}
        </div>
      )}

      {verification && (
        <div className="verification-content" data-testid="verification-details-card">
          <div className="verification-card-header">
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <span className={`verification-status-badge ${getStatusBadgeClass(verification.status)}`} data-testid="verification-status-badge">
                {verification.status}
              </span>
              <span className={`verification-status-badge ${getStatusBadgeClass(verification.effective_status)}`} data-testid="verification-effective-badge">
                {verification.effective_status}
              </span>
              <span className="verification-revision">Rev {verification.revision}</span>
            </div>
            <div className="verification-actions">
              <button
                type="button"
                className="verification-btn verification-btn-secondary"
                onClick={handleToggleProjection}
                disabled={actionLoading}
                data-testid="toggle-projection-btn"
              >
                {showProjection
                  ? t("customerDemo.verificationHideProjection")
                  : t("customerDemo.verificationShowProjection")}
              </button>

              <button
                type="button"
                className="verification-btn verification-btn-secondary"
                onClick={handleReconcile}
                disabled={actionLoading}
                data-testid="reconcile-verification-btn"
              >
                {t("customerDemo.verificationReconcileBtn")}
              </button>

              {isOwner && verification.effective_status === "ACTIVE" && (
                <>
                  <button
                    type="button"
                    className="verification-btn verification-btn-secondary"
                    onClick={() => openActionDialog("suspend")}
                    disabled={actionLoading}
                    data-testid="suspend-verification-btn"
                  >
                    {t("customerDemo.verificationSuspendBtn")}
                  </button>
                  <button
                    type="button"
                    className="verification-btn verification-btn-secondary"
                    onClick={() => openActionDialog("correct")}
                    disabled={actionLoading}
                    data-testid="correct-verification-btn"
                  >
                    {t("customerDemo.verificationCorrectBtn")}
                  </button>
                  <button
                    type="button"
                    className="verification-btn verification-btn-secondary"
                    onClick={() => openActionDialog("supersede")}
                    disabled={actionLoading}
                    data-testid="supersede-verification-btn"
                  >
                    {t("customerDemo.verificationSupersedeBtn")}
                  </button>
                </>
              )}

              {isOwner && verification.effective_status === "SUSPENDED" && (
                <button
                  type="button"
                  className="verification-btn verification-btn-danger"
                  onClick={() => openActionDialog("revoke")}
                  disabled={actionLoading}
                  data-testid="revoke-verification-btn"
                >
                  {t("customerDemo.verificationRevokeBtn")}
                </button>
              )}
            </div>
          </div>

          <div className="verification-meta-grid">
            <div className="verification-meta-item">
              <label>{t("customerDemo.verificationId")}</label>
              <span>{verification.id}</span>
            </div>
            <div className="verification-meta-item">
              <label>{t("customerDemo.verificationIssuedAt")}</label>
              <span>{new Date(verification.issued_at).toLocaleString()}</span>
            </div>
            <div className="verification-meta-item">
              <label>{t("customerDemo.verificationValidThrough")}</label>
              <span>{new Date(verification.valid_through).toLocaleString()}</span>
            </div>
            <div className="verification-meta-item">
              <label>{t("customerDemo.verificationDigest")}</label>
              <span className="verification-digest-mono">{verification.digest.slice(0, 16)}...</span>
            </div>
          </div>

          {verification.effective_reason && (
            <div className="verification-effective-reason" data-testid="effective-reason-box">
              <strong>{t("customerDemo.verificationReasonTitle")}:</strong> {verification.effective_reason}
            </div>
          )}

          {verification.limitations && verification.limitations.length > 0 && (
            <div className="verification-limitations" data-testid="verification-limitations">
              <h5>{t("customerDemo.verificationLimitationsTitle")}</h5>
              <ul>
                {verification.limitations.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>
          )}

          {showProjection && projection && (
            <div className="verification-projection-box" data-testid="verification-projection-section">
              <h4>{t("customerDemo.verificationProjectionTitle")}</h4>
              <p className="verification-projection-disclaimer">{projection.test_qualification}</p>
              <div className="verification-projection-grid">
                <div>
                  <strong>{t("customerDemo.verificationFramework")}:</strong>{" "}
                  <span>
                    {projection.framework_display_name}
                    {projection.framework_version ? (projection.framework_version.startsWith("v") ? ` (${projection.framework_version})` : ` (v${projection.framework_version})`) : ""}
                  </span>
                </div>
                <div>
                  <strong>{t("customerDemo.verificationOrganization")}:</strong> <span>{projection.organization_display_name}</span>
                </div>
                <div>
                  <strong>{t("customerDemo.verificationControlsCount")}:</strong> <span>{projection.controls_count}</span>
                </div>
                <div>
                  <strong>{t("customerDemo.verificationCoveredCount")}:</strong>{" "}
                  <span>{String(projection.scope_summary?.covered_count ?? projection.controls_count)}</span>
                </div>
                <div>
                  <strong>{t("customerDemo.verificationExemptCount")}:</strong>{" "}
                  <span>{String(projection.scope_summary?.exempt_count ?? 0)}</span>
                </div>
                <div>
                  <strong>{t("customerDemo.verificationStatus")}:</strong> <span>{projection.effective_status}</span>
                </div>
              </div>
            </div>
          )}

          <div className="verification-history" data-testid="verification-history">
            <h4>{t("customerDemo.verificationHistoryTitle")}</h4>
            {history.length === 0 ? (
              <p className="verification-history-empty">{t("customerDemo.verificationNoHistory")}</p>
            ) : (
              <div className="verification-timeline" data-testid="verification-history-timeline">
                {history.map((ev) => (
                  <div key={ev.id} className="verification-timeline-item">
                    <span className="timeline-seq">#{ev.sequence}</span>
                    <span className="timeline-type">{ev.event_type}</span>
                    <span className="timeline-date">{new Date(ev.created_at).toLocaleString()}</span>
                    {ev.reason && <p className="timeline-reason">{ev.reason}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {dialogAction && (
        <div className="preaudit-modal-backdrop" data-testid="verification-action-modal">
          <div className="preaudit-modal">
            <h3>{dialogAction.toUpperCase()} Readiness Verification</h3>

            {dialogAction === "supersede" ? (
              <div className="preaudit-form">
                <div className="preaudit-form-group">
                  <label>New Pre-Audit Case ID *</label>
                  <input
                    type="text"
                    value={supersedeCaseId}
                    onChange={(e) => setSupersedeCaseId(e.target.value)}
                    data-testid="supersede-case-id-input"
                    placeholder="UUID of replacement approved case"
                  />
                </div>
                <div className="preaudit-form-group">
                  <label>New Expected Case Revision *</label>
                  <input
                    type="number"
                    value={supersedeRevision}
                    onChange={(e) => setSupersedeRevision(e.target.value)}
                    data-testid="supersede-case-rev-input"
                    min="1"
                  />
                </div>
                <div className="preaudit-form-group">
                  <label>New Review Snapshot ID *</label>
                  <input
                    type="text"
                    value={supersedeSnapshotId}
                    onChange={(e) => setSupersedeSnapshotId(e.target.value)}
                    data-testid="supersede-snapshot-id-input"
                    placeholder="UUID of replacement snapshot"
                  />
                </div>
                <div className="preaudit-form-group">
                  <label>New Review Snapshot Digest *</label>
                  <input
                    type="text"
                    value={supersedeDigest}
                    onChange={(e) => setSupersedeDigest(e.target.value)}
                    data-testid="supersede-digest-input"
                    placeholder="64-char SHA-256 hex digest"
                  />
                </div>
                <div className="preaudit-form-group">
                  <label>Limitations (comma separated)</label>
                  <input
                    type="text"
                    value={supersedeLimitations}
                    onChange={(e) => setSupersedeLimitations(e.target.value)}
                    data-testid="supersede-limitations-input"
                  />
                </div>
                <div className="preaudit-form-group">
                  <label>Notes</label>
                  <input
                    type="text"
                    value={supersedeNotes}
                    onChange={(e) => setSupersedeNotes(e.target.value)}
                    data-testid="supersede-notes-input"
                  />
                </div>
              </div>
            ) : (
              <div className="preaudit-form">
                <div className="preaudit-form-group">
                  <label>{dialogAction === "correct" ? "Correction Notes *" : "Reason *"}</label>
                  <textarea
                    rows={4}
                    value={dialogReason}
                    onChange={(e) => setDialogReason(e.target.value)}
                    data-testid="verification-dialog-textarea"
                    placeholder="Provide detailed justification..."
                  />
                </div>
              </div>
            )}

            <div className="preaudit-modal-actions">
              <button
                type="button"
                className="preaudit-btn preaudit-btn-secondary"
                onClick={() => {
                  setDialogAction(null);
                  setFrozenConfirm(null);
                }}
                disabled={actionLoading}
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                className="preaudit-btn preaudit-btn-primary"
                onClick={handleConfirmDialogAction}
                disabled={actionLoading}
                data-testid="verification-dialog-confirm-btn"
              >
                {actionLoading ? t("common.loading") : t("common.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
