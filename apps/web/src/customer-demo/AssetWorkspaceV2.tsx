import type { TenantRole } from "@conformly/shared";
import React, { FC, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { canManageAssets, canReadAssets } from "../permissions";
import { ConflictError, CustomerDemoApiError, ForbiddenError, UnauthorizedError, ValidationError } from "./api";
import { createAsset, fetchAssets, reviewAsset, updateAsset } from "./operations-api";
import {
  Asset,
  AssetClassification,
  AssetCreateInput,
  AssetStatus,
  AssetType,
} from "./operations-types";
import "./modern-workspace.css";

export interface AssetWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  assets: Asset[];
  loading?: boolean;
  onRefresh?: () => void;
  onSessionExpired?: () => void;
  onAssetMutated?: (updated: Asset) => void;
  onAssetCreated?: (created: Asset) => void;
  targetAssetId?: string | null;
  targetNonce?: number | null;
  onConsumeTarget?: () => void;
}

export const AssetWorkspaceV2: FC<AssetWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  assets,
  loading = false,
  onRefresh,
  onSessionExpired,
  onAssetMutated,
  onAssetCreated,
  targetAssetId = null,
  targetNonce = null,
  onConsumeTarget,
}) => {
  const { t } = useTranslation();

  const isRoleDenied = !canReadAssets(userRole as TenantRole);
  const canManage = canManageAssets(userRole as TenantRole);

  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>("all");

  // Edit / draft state
  const [editName, setEditName] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [editType, setEditType] = useState<AssetType>("software");
  const [editClassification, setEditClassification] = useState<AssetClassification>("internal");
  const [editStatus, setEditStatus] = useState<AssetStatus>("active");
  const [hasEditChanges, setHasEditChanges] = useState<boolean>(false);

  // New asset modal / form state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>("");
  const [newDesc, setNewDesc] = useState<string>("");
  const [newType, setNewType] = useState<AssetType>("software");
  const [newClassification, setNewClassification] = useState<AssetClassification>("internal");
  const [createSubmitting, setCreateSubmitting] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Action feedback states
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const [pendingSwitchAssetId, setPendingSwitchAssetId] = useState<string | null>(null);
  const createAttemptIdRef = useRef<number>(0);
  const mutationGenRef = useRef<number>(0);
  const selectedAssetIdRef = useRef<string | null>(selectedAssetId);
  useEffect(() => {
    selectedAssetIdRef.current = selectedAssetId;
  }, [selectedAssetId]);

  const consumedTargetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!targetAssetId) return;
      if (loading) return;
      const targetKey = `${targetAssetId}:${targetNonce ?? "static"}`;
      if (targetKey === consumedTargetKeyRef.current) return;
      const exists = assets.some((a) => a.id === targetAssetId);
      if (exists) {
        consumedTargetKeyRef.current = targetKey;
        onConsumeTarget?.();
        if (hasEditChanges && selectedAssetId && selectedAssetId !== targetAssetId) {
          setPendingSwitchAssetId(targetAssetId);
        } else {
          setSelectedAssetId(targetAssetId);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [targetAssetId, targetNonce, onConsumeTarget, loading, assets, hasEditChanges, selectedAssetId]);


  const contextRef = useRef({ tenantId, token });
  useEffect(() => {
    contextRef.current = { tenantId, token };
  }, [tenantId, token]);

  // Uncertain POST create recovery state
  const [uncertainCreate, setUncertainCreate] = useState<{
    payload: AssetCreateInput;
    reconciled?: boolean;
    matchingAsset?: Asset | null;
    attemptId: number;
  } | null>(null);

  const selectedAsset = assets.find((a) => a.id === selectedAssetId) || null;

  const lastSelectedAssetIdRef = useRef<string | null>(null);
  const hasEditChangesRef = useRef<boolean>(false);
  useEffect(() => {
    hasEditChangesRef.current = hasEditChanges;
  }, [hasEditChanges]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedAsset) {
        if (selectedAsset.id === lastSelectedAssetIdRef.current && hasEditChangesRef.current) {
          return;
        }
        lastSelectedAssetIdRef.current = selectedAsset.id;
        setEditName(selectedAsset.name);
        setEditDesc(selectedAsset.description || "");
        setEditType(selectedAsset.asset_type);
        setEditClassification(selectedAsset.classification);
        setEditStatus(selectedAsset.status);
        setHasEditChanges(false);
        setActionError(null);
        setActionSuccess(null);
      } else {
        setEditName("");
        setEditDesc("");
        setEditType("software");
        setEditClassification("internal");
        setEditStatus("active");
        setHasEditChanges(false);
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [selectedAssetId, selectedAsset]);

  const filteredAssets = assets.filter((a) => {
    if (selectedTypeFilter === "all") return true;
    return a.asset_type === selectedTypeFilter;
  });

  const handleCreateAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || createSubmitting || Boolean(uncertainCreate)) return;

    if (!newName.trim()) {
      setCreateError(t("portal.entityNameRequired") || "Name is required");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);

    const payload: AssetCreateInput = {
      name: newName.trim(),
      description: newDesc.trim() || null,
      asset_type: newType,
      classification: newClassification,
    };

    try {
      const created = await createAsset(tenantId, token, payload);
      onAssetCreated?.(created);
      setIsCreating(false);
      setNewName("");
      setNewDesc("");
      setSelectedAssetId(created.id);
      setActionSuccess(`Asset registered: ${created.name}`);
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
        setCreateError(err instanceof Error ? err.message : "Failed to create asset");
      } else {
        setUncertainCreate({
          payload,
          reconciled: false,
          matchingAsset: null,
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
      const freshList = await fetchAssets(attemptTenantId, attemptToken);
      if (
        attemptId !== createAttemptIdRef.current ||
        attemptTenantId !== contextRef.current.tenantId ||
        attemptToken !== contextRef.current.token
      ) {
        return;
      }
      const match = freshList.find(
        (a: Asset) =>
          a.name.trim().toLowerCase() === uncertainCreate.payload.name.trim().toLowerCase() &&
          a.asset_type === uncertainCreate.payload.asset_type &&
          a.classification === uncertainCreate.payload.classification
      );
      setUncertainCreate({
        ...uncertainCreate,
        reconciled: true,
        matchingAsset: match || null,
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

  const handleConfirmReconcile = (matched: Asset) => {
    setSelectedAssetId(matched.id);
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

  const handleSelectAsset = (assetId: string) => {
    if (assetId === selectedAssetId) return;
    if (hasEditChanges) {
      setPendingSwitchAssetId(assetId);
      return;
    }
    setSelectedAssetId(assetId);
  };

  const handleUpdateAsset = async () => {
    if (!selectedAsset || !canManage || actionLoading) return;
    setActionLoading("save");
    setActionError(null);
    setActionSuccess(null);
    const mutatingId = selectedAsset.id;
    const mutationGen = ++mutationGenRef.current;

    try {
      const updated = await updateAsset(tenantId, token, selectedAsset.id, {
        name: editName.trim(),
        description: editDesc.trim() || null,
        asset_type: editType,
        classification: editClassification,
        status: editStatus,
        owner_user_id: selectedAsset.owner_user_id ?? null,
        control_id: selectedAsset.control_id ?? null,
        finding_id: selectedAsset.finding_id ?? null,
        legal_entity_id: selectedAsset.legal_entity_id ?? null,
        business_unit_id: selectedAsset.business_unit_id ?? null,
      });
      if (mutatingId !== selectedAssetIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onAssetMutated?.(updated);
      setHasEditChanges(false);
      setActionSuccess("Asset updated successfully.");
    } catch (err: unknown) {
      if (mutatingId !== selectedAssetIdRef.current || mutationGen !== mutationGenRef.current) {
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
        setActionError(err instanceof Error ? err.message : "Failed to update asset.");
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleReviewAsset = async () => {
    if (!selectedAsset || !canManage || actionLoading) return;
    setActionLoading("review");
    setActionError(null);
    const mutatingId = selectedAsset.id;
    const mutationGen = ++mutationGenRef.current;
    try {
      const updated = await reviewAsset(tenantId, token, selectedAsset.id);
      if (mutatingId !== selectedAssetIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      onAssetMutated?.(updated);
      setActionSuccess("Asset review recorded.");
    } catch (err: unknown) {
      if (mutatingId !== selectedAssetIdRef.current || mutationGen !== mutationGenRef.current) {
        return;
      }
      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      setActionError(err instanceof Error ? err.message : "Failed to record asset review.");
    } finally {
      setActionLoading(null);
    }
  };

  if (isRoleDenied) {
    return (
      <div className="mw-card" data-testid="asset-workspace-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice")}
        </div>
      </div>
    );
  }

  return (
    <div className="mw-operations-assets" data-testid="asset-workspace">
      {!canManage && (
        <div
          className="mw-notice-banner"
          data-testid="assets-readonly-notice"
          style={{ marginBottom: "1rem" }}
          role="status"
        >
          {t("portal.operationsReadOnlyNotice")}
        </div>
      )}

      {actionError && (
        <div className="mw-notice-banner error" data-testid="asset-action-error" role="alert">
          {actionError}
        </div>
      )}
      {actionSuccess && (
        <div className="mw-notice-banner success" data-testid="asset-action-success" role="status">
          {actionSuccess}
        </div>
      )}

      <div className="mw-card-header" style={{ marginBottom: "1rem" }}>
        <div>
          <h3 className="mw-card-title">{t("portal.tabAssets")}</h3>
          <p className="mw-card-subtitle">
            Maintain technical, data, hardware, cloud, and facility assets with security classifications and periodic reviews.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
          {canManage && (
            <button
              type="button"
              className="mw-btn mw-btn-primary btn-primary"
              data-testid="new-asset-btn"
              onClick={() => setIsCreating(true)}
            >
              {t("portal.createRecordBtn")}
            </button>
          )}
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-assets-btn"
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
          data-testid="asset-uncertain-banner"
          style={{ borderColor: "#ff9500", background: "#fffdf5", marginBottom: "1.25rem" }}
          role="alert"
        >
          <div style={{ fontWeight: 600 }}>
            {t("portal.uncertainCreateNotice") ||
              "Create outcome uncertain due to network or server error. Please reconcile with server state before proceeding."}
          </div>
          <div style={{ fontSize: "0.85rem", margin: "0.3rem 0" }}>
            Asset Name: <strong>{uncertainCreate.payload.name}</strong>
          </div>
          {reconcileError && <p style={{ color: "#b91c1c", margin: "0.25rem 0" }}>{reconcileError}</p>}
          {uncertainCreate.reconciled && (
            <div data-testid="asset-reconcile-results" style={{ margin: "0.5rem 0" }}>
              {uncertainCreate.matchingAsset ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    Found matching asset: <strong>{uncertainCreate.matchingAsset.name}</strong> (
                    {uncertainCreate.matchingAsset.classification})
                  </span>
                  <button
                    type="button"
                    className="mw-btn mw-btn-primary"
                    data-testid="confirm-reconciled-asset-btn"
                    onClick={() => handleConfirmReconcile(uncertainCreate.matchingAsset!)}
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
              data-testid="check-reconcile-asset-btn"
              onClick={handleReconcileCreate}
              disabled={reconciling}
            >
              {reconciling ? "Checking Server..." : t("portal.checkReconcileBtn")}
            </button>
            {uncertainCreate.reconciled && !uncertainCreate.matchingAsset && (
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
              data-testid="dismiss-uncertain-asset-btn"
              onClick={handleDiscardUncertainCreate}
            >
              Abandon Draft
            </button>
          </div>
        </div>
      )}

      {isCreating && (
        <div className="mw-card" data-testid="new-asset-form-card" style={{ marginBottom: "1.5rem" }}>
          <h4 style={{ margin: "0 0 1rem 0" }}>Register New Asset</h4>
          {createError && (
            <div className="mw-notice-banner error" data-testid="create-asset-error" role="alert">
              {createError}
            </div>
          )}
          <form onSubmit={handleCreateAsset}>
            <div className="mw-form-group">
              <label htmlFor="new-asset-name">Asset Name *</label>
              <input
                id="new-asset-name"
                data-testid="new-asset-name-input"
                type="text"
                className="mw-input"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Production PostgreSQL Database Cluster"
                required
              />
            </div>
            <div className="mw-form-group">
              <label htmlFor="new-asset-desc">Description</label>
              <textarea
                id="new-asset-desc"
                data-testid="new-asset-desc-input"
                className="mw-textarea"
                rows={2}
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Environment, purpose, or data stored"
              />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div className="mw-form-group">
                <label htmlFor="new-asset-type">Asset Type</label>
                <select
                  id="new-asset-type"
                  data-testid="new-asset-type-select"
                  className="mw-select"
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as AssetType)}
                >
                  <option value="software">Software / Service</option>
                  <option value="data">Data / Database</option>
                  <option value="cloud_service">Cloud Service</option>
                  <option value="hardware">Hardware / Device</option>
                  <option value="facility">Facility / Office</option>
                  <option value="personnel">Personnel / Roles</option>
                </select>
              </div>
              <div className="mw-form-group">
                <label htmlFor="new-asset-classification">Classification</label>
                <select
                  id="new-asset-classification"
                  data-testid="new-asset-classification-select"
                  className="mw-select"
                  value={newClassification}
                  onChange={(e) => setNewClassification(e.target.value as AssetClassification)}
                >
                  <option value="public">Public</option>
                  <option value="internal">Internal</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted</option>
                </select>
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
              <button
                type="submit"
                className="mw-btn mw-btn-primary btn-primary"
                data-testid="submit-create-asset-btn"
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                {createSubmitting ? "Creating..." : "Save Asset"}
              </button>
              <button
                type="button"
                className="mw-btn mw-btn-secondary"
                data-testid="cancel-create-asset-btn"
                onClick={() => setIsCreating(false)}
                disabled={createSubmitting || Boolean(uncertainCreate)}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {pendingSwitchAssetId && (
        <div
          className="mw-notice-banner warning"
          data-testid="dirty-switch-guard"
          role="alert"
          style={{ marginBottom: "1rem" }}
        >
          <div>You have unsaved changes in this asset. Switching will discard your edits.</div>
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="cancel-switch-btn"
              onClick={() => setPendingSwitchAssetId(null)}
            >
              Keep Editing
            </button>
            <button
              type="button"
              className="mw-btn mw-btn-danger"
              data-testid="confirm-discard-switch-btn"
              onClick={() => {
                const nextId = pendingSwitchAssetId;
                setPendingSwitchAssetId(null);
                setHasEditChanges(false);
                setSelectedAssetId(nextId);
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
        <div className="mw-card" data-testid="asset-master-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h4 style={{ margin: 0 }}>Register ({filteredAssets.length})</h4>
            <select
              className="mw-select"
              data-testid="asset-type-filter"
              value={selectedTypeFilter}
              onChange={(e) => setSelectedTypeFilter(e.target.value)}
              style={{ width: "auto", fontSize: "0.85rem" }}
            >
              <option value="all">All Types</option>
              <option value="software">Software</option>
              <option value="data">Data</option>
              <option value="cloud_service">Cloud Service</option>
              <option value="hardware">Hardware</option>
              <option value="facility">Facility</option>
              <option value="personnel">Personnel</option>
            </select>
          </div>

          {filteredAssets.length === 0 ? (
            <div style={{ padding: "1.5rem", textAlign: "center", color: "#666", fontSize: "0.9rem" }}>
              No assets found matching current filter.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {filteredAssets.map((a) => {
                const isSelected = a.id === selectedAssetId;
                return (
                  <button
                    key={a.id}
                    type="button"
                    data-testid={`asset-row-${a.id}`}
                    onClick={() => handleSelectAsset(a.id)}
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
                      <strong style={{ fontSize: "0.95rem" }}>{a.name}</strong>
                      <span
                        className="mw-badge"
                        data-testid={`asset-classification-badge-${a.id}`}
                        style={{ fontSize: "0.75rem", textTransform: "uppercase" }}
                      >
                        {a.classification}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "#666" }}>
                      {a.asset_type.toUpperCase()} • Status: {a.status}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="mw-card" data-testid="asset-detail-card">
          {!selectedAsset ? (
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
                  <h3 style={{ margin: "0 0 0.25rem 0" }}>{selectedAsset.name}</h3>
                  <div style={{ fontSize: "0.85rem", color: "#666" }}>
                    Type: <strong data-testid="detail-asset-type">{selectedAsset.asset_type}</strong> •
                    Classification: {selectedAsset.classification.toUpperCase()} •
                    Last Review: {selectedAsset.last_reviewed_at ? new Date(selectedAsset.last_reviewed_at).toLocaleDateString() : "Never"}
                  </div>
                </div>

                {canManage && (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      className="mw-btn mw-btn-secondary"
                      data-testid="review-asset-btn"
                      onClick={handleReviewAsset}
                      disabled={Boolean(actionLoading)}
                    >
                      {actionLoading === "review" ? "Recording..." : t("portal.reviewRecordBtn")}
                    </button>
                    <button
                      type="button"
                      className="mw-btn mw-btn-primary"
                      data-testid="save-asset-draft-btn"
                      onClick={handleUpdateAsset}
                      disabled={Boolean(actionLoading) || !hasEditChanges}
                    >
                      {actionLoading === "save" ? "Saving..." : t("portal.saveDraftBtn")}
                    </button>
                  </div>
                )}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div className="mw-form-group">
                  <label htmlFor="edit-asset-name">Asset Name</label>
                  <input
                    id="edit-asset-name"
                    data-testid="edit-asset-name-input"
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
                  <label htmlFor="edit-asset-desc">Description</label>
                  <textarea
                    id="edit-asset-desc"
                    data-testid="edit-asset-desc-input"
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
                    <label htmlFor="edit-asset-type">Asset Type</label>
                    <select
                      id="edit-asset-type"
                      data-testid="edit-asset-type-select"
                      className="mw-select"
                      value={editType}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditType(e.target.value as AssetType);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="software">Software / Service</option>
                      <option value="data">Data / Database</option>
                      <option value="cloud_service">Cloud Service</option>
                      <option value="hardware">Hardware / Device</option>
                      <option value="facility">Facility / Office</option>
                      <option value="personnel">Personnel / Roles</option>
                    </select>
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-asset-classification">Classification</label>
                    <select
                      id="edit-asset-classification"
                      data-testid="edit-asset-classification-select"
                      className="mw-select"
                      value={editClassification}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditClassification(e.target.value as AssetClassification);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="public">Public</option>
                      <option value="internal">Internal</option>
                      <option value="confidential">Confidential</option>
                      <option value="restricted">Restricted</option>
                    </select>
                  </div>
                  <div className="mw-form-group">
                    <label htmlFor="edit-asset-status">Status</label>
                    <select
                      id="edit-asset-status"
                      data-testid="edit-asset-status-select"
                      className="mw-select"
                      value={editStatus}
                      disabled={!canManage}
                      onChange={(e) => {
                        setEditStatus(e.target.value as AssetStatus);
                        setHasEditChanges(true);
                      }}
                    >
                      <option value="active">Active</option>
                      <option value="in_maintenance">In Maintenance</option>
                      <option value="decommissioned">Decommissioned</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

