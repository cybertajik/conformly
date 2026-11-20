import React, { useState, useEffect, useCallback, useRef } from "react";
import type { TenantRole } from "@conformly/shared";
import { useTranslation } from "../i18n/I18nContext";
import { canManagePolicies, canReadPolicies } from "../permissions";
import {
  ConflictError,
  CustomerDemoApiError,
  ForbiddenError,
  UnauthorizedError,
  ValidationError,
} from "./api";
import {
  fetchPolicies,
  fetchPolicy,
  createPolicy,
  updatePolicy,
  submitPolicyReview,
  approvePolicy,
  publishPolicy,
  archivePolicy,
  fetchPolicyRevisions,
  acknowledgePolicy,
  fetchPolicyAcknowledgements,
} from "./operations-api";
import {
  Policy,
  PolicyCreateInput,
  PolicyUpdateInput,
  PolicyRevision,
  PolicyAcknowledgement,
  PolicyClassification,
} from "./operations-types";
import * as taskApi from "./task-api";
import { ComplianceTask, CreateTaskInput, TaskPriority } from "./task-types";


export interface PolicyWorkspaceV2Props {
  tenantId: string;
  token: string;
  userRole?: string;
  currentUserId?: string;
  policies: Policy[];
  loading?: boolean;
  onRefresh?: () => Promise<void> | void;
  onSessionExpired?: () => void;
  onPolicyMutated?: (updated: Policy) => void;
  onPolicyCreated?: (created: Policy) => void;
  onTaskCreated?: (task: ComplianceTask) => void;
  targetPolicyId?: string | null;
  targetNonce?: number | null;
  onConsumeTarget?: () => void;
}

