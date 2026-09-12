import { useEffect, useState } from "react";
import type {
  WhistleblowerPortalSummary,
  WhistleblowerPublicCaseSummary,
  WhistleblowerSubmissionResult,
} from "@conformly/shared";
import {
  accessWhistleblowerCasePublic,
  addWhistleblowerReporterMessage,
  getPublicWhistleblowerPortal,
  submitWhistleblowerReport,
} from "../api";

interface WhistleblowerPublicPortalProps {
  slug: string;
  onBackToApp?: () => void;
}

const CATEGORIES = [
  { value: "fraud", label: "Financial Fraud & Theft" },
  { value: "harassment", label: "Harassment & Discrimination" },
  { value: "safety", label: "Workplace Health & Safety" },
  { value: "bribery", label: "Bribery & Corruption" },
  { value: "data_privacy", label: "Data Privacy & Security Violation" },
  { value: "other", label: "Other Serious Concern" },
];

export function WhistleblowerPublicPortal({
  slug,
  onBackToApp,
}: WhistleblowerPublicPortalProps) {
  const [activeTab, setActiveTab] = useState<"submit" | "track">("submit");
  const [portal, setPortal] = useState<WhistleblowerPortalSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Submit form state
  const [category, setCategory] = useState("fraud");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submissionResult, setSubmissionResult] =
    useState<WhistleblowerSubmissionResult | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);

  // Track form state
  const [trackCaseId, setTrackCaseId] = useState("");
  const [trackSecret, setTrackSecret] = useState("");
  const [tracking, setTracking] = useState(false);
  const [caseView, setCaseView] = useState<WhistleblowerPublicCaseSummary | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [sendingReply, setSendingReply] = useState(false);

  useEffect(() => {
    let active = true;
    getPublicWhistleblowerPortal(slug)
      .then((data) => {
        if (active) {
          setPortal(data);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message || "Failed to load reporting portal.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [slug]);

  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !summary.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await submitWhistleblowerReport(slug, {
        category,
        title: title.trim(),
        summary: summary.trim(),
      });
      setSubmissionResult(res);
      setTitle("");
      setSummary("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to submit report.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleAccessCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!trackCaseId.trim() || !trackSecret.trim()) return;
    setTracking(true);
    setError(null);
    try {
      const res = await accessWhistleblowerCasePublic(slug, {
        public_case_id: trackCaseId.trim(),
        return_secret: trackSecret.trim(),
      });
      setCaseView(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Invalid Case ID or Return Secret.");
    } finally {
      setTracking(false);
    }
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyBody.trim() || !trackCaseId || !trackSecret) return;
    setSendingReply(true);
    setError(null);
    try {
      await addWhistleblowerReporterMessage(slug, {
        public_case_id: trackCaseId.trim(),
        return_secret: trackSecret.trim(),
        body: replyBody.trim(),
      });
      // Refresh case thread
      const updated = await accessWhistleblowerCasePublic(slug, {
        public_case_id: trackCaseId.trim(),
        return_secret: trackSecret.trim(),
      });
      setCaseView(updated);
      setReplyBody("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send follow-up message.");
    } finally {
      setSendingReply(false);
    }
  };

  const copySecretToClipboard = () => {
    if (!submissionResult) return;
    navigator.clipboard.writeText(submissionResult.return_secret).then(() => {
      setCopiedSecret(true);
      setTimeout(() => setCopiedSecret(false), 3000);
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-slate-100 p-6">
        <div className="text-center space-y-3">
          <div className="animate-spin w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full mx-auto" />
          <p className="text-slate-400 text-sm">Loading secure anonymous portal...</p>
        </div>
      </div>
    );
  }

  if (error && !portal) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 text-slate-100 p-6">
        <div className="max-w-md w-full bg-slate-800 border border-rose-500/30 rounded-xl p-8 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto text-xl font-bold">
            !
          </div>
          <h2 className="text-xl font-semibold text-white">Portal Unavailable</h2>
          <p className="text-sm text-slate-400">{error}</p>
          {onBackToApp && (
            <button
              onClick={onBackToApp}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-slate-200 transition"
            >
              Return to Workspace
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center py-10 px-4 sm:px-6">
      <div className="max-w-2xl w-full space-y-8">
        {/* Header with anonymity guarantees */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            100% Anonymous • Zero Identity Tracking
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            {portal?.title || "Whistleblower Reporting Channel"}
          </h1>
          <p className="text-slate-400 text-sm max-w-lg mx-auto leading-relaxed">
            {portal?.welcome_text ||
              "Your report is protected with application-layer encryption. We do not track IP addresses, browser fingerprints, or cookies."}
          </p>
          {onBackToApp && (
            <div className="pt-2">
              <button
                onClick={onBackToApp}
                className="text-xs text-indigo-400 hover:text-indigo-300 underline transition"
              >
                ← Return to Internal Workspace
              </button>
            </div>
          )}
        </div>

        {/* Global Error Banner */}
        {error && (
          <div className="bg-rose-950/40 border border-rose-500/30 text-rose-200 text-sm px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {/* Successful Submission View */}
        {submissionResult ? (
          <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-8 space-y-6 shadow-2xl">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 text-emerald-400 flex items-center justify-center text-2xl mx-auto">
              ✓
            </div>
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-bold text-white">Report Successfully Submitted</h2>
              <p className="text-slate-400 text-sm">
                Your report has been encrypted and securely delivered to the compliance committee.
              </p>
            </div>

            <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Public Case ID
                </label>
                <div className="text-xl font-mono font-bold text-emerald-400 mt-1">
                  {submissionResult.public_case_id}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Secret Return Key
                </label>
                <div className="flex items-center gap-2 mt-1">
                  <input
                    readOnly
                    value={submissionResult.return_secret}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-amber-300 selection:bg-amber-500/30"
                  />
                  <button
                    onClick={copySecretToClipboard}
                    className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition whitespace-nowrap"
                  >
                    {copiedSecret ? "Copied!" : "Copy Key"}
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-amber-950/30 border border-amber-500/30 rounded-lg p-4 text-xs text-amber-200 space-y-1">
              <p className="font-semibold">⚠️ CRITICAL: Save your Secret Return Key now</p>
              <p className="text-amber-300/80">
                To protect your identity, this secret is hashed with a salted one-way function. It is
                never stored in plaintext on any server and cannot be recovered if lost. You will need
                both your Case ID and this Secret to check for replies.
              </p>
            </div>

            <div className="flex gap-3 justify-center pt-2">
              <button
                onClick={() => {
                  setTrackCaseId(submissionResult.public_case_id);
                  setTrackSecret(submissionResult.return_secret);
                  setSubmissionResult(null);
                  setActiveTab("track");
                }}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition shadow-md"
              >
                Track This Report
              </button>
              <button
                onClick={() => setSubmissionResult(null)}
                className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-semibold transition"
              >
                Submit Another Report
              </button>
            </div>
          </div>
        ) : (
          /* Tab Navigation & Form Panels */
          <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden">
            <div className="grid grid-cols-2 border-b border-slate-800 text-center font-medium text-sm">
              <button
                type="button"
                onClick={() => setActiveTab("submit")}
                className={`py-4 transition border-b-2 ${
                  activeTab === "submit"
                    ? "border-emerald-500 text-emerald-400 bg-slate-800/40 font-semibold"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                Submit Anonymous Report
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("track")}
                className={`py-4 transition border-b-2 ${
                  activeTab === "track"
                    ? "border-emerald-500 text-emerald-400 bg-slate-800/40 font-semibold"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                Track Existing Report
              </button>
            </div>

            <div className="p-6 sm:p-8">
              {activeTab === "submit" ? (
                /* Submit Report Form */
                <form onSubmit={handleSubmitReport} className="space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Report Category
                    </label>
                    <select
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    >
                      {CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>
                          {cat.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Report Subject / Title
                    </label>
                    <input
                      required
                      type="text"
                      placeholder="Concise overview of the concern"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-2">
                      Detailed Summary & Evidence
                    </label>
                    <textarea
                      required
                      rows={6}
                      placeholder="Provide specific dates, departments, names, or transaction details. Do not include your personal identity if you wish to remain anonymous."
                      value={summary}
                      onChange={(e) => setSummary(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 leading-relaxed"
                    />
                  </div>

                  <div className="pt-2">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg font-semibold text-sm transition shadow-lg flex items-center justify-center gap-2"
                    >
                      {submitting ? (
                        <>
                          <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                          Encrypting & Submitting...
                        </>
                      ) : (
                        "Submit Report Anonymously"
                      )}
                    </button>
                  </div>
                </form>
              ) : (
                /* Track Report Form & Message Thread */
                <div className="space-y-6">
                  {!caseView ? (
                    <form onSubmit={handleAccessCase} className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Public Case ID
                        </label>
                        <input
                          required
                          type="text"
                          placeholder="e.g. WB-2026-A1B2C3"
                          value={trackCaseId}
                          onChange={(e) => setTrackCaseId(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-300 mb-2">
                          Secret Return Key
                        </label>
                        <input
                          required
                          type="password"
                          placeholder="wb_..."
                          value={trackSecret}
                          onChange={(e) => setTrackSecret(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={tracking}
                        className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg font-semibold text-sm transition shadow-lg"
                      >
                        {tracking ? "Verifying Credentials..." : "Access Case"}
                      </button>
                    </form>
                  ) : (
                    /* Active Case View & Secure Messaging */
                    <div className="space-y-6">
                      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                        <div>
                          <div className="text-xs font-mono text-slate-400">
                            {caseView.public_case_id}
                          </div>
                          <h2 className="text-lg font-bold text-white mt-0.5">
                            {caseView.title}
                          </h2>
                          <div className="text-xs text-slate-400 mt-1 capitalize">
                            Category: {caseView.category.replace("_", " ")}
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <span
                            className={`px-2.5 py-1 rounded-full text-xs font-medium uppercase tracking-wider ${
                              caseView.status === "resolved"
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : caseView.status === "dismissed"
                                  ? "bg-slate-700 text-slate-300"
                                  : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {caseView.status.replace("_", " ")}
                          </span>
                          <button
                            onClick={() => setCaseView(null)}
                            className="text-xs text-slate-400 hover:text-slate-200 underline"
                          >
                            Sign Out of Case
                          </button>
                        </div>
                      </div>

                      {/* Conversation thread */}
                      <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
                        {caseView.messages.map((m) => (
                          <div
                            key={m.id}
                            className={`p-4 rounded-xl text-sm leading-relaxed ${
                              m.sender_type === "reporter"
                                ? "bg-slate-800/80 border border-slate-700 ml-6"
                                : "bg-indigo-950/40 border border-indigo-500/30 mr-6"
                            }`}
                          >
                            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                              <span
                                className={`font-semibold ${
                                  m.sender_type === "reporter"
                                    ? "text-emerald-400"
                                    : "text-indigo-300"
                                }`}
                              >
                                {m.sender_type === "reporter"
                                  ? "Anonymous Reporter"
                                  : "Compliance Committee"}
                              </span>
                              <span>{new Date(m.created_at).toLocaleString()}</span>
                            </div>
                            <div className="text-slate-200 whitespace-pre-wrap">{m.body}</div>
                          </div>
                        ))}
                      </div>

                      {/* Reply Box (if not closed) */}
                      {caseView.status !== "resolved" && caseView.status !== "dismissed" ? (
                        <form onSubmit={handleSendReply} className="space-y-3 pt-2">
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                            Post Follow-Up Message
                          </label>
                          <textarea
                            required
                            rows={3}
                            placeholder="Add additional facts, clarify questions, or reply to compliance committee..."
                            value={replyBody}
                            onChange={(e) => setReplyBody(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <button
                            type="submit"
                            disabled={sendingReply}
                            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-semibold transition"
                          >
                            {sendingReply ? "Sending..." : "Send Message"}
                          </button>
                        </form>
                      ) : (
                        <div className="bg-slate-950 border border-slate-800 p-4 rounded-lg text-center text-xs text-slate-400">
                          This case has been closed ({caseView.status}). New messages can no longer
                          be posted to this thread.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
