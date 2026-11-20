import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { ForbiddenError, UnauthorizedError } from "./api";
import { fetchFailedJobs, fetchOutboxMessages } from "./task-api";
import { FailedJobItem, OutboxMessageResponse } from "./task-types";
import "./modern-workspace.css";

export interface JobStatusPanelProps {
  tenantId: string;
  token: string;
  userRole?: string;
  onSessionExpired?: () => void;
}

const PAGE_SIZE = 10;

export const JobStatusPanel: React.FC<JobStatusPanelProps> = ({
  tenantId,
  token,
  userRole,
  onSessionExpired,
}) => {
  const { t } = useTranslation();

  // Authoritative role check: Owner, Administrator, Compliance Manager
  const isAuthorized = Boolean(
    userRole === "owner" ||
    userRole === "administrator" ||
    userRole === "compliance_manager"
  );

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDenied, setIsDenied] = useState<boolean>(!isAuthorized);

  const [failedCount, setFailedCount] = useState<number>(0);
  const [recentFailures, setRecentFailures] = useState<FailedJobItem[]>([]);

  const [outboxItems, setOutboxItems] = useState<OutboxMessageResponse[]>([]);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [outboxOffset, setOutboxOffset] = useState<number>(0);
  const [selectedStateFilter, setSelectedStateFilter] = useState<string>("all");

  const abortControllerRef = useRef<AbortController | null>(null);
  const requestGenRef = useRef<number>(0);

  const loadJobData = useCallback(async () => {
    if (!isAuthorized) {
      setIsDenied(true);
      setLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    const currentGen = ++requestGenRef.current;

    setLoading(true);
    setError(null);

    try {
      const outboxQuery = {
        state: selectedStateFilter !== "all" ? (selectedStateFilter as "pending" | "processing" | "delivered" | "failed") : undefined,
        limit: PAGE_SIZE,
        offset: outboxOffset,
      };

      const [failedRes, outboxRes] = await Promise.all([
        fetchFailedJobs(tenantId, token, abortController.signal),
        fetchOutboxMessages(tenantId, token, outboxQuery, abortController.signal),
      ]);

      if (currentGen !== requestGenRef.current) return;

      setFailedCount(failedRes.total_failed);
      setRecentFailures(failedRes.recent_failures || []);
      const items = outboxRes || [];
      setOutboxItems(items);
      setHasMore(items.length === PAGE_SIZE);
      setIsDenied(false);
    } catch (err: unknown) {
      if (currentGen !== requestGenRef.current) return;
      if (abortController.signal.aborted) return;

      if (err instanceof UnauthorizedError) {
        onSessionExpired?.();
        return;
      }
      if (err instanceof ForbiddenError) {
        setIsDenied(true);
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load job status");
    } finally {
      if (currentGen === requestGenRef.current) {
        setLoading(false);
      }
    }
  }, [tenantId, token, isAuthorized, selectedStateFilter, outboxOffset, onSessionExpired]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadJobData();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadJobData]);

  const formatUtcDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    const d = new Date(dateStr);
    return `${d.toISOString().replace("T", " ").substring(0, 19)} UTC`;
  };

  if (isDenied) {
    return (
      <div className="mw-card" data-testid="job-status-denied">
        <div className="mw-notice-banner error" role="alert">
          {t("portal.operationsDeniedNotice") ||
            "Access denied: viewing background job status requires Owner, Administrator, or Compliance Manager role."}
        </div>
      </div>
    );
  }

  const currentPage = Math.floor(outboxOffset / PAGE_SIZE) + 1;

  return (
    <div className="mw-operations-jobs" data-testid="job-status-panel">
      {/* Header */}
      <div className="mw-card-header" style={{ marginBottom: "1rem" }}>
        <div>
          <h3 className="mw-card-title">{t("portal.tabJobs") || "Operational Job Status"}</h3>
          <p className="mw-card-subtitle" style={{ margin: "0.25rem 0 0 0", color: "#666" }}>
            Read-only visibility into background job executions and outbox notification delivery state.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="refresh-jobs-btn"
            onClick={() => void loadJobData()}
            disabled={loading}
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div
          className="mw-notice-banner error"
          data-testid="job-status-error"
          style={{ marginBottom: "1rem" }}
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Operational Metrics Cards */}
      <div
        className="mw-metrics-row"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div
          className="mw-card"
          data-testid="metric-failed-jobs"
          style={{
            padding: "1rem",
            borderLeft: failedCount > 0 ? "4px solid #d32f2f" : "4px solid #2e7d32",
          }}
        >
          <div style={{ fontSize: "0.8rem", color: "#666", textTransform: "uppercase" }}>
            Failed Background Jobs
          </div>
          <div
            style={{
              fontSize: "1.6rem",
              fontWeight: 700,
              color: failedCount > 0 ? "#d32f2f" : "#2e7d32",
            }}
          >
            {failedCount}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#888", marginTop: "0.25rem" }}>
            Recent queue failures
          </div>
        </div>

        <div
          className="mw-card"
          data-testid="metric-outbox-total"
          style={{ padding: "1rem", borderLeft: "4px solid #0052cc" }}
        >
          <div style={{ fontSize: "0.8rem", color: "#666", textTransform: "uppercase" }}>
            Total Outbox Messages
          </div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0052cc" }}>
            {outboxOffset + outboxItems.length}{hasMore ? "+" : ""}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#888", marginTop: "0.25rem" }}>
            Notification outbox records
          </div>
        </div>
      </div>

      {/* Recent Failures Section (if any) */}
      {recentFailures.length > 0 && (
        <div className="mw-card" style={{ marginBottom: "1.5rem", padding: "1rem" }}>
          <h4 style={{ margin: "0 0 0.75rem 0", color: "#d32f2f" }}>
            Recent Job Failures ({recentFailures.length})
          </h4>
          <table
            className="mw-table"
            data-testid="failed-jobs-table"
            style={{ width: "100%", borderCollapse: "collapse" }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                <th style={{ padding: "0.5rem", fontSize: "0.8rem" }}>Job ID</th>
                <th style={{ padding: "0.5rem", fontSize: "0.8rem" }}>Job Name</th>
                <th style={{ padding: "0.5rem", fontSize: "0.8rem" }}>Error Code</th>
                <th style={{ padding: "0.5rem", fontSize: "0.8rem" }}>Attempts</th>
                <th style={{ padding: "0.5rem", fontSize: "0.8rem" }}>Failed At (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {recentFailures.map((job) => {
                const jId = job.job_id || job.id || "";
                const jName = job.job_name || job.kind || "";
                const jFailedAt = job.failed_at || job.updated_at || job.created_at || "";
                return (
                  <tr
                    key={jId}
                    data-testid={`failed-job-row-${jId}`}
                    style={{ borderBottom: "1px solid #f0f0f0", fontSize: "0.85rem" }}
                  >
                    <td style={{ padding: "0.5rem", fontFamily: "monospace" }}>{jId}</td>
                    <td style={{ padding: "0.5rem", fontWeight: 600 }}>{jName}</td>
                    <td style={{ padding: "0.5rem", color: "#d32f2f" }}>{job.error_code || "-"}</td>
                    <td style={{ padding: "0.5rem" }}>{job.attempts}</td>
                    <td style={{ padding: "0.5rem", color: "#666" }}>{formatUtcDate(jFailedAt)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Outbox Notifications Table */}
      <div className="mw-card" style={{ padding: "1rem" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "1rem",
            flexWrap: "wrap",
            gap: "0.5rem",
          }}
        >
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <h4 style={{ margin: 0, fontSize: "1rem" }}>Outbox Messages</h4>
            <select
              className="mw-select"
              data-testid="outbox-state-filter"
              value={selectedStateFilter}
              onChange={(e) => {
                setSelectedStateFilter(e.target.value);
                setOutboxOffset(0);
              }}
              style={{ fontSize: "0.8rem", padding: "0.2rem 0.5rem" }}
            >
              <option value="all">All States</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="delivered">Delivered</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div style={{ fontSize: "0.85rem", color: "#666" }} data-testid="outbox-header-info">
            Page {currentPage} ({outboxItems.length} loaded{hasMore ? ", more available" : ""})
          </div>
        </div>

        {outboxItems.length === 0 ? (
          <div
            data-testid="empty-outbox-state"
            style={{ padding: "2rem", textAlign: "center", color: "#888" }}
          >
            No outbox messages found for the selected filter.
          </div>
        ) : (
          <table
            className="mw-table"
            data-testid="outbox-table"
            style={{ width: "100%", borderCollapse: "collapse" }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>Message ID</th>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>Type</th>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>State</th>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>Attempts</th>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>Last Attempt</th>
                <th style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>Created (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {outboxItems.map((msg) => (
                <tr
                  key={msg.id}
                  data-testid={`outbox-row-${msg.id}`}
                  style={{ borderBottom: "1px solid #f0f0f0", fontSize: "0.85rem" }}
                >
                  <td style={{ padding: "0.5rem 0.75rem", fontFamily: "monospace" }}>{msg.id}</td>
                  <td style={{ padding: "0.5rem 0.75rem" }}>{msg.kind || msg.message_type}</td>
                  <td style={{ padding: "0.5rem 0.75rem" }}>
                    <span
                      className={`mw-badge status-${msg.state}`}
                      data-testid={`outbox-state-${msg.id}`}
                      style={{
                        padding: "0.2rem 0.4rem",
                        borderRadius: "4px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        textTransform: "uppercase",
                      }}
                    >
                      {msg.state}
                    </span>
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem" }}>{msg.attempts}</td>
                  <td style={{ padding: "0.5rem 0.75rem", color: "#666" }}>
                    {formatUtcDate(msg.last_attempt_at || msg.available_at || null)}
                  </td>
                  <td style={{ padding: "0.5rem 0.75rem", color: "#666" }}>
                    {formatUtcDate(msg.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination Controls */}
        <div
          data-testid="outbox-pagination"
          style={{
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            gap: "0.5rem",
            marginTop: "1rem",
            paddingTop: "0.5rem",
            borderTop: "1px solid #f0f0f0",
          }}
        >
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="outbox-prev-btn"
            disabled={outboxOffset === 0 || loading}
            onClick={() => setOutboxOffset(Math.max(0, outboxOffset - PAGE_SIZE))}
            style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
          >
            Previous
          </button>
          <span style={{ fontSize: "0.8rem", color: "#666" }} data-testid="outbox-page-indicator">
            Page {currentPage}
          </span>
          <button
            type="button"
            className="mw-btn mw-btn-secondary"
            data-testid="outbox-next-btn"
            disabled={!hasMore || loading}
            onClick={() => setOutboxOffset(outboxOffset + PAGE_SIZE)}
            style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
