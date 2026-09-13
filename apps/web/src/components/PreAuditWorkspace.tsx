import type {
  FindingSeverity,
  PreAuditCheckResult,
  PreAuditFindingSummary,
  PreAuditStatus,
  PreAuditSummary,
  RemediationStatus,
  TenantFrameworkAdoptionSummary,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  addPreAuditFinding,
  cancelPreAudit,
  completePreAuditReview,
  createPreAudit,
  generatePreAuditManifest,
  generatePreAuditReport,
  getPreAudit,
  issuePreAuditCertificate,
  listPreAudits,
  listTenantAdoptions,
  revokePreAuditCertificate,
  runPreAuditChecks,
  submitPreAuditForReview,
  updatePreAuditFinding,
} from "../api";
import { getAccessToken } from "../auth";
import { canManagePreAudit } from "../permissions";

interface PreAuditWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
  currentUserId?: string;
}

type DetailTab = "posture" | "checks" | "findings" | "reports" | "credential";

export function PreAuditWorkspace({
  tenantId,
  userRole,
  currentUserId,
}: PreAuditWorkspaceProps) {
  const [preAudits, setPreAudits] = useState<PreAuditSummary[]>([]);
  const [adoptions, setAdoptions] = useState<TenantFrameworkAdoptionSummary[]>([]);
  const [selectedAuditId, setSelectedAuditId] = useState<string | null>(null);
  const [selectedAudit, setSelectedAudit] = useState<PreAuditSummary | null>(null);
  const [activeTab, setActiveTab] = useState<DetailTab>("posture");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modal / form states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAdoptionId, setNewAdoptionId] = useState("");

  const [showFindingModal, setShowFindingModal] = useState(false);
  const [findingTitle, setFindingTitle] = useState("");
  const [findingDesc, setFindingDesc] = useState("");
  const [findingSeverity, setFindingSeverity] = useState<FindingSeverity>("medium");
  const [findingRecommendation, setFindingRecommendation] = useState("");
  const [findingCheckId, setFindingCheckId] = useState<string>("");

  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewerUserId, setReviewerUserId] = useState("");

  const [showRevokeModal, setShowRevokeModal] = useState(false);
  const [revokeCertId, setRevokeCertId] = useState("");
  const [revokeReason, setRevokeReason] = useState("");

  const [snapshotModalCheck, setSnapshotModalCheck] = useState<string | null>(null);

  const canManage = canManagePreAudit(userRole);

  const loadData = useCallback(async () => {
    const token = getAccessToken();
    if (!token) return;
    try {
      setError(null);
      const [auditList, adoptionList] = await Promise.all([
        listPreAudits(token, tenantId),
        listTenantAdoptions(token, tenantId),
      ]);
      setPreAudits(auditList);
      setAdoptions(adoptionList.filter((a) => a.status === "active"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load pre-audits");
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  const loadSelectedAudit = useCallback(
    async (auditId: string) => {
      const token = getAccessToken();
      if (!token) return;
      try {
        setActionLoading(true);
        const detail = await getPreAudit(token, tenantId, auditId);
        setSelectedAudit(detail);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load pre-audit details");
      } finally {
        setActionLoading(false);
      }
    },
    [tenantId]
  );

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadData();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadData]);

  useEffect(() => {
    let active = true;
    async function fetchAudit() {
      if (!selectedAuditId) {
        setSelectedAudit(null);
        return;
      }
      const token = getAccessToken();
      if (!token) return;
      try {
        const detail = await getPreAudit(token, tenantId, selectedAuditId);
        if (active) setSelectedAudit(detail);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : "Failed to load pre-audit details");
      }
    }
    void fetchAudit();
    return () => {
      active = false;
    };
  }, [selectedAuditId, tenantId]);

  const handleCreatePreAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    const token = getAccessToken();
    if (!token || !newTitle || !newAdoptionId) return;
    try {
      setActionLoading(true);
      setError(null);
      const created = await createPreAudit(token, tenantId, {
        title: newTitle,
        description: newDescription,
        framework_adoption_id: newAdoptionId,
        lead_user_id: currentUserId || "default-lead",
      });
      setShowCreateModal(false);
      setNewTitle("");
      setNewDescription("");
      setNewAdoptionId("");
      setSuccessMessage("Pre-audit readiness assessment created successfully.");
      await loadData();
      setSelectedAuditId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create pre-audit");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunChecks = async () => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await runPreAuditChecks(token, tenantId, selectedAudit.id);
      setSelectedAudit(updated);
      setSuccessMessage("Deterministic readiness checks evaluated successfully.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run checks");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAudit || !reviewerUserId) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await submitPreAuditForReview(token, tenantId, selectedAudit.id, {
        reviewer_user_id: reviewerUserId,
        expected_version: selectedAudit.version,
      });
      setShowReviewModal(false);
      setReviewerUserId("");
      setSelectedAudit(updated);
      setSuccessMessage("Assessment submitted for review.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit review");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCompleteReview = async () => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await completePreAuditReview(token, tenantId, selectedAudit.id, {
        expected_version: selectedAudit.version,
      });
      setSelectedAudit(updated);
      setSuccessMessage("Review completed. Assessment is finalized.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete review");
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancelAssessment = async () => {
    if (!selectedAudit) return;
    if (!window.confirm("Are you sure you want to cancel this pre-audit assessment?")) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const updated = await cancelPreAudit(token, tenantId, selectedAudit.id, {
        expected_version: selectedAudit.version,
      });
      setSelectedAudit(updated);
      setSuccessMessage("Pre-audit assessment cancelled.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to cancel assessment");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddFinding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAudit || !findingTitle || !findingDesc) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      await addPreAuditFinding(token, tenantId, selectedAudit.id, {
        title: findingTitle,
        description: findingDesc,
        severity: findingSeverity,
        recommendation: findingRecommendation || null,
        check_id: findingCheckId || null,
      });
      setShowFindingModal(false);
      setFindingTitle("");
      setFindingDesc("");
      setFindingRecommendation("");
      setFindingCheckId("");
      setSuccessMessage("Readiness finding recorded.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add finding");
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateFindingStatus = async (
    finding: PreAuditFindingSummary,
    newStatus: RemediationStatus
  ) => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      await updatePreAuditFinding(token, tenantId, selectedAudit.id, finding.id, {
        expected_version: finding.version,
        remediation_status: newStatus,
      });
      setSuccessMessage("Finding remediation status updated.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update finding status");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const placeholderFileId = "00000000-0000-0000-0000-000000000001";
      await generatePreAuditReport(token, tenantId, selectedAudit.id, {
        file_id: placeholderFileId,
        report_type: "readiness_summary",
      });
      setSuccessMessage("Report artifact generated successfully.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate report");
    } finally {
      setActionLoading(false);
    }
  };

  const handleGenerateManifest = async () => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      const placeholderFileId = "00000000-0000-0000-0000-000000000002";
      const manifestPayload = JSON.stringify({
        pre_audit_id: selectedAudit.id,
        rule_version: selectedAudit.rule_version,
        generated_at: new Date().toISOString(),
        checks_count: selectedAudit.checks?.length ?? 0,
      });
      await generatePreAuditManifest(token, tenantId, selectedAudit.id, {
        file_id: placeholderFileId,
        manifest_content: manifestPayload,
      });
      setSuccessMessage("Audit manifest generated with cryptographic SHA-256 seal.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate manifest");
    } finally {
      setActionLoading(false);
    }
  };

  const handleIssueCertificate = async () => {
    if (!selectedAudit) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      await issuePreAuditCertificate(token, tenantId, selectedAudit.id, {
        validity_days: 365,
      });
      setSuccessMessage("Pre-Audit Readiness Credential issued successfully.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue certificate");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevokeCertificate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAudit || !revokeCertId || !revokeReason) return;
    const token = getAccessToken();
    if (!token) return;
    try {
      setActionLoading(true);
      setError(null);
      await revokePreAuditCertificate(token, tenantId, selectedAudit.id, revokeCertId, {
        reason: revokeReason,
      });
      setShowRevokeModal(false);
      setRevokeCertId("");
      setRevokeReason("");
      setSuccessMessage("Readiness credential revoked.");
      await loadSelectedAudit(selectedAudit.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke certificate");
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: PreAuditStatus) => {
    switch (status) {
      case "planning":
        return <span className="badge badge-neutral">Planning</span>;
      case "in_progress":
        return <span className="badge badge-info">In Progress</span>;
      case "in_review":
        return <span className="badge badge-warning">In Review</span>;
      case "completed":
        return <span className="badge badge-success">Completed</span>;
      case "cancelled":
        return <span className="badge badge-danger">Cancelled</span>;
      default:
        return <span className="badge badge-neutral">{status}</span>;
    }
  };

  const getCheckBadge = (result: PreAuditCheckResult) => {
    switch (result) {
      case "pass":
        return <span className="badge badge-success">Pass</span>;
      case "fail":
        return <span className="badge badge-danger">Fail</span>;
      case "not_applicable":
        return <span className="badge badge-neutral">N/A</span>;
      case "pending":
        return <span className="badge badge-warning">Pending</span>;
      default:
        return <span className="badge badge-neutral">{result}</span>;
    }
  };

  const getSeverityBadge = (severity: FindingSeverity) => {
    switch (severity) {
      case "critical":
        return <span className="badge badge-danger">Critical</span>;
      case "high":
        return <span className="badge badge-danger">High</span>;
      case "medium":
        return <span className="badge badge-warning">Medium</span>;
      case "low":
        return <span className="badge badge-info">Low</span>;
      default:
        return <span className="badge badge-neutral">{severity}</span>;
    }
  };

  return (
    <div className="preaudit-workspace" data-testid="preaudit-workspace">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div>
          <h2 style={{ margin: 0 }}>Pre-Audit Readiness Workspace</h2>
          <p style={{ margin: "0.25rem 0 0", color: "#4a5d55", fontSize: "0.875rem" }}>
            Deterministic readiness evaluations and evidence verification prior to independent audit.
          </p>
        </div>
        {canManage && (
          <button
            onClick={() => setShowCreateModal(true)}
            data-testid="create-preaudit-btn"
          >
            + New Readiness Assessment
          </button>
        )}
      </div>

      <div
        className="card"
        style={{
          background: "#f0fdf4",
          borderLeft: "4px solid #16a34a",
          padding: "0.75rem 1rem",
          marginBottom: "1.5rem",
          fontSize: "0.8125rem",
          color: "#166534",
        }}
      >
        <strong>Compliance Notice:</strong> Conformly provides pre-audit readiness assessments and
        operational tools to evaluate adherence to compliance criteria. Conformly is not an
        accredited certification body. Issued credentials demonstrate readiness assessment completion,
        not external certification.
      </div>

      {error && (
        <div
          className="card"
          style={{ background: "#fef2f2", color: "#991b1b", borderLeft: "4px solid #dc2626", marginBottom: "1rem" }}
          data-testid="error-alert"
        >
          {error}
        </div>
      )}

      {successMessage && (
        <div
          className="card"
          style={{ background: "#f0fdf4", color: "#166534", borderLeft: "4px solid #16a34a", marginBottom: "1rem" }}
          data-testid="success-alert"
        >
          {successMessage}
        </div>
      )}

      {loading ? (
        <p>Loading readiness assessments...</p>
      ) : selectedAudit ? (
        /* Detail View */
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem" }}>
            <button
              className="secondary"
              onClick={() => setSelectedAuditId(null)}
              data-testid="back-to-list-btn"
            >
              ← Back to Assessments
            </button>
            <h3 style={{ margin: 0 }}>{selectedAudit.title}</h3>
            {getStatusBadge(selectedAudit.status)}
            <span style={{ fontSize: "0.8125rem", color: "#64748b" }}>
              Rule Engine: <code>{selectedAudit.rule_version}</code>
            </span>
          </div>

          {/* Sub Navigation */}
          <div className="subnav" role="tablist">
            <button
              className={`subnav-tab ${activeTab === "posture" ? "active" : ""}`}
              onClick={() => setActiveTab("posture")}
              role="tab"
              aria-selected={activeTab === "posture"}
            >
              Readiness Dashboard
            </button>
            <button
              className={`subnav-tab ${activeTab === "checks" ? "active" : ""}`}
              onClick={() => setActiveTab("checks")}
              role="tab"
              aria-selected={activeTab === "checks"}
            >
              Control Checks ({selectedAudit.checks?.length ?? 0})
            </button>
            <button
              className={`subnav-tab ${activeTab === "findings" ? "active" : ""}`}
              onClick={() => setActiveTab("findings")}
              role="tab"
              aria-selected={activeTab === "findings"}
            >
              Gaps & Findings ({selectedAudit.findings?.length ?? 0})
            </button>
            <button
              className={`subnav-tab ${activeTab === "reports" ? "active" : ""}`}
              onClick={() => setActiveTab("reports")}
              role="tab"
              aria-selected={activeTab === "reports"}
            >
              Artifacts & Manifests ({((selectedAudit.reports?.length ?? 0) + (selectedAudit.manifests?.length ?? 0))})
            </button>
            <button
              className={`subnav-tab ${activeTab === "credential" ? "active" : ""}`}
              onClick={() => setActiveTab("credential")}
              role="tab"
              aria-selected={activeTab === "credential"}
            >
              Readiness Credential ({selectedAudit.certificates?.length ?? 0})
            </button>
          </div>

          {/* Tab 1: Posture & Actions */}
          {activeTab === "posture" && (
            <div>
              {/* Truthful Scope & Delimitation Banner */}
              <div
                className="card"
                style={{
                  marginBottom: "1.5rem",
                  borderLeft: selectedAudit.score_summary?.scope_type === "profile_scoped" ? "4px solid #f59e0b" : "4px solid #2563eb",
                  backgroundColor: selectedAudit.score_summary?.scope_type === "profile_scoped" ? "#fffbeb" : "#eff6ff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div>
                    <span
                      style={{
                        display: "inline-block",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        padding: "0.2rem 0.5rem",
                        borderRadius: "4px",
                        backgroundColor: selectedAudit.score_summary?.scope_type === "profile_scoped" ? "#fef3c7" : "#dbeafe",
                        color: selectedAudit.score_summary?.scope_type === "profile_scoped" ? "#b45309" : "#1e40af",
                        marginBottom: "0.5rem",
                      }}
                    >
                      {selectedAudit.score_summary?.scope_type === "profile_scoped"
                        ? "Profile-Scoped Readiness"
                        : "Full Standard Readiness"}
                    </span>
                    <h4 style={{ margin: "0 0 0.25rem", color: "#1e293b" }}>
                      Declared Scope: {selectedAudit.score_summary?.declared_scope || "Framework Scope"}
                    </h4>
                    {selectedAudit.score_summary?.scope_limitations && selectedAudit.score_summary.scope_limitations.length > 0 && (
                      <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.25rem", fontSize: "0.8125rem", color: "#64748b" }}>
                        {selectedAudit.score_summary.scope_limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
                <div
                  style={{
                    marginTop: "0.75rem",
                    paddingTop: "0.75rem",
                    borderTop: "1px solid rgba(0,0,0,0.06)",
                    fontSize: "0.75rem",
                    color: "#64748b",
                    fontStyle: "italic",
                  }}
                >
                  ℹ️ {selectedAudit.score_summary?.disclaimer || "Conformly is an audit-readiness and compliance operations platform, not an accredited certification body."}
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
                <div className="card" style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Overall Score</div>
                  <div style={{ fontSize: "2.25rem", fontWeight: 700, color: "var(--accent)", margin: "0.5rem 0" }}>
                    {selectedAudit.overall_score !== null ? `${Math.round(selectedAudit.overall_score * 100)}%` : "N/A"}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Deterministic weighted score</div>
                </div>

                <div className="card" style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "0.8125rem", color: "#64748b", textTransform: "uppercase" }}>Passed Checks</div>
                  <div style={{ fontSize: "2.25rem", fontWeight: 700, color: "#16a34a", margin: "0.5rem 0" }}>
                    {selectedAudit.score_summary?.passed_checks ?? 0} / {selectedAudit.score_summary?.total_checks ?? 0}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                    {selectedAudit.score_summary?.failed_checks ?? 0} failed, {selectedAudit.score_summary?.not_applicable_checks ?? 0} n/a
                  </div>
                </div>

                <div className="card" style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "0.8125rem", color: "#64748b", textTransform: "uppercase" }}>Open Gaps / Findings</div>
                  <div style={{ fontSize: "2.25rem", fontWeight: 700, color: (selectedAudit.score_summary?.open_findings ?? 0) > 0 ? "#dc2626" : "#16a34a", margin: "0.5rem 0" }}>
                    {selectedAudit.score_summary?.open_findings ?? 0}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Action items requiring resolution</div>
                </div>

                <div className="card" style={{ textAlign: "center" }}>
                  <div style={{ fontSize: "0.8125rem", color: "#64748b", textTransform: "uppercase" }}>Reviewer Status</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: 600, color: "#334155", margin: "1rem 0" }}>
                    {selectedAudit.reviewed_at ? "Approved & Reviewed" : selectedAudit.reviewer_user_id ? "In Review" : "Unassigned"}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#64748b" }}>Independent verification</div>
                </div>
              </div>

              {/* Assessment Actions */}
              {canManage && (
                <div className="card">
                  <h4 style={{ margin: "0 0 1rem" }}>Readiness Lifecycle Actions</h4>
                  <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                    {(selectedAudit.status === "planning" ||
                      selectedAudit.status === "in_progress" ||
                      selectedAudit.status === "in_review") && (
                      <button
                        onClick={() => void handleRunChecks()}
                        disabled={actionLoading}
                        data-testid="run-checks-btn"
                      >
                        {actionLoading ? "Evaluating..." : "Run Deterministic Checks"}
                      </button>
                    )}

                    {selectedAudit.status === "in_progress" && (
                      <button
                        className="secondary"
                        onClick={() => setShowReviewModal(true)}
                        disabled={actionLoading}
                        data-testid="submit-review-btn"
                      >
                        Submit for Review
                      </button>
                    )}

                    {selectedAudit.status === "in_review" && (
                      <button
                        onClick={() => void handleCompleteReview()}
                        disabled={actionLoading}
                        data-testid="complete-review-btn"
                      >
                        Complete Review
                      </button>
                    )}

                    {selectedAudit.status !== "completed" && selectedAudit.status !== "cancelled" && (
                      <button
                        className="secondary"
                        style={{ color: "#dc2626", borderColor: "#fca5a5" }}
                        onClick={() => void handleCancelAssessment()}
                        disabled={actionLoading}
                        data-testid="cancel-assessment-btn"
                      >
                        Cancel Assessment
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Control Checks */}
          {activeTab === "checks" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ margin: 0 }}>Evaluated Control Checks</h4>
                {canManage && (
                  <button
                    className="secondary"
                    onClick={() => void handleRunChecks()}
                    disabled={actionLoading}
                  >
                    Re-evaluate Checks
                  </button>
                )}
              </div>

              {(!selectedAudit.checks || selectedAudit.checks.length === 0) ? (
                <div className="card">
                  <p>No checks evaluated yet. Click "Run Deterministic Checks" to assess controls.</p>
                </div>
              ) : (
                <div className="table-wrapper">
                  <table className="data-table" data-testid="checks-table">
                    <thead>
                      <tr>
                        <th>Control</th>
                        <th>Result</th>
                        <th>Evidence Count</th>
                        <th>Policy</th>
                        <th>Open Gaps</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>Snapshot</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedAudit.checks.map((c) => (
                        <tr key={c.id}>
                          <td>
                            <strong>{c.control_id.slice(0, 8)}...</strong>
                            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{c.control_type}</div>
                          </td>
                          <td>{getCheckBadge(c.result)}</td>
                          <td>{c.evidence_count}</td>
                          <td>{c.policy_count > 0 ? "Linked" : "Missing"}</td>
                          <td>{c.open_findings_count}</td>
                          <td>{c.implementation_status || "not_started"}</td>
                          <td>{Math.round(c.score * 100)}%</td>
                          <td>
                            <button
                              className="secondary"
                              style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                              onClick={() => setSnapshotModalCheck(c.id)}
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 3: Findings */}
          {activeTab === "findings" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ margin: 0 }}>Identified Readiness Gaps</h4>
                {canManage && (
                  <button
                    onClick={() => setShowFindingModal(true)}
                    data-testid="add-finding-btn"
                  >
                    + Record Gap / Finding
                  </button>
                )}
              </div>

              {(!selectedAudit.findings || selectedAudit.findings.length === 0) ? (
                <div className="card">
                  <p>No readiness gaps identified for this assessment.</p>
                </div>
              ) : (
                <div className="table-wrapper">
                  <table className="data-table" data-testid="findings-table">
                    <thead>
                      <tr>
                        <th>Title</th>
                        <th>Severity</th>
                        <th>Remediation Status</th>
                        <th>Recommendation</th>
                        {canManage && <th>Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {selectedAudit.findings.map((f) => (
                        <tr key={f.id}>
                          <td>
                            <strong>{f.title}</strong>
                            <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{f.description}</div>
                          </td>
                          <td>{getSeverityBadge(f.severity)}</td>
                          <td>
                            <span className={`badge ${f.remediation_status === "resolved" ? "badge-success" : "badge-warning"}`}>
                              {f.remediation_status.replace("_", " ")}
                            </span>
                          </td>
                          <td style={{ fontSize: "0.8125rem" }}>{f.recommendation || "—"}</td>
                          {canManage && (
                            <td>
                              {f.remediation_status !== "resolved" && (
                                <button
                                  className="secondary"
                                  style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                                  onClick={() => void handleUpdateFindingStatus(f, "resolved")}
                                >
                                  Mark Resolved
                                </button>
                              )}
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Tab 4: Artifacts & Manifests */}
          {activeTab === "reports" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ margin: 0 }}>Cryptographic Artifacts & Manifests</h4>
                {canManage && (
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      className="secondary"
                      onClick={() => void handleGenerateReport()}
                      disabled={actionLoading}
                    >
                      Generate Report
                    </button>
                    <button
                      onClick={() => void handleGenerateManifest()}
                      disabled={actionLoading}
                    >
                      Generate SHA-256 Manifest
                    </button>
                  </div>
                )}
              </div>

              <div className="card">
                <h5>Machine-Readable Manifests</h5>
                {(!selectedAudit.manifests || selectedAudit.manifests.length === 0) ? (
                  <p style={{ fontSize: "0.875rem", color: "#64748b" }}>No cryptographic manifests generated yet.</p>
                ) : (
                  <ul>
                    {selectedAudit.manifests.map((m) => (
                      <li key={m.id} style={{ marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                        <strong>SHA-256:</strong> <code>{m.manifest_hash_sha256}</code> — {m.record_count} items (Engine: {m.rule_version})
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="card">
                <h5>Readiness Summary Reports</h5>
                {(!selectedAudit.reports || selectedAudit.reports.length === 0) ? (
                  <p style={{ fontSize: "0.875rem", color: "#64748b" }}>No reports generated yet.</p>
                ) : (
                  <ul>
                    {selectedAudit.reports.map((r) => (
                      <li key={r.id} style={{ marginBottom: "0.5rem", fontSize: "0.875rem" }}>
                        <strong>Type:</strong> {r.report_type} — Generated: {new Date(r.generated_at).toLocaleString()}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          )}

          {/* Tab 5: Credential */}
          {activeTab === "credential" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ margin: 0 }}>Conformly Pre-Audit Readiness Credential</h4>
                {canManage && selectedAudit.status === "completed" && (
                  <button
                    onClick={() => void handleIssueCertificate()}
                    disabled={actionLoading}
                    data-testid="issue-credential-btn"
                  >
                    Issue Readiness Credential
                  </button>
                )}
              </div>

              {(!selectedAudit.certificates || selectedAudit.certificates.length === 0) ? (
                <div className="card">
                  <p>
                    No readiness credential issued for this assessment.
                    {selectedAudit.status !== "completed" && " (The assessment must be completed before issuing a credential)."}
                  </p>
                </div>
              ) : (
                <div>
                  {selectedAudit.certificates.map((cert) => (
                    <div key={cert.id} className="card" style={{ border: "2px solid var(--border-accent-strong)", padding: "1.5rem" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <div style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--accent)", fontWeight: 700 }}>
                            Conformly Pre-Audit Readiness Badge
                          </div>
                          <h3 style={{ margin: "0.5rem 0", color: "var(--text-primary)" }}>
                            Credential #{cert.certificate_number}
                          </h3>
                        </div>
                        <div>
                          <span className={`badge ${cert.status === "active" ? "badge-success" : "badge-danger"}`}>
                            {cert.status}
                          </span>
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", margin: "1rem 0", fontSize: "0.875rem" }}>
                        <div><strong>Issued:</strong> {new Date(cert.issued_at).toLocaleDateString()}</div>
                        <div><strong>Expires:</strong> {new Date(cert.expires_at).toLocaleDateString()}</div>
                        {cert.revoked_at && (
                          <div style={{ color: "#dc2626" }}>
                            <strong>Revoked:</strong> {new Date(cert.revoked_at).toLocaleDateString()} ({cert.revoked_reason})
                          </div>
                        )}
                      </div>

                      <div style={{ padding: "0.6rem 0.8rem", background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "4px", fontSize: "0.75rem", color: "#64748b", fontStyle: "italic", marginBottom: "0.5rem" }}>
                        ℹ️ Conformly Pre-Audit Readiness Badges represent automated internal evaluations of declared scope, not accredited third-party certifications.
                      </div>

                      {canManage && cert.status === "active" && (
                        <div style={{ marginTop: "1rem", borderTop: "1px solid var(--border-default)", paddingTop: "0.75rem" }}>
                          <button
                            className="secondary"
                            style={{ color: "#dc2626", borderColor: "#fca5a5", fontSize: "0.75rem", minHeight: "auto", padding: "0.3rem 0.6rem" }}
                            onClick={() => {
                              setRevokeCertId(cert.id);
                              setShowRevokeModal(true);
                            }}
                          >
                            Revoke Credential
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Pre-Audit List View */
        <div>
          {preAudits.length === 0 ? (
            <div className="card">
              <p>No pre-audit readiness assessments found. Create one to begin evaluation.</p>
            </div>
          ) : (
            <div className="table-wrapper">
              <table className="data-table" data-testid="preaudits-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Readiness Score</th>
                    <th>Rule Version</th>
                    <th>Created</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {preAudits.map((pa) => (
                    <tr key={pa.id}>
                      <td>
                        <strong>{pa.title}</strong>
                        {pa.description && (
                          <div style={{ fontSize: "0.75rem", color: "#64748b" }}>{pa.description}</div>
                        )}
                      </td>
                      <td>{getStatusBadge(pa.status)}</td>
                      <td>
                        <strong>{pa.overall_score !== null ? `${Math.round(pa.overall_score * 100)}%` : "Pending"}</strong>
                      </td>
                      <td><code>{pa.rule_version}</code></td>
                      <td>{new Date(pa.created_at).toLocaleDateString()}</td>
                      <td>
                        <button
                          className="secondary"
                          style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem", minHeight: "auto" }}
                          onClick={() => setSelectedAuditId(pa.id)}
                          data-testid={`view-preaudit-${pa.id}`}
                        >
                          View Assessment
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal: Create Pre-Audit */}
      {showCreateModal && (
        <div className="modal-backdrop" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", placeItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "min(90vw, 32rem)", background: "var(--bg-surface)", padding: "1.5rem" }}>
            <h3 style={{ marginTop: 0 }}>New Readiness Assessment</h3>
            <form onSubmit={(e) => void handleCreatePreAudit(e)}>
              <label htmlFor="pa-title">Assessment Title</label>
              <input
                id="pa-title"
                type="text"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. SOC 2 Type II Readiness"
              />

              <label htmlFor="pa-desc">Description</label>
              <textarea
                id="pa-desc"
                rows={3}
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Scope, objectives, and audit window..."
              />

              <label htmlFor="pa-adoption">Framework Adoption</label>
              <select
                id="pa-adoption"
                required
                value={newAdoptionId}
                onChange={(e) => setNewAdoptionId(e.target.value)}
              >
                <option value="">Select adopted framework...</option>
                {adoptions.map((adp) => (
                  <option key={adp.id} value={adp.id}>
                    Framework Version {adp.framework_version_id.slice(0, 8)} ({adp.status})
                  </option>
                ))}
              </select>

              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" disabled={actionLoading}>
                  Create Assessment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Add Finding */}
      {showFindingModal && (
        <div className="modal-backdrop" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", placeItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "min(90vw, 32rem)", background: "var(--bg-surface)", padding: "1.5rem" }}>
            <h3 style={{ marginTop: 0 }}>Record Readiness Gap</h3>
            <form onSubmit={(e) => void handleAddFinding(e)}>
              <label htmlFor="f-title">Gap Summary</label>
              <input
                id="f-title"
                type="text"
                required
                value={findingTitle}
                onChange={(e) => setFindingTitle(e.target.value)}
                placeholder="e.g. Missing MFA evidence for administrative accounts"
              />

              <label htmlFor="f-desc">Detailed Description</label>
              <textarea
                id="f-desc"
                rows={3}
                required
                value={findingDesc}
                onChange={(e) => setFindingDesc(e.target.value)}
              />

              <label htmlFor="f-sev">Severity</label>
              <select
                id="f-sev"
                value={findingSeverity}
                onChange={(e) => setFindingSeverity(e.target.value as FindingSeverity)}
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              <label htmlFor="f-rec">Remediation Recommendation</label>
              <textarea
                id="f-rec"
                rows={2}
                value={findingRecommendation}
                onChange={(e) => setFindingRecommendation(e.target.value)}
                placeholder="Steps required to resolve this gap..."
              />

              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowFindingModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" disabled={actionLoading}>
                  Record Gap
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Submit for Review */}
      {showReviewModal && (
        <div className="modal-backdrop" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", placeItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "min(90vw, 28rem)", background: "var(--bg-surface)", padding: "1.5rem" }}>
            <h3 style={{ marginTop: 0 }}>Submit Assessment for Review</h3>
            <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
              To ensure independence, the reviewer must be a different tenant member than the assessment lead.
            </p>
            <form onSubmit={(e) => void handleSubmitReview(e)}>
              <label htmlFor="rev-user">Reviewer User ID</label>
              <input
                id="rev-user"
                type="text"
                required
                value={reviewerUserId}
                onChange={(e) => setReviewerUserId(e.target.value)}
                placeholder="UUID of reviewer..."
              />

              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowReviewModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" disabled={actionLoading}>
                  Submit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Revoke Certificate */}
      {showRevokeModal && (
        <div className="modal-backdrop" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", placeItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "min(90vw, 28rem)", background: "var(--bg-surface)", padding: "1.5rem" }}>
            <h3 style={{ marginTop: 0, color: "#dc2626" }}>Revoke Credential</h3>
            <p style={{ fontSize: "0.875rem", color: "#64748b" }}>
              Revocation is irreversible. Please specify the compliance justification.
            </p>
            <form onSubmit={(e) => void handleRevokeCertificate(e)}>
              <label htmlFor="rev-reason">Revocation Reason</label>
              <textarea
                id="rev-reason"
                rows={3}
                required
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                placeholder="e.g. Invalidation of evidence, control regression..."
              />

              <div style={{ display: "flex", gap: "0.75rem", justifyContent: "flex-end", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowRevokeModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  style={{ background: "#dc2626", borderColor: "#dc2626" }}
                  disabled={actionLoading}
                >
                  Confirm Revocation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Snapshot Inspector */}
      {snapshotModalCheck && (
        <div className="modal-backdrop" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", placeItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "min(90vw, 36rem)", background: "var(--bg-surface)", padding: "1.5rem" }}>
            <h3 style={{ marginTop: 0 }}>Deterministic Evaluation Snapshot</h3>
            <pre style={{ background: "#f8fafc", padding: "1rem", borderRadius: "0.5rem", overflowX: "auto", fontSize: "0.75rem" }}>
              {JSON.stringify(
                selectedAudit?.checks?.find((c) => c.id === snapshotModalCheck),
                null,
                2
              )}
            </pre>
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "1rem" }}>
              <button
                className="secondary"
                onClick={() => setSnapshotModalCheck(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
