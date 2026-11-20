import type { TenantRole } from "@conformly/shared";
import React, { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { canManageRisks, canReadRisks } from "../permissions";
import { ConflictError, CustomerDemoApiError, ForbiddenError, UnauthorizedError, ValidationError } from "./api";
import {
  createRisk,
  createRiskTreatment,
  fetchRisks,
  reviewRisk,
  updateRisk,
} from "./operations-api";
import {
  Risk,
  RiskCategory,
  RiskCreateInput,
  RiskStatus,
  RiskTreatmentStrategy,
} from "./operations-types";
import "./modern-workspace.css";

export interface RiskWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  risks: Risk[];
  loading?: boolean;
  onRefresh?: () => void;
  onSessionExpired?: () => void;
  onRiskMutated?: (updated: Risk) => void;
  onRiskCreated?: (created: Risk) => void;
  targetRiskId?: string | null;
  targetNonce?: number | null;
  onConsumeTarget?: () => void;
}

export const RiskWorkspaceV2: FC<RiskWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  risks,
  loading = false,
  onRefresh,
  onSessionExpired,
  onRiskMutated,
  onRiskCreated,
  targetRiskId = null,
  targetNonce = null,
  onConsumeTarget,
}) => {
  const { t } = useTranslation();

  const isRoleDenied = !canReadRisks(userRole as TenantRole);
  const canManage = canManageRisks(userRole as TenantRole);

  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(null);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>("all");

  // Edit / draft state
  const [editTitle, setEditTitle] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [editCategory, setEditCategory] = useState<RiskCategory>("security");
  const [editLikelihood, setEditLikelihood] = useState<number>(3);
  const [editImpact, setEditImpact] = useState<number>(3);
  const [editResidualScore, setEditResidualScore] = useState<number | "">("");
  const [editStatus, setEditStatus] = useState<RiskStatus>("identified");
  const [hasEditChanges, setHasEditChanges] = useState<boolean>(false);

  // New risk modal / form state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newTitle, setNewTitle] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newCategory, setNewCategory] = useState<RiskCategory>("security");
  const [newLikelihood, setNewLikelihood] = useState<number>(3);
  const [newImpact, setNewImpact] = useState<number>(3);
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Treatment form state
  const [isAddingTreatment, setIsAddingTreatment] = useState<boolean>(false);
  const [treatStrategy, setTreatStrategy] = useState<RiskTreatmentStrategy>("mitigate");
  const [treatPlan, setTreatPlan] = useState<string>("");
  const [treatTargetDate, setTreatTargetDate] = useState<string>("");
  const [treatSubmitting, setTreatSubmitting] = useState<boolean>(false);

  // Action feedback states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [pendingSwitchRiskId, setPendingSwitchRiskId] = useState<string | null>(null);
  const createAttemptIdRef = useRef<number>(0);
  const mutationGenRef = useRef<number>(0);
  const selectedRiskIdRef = useRef<string | null>(selectedRiskId);
  useEffect(() => {
    selectedRiskIdRef.current = selectedRiskId;
  }, [selectedRiskId]);

  const consumedTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!targetRiskId) return;
      if (loading) return;
      const targetKey = `${targetRiskId}:${targetNonce ?? "static"}`;
      if (targetKey === consumedTargetKeyRef.current) return;
      const exists = risks.some((r) => r.id === targetRiskId);
      if (exists) {
        consumedTargetKeyRef.current = targetKey;
        onConsumeTarget?.();
        if (hasEditChanges && selectedRiskId && selectedRiskId !== targetRiskId) {
          setPendingSwitchRiskId(targetRiskId);
        } else {
          setSelectedRiskId(targetRiskId);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [targetRiskId, targetNonce, onConsumeTarget, loading, risks, hasEditChanges, selectedRiskId]);


  const contextRef = useRef({ tenantId, token });
  useEffect(() => {
    contextRef.current = { tenantId, token };
  }, [tenantId, token]);

  // Uncertain POST create recovery state
  const [uncertainCreate, setUncertainCreate] = useState<{
    payload: RiskCreateInput;
    reconciled?: boolean;
    matchingRisk?: Risk | null;
    attemptId: number;
  } | null>(null);

  // Find currently selected risk
  const selectedRisk = risks.find((r) => r.id === selectedRiskId) || null;

  const lastSelectedRiskIdRef = useRef<string | null>(null);
  const hasEditChangesRef = useRef<boolean>(false);
  useEffect(() => {
    hasEditChangesRef.current = hasEditChanges;
  }, [hasEditChanges]);

  // Sync edit form on selection change (preserving dirty in-flight edits on background refresh)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedRisk) {
        if (selectedRisk.id === lastSelectedRiskIdRef.current && hasEditChangesRef.current) {
          return;
        }
        lastSelectedRiskIdRef.current = selectedRisk.id;
        setEditTitle(selectedRisk.title);
        setEditDesc(selectedRisk.description);
        setEditCategory(selectedRisk.category);
        setEditLikelihood(selectedRisk.likelihood);
        setEditImpact(selectedRisk.impact);
        setEditResidualScore(selectedRisk.residual_score ?? "");
        setEditStatus(selectedRisk.status);
        setHasEditChanges(false);
        setActionError(null);
        setActionSuccess(null);
      } else {
        setEditTitle("");
        setEditDesc("");
        setEditCategory("security");
        setEditLikelihood(3);
        setEditImpact(3);
        setEditResidualScore("");
        setEditStatus("identified");
        setHasEditChanges(false);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedRiskId, selectedRisk]);

  // Filter risks list
  const filteredRisks = risks.filter((r) => {
    if (selectedCategoryFilter === "all") return true;
    return r.category === selectedCategoryFilter;
  });

  // Handle Create Risk
  const handleCreateRisk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || createSubmitting || Boolean(uncertainCreate)) return;

    if (!newTitle.trim()) {
      setCreateError(t("portal.entityNameRequired") || "Title is required");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    const payload: RiskCreateInput = {
      title: newTitle.trim(),
      description: newDesc.trim(),
      category: newCategory,
      likelihood: Number(newLikelihood),
      impact: Number(newImpact),
    };

    try {
      const created = await createRisk(tenantId, token, payload);
      onRiskCreated?.(created);
      setIsCreating(false);
      setNewTitle("");
      setNewDesc("");
      setSelectedRiskId(created.id);
      setActionSuccess(`Risk created: ${created.title}`);
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
        setCreateError(err instanceof Error ? err.message : "Failed to create risk");
      } else {
        setUncertainCreate({
          payload,
          reconciled: false,
          matchingRisk: null,
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

  const [reconciling, setReconciling] = useState<boolean>(false);
  const [reconcileError, setReconcileError] = useState<string | null>(null);

  // Reconcile uncertain create via fresh scoped GET and full payload comparison
  const handleReconcileCreate = async () => {
    if (!uncertainCreate || reconciling) return;
    const attemptId = uncertainCreate.attemptId;
    const attemptTenantId = tenantId;
    const attemptToken = token;

    setReconciling(true);
    setReconcileError(null);
    try {
      const freshList = await fetchRisks(attemptTenantId, attemptToken);
      if (
        attemptId !== createAttemptIdRef.current ||
        attemptTenantId !== contextRef.current.tenantId ||
        attemptToken !== contextRef.current.token
      ) {
        return;
      }
      const match = freshList.find(
        (r: Risk) =>
          r.title.trim().toLowerCase() === uncertainCreate.payload.title.trim().toLowerCase() &&
          r.description.trim() === uncertainCreate.payload.description.trim() &&
          r.category === uncertainCreate.payload.category
      );
      setUncertainCreate({
        ...uncertainCreate,
        reconciled: true,
        matchingRisk: match || null,
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
  const handleConfirmReconcile = (matched: Risk) => {
    setSelectedRiskId(matched.id);
    setUncertainCreate(null);
    setIsCreating(false);
    setActionSuccess(`${t("portal.reconciledSuccess")} (${matched.title})`);
  };

  // Discard uncertain attempt (abandon draft)
  const handleDiscardUncertainCreate = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
    setIsCreating(false);
    setNewTitle("");
    setNewDesc("");
  };

  // Allow resubmit after user confirmation
  const handleAllowResubmit = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
  };

  const handleSelectRisk = (riskId: string) => {
    if (riskId === selectedRiskId) return;
    if (hasEditChanges) {
      setPendingSwitchRiskId(riskId);
      return;
    }
    setSelectedRiskId(riskId);
  };

  // Handle Update Risk
  const handleUpdateRisk = async () => {
    if (!selectedRisk || !canManage || actionLoading) return;
    setActionLoading("save");
    setActionError(null);
    setActionSuccess(null);
    const mutatingId = selectedRisk.id;
    const mutationGen = ++mutationGenRef.current;

    try {
      const updated = await updateRisk(tenantId, token, selectedRisk.id, {
        title: editTitle.trim(),
        description: editDesc.trim(),
        category: editCategory,
        likelihood: Number(editLikelihood),
        impact: Number(editImpact),
        residual_score: editResidualScore === "" ? null : Number(editResidualScore),
        status: editStatus,
        owner_user_id: selectedRisk.owner_user_id ?? null,
        control_id: selectedRisk.control_id ?? null,
        finding_id: selectedRisk.finding_id ?? null,
        legal_entity_id: selectedRisk.legal_entity_id ?? null,
        business_unit_id: selectedRisk.business_unit_id ?? null,
      });
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onRiskMutated?.(updated);
      setHasEditChanges(false);
      setActionSuccess("Risk updated successfully.");
    } catch (err: unknown) {
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ConflictError) {
        setActionError(t("portal.conflictReloadNotice"));
      } else if (err instanceof ValidationError) {
        setActionError(`Validation error: ${err.message}`);
      } else {
        setActionError(err instanceof Error ? err.message : "Failed to update risk.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Review Risk
  const handleReviewRisk = async () => {
    if (!selectedRisk || !canManage || actionLoading) return;
    setActionLoading("review");
    setActionError(null);
    const mutatingId = selectedRisk.id;
    const mutationGen = ++mutationGenRef.current;
    try {
      const updated = await reviewRisk(tenantId, token, selectedRisk.id);
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onRiskMutated?.(updated);
      setActionSuccess("Risk review recorded.");
    } catch (err: unknown) {
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError(err instanceof Error ? err.message : "Failed to record risk review.");
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Add Treatment
  const handleAddTreatment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRisk || !canManage || treatSubmitting) return;

    if (!treatPlan.trim()) {
      setActionError("Treatment plan is required");
      return;
    }

    setTreatSubmitting(true);
    setActionError(null);
    const mutatingId = selectedRisk.id;
    const mutationGen = ++mutationGenRef.current;

    try {
      const treatment = await createRiskTreatment(tenantId, token, selectedRisk.id, {
        strategy: treatStrategy,
        treatment_plan: treatPlan.trim(),
        target_date: treatTargetDate || null,
      });
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      const updatedRisk: Risk = {
        ...selectedRisk,
        treatments: [...(selectedRisk.treatments || []), treatment],
      };
      onRiskMutated?.(updatedRisk);
      setIsAddingTreatment(false);
      setTreatPlan("");
      setTreatTargetDate("");
      setActionSuccess("Treatment plan added.");
    } catch (err: unknown) {
      if (mutatingId !== selectedRiskIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError(err instanceof Error ? err.message : "Failed to add treatment.");
    } finally {
      setTreatSubmitting(false);
    }
  };

  if (isRoleDenied) {
    return (
      <div className="mw-card" data-testid="risk-workspace-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice")}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-operations-risks" data-testid="risk-workspace">
      {/* Read-Only Notice */}
      {!canManage && (
        <div
          className="mw-notice-banner"
          data-testid="risks-readonly-notice"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {t("portal.operationsReadOnlyNotice")}
        </div>
      )}

      {/* Action Messages */}
      {actionError && (
        <div className="mw-notice-banner error" data-testid="risk-action-error" role="alert">
          {actionError}
        </div>
      )}
      {actionSuccess && (
        <div className="mw-notice-banner success" data-testid="risk-action-success" role="status">
          {actionSuccess}
        </div>
      )}

      {/* Header and Toolbar */}
      <div className="mw-card-header" style={{ marginBottom: "1rem" }}>
        <div>
          <h3 className="mw-card-title">{t("portal.tabRisks")}</h3>
          <p className="mw-card-subtitle">
            Identify, assess, and treat operational, security, and compliance risks with inherent and residual scores.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {canManage && (
            <button
              type="button"
              className="mw-btn mw-btn-primary btn-primary"
              data-testid="new-risk-btn"
              onClick={() => setIsCreating(true)}
            >
              {t("portal.createRecordBtn")}
            </button>
          )}
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-risks-btn"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? t("portal.refreshingOperationsBtn") : t("portal.refreshOperationsBtn")}
          </button>
        </div>
      </div>

      {/* Uncertain Create Recovery Banner */}
      {uncertainCreate && (
        <div
          className="mw-notice-banner"
          data-testid="risk-uncertain-banner"
          style={{ borderColor: "#ff9500", background: "#fffdf5", marginBottom: "1.25rem" }}
          role="alert"
        >
          <div style={{ fontWeight: 600 }}>
            {t("portal.uncertainCreateNotice") ||
              "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."}
          </div>
          <div style={{ fontSize: "0.85rem", margin: "0.3rem 0" }}>
            Title: <strong>{uncertainCreate.payload.title}</strong>
          </div>
          {reconcileError && <p style={{ color: "#b91c1c", margin: "0.25rem 0" }}>{reconcileError}</p>}
          {uncertainCreate.reconciled && (
            <div data-testid="risk-reconcile-results" style={{ margin: "0.5rem 0" }}>
              {uncertainCreate.matchingRisk ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    Found matching risk: <strong>{uncertainCreate.matchingRisk.title}</strong> (Score:{" "}
                    {uncertainCreate.matchingRisk.inherent_score})
                  </span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="confirm-reconciled-risk-btn"
                    onClick={() => handleConfirmReconcile(uncertainCreate.matchingRisk!)}
                  >
                    Adopt Existing Record
                  </button>
                </div>
              ) : (
                <div style={{ fontStyle: "italic", color: "#666" }}>
                  {t("portal.reconcileNotFound") || "No matching record was found on the server."}
                </div>
              )}
            </div>
          )}
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="check-reconcile-risk-btn"
              onClick={handleReconcileCreate}
              disabled={reconciling}
            >
              {reconciling ? "Checking Server..." : t("portal.checkReconcileBtn")}
            </button>
            {uncertainCreate.reconciled && !uncertainCreate.matchingRisk && (
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="force-resubmit-btn"
                onClick={handleAllowResubmit}
              >
                Acknowledge & Allow Resubmit
              </button>
            )}
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="dismiss-uncertain-risk-btn"
              onClick={handleDiscardUncertainCreate}
            >
              Abandon Draft
            </button>
          </div>
        </div>
      )}

      {/* New Risk Modal / Form */}
      {isCreating && (
        <div className="mw-card" data-testid="new-risk-form-card" style={{ marginBottom: "1.5rem" }}>
          <h4 style={{ margin: "0 0 1rem 0" }}>Register New Risk</h4>
          {createError && (
            <div className="mw-notice-banner error" data-testid="create-risk-error" role="alert">
              {createError}
            </div>
          )}
          <form onSubmit={handleCreateRisk}>
            <div className="mw-form-group">
              <label htmlFor="new-risk-title">Risk Title *</label>
              <input
                id="new-risk-title"
                data-testid="new-risk-title-input"
                type="text"
                className="mw-input"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Unauthorized Cloud S3 Bucket Access"
                required
              />
            </div>
            <div className="mw-form-group">
              <label htmlFor="new-risk-desc">Description</label>
              <textarea
                id="new-risk-desc"
                data-testid="new-risk-desc-input"
                className="mw-textarea"
                rows={2}
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Describe scenario, vulnerability, and impact"
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
              <div className="mw-form-group">
                <label htmlFor="new-risk-category">Category</label>
                <select
                  id="new-risk-category"
                  data-testid="new-risk-category-select"
                  className="mw-select"
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value as RiskCategory)}
                >
                  <option value="security">Security</option>
                  <option value="operational">Operational</option>
                  <option value="technical">Technical</option>
                  <option value="governance">Governance</option>
                  <option value="compliance">Compliance</option>
                  <option value="third_party">Third Party</option>
                  <option value="financial">Financial</option>
                </select>
              </div>
              <div className="mw-form-group">
                <label htmlFor="new-risk-likelihood">Likelihood (1–5)</label>
                <input
                  id="new-risk-likelihood"
                  data-testid="new-risk-likelihood-input"
                  type="number"
                  min={1}
                  max={5}
                  className="mw-input"
                  value={newLikelihood}
                  onChange={(e) => setNewLikelihood(Number(e.target.value))}
                />
              </div>
              <div className="mw-form-group">
                <label htmlFor="new-risk-impact">Impact (1–5)</label>
                <input
                  id="new-risk-impact"
                  data-testid="new-risk-impact-input"
                  type="number"
                  min={1}
                  max={5}
                  className="mw-input"
                  value={newImpact}
                  onChange={(e) => setNewImpact(Number(e.target.value))}
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
              <button
                type="submit"
                className="mw-btn mw-btn-primary btn-primary"
                data-testid="submit-create-risk-btn"
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                {createSubmitting ? "Creating..." : "Save Risk"}
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="cancel-create-risk-btn"
                onClick={() => setIsCreating(false)}
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingSwitchRiskId && (
        <div
          className="mw-notice-banner warning"
          data-testid="dirty-switch-guard"
          role="alert"
          style={{ marginBottom: "1rem" }}
        >
          <div>You have unsaved changes in this risk. Switching will discard your edits.</div>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="cancel-switch-btn"
              onClick={() => setPendingSwitchRiskId(null)}
            >
              Keep Editing
            </button>
            <button
              type="button"
              className="mw-btn mw-btn-danger"
              data-testid="confirm-discard-switch-btn"
              onClick={() => {
                const nextId = pendingSwitchRiskId;
                setPendingSwitchRiskId(null);
                setHasEditChanges(false);
                setSelectedRiskId(nextId);
              }}
            >
              Discard and Switch
            </button>
          </div>
        </div>
      )}

      {/* Master / Detail Layout */}
      <div
        className="mw-operations-grid"
        style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.25rem", alignItems: "start" }}
      >
        {/* Risks Master List */}
        <div className="mw-card" data-testid="risk-master-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h4 style={{ margin: 0 }}>Register ({filteredRisks.length})</h4>
            <select
              className="mw-select"
              data-testid="risk-category-filter"
              value={selectedCategoryFilter}
              onChange={(e) => setSelectedCategoryFilter(e.target.value)}
              style={{ width: "auto", fontSize: "0.85rem" }}
            >
              <option value="all">All Categories</option>
              <option value="security">Security</option>
              <option value="operational">Operational</option>
              <option value="technical">Technical</option>
              <option value="governance">Governance</option>
              <option value="compliance">Compliance</option>
              <option value="third_party">Third Party</option>
              <option value="financial">Financial</option>
            </select>
          </div>

          {filteredRisks.length === 0 ? (
            <div style={{ padding: "1.5rem", textAlign: "center", color: "#666", fontSize: "0.9rem" }}>
              No risks found matching current filter.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {filteredRisks.map((r) => {
                const isSelected = r.id === selectedRiskId;
                return (
                  <button
                    key={r.id}
                    type="button"
                    data-testid={`risk-row-${r.id}`}
                    onClick={() => handleSelectRisk(r.id)}
                    style={{
                      textAlign: "left",
                      padding: "0.75rem",
                      borderRadius: "6px",
                      border: isSelected ? "2px solid #0052cc" : "1px solid #e2e8f0",
                      background: isSelected ? "#f4f8ff" : "#fff",
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      gap: "0.25rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <strong style={{ fontSize: "0.95rem" }}>{r.title}</strong>
                      <span
                        className="mw-badge"
                        data-testid={`risk-score-badge-${r.id}`}
                        style={{
                          fontSize: "0.75rem",
                          background: r.inherent_score >= 15 ? "#ffebe6" : r.inherent_score >= 8 ? "#fff0b3" : "#e3fcef",
                          color: r.inherent_score >= 15 ? "#bf2600" : r.inherent_score >= 8 ? "#172b4d" : "#006644",
                        }}
                      >
                        Score: {r.inherent_score}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "#666" }}>
                      {r.category.toUpperCase()} • Status: {r.status}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Selected Risk Detail & Edit Form */}
        <div className="mw-card" data-testid="risk-detail-card">
          {!selectedRisk ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#666" }}>
              {t("portal.noRecordSelected")}
            </div>
          ) : (
            <div>
              {/* Header / Meta */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  borderBottom: "1px solid #eee",
                  paddingBottom: "1rem",
                  marginBottom: "1rem",
                }}
              >
                <div>
                  <h3 style={{ margin: "0 0 0.25rem 0" }}>{selectedRisk.title}</h3>
                  <div style={{ fontSize: "0.85rem", color: "#666" }}>
                    Inherent Score: <strong data-testid="detail-inherent-score">{selectedRisk.inherent_score}</strong> (L:{selectedRisk.likelihood} × I:{selectedRisk.impact}) •
                    Residual: {selectedRisk.residual_score ?? "Unrated"} •
                    Last Review: {selectedRisk.last_reviewed_at ? new Date(selectedRisk.last_reviewed_at).toLocaleDateString() : "Never"}
                  </div>
                </div>

                {canManage && (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="review-risk-btn"
                      onClick={handleReviewRisk}
                      disabled={Boolean(actionLoading)}
                    >
                      {actionLoading === "review" ? "Recording..." : t("portal.reviewRecordBtn")}
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="save-risk-draft-btn"
                      onClick={handleUpdateRisk}
                      disabled={Boolean(actionLoading) || !hasEditChanges}
                    >
                      {actionLoading === "save" ? "Saving..." : t("portal.saveDraftBtn")}
                    </button>
                  </div>
                )}
              </div>

              {/* Editable Risk Attributes */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="mw-form-group">
                  <label htmlFor="edit-risk-title">Title</label>
                  <input
                    id="edit-risk-title"
                    data-testid="edit-risk-title-input"
                    type="text"
                    className="mw-input"
                    value={editTitle}
                    disabled={!canManage}
                    onChange={(e) => {
                      setEditTitle(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div className="mw-form-group">
                  <label htmlFor="edit-risk-desc">Description</label>
                  <textarea
                    id="edit-risk-desc"
                    data-testid="edit-risk-desc-input"
                    className="mw-textarea"
                    rows={2}
                    value={editDesc}
                    disabled={!canManage}
                    onChange={(e) => {
                      setEditDesc(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "1rem" }}>
                  <div className="mw-form-group">
                    <label htmlFor="edit-risk-category">Category</label>
                    <select
                      id="edit-risk-category"
                      data-testid="edit-risk-category-select"
                      className="mw-select"
                      value={editCategory}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditCategory(e.target.value as RiskCategory);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="security">Security</option>
                      <option value="operational">Operational</option>
                      <option value="technical">Technical</option>
                      <option value="governance">Governance</option>
                      <option value="compliance">Compliance</option>
                      <option value="third_party">Third Party</option>
                      <option value="financial">Financial</option>
                    </select>
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-risk-likelihood">Likelihood (1–5)</label>
                    <input
                      id="edit-risk-likelihood"
                      data-testid="edit-risk-likelihood-input"
                      type="number"
                      min={1}
                      max={5}
                      className="mw-input"
                      value={editLikelihood}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditLikelihood(Number(e.target.value));
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-risk-impact">Impact (1–5)</label>
                    <input
                      id="edit-risk-impact"
                      data-testid="edit-risk-impact-input"
                      type="number"
                      min={1}
                      max={5}
                      className="mw-input"
                      value={editImpact}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditImpact(Number(e.target.value));
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-risk-status">Status</label>
                    <select
                      id="edit-risk-status"
                      data-testid="edit-risk-status-select"
                      className="mw-select"
                      value={editStatus}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditStatus(e.target.value as RiskStatus);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="identified">Identified</option>
                      <option value="assessed">Assessed</option>
                      <option value="treating">Treating</option>
                      <option value="monitored">Monitored</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Treatments Section */}
              <div style={{ marginTop: "1.5rem", borderTop: "1px solid #eee", paddingTop: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <h4 style={{ margin: 0 }}>
                    {t("portal.treatmentsTitle")} ({selectedRisk.treatments?.length || 0})
                  </h4>
                  {canManage && (
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="open-add-treatment-btn"
                      onClick={() => setIsAddingTreatment(true)}
                    >
                      {t("portal.addTreatmentBtn")}
                    </button>
                  )}
                </div>

                {/* Add Treatment Subform */}
                {isAddingTreatment && (
                  <form
                    onSubmit={handleAddTreatment}
                    data-testid="add-treatment-form"
                    style={{ background: "#f8f9fa", padding: "1rem", borderRadius: "6px", marginBottom: "1rem" }}
                  >
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "0.75rem" }}>
                      <div className="mw-form-group">
                        <label htmlFor="treat-strategy">Strategy</label>
                        <select
                          id="treat-strategy"
                          data-testid="treat-strategy-select"
                          className="mw-select"
                          value={treatStrategy}
                          onChange={(e) => setTreatStrategy(e.target.value as RiskTreatmentStrategy)}
                        >
                          <option value="mitigate">Mitigate</option>
                          <option value="accept">Accept</option>
                          <option value="transfer">Transfer</option>
                          <option value="avoid">Avoid</option>
                        </select>
                      </div>
                      <div className="mw-form-group">
                        <label htmlFor="treat-target-date">Target Due Date</label>
                        <input
                          id="treat-target-date"
                          data-testid="treat-target-date-input"
                          type="date"
                          className="mw-input"
                          value={treatTargetDate}
                          onChange={(e) => setTreatTargetDate(e.target.value)}
                        />
                      </div>
                    </div>
                    <div className="mw-form-group">
                      <label htmlFor="treat-plan">Action Plan *</label>
                      <textarea
                        id="treat-plan"
                        data-testid="treat-plan-input"
                        className="mw-textarea"
                        rows={2}
                        value={treatPlan}
                        onChange={(e) => setTreatPlan(e.target.value)}
                        placeholder="Specific control implementation or mitigation actions"
                        required
                      />
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                      <button
                        type="submit"
                        className="mw-btn mw-btn-primary"
                        data-testid="submit-treatment-btn"
                        disabled={treatSubmitting}
                      >
                        {treatSubmitting ? "Adding..." : "Save Treatment"}
                      </button>
                      <button
                        type="button"
                        className="mw-btn mw-btn-secondary"
                        onClick={() => setIsAddingTreatment(false)}
                        disabled={treatSubmitting}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                {/* Treatment List */}
                {(!selectedRisk.treatments || selectedRisk.treatments.length === 0) ? (
                  <div style={{ color: "#666", fontSize: "0.85rem" }}>
                    No treatments registered yet for this risk.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {selectedRisk.treatments.map((tr) => (
                      <div
                        key={tr.id}
                        data-testid={`treatment-row-${tr.id}`}
                        style={{
                          padding: "0.5rem 0.75rem",
                          border: "1px solid #e2e8f0",
                          borderRadius: "4px",
                          fontSize: "0.85rem",
                          background: "#fff",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <strong>{tr.strategy.toUpperCase()}: {tr.treatment_plan}</strong>
                          <span
                            className="mw-badge"
                            style={{ fontSize: "0.75rem", textTransform: "uppercase" }}
                          >
                            {tr.status}
                          </span>
                        </div>
                        {tr.target_date && (
                          <div style={{ color: "#666", fontSize: "0.8rem", marginTop: "0.25rem" }}>
                            Target: {tr.target_date}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

