import type {
  CanonicalControlSummary,
  ControlMappingSummary,
  CustomControlSummary,
  FrameworkSummary,
  FrameworkVersionSummary,
  ImpactReportSummary,
  OverlayApplicability,
  TenantControlOverlaySummary,
  TenantFrameworkAdoptionSummary,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  adoptFrameworkVersion,
  createCustomControl,
  deleteControlMapping,
  deleteTenantOverlay,
  getCanonicalVersionDetails,
  getTenantImpactAnalysis,
  listCanonicalFrameworks,
  listControlMappings,
  listCustomControls,
  listTenantAdoptions,
  listTenantOverlays,
  manageTenantOverlay,
} from "../api";
import { getAccessToken } from "../auth";
import { canManageFrameworks } from "../permissions";

interface FrameworkCatalogProps {
  tenantId: string;
  userRole: TenantRole;
}

export function FrameworkCatalog({ tenantId, userRole }: FrameworkCatalogProps) {
  const token = getAccessToken() ?? "";
  const canManage = canManageFrameworks(userRole);

  const [frameworks, setFrameworks] = useState<FrameworkSummary[]>([]);
  const [adoptions, setAdoptions] = useState<TenantFrameworkAdoptionSummary[]>([]);
  const [selectedFramework, setSelectedFramework] = useState<FrameworkSummary | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<FrameworkVersionSummary | null>(null);
  const [overlays, setOverlays] = useState<TenantControlOverlaySummary[]>([]);
  const [customControls, setCustomControls] = useState<CustomControlSummary[]>([]);
  const [mappings, setMappings] = useState<ControlMappingSummary[]>([]);

  // Impact Analysis & Adoption State
  const [impactReport, setImpactReport] = useState<ImpactReportSummary | null>(null);
  const [analyzingTargetVersion, setAnalyzingTargetVersion] = useState<string | null>(null);
  const [adoptionMessage, setAdoptionMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // New Custom Control Form State
  const [newCustIdent, setNewCustIdent] = useState("");
  const [newCustTitle, setNewCustTitle] = useState("");
  const [newCustDesc, setNewCustDesc] = useState("");
  const [newCustCat, setNewCustCat] = useState("Organizational");

  // Overlay Edit Modal State
  const [overlayControl, setOverlayControl] = useState<CanonicalControlSummary | null>(null);
  const [overlayApplicability, setOverlayApplicability] =
    useState<OverlayApplicability>("applicable");
  const [overlayNotes, setOverlayNotes] = useState("");
  const [overlayJustification, setOverlayJustification] = useState("");

  const loadCatalogData = useCallback(async () => {
    try {
      const [fws, adps, custs, maps] = await Promise.all([
        listCanonicalFrameworks(token),
        listTenantAdoptions(token, tenantId),
        listCustomControls(token, tenantId),
        listControlMappings(token, tenantId),
      ]);
      setFrameworks(fws);
      setAdoptions(adps);
      setCustomControls(custs);
      setMappings(maps);

      if (fws.length > 0) {
        setSelectedFramework((curr) => curr ?? fws[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load framework catalog.");
    } finally {
      setLoading(false);
    }
  }, [tenantId, token]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadCatalogData();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadCatalogData]);

  useEffect(() => {
    let active = true;
    async function loadVersionDetails() {
      if (!selectedFramework) return;
      const releasedVersion =
        selectedFramework.versions?.find((v) => v.release_state === "released") ??
        selectedFramework.versions?.[0];
      if (releasedVersion) {
        try {
          const detailed = await getCanonicalVersionDetails(
            token,
            selectedFramework.id,
            releasedVersion.id
          );
          if (active) setSelectedVersion(detailed);
        } catch {
          // ignore
        }
      } else {
        if (active) setSelectedVersion(null);
      }
    }
    void loadVersionDetails();
    return () => {
      active = false;
    };
  }, [selectedFramework, token]);

  useEffect(() => {
    let active = true;
    async function loadAdoptionOverlays() {
      if (!selectedFramework) return;
      const activeAdoption = adoptions.find(
        (a) => a.framework_id === selectedFramework.id && a.status === "active"
      );
      if (activeAdoption) {
        try {
          const ovs = await listTenantOverlays(token, tenantId, activeAdoption.id);
          if (active) setOverlays(ovs);
        } catch {
          if (active) setOverlays([]);
        }
      } else {
        if (active) setOverlays([]);
      }
    }
    void loadAdoptionOverlays();
    return () => {
      active = false;
    };
  }, [selectedFramework, adoptions, tenantId, token]);

  async function handleRunImpactAnalysis(targetVersionId: string) {
    if (!selectedFramework) return;
    setAnalyzingTargetVersion(targetVersionId);
    setError(null);
    try {
      const report = await getTenantImpactAnalysis(
        token,
        tenantId,
        selectedFramework.id,
        targetVersionId
      );
      setImpactReport(report);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run impact analysis.");
    } finally {
      setAnalyzingTargetVersion(null);
    }
  }

  async function handleAdoptVersion(versionId: string) {
    if (!canManage) return;
    setError(null);
    setAdoptionMessage(null);
    try {
      await adoptFrameworkVersion(token, tenantId, versionId, true);
      setAdoptionMessage("Successfully adopted framework version.");
      setImpactReport(null);
      await loadCatalogData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to adopt version.");
    }
  }

  async function handleSaveOverlay() {
    if (!overlayControl || !selectedFramework) return;
    const activeAdoption = adoptions.find(
      (a) => a.framework_id === selectedFramework.id && a.status === "active"
    );
    if (!activeAdoption) return;

    try {
      await manageTenantOverlay(token, tenantId, activeAdoption.id, {
        canonical_control_id: overlayControl.id,
        applicability: overlayApplicability,
        justification: overlayJustification,
        internal_notes: overlayNotes,
      });
      setOverlayControl(null);
      const ovs = await listTenantOverlays(token, tenantId, activeAdoption.id);
      setOverlays(ovs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save overlay.");
    }
  }

  async function handleDeleteOverlay(overlayId: string) {
    if (!selectedFramework) return;
    const activeAdoption = adoptions.find(
      (a) => a.framework_id === selectedFramework.id && a.status === "active"
    );
    if (!activeAdoption) return;

    try {
      await deleteTenantOverlay(token, tenantId, activeAdoption.id, overlayId);
      const ovs = await listTenantOverlays(token, tenantId, activeAdoption.id);
      setOverlays(ovs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete overlay.");
    }
  }

  async function handleDeleteMapping(mappingId: string) {
    if (!canManage) return;
    try {
      await deleteControlMapping(token, tenantId, mappingId);
      setMappings((prev) => prev.filter((m) => m.id !== mappingId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete mapping.");
    }
  }

  async function handleCreateCustomControl(e: React.FormEvent) {
    e.preventDefault();
    if (!canManage || !newCustIdent || !newCustTitle || !newCustDesc) return;
    try {
      const created = await createCustomControl(token, tenantId, {
        identifier: newCustIdent,
        title: newCustTitle,
        description: newCustDesc,
        category: newCustCat,
      });
      setCustomControls((prev) => [...prev, created]);
      setNewCustIdent("");
      setNewCustTitle("");
      setNewCustDesc("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create custom control.");
    }
  }

  if (loading) {
    return <div className="card" style={{ padding: "2rem" }}>Loading compliance frameworks...</div>;
  }

  const activeAdoption = selectedFramework
    ? adoptions.find((a) => a.framework_id === selectedFramework.id && a.status === "active")
    : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 700 }}>Framework Catalog & Overlays</h2>
          <p style={{ margin: "0.25rem 0 0", color: "var(--color-text-muted)" }}>
            Canonical compliance catalogs, tenant overlays, custom controls, and version impact analysis.
          </p>
        </div>
      </div>

      {error && (
        <div style={{ padding: "0.75rem 1rem", backgroundColor: "#fee2e2", color: "#991b1b", borderRadius: "6px" }}>
          {error}
        </div>
      )}
      {adoptionMessage && (
        <div style={{ padding: "0.75rem 1rem", backgroundColor: "#dcfce7", color: "#166534", borderRadius: "6px" }}>
          {adoptionMessage}
        </div>
      )}

      {/* Framework Selector & Active Adoption Status */}
      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: "1.5rem" }}>
        {/* Left: Frameworks list */}
        <div className="card" style={{ padding: "1rem" }}>
          <h3 style={{ margin: "0 0 1rem", fontSize: "1rem", fontWeight: 600 }}>Compliance Catalogs</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {frameworks.map((fw) => {
              const isSelected = selectedFramework?.id === fw.id;
              const fwAdoption = adoptions.find((a) => a.framework_id === fw.id && a.status === "active");
              return (
                <button
                  key={fw.id}
                  onClick={() => {
                    setSelectedFramework(fw);
                    setImpactReport(null);
                  }}
                  style={{
                    padding: "0.75rem",
                    textAlign: "left",
                    borderRadius: "6px",
                    border: isSelected ? "2px solid #2563eb" : "1px solid var(--color-border)",
                    backgroundColor: isSelected ? "#eff6ff" : "white",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontWeight: 600, color: isSelected ? "#1d4ed8" : "#111827" }}>{fw.name}</div>
                  <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "0.25rem" }}>
                    {fwAdoption ? "✓ Adopted (Active)" : "Available to Adopt"}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Selected Framework Details */}
        {selectedFramework && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Framework Banner */}
            <div className="card" style={{ padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.25rem" }}>{selectedFramework.name}</h3>
                  <p style={{ margin: "0.25rem 0 0.75rem", color: "var(--color-text-muted)" }}>
                    {selectedFramework.description ?? "Standard compliance framework."}
                  </p>
                  <div style={{ fontSize: "0.875rem", color: "#4b5563" }}>
                    <strong>Active Adoption: </strong>
                    {activeAdoption ? (
                      <span style={{ color: "#166534", fontWeight: 600 }}>
                        Active (Version {selectedFramework.versions?.find((v) => v.id === activeAdoption.framework_version_id)?.version ?? "Adopted"})
                      </span>
                    ) : (
                      <span style={{ color: "#b45309" }}>Not yet adopted</span>
                    )}
                  </div>
                </div>

                {/* Available Versions Dropdown & Actions */}
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  {selectedFramework.versions?.map((v) => {
                    const isAdopted = activeAdoption?.framework_version_id === v.id;
                    const isAnalyzing = analyzingTargetVersion === v.id;
                    return (
                      <div key={v.id} style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                        <span style={{ fontSize: "0.875rem", fontWeight: 600, padding: "0.25rem 0.5rem", background: "#f3f4f6", borderRadius: "4px" }}>
                          v{v.version} ({v.release_state})
                        </span>
                        {canManage && !isAdopted && v.release_state === "released" && (
                          <button
                            onClick={() => handleRunImpactAnalysis(v.id)}
                            disabled={isAnalyzing}
                            style={{
                              fontSize: "0.75rem",
                              padding: "0.25rem 0.5rem",
                              background: isAnalyzing ? "#9ca3af" : "#3b82f6",
                              color: "white",
                              border: "none",
                              borderRadius: "4px",
                              cursor: isAnalyzing ? "not-allowed" : "pointer",
                            }}
                          >
                            {isAnalyzing ? "Analyzing..." : "Analyze & Adopt"}
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Impact Analysis Warning Panel (if computed) */}
            {impactReport && (
              <div className="card" style={{ padding: "1.25rem", borderLeft: "4px solid var(--color-warning)", backgroundColor: "var(--color-warning-bg)" }}>
                <h4 style={{ margin: "0 0 0.5rem", color: "var(--color-warning)" }}>
                  Version Upgrade Impact Analysis: v{impactReport.source_version_string} → v{impactReport.target_version_string}
                </h4>
                <div style={{ display: "flex", gap: "1.5rem", fontSize: "0.875rem", marginBottom: "0.75rem" }}>
                  <div><strong>Overall Risk:</strong> <span style={{ textTransform: "uppercase", fontWeight: 700, color: impactReport.overall_impact_level === "high" ? "var(--color-danger)" : "var(--color-warning)" }}>{impactReport.overall_impact_level}</span></div>
                  <div><strong>Added:</strong> {impactReport.added_controls.length}</div>
                  <div><strong>Modified:</strong> {impactReport.modified_controls.length}</div>
                  <div><strong>Removed:</strong> {impactReport.removed_controls.length}</div>
                  <div><strong>Unchanged:</strong> {impactReport.unchanged_count}</div>
                </div>

                {impactReport.tenant_warnings.length > 0 && (
                  <div style={{ marginBottom: "1rem" }}>
                    <strong style={{ fontSize: "0.875rem", color: "#991b1b" }}>Tenant Warnings:</strong>
                    <ul style={{ margin: "0.25rem 0 0", paddingLeft: "1.25rem", fontSize: "0.875rem", color: "#b91c1c" }}>
                      {impactReport.tenant_warnings.map((w, idx) => (
                        <li key={idx}>
                          <strong>[{w.severity.toUpperCase()}] {w.control_identifier}:</strong> {w.message} — <em>{w.recommendation}</em>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <button
                    onClick={() => handleAdoptVersion(impactReport.target_version_id)}
                    style={{
                      padding: "0.5rem 1rem",
                      backgroundColor: "#16a34a",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    Confirm & Adopt v{impactReport.target_version_string}
                  </button>
                  <button
                    onClick={() => setImpactReport(null)}
                    style={{
                      padding: "0.5rem 1rem",
                      backgroundColor: "#e5e7eb",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Canonical Controls Table with Tenant Overlays */}
            <div className="card" style={{ padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <h4 style={{ margin: 0, fontSize: "1.1rem" }}>
                  Canonical Controls ({selectedVersion?.controls?.length ?? 0})
                </h4>
                <span style={{ fontSize: "0.75rem", color: "#6b7280", fontStyle: "italic" }}>
                  Canonical controls are system-managed and immutable.
                </span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {selectedVersion?.controls?.map((ctrl) => {
                  const overlay = overlays.find((o) => o.canonical_control_id === ctrl.id);
                  return (
                    <div
                      key={ctrl.id}
                      style={{
                        padding: "0.875rem",
                        border: "1px solid var(--color-border)",
                        borderRadius: "6px",
                        backgroundColor: overlay ? "#f8fafc" : "white",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                        <div>
                          <span style={{ fontWeight: 700, color: "#1e40af", marginRight: "0.5rem" }}>
                            {ctrl.identifier}
                          </span>
                          <span style={{ fontWeight: 600 }}>{ctrl.title}</span>
                          <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", padding: "0.15rem 0.4rem", background: "#e0f2fe", color: "#0369a1", borderRadius: "4px" }}>
                            {ctrl.category}
                          </span>
                        </div>

                        {canManage && activeAdoption && (
                          <div style={{ display: "flex", gap: "0.5rem" }}>
                            <button
                              onClick={() => {
                                setOverlayControl(ctrl);
                                setOverlayApplicability(overlay?.applicability ?? "applicable");
                                setOverlayNotes(overlay?.internal_notes ?? "");
                                setOverlayJustification(overlay?.justification ?? "");
                              }}
                              style={{
                                fontSize: "0.75rem",
                                padding: "0.25rem 0.5rem",
                                background: "#475569",
                                color: "white",
                                border: "none",
                                borderRadius: "4px",
                                cursor: "pointer",
                              }}
                            >
                              {overlay ? "Edit Overlay" : "+ Add Overlay"}
                            </button>
                            {overlay && (
                              <button
                                onClick={() => handleDeleteOverlay(overlay.id)}
                                style={{
                                  fontSize: "0.75rem",
                                  padding: "0.25rem 0.5rem",
                                  background: "#ef4444",
                                  color: "white",
                                  border: "none",
                                  borderRadius: "4px",
                                  cursor: "pointer",
                                }}
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        )}
                      </div>

                      <p style={{ margin: "0.5rem 0 0", fontSize: "0.875rem", color: "#374151" }}>
                        {ctrl.description}
                      </p>

                      {/* Display Overlay details if present */}
                      {overlay && (
                        <div style={{ marginTop: "0.5rem", padding: "0.5rem 0.75rem", background: "#f1f5f9", borderRadius: "4px", fontSize: "0.8125rem", borderLeft: "3px solid #3b82f6" }}>
                          <div><strong>Tenant Status:</strong> <span style={{ textTransform: "capitalize", fontWeight: 600 }}>{overlay.applicability.replace("_", " ")}</span></div>
                          {overlay.internal_notes && <div><strong>Internal Notes:</strong> {overlay.internal_notes}</div>}
                          {overlay.justification && <div><strong>Justification:</strong> {overlay.justification}</div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Tenant Custom Controls Section */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ margin: "0 0 0.5rem", fontSize: "1.25rem" }}>Tenant Custom Controls</h3>
        <p style={{ margin: "0 0 1rem", fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
          Define organization-specific controls independent of canonical catalogs.
        </p>

        {canManage && (
          <form onSubmit={handleCreateCustomControl} style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem", padding: "0.75rem", background: "#f9fafb", borderRadius: "6px" }}>
            <input
              type="text"
              placeholder="Identifier (e.g. CUST-01)"
              value={newCustIdent}
              onChange={(e) => setNewCustIdent(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "4px", border: "1px solid #d1d5db", width: "150px" }}
              required
            />
            <input
              type="text"
              placeholder="Control Title"
              value={newCustTitle}
              onChange={(e) => setNewCustTitle(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "4px", border: "1px solid #d1d5db", flex: "1" }}
              required
            />
            <input
              type="text"
              placeholder="Category"
              value={newCustCat}
              onChange={(e) => setNewCustCat(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "4px", border: "1px solid #d1d5db", width: "140px" }}
              required
            />
            <input
              type="text"
              placeholder="Description"
              value={newCustDesc}
              onChange={(e) => setNewCustDesc(e.target.value)}
              style={{ padding: "0.4rem", borderRadius: "4px", border: "1px solid #d1d5db", flex: "2" }}
              required
            />
            <button
              type="submit"
              style={{ padding: "0.4rem 0.8rem", background: "#2563eb", color: "white", border: "none", borderRadius: "4px", fontWeight: 600, cursor: "pointer" }}
            >
              Add Custom Control
            </button>
          </form>
        )}

        {customControls.length === 0 ? (
          <div style={{ color: "#6b7280", fontSize: "0.875rem" }}>No custom controls defined.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {customControls.map((c) => (
              <div key={c.id} style={{ padding: "0.75rem", border: "1px solid var(--color-border)", borderRadius: "4px" }}>
                <span style={{ fontWeight: 700, color: "#16a34a", marginRight: "0.5rem" }}>{c.identifier}</span>
                <span style={{ fontWeight: 600 }}>{c.title}</span>
                <span style={{ marginLeft: "0.5rem", fontSize: "0.75rem", padding: "0.1rem 0.4rem", background: "#f3f4f6", borderRadius: "4px" }}>
                  {c.category}
                </span>
                <div style={{ fontSize: "0.875rem", color: "#4b5563", marginTop: "0.25rem" }}>{c.description}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Control Mappings Section */}
      <div className="card" style={{ padding: "1.25rem" }}>
        <h3 style={{ margin: "0 0 0.5rem", fontSize: "1.25rem" }}>Control Mappings</h3>
        <p style={{ margin: "0 0 1rem", fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
          Explicit cross-mappings between canonical framework controls and internal tenant controls.
        </p>

        {mappings.length === 0 ? (
          <div style={{ color: "#6b7280", fontSize: "0.875rem" }}>No control mappings defined.</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {mappings.map((m) => (
              <div key={m.id} style={{ padding: "0.75rem", border: "1px solid var(--color-border)", borderRadius: "4px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <span style={{ fontWeight: 600 }}>{m.source_type}</span>
                  <span style={{ margin: "0 0.5rem", color: "#6b7280" }}>→ [{m.mapping_type}] →</span>
                  <span style={{ fontWeight: 600 }}>{m.target_type}</span>
                  {m.rationale && <div style={{ fontSize: "0.8125rem", color: "#4b5563", marginTop: "0.25rem" }}>{m.rationale}</div>}
                </div>
                {canManage && (
                  <button
                    onClick={() => handleDeleteMapping(m.id)}
                    style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", background: "#ef4444", color: "white", border: "none", borderRadius: "4px", cursor: "pointer" }}
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Overlay Modal */}
      {overlayControl && (
        <div style={{ position: "fixed", inset: 0, backgroundColor: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div className="card" style={{ width: "500px", padding: "1.5rem" }}>
            <h4 style={{ margin: "0 0 0.5rem" }}>Edit Overlay: {overlayControl.identifier}</h4>
            <p style={{ margin: "0 0 1rem", fontSize: "0.875rem", color: "#6b7280" }}>{overlayControl.title}</p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.25rem" }}>Applicability</label>
                <select
                  value={overlayApplicability}
                  onChange={(e) => setOverlayApplicability(e.target.value as OverlayApplicability)}
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
                >
                  <option value="applicable">Applicable</option>
                  <option value="not_applicable">Not Applicable</option>
                  <option value="scoped_out">Scoped Out</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.25rem" }}>Justification</label>
                <textarea
                  value={overlayJustification}
                  onChange={(e) => setOverlayJustification(e.target.value)}
                  rows={2}
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, marginBottom: "0.25rem" }}>Internal Guidance / Notes</label>
                <textarea
                  value={overlayNotes}
                  onChange={(e) => setOverlayNotes(e.target.value)}
                  rows={3}
                  style={{ width: "100%", padding: "0.5rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => setOverlayControl(null)}
                  style={{ padding: "0.5rem 1rem", background: "#e5e7eb", border: "none", borderRadius: "4px", cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveOverlay}
                  style={{ padding: "0.5rem 1rem", background: "#2563eb", color: "white", border: "none", borderRadius: "4px", fontWeight: 600, cursor: "pointer" }}
                >
                  Save Overlay
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
