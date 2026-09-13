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
  evaluateAdoptionApplicability,
  type TenantProfileContextData,
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

  // Applicability Evaluation & Filter State
  const [showApplicabilityModal, setShowApplicabilityModal] = useState(false);
  const [evaluatingApplicability, setEvaluatingApplicability] = useState(false);
  const [applicabilityFilter, setApplicabilityFilter] = useState<
    "all" | "applicable" | "scoped_out" | "not_applicable"
  >("all");
  const [profileForm, setProfileForm] = useState<TenantProfileContextData>({
    entity_role: "both",
    deployment_model: "cloud_saas",
    employee_count: 25,
    processes_personal_data: true,
    processes_special_category_data: false,
    has_physical_offices: true,
    operates_own_datacenter: false,
    involves_international_transfers: false,
    uses_subprocessors: true,
  });

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

  async function handleEvaluateApplicability() {
    if (!selectedFramework) return;
    const activeAdoption = adoptions.find(
      (a) => a.framework_id === selectedFramework.id && a.status === "active"
    );
    if (!activeAdoption) return;

    setEvaluatingApplicability(true);
    try {
      const updatedOverlays = await evaluateAdoptionApplicability(
        token,
        tenantId,
        activeAdoption.id,
        profileForm
      );
      setOverlays(updatedOverlays);
      setShowApplicabilityModal(false);
      setAdoptionMessage(
        `Applicability evaluated successfully! ${updatedOverlays.length} controls evaluated.`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to evaluate applicability.");
    } finally {
      setEvaluatingApplicability(false);
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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ fontWeight: 600, color: isSelected ? "#1d4ed8" : "#111827" }}>{fw.name}</div>
                    {fw.is_blocked && (
                      <span style={{ fontSize: "0.6875rem", padding: "0.1rem 0.35rem", background: "#fee2e2", color: "#991b1b", borderRadius: "4px", fontWeight: 600 }}>
                        Blocked
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "0.25rem" }}>
                    {fwAdoption ? "✓ Adopted (Active)" : fw.is_blocked ? "Pending Decision" : "Available to Adopt"}
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: "1.25rem" }}>{selectedFramework.name}</h3>
                  <p style={{ margin: "0.25rem 0 0.75rem", color: "var(--color-text-muted)" }}>
                    {selectedFramework.description ?? "Standard compliance framework."}
                  </p>

                  {/* Pack Metadata Badges */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
                    <span style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", background: "#f1f5f9", borderRadius: "4px", color: "#334155" }}>
                      <strong>Jurisdiction:</strong> {selectedFramework.jurisdiction || "Universal"}
                    </span>
                    <span style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", background: "#f1f5f9", borderRadius: "4px", color: "#334155" }}>
                      <strong>Edition:</strong> {selectedFramework.source_edition || "Canonical"}
                    </span>
                    <span style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", background: "#f1f5f9", borderRadius: "4px", color: "#334155" }}>
                      <strong>Profile:</strong> {selectedFramework.profile || "Full Standard"}
                    </span>
                    {selectedFramework.declared_scope && (
                      <span style={{ fontSize: "0.75rem", padding: "0.2rem 0.5rem", background: "#e0e7ff", borderRadius: "4px", color: "#3730a3" }}>
                        <strong>Scope:</strong> {selectedFramework.declared_scope}
                      </span>
                    )}
                  </div>

                  {/* Blocker Alert Box */}
                  {selectedFramework.is_blocked && (
                    <div style={{ marginBottom: "0.75rem", padding: "0.6rem 0.8rem", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "6px", color: "#991b1b", fontSize: "0.8125rem" }}>
                      <strong style={{ display: "block", marginBottom: "0.25rem" }}>⚠️ Adoption Blocked</strong>
                      This pack is currently in draft status or pending owner/legal decision. It cannot be adopted or used for pre-audit certificates until published.
                      {selectedFramework.limitations && selectedFramework.limitations.length > 0 && (
                        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.25rem" }}>
                          {selectedFramework.limitations.map((lim, idx) => (
                            <li key={idx}>{lim}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}

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
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                  {selectedFramework.versions?.map((v) => {
                    const isAdopted = activeAdoption?.framework_version_id === v.id;
                    const isAnalyzing = analyzingTargetVersion === v.id;
                    const isBlocked = selectedFramework.is_blocked || v.is_blocked;
                    return (
                      <div key={v.id} style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                        <span style={{ fontSize: "0.875rem", fontWeight: 600, padding: "0.25rem 0.5rem", background: "#f3f4f6", borderRadius: "4px" }}>
                          v{v.version} ({v.release_state})
                        </span>
                        {canManage && !isAdopted && v.release_state === "released" && !isBlocked && (
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
                        {isBlocked && (
                          <span
                            title="Adoption is blocked for this framework version pending owner decision or release"
                            style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem", background: "#fee2e2", color: "#991b1b", borderRadius: "4px", fontWeight: 600 }}
                          >
                            Blocked
                          </span>
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
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: "1.1rem" }}>
                    Canonical Controls ({selectedVersion?.controls?.length ?? 0})
                  </h4>
                  <span style={{ fontSize: "0.75rem", color: "#6b7280", fontStyle: "italic" }}>
                    Canonical controls are system-managed, legally reviewed, and independently approved.
                  </span>
                </div>

                {canManage && activeAdoption && (
                  <button
                    onClick={() => setShowApplicabilityModal(true)}
                    style={{
                      padding: "0.4rem 0.75rem",
                      background: "#2563eb",
                      color: "white",
                      border: "none",
                      borderRadius: "6px",
                      fontSize: "0.8125rem",
                      fontWeight: 600,
                      cursor: "pointer",
                    }}
                  >
                    ⚡ Evaluate Applicability Rules
                  </button>
                )}
              </div>

              {/* Applicability Filter Tabs */}
              <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
                {(["all", "applicable", "scoped_out", "not_applicable"] as const).map((filterVal) => {
                  const count = (selectedVersion?.controls ?? []).filter((c) => {
                    const ov = overlays.find((o) => o.canonical_control_id === c.id);
                    const app = ov?.applicability ?? "applicable";
                    return filterVal === "all" ? true : app === filterVal;
                  }).length;

                  const label =
                    filterVal === "all"
                      ? "All Controls"
                      : filterVal === "applicable"
                      ? "Applicable"
                      : filterVal === "scoped_out"
                      ? "Scoped Out"
                      : "Not Applicable";

                  const isActive = applicabilityFilter === filterVal;

                  return (
                    <button
                      key={filterVal}
                      onClick={() => setApplicabilityFilter(filterVal)}
                      style={{
                        padding: "0.3rem 0.65rem",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        border: "1px solid",
                        borderColor: isActive ? "#2563eb" : "#d1d5db",
                        borderRadius: "20px",
                        background: isActive ? "#eff6ff" : "white",
                        color: isActive ? "#1d4ed8" : "#4b5563",
                        cursor: "pointer",
                      }}
                    >
                      {label} ({count})
                    </button>
                  );
                })}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {selectedVersion?.controls
                  ?.filter((ctrl) => {
                    const overlay = overlays.find((o) => o.canonical_control_id === ctrl.id);
                    const currentApp = overlay?.applicability ?? "applicable";
                    return applicabilityFilter === "all" ? true : currentApp === applicabilityFilter;
                  })
                  .map((ctrl) => {
                  const overlay = overlays.find((o) => o.canonical_control_id === ctrl.id);
                  const applicabilityState = overlay?.applicability ?? "applicable";
                  return (
                    <div
                      key={ctrl.id}
                      style={{
                        padding: "0.875rem",
                        border: "1px solid var(--color-border)",
                        borderRadius: "6px",
                        backgroundColor:
                          applicabilityState === "scoped_out"
                            ? "#fffbeb"
                            : applicabilityState === "not_applicable"
                            ? "#f3f4f6"
                            : "white",
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
                          <span
                            style={{
                              marginLeft: "0.5rem",
                              fontSize: "0.75rem",
                              padding: "0.15rem 0.45rem",
                              borderRadius: "4px",
                              fontWeight: 600,
                              textTransform: "capitalize",
                              backgroundColor:
                                applicabilityState === "applicable"
                                  ? "#dcfce7"
                                  : applicabilityState === "scoped_out"
                                  ? "#fef3c7"
                                  : "#e5e7eb",
                              color:
                                applicabilityState === "applicable"
                                  ? "#15803d"
                                  : applicabilityState === "scoped_out"
                                  ? "#b45309"
                                  : "#4b5563",
                            }}
                          >
                            {applicabilityState.replace("_", " ")}
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

                      {/* Display Guidance / Evidence Requests if present */}
                      {ctrl.guidance && (
                        <div style={{ marginTop: "0.6rem", padding: "0.6rem 0.8rem", background: "#f8fafc", borderRadius: "4px", fontSize: "0.8125rem", borderLeft: "3px solid #64748b", whiteSpace: "pre-line" }}>
                          <strong style={{ color: "#334155" }}>Implementation & Evidence Guidance:</strong>
                          <div style={{ marginTop: "0.25rem", color: "#475569" }}>{ctrl.guidance}</div>
                        </div>
                      )}

                      {/* Display Provenance & Coverage if present */}
                      {(ctrl.source_reference || ctrl.why_evidence_requested || ctrl.coverage_disposition) && (
                        <div style={{ marginTop: "0.5rem", padding: "0.5rem 0.75rem", background: "#f8fafc", borderRadius: "4px", fontSize: "0.8125rem", border: "1px solid #e2e8f0" }}>
                          {ctrl.source_reference && (
                            <div style={{ marginBottom: "0.25rem" }}>
                              <strong style={{ color: "#475569" }}>Source Reference: </strong>
                              <span style={{ color: "#1e293b", fontFamily: "monospace" }}>{ctrl.source_reference}</span>
                            </div>
                          )}
                          {ctrl.why_evidence_requested && (
                            <div style={{ marginBottom: "0.25rem" }}>
                              <strong style={{ color: "#475569" }}>Evidence Purpose: </strong>
                              <span style={{ color: "#334155" }}>{ctrl.why_evidence_requested}</span>
                            </div>
                          )}
                          {ctrl.coverage_disposition && (
                            <div>
                              <strong style={{ color: "#475569" }}>Coverage Disposition: </strong>
                              <span style={{ color: "#0f766e", fontWeight: 600 }}>{ctrl.coverage_disposition}</span>
                              {ctrl.coverage_rationale && (
                                <span style={{ color: "#64748b" }}> — {ctrl.coverage_rationale}</span>
                              )}
                            </div>
                          )}
                        </div>
                      )}

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

      {/* Applicability Evaluation Modal */}
      {showApplicabilityModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="card"
            style={{
              background: "white",
              padding: "1.5rem",
              maxWidth: "540px",
              width: "100%",
              maxHeight: "90vh",
              overflowY: "auto",
            }}
          >
            <h4 style={{ margin: "0 0 0.5rem", fontSize: "1.2rem" }}>
              ⚡ Deterministic Applicability Questionnaire
            </h4>
            <p style={{ margin: "0 0 1rem", fontSize: "0.8125rem", color: "#6b7280" }}>
              Configure your operational profile to deterministically determine applicable, scoped out, and non-applicable safeguards.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", fontSize: "0.875rem" }}>
              <div>
                <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Regulatory Role under GDPR / Privacy
                </label>
                <select
                  value={profileForm.entity_role ?? "both"}
                  onChange={(e) =>
                    setProfileForm((prev) => ({
                      ...prev,
                      entity_role: e.target.value as "controller" | "processor" | "both",
                    }))
                  }
                  style={{ width: "100%", padding: "0.45rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
                >
                  <option value="both">Both Controller & Processor</option>
                  <option value="controller">Data Controller Only</option>
                  <option value="processor">Data Processor Only</option>
                </select>
              </div>

              <div>
                <label style={{ display: "block", fontWeight: 600, marginBottom: "0.25rem" }}>
                  Total Employee Count (German § 38 BDSG DPO threshold if &ge; 20)
                </label>
                <input
                  type="number"
                  min={1}
                  value={profileForm.employee_count ?? 25}
                  onChange={(e) =>
                    setProfileForm((prev) => ({
                      ...prev,
                      employee_count: parseInt(e.target.value, 10) || 1,
                    }))
                  }
                  style={{ width: "100%", padding: "0.45rem", borderRadius: "4px", border: "1px solid #d1d5db" }}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={profileForm.has_physical_offices ?? true}
                    onChange={(e) =>
                      setProfileForm((prev) => ({ ...prev, has_physical_offices: e.target.checked }))
                    }
                  />
                  <span>Has physical office facilities (uncheck if 100% remote)</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={profileForm.operates_own_datacenter ?? false}
                    onChange={(e) =>
                      setProfileForm((prev) => ({ ...prev, operates_own_datacenter: e.target.checked }))
                    }
                  />
                  <span>Operates own data centers (uncheck if 100% public cloud)</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={profileForm.processes_special_category_data ?? false}
                    onChange={(e) =>
                      setProfileForm((prev) => ({ ...prev, processes_special_category_data: e.target.checked }))
                    }
                  />
                  <span>Processes special category data (health/biometrics under § 22 BDSG)</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={profileForm.involves_international_transfers ?? false}
                    onChange={(e) =>
                      setProfileForm((prev) => ({ ...prev, involves_international_transfers: e.target.checked }))
                    }
                  />
                  <span>Transfers personal data outside the European Economic Area (EEA)</span>
                </label>

                <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={profileForm.uses_subprocessors ?? true}
                    onChange={(e) =>
                      setProfileForm((prev) => ({ ...prev, uses_subprocessors: e.target.checked }))
                    }
                  />
                  <span>Uses third-party sub-processors / external vendors</span>
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1rem" }}>
                <button
                  type="button"
                  onClick={() => setShowApplicabilityModal(false)}
                  disabled={evaluatingApplicability}
                  style={{ padding: "0.5rem 1rem", background: "#e5e7eb", border: "none", borderRadius: "4px", cursor: "pointer" }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleEvaluateApplicability}
                  disabled={evaluatingApplicability}
                  style={{
                    padding: "0.5rem 1rem",
                    background: "#2563eb",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    fontWeight: 600,
                    cursor: evaluatingApplicability ? "not-allowed" : "pointer",
                  }}
                >
                  {evaluatingApplicability ? "Evaluating..." : "Run Evaluation"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
