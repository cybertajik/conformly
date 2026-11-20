import type { TenantRole } from "@conformly/shared";
import React, { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { canManageVendors, canReadVendors } from "../permissions";
import { ConflictError, CustomerDemoApiError, ForbiddenError, UnauthorizedError, ValidationError } from "./api";
import { createVendor, fetchVendors, reviewVendor, updateVendor } from "./operations-api";
import {
  Vendor,
  VendorCreateInput,
  VendorCriticality,
  VendorStatus,
} from "./operations-types";
import "./modern-workspace.css";

export interface VendorWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  vendors: Vendor[];
  loading?: boolean;
  onRefresh?: () => void;
  onSessionExpired?: () => void;
  onVendorMutated?: (updated: Vendor) => void;
  onVendorCreated?: (created: Vendor) => void;
  targetVendorId?: string | null;
  targetNonce?: number | null;
  onConsumeTarget?: () => void;
}

export const VendorWorkspaceV2: FC<VendorWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  vendors,
  loading = false,
  onRefresh,
  onSessionExpired,
  onVendorMutated,
  onVendorCreated,
  targetVendorId = null,
  targetNonce = null,
  onConsumeTarget,
}) => {
  const { t } = useTranslation();

  const isRoleDenied = !canReadVendors(userRole as TenantRole);
  const canManage = canManageVendors(userRole as TenantRole);

  const [selectedVendorId, setSelectedVendorId] = useState<string | null>(null);
  const [selectedCriticalityFilter, setSelectedCriticalityFilter] = useState<string>("all");

  // Edit / draft state
  const [editName, setEditName] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [editCriticality, setEditCriticality] = useState<VendorCriticality>("medium");
  const [editClassification, setEditClassification] = useState<string>("Confidential");
  const [editResidency, setEditResidency] = useState<string>("DE");
  const [editDpaSigned, setEditDpaSigned] = useState<boolean>(false);
  const [editStatus, setEditStatus] = useState<VendorStatus>("active");
  const [hasEditChanges, setHasEditChanges] = useState<boolean>(false);

  // New vendor modal / form state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newCriticality, setNewCriticality] = useState<VendorCriticality>("medium");
  const [newClassification, setNewClassification] = useState<string>("Confidential");
  const [newResidency, setNewResidency] = useState<string>("DE");
  const [newDpaSigned, setNewDpaSigned] = useState<boolean>(false);
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Action feedback states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [pendingSwitchVendorId, setPendingSwitchVendorId] = useState<string | null>(null);
  const createAttemptIdRef = useRef<number>(0);
  const mutationGenRef = useRef<number>(0);
  const selectedVendorIdRef = useRef<string | null>(selectedVendorId);
  useEffect(() => {
    selectedVendorIdRef.current = selectedVendorId;
  }, [selectedVendorId]);

  const consumedTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!targetVendorId) return;
      if (loading) return;
      const targetKey = `${targetVendorId}:${targetNonce ?? "static"}`;
      if (targetKey === consumedTargetKeyRef.current) return;
      const exists = vendors.some((v) => v.id === targetVendorId);
      if (exists) {
        consumedTargetKeyRef.current = targetKey;
        onConsumeTarget?.();
        if (hasEditChanges && selectedVendorId && selectedVendorId !== targetVendorId) {
          setPendingSwitchVendorId(targetVendorId);
        } else {
          setSelectedVendorId(targetVendorId);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [targetVendorId, targetNonce, onConsumeTarget, loading, vendors, hasEditChanges, selectedVendorId]);


  const contextRef = useRef({ tenantId, token });
  useEffect(() => {
    contextRef.current = { tenantId, token };
  }, [tenantId, token]);

  // Uncertain POST create recovery state
  const [uncertainCreate, setUncertainCreate] = useState<{
    payload: VendorCreateInput;
    reconciled?: boolean;
    matchingVendor?: Vendor | null;
    attemptId: number;
  } | null>(null);

  const selectedVendor = vendors.find((v) => v.id === selectedVendorId) || null;

  const lastSelectedVendorIdRef = useRef<string | null>(null);
  const hasEditChangesRef = useRef<boolean>(false);
  useEffect(() => {
    hasEditChangesRef.current = hasEditChanges;
  }, [hasEditChanges]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedVendor) {
        if (selectedVendor.id === lastSelectedVendorIdRef.current && hasEditChangesRef.current) {
          return;
        }
        lastSelectedVendorIdRef.current = selectedVendor.id;
        setEditName(selectedVendor.name);
        setEditDesc(selectedVendor.service_description);
        setEditCriticality(selectedVendor.criticality);
        setEditClassification(selectedVendor.data_classification_accessed);
        setEditResidency(selectedVendor.country_residency);
        setEditDpaSigned(selectedVendor.dpa_signed);
        setEditStatus("active");
        setHasEditChanges(false);
        setActionError(null);
        setActionSuccess(null);
      } else {
        setEditName("");
        setEditDesc("");
        setEditCriticality("medium");
        setEditClassification("Confidential");
        setEditResidency("DE");
        setEditDpaSigned(false);
        setEditStatus("active");
        setHasEditChanges(false);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedVendorId, selectedVendor]);

  const filteredVendors = vendors.filter((v) => {
    if (selectedCriticalityFilter === "all") return true;
    return v.criticality === selectedCriticalityFilter;
  });

  const handleCreateVendor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || createSubmitting || Boolean(uncertainCreate)) return;

    if (!newName.trim()) {
      setCreateError(t("portal.entityNameRequired") || "Name is required");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    const payload: VendorCreateInput = {
      name: newName.trim(),
      service_description: newDesc.trim(),
      criticality: newCriticality,
      data_classification_accessed: newClassification,
      country_residency: newResidency.trim().toUpperCase() || "DE",
      dpa_signed: newDpaSigned,
    };

    try {
      const created = await createVendor(tenantId, token, payload);
      onVendorCreated?.(created);
      setIsCreating(false);
      setNewName("");
      setNewDesc("");
      setSelectedVendorId(created.id);
      setActionSuccess(`Vendor registered: ${created.name}`);
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
        setCreateError(err instanceof Error ? err.message : "Failed to create vendor");
      } else {
        setUncertainCreate({
          payload,
          reconciled: false,
          matchingVendor: null,
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
      const freshList = await fetchVendors(attemptTenantId, attemptToken);
      if (
        attemptId !== createAttemptIdRef.current ||
        attemptTenantId !== contextRef.current.tenantId ||
        attemptToken !== contextRef.current.token
      ) {
        return;
      }
      const match = freshList.find(
        (v: Vendor) =>
          v.name.trim().toLowerCase() === uncertainCreate.payload.name.trim().toLowerCase() &&
          v.service_description.trim() === uncertainCreate.payload.service_description.trim() &&
          v.criticality === uncertainCreate.payload.criticality
      );
      setUncertainCreate({
        ...uncertainCreate,
        reconciled: true,
        matchingVendor: match || null,
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

  const handleConfirmReconcile = (matched: Vendor) => {
    setSelectedVendorId(matched.id);
    setUncertainCreate(null);
    setIsCreating(false);
    setActionSuccess(`${t("portal.reconciledSuccess")} (${matched.name})`);
  };

  const handleDiscardUncertainCreate = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
    setIsCreating(false);
    setNewName("");
    setNewDesc("");
  };

  const handleAllowResubmit = () => {
    setUncertainCreate(null);
    setCreateError(null);
    setReconcileError(null);
  };

  const handleSelectVendor = (vendorId: string) => {
    if (vendorId === selectedVendorId) return;
    if (hasEditChanges) {
      setPendingSwitchVendorId(vendorId);
      return;
    }
    setSelectedVendorId(vendorId);
  };

  const handleUpdateVendor = async () => {
    if (!selectedVendor || !canManage || actionLoading) return;
    setActionLoading("save");
    setActionError(null);
    setActionSuccess(null);
    const mutatingId = selectedVendor.id;
    const mutationGen = ++mutationGenRef.current;

    try {
      const updated = await updateVendor(tenantId, token, selectedVendor.id, {
        name: editName.trim(),
        service_description: editDesc.trim(),
        criticality: editCriticality,
        data_classification_accessed: editClassification,
        country_residency: selectedVendor.country_residency || "DE",
        dpa_signed: editDpaSigned,
        status: editStatus,
        owner_user_id: selectedVendor.owner_user_id ?? null,
        control_id: selectedVendor.control_id ?? null,
        finding_id: selectedVendor.finding_id ?? null,
        legal_entity_id: selectedVendor.legal_entity_id ?? null,
        business_unit_id: selectedVendor.business_unit_id ?? null,
      });
      if (mutatingId !== selectedVendorIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onVendorMutated?.(updated);
      setHasEditChanges(false);
      setActionSuccess("Vendor updated successfully.");
    } catch (err: unknown) {
      if (mutatingId !== selectedVendorIdRef.current || mutationGen !== mutationGenRef.current) {
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
        setActionError(err instanceof Error ? err.message : "Failed to update vendor.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleReviewVendor = async () => {
    if (!selectedVendor || !canManage || actionLoading) return;
    setActionLoading("review");
    setActionError(null);
    const mutatingId = selectedVendor.id;
    const mutationGen = ++mutationGenRef.current;
    try {
      const updated = await reviewVendor(tenantId, token, selectedVendor.id);
      if (mutatingId !== selectedVendorIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onVendorMutated?.(updated);
      setActionSuccess("Vendor security review recorded.");
    } catch (err: unknown) {
      if (mutatingId !== selectedVendorIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError(err instanceof Error ? err.message : "Failed to record vendor review.");
    } finally {
      setActionLoading(null);
    }
  };

  if (isRoleDenied) {
    return (
      <div className="mw-card" data-testid="vendor-workspace-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice")}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-operations-vendors" data-testid="vendor-workspace">
      {!canManage && (
        <div
          className="mw-notice-banner"
          data-testid="vendors-readonly-notice"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {t("portal.operationsReadOnlyNotice")}
        </div>
      )}

      {actionError && (
        <div className="mw-notice-banner error" data-testid="vendor-action-error" role="alert">
          {actionError}
        </div>
      )}
      {actionSuccess && (
        <div className="mw-notice-banner success" data-testid="vendor-action-success" role="status">
          {actionSuccess}
        </div>
      )}

      <div className="mw-card-header" style={{ marginBottom: "1rem" }}>
        <div>
          <h3 className="mw-card-title">{t("portal.tabVendors")}</h3>
          <p className="mw-card-subtitle">
            Manage supply-chain partners, criticality, data processing agreements (DPA), data residency, and security reviews.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {canManage && (
            <button
              type="button"
              className="mw-btn mw-btn-primary btn-primary"
              data-testid="new-vendor-btn"
              onClick={() => setIsCreating(true)}
            >
              {t("portal.createRecordBtn")}
            </button>
          )}
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-vendors-btn"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? t("portal.refreshingOperationsBtn") : t("portal.refreshOperationsBtn")}
          </button>
        </div>
      </div>

      {uncertainCreate && (
        <div
          className="mw-notice-banner"
          data-testid="vendor-uncertain-banner"
          style={{ borderColor: "#ff9500", background: "#fffdf5", marginBottom: "1.25rem" }}
          role="alert"
        >
          <div style={{ fontWeight: 600 }}>
            {t("portal.uncertainCreateNotice") ||
              "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."}
          </div>
          <div style={{ fontSize: "0.85rem", margin: "0.3rem 0" }}>
            Vendor Name: <strong>{uncertainCreate.payload.name}</strong>
          </div>
          {reconcileError && <p style={{ color: "#b91c1c", margin: "0.25rem 0" }}>{reconcileError}</p>}
          {uncertainCreate.reconciled && (
            <div data-testid="vendor-reconcile-results" style={{ margin: "0.5rem 0" }}>
              {uncertainCreate.matchingVendor ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    Found matching vendor: <strong>{uncertainCreate.matchingVendor.name}</strong> (
                    {uncertainCreate.matchingVendor.criticality})
                  </span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="confirm-reconciled-vendor-btn"
                    onClick={() => handleConfirmReconcile(uncertainCreate.matchingVendor!)}
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
              data-testid="check-reconcile-vendor-btn"
              onClick={handleReconcileCreate}
              disabled={reconciling}
            >
              {reconciling ? "Checking Server..." : t("portal.checkReconcileBtn")}
            </button>
            {uncertainCreate.reconciled && !uncertainCreate.matchingVendor && (
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
              data-testid="dismiss-uncertain-vendor-btn"
              onClick={handleDiscardUncertainCreate}
            >
              Abandon Draft
            </button>
          </div>
        </div>
      )}

      {isCreating && (
        <div className="mw-card" data-testid="new-vendor-form-card" style={{ marginBottom: "1.5rem" }}>
          <h4 style={{ margin: "0 0 1rem 0" }}>Register New Vendor</h4>
          {createError && (
            <div className="mw-notice-banner error" data-testid="create-vendor-error" role="alert">
              {createError}
            </div>
          )}
          <form onSubmit={handleCreateVendor}>
            <div className="mw-form-group">
              <label htmlFor="new-vendor-name">Vendor Name *</label>
              <input
                id="new-vendor-name"
                data-testid="new-vendor-name-input"
                type="text"
                className="mw-input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Amazon Web Services EMEA SARL"
                required
              />
            </div>
            <div className="mw-form-group">
              <label htmlFor="new-vendor-desc">Service Description</label>
              <textarea
                id="new-vendor-desc"
                data-testid="new-vendor-desc-input"
                className="mw-textarea"
                rows={2}
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Cloud infrastructure, data processing, and hosting"
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
              <div className="mw-form-group">
                <label htmlFor="new-vendor-criticality">Criticality</label>
                <select
                  id="new-vendor-criticality"
                  data-testid="new-vendor-criticality-select"
                  className="mw-select"
                  value={newCriticality}
                  onChange={(e) => setNewCriticality(e.target.value as VendorCriticality)}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div className="mw-form-group">
                <label htmlFor="new-vendor-classification">Data Classification</label>
                <input
                  id="new-vendor-classification"
                  data-testid="new-vendor-classification-input"
                  type="text"
                  className="mw-input"
                  value={newClassification}
                  onChange={(e) => setNewClassification(e.target.value)}
                />
              </div>
              <div className="mw-form-group">
                <label htmlFor="new-vendor-residency">Country Residency (2-letter)</label>
                <input
                  id="new-vendor-residency"
                  data-testid="new-vendor-residency-input"
                  type="text"
                  maxLength={2}
                  className="mw-input"
                  value={newResidency}
                  onChange={(e) => setNewResidency(e.target.value.toUpperCase())}
                />
              </div>
            </div>
            <div className="mw-form-group" style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.5rem" }}>
              <input
                id="new-vendor-dpa"
                data-testid="new-vendor-dpa-checkbox"
                type="checkbox"
                checked={newDpaSigned}
                onChange={(e) => setNewDpaSigned(e.target.checked)}
              />
              <label htmlFor="new-vendor-dpa" style={{ margin: 0 }}>
                Data Processing Agreement (DPA) Signed & Executed
              </label>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
              <button
                type="submit"
                className="mw-btn mw-btn-primary btn-primary"
                data-testid="submit-create-vendor-btn"
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                {createSubmitting ? "Creating..." : "Save Vendor"}
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="cancel-create-vendor-btn"
                onClick={() => setIsCreating(false)}
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingSwitchVendorId && (
        <div
          className="mw-notice-banner warning"
          data-testid="dirty-switch-guard"
          role="alert"
          style={{ marginBottom: "1rem" }}
        >
          <div>You have unsaved changes in this vendor. Switching will discard your edits.</div>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="cancel-switch-btn"
              onClick={() => setPendingSwitchVendorId(null)}
            >
              Keep Editing
            </button>
            <button
              type="button"
              className="mw-btn mw-btn-danger"
              data-testid="confirm-discard-switch-btn"
              onClick={() => {
                const nextId = pendingSwitchVendorId;
                setPendingSwitchVendorId(null);
                setHasEditChanges(false);
                setSelectedVendorId(nextId);
              }}
            >
              Discard and Switch
            </button>
          </div>
        </div>
      )}

      <div
        className="mw-operations-grid"
        style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1.25rem", alignItems: "start" }}
      >
        <div className="mw-card" data-testid="vendor-master-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h4 style={{ margin: 0 }}>Register ({filteredVendors.length})</h4>
            <select
              className="mw-select"
              data-testid="vendor-criticality-filter"
              value={selectedCriticalityFilter}
              onChange={(e) => setSelectedCriticalityFilter(e.target.value)}
              style={{ width: "auto", fontSize: "0.85rem" }}
            >
              <option value="all">All Criticalities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>

          {filteredVendors.length === 0 ? (
            <div style={{ padding: "1.5rem", textAlign: "center", color: "#666", fontSize: "0.9rem" }}>
              No vendors found matching current filter.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {filteredVendors.map((v) => {
                const isSelected = v.id === selectedVendorId;
                return (
                  <button
                    key={v.id}
                    type="button"
                    data-testid={`vendor-row-${v.id}`}
                    onClick={() => handleSelectVendor(v.id)}
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
                      <strong style={{ fontSize: "0.95rem" }}>{v.name}</strong>
                      <span
                        className="mw-badge"
                        data-testid={`vendor-criticality-badge-${v.id}`}
                        style={{
                          fontSize: "0.75rem",
                          textTransform: "uppercase",
                          background: v.criticality === "critical" ? "#ffebe6" : "#f4f5f7",
                          color: v.criticality === "critical" ? "#bf2600" : "#172b4d",
                        }}
                      >
                        {v.criticality}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "#666" }}>
                      Country: {v.country_residency} • DPA: {v.dpa_signed ? "Signed" : "Pending"}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="mw-card" data-testid="vendor-detail-card">
          {!selectedVendor ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#666" }}>
              {t("portal.noRecordSelected")}
            </div>
          ) : (
            <div>
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
                  <h3 style={{ margin: "0 0 0.25rem 0" }}>{selectedVendor.name}</h3>
                  <div style={{ fontSize: "0.85rem", color: "#666" }}>
                    Criticality: <strong data-testid="detail-vendor-criticality">{selectedVendor.criticality}</strong> •
                    Residency: {selectedVendor.country_residency} •
                    DPA: {selectedVendor.dpa_signed ? "Executed" : "Missing"} •
                    Last Review: {selectedVendor.security_reviewed_at ? new Date(selectedVendor.security_reviewed_at).toLocaleDateString() : "Never"}
                  </div>
                </div>

                {canManage && (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="review-vendor-btn"
                      onClick={handleReviewVendor}
                      disabled={Boolean(actionLoading)}
                    >
                      {actionLoading === "review" ? "Recording..." : t("portal.reviewRecordBtn")}
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="save-vendor-draft-btn"
                      onClick={handleUpdateVendor}
                      disabled={Boolean(actionLoading) || !hasEditChanges}
                    >
                      {actionLoading === "save" ? "Saving..." : t("portal.saveDraftBtn")}
                    </button>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="mw-form-group">
                  <label htmlFor="edit-vendor-name">Vendor Name</label>
                  <input
                    id="edit-vendor-name"
                    data-testid="edit-vendor-name-input"
                    type="text"
                    className="mw-input"
                    value={editName}
                    disabled={!canManage}
                    onChange={(e) => {
                      setEditName(e.target.value);
                      setHasEditChanges(true);
                    }}
                  />
                </div>

                <div className="mw-form-group">
                  <label htmlFor="edit-vendor-desc">Service Description</label>
                  <textarea
                    id="edit-vendor-desc"
                    data-testid="edit-vendor-desc-input"
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

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                  <div className="mw-form-group">
                    <label htmlFor="edit-vendor-criticality">Criticality</label>
                    <select
                      id="edit-vendor-criticality"
                      data-testid="edit-vendor-criticality-select"
                      className="mw-select"
                      value={editCriticality}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditCriticality(e.target.value as VendorCriticality);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-vendor-classification">Data Classification</label>
                    <input
                      id="edit-vendor-classification"
                      data-testid="edit-vendor-classification-input"
                      type="text"
                      className="mw-input"
                      value={editClassification}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditClassification(e.target.value);
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-vendor-residency">Country Residency (2-letter)</label>
                    <input
                      id="edit-vendor-residency"
                      data-testid="edit-vendor-residency-input"
                      type="text"
                      maxLength={2}
                      className="mw-input"
                      value={editResidency}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditResidency(e.target.value.toUpperCase());
                        setHasEditChanges(true);
                      }}
                    />
                  </div>
                </div>

                <div className="mw-form-group" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <input
                    id="edit-vendor-dpa"
                    data-testid="edit-vendor-dpa-checkbox"
                    type="checkbox"
                    checked={editDpaSigned}
                    disabled={!canManage}
                    onChange={(e) => {
                      setEditDpaSigned(e.target.checked);
                      setHasEditChanges(true);
                    }}
                  />
                  <label htmlFor="edit-vendor-dpa" style={{ margin: 0 }}>
                    Data Processing Agreement (DPA) Signed & Executed
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

