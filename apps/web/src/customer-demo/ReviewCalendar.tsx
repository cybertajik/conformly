import React, { useMemo, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import { Policy, Risk, Asset, Vendor } from "./operations-types";
import { ComplianceTask } from "./task-types";
import "./modern-workspace.css";

export type ReviewSourceKind = "policy" | "risk" | "asset" | "vendor" | "task";
export type ReviewBucket = "all" | "overdue" | "today" | "next7" | "next30";

export interface ReviewItem {
  id: string;
  sourceKind: ReviewSourceKind;
  sourceId: string;
  title: string;
  dueDate: string; // Server date string
  status: string;
  priority?: string | null;
  moduleTab: "policies" | "risks" | "assets" | "vendors" | "tasks";
}

export interface ReviewCalendarProps {
  tenantId: string;
  token: string;
  userRole?: string;
  policies?: Policy[];
  risks?: Risk[];
  assets?: Asset[];
  vendors?: Vendor[];
  tasks?: ComplianceTask[];
  policiesLoaded?: boolean;
  risksLoaded?: boolean;
  assetsLoaded?: boolean;
  vendorsLoaded?: boolean;
  tasksLoaded?: boolean;
  tasksComplete?: boolean;
  policiesError?: string | null;
  risksError?: string | null;
  assetsError?: string | null;
  vendorsError?: string | null;
  tasksError?: string | null;
  currentDate?: Date | string;
  onNavigateToRecord?: (tab: "policies" | "risks" | "assets" | "vendors" | "tasks", recordId: string) => void;
  onRefresh?: () => void;
}

function getUtcDayStart(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

export const ReviewCalendar: React.FC<ReviewCalendarProps> = ({
  policies = [],
  risks = [],
  assets = [],
  vendors = [],
  tasks = [],
  policiesLoaded = true,
  risksLoaded = true,
  assetsLoaded = true,
  vendorsLoaded = true,
  tasksLoaded = true,
  tasksComplete = true,
  policiesError = null,
  risksError = null,
  assetsError = null,
  vendorsError = null,
  tasksError = null,
  currentDate,
  onNavigateToRecord,
  onRefresh,
}) => {
  const { t } = useTranslation();
  const [selectedBucket, setSelectedBucket] = useState<ReviewBucket>("all");
  const [selectedSource, setSelectedSource] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const clock = useMemo(() => {
    return currentDate ? new Date(currentDate) : new Date();
  }, [currentDate]);

  const todayUtcStart = useMemo(() => getUtcDayStart(clock), [clock]);
  const oneDayMs = 86400000;
  const next7End = todayUtcStart + 7 * oneDayMs;
  const next30End = todayUtcStart + 30 * oneDayMs;

  // Aggregate items strictly from server dates
  const allItems: ReviewItem[] = useMemo(() => {
    const list: ReviewItem[] = [];

    // 1. Policies: next_review_due
    for (const p of policies) {
      if (p.next_review_due && p.status !== "archived") {
        list.push({
          id: `pol-${p.id}`,
          sourceKind: "policy",
          sourceId: p.id,
          title: p.title,
          dueDate: p.next_review_due,
          status: p.status,
          moduleTab: "policies",
        });
      }
    }

    // 2. Risks: next_review_due_at
    for (const r of risks) {
      if (r.next_review_due_at && r.status !== "closed") {
        list.push({
          id: `risk-${r.id}`,
          sourceKind: "risk",
          sourceId: r.id,
          title: r.title,
          dueDate: r.next_review_due_at,
          status: r.status,
          priority: r.category,
          moduleTab: "risks",
        });
      }
    }

    // 3. Assets: next_review_due_at
    for (const a of assets) {
      if (a.next_review_due_at && a.status !== "decommissioned") {
        list.push({
          id: `asset-${a.id}`,
          sourceKind: "asset",
          sourceId: a.id,
          title: a.name,
          dueDate: a.next_review_due_at,
          status: a.status,
          moduleTab: "assets",
        });
      }
    }

    // 4. Vendors: next_review_due_at
    for (const v of vendors) {
      if (v.next_review_due_at && v.status !== "terminated") {
        list.push({
          id: `vendor-${v.id}`,
          sourceKind: "vendor",
          sourceId: v.id,
          title: v.name,
          dueDate: v.next_review_due_at,
          status: v.status || "active",
          priority: v.criticality,
          moduleTab: "vendors",
        });
      }
    }

    // 5. Tasks: due_date
    for (const task of tasks) {
      if (task.due_date && task.status !== "completed" && task.status !== "cancelled") {
        list.push({
          id: `task-${task.id}`,
          sourceKind: "task",
          sourceId: task.id,
          title: task.title,
          dueDate: task.due_date,
          status: task.status,
          priority: task.priority,
          moduleTab: "tasks",
        });
      }
    }

    return list;
  }, [policies, risks, assets, vendors, tasks]);

  // Check if any module encountered errors or missing data
  const hasModuleErrors = Boolean(
    policiesError || risksError || assetsError || vendorsError || tasksError
  );
  const isPartialCoverage = hasModuleErrors || !policiesLoaded || !risksLoaded || !assetsLoaded || !vendorsLoaded || !tasksLoaded || tasksComplete === false;

  // Categorize into buckets
  const bucketCounts = useMemo(() => {
    let overdue = 0;
    let today = 0;
    let next7 = 0;
    let next30 = 0;

    for (const item of allItems) {
      const itemTime = getUtcDayStart(new Date(item.dueDate));
      if (itemTime < todayUtcStart) {
        overdue++;
      } else if (itemTime === todayUtcStart) {
        today++;
        next7++;
        next30++;
      } else {
        if (itemTime <= next7End) next7++;
        if (itemTime <= next30End) next30++;
      }
    }

    return {
      all: allItems.length,
      overdue,
      today,
      next7,
      next30,
    };
  }, [allItems, todayUtcStart, next7End, next30End]);

  // Filter items
  const filteredItems = useMemo(() => {
    return allItems
      .filter((item) => {
        // Bucket filter
        const itemTime = getUtcDayStart(new Date(item.dueDate));
        if (selectedBucket === "overdue") {
          if (itemTime >= todayUtcStart) return false;
        } else if (selectedBucket === "today") {
          if (itemTime !== todayUtcStart) return false;
        } else if (selectedBucket === "next7") {
          if (itemTime < todayUtcStart || itemTime > next7End) return false;
        } else if (selectedBucket === "next30") {
          if (itemTime < todayUtcStart || itemTime > next30End) return false;
        }

        // Source filter
        if (selectedSource !== "all" && item.sourceKind !== selectedSource) {
          return false;
        }

        // Search query
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          return item.title.toLowerCase().includes(q) || item.status.toLowerCase().includes(q);
        }

        return true;
      })
      .sort((a, b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime());
  }, [allItems, selectedBucket, selectedSource, searchQuery, todayUtcStart, next7End, next30End]);

  const formatUtcDate = (dateStr: string) => {
    const d = new Date(dateStr);
    const yr = d.getUTCFullYear();
    const mo = String(d.getUTCMonth() + 1).padStart(2, "0");
    const day = String(d.getUTCDate()).padStart(2, "0");
    return `${yr}-${mo}-${day} (UTC)`;
  };

  return (
    <div className="mw-operations-calendar" data-testid="review-calendar">
      {/* Header & Coverage Summary */}
      <div className="mw-card-header" style={{ marginBottom: "1rem" }}>
        <div>
          <h3 className="mw-card-title">{t("portal.tabReviews") || "Review Hub & Calendar"}</h3>
          <p className="mw-card-subtitle" style={{ margin: "0.25rem 0 0 0", color: "#666" }}>
            Aggregated periodic review milestones across policies, risk register, assets, vendors, and compliance tasks.
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {onRefresh && (
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="refresh-calendar-btn"
              onClick={onRefresh}
            >
              Refresh
            </button>
          )}
        </div>
      </div>

      {/* Honest Coverage Notice if modules failed */}
      {isPartialCoverage && (
        <div
          className="mw-notice-banner warning"
          data-testid="calendar-partial-coverage-notice"
          style={{ marginBottom: "1rem" }}
          role="alert"
        >
          <strong>Partial Coverage Notice:</strong> Some operations data could not be fully loaded.
          Upcoming counts reflect available modules only and are not authoritative totals.
          {policiesError && <div>Policies error: {policiesError}</div>}
          {risksError && <div>Risks error: {risksError}</div>}
          {assetsError && <div>Assets error: {assetsError}</div>}
          {vendorsError && <div>Vendors error: {vendorsError}</div>}
          {tasksError && <div>Tasks error: {tasksError}</div>}
          {tasksComplete === false && !tasksError && (
            <div data-testid="calendar-tasks-bounded-notice">
              Tasks review items reflect a bounded range ({tasks.length} loaded) and may not represent the complete schedule.
            </div>
          )}
        </div>
      )}

      {/* Metrics Badges */}
      <div
        className="mw-metrics-row"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: "1rem",
          marginBottom: "1.25rem",
        }}
      >
        <div
          className={`mw-metric-card ${selectedBucket === "all" ? "active" : ""}`}
          data-testid="badge-actionable"
          style={{
            padding: "0.75rem 1rem",
            background: "#fff",
            border: selectedBucket === "all" ? "2px solid #0052cc" : "1px solid #e0e0e0",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={() => setSelectedBucket("all")}
        >
          <div style={{ fontSize: "0.8rem", color: "#666" }}>All Active</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{bucketCounts.all}</div>
        </div>

        <div
          className={`mw-metric-card ${selectedBucket === "overdue" ? "active" : ""}`}
          data-testid="badge-overdue"
          style={{
            padding: "0.75rem 1rem",
            background: "#fff",
            border: selectedBucket === "overdue" ? "2px solid #d32f2f" : "1px solid #e0e0e0",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={() => setSelectedBucket("overdue")}
        >
          <div style={{ fontSize: "0.8rem", color: "#d32f2f", fontWeight: 600 }}>Overdue</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#d32f2f" }}>
            {bucketCounts.overdue}
          </div>
        </div>

        <div
          className={`mw-metric-card ${selectedBucket === "today" ? "active" : ""}`}
          data-testid="badge-today"
          style={{
            padding: "0.75rem 1rem",
            background: "#fff",
            border: selectedBucket === "today" ? "2px solid #ed6c02" : "1px solid #e0e0e0",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={() => setSelectedBucket("today")}
        >
          <div style={{ fontSize: "0.8rem", color: "#ed6c02", fontWeight: 600 }}>Today</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#ed6c02" }}>
            {bucketCounts.today}
          </div>
        </div>

        <div
          className={`mw-metric-card ${selectedBucket === "next7" ? "active" : ""}`}
          data-testid="badge-next7"
          style={{
            padding: "0.75rem 1rem",
            background: "#fff",
            border: selectedBucket === "next7" ? "2px solid #0288d1" : "1px solid #e0e0e0",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={() => setSelectedBucket("next7")}
        >
          <div style={{ fontSize: "0.8rem", color: "#0288d1" }}>Next 7 Days</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{bucketCounts.next7}</div>
        </div>

        <div
          className={`mw-metric-card ${selectedBucket === "next30" ? "active" : ""}`}
          data-testid="badge-next30"
          style={{
            padding: "0.75rem 1rem",
            background: "#fff",
            border: selectedBucket === "next30" ? "2px solid #2e7d32" : "1px solid #e0e0e0",
            borderRadius: "6px",
            cursor: "pointer",
          }}
          onClick={() => setSelectedBucket("next30")}
        >
          <div style={{ fontSize: "0.8rem", color: "#2e7d32" }}>Next 30 Days</div>
          <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{bucketCounts.next30}</div>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        className="mw-filter-bar"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "1rem",
          gap: "0.75rem",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.85rem", color: "#666" }}>Filter:</span>
          <select
            className="mw-select"
            data-testid="review-bucket-filter"
            value={selectedBucket}
            onChange={(e) => setSelectedBucket(e.target.value as ReviewBucket)}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All Dates</option>
            <option value="overdue">Overdue Only</option>
            <option value="today">Today</option>
            <option value="next7">Next 7 Days</option>
            <option value="next30">Next 30 Days</option>
          </select>

          <select
            className="mw-select"
            data-testid="review-source-filter"
            value={selectedSource}
            onChange={(e) => setSelectedSource(e.target.value)}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem" }}
          >
            <option value="all">All Modules</option>
            <option value="policy">Policies</option>
            <option value="risk">Risk Register</option>
            <option value="asset">Assets</option>
            <option value="vendor">Vendors</option>
            <option value="task">Tasks</option>
          </select>

          <input
            type="text"
            className="mw-input"
            data-testid="review-search-input"
            placeholder="Search reviews..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ fontSize: "0.85rem", padding: "0.25rem 0.5rem", width: "180px" }}
          />
        </div>

        <div style={{ fontSize: "0.85rem", color: "#666" }}>
          Showing {filteredItems.length} review item{filteredItems.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Table of Review Items */}
      <div className="mw-card" style={{ padding: "0.5rem" }}>
        {filteredItems.length === 0 ? (
          <div
            data-testid="empty-reviews-state"
            style={{ padding: "2rem", textAlign: "center", color: "#888" }}
          >
            No upcoming reviews found matching the selected filters.
          </div>
        ) : (
          <table
            className="mw-table"
            data-testid="reviews-table"
            style={{ width: "100%", borderCollapse: "collapse" }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #e0e0e0", textAlign: "left" }}>
                <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Record</th>
                <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Module</th>
                <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Status</th>
                <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>Review Due (UTC)</th>
                <th style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem", textAlign: "right" }}>
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => {
                const itemTime = getUtcDayStart(new Date(item.dueDate));
                const isOverdue = itemTime < todayUtcStart;

                return (
                  <tr
                    key={item.id}
                    data-testid={`review-item-${item.sourceKind}-${item.sourceId}`}
                    style={{
                      borderBottom: "1px solid #f0f0f0",
                      background: isOverdue ? "rgba(211, 47, 47, 0.04)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "0.6rem 0.75rem" }}>
                      <div style={{ fontWeight: 500, fontSize: "0.9rem" }}>{item.title}</div>
                      {item.priority && (
                        <span style={{ fontSize: "0.75rem", color: "#666", textTransform: "capitalize" }}>
                          Priority / Category: {item.priority}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "0.6rem 0.75rem" }}>
                      <span
                        className="mw-badge"
                        style={{
                          textTransform: "uppercase",
                          fontSize: "0.75rem",
                          padding: "0.2rem 0.4rem",
                          borderRadius: "4px",
                          background: "#eef2f7",
                          color: "#334155",
                          fontWeight: 600,
                        }}
                      >
                        {item.sourceKind}
                      </span>
                    </td>
                    <td style={{ padding: "0.6rem 0.75rem" }}>
                      <span
                        className={`mw-badge status-${item.status.replace("_", "-")}`}
                        style={{
                          padding: "0.2rem 0.4rem",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                        }}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td style={{ padding: "0.6rem 0.75rem", fontSize: "0.85rem" }}>
                      <span
                        style={{
                          color: isOverdue ? "#d32f2f" : "#333",
                          fontWeight: isOverdue ? 600 : 400,
                        }}
                      >
                        {formatUtcDate(item.dueDate)}
                      </span>
                      {isOverdue && (
                        <span
                          className="mw-badge"
                          style={{
                            marginLeft: "0.5rem",
                            background: "#ffebee",
                            color: "#c62828",
                            fontSize: "0.7rem",
                            padding: "0.15rem 0.35rem",
                            borderRadius: "3px",
                            fontWeight: 600,
                          }}
                        >
                          OVERDUE
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "0.6rem 0.75rem", textAlign: "right" }}>
                      {onNavigateToRecord && (
                        <button
                          type="button"
                          className="mw-btn mw-btn-secondary"
                          data-testid={`navigate-review-${item.sourceId}`}
                          style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
                          onClick={() => onNavigateToRecord(item.moduleTab, item.sourceId)}
                        >
                          View Record
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
