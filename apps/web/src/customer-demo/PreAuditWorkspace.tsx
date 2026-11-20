/**
 * Conformly Customer Pre-audit Workspace (MVP-D).
 * Provides end-to-end workflow management for pre-audit cases:
 * - Case listing and creation with eligible lead/reviewer assignment
 * - Scope freeze, review submission, independent review, Owner approval, and cancellation
 * - Real-time blocker visibility with direct links to control/assessment work
 * - Private report archive download from frozen snapshot
 * - Immutable event history inspection
 */

import React, { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { ConflictError, UnauthorizedError } from "./api";
import {
  approvePreauditCase,
  cancelPreauditCase,
  createPreauditCase,
  downloadPreauditReport,
  fetchPreauditActors,
  freezePreauditScope,
  getPreauditCase,
  getPreauditHistory,
  listPreauditCases,
  recordReviewDecision,
  submitPreauditReview,
} from "./preaudit-api";
import {
  ApprovePreauditPayload,
  CancelPreauditPayload,
  CreatePreauditPayload,
  FreezeScopePayload,
  PreauditActor,
  PreauditCaseDetail,
  PreauditCaseSummary,
  PreauditEvent,
  PreauditStatus,
  ReviewDecisionPayload,
  SubmitReviewPayload,
} from "./preaudit-types";
import {
  ReadinessVerificationPanel,
  type UncertainOp as VerificationUncertainOp,
} from "./ReadinessVerificationPanel";
import { isVerificationEnabled } from "./verification-api";
import "./preaudit-workspace.css";

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
  throw new Error("Secure random UUID generation is not available");
}

export interface PreAuditWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  currentUserId?: string;
  adoptionId?: string;
  activeView?: string;
  onSessionExpired?: () => void;
  onNavigateToWork?: (workId: string, tab: string) => void;
}

export type UncertainOperation =
  | { action: "create"; operationId: string; payload: CreatePreauditPayload; error: string; caseId?: undefined }
  | { action: "freeze"; operationId: string; payload: FreezeScopePayload; error: string; caseId: string }
  | { action: "submit"; operationId: string; payload: SubmitReviewPayload; error: string; caseId: string }
  | { action: "review"; operationId: string; payload: ReviewDecisionPayload; error: string; caseId: string }
  | { action: "approve"; operationId: string; payload: ApprovePreauditPayload; error: string; caseId: string }
  | { action: "cancel"; operationId: string; payload: CancelPreauditPayload; error: string; caseId: string };

