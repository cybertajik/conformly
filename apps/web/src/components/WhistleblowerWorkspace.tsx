import { useEffect, useState, useTransition } from "react";
import type {
  TenantContext,
  WhistleblowerCaseStatus,
  WhistleblowerCaseSummary,
  WhistleblowerPortalSummary,
} from "@conformly/shared";
import {
  addWhistleblowerHandlerMessage,
  assignWhistleblowerHandler,
  getTenantWhistleblowerPortal,
  getWhistleblowerCaseDetail,
  listWhistleblowerCases,
  setupOrUpdateWhistleblowerPortal,
  updateWhistleblowerCaseStatus,
} from "../api";
import {
  canManageWhistleblowerCases,
  canManageWhistleblowerPortal,
  canReadWhistleblowerCases,
} from "../permissions";

interface WhistleblowerWorkspaceProps {
  token: string;
  tenantContext: TenantContext;
  onOpenPublicPortal: (slug: string) => void;
}

export function WhistleblowerWorkspace({
  token,
  tenantContext,
  onOpenPublicPortal,
}: WhistleblowerWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<"cases" | "portal">("cases");
  const [, startTransition] = useTransition();

  // Portal State
  const [portal, setPortal] = useState<WhistleblowerPortalSummary | null>(null);
  const [portalSlug, setPortalSlug] = useState("");
  const [portalTitle, setPortalTitle] = useState("");
  const [portalWelcome, setPortalWelcome] = useState("");
  const [portalActive, setPortalActive] = useState(true);
  const [savingPortal, setSavingPortal] = useState(false);

  const canRead = canReadWhistleblowerCases(tenantContext.role);
  const canManage = canManageWhistleblowerCases(tenantContext.role);
  const canManagePortal = canManageWhistleblowerPortal(tenantContext.role);

  // Cases State
  const [cases, setCases] = useState<WhistleblowerCaseSummary[]>([]);
  const [totalCases, setTotalCases] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [loadingCases, setLoadingCases] = useState(canRead);

  // Selected Case Detail State
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<WhistleblowerCaseSummary | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [replyText, setReplyText] = useState("");
  const [sendingReply, setSendingReply] = useState(false);
  const [closedReason, setClosedReason] = useState("");
  const [showClosedReasonInput, setShowClosedReasonInput] = useState<"resolved" | "dismissed" | null>(null);

  // Handler Assignment
  const [assigneeId, setAssigneeId] = useState("");

  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load Portal on mount
  useEffect(() => {
    let active = true;
    if (!canRead) return;

    getTenantWhistleblowerPortal(token, tenantContext.tenant_id)
      .then((p) => {
        if (active && p) {
          setPortal(p);
          setPortalSlug(p.slug);
          setPortalTitle(p.title);
          setPortalWelcome(p.welcome_text);
          setPortalActive(p.is_active);
        }
      })
      .catch(() => {
        // Portal not configured yet is normal
      });

    return () => {
      active = false;
    };
  }, [token, tenantContext.tenant_id, canRead]);

  // Load Cases when filter changes
  useEffect(() => {
    let active = true;
    if (!canRead) return;

    const filterStatus =
      statusFilter !== "all" ? (statusFilter as WhistleblowerCaseStatus) : undefined;

    listWhistleblowerCases(token, tenantContext.tenant_id, { status: filterStatus })
      .then((res) => {
        if (active) {
          setCases(res.items);
          setTotalCases(res.total);
          setLoadingCases(false);
        }
      })
      .catch((err: Error) => {
        if (active) {
          setError(err.message || "Failed to load cases");
          setLoadingCases(false);
        }
      });

    return () => {
      active = false;
    };
  }, [token, tenantContext.tenant_id, statusFilter, canRead]);

  // Load selected case detail
  const loadCaseDetail = async (caseId: string) => {
    setSelectedCaseId(caseId);
    setLoadingDetail(true);
    setError(null);
    try {
      const detail = await getWhistleblowerCaseDetail(token, tenantContext.tenant_id, caseId);
      setSelectedCase(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load case detail");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSavePortal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManagePortal) return;
    setSavingPortal(true);
    setError(null);
    setSuccessMsg(null);
    try {
      const updated = await setupOrUpdateWhistleblowerPortal(token, tenantContext.tenant_id, {
        slug: portalSlug.trim(),
        title: portalTitle.trim(),
        welcome_text: portalWelcome.trim(),
        is_active: portalActive,
        expected_version: portal?.version,
      });
      setPortal(updated);
      setSuccessMsg("Whistleblower portal settings saved successfully.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save portal settings");
    } finally {
      setSavingPortal(false);
    }
  };

  const handleSendHandlerReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || !selectedCase || !replyText.trim()) return;
    setSendingReply(true);
    setError(null);
    try {
      await addWhistleblowerHandlerMessage(token, tenantContext.tenant_id, selectedCase.id, {
        body: replyText.trim(),
      });
      // Refresh detail
      const refreshed = await getWhistleblowerCaseDetail(
        token,
        tenantContext.tenant_id,
        selectedCase.id
      );
      setSelectedCase(refreshed);
      setReplyText("");
      // Refresh cases list
      const res = await listWhistleblowerCases(token, tenantContext.tenant_id);
      setCases(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send response to reporter");
    } finally {
      setSendingReply(false);
    }
  };

  const handleTransitionStatus = async (
    targetStatus: WhistleblowerCaseStatus,
    reason?: string
  ) => {
    if (!canManage || !selectedCase) return;
    setError(null);
    try {
      await updateWhistleblowerCaseStatus(token, tenantContext.tenant_id, selectedCase.id, {
        status: targetStatus,
        closed_reason: reason || null,
        expected_version: selectedCase.version,
      });
      setShowClosedReasonInput(null);
      setClosedReason("");
      const refreshed = await getWhistleblowerCaseDetail(
        token,
        tenantContext.tenant_id,
        selectedCase.id
      );
      setSelectedCase(refreshed);
      const res = await listWhistleblowerCases(token, tenantContext.tenant_id);
      setCases(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update case status");
    }
  };

  const handleAssignHandler = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManage || !selectedCase || !assigneeId) return;
    setError(null);
    try {
      await assignWhistleblowerHandler(token, tenantContext.tenant_id, selectedCase.id, {
        handler_user_id: assigneeId,
      });
      const refreshed = await getWhistleblowerCaseDetail(
        token,
        tenantContext.tenant_id,
        selectedCase.id
      );
      setSelectedCase(refreshed);
      setAssigneeId("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to assign handler");
    }
  };

  if (!canRead) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
        <h2 className="text-lg font-semibold text-slate-200">Whistleblower Module Restricted</h2>
        <p className="text-sm mt-1">
          Whistleblower reports are confidential. Only Owner, Administrator, and Compliance Manager
          roles are authorized to access case data.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Whistleblower & Ethics Channel
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
              Zero-Knowledge Intake
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Manage anonymous intake, encrypted two-way communications, and compliance triage.
          </p>
        </div>

        {portal?.slug && (
          <button
            onClick={() => onOpenPublicPortal(portal.slug)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 rounded-lg text-sm font-medium transition"
          >
            <span>🔗 Open Public Intake Portal</span>
          </button>
        )}
      </div>

      {/* Global Alerts */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-500/30 text-rose-200 text-sm px-4 py-3 rounded-lg flex justify-between items-center">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-rose-200">
            ✕
          </button>
        </div>
      )}

      {successMsg && (
        <div className="bg-emerald-950/40 border border-emerald-500/30 text-emerald-200 text-sm px-4 py-3 rounded-lg flex justify-between items-center">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-200">
            ✕
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-800 space-x-6 text-sm font-medium">
        <button
          onClick={() => {
            startTransition(() => {
              setActiveTab("cases");
              setSelectedCaseId(null);
            });
          }}
          className={`pb-3 transition border-b-2 ${
            activeTab === "cases"
              ? "border-indigo-500 text-indigo-400 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Case Investigations ({totalCases})
        </button>
        <button
          onClick={() => {
            startTransition(() => {
              setActiveTab("portal");
              setSelectedCaseId(null);
            });
          }}
          className={`pb-3 transition border-b-2 ${
            activeTab === "portal"
              ? "border-indigo-500 text-indigo-400 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Public Portal Settings
        </button>
      </div>

      {/* Portal Settings Tab */}
      {activeTab === "portal" && (
        <div className="max-w-2xl bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Public Intake Portal Configuration</h2>
            <p className="text-xs text-slate-400 mt-1">
              Configure the public link where employees and third parties can submit reports anonymously.
            </p>
          </div>

          <form onSubmit={handleSavePortal} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Portal URL Slug
              </label>
              <div className="flex items-center">
                <span className="bg-slate-950 border border-r-0 border-slate-700 rounded-l-lg px-3 py-2 text-sm text-slate-500 font-mono">
                  /public/whistleblower/
                </span>
                <input
                  required
                  type="text"
                  placeholder="acme-corp"
                  value={portalSlug}
                  onChange={(e) => setPortalSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-r-lg px-3 py-2 text-sm text-slate-100 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
              <p className="text-xs text-slate-500 mt-1">
                Lowercase letters, numbers, and hyphens only. Must be globally unique.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Portal Title
              </label>
              <input
                required
                type="text"
                placeholder="Acme Whistleblower & Ethics Line"
                value={portalTitle}
                onChange={(e) => setPortalTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Welcome / Intake Instructions
              </label>
              <textarea
                required
                rows={4}
                placeholder="Describe your commitment to privacy, anti-retaliation policies, and reporting guidelines..."
                value={portalWelcome}
                onChange={(e) => setPortalWelcome(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="portal_active_toggle"
                checked={portalActive}
                onChange={(e) => setPortalActive(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-950"
              />
              <label htmlFor="portal_active_toggle" className="text-sm text-slate-300">
                Portal is active and accepting public reports
              </label>
            </div>

            {canManagePortal && (
              <div className="pt-3">
                <button
                  type="submit"
                  disabled={savingPortal}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-semibold transition shadow-md"
                >
                  {savingPortal ? "Saving..." : "Save Portal Settings"}
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* Cases Tab */}
      {activeTab === "cases" && (
        <div className="space-y-6">
          {/* Filter Bar */}
          <div className="flex items-center gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Status Filter:
            </span>
            <div className="flex flex-wrap gap-2">
              {["all", "submitted", "acknowledged", "under_investigation", "resolved", "dismissed"].map(
                (st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium capitalize transition ${
                      statusFilter === st
                        ? "bg-indigo-600 text-white shadow-sm"
                        : "bg-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {st.replace("_", " ")}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Master-Detail Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left: Cases List Table */}
            <div className={`space-y-3 ${selectedCaseId ? "lg:col-span-5" : "lg:col-span-12"}`}>
              {loadingCases ? (
                <div className="p-8 text-center text-slate-400">Loading cases...</div>
              ) : cases.length === 0 ? (
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400">
                  <p className="text-sm font-medium text-slate-300">No whistleblower cases found</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {statusFilter !== "all"
                      ? `No cases match status "${statusFilter}".`
                      : "No reports have been submitted yet."}
                  </p>
                </div>
              ) : (
                <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950/60 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3">Case ID</th>
                        <th className="px-4 py-3">Subject / Title</th>
                        <th className="px-4 py-3">Status</th>
                        {!selectedCaseId && <th className="px-4 py-3">Submitted</th>}
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {cases.map((c) => (
                        <tr
                          key={c.id}
                          onClick={() => loadCaseDetail(c.id)}
                          className={`cursor-pointer transition hover:bg-slate-800/40 ${
                            selectedCaseId === c.id ? "bg-indigo-950/20" : ""
                          }`}
                        >
                          <td className="px-4 py-3 font-mono text-xs font-semibold text-indigo-400">
                            {c.public_case_id}
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-slate-200 truncate max-w-xs">
                              {c.title}
                            </div>
                            <div className="text-xs text-slate-500 capitalize">
                              {c.category.replace("_", " ")}
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase tracking-wider ${
                                c.status === "resolved"
                                  ? "bg-emerald-500/20 text-emerald-400"
                                  : c.status === "dismissed"
                                    ? "bg-slate-700 text-slate-300"
                                    : c.status === "under_investigation"
                                      ? "bg-indigo-500/20 text-indigo-400"
                                      : "bg-amber-500/20 text-amber-400"
                              }`}
                            >
                              {c.status.replace("_", " ")}
                            </span>
                          </td>
                          {!selectedCaseId && (
                            <td className="px-4 py-3 text-xs text-slate-400">
                              {new Date(c.created_at).toLocaleDateString()}
                            </td>
                          )}
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                loadCaseDetail(c.id);
                              }}
                              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                            >
                              Manage →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Right: Selected Case Detail Drawer */}
            {selectedCaseId && (
              <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6 shadow-xl sticky top-6">
                {loadingDetail || !selectedCase ? (
                  <div className="p-12 text-center text-slate-400">Loading case details...</div>
                ) : (
                  <>
                    {/* Header */}
                    <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-bold text-indigo-400">
                            {selectedCase.public_case_id}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${
                              selectedCase.status === "resolved"
                                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                : selectedCase.status === "dismissed"
                                  ? "bg-slate-700 text-slate-300"
                                  : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {selectedCase.status.replace("_", " ")}
                          </span>
                        </div>
                        <h2 className="text-xl font-bold text-white mt-1">{selectedCase.title}</h2>
                        <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
                          <span className="capitalize">
                            Category: {selectedCase.category.replace("_", " ")}
                          </span>
                          <span>•</span>
                          <span>Submitted {new Date(selectedCase.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => setSelectedCaseId(null)}
                        className="text-slate-400 hover:text-slate-200 text-sm"
                      >
                        ✕ Close
                      </button>
                    </div>

                    {/* Decrypted Summary */}
                    {selectedCase.summary && (
                      <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-2">
                        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                          Original Anonymous Report Summary
                        </div>
                        <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
                          {selectedCase.summary}
                        </p>
                      </div>
                    )}

                    {/* Two-way message thread */}
                    <div className="space-y-3">
                      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                        Encrypted Two-Way Conversation ({selectedCase.messages?.length || 0})
                      </div>
                      <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                        {selectedCase.messages?.map((msg) => (
                          <div
                            key={msg.id}
                            className={`p-3.5 rounded-lg text-sm leading-relaxed ${
                              msg.sender_type === "reporter"
                                ? "bg-slate-800/90 border border-slate-700 mr-4"
                                : "bg-indigo-950/40 border border-indigo-500/30 ml-4"
                            }`}
                          >
                            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
                              <span
                                className={`font-semibold ${
                                  msg.sender_type === "reporter"
                                    ? "text-emerald-400"
                                    : "text-indigo-300"
                                }`}
                              >
                                {msg.sender_type === "reporter"
                                  ? "Anonymous Reporter"
                                  : "Compliance Team"}
                              </span>
                              <span>{new Date(msg.created_at).toLocaleTimeString()}</span>
                            </div>
                            <div className="text-slate-200 whitespace-pre-wrap">{msg.body}</div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Handler Actions: Send Message */}
                    {canManage &&
                      selectedCase.status !== "resolved" &&
                      selectedCase.status !== "dismissed" && (
                        <form onSubmit={handleSendHandlerReply} className="space-y-2 pt-2 border-t border-slate-800">
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider">
                            Reply to Anonymous Reporter
                          </label>
                          <textarea
                            rows={3}
                            placeholder="Message will be encrypted and visible when the reporter checks their case key..."
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-slate-500">
                              Replying auto-acknowledges submitted cases.
                            </span>
                            <button
                              type="submit"
                              disabled={sendingReply || !replyText.trim()}
                              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold transition"
                            >
                              {sendingReply ? "Sending..." : "Send Reply"}
                            </button>
                          </div>
                        </form>
                      )}

                    {/* Status Transitions */}
                    {canManage && (
                      <div className="pt-4 border-t border-slate-800 space-y-3">
                        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                          Lifecycle Status Actions
                        </div>

                        {showClosedReasonInput ? (
                          <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-3">
                            <label className="block text-xs font-medium text-slate-300">
                              Reason / Resolution Summary for {showClosedReasonInput}:
                            </label>
                            <textarea
                              rows={2}
                              value={closedReason}
                              onChange={(e) => setClosedReason(e.target.value)}
                              placeholder="Document actions taken or justification..."
                              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() =>
                                  handleTransitionStatus(
                                    showClosedReasonInput === "resolved"
                                      ? "resolved"
                                      : "dismissed",
                                    closedReason
                                  )
                                }
                                className={`px-3 py-1.5 rounded text-xs font-semibold text-white ${
                                  showClosedReasonInput === "resolved"
                                    ? "bg-emerald-600 hover:bg-emerald-500"
                                    : "bg-slate-700 hover:bg-slate-600"
                                }`}
                              >
                                Confirm {showClosedReasonInput}
                              </button>
                              <button
                                onClick={() => {
                                  setShowClosedReasonInput(null);
                                  setClosedReason("");
                                }}
                                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex flex-wrap gap-2">
                            {selectedCase.status === "submitted" && (
                              <button
                                onClick={() => handleTransitionStatus("acknowledged")}
                                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition"
                              >
                                Mark Acknowledged
                              </button>
                            )}

                            {(selectedCase.status === "submitted" ||
                              selectedCase.status === "acknowledged") && (
                              <button
                                onClick={() => handleTransitionStatus("under_investigation")}
                                className="px-3 py-1.5 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded-lg text-xs font-medium transition"
                              >
                                Start Investigation
                              </button>
                            )}

                            {selectedCase.status !== "resolved" &&
                              selectedCase.status !== "dismissed" && (
                                <>
                                  <button
                                    onClick={() => setShowClosedReasonInput("resolved")}
                                    className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-medium transition"
                                  >
                                    Resolve Case
                                  </button>
                                  <button
                                    onClick={() => setShowClosedReasonInput("dismissed")}
                                    className="px-3 py-1.5 bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/40 rounded-lg text-xs font-medium transition"
                                  >
                                    Dismiss Case
                                  </button>
                                </>
                              )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Handler Assignment Section */}
                    {canManage && (
                      <div className="pt-4 border-t border-slate-800 space-y-3">
                        <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                          Assigned Investigators
                        </div>
                        {selectedCase.assignments && selectedCase.assignments.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {selectedCase.assignments.map((a) => (
                              <span
                                key={a.id}
                                className="inline-flex items-center gap-1.5 px-3 py-1 bg-slate-800 text-slate-300 rounded-lg text-xs font-mono"
                              >
                                👤 {a.handler_user_id}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-slate-500">No handlers assigned yet.</p>
                        )}

                        <form onSubmit={handleAssignHandler} className="flex gap-2 pt-1">
                          <input
                            type="text"
                            placeholder="Handler User ID (UUID)..."
                            value={assigneeId}
                            onChange={(e) => setAssigneeId(e.target.value)}
                            className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono"
                          />
                          <button
                            type="submit"
                            disabled={!assigneeId.trim()}
                            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 rounded-lg text-xs font-medium transition"
                          >
                            Assign
                          </button>
                        </form>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
