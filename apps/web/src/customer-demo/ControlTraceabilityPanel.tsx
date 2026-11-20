import React, { FC, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { AssessmentWorkItem } from "./assessment-types";
import { ControlWorkItem } from "./control-evidence-types";
import "./modern-workspace.css";

export interface ControlTraceabilityPanelProps {
  control: ControlWorkItem;
  assessment?: AssessmentWorkItem | null;
  onNavigateToEvidence?: (workId: string) => void;
  onNavigateToAssessment?: (workId: string) => void;
  onClose?: () => void;
}

export const ControlTraceabilityPanel: FC<ControlTraceabilityPanelProps> = ({
  control,
  assessment,
  onNavigateToEvidence,
  onNavigateToAssessment,
  onClose,
}) => {
  const { t } = useTranslation();
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (text: string, id: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1500);
    }
  };

  const links = control.links || [];
  const findings = assessment?.findings || [];
  const history = assessment?.history || [];
  const reqResults = control.requirement_results || [];

  return (
    <section
      className="mw-card"
      data-testid="control-traceability-panel"
      aria-labelledby="traceability-panel-title"
      style={{
        border: "1px solid var(--mw-primary, #0066cc)",
        background: "#ffffff",
        marginBottom: "1.5rem",
      }}
    >
      <div
        className="mw-card-header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          flexWrap: "wrap",
          gap: "0.5rem",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
            <span
              style={{
                fontSize: "0.75rem",
                padding: "0.15rem 0.4rem",
                borderRadius: "4px",
                background: "rgba(0, 102, 204, 0.1)",
                color: "var(--mw-primary, #0066cc)",
                fontWeight: 700,
              }}
            >
              {control.control_id}
            </span>
            <span style={{ fontSize: "0.75rem", color: "#666" }}>
              Work ID: {control.id}
            </span>
          </div>
          <h2 id="traceability-panel-title" className="mw-card-title" style={{ fontSize: "1.2rem" }}>
            {control.title}
          </h2>
          <p className="mw-card-subtitle">
            {t("portal.traceabilitySubtitle") || "Complete pin-level traceability for control, evidence, and assessment."}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {onClose && (
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="close-traceability-btn"
              onClick={onClose}
              style={{ fontSize: "0.85rem", padding: "0.3rem 0.6rem" }}
            >
              {t("portal.closeBtn") || "Close"}
            </button>
          )}
        </div>
      </div>

      <div className="mw-card-body" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {/* Synthetic Provenance Disclaimer Banner */}
        <div
          role="note"
          data-testid="synthetic-provenance-banner"
          className="mw-notice-banner"
          style={{
            borderColor: "#6c757d",
            background: "rgba(108, 117, 125, 0.05)",
            color: "#495057",
            fontSize: "0.8rem",
          }}
        >
          <strong>Synthetic Demonstration Notice: </strong>
          {t("portal.syntheticProvenanceNotice") ||
            "Framework pack requirements, controls, and procedures are synthetic demonstration artifacts. They do not constitute validated legal opinions, official certifications, or compliance guarantees."}
        </div>

        {/* Action Navigation Shortcuts */}
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          {onNavigateToEvidence && (
            <button
              type="button"
              className="mw-btn mw-btn-primary"
              data-testid="nav-to-evidence-btn"
              onClick={() => onNavigateToEvidence(control.id)}
              style={{ fontSize: "0.85rem" }}
            >
              {t("portal.openEvidenceBtn") || "Open Evidence Workspace"}
            </button>
          )}
          {onNavigateToAssessment && (
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="nav-to-assessment-btn"
              onClick={() => onNavigateToAssessment(control.id)}
              style={{ fontSize: "0.85rem" }}
            >
              {t("portal.openAssessmentBtn") || "Open Assessment Workspace"}
            </button>
          )}
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="toggle-technical-details-btn"
            onClick={() => setShowTechnicalDetails((prev) => !prev)}
            style={{ fontSize: "0.85rem" }}
          >
            {showTechnicalDetails ? "Hide Technical Hashes" : "Show Technical Hashes & Pins"}
          </button>
        </div>

        {/* SECTION 1: Framework & Control Version Pins */}
        <div
          data-testid="section-version-pins"
          style={{
            padding: "0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--mw-border-color, #e0e0e0)",
            background: "rgba(0,0,0,0.01)",
          }}
        >
          <h3 style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            Framework & Control Version Pins
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.5rem", fontSize: "0.85rem" }}>
            <div>
              <span style={{ color: "#666" }}>Pack Version: </span>
              <strong data-testid="trace-pack-version">v{control.pack_version}</strong>
            </div>
            <div>
              <span style={{ color: "#666" }}>Control Version ID: </span>
              <code style={{ fontSize: "0.8rem" }}>{control.control_version_id}</code>
            </div>
            <div>
              <span style={{ color: "#666" }}>Owner: </span>
              <strong>{control.owner_display_name || "Unassigned"}</strong>
            </div>
            <div>
              <span style={{ color: "#666" }}>Due Date: </span>
              <strong>{control.due_date || "None set"}</strong>
            </div>
          </div>

          {showTechnicalDetails && (
            <div style={{ marginTop: "0.5rem", paddingTop: "0.5rem", borderTop: "1px dashed var(--mw-border-color, #e0e0e0)", fontSize: "0.8rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span>Bundle Digest: </span>
                <code style={{ wordBreak: "break-all" }}>{control.bundle_digest}</code>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => handleCopy(control.bundle_digest, "bundle_digest")}
                  style={{ fontSize: "0.7rem", padding: "0.1rem 0.3rem" }}
                >
                  {copiedId === "bundle_digest" ? "Copied" : "Copy"}
                </button>
              </div>
              <div style={{ marginTop: "0.25rem" }}>
                <span>Provenance: </span>
                <code>{control.provenance}</code>
              </div>
            </div>
          )}

          {/* Mapped Requirements */}
          <div style={{ marginTop: "0.75rem" }}>
            <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#555", marginBottom: "0.3rem" }}>
              Mapped Requirements ({reqResults.length})
            </div>
            {reqResults.length === 0 ? (
              <span style={{ fontSize: "0.8rem", color: "#888" }}>No direct requirement mappings.</span>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                {reqResults.map((r) => (
                  <span
                    key={r.requirement_id}
                    data-testid={`req-badge-${r.requirement_id}`}
                    style={{
                      fontSize: "0.75rem",
                      padding: "0.2rem 0.5rem",
                      borderRadius: "4px",
                      background: r.result === "APPLICABLE" ? "rgba(40, 167, 69, 0.1)" : "rgba(0,0,0,0.05)",
                      color: r.result === "APPLICABLE" ? "#155724" : "#495057",
                      border: "1px solid rgba(0,0,0,0.08)",
                    }}
                  >
                    <strong>{r.requirement_identifier}</strong>: {r.requirement_title} ({r.result})
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* SECTION 2: Pinned Evidence Links */}
        <div
          data-testid="section-pinned-evidence"
          style={{
            padding: "0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--mw-border-color, #e0e0e0)",
            background: "rgba(0,0,0,0.01)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <h3 style={{ fontSize: "0.9rem", fontWeight: 700, margin: 0 }}>
              Pinned Evidence ({links.length})
            </h3>
            {links.length === 0 && (
              <span style={{ fontSize: "0.75rem", color: "#d9534f", fontWeight: 600 }}>
                Attention: No evidence pinned
              </span>
            )}
          </div>

          {links.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "#666", fontStyle: "italic", margin: 0 }}>
              No evidence links currently pinned to this control work item.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {links.map((link) => (
                <div
                  key={link.id}
                  data-testid={`evidence-link-row-${link.id}`}
                  style={{
                    padding: "0.5rem",
                    borderRadius: "4px",
                    border: "1px solid var(--mw-border-color, #e0e0e0)",
                    background: "#ffffff",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.4rem" }}>
                    <div>
                      <strong>{link.filename}</strong>
                      <span style={{ marginLeft: "0.4rem", fontSize: "0.75rem", color: "#666" }}>
                        (rev #{link.revision_number}, {link.classification})
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                      <span
                        data-testid={`link-validity-${link.id}`}
                        style={{
                          fontSize: "0.7rem",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                          fontWeight: 700,
                          background: link.validity === "AVAILABLE" ? "rgba(40, 167, 69, 0.1)" : "rgba(220, 53, 69, 0.1)",
                          color: link.validity === "AVAILABLE" ? "#155724" : "#721c24",
                        }}
                      >
                        {link.validity}
                      </span>
                      <span
                        data-testid={`link-review-${link.id}`}
                        style={{
                          fontSize: "0.7rem",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                          fontWeight: 700,
                          background: link.review === "ACCEPTED" ? "rgba(40, 167, 69, 0.1)" : "rgba(255, 149, 0, 0.1)",
                          color: link.review === "ACCEPTED" ? "#155724" : "#856404",
                        }}
                      >
                        {link.review}
                      </span>
                      <span
                        data-testid={`link-scan-${link.id}`}
                        style={{
                          fontSize: "0.7rem",
                          padding: "0.15rem 0.4rem",
                          borderRadius: "4px",
                          fontWeight: 700,
                          background: link.scan_status === "SCANNED_AT_LINK" ? "rgba(40, 167, 69, 0.1)" : "rgba(108, 117, 125, 0.1)",
                          color: link.scan_status === "SCANNED_AT_LINK" ? "#155724" : "#495057",
                        }}
                      >
                        {link.scan_status}
                      </span>
                    </div>
                  </div>

                  {link.rationale && (
                    <div style={{ fontSize: "0.8rem", color: "#555", marginTop: "0.25rem" }}>
                      Rationale: {link.rationale}
                    </div>
                  )}

                  {showTechnicalDetails && (
                    <div style={{ marginTop: "0.3rem", fontSize: "0.75rem", color: "#666" }}>
                      Digest: <code>{link.digest}</code>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* SECTION 3: Assessment Procedure & Latest Result */}
        <div
          data-testid="section-assessment-trace"
          style={{
            padding: "0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--mw-border-color, #e0e0e0)",
            background: "rgba(0,0,0,0.01)",
          }}
        >
          <h3 style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            Assessment & Verification Procedure
          </h3>

          {!assessment ? (
            <p style={{ fontSize: "0.85rem", color: "#666", fontStyle: "italic", margin: 0 }}>
              Assessment work item has not yet been loaded or initialized.
            </p>
          ) : (
            <div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.5rem", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                <div>
                  <span style={{ color: "#666" }}>Primary State: </span>
                  <strong data-testid="trace-primary-state">{assessment.primary_state}</strong>
                </div>
                <div>
                  <span style={{ color: "#666" }}>Latest Result: </span>
                  <strong data-testid="trace-latest-result">
                    {assessment.latest_assessment?.result || "UNASSESSED"}
                  </strong>
                </div>
                <div>
                  <span style={{ color: "#666" }}>Procedure Version: </span>
                  <code>{assessment.procedure.version}</code>
                </div>
              </div>

              {assessment.latest_assessment?.is_stale && (
                <div
                  role="alert"
                  data-testid="assessment-stale-warning"
                  className="mw-notice-banner"
                  style={{ borderColor: "#ff9500", background: "#fffdf5", color: "#856404", fontSize: "0.8rem", marginBottom: "0.5rem" }}
                >
                  <strong>Stale Assessment: </strong>
                  {assessment.latest_assessment.stale_reasons.join(", ") || "Control or evidence pins have changed since assessment."}
                </div>
              )}

              {showTechnicalDetails && (
                <div style={{ fontSize: "0.75rem", color: "#666", borderTop: "1px dashed var(--mw-border-color, #e0e0e0)", paddingTop: "0.4rem" }}>
                  <div>Procedure ID: <code>{assessment.procedure.id}</code></div>
                  <div>Procedure Digest: <code>{assessment.procedure.digest}</code></div>
                  {assessment.latest_assessment && (
                    <div>Event ID: <code>{assessment.latest_assessment.event_id}</code> (Rev #{assessment.latest_assessment.revision})</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* SECTION 4: Findings & Remediation History */}
        <div
          data-testid="section-findings-history"
          style={{
            padding: "0.75rem",
            borderRadius: "6px",
            border: "1px solid var(--mw-border-color, #e0e0e0)",
            background: "rgba(0,0,0,0.01)",
          }}
        >
          <h3 style={{ fontSize: "0.9rem", fontWeight: 700, marginBottom: "0.5rem" }}>
            Findings & History ({findings.length} findings, {history.length} events)
          </h3>

          {findings.length === 0 ? (
            <p style={{ fontSize: "0.85rem", color: "#666", fontStyle: "italic", margin: 0 }}>
              No open or recorded findings for this control.
            </p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginBottom: "0.75rem" }}>
              {findings.map((f) => (
                <div
                  key={f.id}
                  data-testid={`finding-item-${f.id}`}
                  style={{
                    padding: "0.4rem 0.6rem",
                    borderRadius: "4px",
                    border: "1px solid var(--mw-border-color, #e0e0e0)",
                    background: "#ffffff",
                    fontSize: "0.85rem",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "0.15rem 0.4rem",
                        borderRadius: "4px",
                        fontWeight: 700,
                        marginRight: "0.5rem",
                        background: f.severity === "CRITICAL" || f.severity === "HIGH" ? "rgba(220, 53, 69, 0.1)" : "rgba(255, 149, 0, 0.1)",
                        color: f.severity === "CRITICAL" || f.severity === "HIGH" ? "#721c24" : "#856404",
                      }}
                    >
                      {f.severity}
                    </span>
                    <strong>Status: {f.status}</strong>
                    {f.due_date && <span style={{ marginLeft: "0.5rem", color: "#666" }}>Due: {f.due_date}</span>}
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "#888" }}>v{f.version}</span>
                </div>
              ))}
            </div>
          )}

          {showTechnicalDetails && history.length > 0 && (
            <div style={{ marginTop: "0.5rem", borderTop: "1px dashed var(--mw-border-color, #e0e0e0)", paddingTop: "0.5rem" }}>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#666", marginBottom: "0.3rem" }}>
                Audit Event History
              </div>
              <div style={{ maxHeight: "150px", overflowY: "auto", fontSize: "0.75rem" }}>
                {history.map((evt) => (
                  <div key={evt.event_id} style={{ padding: "0.2rem 0", borderBottom: "1px dotted rgba(0,0,0,0.05)" }}>
                    <code>{evt.created_at}</code> | <strong>{evt.event_type}</strong> | Rev #{evt.revision} | Actor: {evt.actor_id}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