export const PreAuditWorkspace: FC<PreAuditWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  currentUserId,
  adoptionId = "",
  activeView,
  onSessionExpired,
  onNavigateToWork,
}) => {
  const { t } = useTranslation();

  // State
  const [summaries, setSummaries] = useState<PreauditCaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<PreauditCaseDetail | null>(null);
  const [actors, setActors] = useState<PreauditActor[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [historyEvents, setHistoryEvents] = useState<PreauditEvent[] | null>(null);
  const [showHistory, setShowHistory] = useState<boolean>(false);

  // Unresolved operations tracked independently per operation identity
  const [uncertainOps, setUncertainOps] = useState<UncertainOperation[]>([]);
  const [verificationUncertainOps, setVerificationUncertainOps] = useState<VerificationUncertainOp[]>([]);
  const [abandonTargetOp, setAbandonTargetOp] = useState<UncertainOperation | null>(null);

  const recordUncertainOp = (op: UncertainOperation) => {
    setUncertainOps((prev) => {
      const idx = prev.findIndex((o) => o.operationId === op.operationId);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = op;
        return copy;
      }
      return [...prev, op];
    });
  };

  const settleUncertainOp = (operationId: string) => {
    setUncertainOps((prev) => prev.filter((o) => o.operationId !== operationId));
  };

  // Modal Dialogs & Frozen Confirmation Intent
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [createLeadId, setCreateLeadId] = useState<string>("");
  const [createReviewerId, setCreateReviewerId] = useState<string>("");
  const [createTitle, setCreateTitle] = useState<string>("");
  const [createDescription, setCreateDescription] = useState<string>("");

  const [showReviewModal, setShowReviewModal] = useState<boolean>(false);
  const [reviewDecision, setReviewDecision] = useState<"ACCEPT" | "REQUEST_CHANGES">("ACCEPT");
  const [reviewNotes, setReviewNotes] = useState<string>("");
  const [frozenReviewIntent, setFrozenReviewIntent] = useState<{
    lifetime: number;
    reqId: number;
    caseId: string;
    expectedRevision: number;
    snapshotId: string;
    snapshotDigest: string;
    operationId: string;
  } | null>(null);

  const [showApproveModal, setShowApproveModal] = useState<boolean>(false);
  const [approvalNotes, setApprovalNotes] = useState<string>("");
  const [frozenApproveIntent, setFrozenApproveIntent] = useState<{
    lifetime: number;
    reqId: number;
    caseId: string;
    expectedRevision: number;
    snapshotId: string;
    snapshotDigest: string;
    operationId: string;
  } | null>(null);

  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>("");
  const [frozenCancelIntent, setFrozenCancelIntent] = useState<{
    lifetime: number;
    reqId: number;
    caseId: string;
    expectedRevision: number;
    operationId: string;
  } | null>(null);

  const [showAbandonConfirm, setShowAbandonConfirm] = useState<boolean>(false);
  const [abandonAcknowledged, setAbandonAcknowledged] = useState<boolean>(false);

  const normalizedRole = typeof userRole === "string" ? userRole.trim().toLowerCase() : "";
  const isOwner = normalizedRole === "owner";

  const contextLifetimeRef = useRef<number>(0);
  const caseRequestIdRef = useRef<number>(0);
  const selectedCaseIdRef = useRef<string | null>(null);
  const activeMutationIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);



  const isAssignedLead = Boolean(
    activeCase && currentUserId && activeCase.lead_user_id === currentUserId,
  );
  const isAssignedReviewer = Boolean(
    activeCase && currentUserId && activeCase.reviewer_user_id === currentUserId,
  );

  const hasActiveCaseUncertain = Boolean(
    activeCase && uncertainOps.some((o) => o.caseId === activeCase.id),
  );
  const hasCreateUncertain = uncertainOps.some((o) => o.action === "create");

  function isNetworkError(err: unknown): boolean {
    if (err instanceof TypeError) return true;
    if (err && typeof err === "object") {
      const status = (err as { status?: number }).status;
      if (status === 0 || status === 502 || status === 503 || status === 504) return true;
      const msg = String((err as { message?: unknown }).message || "").toLowerCase();
      if (
        msg.includes("network") ||
        msg.includes("fetch") ||
        msg.includes("timeout") ||
        msg.includes("failed to fetch") ||
        msg.includes("aborted")
      ) {
        return true;
      }
    }
    return false;
  }

  // Context fencing on replacement: clean unmount & cancel in-flight requests
  useEffect(() => {
    const lifetime = ++contextLifetimeRef.current;
    let ignore = false;
    const ac = new AbortController();
    abortControllerRef.current = ac;

    const run = async () => {
      if (ignore || contextLifetimeRef.current !== lifetime) return;
      setIsLoading(true);
      setIsSubmitting(false);
      setIsDetailLoading(false);
      setErrorMsg(null);
      setSuccessMsg(null);
      setSummaries([]);
      selectedCaseIdRef.current = null;
      setSelectedCaseId(null);
      setActiveCase(null);
      setActors([]);
      setHistoryEvents(null);
      setShowHistory(false);
      setShowCreateModal(false);
      setShowReviewModal(false);
      setShowApproveModal(false);
      setShowCancelModal(false);
      setFrozenReviewIntent(null);
      setFrozenApproveIntent(null);
      setFrozenCancelIntent(null);
      setUncertainOps([]);
      setVerificationUncertainOps([]);
      setAbandonTargetOp(null);
      setShowAbandonConfirm(false);
      setAbandonAcknowledged(false);

      try {
        const [caseListRes, actorList] = await Promise.all([
          listPreauditCases(tenantId, token, ac.signal),
          fetchPreauditActors(tenantId, token, ac.signal),
        ]);
        if (ignore || contextLifetimeRef.current !== lifetime) return;
        setSummaries(caseListRes.items);
        setActors(actorList);

        const firstId = caseListRes.items[0]?.id ?? null;
        selectedCaseIdRef.current = firstId;
        setSelectedCaseId(firstId);
        if (firstId) {
          const reqId = ++caseRequestIdRef.current;
          setIsDetailLoading(true);
          try {
            const detail = await getPreauditCase(tenantId, firstId, token, ac.signal);
            if (!ignore && contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId) {
              setActiveCase(detail);
            }
          } catch (err: unknown) {
            if (ignore || contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) return;
            if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
              onSessionExpired?.();
              return;
            }
            setErrorMsg(getErrorMessage(err, "Failed to load case detail"));
          } finally {
            if (!ignore && contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId) {
              setIsDetailLoading(false);
            }
          }
        }
      } catch (err: unknown) {
        if (ignore || contextLifetimeRef.current !== lifetime) return;
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to load pre-audit cases"));
      } finally {
        if (!ignore && contextLifetimeRef.current === lifetime) setIsLoading(false);
      }
    };

    void run();

    return () => {
      ignore = true;
      ac.abort();
      contextLifetimeRef.current += 1;
      setIsSubmitting(false);
      setIsDetailLoading(false);
      setUncertainOps([]);
      setVerificationUncertainOps([]);
      setAbandonTargetOp(null);
      setShowAbandonConfirm(false);
      setAbandonAcknowledged(false);
    };
  }, [tenantId, token, userRole, currentUserId, adoptionId, activeView, onSessionExpired]);

  // Load single case details when user selects a case
  const handleSelectCase = async (caseId: string) => {
    const lifetime = contextLifetimeRef.current;
    const reqId = ++caseRequestIdRef.current;
    selectedCaseIdRef.current = caseId;
    setSelectedCaseId(caseId);
    setActiveCase(null);
    setShowHistory(false);
    setHistoryEvents(null);
    setShowReviewModal(false);
    setFrozenReviewIntent(null);
    setShowApproveModal(false);
    setFrozenApproveIntent(null);
    setShowCancelModal(false);
    setFrozenCancelIntent(null);
    setErrorMsg(null);
    setSuccessMsg(null);
    setIsSubmitting(false);
    setIsDetailLoading(true);
    try {
      const detail = await getPreauditCase(tenantId, caseId, token);
      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) return;
      setActiveCase(detail);
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) return;
      if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
        onSessionExpired?.();
        return;
      }
      setErrorMsg(getErrorMessage(err, "Failed to load case details"));
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId) {
        setIsDetailLoading(false);
      }
    }
  };

  // Load history when toggled
  const handleToggleHistory = async () => {
    if (!activeCase) return;
    if (showHistory) {
      setShowHistory(false);
      return;
    }
    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const targetCaseId = activeCase.id;
    setErrorMsg(null);
    try {
      const hist = await getPreauditHistory(tenantId, targetCaseId, token);
      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) return;
      setHistoryEvents(hist.events);
      setShowHistory(true);
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) return;
      if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
        onSessionExpired?.();
        return;
      }
      setErrorMsg(getErrorMessage(err, "Failed to load history"));
    }
  };

  // 1. Create Pre-audit Case
  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || hasCreateUncertain) return;
    if (!createLeadId || !createReviewerId) {
      setErrorMsg("Lead and Reviewer must be selected");
      return;
    }
    if (createLeadId === createReviewerId) {
      setErrorMsg("Lead and Reviewer must be different individuals");
      return;
    }
    const targetAdoption = adoptionId || (summaries[0]?.adoption_id ?? "");
    if (!targetAdoption) {
      setErrorMsg("No active framework adoption found");
      return;
    }

    const lifetime = contextLifetimeRef.current;
    const mutId = ++activeMutationIdRef.current;
    setIsSubmitting(true);
    setErrorMsg(null);
    const opId = getSecureUUID();
    const payload = {
      operation_id: opId,
      adoption_id: targetAdoption,
      lead_user_id: createLeadId,
      reviewer_user_id: createReviewerId,
      title: createTitle.trim() || undefined,
      description: createDescription.trim() || undefined,
    };

    try {
      const created = await createPreauditCase(tenantId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      settleUncertainOp(opId);
      const summaryItem: PreauditCaseSummary = {
        id: created.id,
        tenant_id: created.tenant_id,
        adoption_id: created.adoption_id,
        pack_name: created.pack_name,
        pack_version: created.pack_version,
        lead_user_id: created.lead_user_id,
        reviewer_user_id: created.reviewer_user_id,
        status: created.status,
        revision: created.revision,
        title: created.title || `Case ${created.id.slice(0, 8)}`,
        created_at: created.created_at,
        updated_at: created.updated_at,
      };
      setSummaries((prev) => [summaryItem, ...prev.filter((c) => c.id !== created.id)]);
      selectedCaseIdRef.current = created.id;
      setSelectedCaseId(created.id);
      setActiveCase(created);
      setShowCreateModal(false);
      setCreateTitle("");
      setCreateDescription("");
      setSuccessMsg("Pre-audit case created successfully");
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "create",
          operationId: opId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Case creation outcome is uncertain."),
        });
      }
      if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
        onSessionExpired?.();
        return;
      }
      setErrorMsg(getErrorMessage(err, "Failed to create pre-audit case"));
    } finally {
      if (contextLifetimeRef.current === lifetime && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 2. Freeze Scope (Assigned Lead only)
  const handleFreezeScope = async () => {
    if (!activeCase || !isAssignedLead || hasActiveCaseUncertain || isSubmitting) return;
    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const targetCaseId = activeCase.id;
    setIsSubmitting(true);
    setErrorMsg(null);
    const opId = getSecureUUID();
    const payload = {
      operation_id: opId,
      expected_revision: activeCase.revision,
    };
    try {
      const updated = await freezePreauditScope(tenantId, targetCaseId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      settleUncertainOp(opId);
      setSummaries((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s)),
      );
      if (caseRequestIdRef.current === reqId) {
        setActiveCase(updated);
        setSuccessMsg("Scope frozen into snapshot");
      }
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "freeze",
          operationId: opId,
          caseId: targetCaseId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Scope freeze outcome is uncertain."),
        });
      }
      if (caseRequestIdRef.current === reqId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to freeze scope"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 3. Submit Review (Assigned Lead only)
  const handleSubmitReview = async () => {
    if (!activeCase || !isAssignedLead || hasActiveCaseUncertain || isSubmitting) return;
    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const targetCaseId = activeCase.id;
    setIsSubmitting(true);
    setErrorMsg(null);
    const opId = getSecureUUID();
    const payload = {
      operation_id: opId,
      expected_revision: activeCase.revision,
      submission_notes: "Submitted for independent review",
    };
    try {
      const updated = await submitPreauditReview(tenantId, targetCaseId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      settleUncertainOp(opId);
      setSummaries((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s)),
      );
      if (caseRequestIdRef.current === reqId) {
        setActiveCase(updated);
        setSuccessMsg("Submitted for review");
      }
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "submit",
          operationId: opId,
          caseId: targetCaseId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Review submission outcome is uncertain."),
        });
      }
      if (caseRequestIdRef.current === reqId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to submit review"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 4. Open Review Modal (Freezes intent context)
  const handleOpenReviewModal = () => {
    if (!activeCase || !activeCase.current_review_snapshot_id || !activeCase.current_review_snapshot_digest) {
      setErrorMsg("Case has no frozen review snapshot");
      return;
    }
    setFrozenReviewIntent({
      lifetime: contextLifetimeRef.current,
      reqId: caseRequestIdRef.current,
      caseId: activeCase.id,
      expectedRevision: activeCase.revision,
      snapshotId: activeCase.current_review_snapshot_id,
      snapshotDigest: activeCase.current_review_snapshot_digest,
      operationId: getSecureUUID(),
    });
    setReviewNotes("");
    setReviewDecision("ACCEPT");
    setShowReviewModal(true);
  };

  // Record Review Decision
  const handleReviewDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frozenReviewIntent || hasActiveCaseUncertain || isSubmitting) return;
    if (
      !activeCase ||
      frozenReviewIntent.lifetime !== contextLifetimeRef.current ||
      frozenReviewIntent.reqId !== caseRequestIdRef.current ||
      activeCase.id !== frozenReviewIntent.caseId ||
      activeCase.revision !== frozenReviewIntent.expectedRevision ||
      activeCase.current_review_snapshot_id !== frozenReviewIntent.snapshotId
    ) {
      setErrorMsg("Case state mutated since confirmation; review intent invalidated");
      setShowReviewModal(false);
      setFrozenReviewIntent(null);
      return;
    }
    if (!reviewNotes.trim()) {
      setErrorMsg("Review notes are required");
      return;
    }

    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const targetCaseId = frozenReviewIntent.caseId;
    setIsSubmitting(true);
    setErrorMsg(null);
    const payload = {
      operation_id: frozenReviewIntent.operationId,
      expected_revision: frozenReviewIntent.expectedRevision,
      snapshot_id: frozenReviewIntent.snapshotId,
      snapshot_digest: frozenReviewIntent.snapshotDigest,
      decision: reviewDecision,
      notes: reviewNotes.trim(),
    };
    try {
      const updated = await recordReviewDecision(tenantId, targetCaseId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      setSummaries((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s)),
      );
      if (caseRequestIdRef.current === reqId) {
        setActiveCase(updated);
        setSuccessMsg(reviewDecision === "ACCEPT" ? "Review accepted" : "Changes requested from lead");
      }
      settleUncertainOp(frozenReviewIntent.operationId);
      setShowReviewModal(false);
      setFrozenReviewIntent(null);
      setReviewNotes("");
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "review",
          operationId: frozenReviewIntent.operationId,
          caseId: targetCaseId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Review decision outcome is uncertain."),
        });
      }
      if (caseRequestIdRef.current === reqId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to record review decision"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 5. Open Approve Modal (Freezes intent context)
  const handleOpenApproveModal = () => {
    if (!activeCase || !activeCase.current_review_snapshot_id || !activeCase.current_review_snapshot_digest) {
      setErrorMsg("Missing review snapshot for approval");
      return;
    }
    setFrozenApproveIntent({
      lifetime: contextLifetimeRef.current,
      reqId: caseRequestIdRef.current,
      caseId: activeCase.id,
      expectedRevision: activeCase.revision,
      snapshotId: activeCase.current_review_snapshot_id,
      snapshotDigest: activeCase.current_review_snapshot_digest,
      operationId: getSecureUUID(),
    });
    setApprovalNotes("");
    setShowApproveModal(true);
  };

  // Owner Approve
  const handleApproveCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frozenApproveIntent || hasActiveCaseUncertain || isSubmitting) return;
    if (
      !activeCase ||
      frozenApproveIntent.lifetime !== contextLifetimeRef.current ||
      frozenApproveIntent.reqId !== caseRequestIdRef.current ||
      activeCase.id !== frozenApproveIntent.caseId ||
      activeCase.revision !== frozenApproveIntent.expectedRevision ||
      activeCase.current_review_snapshot_id !== frozenApproveIntent.snapshotId
    ) {
      setErrorMsg("Case state mutated since confirmation; approval intent invalidated");
      setShowApproveModal(false);
      setFrozenApproveIntent(null);
      return;
    }

    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const targetCaseId = frozenApproveIntent.caseId;
    setIsSubmitting(true);
    setErrorMsg(null);
    const payload = {
      operation_id: frozenApproveIntent.operationId,
      expected_revision: frozenApproveIntent.expectedRevision,
      snapshot_id: frozenApproveIntent.snapshotId,
      snapshot_digest: frozenApproveIntent.snapshotDigest,
      approval_notes: approvalNotes.trim() || undefined,
    };
    try {
      const updated = await approvePreauditCase(tenantId, targetCaseId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      setSummaries((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s)),
      );
      if (caseRequestIdRef.current === reqId) {
        setActiveCase(updated);
        setSuccessMsg("Pre-audit approved by tenant Owner");
      }
      settleUncertainOp(frozenApproveIntent.operationId);
      setShowApproveModal(false);
      setFrozenApproveIntent(null);
      setApprovalNotes("");
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "approve",
          operationId: frozenApproveIntent.operationId,
          caseId: targetCaseId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Approval outcome is uncertain."),
        });
      }
      if (caseRequestIdRef.current === reqId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to approve pre-audit"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 6. Open Cancel Modal (Freezes intent context)
  const handleOpenCancelModal = () => {
    if (!activeCase) return;
    setFrozenCancelIntent({
      lifetime: contextLifetimeRef.current,
      reqId: caseRequestIdRef.current,
      caseId: activeCase.id,
      expectedRevision: activeCase.revision,
      operationId: getSecureUUID(),
    });
    setCancelReason("");
    setShowCancelModal(true);
  };

  // Cancel Case
  const handleCancelCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!frozenCancelIntent || hasActiveCaseUncertain || isSubmitting) return;
    if (
      !activeCase ||
      frozenCancelIntent.lifetime !== contextLifetimeRef.current ||
      frozenCancelIntent.reqId !== caseRequestIdRef.current ||
      activeCase.id !== frozenCancelIntent.caseId ||
      activeCase.revision !== frozenCancelIntent.expectedRevision
    ) {
      setErrorMsg("Case state mutated since confirmation; cancellation intent invalidated");
      setShowCancelModal(false);
      setFrozenCancelIntent(null);
      return;
    }
    if (!cancelReason.trim()) {
      setErrorMsg("Cancellation reason is required");
      return;
    }

    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const targetCaseId = frozenCancelIntent.caseId;
    setIsSubmitting(true);
    setErrorMsg(null);
    const payload = {
      operation_id: frozenCancelIntent.operationId,
      expected_revision: frozenCancelIntent.expectedRevision,
      reason: cancelReason.trim(),
    };
    try {
      const updated = await cancelPreauditCase(tenantId, targetCaseId, payload, token);
      if (contextLifetimeRef.current !== lifetime) return;
      setSummaries((prev) =>
        prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s)),
      );
      if (caseRequestIdRef.current === reqId) {
        setActiveCase(updated);
        setSuccessMsg("Pre-audit case cancelled");
      }
      settleUncertainOp(frozenCancelIntent.operationId);
      setShowCancelModal(false);
      setFrozenCancelIntent(null);
      setCancelReason("");
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (isNetworkError(err)) {
        recordUncertainOp({
          action: "cancel",
          operationId: frozenCancelIntent.operationId,
          caseId: targetCaseId,
          payload,
          error: getErrorMessage(err, "Network connection lost. Cancellation outcome is uncertain."),
        });
      }
      if (caseRequestIdRef.current === reqId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Failed to cancel case"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // 7. Download Private Report
  const handleDownloadReport = async () => {
    if (!activeCase) {
      setErrorMsg("No active pre-audit case selected for download");
      return;
    }
    const clickCaseId = activeCase.id;
    const clickRevision = activeCase.revision;
    const clickSnapshotId = activeCase.current_review_snapshot_id;
    const clickSnapshotDigest = activeCase.current_review_snapshot_digest;

    if (!clickSnapshotId || !clickSnapshotDigest) {
      setErrorMsg("No frozen review snapshot available for report download");
      return;
    }

    const lifetime = contextLifetimeRef.current;
    const reqId = caseRequestIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    const ac = new AbortController();

    setIsSubmitting(true);
    setErrorMsg(null);
    let objectUrl: string | null = null;
    try {
      const res = await downloadPreauditReport(
        tenantId,
        clickCaseId,
        {
          expected_revision: clickRevision,
          snapshot_id: clickSnapshotId,
          expected_snapshot_digest: clickSnapshotDigest,
        },
        token,
        ac.signal,
      );

      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) {
        return;
      }

      objectUrl = window.URL.createObjectURL(res.blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setSuccessMsg("Private report archive downloaded");
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime || caseRequestIdRef.current !== reqId) {
        return;
      }
      if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
        onSessionExpired?.();
        return;
      }
      setErrorMsg(getErrorMessage(err, "Failed to download report archive"));
    } finally {
      if (objectUrl) {
        window.URL.revokeObjectURL(objectUrl);
      }
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === reqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  // Uncertain write recovery actions
  const handleRetryUncertain = async (target?: UncertainOperation) => {
    const targetOp = (target && 'operationId' in target) ? target : uncertainOps[0];
    if (!targetOp) return;
    const lifetime = contextLifetimeRef.current;
    const startReqId = caseRequestIdRef.current;
    const startCaseId = selectedCaseIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      let updated: PreauditCaseDetail;
      if (targetOp.action === "create") {
        updated = await createPreauditCase(tenantId, targetOp.payload, token);
      } else if (targetOp.action === "freeze") {
        updated = await freezePreauditScope(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "submit") {
        updated = await submitPreauditReview(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "review") {
        updated = await recordReviewDecision(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "approve") {
        updated = await approvePreauditCase(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "cancel") {
        updated = await cancelPreauditCase(tenantId, targetOp.caseId, targetOp.payload, token);
      } else {
        throw new Error("Unknown action in uncertain retry");
      }

      if (contextLifetimeRef.current !== lifetime) return;

      // Settle ONLY this matching operation intent
      settleUncertainOp(targetOp.operationId);

      const summaryItem: PreauditCaseSummary = {
        id: updated.id,
        tenant_id: updated.tenant_id,
        adoption_id: updated.adoption_id,
        pack_name: updated.pack_name,
        pack_version: updated.pack_version,
        lead_user_id: updated.lead_user_id,
        reviewer_user_id: updated.reviewer_user_id,
        status: updated.status,
        revision: updated.revision,
        title: updated.title || `Case ${updated.id.slice(0, 8)}`,
        created_at: updated.created_at,
        updated_at: updated.updated_at,
      };

      setSummaries((prev) => {
        const found = prev.find((s) => s.id === updated.id);
        if (found) {
          return prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s));
        }
        return [summaryItem, ...prev];
      });

      // Check live monotonic selection admission before altering active view
      if (caseRequestIdRef.current === startReqId && selectedCaseIdRef.current === startCaseId) {
        if (!selectedCaseIdRef.current || selectedCaseIdRef.current === updated.id) {
          selectedCaseIdRef.current = updated.id;
          setSelectedCaseId(updated.id);
          setActiveCase(updated);
        }
        setSuccessMsg(
          updated.replayed
            ? `Server confirmed operation was already applied (Event ${updated.applied_event_id ? String(updated.applied_event_id).slice(0, 8) : "recorded"}, Revision ${updated.applied_revision ?? updated.revision})`
            : "Operation completed successfully upon retry",
        );
      }
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (caseRequestIdRef.current === startReqId && selectedCaseIdRef.current === startCaseId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        setErrorMsg(getErrorMessage(err, "Retry failed; outcome remains uncertain"));
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === startReqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  const handleResolveUncertain = async (target?: UncertainOperation) => {
    const targetOp = (target && 'operationId' in target) ? target : uncertainOps[0];
    if (!targetOp) return;
    const lifetime = contextLifetimeRef.current;
    const startReqId = caseRequestIdRef.current;
    const startCaseId = selectedCaseIdRef.current;
    const mutId = ++activeMutationIdRef.current;
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      let updated: PreauditCaseDetail;
      if (targetOp.action === "create") {
        updated = await createPreauditCase(tenantId, targetOp.payload, token);
      } else if (targetOp.action === "freeze") {
        updated = await freezePreauditScope(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "submit") {
        updated = await submitPreauditReview(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "review") {
        updated = await recordReviewDecision(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "approve") {
        updated = await approvePreauditCase(tenantId, targetOp.caseId, targetOp.payload, token);
      } else if (targetOp.action === "cancel") {
        updated = await cancelPreauditCase(tenantId, targetOp.caseId, targetOp.payload, token);
      } else {
        throw new Error("Unknown action in uncertain resolve");
      }

      if (contextLifetimeRef.current !== lifetime) return;

      // Settle ONLY this matching operation intent
      settleUncertainOp(targetOp.operationId);

      const summaryItem: PreauditCaseSummary = {
        id: updated.id,
        tenant_id: updated.tenant_id,
        adoption_id: updated.adoption_id,
        pack_name: updated.pack_name,
        pack_version: updated.pack_version,
        lead_user_id: updated.lead_user_id,
        reviewer_user_id: updated.reviewer_user_id,
        status: updated.status,
        revision: updated.revision,
        title: updated.title || `Case ${updated.id.slice(0, 8)}`,
        created_at: updated.created_at,
        updated_at: updated.updated_at,
      };

      setSummaries((prev) => {
        const found = prev.find((s) => s.id === updated.id);
        if (found) {
          return prev.map((s) => (s.id === updated.id ? { ...s, status: updated.status, revision: updated.revision } : s));
        }
        return [summaryItem, ...prev];
      });

      // Check live monotonic selection admission before altering active view
      if (caseRequestIdRef.current === startReqId && selectedCaseIdRef.current === startCaseId) {
        if (!selectedCaseIdRef.current || selectedCaseIdRef.current === updated.id) {
          selectedCaseIdRef.current = updated.id;
          setSelectedCaseId(updated.id);
          setActiveCase(updated);
        }
        setSuccessMsg(
          updated.replayed
            ? `Reconciled: server confirmed operation was applied previously (Event ${updated.applied_event_id ? String(updated.applied_event_id).slice(0, 8) : "recorded"}, Revision ${updated.applied_revision ?? updated.revision})`
            : `Reconciled: operation committed upon reconciliation (Revision ${updated.revision})`,
        );
      }
    } catch (err: unknown) {
      if (contextLifetimeRef.current !== lifetime) return;
      if (caseRequestIdRef.current === startReqId && selectedCaseIdRef.current === startCaseId) {
        if (err instanceof UnauthorizedError || (err && (err as { status?: number }).status === 401)) {
          onSessionExpired?.();
          return;
        }
        if (err instanceof ConflictError || (err && (err as { status?: number }).status === 409)) {
          setErrorMsg(getErrorMessage(err, "Operation conflict detected on server; outcome remains unresolved"));
        } else {
          setErrorMsg(getErrorMessage(err, "Reconciliation failed; outcome remains uncertain"));
        }
      }
    } finally {
      if (contextLifetimeRef.current === lifetime && caseRequestIdRef.current === startReqId && activeMutationIdRef.current === mutId) {
        setIsSubmitting(false);
      }
    }
  };

  const handleAbandonUncertain = (target?: UncertainOperation) => {
    const targetOp = (target && 'operationId' in target) ? target : uncertainOps[0];
    if (!targetOp) return;
    setAbandonTargetOp(targetOp);
    setShowAbandonConfirm(true);
    setAbandonAcknowledged(false);
  };

  const handleConfirmAbandon = () => {
    if (!abandonAcknowledged || !abandonTargetOp) return;
    const targetId = abandonTargetOp.operationId;
    settleUncertainOp(targetId);
    setShowAbandonConfirm(false);
    setAbandonAcknowledged(false);
    setAbandonTargetOp(null);
    setErrorMsg("Uncertain operation intent disposed. Note: Any write already committed on the server remains in effect and was not cancelled.");
  };


  const getStatusBadgeClass = (status: PreauditStatus) => {
    switch (status) {
      case "DRAFT":
        return "preaudit-badge-draft";
      case "FROZEN":
        return "preaudit-badge-frozen";
      case "IN_REVIEW":
        return "preaudit-badge-in_review";
      case "CHANGES_REQUESTED":
        return "preaudit-badge-changes_requested";
      case "REVIEWED":
        return "preaudit-badge-reviewed";
      case "APPROVED":
        return "preaudit-badge-approved";
      case "CANCELLED":
        return "preaudit-badge-cancelled";
      default:
        return "preaudit-badge-draft";
    }
  };

  if (isLoading && summaries.length === 0) {
    return (
      <div className="preaudit-workspace" data-testid="preaudit-workspace-loading">
        <p>{t("common.loading")}</p>
      </div>
    );
  }

  return (
    <div className="preaudit-workspace" data-testid="preaudit-workspace">
      {/* Header */}
      <div className="preaudit-header">
        <div className="preaudit-header-titles">
          <h2>{t("customerDemo.preauditTitle")}</h2>
          <p>{t("customerDemo.preauditSubtitle")}</p>
        </div>
        <div className="preaudit-header-actions">
          <button
            type="button"
            className="preaudit-btn preaudit-btn-primary"
            onClick={() => {
              setShowCreateModal(true);
              if (actors.length > 0) {
                setCreateLeadId(actors[0].user_id);
                setCreateReviewerId(actors.length > 1 ? actors[1].user_id : "");
              }
            }}
            data-testid="create-preaudit-case-btn"
          >
            {t("customerDemo.createPreauditBtn")}
          </button>
        </div>
      </div>

      {/* Uncertain Write Recovery Banners */}
      {uncertainOps.length > 0 && (
        <div className="uncertain-operations-container">
          {uncertainOps.map((op) => (
            <div
              key={op.operationId}
              className="preaudit-alert preaudit-alert-warning"
              role="alert"
              data-testid="uncertain-operation-alert"
            >
              <div className="uncertain-alert-body">
                <strong>Network Loss — Outcome Uncertain</strong>
                <p>{op.error}</p>
                <p>
                  The server may have committed this operation. You can retry with the identical payload, inspect the server outcome, or explicitly abandon this intent.
                </p>
                <div className="uncertain-actions" style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                  <button
                    type="button"
                    className="preaudit-btn preaudit-btn-primary"
                    onClick={() => handleRetryUncertain(op)}
                    disabled={isSubmitting}
                    data-testid="uncertain-retry-btn"
                  >
                    Retry (Exact Payload)
                  </button>
                  <button
                    type="button"
                    className="preaudit-btn preaudit-btn-secondary"
                    onClick={() => handleResolveUncertain(op)}
                    disabled={isSubmitting || isDetailLoading}
                    data-testid="uncertain-resolve-btn"
                  >
                    Check Outcome
                  </button>
                  <button
                    type="button"
                    className="preaudit-btn preaudit-btn-secondary"
                    onClick={() => handleAbandonUncertain(op)}
                    disabled={isSubmitting}
                    data-testid="uncertain-abandon-btn"
                  >
                    Abandon & New Intent
                  </button>
                </div>
                {showAbandonConfirm && abandonTargetOp?.operationId === op.operationId && (
                  <div
                    className="uncertain-abandon-dialog"
                    data-testid="uncertain-abandon-dialog"
                    style={{ marginTop: "12px", padding: "10px", background: "rgba(0,0,0,0.05)", borderRadius: "4px" }}
                  >
                    <p style={{ margin: "0 0 8px 0", color: "#c0392b" }}>
                      Warning: This operation may have already committed on the server. Discarding this intent does not cancel or revert any committed changes.
                    </p>
                    <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", marginBottom: "8px" }}>
                      <input
                        type="checkbox"
                        data-testid="uncertain-abandon-acknowledge-checkbox"
                        checked={abandonAcknowledged}
                        onChange={(e) => setAbandonAcknowledged(e.target.checked)}
                      />
                      <span>I acknowledge that this write may have committed on the server and that disposal does not cancel it.</span>
                    </label>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        type="button"
                        className="preaudit-btn preaudit-btn-danger"
                        data-testid="uncertain-confirm-abandon-btn"
                        disabled={!abandonAcknowledged}
                        onClick={handleConfirmAbandon}
                      >
                        Confirm Intent Disposal
                      </button>
                      <button
                        type="button"
                        className="preaudit-btn preaudit-btn-secondary"
                        onClick={() => {
                          setShowAbandonConfirm(false);
                          setAbandonAcknowledged(false);
                          setAbandonTargetOp(null);
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Notifications */}
      {errorMsg && (
        <div className="preaudit-alert preaudit-alert-error" role="alert" data-testid="preaudit-error-alert">
          <span>{errorMsg}</span>
          <button
            type="button"
            className="preaudit-btn preaudit-btn-secondary"
            onClick={() => setErrorMsg(null)}
          >
            {t("common.dismiss")}
          </button>
        </div>
      )}

      {successMsg && (
        <div className="preaudit-alert preaudit-alert-info" role="status" data-testid="preaudit-success-alert">
          <span>{successMsg}</span>
          <button
            type="button"
            className="preaudit-btn preaudit-btn-secondary"
            onClick={() => setSuccessMsg(null)}
          >
            {t("common.dismiss")}
          </button>
        </div>
      )}

      {/* Case Selector if multiple cases */}
      {summaries.length > 1 && (
        <div className="preaudit-form-group">
          <label htmlFor="preaudit-case-select">Select Pre-audit Case:</label>
          <select
            id="preaudit-case-select"
            className="preaudit-select"
            value={selectedCaseId || ""}
            onChange={(e) => void handleSelectCase(e.target.value)}
            data-testid="preaudit-case-select"
          >
            {summaries.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title || `Pre-audit (${c.pack_name})`} — {c.status} (Rev {c.revision})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Main Case Card */}
      {!activeCase ? (
        <div className="preaudit-case-card" data-testid="preaudit-no-cases">
          {isDetailLoading ? <p>{t("common.loading")}</p> : <p>{t("customerDemo.preauditNoCases")}</p>}
        </div>
      ) : (
        <div className="preaudit-case-card" data-testid="preaudit-active-case-card">
          <div className="preaudit-case-card-header">
            <div className="preaudit-case-title-area">
              <h3>{activeCase.title || `Pre-audit: ${activeCase.pack_name} v${activeCase.pack_version}`}</h3>
              {activeCase.description && <p>{activeCase.description}</p>}
              <div className="preaudit-case-meta">
                <span className="preaudit-meta-item">
                  <strong>{t("customerDemo.preauditLeadLabel")}:</strong> {activeCase.lead_name}
                </span>
                <span className="preaudit-meta-item">
                  <strong>{t("customerDemo.preauditReviewerLabel")}:</strong> {activeCase.reviewer_name}
                </span>
                <span className="preaudit-meta-item">
                  <strong>{t("customerDemo.preauditRevisionLabel")}:</strong> {activeCase.revision}
                </span>
              </div>
            </div>
            <div>
              <span
                className={`preaudit-badge ${getStatusBadgeClass(activeCase.status)}`}
                data-testid="preaudit-status-badge"
              >
                {activeCase.status}
              </span>
            </div>
          </div>

          {/* Stale warnings */}
          {!activeCase.is_scope_current && activeCase.status !== "APPROVED" && activeCase.status !== "CANCELLED" && (
            <div className="preaudit-alert preaudit-alert-warning" data-testid="stale-scope-warning">
              Framework adoption or scope selection has changed since this case was initiated.
            </div>
          )}
          {!activeCase.is_review_current && (activeCase.status === "IN_REVIEW" || activeCase.status === "REVIEWED") && (
            <div className="preaudit-alert preaudit-alert-warning" data-testid="stale-review-warning">
              Underlying compliance work or evidence has been modified after review snapshot creation.
            </div>
          )}

          {/* Blockers Section */}
          <div className="preaudit-card-section">
            <div className="preaudit-card-section-title">
              {t("customerDemo.preauditBlockersTitle")} ({activeCase.blockers.length})
            </div>
            {activeCase.blockers.length === 0 ? (
              <p style={{ color: "#16a34a", fontSize: "0.875rem", margin: 0 }}>
                No active pre-audit blockers. Case is ready for review.
              </p>
            ) : (
              <div className="preaudit-blockers-container" data-testid="preaudit-blockers-list">
                {activeCase.blockers.map((b, i) => (
                  <div key={i} className="preaudit-blocker-item" data-testid="preaudit-blocker-item">
                    <span className="preaudit-blocker-code">[{b.code}]</span>
                    <span>{b.description}</span>
                    {b.work_id && onNavigateToWork && (
                      <button
                        type="button"
                        className="preaudit-blocker-link"
                        onClick={() => onNavigateToWork(b.work_id!, "assessment")}
                        data-testid={`blocker-nav-link-${b.control_code || i}`}
                      >
                        View Assessment &rarr;
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Workflow Action Buttons */}
          <div className="preaudit-card-section">
            <div className="preaudit-card-section-title">{t("common.actions")}</div>
            <div className="preaudit-workflow-actions">
              {/* DRAFT -> Freeze Scope (Assigned Lead only) */}
              {activeCase.status === "DRAFT" && isAssignedLead && (
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-primary"
                  onClick={handleFreezeScope}
                  disabled={isSubmitting || hasActiveCaseUncertain}
                  data-testid="freeze-scope-btn"
                >
                  {t("customerDemo.freezeScopeBtn")}
                </button>
              )}

              {/* FROZEN or CHANGES_REQUESTED -> Submit for Review (Assigned Lead only) */}
              {(activeCase.status === "FROZEN" || activeCase.status === "CHANGES_REQUESTED") &&
                isAssignedLead && (
                  <button
                    type="button"
                    className="preaudit-btn preaudit-btn-primary"
                    onClick={handleSubmitReview}
                    disabled={isSubmitting || hasActiveCaseUncertain}
                    data-testid="submit-review-btn"
                  >
                    {t("customerDemo.submitPreauditReviewBtn")}
                  </button>
                )}

              {/* IN_REVIEW -> Record Decision (Assigned Reviewer only) */}
              {activeCase.status === "IN_REVIEW" && isAssignedReviewer && (
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-primary"
                  onClick={handleOpenReviewModal}
                  disabled={isSubmitting || hasActiveCaseUncertain}
                  data-testid="record-review-decision-btn"
                >
                  Record Review Decision
                </button>
              )}

              {/* REVIEWED -> Owner Approve (Owner who is not reviewer) */}
              {activeCase.status === "REVIEWED" && isOwner && !isAssignedReviewer && (
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-success"
                  onClick={handleOpenApproveModal}
                  disabled={isSubmitting || hasActiveCaseUncertain}
                  data-testid="approve-preaudit-btn"
                >
                  {t("customerDemo.approvePreauditBtn")}
                </button>
              )}

              {/* Download Report (if review snapshot exists) */}
              {activeCase.current_review_snapshot_id && (
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-secondary"
                  onClick={handleDownloadReport}
                  disabled={isSubmitting}
                  data-testid="download-preaudit-report-btn"
                >
                  {t("customerDemo.downloadReportBtn")}
                </button>
              )}

              {/* Toggle History */}
              <button
                type="button"
                className="preaudit-btn preaudit-btn-secondary"
                onClick={handleToggleHistory}
                data-testid="toggle-history-btn"
              >
                {showHistory ? "Hide History" : t("customerDemo.preauditHistoryTitle")}
              </button>

              {/* Cancel Case (Owner only, while active) */}
              {isOwner && activeCase.status !== "APPROVED" && activeCase.status !== "CANCELLED" && (
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-danger"
                  onClick={handleOpenCancelModal}
                  disabled={isSubmitting || hasActiveCaseUncertain}
                  data-testid="cancel-preaudit-btn"
                >
                  {t("customerDemo.cancelPreauditBtn")}
                </button>
              )}
            </div>
          </div>

          {/* Immutable Event History */}
          {showHistory && (
            <div className="preaudit-card-section" data-testid="preaudit-history-section">
              <div className="preaudit-card-section-title">{t("customerDemo.preauditHistoryTitle")}</div>
              {!historyEvents || historyEvents.length === 0 ? (
                <p>{t("common.loading")}</p>
              ) : (
                <div className="preaudit-history-list" data-testid="preaudit-history-list">
                  {historyEvents.map((ev) => (
                    <div key={ev.id} className="preaudit-history-item" data-testid="preaudit-history-item">
                      <span className="preaudit-history-type">
                        {ev.event_type} (Rev {ev.revision})
                      </span>
                      <span className="preaudit-history-time">
                        {new Date(ev.created_at).toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {isVerificationEnabled() && activeCase && (
            <ReadinessVerificationPanel
              tenantId={tenantId}
              token={token}
              preauditCase={activeCase}
              isOwner={isOwner}
              userRole={userRole}
              currentUserId={currentUserId}
              adoptionId={adoptionId || activeCase.adoption_id}
              activeView={activeView}
              uncertainOps={verificationUncertainOps}
              onUncertainOpsChange={setVerificationUncertainOps}
              onVerificationChange={() => {
                if (selectedCaseIdRef.current === activeCase.id) {
                  handleSelectCase(activeCase.id);
                }
              }}
              onSessionExpired={onSessionExpired}
            />
          )}
        </div>
      )}

      {/* Modal: Create Case */}
      {showCreateModal && (
        <div className="preaudit-modal-backdrop" data-testid="create-case-modal">
          <div className="preaudit-modal">
            <h3>{t("customerDemo.createPreauditBtn")}</h3>
            <form onSubmit={handleCreateCase}>
              <div className="preaudit-form-group">
                <label htmlFor="create-case-title">Title (Optional):</label>
                <input
                  id="create-case-title"
                  type="text"
                  className="preaudit-input"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  placeholder="e.g. Q4 SOC2 Readiness Review"
                  data-testid="create-case-title-input"
                />
              </div>
              <div className="preaudit-form-group">
                <label htmlFor="create-case-desc">Description (Optional):</label>
                <textarea
                  id="create-case-desc"
                  className="preaudit-textarea"
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  placeholder="Review objectives and context"
                  data-testid="create-case-desc-input"
                />
              </div>
              <div className="preaudit-form-group">
                <label htmlFor="create-case-lead">{t("customerDemo.preauditLeadLabel")}:</label>
                <select
                  id="create-case-lead"
                  className="preaudit-select"
                  value={createLeadId}
                  onChange={(e) => setCreateLeadId(e.target.value)}
                  required
                  data-testid="create-case-lead-select"
                >
                  <option value="">-- Select Assigned Lead --</option>
                  {actors.map((a) => (
                    <option key={a.user_id} value={a.user_id}>
                      {a.display_name} ({a.email}) — {a.role}
                    </option>
                  ))}
                </select>
              </div>
              <div className="preaudit-form-group">
                <label htmlFor="create-case-reviewer">{t("customerDemo.preauditReviewerLabel")}:</label>
                <select
                  id="create-case-reviewer"
                  className="preaudit-select"
                  value={createReviewerId}
                  onChange={(e) => setCreateReviewerId(e.target.value)}
                  required
                  data-testid="create-case-reviewer-select"
                >
                  <option value="">-- Select Independent Reviewer --</option>
                  {actors.map((a) => (
                    <option key={a.user_id} value={a.user_id}>
                      {a.display_name} ({a.email}) — {a.role}
                    </option>
                  ))}
                </select>
              </div>
              <div className="preaudit-modal-actions">
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  className="preaudit-btn preaudit-btn-primary"
                  disabled={isSubmitting || hasCreateUncertain}
                  data-testid="submit-create-case-btn"
                >
                  {t("common.save")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Review Decision */}
      {showReviewModal && frozenReviewIntent && (
        <div className="preaudit-modal-backdrop" data-testid="review-decision-modal">
          <div className="preaudit-modal">
            <h3>Record Independent Review Decision</h3>
            <p style={{ fontSize: "0.85rem", color: "#64748b" }}>
              Frozen snapshot digest: <code>{frozenReviewIntent.snapshotDigest.slice(0, 16)}...</code>
            </p>
            <form onSubmit={handleReviewDecision}>
              <div className="preaudit-form-group">
                <label>Review Decision:</label>
                <div style={{ display: "flex", gap: "1rem", marginTop: "0.25rem" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <input
                      type="radio"
                      name="decision"
                      value="ACCEPT"
                      checked={reviewDecision === "ACCEPT"}
                      onChange={() => setReviewDecision("ACCEPT")}
                      data-testid="decision-accept-radio"
                    />
                    Accept (All requirements satisfied)
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <input
                      type="radio"
                      name="decision"
                      value="REQUEST_CHANGES"
                      checked={reviewDecision === "REQUEST_CHANGES"}
                      onChange={() => setReviewDecision("REQUEST_CHANGES")}
                      data-testid="decision-changes-radio"
                    />
                    Request Changes
                  </label>
                </div>
              </div>
              <div className="preaudit-form-group">
                <label htmlFor="review-notes">Review Notes / Remediation Feedback:</label>
                <textarea
                  id="review-notes"
                  className="preaudit-textarea"
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="Record verification rationale or specific control remediation required"
                  required
                  data-testid="review-notes-input"
                />
              </div>
              <div className="preaudit-modal-actions">
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-secondary"
                  onClick={() => {
                    setShowReviewModal(false);
                    setFrozenReviewIntent(null);
                  }}
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  className="preaudit-btn preaudit-btn-primary"
                  disabled={isSubmitting}
                  data-testid="submit-review-decision-btn"
                >
                  Submit Decision
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Approve Case */}
      {showApproveModal && frozenApproveIntent && (
        <div className="preaudit-modal-backdrop" data-testid="approve-case-modal">
          <div className="preaudit-modal">
            <h3>{t("customerDemo.approvePreauditBtn")}</h3>
            <p style={{ fontSize: "0.875rem", color: "#334155" }}>
              Are you sure you want to approve this pre-audit case? This marks the review as completed.
            </p>
            <form onSubmit={handleApproveCase}>
              <div className="preaudit-form-group">
                <label htmlFor="approve-notes">Owner Approval Notes (Optional):</label>
                <textarea
                  id="approve-notes"
                  className="preaudit-textarea"
                  value={approvalNotes}
                  onChange={(e) => setApprovalNotes(e.target.value)}
                  placeholder="Record formal executive review sign-off"
                  data-testid="approve-notes-input"
                />
              </div>
              <div className="preaudit-modal-actions">
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-secondary"
                  onClick={() => {
                    setShowApproveModal(false);
                    setFrozenApproveIntent(null);
                  }}
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  className="preaudit-btn preaudit-btn-success"
                  disabled={isSubmitting}
                  data-testid="confirm-approve-btn"
                >
                  {t("customerDemo.approvePreauditBtn")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Cancel Case */}
      {showCancelModal && frozenCancelIntent && (
        <div className="preaudit-modal-backdrop" data-testid="cancel-case-modal">
          <div className="preaudit-modal">
            <h3>{t("customerDemo.cancelPreauditBtn")}</h3>
            <p style={{ fontSize: "0.875rem", color: "#dc2626" }}>
              Cancellation is permanent and cannot be undone.
            </p>
            <form onSubmit={handleCancelCase}>
              <div className="preaudit-form-group">
                <label htmlFor="cancel-reason">Cancellation Reason:</label>
                <textarea
                  id="cancel-reason"
                  className="preaudit-textarea"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="Provide explicit cancellation rationale"
                  required
                  data-testid="cancel-reason-input"
                />
              </div>
              <div className="preaudit-modal-actions">
                <button
                  type="button"
                  className="preaudit-btn preaudit-btn-secondary"
                  onClick={() => {
                    setShowCancelModal(false);
                    setFrozenCancelIntent(null);
                  }}
                >
                  {t("common.cancel")}
                </button>
                <button
                  type="submit"
                  className="preaudit-btn preaudit-btn-danger"
                  disabled={isSubmitting}
                  data-testid="confirm-cancel-btn"
                >
                  {t("customerDemo.cancelPreauditBtn")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
