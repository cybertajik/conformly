import type { TenantRole } from "@conformly/shared";
import React, { FC, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../i18n/I18nContext";
import {
  canReadAssets,
  canReadPolicies,
  canReadRisks,
  canReadTasks,
  canReadVendors,
} from "../permissions";
import { ForbiddenError, UnauthorizedError } from "./api";
import { AssetWorkspaceV2 } from "./AssetWorkspaceV2";
import { JobStatusPanel } from "./JobStatusPanel";
import {
  fetchAssets,
  fetchPolicies,
  fetchRisks,
  fetchVendors,
} from "./operations-api";
import {
  Asset,
  OperationsTab,
  Policy,
  Risk,
  Vendor,
} from "./operations-types";
import { PolicyWorkspaceV2 } from "./PolicyWorkspaceV2";
import { ReviewCalendar } from "./ReviewCalendar";
import { RiskWorkspaceV2 } from "./RiskWorkspaceV2";
import { fetchTasks } from "./task-api";
import { ComplianceTask } from "./task-types";
import { TaskWorkspaceV2 } from "./TaskWorkspaceV2";
import { VendorWorkspaceV2 } from "./VendorWorkspaceV2";
import { TrainingWorkspace } from "./TrainingWorkspace";
import "./modern-workspace.css";

export type ModuleStatus = "idle" | "loading" | "loaded" | "denied" | "error" | "stale";

export interface OperationsWorkspaceProps {
  tenantId: string;
  token: string;
  userRole?: string;
  currentUserId?: string;
  initialTab?: OperationsTab;
  onSessionExpired?: () => void;
}

export const OperationsWorkspace: FC<OperationsWorkspaceProps> = ({
  tenantId,
  token,
  userRole,
  currentUserId,
  initialTab = "policies",
  onSessionExpired,
}) => {
  const { t } = useTranslation();

  const [activeTab, setActiveTab] = useState<OperationsTab>(initialTab);
  const [navTarget, setNavTarget] = useState<{ tab: OperationsTab; recordId: string; nonce: number } | null>(null);

  const handleNavigateToRecord = (tab: OperationsTab, recordId: string) => {
    setNavTarget({ tab, recordId, nonce: Date.now() });
    setActiveTab(tab);
  };

  const handleConsumeTarget = useCallback(() => {
    setNavTarget(null);
  }, []);

  // Data registers state
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [risks, setRisks] = useState<Risk[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [tasks, setTasks] = useState<ComplianceTask[]>([]);

  // Loading and error states per register
  const [loadingPolicies, setLoadingPolicies] = useState<boolean>(false);
  const [loadingRisks, setLoadingRisks] = useState<boolean>(false);
  const [loadingAssets, setLoadingAssets] = useState<boolean>(false);
  const [loadingVendors, setLoadingVendors] = useState<boolean>(false);
  const [loadingTasks, setLoadingTasks] = useState<boolean>(false);

  const [policyStatus, setPolicyStatus] = useState<ModuleStatus>("idle");
  const [riskStatus, setRiskStatus] = useState<ModuleStatus>("idle");
  const [assetStatus, setAssetStatus] = useState<ModuleStatus>("idle");
  const [vendorStatus, setVendorStatus] = useState<ModuleStatus>("idle");
  const [taskStatus, setTaskStatus] = useState<ModuleStatus>("idle");
  const [tasksComplete, setTasksComplete] = useState<boolean>(true);

  const [policyError, setPolicyError] = useState<string | null>(null);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [vendorError, setVendorError] = useState<string | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);

  // Generations and epochs to fence stale async responses
  const policyGenRef = useRef<number>(0);
  const riskGenRef = useRef<number>(0);
  const assetGenRef = useRef<number>(0);
  const vendorGenRef = useRef<number>(0);
  const taskGenRef = useRef<number>(0);

  const policyMutationEpochRef = useRef<number>(0);
  const riskMutationEpochRef = useRef<number>(0);
  const assetMutationEpochRef = useRef<number>(0);
  const vendorMutationEpochRef = useRef<number>(0);
  const taskMutationEpochRef = useRef<number>(0);

  const contextRef = useRef({ tenantId, token });
  useEffect(() => {
    contextRef.current = { tenantId, token };
  }, [tenantId, token]);

  const onSessionExpiredRef = useRef(onSessionExpired);
  useEffect(() => {
    onSessionExpiredRef.current = onSessionExpired;
  }, [onSessionExpired]);

  const handle401 = useCallback(() => {
    policyGenRef.current += 1;
    riskGenRef.current += 1;
    assetGenRef.current += 1;
    vendorGenRef.current += 1;
    taskGenRef.current += 1;
    onSessionExpiredRef.current?.();
  }, []);

  const canReadPol = canReadPolicies(userRole as TenantRole);
  const canReadRsk = canReadRisks(userRole as TenantRole);
  const canReadAst = canReadAssets(userRole as TenantRole);
  const canReadVen = canReadVendors(userRole as TenantRole);
  const canReadTsk = canReadTasks(userRole as TenantRole);

  // Load Policies
  const loadPolicies = useCallback(async () => {
    if (!tenantId || !token) return;
    if (!canReadPol) {
      setPolicyStatus("denied");
      setPolicyError(t("portal.accessDenied") || "Access forbidden (403)");
      return;
    }
    const gen = ++policyGenRef.current;
    const epoch = policyMutationEpochRef.current;
    setLoadingPolicies(true);
    try {
      const data = await fetchPolicies(tenantId, token);
      if (
        gen !== policyGenRef.current ||
        contextRef.current.tenantId !== tenantId ||
        contextRef.current.token !== token
      ) {
        return;
      }
      if (epoch === policyMutationEpochRef.current) {
        setPolicies(data);
      }
      setPolicyStatus("loaded");
      setPolicyError(null);
    } catch (err: unknown) {
      if (gen !== policyGenRef.current) return;
      if (err instanceof UnauthorizedError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 401)) {
        handle401();
        return;
      }
      if (err instanceof ForbiddenError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 403)) {
        setPolicyStatus("denied");
        setPolicyError(t("portal.accessDenied") || "Access forbidden (403)");
      } else {
        const msg = err instanceof Error ? err.message : "Failed to load policies";
        setPolicyError(msg);
        setPolicyStatus(policies.length > 0 ? "stale" : "error");
      }
    } finally {
      if (gen === policyGenRef.current) {
        setLoadingPolicies(false);
      }
    }
  }, [tenantId, token, canReadPol, t, handle401, policies.length]);

  // Load Risks
  const loadRisks = useCallback(async () => {
    if (!tenantId || !token) return;
    if (!canReadRsk) {
      setRiskStatus("denied");
      setRiskError(t("portal.accessDenied") || "Access forbidden (403)");
      return;
    }
    const gen = ++riskGenRef.current;
    const epoch = riskMutationEpochRef.current;
    setLoadingRisks(true);
    try {
      const data = await fetchRisks(tenantId, token);
      if (
        gen !== riskGenRef.current ||
        contextRef.current.tenantId !== tenantId ||
        contextRef.current.token !== token
      ) {
        return;
      }
      if (epoch === riskMutationEpochRef.current) {
        setRisks(data);
      }
      setRiskStatus("loaded");
      setRiskError(null);
    } catch (err: unknown) {
      if (gen !== riskGenRef.current) return;
      if (err instanceof UnauthorizedError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 401)) {
        handle401();
        return;
      }
      if (err instanceof ForbiddenError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 403)) {
        setRiskStatus("denied");
        setRiskError(t("portal.accessDenied") || "Access forbidden (403)");
      } else {
        const msg = err instanceof Error ? err.message : "Failed to load risks";
        setRiskError(msg);
        setRiskStatus(risks.length > 0 ? "stale" : "error");
      }
    } finally {
      if (gen === riskGenRef.current) {
        setLoadingRisks(false);
      }
    }
  }, [tenantId, token, canReadRsk, t, handle401, risks.length]);

  // Load Assets
  const loadAssets = useCallback(async () => {
    if (!tenantId || !token) return;
    if (!canReadAst) {
      setAssetStatus("denied");
      setAssetError(t("portal.accessDenied") || "Access forbidden (403)");
      return;
    }
    const gen = ++assetGenRef.current;
    const epoch = assetMutationEpochRef.current;
    setLoadingAssets(true);
    try {
      const data = await fetchAssets(tenantId, token);
      if (
        gen !== assetGenRef.current ||
        contextRef.current.tenantId !== tenantId ||
        contextRef.current.token !== token
      ) {
        return;
      }
      if (epoch === assetMutationEpochRef.current) {
        setAssets(data);
      }
      setAssetStatus("loaded");
      setAssetError(null);
    } catch (err: unknown) {
      if (gen !== assetGenRef.current) return;
      if (err instanceof UnauthorizedError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 401)) {
        handle401();
        return;
      }
      if (err instanceof ForbiddenError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 403)) {
        setAssetStatus("denied");
        setAssetError(t("portal.accessDenied") || "Access forbidden (403)");
      } else {
        const msg = err instanceof Error ? err.message : "Failed to load assets";
        setAssetError(msg);
        setAssetStatus(assets.length > 0 ? "stale" : "error");
      }
    } finally {
      if (gen === assetGenRef.current) {
        setLoadingAssets(false);
      }
    }
  }, [tenantId, token, canReadAst, t, handle401, assets.length]);

  // Load Vendors
  const loadVendors = useCallback(async () => {
    if (!tenantId || !token) return;
    if (!canReadVen) {
      setVendorStatus("denied");
      setVendorError(t("portal.accessDenied") || "Access forbidden (403)");
      return;
    }
    const gen = ++vendorGenRef.current;
    const epoch = vendorMutationEpochRef.current;
    setLoadingVendors(true);
    try {
      const data = await fetchVendors(tenantId, token);
      if (
        gen !== vendorGenRef.current ||
        contextRef.current.tenantId !== tenantId ||
        contextRef.current.token !== token
      ) {
        return;
      }
      if (epoch === vendorMutationEpochRef.current) {
        setVendors(data);
      }
      setVendorStatus("loaded");
      setVendorError(null);
    } catch (err: unknown) {
      if (gen !== vendorGenRef.current) return;
      if (err instanceof UnauthorizedError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 401)) {
        handle401();
        return;
      }
      if (err instanceof ForbiddenError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 403)) {
        setVendorStatus("denied");
        setVendorError(t("portal.accessDenied") || "Access forbidden (403)");
      } else {
        const msg = err instanceof Error ? err.message : "Failed to load vendors";
        setVendorError(msg);
        setVendorStatus(vendors.length > 0 ? "stale" : "error");
      }
    } finally {
      if (gen === vendorGenRef.current) {
        setLoadingVendors(false);
      }
    }
  }, [tenantId, token, canReadVen, t, handle401, vendors.length]);

  // Load Tasks with bounded multi-page aggregation for calendar and operations
  const loadTasks = useCallback(async () => {
    if (!tenantId || !token) return;
    if (!canReadTsk) {
      setTaskStatus("denied");
      setTaskError(t("portal.accessDenied") || "Access forbidden (403)");
      setTasksComplete(false);
      return;
    }
    const gen = ++taskGenRef.current;
    const epoch = taskMutationEpochRef.current;
    setLoadingTasks(true);
    try {
      const TASK_BOUND = 200;
      const PAGE_SIZE = 100;
      let loadedTasks: ComplianceTask[] = [];
      let offset = 0;
      let isComplete = true;

      while (loadedTasks.length < TASK_BOUND) {
        const page = await fetchTasks(tenantId, token, { limit: PAGE_SIZE, offset });
        if (
          gen !== taskGenRef.current ||
          contextRef.current.tenantId !== tenantId ||
          contextRef.current.token !== token
        ) {
          return;
        }
        loadedTasks = [...loadedTasks, ...page];
        if (page.length < PAGE_SIZE) {
          isComplete = true;
          break;
        }
        offset += page.length;
        if (loadedTasks.length >= TASK_BOUND) {
          isComplete = false;
          break;
        }
      }

      if (epoch === taskMutationEpochRef.current) {
        setTasks(loadedTasks);
      }
      setTaskStatus("loaded");
      setTasksComplete(isComplete);
      setTaskError(null);
    } catch (err: unknown) {
      if (gen !== taskGenRef.current) return;
      if (err instanceof UnauthorizedError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 401)) {
        handle401();
        return;
      }
      if (err instanceof ForbiddenError || (typeof err === "object" && err !== null && "status" in err && (err as { status: unknown }).status === 403)) {
        setTaskStatus("denied");
        setTaskError(t("portal.accessDenied") || "Access forbidden (403)");
        setTasksComplete(false);
      } else {
        const msg = err instanceof Error ? err.message : "Failed to load tasks";
        setTaskError(msg);
        setTaskStatus(tasks.length > 0 ? "stale" : "error");
        setTasksComplete(false);
      }
    } finally {
      if (gen === taskGenRef.current) {
        setLoadingTasks(false);
      }
    }
  }, [tenantId, token, canReadTsk, t, handle401, tasks.length]);


  // Initial load across all accessible registers
  useEffect(() => {
    let ignore = false;
    void (async () => {
      await Promise.resolve();
      if (!ignore) {
        await Promise.all([
          loadPolicies(),
          loadRisks(),
          loadAssets(),
          loadVendors(),
          loadTasks(),
        ]);
      }
    })();
    return () => {
      ignore = true;
    };
  }, [loadPolicies, loadRisks, loadAssets, loadVendors, loadTasks]);

  // In-memory cache update callbacks with epoch protection
  const handlePolicyMutated = (updated: Policy) => {
    policyMutationEpochRef.current += 1;
    setPolicies((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
  };
  const handlePolicyCreated = (created: Policy) => {
    policyMutationEpochRef.current += 1;
    setPolicies((prev) => [created, ...prev]);
  };

  const handleRiskMutated = (updated: Risk) => {
    riskMutationEpochRef.current += 1;
    setRisks((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  };
  const handleRiskCreated = (created: Risk) => {
    riskMutationEpochRef.current += 1;
    setRisks((prev) => [created, ...prev]);
  };

  const handleAssetMutated = (updated: Asset) => {
    assetMutationEpochRef.current += 1;
    setAssets((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  };
  const handleAssetCreated = (created: Asset) => {
    assetMutationEpochRef.current += 1;
    setAssets((prev) => [created, ...prev]);
  };

  const handleVendorMutated = (updated: Vendor) => {
    vendorMutationEpochRef.current += 1;
    setVendors((prev) => prev.map((v) => (v.id === updated.id ? updated : v)));
  };
  const handleVendorCreated = (created: Vendor) => {
    vendorMutationEpochRef.current += 1;
    setVendors((prev) => [created, ...prev]);
  };

  const handleTaskMutated = (updated: ComplianceTask) => {
    taskMutationEpochRef.current += 1;
    setTasks((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
  };
  const handleTaskCreated = (created: ComplianceTask) => {
    taskMutationEpochRef.current += 1;
    setTasks((prev) => [created, ...prev]);
  };


  const renderBadge = (status: ModuleStatus, count: number) => {
    if (status === "denied") return "(—)";
    if (status === "error" && count === 0) return "(!)";
    return `(${count})`;
  };

  return (
    <div className="mw-workspace modern-workspace-root" data-testid="operations-workspace">
      {/* View Header */}
      <div className="mw-card-header" style={{ marginBottom: "1.5rem" }}>
        <div>
          <h2 className="mw-card-title">{t("portal.operationsTitle")}</h2>
          <p className="mw-card-subtitle">{t("portal.operationsSubtitle")}</p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div
        className="mw-tabs"
        data-testid="operations-tabs-bar"
        style={{
          display: "flex",
          gap: "0.5rem",
          borderBottom: "2px solid #e2e8f0",
          marginBottom: "1.5rem",
        }}
        role="tablist"
      >
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "policies"}
          className={`mw-tab-btn ${activeTab === "policies" ? "active" : ""}`}
          data-testid="operations-tab-policies"
          onClick={() => setActiveTab("policies")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "policies" ? "3px solid #0052cc" : "none",
            color: activeTab === "policies" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabPolicies")} {renderBadge(policyStatus, policies.length)}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "risks"}
          className={`mw-tab-btn ${activeTab === "risks" ? "active" : ""}`}
          data-testid="operations-tab-risks"
          onClick={() => setActiveTab("risks")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "risks" ? "3px solid #0052cc" : "none",
            color: activeTab === "risks" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabRisks")} {renderBadge(riskStatus, risks.length)}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "assets"}
          className={`mw-tab-btn ${activeTab === "assets" ? "active" : ""}`}
          data-testid="operations-tab-assets"
          onClick={() => setActiveTab("assets")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "assets" ? "3px solid #0052cc" : "none",
            color: activeTab === "assets" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabAssets")} {renderBadge(assetStatus, assets.length)}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "vendors"}
          className={`mw-tab-btn ${activeTab === "vendors" ? "active" : ""}`}
          data-testid="operations-tab-vendors"
          onClick={() => setActiveTab("vendors")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "vendors" ? "3px solid #0052cc" : "none",
            color: activeTab === "vendors" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabVendors")} {renderBadge(vendorStatus, vendors.length)}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "tasks"}
          className={`mw-tab-btn ${activeTab === "tasks" ? "active" : ""}`}
          data-testid="operations-tab-tasks"
          onClick={() => setActiveTab("tasks")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "tasks" ? "3px solid #0052cc" : "none",
            color: activeTab === "tasks" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabTasks") || "Tasks"} {renderBadge(taskStatus, tasks.length)}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "reviews"}
          className={`mw-tab-btn ${activeTab === "reviews" ? "active" : ""}`}
          data-testid="operations-tab-reviews"
          onClick={() => setActiveTab("reviews")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "reviews" ? "3px solid #0052cc" : "none",
            color: activeTab === "reviews" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabReviews") || "Review Hub"}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "jobs"}
          className={`mw-tab-btn ${activeTab === "jobs" ? "active" : ""}`}
          data-testid="operations-tab-jobs"
          onClick={() => setActiveTab("jobs")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "jobs" ? "3px solid #0052cc" : "none",
            color: activeTab === "jobs" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabJobs") || "Job Status"}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "training"}
          className={`mw-tab-btn ${activeTab === "training" ? "active" : ""}`}
          data-testid="operations-tab-training"
          onClick={() => setActiveTab("training")}
          style={{
            padding: "0.6rem 1.2rem",
            fontWeight: 600,
            borderBottom: activeTab === "training" ? "3px solid #0052cc" : "none",
            color: activeTab === "training" ? "#0052cc" : "#666",
            background: "none",
            borderTop: "none",
            borderLeft: "none",
            borderRight: "none",
            cursor: "pointer",
          }}
        >
          {t("portal.tabTraining") || "Training & LMS"}
        </button>

      </div>

      {/* Tab Panels: Kept mounted to preserve in-flight edit forms and draft states */}
      <div
        data-testid="operations-panel-policies"
        style={{ display: activeTab === "policies" ? "block" : "none" }}
      >
        {policyStatus === "denied" ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-denied-policies"
            style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied"}</h3>
            <p style={{ margin: 0 }}>{policyError || "You do not have permission to access policies (403 Forbidden)."}</p>
          </div>
        ) : policyStatus === "error" && policies.length === 0 ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-error-policies"
            style={{ padding: "1.5rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.errorLoadingPolicies") || "Failed to load policies"}</h3>
            <p>{policyError || "A server or network error occurred while loading policies."}</p>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-policies-btn"
              onClick={() => loadPolicies()}
            >
              {t("portal.retry") || "Retry"}
            </button>
          </div>
        ) : (
          <>
            {policyStatus === "stale" && (
              <div
                role="status"
                className="mw-card"
                data-testid="operations-stale-policies"
                style={{
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>{policyError || "Unable to refresh policies. Displaying cached data."}</span>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => loadPolicies()}
                >
                  {t("portal.retry") || "Retry"}
                </button>
              </div>
            )}
            <PolicyWorkspaceV2
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              currentUserId={currentUserId}
              policies={policies}
              loading={loadingPolicies}
              targetPolicyId={navTarget?.tab === "policies" ? navTarget.recordId : null}
              targetNonce={navTarget?.tab === "policies" ? navTarget.nonce : null}
              onConsumeTarget={handleConsumeTarget}
              onRefresh={loadPolicies}
              onSessionExpired={onSessionExpired}
              onPolicyMutated={handlePolicyMutated}
              onPolicyCreated={handlePolicyCreated}
              onTaskCreated={handleTaskCreated}
            />
          </>
        )}
      </div>

      <div
        data-testid="operations-panel-risks"
        style={{ display: activeTab === "risks" ? "block" : "none" }}
      >
        {riskStatus === "denied" ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-denied-risks"
            style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied"}</h3>
            <p style={{ margin: 0 }}>{riskError || "You do not have permission to access risks (403 Forbidden)."}</p>
          </div>
        ) : riskStatus === "error" && risks.length === 0 ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-error-risks"
            style={{ padding: "1.5rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.errorLoadingRisks") || "Failed to load risks"}</h3>
            <p>{riskError || "A server or network error occurred while loading risks."}</p>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-risks-btn"
              onClick={() => loadRisks()}
            >
              {t("portal.retry") || "Retry"}
            </button>
          </div>
        ) : (
          <>
            {riskStatus === "stale" && (
              <div
                role="status"
                className="mw-card"
                data-testid="operations-stale-risks"
                style={{
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>{riskError || "Unable to refresh risks. Displaying cached data."}</span>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => loadRisks()}
                >
                  {t("portal.retry") || "Retry"}
                </button>
              </div>
            )}
            <RiskWorkspaceV2
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              risks={risks}
              loading={loadingRisks}
              targetRiskId={navTarget?.tab === "risks" ? navTarget.recordId : null}
              targetNonce={navTarget?.tab === "risks" ? navTarget.nonce : null}
              onConsumeTarget={handleConsumeTarget}
              onRefresh={loadRisks}
              onSessionExpired={onSessionExpired}
              onRiskMutated={handleRiskMutated}
              onRiskCreated={handleRiskCreated}
            />
          </>
        )}
      </div>

      <div
        data-testid="operations-panel-assets"
        style={{ display: activeTab === "assets" ? "block" : "none" }}
      >
        {assetStatus === "denied" ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-denied-assets"
            style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied"}</h3>
            <p style={{ margin: 0 }}>{assetError || "You do not have permission to access assets (403 Forbidden)."}</p>
          </div>
        ) : assetStatus === "error" && assets.length === 0 ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-error-assets"
            style={{ padding: "1.5rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.errorLoadingAssets") || "Failed to load assets"}</h3>
            <p>{assetError || "A server or network error occurred while loading assets."}</p>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-assets-btn"
              onClick={() => loadAssets()}
            >
              {t("portal.retry") || "Retry"}
            </button>
          </div>
        ) : (
          <>
            {assetStatus === "stale" && (
              <div
                role="status"
                className="mw-card"
                data-testid="operations-stale-assets"
                style={{
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>{assetError || "Unable to refresh assets. Displaying cached data."}</span>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => loadAssets()}
                >
                  {t("portal.retry") || "Retry"}
                </button>
              </div>
            )}
            <AssetWorkspaceV2
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              assets={assets}
              loading={loadingAssets}
              targetAssetId={navTarget?.tab === "assets" ? navTarget.recordId : null}
              targetNonce={navTarget?.tab === "assets" ? navTarget.nonce : null}
              onConsumeTarget={handleConsumeTarget}
              onRefresh={loadAssets}
              onSessionExpired={onSessionExpired}
              onAssetMutated={handleAssetMutated}
              onAssetCreated={handleAssetCreated}
            />
          </>
        )}
      </div>

      <div
        data-testid="operations-panel-vendors"
        style={{ display: activeTab === "vendors" ? "block" : "none" }}
      >
        {vendorStatus === "denied" ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-denied-vendors"
            style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied"}</h3>
            <p style={{ margin: 0 }}>{vendorError || "You do not have permission to access vendors (403 Forbidden)."}</p>
          </div>
        ) : vendorStatus === "error" && vendors.length === 0 ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-error-vendors"
            style={{ padding: "1.5rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.errorLoadingVendors") || "Failed to load vendors"}</h3>
            <p>{vendorError || "A server or network error occurred while loading vendors."}</p>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-vendors-btn"
              onClick={() => loadVendors()}
            >
              {t("portal.retry") || "Retry"}
            </button>
          </div>
        ) : (
          <>
            {vendorStatus === "stale" && (
              <div
                role="status"
                className="mw-card"
                data-testid="operations-stale-vendors"
                style={{
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>{vendorError || "Unable to refresh vendors. Displaying cached data."}</span>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => loadVendors()}
                >
                  {t("portal.retry") || "Retry"}
                </button>
              </div>
            )}
            <VendorWorkspaceV2
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              vendors={vendors}
              loading={loadingVendors}
              targetVendorId={navTarget?.tab === "vendors" ? navTarget.recordId : null}
              targetNonce={navTarget?.tab === "vendors" ? navTarget.nonce : null}
              onConsumeTarget={handleConsumeTarget}
              onRefresh={loadVendors}
              onSessionExpired={onSessionExpired}
              onVendorMutated={handleVendorMutated}
              onVendorCreated={handleVendorCreated}
            />
          </>
        )}
      </div>

      {/* Tasks Panel */}
      <div
        data-testid="operations-panel-tasks"
        style={{ display: activeTab === "tasks" ? "block" : "none" }}
      >
        {taskStatus === "denied" ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-denied-tasks"
            style={{ padding: "1.5rem", borderLeft: "4px solid #d97706", backgroundColor: "#fffbeb" }}
          >
            <h3 style={{ marginTop: 0 }}>{t("portal.accessDenied") || "Access Denied"}</h3>
            <p style={{ margin: 0 }}>{taskError || "You do not have permission to access tasks (403 Forbidden)."}</p>
          </div>
        ) : taskStatus === "error" && tasks.length === 0 ? (
          <div
            role="status"
            className="mw-card"
            data-testid="operations-error-tasks"
            style={{ padding: "1.5rem", borderLeft: "4px solid #ef4444", backgroundColor: "#fef2f2" }}
          >
            <h3 style={{ marginTop: 0 }}>Failed to load tasks</h3>
            <p>{taskError || "A server or network error occurred while loading tasks."}</p>
            <button
              type="button"
              className="mw-btn mw-btn-secondary"
              data-testid="retry-tasks-btn"
              onClick={() => loadTasks()}
            >
              {t("portal.retry") || "Retry"}
            </button>
          </div>
        ) : (
          <>
            {taskStatus === "stale" && (
              <div
                role="status"
                className="mw-card"
                data-testid="operations-stale-tasks"
                style={{
                  padding: "0.75rem 1rem",
                  marginBottom: "1rem",
                  backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span>{taskError || "Unable to refresh tasks. Displaying cached data."}</span>
                <button
                  type="button"
                  className="mw-btn mw-btn-secondary"
                  onClick={() => loadTasks()}
                >
                  {t("portal.retry") || "Retry"}
                </button>
              </div>
            )}
            <TaskWorkspaceV2
              tenantId={tenantId}
              token={token}
              userRole={userRole}
              loading={loadingTasks}
              targetTaskId={navTarget?.tab === "tasks" ? navTarget.recordId : null}
              targetNonce={navTarget?.tab === "tasks" ? navTarget.nonce : null}
              onConsumeTarget={handleConsumeTarget}
              onRefresh={loadTasks}
              onSessionExpired={onSessionExpired}
              onTaskMutated={handleTaskMutated}
              onTaskCreated={handleTaskCreated}
            />
          </>
        )}
      </div>

      {/* Review Calendar Panel */}
      <div
        data-testid="operations-panel-reviews"
        style={{ display: activeTab === "reviews" ? "block" : "none" }}
      >
        <ReviewCalendar
          tenantId={tenantId}
          token={token}
          userRole={userRole}
          policies={policies}
          risks={risks}
          assets={assets}
          vendors={vendors}
          tasks={tasks}
          policiesLoaded={policyStatus === "loaded"}
          risksLoaded={riskStatus === "loaded"}
          assetsLoaded={assetStatus === "loaded"}
          vendorsLoaded={vendorStatus === "loaded"}
          tasksLoaded={taskStatus === "loaded"}
          tasksComplete={taskStatus === "loaded" ? tasksComplete : false}
          policiesError={policyError}
          risksError={riskError}
          assetsError={assetError}
          vendorsError={vendorError}
          tasksError={taskError}
          onNavigateToRecord={(tab, recordId) => {
            handleNavigateToRecord(tab, recordId);
          }}
          onRefresh={() => {
            void Promise.all([loadPolicies(), loadRisks(), loadAssets(), loadVendors(), loadTasks()]);
          }}
        />
      </div>

      {/* Job Status Panel */}
      <div
        data-testid="operations-panel-jobs"
        style={{ display: activeTab === "jobs" ? "block" : "none" }}
      >
        <JobStatusPanel
          tenantId={tenantId}
          token={token}
          userRole={userRole}
          onSessionExpired={onSessionExpired}
        />
      </div>

      {/* Training Panel */}
      <div
        data-testid="operations-panel-training"
        style={{ display: activeTab === "training" ? "block" : "none" }}
      >
        <TrainingWorkspace
          tenantId={tenantId}
          token={token}
          userRole={userRole}
          isActive={activeTab === "training"}
          onSessionExpired={onSessionExpired}
        />
      </div>

    </div>
  );
};
