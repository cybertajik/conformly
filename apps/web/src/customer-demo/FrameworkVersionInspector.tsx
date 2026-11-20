import React, { FC, useMemo, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { DemoPackRequirement, WorkspaceData } from "./types";
import "./modern-workspace.css";

export interface FrameworkVersionInspectorProps {
  workspace: WorkspaceData;
  selectedCandidateVersionId?: string;
  onSelectCandidateVersion?: (packVersionId: string) => void;
  userRole?: string;
}

export interface VersionPinDiff {
  identifier: string;
  title: string;
  currentReqVer: string;
  candidateReqVer: string;
  currentRuleVer: string;
  candidateRuleVer: string;
  currentCtrlVer: string;
  candidateCtrlVer: string;
  hasChangedPins: boolean;
}

export const FrameworkVersionInspector: FC<FrameworkVersionInspectorProps> = ({
  workspace,
  selectedCandidateVersionId,
  onSelectCandidateVersion,
}) => {
  const { t } = useTranslation();
  const manifest = workspace.manifest;
  const packs = useMemo(() => manifest?.packs || [], [manifest?.packs]);

  // Determine currently adopted pack. An unknown adopted version must NOT silently fall back to packs[0].
  const adoptedVersionId = workspace.selected_pack?.pack_version_id;
  const currentPack = useMemo(() => {
    if (adoptedVersionId) {
      return packs.find((p) => p.pack_version_id === adoptedVersionId) || null;
    }
    return packs[0] || null;
  }, [packs, adoptedVersionId]);

  const adoptedUnavailable = Boolean(adoptedVersionId && !currentPack);

  // Candidate pack for comparison (default to the other version of the same pack if available, or another pack)
  const defaultCandidate = useMemo(() => {
    if (!currentPack) return packs[0] || null;
    const samePackCandidate = packs.find(
      (p) => p.pack_id === currentPack.pack_id && p.pack_version_id !== currentPack.pack_version_id
    );
    if (samePackCandidate) return samePackCandidate;
    return packs.find((p) => p.pack_version_id !== currentPack.pack_version_id) || currentPack;
  }, [packs, currentPack]);

  const groupedPacks = useMemo(() => {
    const map = new Map<string, { pack_id: string; name: string; versions: typeof packs }>();
    for (const p of packs) {
      let g = map.get(p.pack_id);
      if (!g) {
        const baseName = p.name.replace(/ (Baseline|Extended|v[0-9.]+|Pack.*)$/i, "").trim() || p.name;
        g = { pack_id: p.pack_id, name: baseName, versions: [] };
        map.set(p.pack_id, g);
      }
      g.versions.push(p);
    }
    return Array.from(map.values());
  }, [packs]);

  const [internalCandidateVersionId, setInternalCandidateVersionId] = useState<string>("");

  const effectiveCandidateVersionId = selectedCandidateVersionId !== undefined
    ? selectedCandidateVersionId
    : (internalCandidateVersionId || defaultCandidate?.pack_version_id || "");

  const candidatePack = useMemo(() => {
    if (!effectiveCandidateVersionId) return null;
    return packs.find((p) => p.pack_version_id === effectiveCandidateVersionId) || null;
  }, [packs, effectiveCandidateVersionId]);

  const candidateUnavailable = Boolean(effectiveCandidateVersionId && !candidatePack);

  const handleCandidateChange = (newVersionId: string) => {
    setInternalCandidateVersionId(newVersionId);
    onSelectCandidateVersion?.(newVersionId);
  };

  // Compare requirements between current and candidate
  const comparison = useMemo(() => {
    if (!currentPack || !candidatePack) return null;

    const samePack = currentPack.pack_id === candidatePack.pack_id;
    const sameVersion = currentPack.pack_version_id === candidatePack.pack_version_id;
    const adoptedDigest = workspace.selected_pack?.bundle_digest;
    const hasAdoptionDigestDrift = Boolean(
      adoptedDigest &&
      currentPack.pack_version_id === workspace.selected_pack?.pack_version_id &&
      adoptedDigest !== currentPack.bundle_digest
    );
    const hasDigestDrift = Boolean(
      hasAdoptionDigestDrift ||
      (sameVersion && currentPack.bundle_digest !== candidatePack.bundle_digest)
    );

    if (!samePack) {
      return {
        samePack: false,
        sameVersion: false,
        hasDigestDrift: false,
        added: [],
        removed: [],
        unchanged: [],
        pinDiffs: [],
      };
    }

    const currentReqsMap = new Map<string, DemoPackRequirement>();
    for (const r of currentPack.requirements) {
      currentReqsMap.set(r.id, r);
    }

    const candidateReqsMap = new Map<string, DemoPackRequirement>();
    for (const r of candidatePack.requirements) {
      candidateReqsMap.set(r.id, r);
    }

    const added: DemoPackRequirement[] = [];
    const removed: DemoPackRequirement[] = [];
    const unchanged: DemoPackRequirement[] = [];
    const pinDiffs: VersionPinDiff[] = [];

    // Check candidate requirements against current
    for (const [id, candReq] of candidateReqsMap.entries()) {
      const curReq = currentReqsMap.get(id);
      if (!curReq) {
        added.push(candReq);
      } else {
        const reqVerChanged = curReq.version_id !== candReq.version_id;
        const ruleVerChanged = curReq.rule_version_id !== candReq.rule_version_id;
        const ctrlVerChanged = curReq.control_version_id !== candReq.control_version_id;
        const hasDiff = reqVerChanged || ruleVerChanged || ctrlVerChanged;

        if (hasDiff) {
          pinDiffs.push({
            identifier: candReq.identifier,
            title: candReq.title,
            currentReqVer: curReq.version_id,
            candidateReqVer: candReq.version_id,
            currentRuleVer: curReq.rule_version_id,
            candidateRuleVer: candReq.rule_version_id,
            currentCtrlVer: curReq.control_version_id,
            candidateCtrlVer: candReq.control_version_id,
            hasChangedPins: true,
          });
        } else {
          unchanged.push(candReq);
        }
      }
    }

    // Check for removed requirements
    for (const [id, curReq] of currentReqsMap.entries()) {
      if (!candidateReqsMap.has(id)) {
        removed.push(curReq);
      }
    }

    return {
      samePack: true,
      sameVersion,
      hasDigestDrift,
      added,
      removed,
      unchanged,
      pinDiffs,
    };
  }, [
    currentPack,
    candidatePack,
    workspace.selected_pack?.bundle_digest,
    workspace.selected_pack?.pack_version_id,
  ]);

  const isStale = Boolean(workspace.selected_pack?.is_stale);

  return (
    <section className="mw-card" data-testid="version-inspector" aria-labelledby="inspector-title" style={{ marginTop: "1.5rem" }}>
      <div className="mw-card-header">
        <h2 id="inspector-title" className="mw-card-title">
          {t("portal.versionInspectorTitle")}
        </h2>
        <p className="mw-card-subtitle">
          {t("portal.versionInspectorSubtitle")}
        </p>
      </div>

      <div className="mw-card-body">
        {/* Synthetic Non-Legal Notice */}
        <div className="mw-notice-banner" style={{ marginBottom: "1rem" }} role="note">
          <strong>Notice: </strong>
          Deterministic synthetic demonstration pack comparison. Non-legal guidance only.
        </div>

        {/* Adopted version unavailable notice */}
        {adoptedUnavailable && (
          <div
            role="alert"
            className="mw-notice-banner"
            data-testid="adopted-unavailable-notice"
            style={{ background: "#fff5f5", borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}
          >
            <strong>{t("portal.adoptedVersionUnavailable")}</strong>
            <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
              Adopted Pack Version ID: <code>{adoptedVersionId}</code>
            </div>
          </div>
        )}

        {/* Candidate version unavailable notice */}
        {candidateUnavailable && (
          <div
            role="alert"
            className="mw-notice-banner"
            data-testid="candidate-unavailable-notice"
            style={{ background: "#fff5f5", borderColor: "#dc3545", color: "#721c24", marginBottom: "1rem" }}
          >
            <strong>Candidate Version Unavailable: The selected candidate framework version is not present in the catalog manifest.</strong>
            <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
              Candidate Pack Version ID: <code>{effectiveCandidateVersionId}</code>
            </div>
          </div>
        )}

        {/* Stale Warning Banner if applicable */}
        {isStale && (
          <div className="mw-notice-banner" data-testid="stale-warning" style={{ background: "rgba(255, 149, 0, 0.1)", borderColor: "#ff9500", color: "#b36b00", marginBottom: "1rem" }}>
            <strong>Stale Adoption: </strong>
            Company profile facts have been modified since this framework version was adopted. Re-evaluation is required.
          </div>
        )}

        {/* Current vs Candidate Selector */}
        {!adoptedUnavailable && currentPack && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1rem", marginBottom: "1.25rem" }}>
            <div style={{ padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--mw-border-color)", background: "var(--mw-card-bg)" }}>
              <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "var(--mw-primary)", marginBottom: "0.25rem" }}>
                {t("portal.currentVersionBadge")}
              </div>
              <div style={{ fontWeight: 600, fontSize: "1rem" }}>
                {currentPack.name} (v{currentPack.version})
              </div>
              <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                Digest: <code style={{ fontSize: "0.75rem" }}>{currentPack.bundle_digest?.slice(0, 16)}...</code>
              </div>
              <div style={{ fontSize: "0.8rem", color: "#666" }}>
                Requirements: <strong>{currentPack.requirement_count || 0}</strong>
              </div>
            </div>

            <div style={{ padding: "0.75rem", borderRadius: "8px", border: "1px solid var(--mw-border-color)", background: "var(--mw-card-bg)" }}>
              <label htmlFor="candidate-version-select" style={{ display: "block", fontSize: "0.75rem", textTransform: "uppercase", fontWeight: 700, color: "#666", marginBottom: "0.25rem" }}>
                {t("portal.candidateVersionBadge")}
              </label>
              <select
                id="candidate-version-select"
                data-testid="candidate-version-select"
                className="mw-select"
                value={effectiveCandidateVersionId}
                onChange={(e) => handleCandidateChange(e.target.value)}
                style={{ width: "100%", marginBottom: "0.5rem" }}
              >
                {candidateUnavailable && (
                  <option value={effectiveCandidateVersionId} disabled>
                    {effectiveCandidateVersionId} [Unavailable Candidate]
                  </option>
                )}
                {groupedPacks.map((g) => (
                  <optgroup key={g.pack_id} label={g.name}>
                    {g.versions.map((p) => (
                      <option key={p.pack_version_id} value={p.pack_version_id}>
                        {p.name} (v{p.version}) - {p.pack_id}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <div style={{ fontSize: "0.8rem", color: "#666" }}>
                Digest: <code style={{ fontSize: "0.75rem" }}>{candidatePack?.bundle_digest?.slice(0, 16)}...</code>
              </div>
            </div>
          </div>
        )}

        {/* Cross-Pack Guard */}
        {comparison && !comparison.samePack && (
          <div
            role="status"
            className="mw-notice-banner"
            data-testid="cross-pack-notice"
            style={{ background: "#e8f4f8", borderColor: "#17a2b8", color: "#0c5460", marginBottom: "1.25rem" }}
          >
            <strong>{t("portal.crossPackComparisonNotice")}</strong>
            <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
              Current: <code>{currentPack?.pack_id}</code> &ne; Candidate: <code>{candidatePack?.pack_id}</code>
            </div>
            <p style={{ margin: "0.5rem 0 0", fontSize: "0.85rem", opacity: 0.95 }}>
              {t("portal.crossPackReplacementDisclaimer")}
            </p>
          </div>
        )}

        {/* Digest Drift Guard */}
        {comparison?.hasDigestDrift && (
          <div
            role="alert"
            className="mw-notice-banner"
            data-testid="inconsistent-digest-notice"
            style={{ background: "#fff5f5", borderColor: "#dc3545", color: "#721c24", marginBottom: "1.25rem" }}
          >
            <strong>{t("portal.inconsistentDigestNotice")}</strong>
            <div style={{ fontSize: "0.8rem", marginTop: "0.25rem" }}>
              Version: <code>{currentPack?.pack_version_id}</code> | Digest A: <code>{currentPack?.bundle_digest.slice(0, 16)}...</code> vs Digest B: <code>{candidatePack?.bundle_digest.slice(0, 16)}...</code>
            </div>
          </div>
        )}

        {/* Bundle Digest Comparison Bar */}
        {!adoptedUnavailable && currentPack && candidatePack && comparison?.samePack && !comparison.hasDigestDrift && (
          <div
            data-testid="bundle-digest-comparison"
            style={{
              padding: "0.75rem",
              borderRadius: "6px",
              background: "rgba(0, 0, 0, 0.03)",
              marginBottom: "1.25rem",
              fontSize: "0.85rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
              <span>
                <strong>{t("portal.bundleDigestLabel")}:</strong>
              </span>
              <span>
                {comparison.sameVersion
                  ? "Identical versions (0 diffs)"
                  : "Digests differ (Candidate contains distinct requirement set or rules)"}
              </span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "#666", marginTop: "0.25rem", wordBreak: "break-all" }}>
              Current: <code>{currentPack.bundle_digest}</code>
              <br />
              Candidate: <code>{candidatePack.bundle_digest}</code>
            </div>
          </div>
        )}

        {/* Diff Sections: Rendered only when same pack and no digest drift */}
        {comparison && comparison.samePack && !comparison.hasDigestDrift && (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Added Requirements */}
            <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid #c3e6cb", background: "#f8fff9" }}>
              <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#155724" }}>
                {t("portal.addedRequirements")} ({comparison.added.length})
              </h3>
              {comparison.added.length === 0 ? (
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#666" }}>None</p>
              ) : (
                <ul data-testid="added-requirements-list" style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
                  {comparison.added.map((r) => (
                    <li key={r.id}>
                      <strong>{r.identifier}</strong>: {r.title}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Removed Requirements */}
            <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid #f8d7da", background: "#fff9f9" }}>
              <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#721c24" }}>
                {t("portal.removedRequirements")} ({comparison.removed.length})
              </h3>
              {comparison.removed.length === 0 ? (
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#666" }}>None</p>
              ) : (
                <ul data-testid="removed-requirements-list" style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
                  {comparison.removed.map((r) => (
                    <li key={r.id}>
                      <strong>{r.identifier}</strong>: {r.title}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Changed Version Pins */}
            <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid #fff3cd", background: "#fffdf5" }}>
              <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#856404" }}>
                {t("portal.changedPins")} ({comparison.pinDiffs.length})
              </h3>
              {comparison.pinDiffs.length === 0 ? (
                <p style={{ margin: 0, fontSize: "0.85rem", color: "#666" }}>No changed pins in matching requirements</p>
              ) : (
                <ul data-testid="changed-pins-list" style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
                  {comparison.pinDiffs.map((d) => (
                    <li key={d.identifier}>
                      <strong>{d.identifier}</strong>: {d.title}
                      <div style={{ fontSize: "0.75rem", color: "#666", marginTop: "0.15rem" }}>
                        Rule pin: <code>{d.currentRuleVer.slice(0, 8)}</code> &rarr; <code>{d.candidateRuleVer.slice(0, 8)}</code> |
                        Control pin: <code>{d.currentCtrlVer.slice(0, 8)}</code> &rarr; <code>{d.candidateCtrlVer.slice(0, 8)}</code>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Unchanged Requirements */}
            <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid #e2e3e5", background: "#fdfdfd" }}>
              <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#383d41" }}>
                {t("portal.unchangedRequirements")} ({comparison.unchanged.length})
              </h3>
              <ul data-testid="unchanged-requirements-list" style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
                {comparison.unchanged.map((r) => (
                  <li key={r.id}>
                    <strong>{r.identifier}</strong>: {r.title}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {/* Preserved Immutable Adoption History */}
        <div style={{ marginTop: "1.5rem", borderTop: "1px solid var(--mw-border-color)", paddingTop: "1rem" }}>
          <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            {t("portal.adoptionHistoryTitle")}
          </h3>
          {(!workspace.history_summary || workspace.history_summary.length === 0) ? (
            <p style={{ fontSize: "0.85rem", color: "#666" }}>
              {t("portal.noAdoptionHistory")}
            </p>
          ) : (
            <div data-testid="adoption-history-list" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              {workspace.history_summary.map((h, idx) => (
                <div
                  key={`${h.selection_revision}-${idx}`}
                  style={{
                    padding: "0.5rem 0.75rem",
                    borderRadius: "6px",
                    background: "rgba(0,0,0,0.02)",
                    border: "1px solid var(--mw-border-color)",
                    fontSize: "0.85rem",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    flexWrap: "wrap",
                    gap: "0.5rem",
                  }}
                >
                  <div>
                    <strong>Rev {h.selection_revision}:</strong> Pack Version ID: <code>{h.pack_version_id.slice(0, 12)}...</code>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "#666" }}>
                    Digest: <code>{h.bundle_digest.slice(0, 10)}...</code> | {new Date(h.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