export const PolicyWorkspaceV2: React.FC<PolicyWorkspaceV2Props> = ({
  tenantId,
  token,
  userRole = "owner",
  currentUserId,
  policies = [],
  loading = false,
  onRefresh,
  onSessionExpired,
  onPolicyMutated,
  onPolicyCreated,
  onTaskCreated,
  targetPolicyId = null,
  targetNonce = null,
  onConsumeTarget,
}) => {
  const { t } = useTranslation();

  const canManage = canManagePolicies(userRole as TenantRole);
  const isRoleDenied = !canReadPolicies(userRole as TenantRole);

  // Workspace View State
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [selectedStatusFilter, setSelectedStatusFilter] = useState<string>("all");

  // Revisions & Acknowledgements State
  const [revisions, setRevisions] = useState<PolicyRevision[]>([]);
  const [acknowledgements, setAcknowledgements] = useState<PolicyAcknowledgement[]>([]);
  const [loadingRevs, setLoadingRevs] = useState<boolean>(false);

  // Policy Detail State
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Form State for Editing Selected Policy
  const [editTitle, setEditTitle] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [editVersionString, setEditVersionString] = useState<string>("");
  const [editReviewCycle, setEditReviewCycle] = useState<number>(365);
  const [editContent, setEditContent] = useState<string>("");
  const [editClassification, setEditClassification] = useState<PolicyClassification>("Internal");
  const [hasEditChanges, setHasEditChanges] = useState<boolean>(false);

  // Concurrency & Server Version Tracking
  const [conflictOccurred, setConflictOccurred] = useState<boolean>(false);
  const [serverVersion, setServerVersion] = useState<number>(1);
  void serverVersion;

  // Creation Modal / Form State
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newVersionString, setNewVersionString] = useState<string>("1.0");
  const [newReviewCycle, setNewReviewCycle] = useState<number>(365);
  const [newContent, setNewContent] = useState<string>("");
  const [newClassification, setNewClassification] = useState<PolicyClassification>("Internal");
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Priority 1 & 2: Authoritative snapshot and pinned base version
  const [authoritativeDetail, setAuthoritativeDetail] = useState<Policy | null>(null);
  const authoritativeDetailRef = useRef<Policy | null>(null);
  useEffect(() => {
    authoritativeDetailRef.current = authoritativeDetail;
  }, [authoritativeDetail]);

  const [editorBaseVersion, setEditorBaseVersion] = useState<number>(1);
  const editorBaseVersionRef = useRef<number>(1);
  useEffect(() => {
    editorBaseVersionRef.current = editorBaseVersion;
  }, [editorBaseVersion]);

  const [hasAuthoritativeBody, setHasAuthoritativeBody] = useState<boolean>(false);
  const [bodyUnavailable, setBodyUnavailable] = useState<boolean>(false);
  const [isBodyDirty, setIsBodyDirty] = useState<boolean>(false);
  const isBodyDirtyRef = useRef<boolean>(false);
  useEffect(() => {
    isBodyDirtyRef.current = isBodyDirty;
  }, [isBodyDirty]);
  const [showFollowupModal, setShowFollowupModal] = useState<boolean>(false);
  const [followupTitle, setFollowupTitle] = useState<string>("");
  const [followupDesc, setFollowupDesc] = useState<string>("");
  const [followupDueDate, setFollowupDueDate] = useState<string>("");
  const [followupPriority, setFollowupPriority] = useState<TaskPriority>("medium");
  const [followupSubmitting, setFollowupSubmitting] = useState<boolean>(false);
  const [followupError, setFollowupError] = useState<string | null>(null);

  // Uncertain follow-up create recovery state
  const [uncertainFollowup, setUncertainFollowup] = useState<{
    payload: CreateTaskInput;
    reconciled?: boolean;
    matchingTask?: ComplianceTask | null;
    ambiguous?: boolean;
    incomplete?: boolean;
    attemptId: number;
  } | null>(null);
  const [reconcilingFollowup, setReconcilingFollowup] = useState<boolean>(false);
  const [reconcileFollowupError, setReconcileFollowupError] = useState<string | null>(null);
  const followupAttemptIdRef = useRef<number>(0);

  // Priority 3: Guarded dirty switch
  const [pendingSwitchPolicyId, setPendingSwitchPolicyId] = useState<string | null>(null);

  // Uncertain POST create recovery state
  const [uncertainCreate, setUncertainCreate] = useState<{
    payload: PolicyCreateInput;
    reconciled?: boolean;
    matchingPolicy?: Policy | null;
    attemptId: number;
  } | null>(null);
  const [reconciling, setReconciling] = useState<boolean>(false);
  const [reconcileError, setReconcileError] = useState<string | null>(null);

  // Action feedback states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Generational fencing refs
  const lastSelectedPolicyIdRef = useRef<string | null>(null);
  const hasEditChangesRef = useRef<boolean>(false);
  useEffect(() => {
    hasEditChangesRef.current = hasEditChanges;
  }, [hasEditChanges]);

  const isMountedRef = useRef<boolean>(true);
  const detailAbortControllerRef = useRef<AbortController | null>(null);
  const detailGenRef = useRef<number>(0);
  const revsAbortControllerRef = useRef<AbortController | null>(null);
  const revsGenRef = useRef<number>(0);
  const mutationGenRef = useRef<number>(0);
  const createAttemptIdRef = useRef<number>(0);
  const followupReconcileAbortRef = useRef<AbortController | null>(null);
  const followupCreateAbortRef = useRef<AbortController | null>(null);

  const contextRef = useRef({ tenantId, token });
  useEffect(() => {
    contextRef.current = { tenantId, token };
  }, [tenantId, token]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      detailAbortControllerRef.current?.abort();
      revsAbortControllerRef.current?.abort();
      followupReconcileAbortRef.current?.abort();
      followupCreateAbortRef.current?.abort();
    };
  }, []);

  // Find currently selected policy object from props
  const selectedPolicy = policies.find((p) => p.id === selectedPolicyId) || null;
  const selectedPolicyRef = useRef<Policy | null>(selectedPolicy);
  useEffect(() => {
    selectedPolicyRef.current = selectedPolicy;
  }, [selectedPolicy]);

  const selectedPolicyIdRef = useRef<string | null>(selectedPolicyId);
  useEffect(() => {
    selectedPolicyIdRef.current = selectedPolicyId;
  }, [selectedPolicyId]);

  // Calendar navigation target effect
  const consumedTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!targetPolicyId) return;
      if (loading) return;
      const targetKey = `${targetPolicyId}:${targetNonce ?? "static"}`;
      if (targetKey === consumedTargetKeyRef.current) return;
      const exists = policies.some((p) => p.id === targetPolicyId);
      if (exists) {
        consumedTargetKeyRef.current = targetKey;
        onConsumeTarget?.();
        if (hasEditChanges && selectedPolicyId && selectedPolicyId !== targetPolicyId) {
          setPendingSwitchPolicyId(targetPolicyId);
        } else {
          setSelectedPolicyId(targetPolicyId);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [targetPolicyId, targetNonce, onConsumeTarget, loading, policies, hasEditChanges, selectedPolicyId]);

  // Context fencing: invalidate in-flight follow-up attempts and clear uncertain state immediately on tenant, token, or selected policy change
  useEffect(() => {
    followupReconcileAbortRef.current?.abort();
    followupCreateAbortRef.current?.abort();
    followupAttemptIdRef.current++;
    const timer = setTimeout(() => {
      setUncertainFollowup(null);
      setReconcilingFollowup(false);
      setReconcileFollowupError(null);
    }, 0);
    return () => clearTimeout(timer);
  }, [tenantId, token, selectedPolicy?.id]);

  // Load Policy Detail with explicit authoritative snapshot
  const loadPolicyDetail = useCallback(
    async (policyId: string, forceOverwrite: boolean = false) => {
      if (!tenantId || !token || !policyId) return;

      if (detailAbortControllerRef.current) {
        detailAbortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      detailAbortControllerRef.current = abortController;
      const currentGen = ++detailGenRef.current;

      setLoadingDetail(true);
      setDetailError(null);

      try {
        const detail = await fetchPolicy(tenantId, token, policyId, abortController.signal);
        if (currentGen !== detailGenRef.current) return;
        if (policyId !== selectedPolicyIdRef.current) return;

        lastSelectedPolicyIdRef.current = policyId;
        authoritativeDetailRef.current = detail;
        setAuthoritativeDetail(detail);
        setEditorBaseVersion(detail.version);
        setServerVersion(detail.version);

        // Always hydrate body if user hasn't dirtied it, keeping editor and base version aligned
        if (!isBodyDirtyRef.current || forceOverwrite) {
          setEditContent(detail.restricted_content || detail.content || "");
          setIsBodyDirty(false);
          setHasAuthoritativeBody(true);
          setBodyUnavailable(false);
        }

        // Populate metadata fields only if there are no dirty unsaved changes in progress
        if (!hasEditChangesRef.current || forceOverwrite) {
          setEditTitle(detail.title);
          setEditDesc(detail.description);
          setEditVersionString(detail.version_string);
          setEditReviewCycle(detail.review_cycle_days);
          setEditClassification(detail.classification);
          setHasEditChanges(false);
        }
        setConflictOccurred(false);
        setActionError(null);
      } catch (err: unknown) {
        if (!isMountedRef.current || abortController.signal.aborted || currentGen !== detailGenRef.current || tenantId !== contextRef.current.tenantId || token !== contextRef.current.token) return;

        if (err instanceof UnauthorizedError) {
          if (isMountedRef.current && token === contextRef.current.token && tenantId === contextRef.current.tenantId) {
            onSessionExpired?.();
          }
          return;
        }

        setDetailError("Failed to load policy details.");
        setHasAuthoritativeBody(false);
        setBodyUnavailable(true);
        authoritativeDetailRef.current = null;
        setAuthoritativeDetail(null);

        // Priority 1: A list row is not an authoritative protected body!
        const fallbackPolicy = selectedPolicyRef.current;
        if (fallbackPolicy && fallbackPolicy.id === policyId) {
          lastSelectedPolicyIdRef.current = policyId;
          setEditorBaseVersion(fallbackPolicy.version);
          setServerVersion(fallbackPolicy.version);
          if (!hasEditChangesRef.current || forceOverwrite) {
            setEditTitle(fallbackPolicy.title);
            setEditDesc(fallbackPolicy.description);
            setEditVersionString(fallbackPolicy.version_string);
            setEditReviewCycle(fallbackPolicy.review_cycle_days);
            setEditClassification(fallbackPolicy.classification);
            // Leave content empty and marked unavailable
            setEditContent("");
          }
        }
      } finally {
        if (currentGen === detailGenRef.current) {
          setLoadingDetail(false);
        }
      }
    },
    [tenantId, token, onSessionExpired]
  );

  // Trigger detail hydration when selectedPolicyId changes
  useEffect(() => {
    if (!selectedPolicyId || !tenantId || !token) {
      const timer = setTimeout(() => {
        lastSelectedPolicyIdRef.current = null;
        setAuthoritativeDetail(null);
        authoritativeDetailRef.current = null;
        setHasAuthoritativeBody(false);
        setBodyUnavailable(false);
        setIsBodyDirty(false);
        setEditTitle("");
        setEditDesc("");
        setEditVersionString("");
        setEditReviewCycle(365);
        setEditContent("");
        setEditClassification("Internal");
        setHasEditChanges(false);
        setRevisions([]);
        setAcknowledgements([]);
      }, 0);
      return () => clearTimeout(timer);
    }

    // If same policy is selected and has dirty edits, preserve them!
    if (selectedPolicyId === lastSelectedPolicyIdRef.current && hasEditChangesRef.current) {
      return;
    }

    void loadPolicyDetail(selectedPolicyId);
  }, [selectedPolicyId, tenantId, token, loadPolicyDetail]);

  // Load revisions and acknowledgements when a policy is selected
  const loadRevsAndAcks = useCallback(
    async (policyId: string) => {
      if (!tenantId || !token || !policyId) return;

      if (revsAbortControllerRef.current) {
        revsAbortControllerRef.current.abort();
      }
      const abortController = new AbortController();
      revsAbortControllerRef.current = abortController;
      const currentGen = ++revsGenRef.current;

      setLoadingRevs(true);
      setRevisions([]);
      setAcknowledgements([]);

      try {
        const [revData, ackData] = await Promise.all([
          fetchPolicyRevisions(tenantId, token, policyId, abortController.signal),
          fetchPolicyAcknowledgements(tenantId, token, policyId, abortController.signal),
        ]);
        if (currentGen !== revsGenRef.current) return;
        if (policyId !== selectedPolicyIdRef.current) return;

        setRevisions(revData);
        setAcknowledgements(ackData);
      } catch (err: unknown) {
        if (!isMountedRef.current || abortController.signal.aborted || currentGen !== revsGenRef.current || tenantId !== contextRef.current.tenantId || token !== contextRef.current.token) return;
        if (err instanceof UnauthorizedError) {
          if (isMountedRef.current && token === contextRef.current.token && tenantId === contextRef.current.tenantId) {
            onSessionExpired?.();
          }
          return;
        }
      } finally {
        if (currentGen === revsGenRef.current) {
          setLoadingRevs(false);
        }
      }
    },
    [tenantId, token, onSessionExpired]
  );

  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedPolicyId) {
        void loadRevsAndAcks(selectedPolicyId);
      } else {
        setRevisions([]);
        setAcknowledgements([]);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedPolicyId, selectedPolicy?.status, selectedPolicy?.version, loadRevsAndAcks]);

  // Filter policies list
  const filteredPolicies = policies.filter((p) => {
    if (selectedStatusFilter === "all") return true;
    return p.status === selectedStatusFilter;
  });

  // Check if current actor identity is known and matches policy owner
  const isAuthor = Boolean(
    currentUserId &&
      selectedPolicy?.owner_user_id &&
      currentUserId === selectedPolicy.owner_user_id
  );

  // Author cannot self-approve; only a distinct approver can approve
  const canApprove = canManage && !isAuthor;
  void canApprove;

  // Check if current user has already acknowledged the selected policy
  const hasCurrentUserAcknowledged = Boolean(
    currentUserId && acknowledgements.some((a) => a.user_id === currentUserId)
  );

  // Handle Policy Creation
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || createSubmitting || Boolean(uncertainCreate)) return;

    if (!newTitle.trim()) {
      setCreateError(t("portal.entityNameRequired") || "Title is required.");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    // Protected narrative routing: Restricted or Confidential body routes to restricted_content
    const isProtected =
      newClassification === "Restricted" ||
      (newClassification === "Confidential" && Boolean(newContent.trim()));

    const payload: PolicyCreateInput = {
      title: newTitle.trim(),
      description: newDesc.trim() || newTitle.trim(),
      version_string: newVersionString.trim() || "1.0",
      review_cycle_days: Number(newReviewCycle) || 365,
      classification: newClassification,
      content: isProtected ? "" : (newContent.trim() || null),
      restricted_content: isProtected ? newContent.trim() : null,
    };

    try {
      const created = await createPolicy(tenantId, token, payload);
      onPolicyCreated?.(created);
      setIsCreating(false);
      setNewTitle("");
      setNewDesc("");
      setNewContent("");
      setSelectedPolicyId(created.id);
      setActionSuccess(`Policy created: ${created.title}`);
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      const isDefinite =
        err instanceof ValidationError ||
        err instanceof ForbiddenError ||
        (err instanceof CustomerDemoApiError && [400, 401, 403, 409, 422].includes(err.status));

      if (isDefinite) {
        setCreateError(err instanceof Error ? err.message : "Failed to create policy");
      } else {
        // Transport error (TypeError), AbortError, malformed 2xx, 5xx server failure
        setUncertainCreate({
          payload,
          reconciled: false,
          matchingPolicy: null,
          attemptId: ++createAttemptIdRef.current,
        });
        setCreateError(
          t("portal.uncertainCreateNotice") ||
            "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."
        );
      }
    } finally {
      setCreateSubmitting(false);
    }
  };

  // Reconcile uncertain create via fresh scoped GET and full payload comparison
  const handleReconcileCreate = async () => {
    if (!uncertainCreate || reconciling) return;
    const attemptId = uncertainCreate.attemptId;
    const attemptTenantId = tenantId;
    const attemptToken = token;

    setReconciling(true);
    setReconcileError(null);
    try {
      const freshList = await fetchPolicies(attemptTenantId, attemptToken);
      if (
        attemptId !== createAttemptIdRef.current ||
        attemptTenantId !== contextRef.current.tenantId ||
        attemptToken !== contextRef.current.token
      ) {
        return;
      }
      const match = freshList.find(
        (p) =>
          p.title.trim().toLowerCase() === uncertainCreate.payload.title.trim().toLowerCase() &&
          p.description.trim() === uncertainCreate.payload.description.trim() &&
          p.classification === uncertainCreate.payload.classification
      );
      setUncertainCreate({
        ...uncertainCreate,
        reconciled: true,
        matchingPolicy: match || null,
      });
    } catch (err: unknown) {
      if (attemptId !== createAttemptIdRef.current) return;
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setReconcileError(err instanceof Error ? err.message : "Failed to fetch server state");
    } finally {
      if (attemptId === createAttemptIdRef.current) {
        setReconciling(false);
      }
    }
  };

  // Confirm match from reconciliation
  const handleConfirmReconcile = (matched: Policy) => {
    setSelectedPolicyId(matched.id);
    setUncertainCreate(null);
    setIsCreating(false);
    setActionSuccess(`${t("portal.reconciledSuccess")} (${matched.title})`);
  };

  // Discard uncertain create attempt
  const handleDiscardUncertainCreate = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
    setIsCreating(false);
    setNewTitle("");
    setNewDesc("");
    setNewContent("");
  };

  // Allow resubmit after confirmed no duplicate
  const handleAllowResubmit = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
  };

  // Handle Save Draft (Update)
  const handleSaveDraft = async () => {
    if (!selectedPolicy || !canManage || actionLoading) return;

    setActionLoading("save");
    setActionError(null);
    setActionSuccess(null);

    const mutatingId = selectedPolicy.id;
    const mutationGen = ++mutationGenRef.current;

    // Protected narrative routing: Restricted or Confidential routes to restricted_content
    const isProtected =
      editClassification === "Restricted" ||
      (editClassification === "Confidential" && Boolean(editContent.trim()));

    // Priority 2: Use pinned base version editorBaseVersionRef.current, NOT selectedPolicy.version!
    const payload: PolicyUpdateInput = {
      expected_version: editorBaseVersionRef.current,
      title: editTitle.trim(),
      description: editDesc.trim(),
      version_string: editVersionString.trim(),
      review_cycle_days: Number(editReviewCycle) || 365,
      classification: editClassification,
    };

    // Priority 1: Only transmit content/restricted_content if body is authoritatively loaded;
    // unavailable body yields strictly metadata-only payload omitting body fields.
    if (hasAuthoritativeBody) {
      payload.content = isProtected ? "" : editContent;
      payload.restricted_content = isProtected ? editContent : null;
    }

    try {
      const updated = await updatePolicy(tenantId, token, selectedPolicy.id, payload);
      onPolicyMutated?.(updated);

      if (mutatingId !== selectedPolicyIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }

      setHasEditChanges(false);
      setIsBodyDirty(false);
      setServerVersion(updated.version);
      setEditorBaseVersion(updated.version);
      setAuthoritativeDetail(updated);
      // P1 fix: Saving metadata on an unavailable/unhydrated body does NOT make the body available.
      if (hasAuthoritativeBody) {
        setHasAuthoritativeBody(true);
        setBodyUnavailable(false);
      }
      setConflictOccurred(false);
      setActionSuccess("Draft saved successfully.");
    } catch (err: unknown) {
      if (mutatingId !== selectedPolicyIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice") || "Version conflict: another user modified this policy.");
      } else if (err instanceof ValidationError) {
        setActionError(`Validation error: ${err.message}`);
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to save draft.");
      }
    } finally {
      if (mutatingId === selectedPolicyIdRef.current && mutationGen === mutationGenRef.current) {
        setActionLoading(null);
      }
    }
  };

  // Discard local edits restoring authoritative detail snapshot
  const handleDiscardChanges = () => {
    const snap = authoritativeDetailRef.current;
    if (snap) {
      setEditTitle(snap.title);
      setEditDesc(snap.description);
      setEditVersionString(snap.version_string);
      setEditReviewCycle(snap.review_cycle_days);
      setEditClassification(snap.classification);
      setEditContent(snap.restricted_content || snap.content || "");
      setEditorBaseVersion(snap.version);
      setServerVersion(snap.version);
      setHasEditChanges(false);
      setConflictOccurred(false);
      setActionError(null);
    } else if (selectedPolicy) {
      void loadPolicyDetail(selectedPolicy.id);
    }
  };

  // Guarded policy selection
  const handleSelectPolicy = (policyId: string) => {
    if (policyId === selectedPolicyId) return;
    if (hasEditChanges) {
      setPendingSwitchPolicyId(policyId);
      return;
    }
    setSelectedPolicyId(policyId);
  };

  // Handle Create Follow-up Task with duplicate POST protection and lifetime fencing
  const handleCreateFollowupTask = async (e?: React.SyntheticEvent, isResubmit = false) => {
    if (e && typeof e.preventDefault === "function") {
      e.preventDefault();
    }
    if (!selectedPolicy || !canManage || followupSubmitting) return;
    if (!isResubmit && Boolean(uncertainFollowup)) return;
    if (!followupTitle.trim()) {
      setFollowupError("Title is required.");
      return;
    }
    if (followupCreateAbortRef.current) {
      followupCreateAbortRef.current.abort();
    }
    const abortCtrl = new AbortController();
    followupCreateAbortRef.current = abortCtrl;

    const attemptId = ++followupAttemptIdRef.current;
    const reqTenantId = tenantId;
    const reqToken = token;
    const reqPolicyId = selectedPolicy.id;

    const taskPayload: CreateTaskInput = {
      title: followupTitle.trim(),
      description: followupDesc.trim() || followupTitle.trim(),
      due_date: followupDueDate
        ? (followupDueDate.includes("T") ? new Date(followupDueDate).toISOString() : `${followupDueDate}T00:00:00Z`)
        : new Date(Date.now() + 7 * 86400000).toISOString(),
      priority: followupPriority,
      policy_id: reqPolicyId,
    };

    setFollowupSubmitting(true);
    setFollowupError(null);
    try {
      const task = await taskApi.createTask(reqTenantId, reqToken, taskPayload, abortCtrl.signal);
      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        attemptId !== followupAttemptIdRef.current ||
        reqTenantId !== contextRef.current.tenantId ||
        reqToken !== contextRef.current.token ||
        reqPolicyId !== selectedPolicyRef.current?.id
      ) {
        return;
      }
      setShowFollowupModal(false);
      setUncertainFollowup(null);
      setFollowupTitle("");
      setFollowupDesc("");
      setFollowupDueDate("");
      setActionSuccess("Follow-up task created successfully.");
      onTaskCreated?.(task);
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        attemptId !== followupAttemptIdRef.current ||
        reqTenantId !== contextRef.current.tenantId ||
        reqToken !== contextRef.current.token ||
        reqPolicyId !== selectedPolicyRef.current?.id
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === contextRef.current.token &&
          reqTenantId === contextRef.current.tenantId
        ) {
          onSessionExpired?.();
        }
        return;
      }
      const isDefinite =
        err instanceof ValidationError ||
        err instanceof ForbiddenError ||
        (typeof err === "object" && err !== null && "status" in err && (
          (err as { status: unknown }).status === 400 ||
          (err as { status: unknown }).status === 403 ||
          (err as { status: unknown }).status === 422
        ));

      if (isDefinite) {
        setFollowupError(err instanceof Error ? err.message : "Failed to create follow-up task.");
        setUncertainFollowup(null);
      } else {
        // Uncertain outcome: server may have committed task
        setUncertainFollowup({
          payload: taskPayload,
          attemptId,
        });
        setFollowupError("Create outcome uncertain due to network or server error. Please reconcile before proceeding.");
      }
    } finally {
      if (
        isMountedRef.current &&
        !abortCtrl.signal.aborted &&
        attemptId === followupAttemptIdRef.current &&
        reqTenantId === contextRef.current.tenantId &&
        reqToken === contextRef.current.token &&
        reqPolicyId === selectedPolicyRef.current?.id
      ) {
        setFollowupSubmitting(false);
      }
    }
  };

  const handleReconcileFollowup = async () => {
    if (!uncertainFollowup || reconcilingFollowup || !selectedPolicy) return;
    if (followupReconcileAbortRef.current) {
      followupReconcileAbortRef.current.abort();
    }
    const abortCtrl = new AbortController();
    followupReconcileAbortRef.current = abortCtrl;

    const attemptId = uncertainFollowup.attemptId;
    const reqTenantId = tenantId;
    const reqToken = token;
    const reqPolicyId = selectedPolicy.id;
    const attemptedPayload = uncertainFollowup.payload;

    setReconcilingFollowup(true);
    setReconcileFollowupError(null);
    try {
      const PAGE_LIMIT = 100;
      const MAX_PAGES = 3;
      let offset = 0;
      let allFetchedTasks: ComplianceTask[] = [];
      let reachBoundWithMore = false;

      for (let p = 0; p < MAX_PAGES; p++) {
        const pageTasks = await taskApi.fetchTasks(
          reqTenantId,
          reqToken,
          {
            limit: PAGE_LIMIT,
            offset,
          },
          abortCtrl.signal
        );

        if (
          !isMountedRef.current ||
          abortCtrl.signal.aborted ||
          attemptId !== followupAttemptIdRef.current ||
          reqTenantId !== contextRef.current.tenantId ||
          reqToken !== contextRef.current.token ||
          reqPolicyId !== selectedPolicyRef.current?.id
        ) {
          return;
        }

        if (!Array.isArray(pageTasks)) {
          throw new Error("Invalid response format from tasks query");
        }

        allFetchedTasks = allFetchedTasks.concat(pageTasks);
        if (pageTasks.length < PAGE_LIMIT) {
          reachBoundWithMore = false;
          break;
        }
        offset += PAGE_LIMIT;
        if (p === MAX_PAGES - 1) {
          reachBoundWithMore = true;
        }
      }

      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        attemptId !== followupAttemptIdRef.current ||
        reqTenantId !== contextRef.current.tenantId ||
        reqToken !== contextRef.current.token ||
        reqPolicyId !== selectedPolicyRef.current?.id
      ) {
        return;
      }

      const normInstant = (d?: string | null) => {
        if (!d) return null;
        const dt = new Date(d);
        return isNaN(dt.getTime()) ? d : dt.toISOString();
      };

      const matches = allFetchedTasks.filter((t) => {
        // Must belong to this exact policy and not other reference domains
        if (t.policy_id !== reqPolicyId) return false;
        if (t.control_id || t.control_type || t.evidence_id) return false;

        // Exact string comparison without lowercasing meaningful content
        if (t.title.trim() !== attemptedPayload.title.trim()) return false;
        const taskDesc = (t.description || "").trim();
        const payloadDesc = (attemptedPayload.description || attemptedPayload.title).trim();
        if (taskDesc !== payloadDesc) return false;

        // Priority
        if (attemptedPayload.priority && t.priority !== attemptedPayload.priority) return false;

        // Exact ISO instant comparison for due_date
        const attemptedDate = normInstant(attemptedPayload.due_date);
        const taskDate = normInstant(t.due_date);
        if (attemptedDate !== taskDate) return false;

        // Exact assignee comparison (null vs assigned)
        const attemptedAssignee = attemptedPayload.assignee_user_id || null;
        const taskAssignee = t.assignee_user_id || null;
        if (attemptedAssignee !== taskAssignee) return false;

        return true;
      });

      if (matches.length > 1) {
        setUncertainFollowup({
          ...uncertainFollowup,
          reconciled: true,
          matchingTask: null,
          ambiguous: true,
          incomplete: false,
        });
      } else if (matches.length === 1) {
        if (reachBoundWithMore) {
          // Cannot prove uniqueness across unread pages
          setUncertainFollowup({
            ...uncertainFollowup,
            reconciled: true,
            matchingTask: null,
            ambiguous: false,
            incomplete: true,
          });
        } else {
          setUncertainFollowup({
            ...uncertainFollowup,
            reconciled: true,
            matchingTask: matches[0],
            ambiguous: false,
            incomplete: false,
          });
        }
      } else {
        setUncertainFollowup({
          ...uncertainFollowup,
          reconciled: true,
          matchingTask: null,
          ambiguous: false,
          incomplete: reachBoundWithMore,
        });
      }
    } catch (err: unknown) {
      if (
        !isMountedRef.current ||
        abortCtrl.signal.aborted ||
        attemptId !== followupAttemptIdRef.current ||
        reqTenantId !== contextRef.current.tenantId ||
        reqToken !== contextRef.current.token ||
        reqPolicyId !== selectedPolicyRef.current?.id
      ) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        if (
          isMountedRef.current &&
          reqToken === contextRef.current.token &&
          reqTenantId === contextRef.current.tenantId
        ) {
          onSessionExpired?.();
        }
        return;
      }
      setReconcileFollowupError(err instanceof Error ? err.message : "Reconciliation failed.");
    } finally {
      if (
        isMountedRef.current &&
        !abortCtrl.signal.aborted &&
        attemptId === followupAttemptIdRef.current &&
        reqTenantId === contextRef.current.tenantId &&
        reqToken === contextRef.current.token &&
        reqPolicyId === selectedPolicyRef.current?.id
      ) {
        setReconcilingFollowup(false);
      }
    }
  };

  // Handle Submit for Review
  const handleSubmitReview = async () => {
    if (!selectedPolicy || !canManage || actionLoading) return;
    setActionLoading("submit");
    setActionError(null);
    try {
      const updated = await submitPolicyReview(tenantId, token, selectedPolicy.id, {
        expected_version: selectedPolicy.version,
      });
      onPolicyMutated?.(updated);
      setActionSuccess("Policy submitted for independent review.");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice"));
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to submit review.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Approve Policy (Enforces Independent Approval: Author Cannot Approve)
  const handleApprove = async () => {
    if (!selectedPolicy || !canManage || actionLoading) return;
    if (isAuthor) {
      setActionError("Independent 2-person approval required: Policy author cannot self-approve.");
      return;
    }
    setActionLoading("approve");
    setActionError(null);
    try {
      const updated = await approvePolicy(tenantId, token, selectedPolicy.id, {
        expected_version: selectedPolicy.version,
      });
      onPolicyMutated?.(updated);
      setActionSuccess("Policy approved successfully.");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice"));
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to approve policy.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Publish Policy
  const handlePublish = async () => {
    if (!selectedPolicy || !canManage || actionLoading) return;
    setActionLoading("publish");
    setActionError(null);
    try {
      const updated = await publishPolicy(tenantId, token, selectedPolicy.id, {
        expected_version: selectedPolicy.version,
      });
      onPolicyMutated?.(updated);
      setActionSuccess("Policy published successfully.");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice"));
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to publish policy.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Archive Policy
  const handleArchive = async () => {
    if (!selectedPolicy || !canManage || actionLoading) return;
    setActionLoading("archive");
    setActionError(null);
    try {
      const updated = await archivePolicy(tenantId, token, selectedPolicy.id, {
        expected_version: selectedPolicy.version,
      });
      onPolicyMutated?.(updated);
      setActionSuccess("Policy archived.");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setConflictOccurred(true);
        setActionError(t("portal.conflictReloadNotice"));
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to archive policy.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Acknowledge Policy
  const handleAcknowledge = async () => {
    if (!selectedPolicy || actionLoading) return;
    setActionLoading("acknowledge");
    setActionError(null);
    try {
      const ack = await acknowledgePolicy(tenantId, token, selectedPolicy.id);
      setAcknowledgements((prev) => [ack, ...prev]);
      setActionSuccess("Policy acknowledged successfully.");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError(err instanceof Error ? err.message : "Failed to acknowledge policy.");
    } finally {
      setActionLoading(null);
    }
  };

  if (isRoleDenied) {
    return (
      <div className="mw-card" data-testid="policy-workspace-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice")}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-operations-policies" data-testid="policy-workspace">
      {/* Read-Only Notice for non-managers */}
      {!canManage && (
        <div
          className="mw-notice-banner"
          data-testid="policies-readonly-notice"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {t("portal.operationsReadOnlyNotice")}
        </div>
      )}

      {/* Action Success / Error Notifications */}
      {actionSuccess && (
        <div
          className="mw-notice-banner success"
          data-testid="policy-action-success"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {actionSuccess}
        </div>
      )}
      {actionError && (
        <div
          className="mw-notice-banner error"
          data-testid="policy-action-error"
          style={{ marginBottom: "1rem" }}
          role="alert"
        >
          {actionError}
        </div>
      )}

      {/* Optimistic Locking Conflict Notice */}
      {conflictOccurred && (
        <div
          className="mw-notice-banner warning"
          data-testid="policy-conflict-banner"
          style={{ marginBottom: "1rem" }}
          role="alert"
        >
          <p>{t("portal.conflictReloadNotice")}</p>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="policy-reload-btn"
            onClick={() => {
              setConflictOccurred(false);
              setActionError(null);
              if (selectedPolicyId) {
                void loadPolicyDetail(selectedPolicyId, true);
              }
              onRefresh?.();
            }}
          >
            {t("portal.conflictReloadBtn")}
          </button>
        </div>
      )}

      {/* Filter and New Policy Header */}
      <div
        className="mw-filter-bar"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
        }}
      >
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <span style={{ fontSize: "0.85rem", color: "#666" }}>Filter:</span>
          <select
            className="mw-select"
            data-testid="policy-status-filter"
            value={selectedStatusFilter}
            onChange={(e) => setSelectedStatusFilter(e.target.value)}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All</option>
            <option value="draft">Draft</option>
            <option value="in_review">In Review</option>
            <option value="approved">Approved</option>
            <option value="published">Published</option>
            <option value="archived">Archived</option>
          </select>
          {(["all", "draft", "in_review", "approved", "published", "archived"] as const).map(
            (statusKey) => (
              <button
                key={statusKey}
                type="button"
                className={`mw-badge-btn ${selectedStatusFilter === statusKey ? "active" : ""}`}
                data-testid={`filter-${statusKey}`}
                onClick={() => setSelectedStatusFilter(statusKey)}
                style={{
                  padding: "0.25rem 0.6rem",
                  fontSize: "0.8rem",
                  borderRadius: "12px",
                  border: "1px solid #ccc",
                  background: selectedStatusFilter === statusKey ? "#0052cc" : "#fff",
                  color: selectedStatusFilter === statusKey ? "#fff" : "#333",
                  cursor: "pointer",
                }}
              >
                {statusKey === "all"
                  ? "All"
                  : statusKey === "draft"
                  ? t("portal.statusDraft")
                  : statusKey === "in_review"
                  ? t("portal.statusInReview")
                  : statusKey === "approved"
                  ? t("portal.statusApproved")
                  : statusKey === "published"
                  ? t("portal.statusPublished")
                  : t("portal.statusArchived")}
              </button>
            )
          )}
        </div>

        {canManage && (
          <button
            type="button"
            className="mw-btn mw-btn-primary"
            data-testid="new-policy-btn"
            onClick={() => {
              setIsCreating(!isCreating);
              setCreateError(null);
            }}
          >
            {isCreating ? "Cancel" : t("portal.createRecordBtn")}
          </button>
        )}
      </div>

      {/* Creation Modal / Inline Drawer */}
      {isCreating && (
        <div
          className="mw-card"
          data-testid="new-policy-form-card"
          style={{ marginBottom: "1.5rem", border: "1px solid #0052cc" }}
        >
          <h3>Create New Policy</h3>
          {createError && (
            <div className="mw-notice-banner error" role="alert" style={{ marginBottom: "0.75rem" }}>
              {createError}
            </div>
          )}

          {/* Uncertain Create Reconciliation Notice */}
          {uncertainCreate && (
            <div
              className="mw-notice-banner warning"
              data-testid="policy-uncertain-create-banner"
              style={{ marginBottom: "0.75rem" }}
              role="alert"
            >
              <p>{t("portal.uncertainCreateNotice") || "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."}</p>
              {reconcileError && (
                <p style={{ color: "#b91c1c", fontSize: "0.85rem", margin: "0.25rem 0" }}>
                  {reconcileError}
                </p>
              )}
              {!uncertainCreate.reconciled ? (
                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="reconcile-policy-btn"
                    onClick={handleReconcileCreate}
                    disabled={reconciling}
                  >
                    {reconciling ? "Checking Server..." : t("portal.checkReconcileBtn") || "Check Server State"}
                  </button>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="discard-uncertain-btn"
                    onClick={handleDiscardUncertainCreate}
                  >
                    Abandon Draft
                  </button>
                </div>
              ) : uncertainCreate.matchingPolicy ? (
                <div style={{ marginTop: "0.5rem" }}>
                  <p style={{ color: "#155724", fontWeight: 600 }}>
                    Matching record found on server: {uncertainCreate.matchingPolicy.title} (v
                    {uncertainCreate.matchingPolicy.version_string})
                  </p>
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="confirm-reconcile-policy-btn"
                      onClick={() => handleConfirmReconcile(uncertainCreate.matchingPolicy!)}
                    >
                      Adopt Existing Record
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="discard-uncertain-btn"
                      onClick={handleDiscardUncertainCreate}
                    >
                      Abandon Draft
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ marginTop: "0.5rem" }}>
                  <p style={{ color: "#666" }}>
                    No matching record found on server. You may abandon the draft or acknowledge uncertainty to allow resubmission.
                  </p>
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.25rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="force-resubmit-btn"
                      onClick={handleAllowResubmit}
                    >
                      Acknowledge & Allow Resubmit
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="reconcile-policy-btn"
                      onClick={handleReconcileCreate}
                      disabled={reconciling}
                    >
                      Re-check Server
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="discard-uncertain-btn"
                      onClick={handleDiscardUncertainCreate}
                    >
                      Abandon Draft
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          <form onSubmit={handleCreateSubmit}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Title *</label>
                <input
                  type="text"
                  className="mw-input"
                  data-testid="new-policy-title-input"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Access Control Policy"
                />
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Version Code</label>
                <input
                  type="text"
                  className="mw-input"
                  data-testid="policy-version-input"
                  value={newVersionString}
                  onChange={(e) => setNewVersionString(e.target.value)}
                  placeholder="1.0"
                />
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Classification</label>
                <select
                  className="mw-input"
                  data-testid="policy-classification-select"
                  value={newClassification}
                  onChange={(e) => setNewClassification(e.target.value as PolicyClassification)}
                >
                  <option value="Public">Public</option>
                  <option value="Internal">Internal</option>
                  <option value="Confidential">Confidential</option>
                  <option value="Restricted">Restricted (Server Encrypted)</option>
                </select>
                {newClassification === "Restricted" && (
                  <p style={{ fontSize: "0.75rem", color: "#155724", marginTop: "0.2rem" }}>
                    Protected narrative will be stored encrypted (restricted_content).
                  </p>
                )}
              </div>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Review Cycle (Days)</label>
                <input
                  type="number"
                  className="mw-input"
                  data-testid="policy-cycle-input"
                  value={newReviewCycle}
                  onChange={(e) => setNewReviewCycle(Number(e.target.value))}
                  min={1}
                />
              </div>
            </div>

            <div style={{ marginBottom: "0.75rem" }}>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>Description *</label>
              <textarea
                className="mw-input"
                data-testid="new-policy-desc-input"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={2}
                placeholder="High-level purpose and scope of this policy"
              />
            </div>

            <div style={{ marginBottom: "1rem" }}>
              <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600 }}>
                Policy Content / Narrative
              </label>
              <textarea
                className="mw-input"
                data-testid="policy-content-input"
                value={newContent}
                onChange={(e) => setNewContent(e.target.value)}
                rows={4}
                placeholder="Detailed regulatory or operational requirements..."
              />
            </div>

            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                type="submit"
                className="mw-btn mw-btn-primary"
                data-testid="submit-create-policy-btn"
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                {createSubmitting ? "Creating..." : "Save Policy"}
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                onClick={() => setIsCreating(false)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingSwitchPolicyId && (
        <div
          className="mw-notice-banner warning"
          data-testid="dirty-switch-guard"
          role="alert"
          style={{ marginBottom: "1rem" }}
        >
          <div>You have unsaved changes in this policy. Switching will discard your edits.</div>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="cancel-switch-btn"
              onClick={() => setPendingSwitchPolicyId(null)}
            >
              Keep Editing
            </button>
            <button
              type="button"
              className="mw-btn mw-btn-danger"
              data-testid="confirm-discard-switch-btn"
              onClick={() => {
                const nextId = pendingSwitchPolicyId;
                setPendingSwitchPolicyId(null);
                setHasEditChanges(false);
                setSelectedPolicyId(nextId);
              }}
            >
              Discard and Switch
            </button>
          </div>
        </div>
      )}

      {/* Main Workspace Grid: Policies Table on Left, Details & Actions on Right */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "1.5rem" }}>
        {/* Left Column: Policies Table */}
        <div className="mw-card" style={{ padding: "0.5rem" }}>
          {loading && (
            <p style={{ padding: "1rem", color: "#666", fontSize: "0.9rem" }}>Loading policies...</p>
          )}

          {!loading && filteredPolicies.length === 0 && (
            <div style={{ padding: "2rem", textAlign: "center", color: "#666" }}>
              <p>No policies found matching the selected filter.</p>
            </div>
          )}

          {!loading && filteredPolicies.length > 0 && (
            <table
              className="mw-table"
              data-testid="policies-table"
              style={{ width: "100%", borderCollapse: "collapse" }}
            >
              <thead>
                <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Title</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Status</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Ver</th>
                  <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Class</th>
                </tr>
              </thead>
              <tbody>
                {filteredPolicies.map((p) => {
                  const isSelected = p.id === selectedPolicyId;
                  return (
                    <tr
                      key={p.id}
                      data-testid={`policy-row-${p.id}`}
                      onClick={() => handleSelectPolicy(p.id)}
                      style={{
                        cursor: "pointer",
                        background: isSelected ? "#e6f0ff" : "transparent",
                        borderBottom: "1px solid #f0f0f0",
                      }}
                    >
                      <td style={{ padding: "0.6rem 0.75rem", fontWeight: isSelected ? 600 : 400 }}>
                        {p.title}
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem" }}>
                        <span
                          className={`mw-badge status-${p.status}`}
                          data-testid={`policy-status-${p.id}`}
                          style={{
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                            fontWeight: 600,
                            textTransform: "uppercase",
                          }}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem", color: "#666" }}>
                        v{p.version_string}
                      </td>
                      <td style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem", color: "#666" }}>
                        {p.classification}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Right Column: Selected Policy Inspector & Workflow Actions */}
        <div className="mw-card" data-testid="policy-details-panel">
          {!selectedPolicy && (
            <div style={{ padding: "2rem", textAlign: "center", color: "#888" }}>
              <p>{t("portal.noRecordSelected")}</p>
            </div>
          )}

          {selectedPolicy && (
            <div>
              {/* Header */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  borderBottom: "1px solid #eee",
                  paddingBottom: "0.75rem",
                  marginBottom: "1rem",
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{selectedPolicy.title}</h3>
                  <p style={{ margin: 0, fontSize: "0.8rem", color: "#666" }}>
                    ID: {selectedPolicy.id} | v{selectedPolicy.version_string} (Rev {selectedPolicy.version})
                  </p>
                </div>
                <span
                  className={`mw-badge status-${selectedPolicy.status}`}
                  data-testid="detail-policy-status"
                  style={{
                    padding: "0.3rem 0.6rem",
                    borderRadius: "4px",
                    fontWeight: 700,
                    fontSize: "0.8rem",
                  }}
                >
                  {selectedPolicy.status}
                </span>
              </div>

              {loadingDetail && (
                <p style={{ fontSize: "0.85rem", color: "#666" }} data-testid="policy-hydrating-msg">Hydrating policy details...</p>
              )}
              {detailError && (
                <div className="mw-notice-banner error" data-testid="policy-detail-error" style={{ fontSize: "0.85rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{detailError}</span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="retry-policy-detail-btn"
                    onClick={() => {
                      if (selectedPolicy) void loadPolicyDetail(selectedPolicy.id);
                    }}
                  >
                    Retry
                  </button>
                </div>
              )}
              {bodyUnavailable && (
                <div className="mw-notice-banner warning" data-testid="policy-body-unavailable-banner" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                  Protected content is unavailable. Please retry loading policy details before editing or saving.
                </div>
              )}
              {conflictOccurred && (
                <div className="mw-notice-banner warning" data-testid="conflict-reload-banner" role="alert" style={{ fontSize: "0.85rem", marginBottom: "0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>{t("portal.conflictReloadNotice") || "Version conflict: another user modified this policy."}</span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="conflict-reload-btn"
                    onClick={() => {
                      if (selectedPolicy) void loadPolicyDetail(selectedPolicy.id);
                    }}
                  >
                    Reload Latest Version
                  </button>
                </div>
              )}

              {/* Author Independent Approval Denial Notice */}
              {selectedPolicy.status === "in_review" && isAuthor && (
                <div
                  className="mw-notice-banner error"
                  data-testid="author-self-approval-notice"
                  style={{ marginBottom: "0.75rem", fontSize: "0.85rem" }}
                  role="alert"
                >
                  {t("portal.policyOwnerCannotApproveNotice")}
                </div>
              )}

              {/* Lifecycle Action Bar */}
              <div
                className="mw-actions-bar"
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  flexWrap: "wrap",
                  marginBottom: "1rem",
                  padding: "0.5rem",
                  background: "#f9f9fb",
                  borderRadius: "6px",
                }}
              >
                {/* Draft: Submit for Review */}
                {selectedPolicy.status === "draft" && canManage && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="submit-review-policy-btn"
                    onClick={handleSubmitReview}
                    disabled={Boolean(actionLoading) || hasEditChanges}
                  >
                    {actionLoading === "submit" ? "Submitting..." : t("portal.submitReviewBtn")}
                  </button>
                )}

                {/* In Review: Independent Approval */}
                {selectedPolicy.status === "in_review" && canManage && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="approve-policy-btn"
                    onClick={handleApprove}
                    disabled={Boolean(actionLoading)}
                    title={isAuthor ? t("portal.policyOwnerCannotApproveNotice") : undefined}
                  >
                    {actionLoading === "approve" ? "Approving..." : t("portal.approvePolicyBtn")}
                  </button>
                )}

                {/* Approved: Publish */}
                {selectedPolicy.status === "approved" && canManage && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="publish-policy-btn"
                    onClick={handlePublish}
                    disabled={Boolean(actionLoading)}
                  >
                    {actionLoading === "publish" ? "Publishing..." : t("portal.publishPolicyBtn")}
                  </button>
                )}

                {/* Published: Archive */}
                {selectedPolicy.status === "published" && canManage && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="archive-policy-btn"
                    onClick={handleArchive}
                    disabled={Boolean(actionLoading)}
                  >
                    {actionLoading === "archive" ? "Archiving..." : t("portal.archivePolicyBtn")}
                  </button>
                )}

                {/* Create Follow-up Task */}
                {canManage && (
                  <button
                    type="button"
                    className="mw-btn mw-btn-secondary"
                    data-testid="create-followup-task-btn"
                    onClick={() => {
                      setFollowupTitle(`Follow-up: ${selectedPolicy.title}`);
                      setFollowupDesc(`Follow-up task for policy ${selectedPolicy.title}`);
                      setFollowupDueDate("2026-11-20");
                      setFollowupPriority("medium");
                      setFollowupError(null);
                      setShowFollowupModal(true);
                    }}
                    disabled={Boolean(actionLoading)}
                  >
                    Create follow-up task
                  </button>
                )}

                {/* Published: Workforce Acknowledgment */}
                {selectedPolicy.status === "published" && (
                  <button
                    type="button"
                    className={`mw-btn ${hasCurrentUserAcknowledged ? "mw-btn-secondary" : "mw-btn-primary"}`}
                    data-testid="acknowledge-policy-btn"
                    onClick={handleAcknowledge}
                    disabled={Boolean(actionLoading) || hasCurrentUserAcknowledged}
                  >
                    {hasCurrentUserAcknowledged
                      ? t("portal.acknowledgedBadge")
                      : actionLoading === "acknowledge"
                      ? "Acknowledging..."
                      : t("portal.acknowledgePolicyBtn")}
                  </button>
                )}
              </div>

              {/* Editable Fields (Only in Draft status) */}
              <div style={{ marginBottom: "1rem" }}>
                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Title</label>
                  <input
                    type="text"
                    className="mw-input"
                    data-testid="edit-policy-title"
                    value={editTitle}
                    disabled={!canManage || selectedPolicy.status !== "draft" || (!hasAuthoritativeBody && (editClassification === "Restricted" || editClassification === "Confidential"))}
                    onChange={(e) => {
                      setEditTitle(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.5rem" }}>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Version Code</label>
                    <input
                      type="text"
                      className="mw-input"
                      data-testid="edit-policy-version"
                      value={editVersionString}
                      disabled={!canManage || selectedPolicy.status !== "draft" || (!hasAuthoritativeBody && (editClassification === "Restricted" || editClassification === "Confidential"))}
                      onChange={(e) => {
                        setEditVersionString(e.target.value);
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Classification</label>
                    <select
                      className="mw-input"
                      data-testid="edit-policy-classification"
                      value={editClassification}
                      disabled={!canManage || selectedPolicy.status !== "draft" || (!hasAuthoritativeBody && (editClassification === "Restricted" || editClassification === "Confidential"))}
                      onChange={(e) => {
                        setEditClassification(e.target.value as PolicyClassification);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="Public">Public</option>
                      <option value="Internal">Internal</option>
                      <option value="Confidential">Confidential</option>
                      <option value="Restricted">Restricted (Server Encrypted)</option>
                    </select>
                  </div>
                </div>

                <div style={{ marginBottom: "0.5rem" }}>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600 }}>Description</label>
                  <textarea
                    className="mw-input"
                    data-testid="edit-policy-desc"
                    value={editDesc}
                    rows={2}
                    disabled={!canManage || selectedPolicy.status !== "draft" || (!hasAuthoritativeBody && (editClassification === "Restricted" || editClassification === "Confidential"))}
                    onChange={(e) => {
                      setEditDesc(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div style={{ marginBottom: "0.5rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>
                      Policy Content / Narrative
                    </label>
                    {editClassification === "Restricted" && (
                      <span style={{ fontSize: "0.75rem", color: "#155724", fontWeight: 600 }}>
                        Encrypted Field (restricted_content)
                      </span>
                    )}
                  </div>
                  <textarea
                    className="mw-input"
                    data-testid="edit-policy-content-input"
                    value={editContent}
                    rows={5}
                    disabled={!canManage || selectedPolicy.status !== "draft" || (!hasAuthoritativeBody && (editClassification === "Restricted" || editClassification === "Confidential"))}
                    onChange={(e) => {
                      setEditContent(e.target.value);
                      setHasEditChanges(true);
                      setIsBodyDirty(true);
                    }}
                  />
                </div>

                {selectedPolicy.status === "draft" && canManage && (
                  <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="save-policy-draft-btn"
                      onClick={handleSaveDraft}
                      disabled={!hasEditChanges || Boolean(actionLoading)}
                    >
                      {actionLoading === "save" ? "Saving..." : t("portal.saveDraftBtn")}
                    </button>
                    {hasEditChanges && (
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="discard-policy-changes-btn"
                        onClick={handleDiscardChanges}
                      >
                        Discard Changes
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Revision History & Acknowledgement Summary */}
              <div style={{ borderTop: "1px solid #eee", paddingTop: "0.75rem" }}>
                <h4 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem" }}>
                  {t("portal.revisionsHistoryTitle")} ({revisions.length})
                </h4>
                {loadingRevs && (
                  <p style={{ fontSize: "0.8rem", color: "#666" }}>Loading revisions...</p>
                )}
                {!loadingRevs && revisions.length === 0 && (
                  <p style={{ fontSize: "0.8rem", color: "#888" }}>No revisions recorded yet.</p>
                )}
                {!loadingRevs && revisions.length > 0 && (
                  <div style={{ maxHeight: "150px", overflowY: "auto", fontSize: "0.8rem" }}>
                    {revisions.map((rev) => (
                      <div
                        key={rev.id}
                        data-testid={`revision-item-${rev.revision_number}`}
                        style={{
                          padding: "0.3rem 0",
                          borderBottom: "1px dashed #f0f0f0",
                          display: "flex",
                          justifyContent: "space-between",
                        }}
                      >
                        <span>
                          Rev {rev.revision_number} (v{rev.version_string}) - {rev.status}
                        </span>
                        <span style={{ color: "#888" }}>
                          {new Date(rev.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

      {/* Create Follow-up Task Modal */}
      {showFollowupModal && selectedPolicy && (
        <div
          data-testid="followup-task-modal"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="mw-card"
            style={{
              width: "100%",
              maxWidth: "480px",
              padding: "1.5rem",
              background: "#fff",
              borderRadius: "8px",
            }}
          >
            <h3 style={{ margin: "0 0 1rem 0" }}>Create Follow-up Task</h3>
            {followupError && (
              <div
                className="mw-notice-banner error"
                data-testid="followup-task-error"
                style={{ marginBottom: "1rem" }}
              >
                {followupError}
              </div>
            )}
            <form onSubmit={handleCreateFollowupTask}>
              <div style={{ marginBottom: "0.75rem" }}>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem", fontWeight: 600 }}>
                  Policy ID (Linked)
                </label>
                <input
                  type="text"
                  className="mw-input"
                  data-testid="followup-task-policy-id"
                  value={selectedPolicy.id}
                  disabled
                  style={{ width: "100%", background: "#f5f5f5" }}
                />
              </div>
              <div style={{ marginBottom: "0.75rem" }}>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem", fontWeight: 600 }}>
                  Task Title *
                </label>
                <input
                  type="text"
                  className="mw-input"
                  data-testid="followup-task-title-input"
                  value={followupTitle}
                  onChange={(e) => setFollowupTitle(e.target.value)}
                  style={{ width: "100%" }}
                  required
                />
              </div>
              <div style={{ marginBottom: "0.75rem" }}>
                <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem", fontWeight: 600 }}>
                  Description
                </label>
                <textarea
                  className="mw-textarea"
                  data-testid="followup-task-desc-input"
                  value={followupDesc}
                  onChange={(e) => setFollowupDesc(e.target.value)}
                  rows={3}
                  style={{ width: "100%" }}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem", fontWeight: 600 }}>
                    Due Date
                  </label>
                  <input
                    type="date"
                    className="mw-input"
                    data-testid="followup-task-due-input"
                    value={followupDueDate}
                    onChange={(e) => setFollowupDueDate(e.target.value)}
                    style={{ width: "100%" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", marginBottom: "0.25rem", fontWeight: 600 }}>
                    Priority
                  </label>
                  <select
                    className="mw-select"
                    data-testid="followup-task-priority-select"
                    value={followupPriority}
                    onChange={(e) => setFollowupPriority(e.target.value as TaskPriority)}
                    style={{ width: "100%" }}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>
              {uncertainFollowup && (
                <div
                  className="mw-notice-banner warning"
                  data-testid="followup-uncertain-banner"
                  style={{ marginBottom: "0.75rem", padding: "0.5rem 0.75rem" }}
                  role="alert"
                >
                  <p style={{ margin: 0, fontWeight: 600 }}>Create outcome uncertain due to network or server error. Please reconcile before proceeding.</p>
                  {reconcileFollowupError && (
                    <p style={{ color: "#d32f2f", marginTop: "0.25rem", margin: 0 }}>{reconcileFollowupError}</p>
                  )}
                  {!uncertainFollowup.reconciled ? (
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="reconcile-followup-btn"
                        onClick={handleReconcileFollowup}
                        disabled={reconcilingFollowup}
                        style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                      >
                        {reconcilingFollowup ? "Checking server..." : "Reconcile with Server"}
                      </button>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        data-testid="abandon-followup-btn"
                        onClick={() => {
                          setUncertainFollowup(null);
                          setShowFollowupModal(false);
                        }}
                        style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                      >
                        Abandon Draft
                      </button>
                    </div>
                  ) : uncertainFollowup.ambiguous ? (
                    <div style={{ marginTop: "0.5rem" }} data-testid="followup-reconciled-ambiguous">
                      <p style={{ color: "#b45309", fontWeight: 600, margin: 0 }}>
                        Multiple matching tasks found on server; reconciliation remains ambiguous. Cannot adopt automatically.
                      </p>
                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid="abandon-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            setShowFollowupModal(false);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Abandon Draft
                        </button>
                      </div>
                    </div>
                  ) : uncertainFollowup.incomplete ? (
                    <div style={{ marginTop: "0.5rem" }} data-testid="followup-reconciled-incomplete">
                      <p style={{ color: "#b45309", margin: 0 }}>
                        Incomplete task query returned ({uncertainFollowup.matchingTask ? "1" : "0"} matches); cannot confirm absence.
                      </p>
                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                        <button
                          type="button"
                          className="mw-btn mw-btn-primary"
                          data-testid="resubmit-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            void handleCreateFollowupTask(undefined, true);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Resubmit Task
                        </button>
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid="abandon-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            setShowFollowupModal(false);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Abandon
                        </button>
                      </div>
                    </div>
                  ) : uncertainFollowup.matchingTask ? (
                    <div style={{ marginTop: "0.5rem" }} data-testid="followup-reconciled-match">
                      <p style={{ color: "#155724", fontWeight: 600, margin: 0 }}>
                        Matching task found on server: {uncertainFollowup.matchingTask.title}
                      </p>
                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                        <button
                          type="button"
                          className="mw-btn mw-btn-primary"
                          data-testid="adopt-followup-task-btn"
                          onClick={() => {
                            const task = uncertainFollowup.matchingTask!;
                            setUncertainFollowup(null);
                            setShowFollowupModal(false);
                            setFollowupTitle("");
                            setFollowupDesc("");
                            setFollowupDueDate("");
                            setActionSuccess("Existing follow-up task adopted successfully.");
                            onTaskCreated?.(task);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Adopt Existing Task
                        </button>
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid="abandon-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            setShowFollowupModal(false);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Abandon
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ marginTop: "0.5rem" }} data-testid="followup-reconciled-nomatch">
                      <p style={{ color: "#666", margin: 0 }}>
                        No matching task found on server. Safe to resubmit or abandon.
                      </p>
                      <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                        <button
                          type="button"
                          className="mw-btn mw-btn-primary"
                          data-testid="resubmit-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            void handleCreateFollowupTask(undefined, true);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Resubmit Task
                        </button>
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid="abandon-followup-btn"
                          onClick={() => {
                            setUncertainFollowup(null);
                            setShowFollowupModal(false);
                          }}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                        >
                          Abandon
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  data-testid="cancel-create-followup-task-btn"
                  onClick={() => setShowFollowupModal(false)}
                  disabled={followupSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="mw-btn mw-btn-primary"
                  data-testid="confirm-create-followup-task-btn"
                  onClick={(e) => { handleCreateFollowupTask(e); }}
                  disabled={followupSubmitting || Boolean(uncertainFollowup)}
                >
                  {followupSubmitting ? "Creating..." : "Create Task"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};
