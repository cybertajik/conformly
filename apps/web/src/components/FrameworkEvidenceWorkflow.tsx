import { useCallback, useEffect, useState } from "react";

import {
  acceptFrameworkEvidence,
  generateFrameworkEvidenceRequests,
  getFrameworkReadinessEvaluation,
  listEvidence,
  listFrameworkEvidenceRequests,
  listTenantMembers,
  type EvidenceItemSummary,
  type FrameworkEvidenceRequestSummary,
  type FrameworkReadinessSummary,
  type TenantMemberItem,
} from "../api";

interface FrameworkEvidenceWorkflowProps {
  token: string;
  tenantId: string;
  adoptionId: string;
  frameworkName: string;
  versionString: string;
  canManage: boolean;
}

export function FrameworkEvidenceWorkflow({
  token,
  tenantId,
  adoptionId,
  frameworkName,
  versionString,
  canManage,
}: FrameworkEvidenceWorkflowProps) {
  const [requests, setRequests] = useState<FrameworkEvidenceRequestSummary[]>([]);
  const [readiness, setReadiness] = useState<FrameworkReadinessSummary | null>(null);
  const [members, setMembers] = useState<TenantMemberItem[]>([]);
  const [evidenceList, setEvidenceList] = useState<EvidenceItemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Generate modal
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 30);
    return d.toISOString().split("T")[0];
  });
  const [selectedOwnerId, setSelectedOwnerId] = useState<string>("");
  const [submittingGenerate, setSubmittingGenerate] = useState(false);

  // Accept modal
  const [acceptingRequest, setAcceptingRequest] = useState<FrameworkEvidenceRequestSummary | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string>("");
  const [obsStart, setObsStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split("T")[0];
  });
  const [obsEnd, setObsEnd] = useState(() => new Date().toISOString().split("T")[0]);
  const [submittingAccept, setSubmittingAccept] = useState(false);

  const loadWorkflowData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [reqs, ready, mems, evs] = await Promise.all([
        listFrameworkEvidenceRequests(token, tenantId, adoptionId),
        getFrameworkReadinessEvaluation(token, tenantId, adoptionId).catch(() => null),
        listTenantMembers(token, tenantId).catch(() => []),
        listEvidence(token, tenantId).catch(() => []),
      ]);
      setRequests(reqs);
      setReadiness(ready);
      setMembers(mems);
      setEvidenceList(evs);
      if (mems.length > 0 && !selectedOwnerId) {
        setSelectedOwnerId(mems[0].user_id);
      }
      if (evs.length > 0 && !selectedEvidenceId) {
        setSelectedEvidenceId(evs[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load evidence requests workflow.");
    } finally {
      setLoading(false);
    }
  }, [token, tenantId, adoptionId, selectedOwnerId, selectedEvidenceId]);

  useEffect(() => {
    void loadWorkflowData();
  }, [loadWorkflowData]);

  async function handleGenerateRequests(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedOwnerId || !dueDate) return;

    try {
      setSubmittingGenerate(true);
      setError(null);
      setSuccess(null);
      const generated = await generateFrameworkEvidenceRequests(token, tenantId, adoptionId, {
        due_date: new Date(dueDate).toISOString(),
        owner_user_id: selectedOwnerId,
      });
      setSuccess(`Successfully generated ${generated.length} evidence request task(s).`);
      setShowGenerateModal(false);
      await loadWorkflowData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate evidence requests.");
    } finally {
      setSubmittingGenerate(false);
    }
  }

  async function handleAcceptEvidenceSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!acceptingRequest || !selectedEvidenceId || !obsStart || !obsEnd) return;

    try {
      setSubmittingAccept(true);
      setError(null);
      setSuccess(null);
      await acceptFrameworkEvidence(token, tenantId, adoptionId, acceptingRequest.id, {
        evidence_id: selectedEvidenceId,
        observation_start: new Date(obsStart).toISOString(),
        observation_end: new Date(obsEnd).toISOString(),
      });
      setSuccess("Evidence item accepted successfully against framework specification.");
      setAcceptingRequest(null);
      await loadWorkflowData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to accept evidence.");
    } finally {
      setSubmittingAccept(false);
    }
  }

  const satisfiedCount = readiness?.specifications?.filter((s) => !s.problem).length ?? 0;
  const totalSpecs = readiness?.specifications?.length ?? requests.length;
  const blockers = readiness?.blockers ?? [];

  return (
    <div className="card" style={{ padding: "1.25rem", borderRadius: "10px", marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
        <div>
          <h4 style={{ margin: 0, fontSize: "1.15rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span>📋</span>
            <span>Structured Evidence Workflow ({frameworkName} v{versionString})</span>
          </h4>
          <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Deterministic evidence request generation, collection tracking, and audit readiness evaluation.
          </p>
        </div>

        {canManage && (
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              className="button primary"
              onClick={() => setShowGenerateModal(true)}
              style={{ fontSize: "0.85rem", padding: "0.4rem 0.8rem" }}
            >
              {requests.length > 0 ? "↻ Re-generate Requests" : "⚡ Generate Evidence Requests"}
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="alert error" style={{ padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem", background: "rgba(239, 68, 68, 0.1)", border: "1px solid var(--accent-danger)", color: "var(--accent-danger)" }}>
          {error}
        </div>
      )}

      {success && (
        <div className="alert success" style={{ padding: "0.75rem 1rem", borderRadius: "6px", marginBottom: "1rem", background: "rgba(34, 197, 94, 0.1)", border: "1px solid var(--accent-success)", color: "var(--accent-success)" }}>
          {success}
        </div>
      )}

      {/* Readiness Evaluation Card */}
      {readiness && (
        <div style={{ padding: "1rem", background: "var(--bg-subtle)", borderRadius: "8px", border: "1px solid var(--border-subtle)", marginBottom: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}>
                Readiness Evaluation Engine
              </div>
              <div style={{ fontSize: "1.25rem", fontWeight: 700, marginTop: "0.2rem" }}>
                {satisfiedCount} of {totalSpecs} Specifications Ready
              </div>
            </div>

            <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Rule Engine</div>
                <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>{readiness.rule_version}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Audit Status</div>
                <span
                  className="badge"
                  style={{
                    background: blockers.length === 0 && totalSpecs > 0 ? "rgba(34, 197, 94, 0.15)" : "rgba(239, 68, 68, 0.15)",
                    color: blockers.length === 0 && totalSpecs > 0 ? "#16a34a" : "#dc2626",
                    fontWeight: 700,
                  }}
                >
                  {blockers.length === 0 && totalSpecs > 0 ? "Ready for Pre-Audit" : `${blockers.length} Blocker(s)`}
                </span>
              </div>
            </div>
          </div>

          {blockers.length > 0 && (
            <div style={{ marginTop: "0.75rem", paddingTop: "0.75rem", borderTop: "1px solid var(--border-subtle)" }}>
              <strong style={{ fontSize: "0.8rem", color: "#dc2626", display: "block", marginBottom: "0.25rem" }}>
                Identified Readiness Blockers:
              </strong>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                {blockers.map((b, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: "0.75rem",
                      padding: "0.2rem 0.5rem",
                      background: "rgba(239, 68, 68, 0.1)",
                      color: "#dc2626",
                      borderRadius: "4px",
                      border: "1px solid rgba(239, 68, 68, 0.2)",
                    }}
                  >
                    {b}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Evidence Requests List */}
      {loading ? (
        <div style={{ padding: "2rem", textAlign: "center", color: "var(--text-secondary)" }}>
          Loading evidence requests...
        </div>
      ) : requests.length === 0 ? (
        <div style={{ padding: "2rem", textAlign: "center", background: "var(--bg-subtle)", borderRadius: "8px" }}>
          <p style={{ margin: 0, fontWeight: 600, color: "var(--text-primary)" }}>
            No evidence requests generated for this framework.
          </p>
          <p style={{ margin: "0.5rem 0 1rem", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Generate structured requests to automatically assign compliance tasks to your team and collect required evidence items.
          </p>
          {canManage && (
            <button
              type="button"
              className="button primary"
              onClick={() => setShowGenerateModal(true)}
            >
              Generate Evidence Requests Now
            </button>
          )}
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border-subtle)", color: "var(--text-secondary)" }}>
                <th style={{ padding: "0.6rem 0.5rem" }}>Request / Task ID</th>
                <th style={{ padding: "0.6rem 0.5rem" }}>Specification</th>
                <th style={{ padding: "0.6rem 0.5rem" }}>Status</th>
                <th style={{ padding: "0.6rem 0.5rem" }}>Linked Evidence</th>
                <th style={{ padding: "0.6rem 0.5rem" }}>Observation Window</th>
                {canManage && <th style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => {
                const isAccepted = Boolean(req.evidence_id);
                const specProblem = readiness?.specifications?.find(
                  (s) => s.specification_id === req.specification_id
                )?.problem;

                return (
                  <tr key={req.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.6rem 0.5rem" }}>
                      <div style={{ fontWeight: 600, fontFamily: "monospace", fontSize: "0.8rem" }}>
                        REQ-{req.id.slice(0, 8)}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        Task: {req.task_id.slice(0, 8)}
                      </div>
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem" }}>
                      <span style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        {req.specification_id.slice(0, 13)}...
                      </span>
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem" }}>
                      {isAccepted ? (
                        <span
                          className="badge"
                          style={{
                            background: "rgba(34, 197, 94, 0.15)",
                            color: "#16a34a",
                            fontWeight: 600,
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        >
                          ✓ Accepted (v{req.evidence_version ?? 1})
                        </span>
                      ) : (
                        <span
                          className="badge"
                          style={{
                            background: "rgba(234, 179, 8, 0.15)",
                            color: "#ca8a04",
                            fontWeight: 600,
                            padding: "0.2rem 0.5rem",
                            borderRadius: "4px",
                            fontSize: "0.75rem",
                          }}
                        >
                          Pending Acceptance
                        </span>
                      )}
                      {specProblem && (
                        <div style={{ fontSize: "0.7rem", color: "#dc2626", marginTop: "0.2rem" }}>
                          ⚠️ {specProblem}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem" }}>
                      {req.evidence_id ? (
                        <div>
                          <div style={{ fontWeight: 500 }}>
                            {evidenceList.find((e) => e.id === req.evidence_id)?.title || `Evidence ${req.evidence_id.slice(0, 8)}`}
                          </div>
                          {req.accepted_at && (
                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                              Accepted: {new Date(req.accepted_at).toLocaleDateString()}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>
                          No evidence linked
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {req.observation_start && req.observation_end ? (
                        `${new Date(req.observation_start).toLocaleDateString()} – ${new Date(req.observation_end).toLocaleDateString()}`
                      ) : (
                        "—"
                      )}
                    </td>
                    {canManage && (
                      <td style={{ padding: "0.6rem 0.5rem", textAlign: "right" }}>
                        <button
                          type="button"
                          className={`button ${isAccepted ? "secondary" : "primary"}`}
                          onClick={() => {
                            setAcceptingRequest(req);
                            if (req.evidence_id) setSelectedEvidenceId(req.evidence_id);
                            else if (evidenceList.length > 0) setSelectedEvidenceId(evidenceList[0].id);
                          }}
                          style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
                        >
                          {isAccepted ? "Re-Accept" : "Accept Evidence"}
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Generate Requests Modal */}
      {showGenerateModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="card"
            style={{
              width: "100%",
              maxWidth: "500px",
              padding: "1.5rem",
              borderRadius: "10px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.2)",
            }}
          >
            <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.2rem" }}>
              Generate Evidence Requests
            </h3>
            <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Creates structured evidence request tasks for each specification in {frameworkName} v{versionString}.
            </p>

            <form onSubmit={(e) => void handleGenerateRequests(e)} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Assigned Owner
                </label>
                <select
                  value={selectedOwnerId}
                  onChange={(e) => setSelectedOwnerId(e.target.value)}
                  required
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                >
                  {members.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.display_name || m.email} ({m.role})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Due Date
                </label>
                <input
                  type="date"
                  required
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setShowGenerateModal(false)}
                  disabled={submittingGenerate}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={submittingGenerate || !selectedOwnerId}
                >
                  {submittingGenerate ? "Generating..." : "Generate Requests"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Accept Evidence Modal */}
      {acceptingRequest && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="card"
            style={{
              width: "100%",
              maxWidth: "520px",
              padding: "1.5rem",
              borderRadius: "10px",
              boxShadow: "0 20px 25px -5px rgba(0,0,0,0.2)",
            }}
          >
            <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1.2rem" }}>
              Accept Evidence Against Request
            </h3>
            <p style={{ margin: "0 0 1rem 0", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Link a validated tenant evidence record and record its observation period.
            </p>

            <form onSubmit={(e) => void handleAcceptEvidenceSubmit(e)} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Select Evidence Record
                </label>
                {evidenceList.length === 0 ? (
                  <p style={{ fontSize: "0.85rem", color: "#dc2626", margin: 0 }}>
                    No evidence items found in tenant repository. Please create or upload evidence in the Compliance Workspace first.
                  </p>
                ) : (
                  <select
                    value={selectedEvidenceId}
                    onChange={(e) => setSelectedEvidenceId(e.target.value)}
                    required
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                  >
                    {evidenceList.map((ev) => (
                      <option key={ev.id} value={ev.id}>
                        {ev.title} ({ev.classification} • {ev.status})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                    Observation Start
                  </label>
                  <input
                    type="date"
                    required
                    value={obsStart}
                    onChange={(e) => setObsStart(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                    Observation End
                  </label>
                  <input
                    type="date"
                    required
                    value={obsEnd}
                    onChange={(e) => setObsEnd(e.target.value)}
                    style={{ width: "100%", padding: "0.5rem", borderRadius: "6px", border: "1px solid var(--border-default)" }}
                  />
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setAcceptingRequest(null)}
                  disabled={submittingAccept}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button primary"
                  disabled={submittingAccept || !selectedEvidenceId || evidenceList.length === 0}
                >
                  {submittingAccept ? "Accepting..." : "Confirm Acceptance"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
