import { useCallback, useEffect, useState } from "react";
import type {
  PreAuditCertificateSummary,
  PublicProfileDetailSummary,
  TenantRole,
} from "@conformly/shared";
import {
  addTenantPublicCredential,
  addTenantPublicStatement,
  configureTenantPublicProfile,
  deleteTenantPublicCredential,
  deleteTenantPublicStatement,
  getTenantPublicProfile,
  linkPreAuditPublicCredential,
  listPreAudits,
  publishTenantPublicProfile,
  revokeTenantPublicCredential,
  unpublishTenantPublicProfile,
  updateTenantPublicCredential,
} from "../api";
import { canManagePublicProfile } from "../permissions";

interface PublicProfileWorkspaceProps {
  token: string;
  tenantId: string;
  role: TenantRole;
  onOpenPublicView?: (slug: string) => void;
}

export function PublicProfileWorkspace({
  token,
  tenantId,
  role,
  onOpenPublicView,
}: PublicProfileWorkspaceProps) {
  const isManager = canManagePublicProfile(role);

  const [profile, setProfile] = useState<PublicProfileDetailSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<
    "overview" | "branding" | "credentials" | "statements"
  >("overview");

  // Branding form state
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [slug, setSlug] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  // Modals state
  const [showThirdPartyModal, setShowThirdPartyModal] = useState(false);
  const [showPreAuditModal, setShowPreAuditModal] = useState(false);
  const [showRevokeModal, setShowRevokeModal] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState("");

  // Available pre-audit certificates
  const [availableCertificates, setAvailableCertificates] = useState<
    PreAuditCertificateSummary[]
  >([]);

  // Third party form
  const [tpTitle, setTpTitle] = useState("");
  const [tpIssuer, setTpIssuer] = useState("");
  const [tpScope, setTpScope] = useState("");
  const [tpIssuedAt, setTpIssuedAt] = useState(
    new Date().toISOString().split("T")[0]
  );
  const [tpValidUntil, setTpValidUntil] = useState("");
  const [tpVerificationUrl, setTpVerificationUrl] = useState("");

  // Statement form
  const [stTitle, setStTitle] = useState("");
  const [stContent, setStContent] = useState("");

  const refreshProfile = useCallback(async () => {
    try {
      setError(null);
      const data = await getTenantPublicProfile(token, tenantId);
      setProfile(data);
      setDisplayName(data.display_name);
      setDescription(data.description || "");
      setSlug(data.slug);
      setLogoUrl(data.logo_url || "");
      setWebsiteUrl(data.website_url || "");
      setContactEmail(data.primary_contact_email || "");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load public profile draft.");
    } finally {
      setLoading(false);
    }
  }, [token, tenantId]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await refreshProfile();
    }
    void init();
    return () => {
      active = false;
    };
  }, [refreshProfile]);

  // Load available pre-audit certificates when opening import modal
  const handleOpenPreAuditModal = async () => {
    setShowPreAuditModal(true);
    try {
      const audits = await listPreAudits(token, tenantId);
      const certs: PreAuditCertificateSummary[] = [];
      for (const pa of audits) {
        if (pa.certificates) {
          for (const c of pa.certificates) {
            if (c.status === "active") certs.push(c);
          }
        }
      }
      setAvailableCertificates(certs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load pre-audit certificates.");
    }
  };

  const handleSaveBranding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile || !isManager) return;
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const updated = await configureTenantPublicProfile(token, tenantId, {
        display_name: displayName.trim(),
        description: description.trim() || null,
        logo_url: logoUrl.trim() || null,
        website_url: websiteUrl.trim() || null,
        primary_contact_email: contactEmail.trim() || null,
        slug: slug.trim().toLowerCase() !== profile.slug ? slug.trim().toLowerCase() : null,
        expected_version: profile.version,
      });
      setProfile(updated);
      setSuccessMessage("Public profile configuration saved successfully.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save profile settings.");
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePublish = async () => {
    if (!profile || !isManager) return;
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      let updated: PublicProfileDetailSummary;
      if (profile.is_published) {
        updated = await unpublishTenantPublicProfile(token, tenantId, profile.version);
        setSuccessMessage("Profile unpublished. It is no longer visible publicly.");
      } else {
        updated = await publishTenantPublicProfile(token, tenantId, profile.version);
        setSuccessMessage("Profile published successfully to your public Trust Center!");
      }
      setProfile(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to change publication status.");
    } finally {
      setSaving(false);
    }
  };

  const handleAddThirdParty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile || !isManager) return;
    setSaving(true);
    setError(null);

    try {
      await addTenantPublicCredential(token, tenantId, {
        title: tpTitle.trim(),
        issuer_name: tpIssuer.trim(),
        scope_description: tpScope.trim(),
        issued_at: new Date(tpIssuedAt).toISOString(),
        valid_until: tpValidUntil ? new Date(tpValidUntil).toISOString() : null,
        verification_url: tpVerificationUrl.trim() || null,
        is_publicly_visible: true,
        display_order: profile.credentials.length,
      });
      setShowThirdPartyModal(false);
      setTpTitle("");
      setTpIssuer("");
      setTpScope("");
      setTpVerificationUrl("");
      setSuccessMessage("Third-party certification added.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add third-party certification.");
    } finally {
      setSaving(false);
    }
  };

  const handleLinkPreAudit = async (certId: string) => {
    if (!profile || !isManager) return;
    setSaving(true);
    setError(null);

    try {
      await linkPreAuditPublicCredential(token, tenantId, {
        certificate_id: certId,
        is_publicly_visible: true,
        display_order: profile.credentials.length,
      });
      setShowPreAuditModal(false);
      setSuccessMessage("Conformly Pre-Audit Readiness badge linked.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to link pre-audit certificate.");
    } finally {
      setSaving(false);
    }
  };

  const handleToggleVisibility = async (credId: string, currentVisible: boolean) => {
    if (!profile || !isManager) return;
    const cred = profile.credentials.find((c) => c.id === credId);
    if (!cred) return;

    try {
      await updateTenantPublicCredential(token, tenantId, credId, {
        title: cred.title,
        issuer_name: cred.issuer_name,
        scope_description: cred.scope_description,
        valid_until: cred.valid_until,
        verification_url: cred.verification_url,
        is_publicly_visible: !currentVisible,
        display_order: cred.display_order,
      });
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to toggle visibility.");
    }
  };

  const handleRevokeCredential = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!showRevokeModal || !revokeReason.trim() || !isManager) return;
    setSaving(true);
    setError(null);

    try {
      await revokeTenantPublicCredential(token, tenantId, showRevokeModal, revokeReason.trim());
      setShowRevokeModal(null);
      setRevokeReason("");
      setSuccessMessage("Credential revoked.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to revoke credential.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCredential = async (credId: string) => {
    if (!isManager) return;
    if (!window.confirm("Are you sure you want to permanently delete this credential from your public profile?")) {
      return;
    }

    try {
      await deleteTenantPublicCredential(token, tenantId, credId);
      setSuccessMessage("Credential deleted.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete credential.");
    }
  };

  const handleAddStatement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile || !isManager) return;
    setSaving(true);
    setError(null);

    try {
      await addTenantPublicStatement(token, tenantId, {
        title: stTitle.trim(),
        statement_content: stContent.trim(),
        display_order: profile.statements.length,
        is_publicly_visible: true,
      });
      setStTitle("");
      setStContent("");
      setSuccessMessage("Compliance pledge statement added.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add statement.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteStatement = async (statementId: string) => {
    if (!isManager) return;
    try {
      await deleteTenantPublicStatement(token, tenantId, statementId);
      setSuccessMessage("Statement removed.");
      await refreshProfile();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete statement.");
    }
  };

  if (loading) {
    return (
      <div data-testid="profile-workspace-loading" className="p-8 text-center text-slate-400">
        <div className="animate-spin w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full mx-auto mb-3" />
        Loading public profile configuration...
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="p-8 text-center text-rose-400">
        Unable to load public profile draft. {error}
      </div>
    );
  }

  const publicUrl = `/trust-center/${profile.slug}`;

  return (
    <div data-testid="profile-workspace" className="space-y-6">
      {/* Top Banner / Status Overview */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 flex flex-col md:flex-row items-start md:items-center justify-between gap-6 shadow-xl">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white tracking-tight">
              Public Compliance Trust Center
            </h2>
            <span
              data-testid="profile-status-badge"
              className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider flex items-center gap-1.5 ${
                profile.is_published
                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  profile.is_published ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
                }`}
              />
              {profile.is_published ? "Published (Live)" : "Draft (Unpublished)"}
            </span>
          </div>
          <p className="text-sm text-slate-400">
            Publish customer-facing audit readiness badges, ISO/SOC 2 certifications, and compliance commitments.
          </p>
          <div className="flex items-center gap-2 text-xs text-slate-400 pt-1 font-mono">
            <span>Public URL:</span>
            <span className="text-indigo-400">{publicUrl}</span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(window.location.origin + publicUrl);
                setSuccessMessage("Public Trust Center URL copied to clipboard.");
              }}
              className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-[11px] transition"
            >
              Copy Link
            </button>
          </div>
        </div>

        {/* Header Action Buttons */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          {profile.is_published && onOpenPublicView && (
            <button
              data-testid="view-live-trust-center-btn"
              onClick={() => onOpenPublicView(profile.slug)}
              className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-sm font-medium transition shadow"
            >
              View Live Trust Center ↗
            </button>
          )}

          {isManager && (
            <button
              data-testid="toggle-publish-btn"
              disabled={saving}
              onClick={handleTogglePublish}
              className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition shadow-lg flex items-center gap-2 ${
                profile.is_published
                  ? "bg-amber-600/80 hover:bg-amber-600 text-white shadow-amber-600/20"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/20"
              }`}
            >
              {saving
                ? "Processing..."
                : profile.is_published
                ? "Unpublish Profile"
                : "Publish Profile to Live"}
            </button>
          )}
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div data-testid="profile-workspace-error" className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-xl text-sm">
          {error}
        </div>
      )}
      {successMessage && (
        <div data-testid="profile-workspace-success" className="p-4 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 rounded-xl text-sm">
          {successMessage}
        </div>
      )}

      {/* Workspace Tabs */}
      <div className="flex border-b border-slate-800 gap-6 text-sm font-medium">
        <button
          data-testid="tab-overview"
          onClick={() => setActiveTab("overview")}
          className={`pb-3 transition relative ${
            activeTab === "overview"
              ? "text-indigo-400 border-b-2 border-indigo-400"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Trust Center Overview
        </button>
        <button
          data-testid="tab-credentials"
          onClick={() => setActiveTab("credentials")}
          className={`pb-3 transition relative ${
            activeTab === "credentials"
              ? "text-indigo-400 border-b-2 border-indigo-400"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Credentials & Badges ({profile.credentials.length})
        </button>
        <button
          data-testid="tab-statements"
          onClick={() => setActiveTab("statements")}
          className={`pb-3 transition relative ${
            activeTab === "statements"
              ? "text-indigo-400 border-b-2 border-indigo-400"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Compliance Commitments ({profile.statements.length})
        </button>
        <button
          data-testid="tab-branding"
          onClick={() => setActiveTab("branding")}
          className={`pb-3 transition relative ${
            activeTab === "branding"
              ? "text-indigo-400 border-b-2 border-indigo-400"
              : "text-slate-400 hover:text-white"
          }`}
        >
          Branding & Custom Slug
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
            <h3 className="text-base font-semibold text-white">Trust Center Summary</h3>
            <div className="space-y-2 text-xs text-slate-400">
              <div className="flex justify-between py-1 border-b border-slate-800/80">
                <span>Display Name:</span>
                <span className="text-white font-medium">{profile.display_name}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/80">
                <span>Custom URL Slug:</span>
                <span className="text-indigo-400 font-mono">/{profile.slug}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/80">
                <span>Credentials Displayed:</span>
                <span className="text-white font-medium">{profile.credentials.length}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/80">
                <span>Statements Published:</span>
                <span className="text-white font-medium">{profile.statements.length}</span>
              </div>
              <div className="flex justify-between py-1">
                <span>Version:</span>
                <span className="text-white font-mono">v{profile.version}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 md:col-span-2">
            <h3 className="text-base font-semibold text-white">Non-Accredited Notice & Disclaimer</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Every public profile published via Conformly automatically displays our required disclaimer to ensure compliance transparency:
            </p>
            <div className="p-4 bg-amber-950/20 border border-amber-500/30 rounded-xl text-amber-300 text-xs leading-relaxed">
              “Conformly is an audit-readiness and compliance operations platform, not an accredited certification body. Pre-audit certificates indicate verified readiness evaluation results.”
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: CREDENTIALS & BADGES */}
      {activeTab === "credentials" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h3 className="text-lg font-bold text-white">Compliance Credentials</h3>
              <p className="text-xs text-slate-400">
                Manage Conformly-evaluated readiness badges and verified third-party certificates.
              </p>
            </div>

            {isManager && (
              <div className="flex items-center gap-3">
                <button
                  data-testid="import-preaudit-badge-btn"
                  onClick={handleOpenPreAuditModal}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-emerald-600/20"
                >
                  + Link Conformly Pre-Audit Badge
                </button>
                <button
                  data-testid="add-third-party-cert-btn"
                  onClick={() => setShowThirdPartyModal(true)}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition shadow-lg shadow-indigo-600/20"
                >
                  + Add 3rd-Party Cert
                </button>
              </div>
            )}
          </div>

          {profile.credentials.length === 0 ? (
            <div className="p-12 text-center bg-slate-900 border border-dashed border-slate-800 rounded-2xl text-slate-500 text-sm">
              No credentials added yet. Link a Conformly Pre-Audit assessment badge or add your external ISO/SOC 2 certifications.
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
                  <tr>
                    <th className="py-3 px-4">Credential</th>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Issuer</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Visibility</th>
                    {isManager && <th className="py-3 px-4 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {profile.credentials.map((c) => (
                    <tr key={c.id} data-testid={`admin-cred-row-${c.id}`} className="hover:bg-slate-800/40 transition">
                      <td className="py-4 px-4 font-medium text-white">
                        <div>{c.title}</div>
                        {c.source_certificate_id && (
                          <span className="text-[10px] text-emerald-400 font-mono">
                            Conformly Pre-Audit Linked
                          </span>
                        )}
                      </td>
                      <td className="py-4 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            c.credential_type === "conformly_readiness"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : "bg-indigo-500/10 text-indigo-400"
                          }`}
                        >
                          {c.credential_type === "conformly_readiness" ? "Conformly Badge" : "3rd Party"}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-slate-400">{c.issuer_name}</td>
                      <td className="py-4 px-4">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                            c.status === "active"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : "bg-rose-500/10 text-rose-400"
                          }`}
                        >
                          {c.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        {isManager ? (
                          <button
                            data-testid={`toggle-visibility-${c.id}`}
                            onClick={() => handleToggleVisibility(c.id, c.is_publicly_visible)}
                            className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
                              c.is_publicly_visible
                                ? "bg-slate-800 text-slate-200 hover:bg-slate-700"
                                : "bg-slate-800/50 text-slate-500 hover:text-slate-300"
                            }`}
                          >
                            {c.is_publicly_visible ? "👁️ Visible" : "Hidden"}
                          </button>
                        ) : (
                          <span>{c.is_publicly_visible ? "Visible" : "Hidden"}</span>
                        )}
                      </td>
                      {isManager && (
                        <td className="py-4 px-4 text-right space-x-2">
                          {c.status === "active" && (
                            <button
                              data-testid={`revoke-cred-btn-${c.id}`}
                              onClick={() => setShowRevokeModal(c.id)}
                              className="px-2.5 py-1 bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 rounded transition text-[11px]"
                            >
                              Revoke
                            </button>
                          )}
                          <button
                            data-testid={`delete-cred-btn-${c.id}`}
                            onClick={() => handleDeleteCredential(c.id)}
                            className="px-2.5 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 rounded transition text-[11px]"
                          >
                            Delete
                          </button>
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

      {/* TAB 3: STATEMENTS & COMMITMENTS */}
      {activeTab === "statements" && (
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-bold text-white">Compliance Commitments</h3>
            <p className="text-xs text-slate-400">
              Publish executive security pledges, data protection policies, and compliance statements.
            </p>
          </div>

          {isManager && (
            <form onSubmit={handleAddStatement} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <h4 className="text-sm font-semibold text-white">Add New Commitment</h4>
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="Statement Title (e.g., Application-Layer Encryption Policy)"
                  value={stTitle}
                  onChange={(e) => setStTitle(e.target.value)}
                  required
                  className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <textarea
                  placeholder="Detailed commitment text..."
                  value={stContent}
                  onChange={(e) => setStContent(e.target.value)}
                  required
                  rows={3}
                  className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500"
                />
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={saving || !stTitle.trim() || !stContent.trim()}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition"
                  >
                    + Add Statement
                  </button>
                </div>
              </div>
            </form>
          )}

          <div className="space-y-4">
            {profile.statements.map((st) => (
              <div key={st.id} data-testid={`admin-statement-${st.id}`} className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex justify-between items-start gap-4">
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-white">{st.title}</h4>
                  <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                    {st.statement_content}
                  </p>
                </div>
                {isManager && (
                  <button
                    onClick={() => handleDeleteStatement(st.id)}
                    className="px-2.5 py-1 text-xs text-rose-400 hover:bg-rose-500/10 rounded transition shrink-0"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: BRANDING & CUSTOM SLUG */}
      {activeTab === "branding" && (
        <form onSubmit={handleSaveBranding} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 space-y-6 max-w-2xl">
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-white">Trust Center Branding</h3>
            <p className="text-xs text-slate-400">
              Customize how your organization appears to prospective customers and compliance auditors.
            </p>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <label className="block text-slate-400 font-medium mb-1">Company Display Name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                required
                disabled={!isManager}
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Custom Trust Center URL Slug</label>
              <div className="flex items-center">
                <span className="px-3 py-2.5 bg-slate-800 border border-r-0 border-slate-800 rounded-l-xl text-slate-500 text-xs font-mono">
                  /trust-center/
                </span>
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  required
                  disabled={!isManager}
                  className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-r-xl text-sm font-mono text-indigo-400 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                />
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Lowercase letters, numbers, and hyphens only (3-64 characters).
              </p>
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Company Summary / Mission</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                disabled={!isManager}
                className="w-full px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-400 font-medium mb-1">Logo URL (Optional)</label>
                <input
                  type="url"
                  placeholder="https://example.com/logo.png"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  disabled={!isManager}
                  className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-medium mb-1">Website URL</label>
                <input
                  type="url"
                  placeholder="https://example.com"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  disabled={!isManager}
                  className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-400 font-medium mb-1">Compliance Contact Email</label>
              <input
                type="email"
                placeholder="compliance@example.com"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                disabled={!isManager}
                className="w-full px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-white focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              />
            </div>
          </div>

          {isManager && (
            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                disabled={saving}
                className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-semibold transition shadow-lg shadow-indigo-600/20"
              >
                {saving ? "Saving Changes..." : "Save Settings"}
              </button>
            </div>
          )}
        </form>
      )}

      {/* MODAL 1: ADD THIRD-PARTY CERTIFICATION */}
      {showThirdPartyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <form onSubmit={handleAddThirdParty} className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-base font-bold text-white">Add Third-Party Certification</h3>
              <button type="button" onClick={() => setShowThirdPartyModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Certification Title</label>
                <input
                  type="text"
                  placeholder="e.g., ISO/IEC 27001:2022 Certification"
                  value={tpTitle}
                  onChange={(e) => setTpTitle(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Auditing Body / Issuer</label>
                <input
                  type="text"
                  placeholder="e.g., BSI Group, Schellman, Coalfire"
                  value={tpIssuer}
                  onChange={(e) => setTpIssuer(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Scope Description</label>
                <textarea
                  placeholder="Scope of systems, locations, and cloud services covered..."
                  value={tpScope}
                  onChange={(e) => setTpScope(e.target.value)}
                  required
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Issue Date</label>
                  <input
                    type="date"
                    value={tpIssuedAt}
                    onChange={(e) => setTpIssuedAt(e.target.value)}
                    required
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Expiration Date</label>
                  <input
                    type="date"
                    value={tpValidUntil}
                    onChange={(e) => setTpValidUntil(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">External Verification URL</label>
                <input
                  type="url"
                  placeholder="https://verify.issuer.com/..."
                  value={tpVerificationUrl}
                  onChange={(e) => setTpVerificationUrl(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>
            </div>
            <div className="pt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowThirdPartyModal(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
              >
                {saving ? "Adding..." : "Add Certification"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* MODAL 2: LINK CONFORMLY PRE-AUDIT BADGE */}
      {showPreAuditModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-base font-bold text-white">Import Conformly Pre-Audit Badge</h3>
              <button onClick={() => setShowPreAuditModal(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            <p className="text-xs text-slate-400">
              Select an active Pre-Audit certificate evaluated and issued by Conformly:
            </p>

            {availableCertificates.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-xs bg-slate-950 rounded-xl border border-slate-800">
                No active pre-audit certificates found. Run a pre-audit assessment in the Pre-Audit workspace first.
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {availableCertificates.map((c) => (
                  <div key={c.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex justify-between items-center gap-3">
                    <div className="text-xs">
                      <div className="text-white font-medium">{c.certificate_number}</div>
                      <div className="text-slate-500">
                        Issued {new Date(c.issued_at).toLocaleDateString()} • Expires {new Date(c.expires_at).toLocaleDateString()}
                      </div>
                    </div>
                    <button
                      onClick={() => handleLinkPreAudit(c.id)}
                      disabled={saving}
                      className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition"
                    >
                      Link Badge
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowPreAuditModal(false)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: REVOCATION REASON */}
      {showRevokeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <form onSubmit={handleRevokeCredential} className="bg-slate-900 border border-slate-800 rounded-2xl max-w-sm w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-white">Revoke Credential</h3>
            <p className="text-xs text-slate-400">
              Revoking a credential marks it as inactive. It will no longer appear on your public trust center.
            </p>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Reason for Revocation</label>
              <textarea
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                required
                rows={2}
                placeholder="e.g., Certificate superseded by recertification audit."
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowRevokeModal(null)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving || !revokeReason.trim()}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold"
              >
                Confirm Revoke
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
