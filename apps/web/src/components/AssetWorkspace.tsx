import type {
  AssetCriticality,
  AssetItemSummary,
  AssetType,
  DataClassification,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import { createAsset, listAssets } from "../api";
import { getAccessToken } from "../auth";
import { canManageAssets } from "../permissions";

interface AssetWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
}

export function AssetWorkspace({ tenantId, userRole }: AssetWorkspaceProps) {
  const [assets, setAssets] = useState<AssetItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [criticalityFilter, setCriticalityFilter] = useState<string>("");

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [assetType, setAssetType] = useState<AssetType>("cloud_service");
  const [criticality, setCriticality] = useState<AssetCriticality>("high");
  const [classification, setClassification] = useState<DataClassification>("Confidential");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");

  const canManage = canManageAssets(userRole);

  const loadAssets = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    try {
      setError(null);
      const data = await listAssets(token, tenantId, {
        asset_type: (typeFilter || undefined) as AssetType | undefined,
        criticality: (criticalityFilter || undefined) as AssetCriticality | undefined,
      });
      setAssets(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load assets");
    } finally {
      setLoading(false);
    }
  }, [tenantId, typeFilter, criticalityFilter]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadAssets();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadAssets]);

  async function handleCreateAsset(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !name.trim()) return;

    try {
      await createAsset(token, tenantId, {
        name: name.trim(),
        identifier: identifier.trim() || null,
        asset_type: assetType,
        criticality: criticality,
        classification: classification,
        location: location.trim() || null,
        description: description.trim() || null,
      });
      setShowCreateModal(false);
      setName("");
      setIdentifier("");
      setLocation("");
      setDescription("");
      setSuccessMessage("Asset registered successfully in inventory.");
      await loadAssets();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register asset");
    }
  }

  const criticalCount = assets.filter((a) => a.criticality === "critical").length;
  const highCount = assets.filter((a) => a.criticality === "high").length;
  const cloudCount = assets.filter((a) => a.asset_type === "cloud_service").length;
  const dataCount = assets.filter((a) => a.asset_type === "data").length;

  function getCriticalityBadge(c: AssetCriticality) {
    switch (c) {
      case "critical":
        return <span className="badge badge-danger">Critical</span>;
      case "high":
        return <span className="badge badge-warning">High</span>;
      case "medium":
        return <span className="badge badge-info">Medium</span>;
      case "low":
        return <span className="badge badge-success">Low</span>;
    }
  }

  function getClassificationBadge(cls: DataClassification) {
    switch (cls) {
      case "Restricted":
        return <span className="badge badge-danger">Restricted (AES-256)</span>;
      case "Confidential":
        return <span className="badge badge-warning">Confidential</span>;
      case "Internal":
        return <span className="badge badge-info">Internal</span>;
      case "Public":
        return <span className="badge badge-success">Public</span>;
    }
  }

  return (
    <div className="workspace-container">
      <div className="workspace-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="workspace-title">Asset Register</h1>
          <p className="workspace-subtitle">
            System, software, cloud infrastructure, and data asset inventory mapped to classifications and security controls.
          </p>
        </div>
        {canManage && (
          <button className="primary" onClick={() => setShowCreateModal(true)}>
            + Register New Asset
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {successMessage && <div className="success-banner">{successMessage}</div>}

      {/* Metrics Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="metric-card">
          <span className="metric-label">Total Assets</span>
          <span className="metric-value">{assets.length}</span>
          <span className="metric-subtext">Catalogued assets</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Critical Tier</span>
          <span className="metric-value" style={{ color: "var(--color-danger)" }}>{criticalCount}</span>
          <span className="metric-subtext">Tier 1 critical assets</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">High Tier</span>
          <span className="metric-value" style={{ color: "var(--color-warning)" }}>{highCount}</span>
          <span className="metric-subtext">High sensitivity assets</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Cloud / Data Assets</span>
          <span className="metric-value" style={{ color: "var(--accent)" }}>{cloudCount + dataCount}</span>
          <span className="metric-subtext">Cloud services & repositories</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="app-card" style={{ padding: "1rem", marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>Filter:</span>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          style={{ maxWidth: "200px" }}
        >
          <option value="">All Asset Types</option>
          <option value="cloud_service">Cloud Service</option>
          <option value="software">Software</option>
          <option value="hardware">Hardware</option>
          <option value="data">Data Repository</option>
          <option value="physical">Physical Facility</option>
        </select>
        <select
          value={criticalityFilter}
          onChange={(e) => setCriticalityFilter(e.target.value)}
          style={{ maxWidth: "200px" }}
        >
          <option value="">All Criticalities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Assets Table */}
      <div className="app-card">
        {loading ? (
          <div className="loading-state">Loading Asset Register...</div>
        ) : assets.length === 0 ? (
          <div className="empty-state">No assets recorded in inventory. Register an asset to establish compliance scope.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Asset Name</th>
                <th>Identifier</th>
                <th>Type</th>
                <th>Criticality</th>
                <th>Classification</th>
                <th>Location / Scope</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{asset.name}</div>
                    {asset.description && (
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        {asset.description}
                      </div>
                    )}
                  </td>
                  <td>
                    {asset.identifier ? (
                      <span className="badge badge-purple" style={{ fontFamily: "monospace" }}>
                        {asset.identifier}
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-info" style={{ textTransform: "capitalize" }}>
                      {asset.asset_type.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td>{getCriticalityBadge(asset.criticality)}</td>
                  <td>{getClassificationBadge(asset.classification as DataClassification)}</td>
                  <td style={{ color: "var(--text-secondary)" }}>{asset.location || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Register New Asset Modal */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Register New Asset</h3>
              <button className="ghost" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateAsset}>
              <div className="form-group">
                <label>Asset Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Production PostgreSQL Cluster"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Asset Identifier / Tag</label>
                <input
                  type="text"
                  placeholder="e.g., DB-PROD-01"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Asset Type *</label>
                  <select value={assetType} onChange={(e) => setAssetType(e.target.value as AssetType)}>
                    <option value="cloud_service">Cloud Service</option>
                    <option value="software">Software / Application</option>
                    <option value="hardware">Hardware / Server</option>
                    <option value="data">Data Repository</option>
                    <option value="physical">Physical Facility</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Criticality *</label>
                  <select value={criticality} onChange={(e) => setCriticality(e.target.value as AssetCriticality)}>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Data Classification *</label>
                  <select value={classification} onChange={(e) => setClassification(e.target.value as DataClassification)}>
                    <option value="Restricted">Restricted</option>
                    <option value="Confidential">Confidential</option>
                    <option value="Internal">Internal</option>
                    <option value="Public">Public</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Location / Cloud Region</label>
                  <input
                    type="text"
                    placeholder="e.g., AWS eu-central-1"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea
                  rows={2}
                  placeholder="Primary role, purpose, and dependencies"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Register Asset
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
