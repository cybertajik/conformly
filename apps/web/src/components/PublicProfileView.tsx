import { useEffect, useState } from "react";
import type {
  PublicCredentialSummary,
  PublicProfileView as PublicProfileViewType,
} from "@conformly/shared";
import { getPublicProfile } from "../api";

interface PublicProfileViewProps {
  slug: string;
  initialData?: PublicProfileViewType;
  onBackToApp?: () => void;
}

export function PublicProfileView({
  slug,
  initialData,
  onBackToApp,
}: PublicProfileViewProps) {
  const [profile, setProfile] = useState<PublicProfileViewType | null>(
    initialData ?? null
  );
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<
    "all" | "conformly" | "third_party"
  >("all");
  const [selectedCredential, setSelectedCredential] =
    useState<PublicCredentialSummary | null>(null);

  useEffect(() => {
    if (initialData) return;
    let active = true;

    async function loadProfile() {
      try {
        const res = await getPublicProfile(slug);
        if (!active) return;
        if (res.data) {
          setProfile(res.data);
          setError(null);
        } else {
          setError("Compliance profile is currently unpublished or unavailable.");
        }
      } catch (err: unknown) {
        if (!active) return;
        setError(
          err instanceof Error
            ? err.message
            : "Compliance profile is currently unpublished or unavailable."
        );
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    void loadProfile();

    return () => {
      active = false;
    };
  }, [slug, initialData]);

  if (loading) {
    return (
      <div
        data-testid="trust-center-loading"
        className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 p-6"
      >
        <div className="text-center space-y-3">
          <div className="animate-spin w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full mx-auto" />
          <p className="text-slate-400 text-sm">
            Verifying compliance records and credentials...
          </p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div
        data-testid="trust-center-error"
        className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100 p-6"
      >
        <div className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center space-y-5 shadow-2xl">
          <div className="w-14 h-14 rounded-full bg-slate-800 border border-slate-700 text-slate-400 flex items-center justify-center mx-auto text-2xl font-bold">
            🔒
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Trust Center Unavailable
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            {error || "This organization has not published an active public compliance trust center."}
          </p>
          {onBackToApp && (
            <button
              onClick={onBackToApp}
              className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-sm font-medium text-white transition shadow-lg shadow-indigo-600/20"
            >
              Back to Workspace
            </button>
          )}
        </div>
      </div>
    );
  }

  const filteredCredentials = profile.credentials.filter((c) => {
    if (activeFilter === "conformly") return c.credential_type === "conformly_readiness";
    if (activeFilter === "third_party") return c.credential_type === "third_party";
    return true;
  });

  return (
    <div
      data-testid="trust-center-view"
      className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8 selection:bg-indigo-500 selection:text-white"
    >
      <div className="max-w-4xl w-full space-y-10">
        {/* Navigation / Header bar */}
        {onBackToApp && (
          <div className="flex justify-between items-center pb-2 border-b border-slate-800/80">
            <button
              onClick={onBackToApp}
              className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-indigo-400 transition"
            >
              ← Return to Conformly App
            </button>
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-800/80 text-slate-400 border border-slate-700/50">
              Live Public Trust Center
            </span>
          </div>
        )}

        {/* Company Branding & Hero */}
        <header className="bg-gradient-to-b from-slate-900/90 to-slate-900/40 border border-slate-800/80 rounded-2xl p-8 sm:p-10 backdrop-blur-md shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />
          <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-center justify-between relative z-10">
            <div className="flex items-center gap-5">
              {profile.logo_url ? (
                <img
                  src={profile.logo_url}
                  alt={`${profile.display_name} logo`}
                  className="w-20 h-20 rounded-2xl object-cover border-2 border-slate-700/60 shadow-md bg-slate-800"
                />
              ) : (
                <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-extrabold text-white shadow-lg shadow-indigo-500/20">
                  {profile.display_name.charAt(0).toUpperCase()}
                </div>
              )}
              <div>
                <div className="flex items-center gap-2.5 flex-wrap">
                  <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                    {profile.display_name}
                  </h1>
                  {profile.conformly_verified && (
                    <span
                      data-testid="conformly-verified-badge"
                      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold"
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      Verified Pre-Audit
                    </span>
                  )}
                </div>
                {profile.description && (
                  <p className="text-slate-400 text-sm mt-2 max-w-xl leading-relaxed">
                    {profile.description}
                  </p>
                )}
              </div>
            </div>

            {/* Links & Contact */}
            <div className="flex flex-col sm:items-end gap-2 text-xs text-slate-400 border-t sm:border-t-0 pt-4 sm:pt-0 border-slate-800/80 w-full sm:w-auto">
              {profile.website_url && (
                <a
                  href={profile.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 transition"
                >
                  🌐 {profile.website_url.replace(/^https?:\/\//, "")} ↗
                </a>
              )}
              {profile.primary_contact_email && (
                <a
                  href={`mailto:${profile.primary_contact_email}`}
                  className="inline-flex items-center gap-1.5 text-slate-300 hover:text-white transition"
                >
                  ✉️ {profile.primary_contact_email}
                </a>
              )}
              <span className="text-slate-500">
                Published {new Date(profile.published_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </header>

        {/* Regulatory & Disclaimer Banner */}
        <section
          data-testid="regulatory-disclaimer-banner"
          className="bg-amber-950/20 border border-amber-500/30 rounded-xl p-4 sm:p-5 flex items-start gap-4 text-amber-200/90 text-xs sm:text-sm leading-relaxed"
        >
          <div className="text-xl shrink-0 mt-0.5">ℹ️</div>
          <div>
            <strong className="text-amber-300 block font-semibold mb-1">
              Important Compliance Notice
            </strong>
            <p className="text-amber-200/80">{profile.disclaimer}</p>
          </div>
        </section>

        {/* Credentials & Certifications Grid */}
        <section className="space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Verified Credentials & Certifications
              </h2>
              <p className="text-slate-400 text-xs mt-1">
                Audited readiness assessments and third-party industry attestations.
              </p>
            </div>

            {/* Filter buttons */}
            <div className="inline-flex p-1 bg-slate-900 border border-slate-800 rounded-xl text-xs">
              <button
                onClick={() => setActiveFilter("all")}
                className={`px-3 py-1.5 rounded-lg transition font-medium ${
                  activeFilter === "all"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                All ({profile.credentials.length})
              </button>
              <button
                onClick={() => setActiveFilter("conformly")}
                className={`px-3 py-1.5 rounded-lg transition font-medium ${
                  activeFilter === "conformly"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                Conformly Badges
              </button>
              <button
                onClick={() => setActiveFilter("third_party")}
                className={`px-3 py-1.5 rounded-lg transition font-medium ${
                  activeFilter === "third_party"
                    ? "bg-indigo-600 text-white shadow"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                3rd-Party Certifications
              </button>
            </div>
          </div>

          {filteredCredentials.length === 0 ? (
            <div className="bg-slate-900/50 border border-dashed border-slate-800 rounded-xl p-10 text-center text-slate-500 text-sm">
              No credentials found for this category.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCredentials.map((cred) => {
                const isConformly = cred.credential_type === "conformly_readiness";
                return (
                  <article
                    key={cred.id}
                    data-testid={`credential-card-${cred.id}`}
                    className="bg-slate-900/70 border border-slate-800 hover:border-slate-700/80 rounded-xl p-6 transition flex flex-col justify-between space-y-4 hover:shadow-xl group"
                  >
                    <div className="space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg font-bold shadow ${
                              isConformly
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20"
                            }`}
                          >
                            {isConformly ? "🛡️" : "📜"}
                          </div>
                          <div>
                            <span
                              className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${
                                isConformly
                                  ? "bg-emerald-500/10 text-emerald-400"
                                  : "bg-indigo-500/10 text-indigo-400"
                              }`}
                            >
                              {isConformly ? "Conformly Readiness" : "3rd-Party Certification"}
                            </span>
                            <h3 className="text-base font-semibold text-white mt-1 group-hover:text-indigo-300 transition">
                              {cred.title}
                            </h3>
                          </div>
                        </div>
                        <span className="shrink-0 text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          Active
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        {cred.scope_description}
                      </p>
                    </div>

                    <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                      <div>
                        <span className="text-slate-500 block">Issuer</span>
                        <span className="text-slate-300 font-medium">{cred.issuer_name}</span>
                      </div>
                      <button
                        onClick={() => setSelectedCredential(cred)}
                        className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition font-medium"
                      >
                        Details →
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        {/* Public Statements & Compliance Commitments */}
        {profile.statements.length > 0 && (
          <section className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-white tracking-tight">
                Compliance Commitments & Policies
              </h2>
              <p className="text-slate-400 text-xs mt-1">
                Executive pledges and mandatory security baselines.
              </p>
            </div>

            <div className="space-y-4">
              {profile.statements.map((stmt) => (
                <div
                  key={stmt.id}
                  data-testid={`statement-card-${stmt.id}`}
                  className="bg-slate-900/60 border border-slate-800 rounded-xl p-6 space-y-2"
                >
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <span className="text-indigo-400">§</span> {stmt.title}
                  </h3>
                  <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                    {stmt.statement_content}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Footer */}
        <footer className="text-center pt-8 border-t border-slate-900 text-xs text-slate-500 space-y-2">
          <p>
            Powered by{" "}
            <a
              href="https://conformly.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-400 hover:text-white underline transition"
            >
              Conformly Compliance SaaS
            </a>{" "}
            • Pre-Audit Readiness & Compliance Operations
          </p>
          <p>
            Cryptographic verification and real-time audit readiness projection.
          </p>
        </footer>
      </div>

      {/* Credential Inspection Modal */}
      {selectedCredential && (
        <div
          data-testid="credential-detail-modal"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
        >
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 sm:p-8 space-y-6 shadow-2xl relative">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <span
                  className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full ${
                    selectedCredential.credential_type === "conformly_readiness"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "bg-indigo-500/10 text-indigo-400"
                  }`}
                >
                  {selectedCredential.credential_type === "conformly_readiness"
                    ? "Conformly Readiness Badge"
                    : "Third-Party Certification"}
                </span>
                <h3 className="text-xl font-bold text-white">
                  {selectedCredential.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedCredential(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="bg-slate-950/60 rounded-xl p-4 space-y-3 border border-slate-800/80">
                <div className="flex justify-between">
                  <span className="text-slate-500">Issuer:</span>
                  <span className="text-slate-200 font-semibold">
                    {selectedCredential.issuer_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Issued On:</span>
                  <span className="text-slate-200">
                    {new Date(selectedCredential.issued_at).toLocaleDateString()}
                  </span>
                </div>
                {selectedCredential.valid_until && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Valid Until:</span>
                    <span className="text-slate-200">
                      {new Date(selectedCredential.valid_until).toLocaleDateString()}
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Status:</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium">
                    Verified Active
                  </span>
                </div>
              </div>

              <div>
                <h4 className="text-slate-400 font-semibold mb-1">Scope & Details:</h4>
                <p className="text-slate-300 leading-relaxed bg-slate-950/40 p-3 rounded-lg border border-slate-800/50">
                  {selectedCredential.scope_description}
                </p>
              </div>

              {selectedCredential.verification_url && (
                <div className="pt-2">
                  <a
                    href={selectedCredential.verification_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition shadow-lg shadow-indigo-600/20"
                  >
                    Verify External Certificate ↗
                  </a>
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedCredential(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-medium transition"
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
