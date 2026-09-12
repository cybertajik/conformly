import type {
  DeletionProofSummary,
  ExportJobSummary,
  ExportScope,
  TenantCancellationStatus,
  TenantRole,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  createExportJob,
  downloadExportArchive,
  getCancellationStatus,
  listDeletionProofs,
  listExportJobs,
  requestTenantCancellation,
  setLegalHold,
} from "../api";
import {
  canCancelTenant,
  canCreateExport,
  canManageRetention,
  canReadExport,
} from "../permissions";

interface Props {
  token: string;
  tenantId: string;
  tenantSlug: string;
  role: TenantRole;
}

export function DataLifecycleWorkspace({ token, tenantId, tenantSlug, role }: Props) {
  const [exports, setExports] = useState<ExportJobSummary[]>([]);
  const [proofs, setProofs] = useState<DeletionProofSummary[]>([]);
  const [status, setStatus] = useState<TenantCancellationStatus | null>(null);
  const [scope, setScope] = useState<ExportScope>("full");
  const [reason, setReason] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    setError("");
    try {
      const [nextExports, nextStatus, nextProofs] = await Promise.all([
        canReadExport(role) ? listExportJobs(token, tenantId) : Promise.resolve([]),
        getCancellationStatus(token, tenantId),
        listDeletionProofs(token, tenantId),
      ]);
      setExports(nextExports);
      setStatus(nextStatus);
      setProofs(nextProofs);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lifecycle data could not be loaded.");
    }
  }, [role, tenantId, token]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (active) await refresh();
    }
    void init();
    return () => {
      active = false;
    };
  }, [refresh]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The operation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function download(job: ExportJobSummary) {
    await run(async () => {
      const blob = await downloadExportArchive(token, tenantId, job.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `conformly-export-${job.id.slice(0, 8)}.zip`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("Encrypted export downloaded.");
    });
  }

  return (
    <section aria-labelledby="lifecycle-title">
      <h2 id="lifecycle-title">Data export and retention</h2>
      <p>Generate a tenant-scoped archive and manage the documented cancellation lifecycle.</p>
      {error && <div className="alert alert-error" role="alert">{error}</div>}
      {message && <div className="alert alert-success" role="status">{message}</div>}

      <article className="card">
        <h3>Tenant status</h3>
        <p>
          <span className="badge badge-info">{status?.status ?? "loading"}</span>{" "}
          {status?.is_export_window_active &&
            `${status.days_remaining_in_export_window ?? 0} days remain in the export window.`}
        </p>
        {status?.deletion_due_at && <p>Deletion due: {formatDate(status.deletion_due_at)}</p>}
        <p>Legal hold: {status?.legal_hold ? "active" : "not active"}</p>
        {canManageRetention(role) && (
          <button
            className="secondary"
            disabled={busy || !status}
            onClick={() => void run(async () => {
              const enabled = !status?.legal_hold;
              await setLegalHold(
                token,
                tenantId,
                enabled,
                enabled ? "Retention review initiated" : "Retention review completed",
              );
              setMessage(enabled ? "Legal hold enabled." : "Legal hold released.");
            })}
          >
            {status?.legal_hold ? "Release legal hold" : "Enable legal hold"}
          </button>
        )}
      </article>

      {canReadExport(role) && (
        <article className="card">
          <h3>Exports</h3>
          {canCreateExport(role) && (
            <div>
              <label htmlFor="export-scope">Export scope</label>
              <select id="export-scope" value={scope} onChange={(event) => setScope(event.target.value as ExportScope)}>
                <option value="full">Full tenant exit package</option>
                <option value="compliance_only">Compliance records</option>
                <option value="audit_only">Audit records</option>
              </select>
              <button disabled={busy} onClick={() => void run(async () => {
                await createExportJob(token, tenantId, scope);
                setMessage("Export generated.");
              })}>Generate export</button>
            </div>
          )}
          <div className="table-wrapper">
            <table className="data-table">
              <thead><tr><th>Created</th><th>Scope</th><th>Status</th><th>Records</th><th>Expires</th><th>Action</th></tr></thead>
              <tbody>
                {exports.map((job) => (
                  <tr key={job.id}>
                    <td>{formatDate(job.created_at)}</td><td>{job.scope.replaceAll("_", " ")}</td>
                    <td>{job.status}</td><td>{job.records_count}</td><td>{formatDate(job.expires_at)}</td>
                    <td><button className="secondary" disabled={busy || job.status !== "completed"} onClick={() => void download(job)}>Download</button></td>
                  </tr>
                ))}
                {exports.length === 0 && <tr><td colSpan={6}>No exports have been generated.</td></tr>}
              </tbody>
            </table>
          </div>
        </article>
      )}

      {canCancelTenant(role) && status?.status === "active" && (
        <article className="card">
          <h3>Cancel tenant</h3>
          <p>This starts a 30-day export window and schedules active-system deletion for day 90.</p>
          <label htmlFor="cancellation-reason">Reason</label>
          <textarea id="cancellation-reason" value={reason} onChange={(event) => setReason(event.target.value)} />
          <label htmlFor="tenant-confirmation">Type {tenantSlug} to confirm</label>
          <input id="tenant-confirmation" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
          <button className="danger" disabled={busy || reason.trim().length < 3 || confirmation !== tenantSlug} onClick={() => void run(async () => {
            await requestTenantCancellation(token, tenantId, { reason, confirm_slug: confirmation });
            setMessage("Cancellation scheduled. The export window is now open.");
          })}>Schedule cancellation</button>
        </article>
      )}

      {proofs.length > 0 && (
        <article className="card">
          <h3>Deletion evidence</h3>
          <ul>{proofs.map((proof) => <li key={proof.id}>{formatDate(proof.deleted_at)} — proof {proof.proof_manifest_sha256}</li>)}</ul>
        </article>
      )}
    </section>
  );
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}
