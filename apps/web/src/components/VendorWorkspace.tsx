import type {
  TenantRole,
  VendorItemSummary,
  VendorRiskTier,
  VendorStatus,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import { createVendor, listVendors, updateVendor } from "../api";
import { getAccessToken } from "../auth";
import { canManageVendors } from "../permissions";

interface VendorWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
}

export function VendorWorkspace({ tenantId, userRole }: VendorWorkspaceProps) {
  const [vendors, setVendors] = useState<VendorItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [tierFilter, setTierFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [riskTier, setRiskTier] = useState<VendorRiskTier>("tier_2_significant");
  const [serviceDescription, setServiceDescription] = useState("");
  const [dpaSigned, setDpaSigned] = useState(false);
  const [securityReviewDate, setSecurityReviewDate] = useState("");
  const [nextAssessmentDue, setNextAssessmentDue] = useState("");

  const canManage = canManageVendors(userRole);

  const loadVendors = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    try {
      setError(null);
      const data = await listVendors(token, tenantId, {
        risk_tier: (tierFilter || undefined) as VendorRiskTier | undefined,
        status: (statusFilter || undefined) as VendorStatus | undefined,
      });
      setVendors(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load vendors");
    } finally {
      setLoading(false);
    }
  }, [tenantId, tierFilter, statusFilter]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadVendors();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadVendors]);

  async function handleCreateVendor(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !name.trim()) return;

    try {
      await createVendor(token, tenantId, {
        name: name.trim(),
        risk_tier: riskTier,
        service_description: serviceDescription.trim() || null,
        dpa_signed: dpaSigned,
        security_review_date: securityReviewDate || null,
        next_assessment_due: nextAssessmentDue || null,
      });
      setShowCreateModal(false);
      setName("");
      setServiceDescription("");
      setDpaSigned(false);
      setSecurityReviewDate("");
      setNextAssessmentDue("");
      setSuccessMessage("Vendor registered successfully.");
      await loadVendors();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register vendor");
    }
  }

  async function handleToggleDpa(vendor: VendorItemSummary) {
    const token = getAccessToken();
    if (!token) return;

    try {
      await updateVendor(token, tenantId, vendor.id, {
        dpa_signed: !vendor.dpa_signed,
      });
      setSuccessMessage(`DPA status updated for ${vendor.name}.`);
      await loadVendors();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update vendor DPA");
    }
  }

  const tier1Count = vendors.filter((v) => v.risk_tier === "tier_1_critical").length;
  const dpaSignedCount = vendors.filter((v) => v.dpa_signed).length;
  const underReviewCount = vendors.filter((v) => v.status === "under_review").length;

  function getTierBadge(tier: VendorRiskTier) {
    switch (tier) {
      case "tier_1_critical":
        return <span className="badge badge-danger">Tier 1 Critical</span>;
      case "tier_2_significant":
        return <span className="badge badge-warning">Tier 2 Significant</span>;
      case "tier_3_low":
        return <span className="badge badge-info">Tier 3 Low</span>;
    }
  }

  return (
    <div className="workspace-container">
      <div className="workspace-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="workspace-title">Vendor & Third-Party Register</h1>
          <p className="workspace-subtitle">
            Supply chain risk management, Data Processing Agreements (DPA), and periodic third-party security assessments.
          </p>
        </div>
        {canManage && (
          <button className="primary" onClick={() => setShowCreateModal(true)}>
            + Register New Vendor
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {successMessage && <div className="success-banner">{successMessage}</div>}

      {/* Metrics Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="metric-card">
          <span className="metric-label">Total Vendors</span>
          <span className="metric-value">{vendors.length}</span>
          <span className="metric-subtext">Active third parties</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Tier 1 Critical</span>
          <span className="metric-value" style={{ color: "var(--color-danger)" }}>{tier1Count}</span>
          <span className="metric-subtext">Essential service providers</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">DPAs Executed</span>
          <span className="metric-value" style={{ color: "var(--accent)" }}>{dpaSignedCount}</span>
          <span className="metric-subtext">GDPR / DPA signed</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Under Review</span>
          <span className="metric-value" style={{ color: "var(--color-warning)" }}>{underReviewCount}</span>
          <span className="metric-subtext">Assessments pending</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="app-card" style={{ padding: "1rem", marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>Filter:</span>
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          style={{ maxWidth: "220px" }}
        >
          <option value="">All Risk Tiers</option>
          <option value="tier_1_critical">Tier 1 Critical</option>
          <option value="tier_2_significant">Tier 2 Significant</option>
          <option value="tier_3_low">Tier 3 Low</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ maxWidth: "200px" }}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="under_review">Under Review</option>
          <option value="suspended">Suspended</option>
          <option value="terminated">Terminated</option>
        </select>
      </div>

      {/* Vendors Table */}
      <div className="app-card">
        {loading ? (
          <div className="loading-state">Loading Vendor Register...</div>
        ) : vendors.length === 0 ? (
          <div className="empty-state">No vendors recorded. Register third-party processors and SaaS providers.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Vendor Name</th>
                <th>Risk Tier</th>
                <th>DPA Status</th>
                <th>Status</th>
                <th>Last Review</th>
                <th>Next Assessment</th>
                {canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {vendors.map((vendor) => (
                <tr key={vendor.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{vendor.name}</div>
                    {vendor.service_description && (
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        {vendor.service_description}
                      </div>
                    )}
                  </td>
                  <td>{getTierBadge(vendor.risk_tier)}</td>
                  <td>
                    {vendor.dpa_signed ? (
                      <span className="badge badge-success">✓ DPA Signed</span>
                    ) : (
                      <span className="badge badge-warning">⚠ DPA Pending</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${vendor.status === "active" ? "badge-success" : "badge-muted"}`} style={{ textTransform: "capitalize" }}>
                      {vendor.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-secondary)" }}>
                    {vendor.security_review_date ? new Date(vendor.security_review_date).toLocaleDateString() : "—"}
                  </td>
                  <td style={{ color: "var(--text-secondary)" }}>
                    {vendor.next_assessment_due ? new Date(vendor.next_assessment_due).toLocaleDateString() : "—"}
                  </td>
                  {canManage && (
                    <td>
                      <button
                        className="ghost"
                        style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }}
                        onClick={() => void handleToggleDpa(vendor)}
                      >
                        {vendor.dpa_signed ? "Mark DPA Pending" : "Mark DPA Signed"}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Register New Vendor Modal */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Register Third-Party Vendor</h3>
              <button className="ghost" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateVendor}>
              <div className="form-group">
                <label>Vendor Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Amazon Web Services EMEA SARL"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Risk Tier *</label>
                <select value={riskTier} onChange={(e) => setRiskTier(e.target.value as VendorRiskTier)}>
                  <option value="tier_1_critical">Tier 1 Critical (Processes customer/restricted data)</option>
                  <option value="tier_2_significant">Tier 2 Significant (Operational dependence)</option>
                  <option value="tier_3_low">Tier 3 Low (Commodity service / Public data)</option>
                </select>
              </div>
              <div className="form-group">
                <label>Service Description</label>
                <input
                  type="text"
                  placeholder="Cloud hosting and compute infrastructure"
                  value={serviceDescription}
                  onChange={(e) => setServiceDescription(e.target.value)}
                />
              </div>
              <div className="form-group" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  id="dpa_check"
                  checked={dpaSigned}
                  onChange={(e) => setDpaSigned(e.target.checked)}
                />
                <label htmlFor="dpa_check" style={{ marginBottom: 0 }}>Data Processing Agreement (DPA) Executed</label>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Security Review Date</label>
                  <input
                    type="date"
                    value={securityReviewDate}
                    onChange={(e) => setSecurityReviewDate(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label>Next Assessment Due</label>
                  <input
                    type="date"
                    value={nextAssessmentDue}
                    onChange={(e) => setNextAssessmentDue(e.target.value)}
                  />
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Vendor
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
