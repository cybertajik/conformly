import type {
  RiskCategory,
  RiskItemSummary,
  RiskStatus,
  RiskTreatmentStrategy,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import { createRisk, listRisks, updateRisk } from "../api";
import { getAccessToken } from "../auth";
import { canManageRisks } from "../permissions";

interface RiskWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
}

export function RiskWorkspace({ tenantId, userRole }: RiskWorkspaceProps) {
  const [risks, setRisks] = useState<RiskItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  // Create Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCategory, setNewCategory] = useState<RiskCategory>("security");
  const [newLikelihood, setNewLikelihood] = useState<number>(3);
  const [newImpact, setNewImpact] = useState<number>(3);

  // Edit / Treatment Modal state
  const [editingRisk, setEditingRisk] = useState<RiskItemSummary | null>(null);
  const [editStatus, setEditStatus] = useState<RiskStatus>("identified");
  const [editStrategy, setEditStrategy] = useState<RiskTreatmentStrategy>("mitigate");
  const [editPlan, setEditPlan] = useState("");
  const [editResidualLikelihood, setEditResidualLikelihood] = useState<number>(2);
  const [editResidualImpact, setEditResidualImpact] = useState<number>(2);

  const canManage = canManageRisks(userRole);

  const loadRisks = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;

    try {
      setError(null);
      const data = await listRisks(token, tenantId, {
        category: (categoryFilter || undefined) as RiskCategory | undefined,
        status: (statusFilter || undefined) as RiskStatus | undefined,
      });
      setRisks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load risks");
    } finally {
      setLoading(false);
    }
  }, [tenantId, categoryFilter, statusFilter]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadRisks();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadRisks]);

  async function handleCreateRisk(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !newTitle.trim()) return;

    try {
      await createRisk(token, tenantId, {
        title: newTitle.trim(),
        category: newCategory,
        inherent_likelihood: Number(newLikelihood),
        inherent_impact: Number(newImpact),
        description: newDescription.trim() || null,
      });
      setShowCreateModal(false);
      setNewTitle("");
      setNewDescription("");
      setNewLikelihood(3);
      setNewImpact(3);
      setSuccessMessage("Risk registered successfully.");
      await loadRisks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register risk");
    }
  }

  async function handleUpdateTreatment(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !editingRisk) return;

    try {
      await updateRisk(token, tenantId, editingRisk.id, {
        status: editStatus,
        treatment_strategy: editStrategy,
        treatment_plan: editPlan.trim() || null,
        residual_likelihood: Number(editResidualLikelihood),
        residual_impact: Number(editResidualImpact),
      });
      setEditingRisk(null);
      setSuccessMessage("Risk treatment updated successfully.");
      await loadRisks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update risk");
    }
  }

  function openEditModal(risk: RiskItemSummary) {
    setEditingRisk(risk);
    setEditStatus(risk.status);
    setEditStrategy(risk.treatment_strategy ?? "mitigate");
    setEditPlan(risk.treatment_plan ?? "");
    setEditResidualLikelihood(risk.residual_likelihood ?? Math.max(1, risk.inherent_likelihood - 1));
    setEditResidualImpact(risk.residual_impact ?? Math.max(1, risk.inherent_impact - 1));
  }

  function getScoreBadge(score: number) {
    if (score >= 16) return <span className="badge badge-danger">Critical ({score})</span>;
    if (score >= 10) return <span className="badge badge-warning">High ({score})</span>;
    if (score >= 5) return <span className="badge badge-info">Medium ({score})</span>;
    return <span className="badge badge-success">Low ({score})</span>;
  }

  const criticalCount = risks.filter((r) => r.inherent_score >= 16).length;
  const highCount = risks.filter((r) => r.inherent_score >= 10 && r.inherent_score < 16).length;
  const treatingCount = risks.filter((r) => r.status === "treating" || r.status === "monitored").length;

  return (
    <div className="workspace-container">
      <div className="workspace-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="workspace-title">Risk Register</h1>
          <p className="workspace-subtitle">
            Catalog, evaluate, and treat organizational, security, and compliance risks with residual impact scoring.
          </p>
        </div>
        {canManage && (
          <button className="primary" onClick={() => setShowCreateModal(true)}>
            + Register New Risk
          </button>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {successMessage && <div className="success-banner">{successMessage}</div>}

      {/* Metrics Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <div className="metric-card">
          <span className="metric-label">Total Risks</span>
          <span className="metric-value">{risks.length}</span>
          <span className="metric-subtext">Active register items</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Critical Inherent</span>
          <span className="metric-value" style={{ color: "var(--color-danger)" }}>{criticalCount}</span>
          <span className="metric-subtext">Score ≥ 16</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">High Inherent</span>
          <span className="metric-value" style={{ color: "var(--color-warning)" }}>{highCount}</span>
          <span className="metric-subtext">Score 10–15</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Treating / Monitored</span>
          <span className="metric-value" style={{ color: "var(--accent)" }}>{treatingCount}</span>
          <span className="metric-subtext">Controls in progress</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="app-card" style={{ padding: "1rem", marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", fontWeight: 500 }}>Filter:</span>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={{ maxWidth: "200px" }}
        >
          <option value="">All Categories</option>
          <option value="security">Security</option>
          <option value="compliance">Compliance</option>
          <option value="operational">Operational</option>
          <option value="financial">Financial</option>
          <option value="strategic">Strategic</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ maxWidth: "200px" }}
        >
          <option value="">All Statuses</option>
          <option value="identified">Identified</option>
          <option value="assessed">Assessed</option>
          <option value="treating">Treating</option>
          <option value="monitored">Monitored</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* Risks Table */}
      <div className="app-card">
        {loading ? (
          <div className="loading-state">Loading Risk Register...</div>
        ) : risks.length === 0 ? (
          <div className="empty-state">No risks recorded matching your criteria. Register a risk to evaluate posture.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Risk Title</th>
                <th>Category</th>
                <th>Inherent (L×I)</th>
                <th>Residual (L×I)</th>
                <th>Treatment</th>
                <th>Status</th>
                {canManage && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {risks.map((risk) => (
                <tr key={risk.id}>
                  <td>
                    <div style={{ fontWeight: 600 }}>{risk.title}</div>
                    {risk.description && (
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                        {risk.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-purple" style={{ textTransform: "capitalize" }}>
                      {risk.category}
                    </span>
                  </td>
                  <td>
                    {getScoreBadge(risk.inherent_score)}
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "0.4rem" }}>
                      ({risk.inherent_likelihood}×{risk.inherent_impact})
                    </span>
                  </td>
                  <td>
                    {risk.residual_score ? (
                      <>
                        {getScoreBadge(risk.residual_score)}
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "0.4rem" }}>
                          ({risk.residual_likelihood}×{risk.residual_impact})
                        </span>
                      </>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Pending treatment</span>
                    )}
                  </td>
                  <td>
                    {risk.treatment_strategy ? (
                      <span className="badge badge-info" style={{ textTransform: "capitalize" }}>
                        {risk.treatment_strategy}
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td>
                    <span className={`badge ${risk.status === "closed" ? "badge-muted" : "badge-success"}`} style={{ textTransform: "capitalize" }}>
                      {risk.status}
                    </span>
                  </td>
                  {canManage && (
                    <td>
                      <button className="ghost" style={{ padding: "0.3rem 0.6rem", fontSize: "0.8rem" }} onClick={() => openEditModal(risk)}>
                        Update Treatment
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Register New Risk Modal */}
      {showCreateModal && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Register New Risk</h3>
              <button className="ghost" onClick={() => setShowCreateModal(false)}>✕</button>
            </div>
            <form onSubmit={handleCreateRisk}>
              <div className="form-group">
                <label>Risk Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g., Unauthorized Cloud Infrastructure Access"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Category *</label>
                <select value={newCategory} onChange={(e) => setNewCategory(e.target.value as RiskCategory)}>
                  <option value="security">Security</option>
                  <option value="compliance">Compliance</option>
                  <option value="operational">Operational</option>
                  <option value="financial">Financial</option>
                  <option value="strategic">Strategic</option>
                </select>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Inherent Likelihood (1–5) *</label>
                  <select value={newLikelihood} onChange={(e) => setNewLikelihood(Number(e.target.value))}>
                    <option value={1}>1 - Rare</option>
                    <option value={2}>2 - Unlikely</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Likely</option>
                    <option value={5}>5 - Almost Certain</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Inherent Impact (1–5) *</label>
                  <select value={newImpact} onChange={(e) => setNewImpact(Number(e.target.value))}>
                    <option value={1}>1 - Insignificant</option>
                    <option value={2}>2 - Minor</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Major</option>
                    <option value={5}>5 - Severe</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Description / Risk Context</label>
                <textarea
                  rows={3}
                  placeholder="Describe the threat scenario, vulnerabilities, and potential consequences."
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Risk
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Treatment Modal */}
      {editingRisk && (
        <div className="modal-backdrop">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Treat Risk: {editingRisk.title}</h3>
              <button className="ghost" onClick={() => setEditingRisk(null)}>✕</button>
            </div>
            <form onSubmit={handleUpdateTreatment}>
              <div className="form-group">
                <label>Status *</label>
                <select value={editStatus} onChange={(e) => setEditStatus(e.target.value as RiskStatus)}>
                  <option value="identified">Identified</option>
                  <option value="assessed">Assessed</option>
                  <option value="treating">Treating</option>
                  <option value="monitored">Monitored</option>
                  <option value="closed">Closed</option>
                </select>
              </div>
              <div className="form-group">
                <label>Treatment Strategy *</label>
                <select value={editStrategy} onChange={(e) => setEditStrategy(e.target.value as RiskTreatmentStrategy)}>
                  <option value="mitigate">Mitigate (Implement technical/organizational controls)</option>
                  <option value="accept">Accept (Risk within appetite)</option>
                  <option value="transfer">Transfer (Cyber insurance / Vendor agreement)</option>
                  <option value="avoid">Avoid (Eliminate activity)</option>
                </select>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div className="form-group">
                  <label>Residual Likelihood (1–5)</label>
                  <select value={editResidualLikelihood} onChange={(e) => setEditResidualLikelihood(Number(e.target.value))}>
                    <option value={1}>1 - Rare</option>
                    <option value={2}>2 - Unlikely</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Likely</option>
                    <option value={5}>5 - Almost Certain</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Residual Impact (1–5)</label>
                  <select value={editResidualImpact} onChange={(e) => setEditResidualImpact(Number(e.target.value))}>
                    <option value={1}>1 - Insignificant</option>
                    <option value={2}>2 - Minor</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Major</option>
                    <option value={5}>5 - Severe</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Treatment Plan / Action Items</label>
                <textarea
                  rows={3}
                  placeholder="Detail the controls, automated policies, or mitigations applied."
                  value={editPlan}
                  onChange={(e) => setEditPlan(e.target.value)}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="ghost" onClick={() => setEditingRisk(null)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Treatment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
