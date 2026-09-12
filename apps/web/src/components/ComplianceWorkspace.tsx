import type {
  ComplianceTaskSummary,
  ControlEntityType,
  ControlImplementationStatus,
  ControlStatusRecordSummary,
  DataClassification,
  DigestFrequency,
  EvidenceControlLinkSummary,
  EvidenceFileLinkSummary,
  EvidenceItemSummary,
  EvidenceStatus,
  FindingSeverity,
  FindingSummary,
  FrameworkSummary,
  JobExecutionSummary,
  PolicyControlLinkSummary,
  PolicySummary,
  RemediationStatus,
  TaskPriority,
  TenantRole,
  UserNotificationPreferenceSummary,
} from "@conformly/shared";
import { useCallback, useEffect, useState } from "react";

import {
  approvePolicy,
  archivePolicy,
  attachFileToEvidence,
  completeTask,
  createEvidence,
  createFinding,
  createPolicy,
  createTask,
  getCanonicalVersionDetails,
  getUserPreferences,
  linkControlToEvidence,
  linkControlToPolicy,
  listCanonicalFrameworks,
  listControlStatuses,
  listCustomControls,
  listEvidence,
  listFindings,
  listPolicies,
  listTasks,
  listTenantAdoptions,
  publishPolicy,
  remediateFinding,
  removeFileFromEvidence,
  runComplianceJobs,
  submitPolicyReview,
  transitionEvidence,
  unlinkControlFromEvidence,
  unlinkControlFromPolicy,
  updateUserPreferences,
  upsertControlStatus,
} from "../api";
import { getAccessToken } from "../auth";
import {
  canManageControlStatus,
  canManageEvidence,
  canManageFindings,
  canManagePolicies,
  canManageTasks,
  canReadEvidence,
  canReadPolicies,
} from "../permissions";

type WorkspaceTab =
  | "posture"
  | "evidence"
  | "policies"
  | "tasks"
  | "findings"
  | "automation";

interface ComplianceWorkspaceProps {
  tenantId: string;
  userRole: TenantRole;
  currentUserId?: string;
}

interface UnifiedControl {
  id: string;
  type: ControlEntityType;
  identifier: string;
  title: string;
  category: string;
  frameworkName?: string;
}

export function ComplianceWorkspace({
  tenantId,
  userRole,
  currentUserId,
}: ComplianceWorkspaceProps) {
  const token = getAccessToken() ?? "";
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("posture");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [conflictWarning, setConflictWarning] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Core datasets
  const [unifiedControls, setUnifiedControls] = useState<UnifiedControl[]>([]);
  const [controlStatuses, setControlStatuses] = useState<ControlStatusRecordSummary[]>([]);
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItemSummary[]>([]);
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [tasks, setTasks] = useState<ComplianceTaskSummary[]>([]);
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [, setUserPrefs] = useState<UserNotificationPreferenceSummary | null>(null);
  const [lastJobResult, setLastJobResult] = useState<JobExecutionSummary | null>(null);
  const [runningJobs, setRunningJobs] = useState(false);
  const [now] = useState(() => Date.now());

  // Filtering states
  const [evidenceStatusFilter, setEvidenceStatusFilter] = useState<string>("all");
  const [policyStatusFilter, setPolicyStatusFilter] = useState<string>("all");
  const [taskStatusFilter, setTaskStatusFilter] = useState<string>("all");
  const [findingSeverityFilter, setFindingSeverityFilter] = useState<string>("all");

  // Posture modal state
  const [selectedControlForPosture, setSelectedControlForPosture] = useState<UnifiedControl | null>(null);
  const [postureStatusInput, setPostureStatusInput] = useState<ControlImplementationStatus>("not_started");
  const [postureOwnerInput, setPostureOwnerInput] = useState("");
  const [postureNotesInput, setPostureNotesInput] = useState("");

  // Create Evidence modal
  const [showCreateEvidence, setShowCreateEvidence] = useState(false);
  const [newEvidenceTitle, setNewEvidenceTitle] = useState("");
  const [newEvidenceDesc, setNewEvidenceDesc] = useState("");
  const [newEvidenceClass, setNewEvidenceClass] = useState<DataClassification>("Internal");
  const [newEvidenceValidFrom, setNewEvidenceValidFrom] = useState("");
  const [newEvidenceValidUntil, setNewEvidenceValidUntil] = useState("");
  const [newEvidenceRestrictedNotes, setNewEvidenceRestrictedNotes] = useState("");

  // Transition & Detail Evidence modal
  const [selectedEvidenceForDetail, setSelectedEvidenceForDetail] = useState<EvidenceItemSummary | null>(null);
  const [transitionReason, setTransitionReason] = useState("");
  const [newFileIdToAttach, setNewFileIdToAttach] = useState("");
  const [linkControlType, setLinkControlType] = useState<ControlEntityType>("canonical");
  const [linkControlId, setLinkControlId] = useState("");

  // Create Policy modal
  const [showCreatePolicy, setShowCreatePolicy] = useState(false);
  const [newPolicyTitle, setNewPolicyTitle] = useState("");
  const [newPolicyDesc, setNewPolicyDesc] = useState("");
  const [newPolicyVersionStr, setNewPolicyVersionStr] = useState("1.0");
  const [newPolicyCycleDays, setNewPolicyCycleDays] = useState(365);
  const [newPolicyClass, setNewPolicyClass] = useState<DataClassification>("Internal");
  const [newPolicyContent, setNewPolicyContent] = useState("");
  const [newPolicyRestrictedContent, setNewPolicyRestrictedContent] = useState("");

  // Policy Control Link modal
  const [selectedPolicyForDetail, setSelectedPolicyForDetail] = useState<PolicySummary | null>(null);
  const [policyLinkControlType, setPolicyLinkControlType] = useState<ControlEntityType>("canonical");
  const [policyLinkControlId, setPolicyLinkControlId] = useState("");

  // Create Task modal
  const [showCreateTask, setShowCreateTask] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskDueDate, setNewTaskDueDate] = useState("");
  const [newTaskPriority, setNewTaskPriority] = useState<TaskPriority>("medium");
  const [newTaskAssignee, setNewTaskAssignee] = useState("");

  // Create Finding modal
  const [showCreateFinding, setShowCreateFinding] = useState(false);
  const [newFindingTitle, setNewFindingTitle] = useState("");
  const [newFindingDesc, setNewFindingDesc] = useState("");
  const [newFindingSeverity, setNewFindingSeverity] = useState<FindingSeverity>("medium");
  const [newFindingDueDate, setNewFindingDueDate] = useState("");
  const [newFindingPlan, setNewFindingPlan] = useState("");

  // Remediate Finding modal
  const [selectedFindingForRemediation, setSelectedFindingForRemediation] = useState<FindingSummary | null>(null);
  const [remediationStatusInput, setRemediationStatusInput] = useState<RemediationStatus>("in_remediation");
  const [remediationSummaryInput, setRemediationSummaryInput] = useState("");

  // Preferences form
  const [prefEmailEnabled, setPrefEmailEnabled] = useState(true);
  const [prefDigestFrequency, setPrefDigestFrequency] = useState<DigestFrequency>("daily");
  const [prefNotifyTaskAssigned, setPrefNotifyTaskAssigned] = useState(true);
  const [prefNotifyTaskDue, setPrefNotifyTaskDue] = useState(true);
  const [prefNotifyEvidenceExpired, setPrefNotifyEvidenceExpired] = useState(true);
  const [prefNotifyPolicyReview, setPrefNotifyPolicyReview] = useState(true);
  const [prefNotifyFindingRaised, setPrefNotifyFindingRaised] = useState(true);

  // Load compliance workspace datasets
  const loadComplianceData = useCallback(async () => {
    try {
      setError(null);
      setConflictWarning(null);

      const [
        fws,
        adoptions,
        customCtrls,
        statuses,
        evList,
        polList,
        tskList,
        findList,
        prefs,
      ] = await Promise.all([
        listCanonicalFrameworks(token),
        listTenantAdoptions(token, tenantId),
        listCustomControls(token, tenantId),
        listControlStatuses(token, tenantId),
        canReadEvidence(userRole) ? listEvidence(token, tenantId) : Promise.resolve([]),
        canReadPolicies(userRole) ? listPolicies(token, tenantId) : Promise.resolve([]),
        listTasks(token, tenantId),
        listFindings(token, tenantId),
        getUserPreferences(token, tenantId).catch(() => null),
      ]);

      // Collect canonical controls from adopted framework versions
      const allControls: UnifiedControl[] = [];
      const activeAdoptions = adoptions.filter((a) => a.status === "active");

      for (const adoption of activeAdoptions) {
        const fw = fws.find((f: FrameworkSummary) => f.id === adoption.framework_id);
        try {
          const vDetails = await getCanonicalVersionDetails(
            token,
            adoption.framework_id,
            adoption.framework_version_id
          );
          if (vDetails && vDetails.controls) {
            for (const c of vDetails.controls) {
              allControls.push({
                id: c.id,
                type: "canonical",
                identifier: c.identifier,
                title: c.title,
                category: c.category,
                frameworkName: fw ? fw.name : "Canonical",
              });
            }
          }
        } catch {
          // Continue if a single version fails to fetch
        }
      }

      // Add custom controls
      for (const cc of customCtrls) {
        allControls.push({
          id: cc.id,
          type: "custom",
          identifier: cc.identifier,
          title: cc.title,
          category: cc.category,
          frameworkName: "Custom Overlay",
        });
      }

      setUnifiedControls(allControls);
      setControlStatuses(statuses);
      setEvidenceItems(evList);
      setPolicies(polList);
      setTasks(tskList);
      setFindings(findList);

      if (prefs) {
        setUserPrefs(prefs);
        setPrefEmailEnabled(prefs.email_enabled);
        setPrefDigestFrequency(prefs.digest_frequency);
        setPrefNotifyTaskAssigned(prefs.notify_task_assigned);
        setPrefNotifyTaskDue(prefs.notify_task_due);
        setPrefNotifyEvidenceExpired(prefs.notify_evidence_expired);
        setPrefNotifyPolicyReview(prefs.notify_policy_review);
        setPrefNotifyFindingRaised(prefs.notify_finding_raised);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load compliance workspace data.");
    } finally {
      setLoading(false);
    }
  }, [tenantId, token, userRole]);

  useEffect(() => {
    let active = true;
    async function init() {
      if (!active) return;
      await loadComplianceData();
    }
    void init();
    return () => {
      active = false;
    };
  }, [loadComplianceData]);

  // Handle Optimistic Concurrency Conflict
  function handleConflictError(err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("version")) {
      setConflictWarning(
        "Optimistic Concurrency Conflict: Another user or job updated this item concurrently. Please refresh data to see the latest version."
      );
    } else {
      setError(msg);
    }
  }

  // Posture Update Handler
  async function handleSavePosture(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedControlForPosture) return;
    setError(null);
    setConflictWarning(null);

    const existingRecord = controlStatuses.find(
      (s) =>
        s.control_type === selectedControlForPosture.type &&
        s.control_id === selectedControlForPosture.id
    );

    try {
      const updated = await upsertControlStatus(
        token,
        tenantId,
        selectedControlForPosture.type,
        selectedControlForPosture.id,
        {
          status: postureStatusInput,
          assigned_owner_user_id: postureOwnerInput || null,
          notes: postureNotesInput || null,
          expected_version: existingRecord ? existingRecord.version : null,
        }
      );

      setControlStatuses((prev) => {
        const next = prev.filter(
          (s) =>
            !(
              s.control_type === selectedControlForPosture.type &&
              s.control_id === selectedControlForPosture.id
            )
        );
        return [...next, updated];
      });

      setSelectedControlForPosture(null);
      setSuccessMessage(`Posture for ${selectedControlForPosture.identifier} updated successfully.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Create Evidence Handler
  async function handleCreateEvidence(e: React.FormEvent) {
    e.preventDefault();
    if (!newEvidenceTitle.trim()) return;
    setError(null);
    try {
      const created = await createEvidence(token, tenantId, {
        title: newEvidenceTitle.trim(),
        description: newEvidenceDesc.trim(),
        classification: newEvidenceClass,
        owner_user_id: currentUserId || "system",
        valid_from: newEvidenceValidFrom || null,
        valid_until: newEvidenceValidUntil || null,
        restricted_notes: newEvidenceRestrictedNotes || null,
      });
      setEvidenceItems((prev) => [created, ...prev]);
      setShowCreateEvidence(false);
      setNewEvidenceTitle("");
      setNewEvidenceDesc("");
      setNewEvidenceRestrictedNotes("");
      setSuccessMessage("Evidence record created successfully.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Transition Evidence Status Handler
  async function handleTransitionEvidence(targetStatus: EvidenceStatus) {
    if (!selectedEvidenceForDetail) return;
    setError(null);
    setConflictWarning(null);
    try {
      const transitioned = await transitionEvidence(
        token,
        tenantId,
        selectedEvidenceForDetail.id,
        {
          target_status: targetStatus,
          expected_version: selectedEvidenceForDetail.version,
          reason: transitionReason || undefined,
        }
      );
      setEvidenceItems((prev) =>
        prev.map((e) => (e.id === transitioned.id ? transitioned : e))
      );
      setSelectedEvidenceForDetail(transitioned);
      setTransitionReason("");
      setSuccessMessage(`Evidence status changed to ${targetStatus}.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Attach File to Evidence
  async function handleAttachFile() {
    if (!selectedEvidenceForDetail || !newFileIdToAttach.trim()) return;
    setError(null);
    try {
      const link = await attachFileToEvidence(
        token,
        tenantId,
        selectedEvidenceForDetail.id,
        newFileIdToAttach.trim()
      );
      const updatedItem: EvidenceItemSummary = {
        ...selectedEvidenceForDetail,
        file_links: [...(selectedEvidenceForDetail.file_links ?? []), link],
      };
      setSelectedEvidenceForDetail(updatedItem);
      setEvidenceItems((prev) =>
        prev.map((e) => (e.id === updatedItem.id ? updatedItem : e))
      );
      setNewFileIdToAttach("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach file.");
    }
  }

  // Remove File from Evidence
  async function handleRemoveFile(fileId: string) {
    if (!selectedEvidenceForDetail) return;
    setError(null);
    try {
      await removeFileFromEvidence(token, tenantId, selectedEvidenceForDetail.id, fileId);
      const updatedItem: EvidenceItemSummary = {
        ...selectedEvidenceForDetail,
        file_links: (selectedEvidenceForDetail.file_links ?? []).filter(
          (f: EvidenceFileLinkSummary) => f.file_id !== fileId
        ),
      };
      setSelectedEvidenceForDetail(updatedItem);
      setEvidenceItems((prev) =>
        prev.map((e) => (e.id === updatedItem.id ? updatedItem : e))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove file.");
    }
  }

  // Link Control to Evidence
  async function handleLinkControlToEvidence() {
    if (!selectedEvidenceForDetail || !linkControlId) return;
    setError(null);
    try {
      const link = await linkControlToEvidence(
        token,
        tenantId,
        selectedEvidenceForDetail.id,
        linkControlType,
        linkControlId
      );
      const updatedItem: EvidenceItemSummary = {
        ...selectedEvidenceForDetail,
        control_links: [...(selectedEvidenceForDetail.control_links ?? []), link],
      };
      setSelectedEvidenceForDetail(updatedItem);
      setEvidenceItems((prev) =>
        prev.map((e) => (e.id === updatedItem.id ? updatedItem : e))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to link control.");
    }
  }

  // Unlink Control from Evidence
  async function handleUnlinkControlFromEvidence(ctrlType: ControlEntityType, ctrlId: string) {
    if (!selectedEvidenceForDetail) return;
    setError(null);
    try {
      await unlinkControlFromEvidence(
        token,
        tenantId,
        selectedEvidenceForDetail.id,
        ctrlType,
        ctrlId
      );
      const updatedItem: EvidenceItemSummary = {
        ...selectedEvidenceForDetail,
        control_links: (selectedEvidenceForDetail.control_links ?? []).filter(
          (c: EvidenceControlLinkSummary) =>
            !(c.control_type === ctrlType && c.control_id === ctrlId)
        ),
      };
      setSelectedEvidenceForDetail(updatedItem);
      setEvidenceItems((prev) =>
        prev.map((e) => (e.id === updatedItem.id ? updatedItem : e))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlink control.");
    }
  }

  // Policy Lifecycle Handlers
  async function handleCreatePolicy(e: React.FormEvent) {
    e.preventDefault();
    if (!newPolicyTitle.trim()) return;
    setError(null);
    try {
      const created = await createPolicy(token, tenantId, {
        title: newPolicyTitle.trim(),
        description: newPolicyDesc.trim(),
        version_string: newPolicyVersionStr.trim(),
        review_cycle_days: Number(newPolicyCycleDays) || 365,
        classification: newPolicyClass,
        content: newPolicyContent || null,
        restricted_content: newPolicyRestrictedContent || null,
      });
      setPolicies((prev) => [created, ...prev]);
      setShowCreatePolicy(false);
      setNewPolicyTitle("");
      setNewPolicyDesc("");
      setNewPolicyContent("");
      setNewPolicyRestrictedContent("");
      setSuccessMessage("Policy created successfully.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handleSubmitPolicyReview(p: PolicySummary) {
    setError(null);
    setConflictWarning(null);
    try {
      const res = await submitPolicyReview(token, tenantId, p.id, p.version);
      setPolicies((prev) => prev.map((item) => (item.id === res.id ? res : item)));
      setSuccessMessage(`Policy "${p.title}" submitted for review.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handleApprovePolicy(p: PolicySummary) {
    setError(null);
    setConflictWarning(null);
    // Independent 2-person approval check
    if (currentUserId && p.owner_user_id === currentUserId) {
      setError(
        "Independent 2-Person Approval Required: The author/owner cannot approve their own policy. Another authorized user must review and approve it."
      );
      return;
    }
    try {
      const res = await approvePolicy(token, tenantId, p.id, p.version);
      setPolicies((prev) => prev.map((item) => (item.id === res.id ? res : item)));
      setSuccessMessage(`Policy "${p.title}" approved successfully.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handlePublishPolicy(p: PolicySummary) {
    setError(null);
    setConflictWarning(null);
    try {
      const res = await publishPolicy(token, tenantId, p.id, p.version);
      setPolicies((prev) => prev.map((item) => (item.id === res.id ? res : item)));
      setSuccessMessage(`Policy "${p.title}" is now published.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handleArchivePolicy(p: PolicySummary) {
    setError(null);
    setConflictWarning(null);
    try {
      const res = await archivePolicy(token, tenantId, p.id, p.version);
      setPolicies((prev) => prev.map((item) => (item.id === res.id ? res : item)));
      setSuccessMessage(`Policy "${p.title}" has been archived.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Link Control to Policy
  async function handleLinkControlToPolicy() {
    if (!selectedPolicyForDetail || !policyLinkControlId) return;
    setError(null);
    try {
      const link = await linkControlToPolicy(
        token,
        tenantId,
        selectedPolicyForDetail.id,
        policyLinkControlType,
        policyLinkControlId
      );
      const updatedPolicy: PolicySummary = {
        ...selectedPolicyForDetail,
        control_links: [...(selectedPolicyForDetail.control_links ?? []), link],
      };
      setSelectedPolicyForDetail(updatedPolicy);
      setPolicies((prev) =>
        prev.map((p) => (p.id === updatedPolicy.id ? updatedPolicy : p))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to link control to policy.");
    }
  }

  // Unlink Control from Policy
  async function handleUnlinkControlFromPolicy(ctrlType: ControlEntityType, ctrlId: string) {
    if (!selectedPolicyForDetail) return;
    setError(null);
    try {
      await unlinkControlFromPolicy(
        token,
        tenantId,
        selectedPolicyForDetail.id,
        ctrlType,
        ctrlId
      );
      const updatedPolicy: PolicySummary = {
        ...selectedPolicyForDetail,
        control_links: (selectedPolicyForDetail.control_links ?? []).filter(
          (c: PolicyControlLinkSummary) =>
            !(c.control_type === ctrlType && c.control_id === ctrlId)
        ),
      };
      setSelectedPolicyForDetail(updatedPolicy);
      setPolicies((prev) =>
        prev.map((p) => (p.id === updatedPolicy.id ? updatedPolicy : p))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to unlink control.");
    }
  }

  // Task Handlers
  async function handleCreateTask(e: React.FormEvent) {
    e.preventDefault();
    if (!newTaskTitle.trim() || !newTaskDueDate) return;
    setError(null);
    try {
      const created = await createTask(token, tenantId, {
        title: newTaskTitle.trim(),
        description: newTaskDesc.trim(),
        due_date: new Date(newTaskDueDate).toISOString(),
        priority: newTaskPriority,
        assignee_user_id: newTaskAssignee || null,
      });
      setTasks((prev) => [created, ...prev]);
      setShowCreateTask(false);
      setNewTaskTitle("");
      setNewTaskDesc("");
      setNewTaskDueDate("");
      setSuccessMessage("Compliance task created successfully.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handleCompleteTask(t: ComplianceTaskSummary) {
    setError(null);
    setConflictWarning(null);
    try {
      const completed = await completeTask(token, tenantId, t.id, t.version);
      setTasks((prev) => prev.map((item) => (item.id === completed.id ? completed : item)));
      setSuccessMessage(`Task "${t.title}" marked as completed.`);
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Finding Handlers
  async function handleCreateFinding(e: React.FormEvent) {
    e.preventDefault();
    if (!newFindingTitle.trim()) return;
    setError(null);
    try {
      const created = await createFinding(token, tenantId, {
        title: newFindingTitle.trim(),
        description: newFindingDesc.trim(),
        severity: newFindingSeverity,
        due_date: newFindingDueDate ? new Date(newFindingDueDate).toISOString() : null,
        remediation_plan: newFindingPlan || null,
      });
      setFindings((prev) => [created, ...prev]);
      setShowCreateFinding(false);
      setNewFindingTitle("");
      setNewFindingDesc("");
      setNewFindingDueDate("");
      setNewFindingPlan("");
      setSuccessMessage("Finding reported successfully.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  async function handleRemediateFinding(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFindingForRemediation) return;
    setError(null);
    setConflictWarning(null);
    try {
      const updated = await remediateFinding(
        token,
        tenantId,
        selectedFindingForRemediation.id,
        {
          expected_version: selectedFindingForRemediation.version,
          remediation_status: remediationStatusInput,
          remediation_summary: remediationSummaryInput || null,
        }
      );
      setFindings((prev) =>
        prev.map((f) => (f.id === updated.id ? updated : f))
      );
      setSelectedFindingForRemediation(null);
      setRemediationSummaryInput("");
      setSuccessMessage("Remediation record updated successfully.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      handleConflictError(err);
    }
  }

  // Preferences Update Handler
  async function handleSavePreferences(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const updated = await updateUserPreferences(token, tenantId, {
        email_enabled: prefEmailEnabled,
        digest_frequency: prefDigestFrequency,
        notify_task_assigned: prefNotifyTaskAssigned,
        notify_task_due: prefNotifyTaskDue,
        notify_evidence_expired: prefNotifyEvidenceExpired,
        notify_policy_review: prefNotifyPolicyReview,
        notify_finding_raised: prefNotifyFindingRaised,
      });
      setUserPrefs(updated);
      setSuccessMessage("Notification preferences saved.");
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences.");
    }
  }

  // Deterministic Automation Trigger Handler
  async function handleRunJobs() {
    setRunningJobs(true);
    setError(null);
    try {
      const result = await runComplianceJobs(token, tenantId);
      setLastJobResult(result);
      // Reload evidence, tasks, and policies to reflect state updates
      await loadComplianceData();
      const totalAlerts =
        result.expired_evidence.alerts_enqueued +
        result.overdue_tasks.alerts_enqueued +
        result.policy_alerts.alerts_enqueued;
      setSuccessMessage(
        `Deterministic jobs executed successfully: ${totalAlerts} notifications queued.`
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run deterministic compliance jobs.");
    } finally {
      setRunningJobs(false);
    }
  }

  if (loading) {
    return <p>Loading compliance workspace...</p>;
  }

  // Posture metrics calculations
  const totalControls = unifiedControls.length;
  const implementedCount = controlStatuses.filter((s) => s.status === "implemented").length;
  const inProgressCount = controlStatuses.filter((s) => s.status === "in_progress").length;
  const assessedCount = controlStatuses.filter((s) => s.status === "assessed").length;
  const notStartedCount = Math.max(0, totalControls - implementedCount - inProgressCount - assessedCount);
  const compliancePercent = totalControls > 0 ? Math.round(((implementedCount + assessedCount) / totalControls) * 100) : 0;

  return (
    <div style={{ marginTop: "1rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.5rem" }}>Compliance Workspace</h2>
          <p style={{ margin: "0.25rem 0 0", color: "#4a5d55", fontSize: "0.875rem" }}>
            Operational compliance, evidence governance, versioned policies, and audit readiness.
          </p>
        </div>
        <button
          className="secondary"
          onClick={() => void loadComplianceData()}
          title="Refresh latest state from server"
        >
          Refresh Data
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {conflictWarning && (
        <div className="alert alert-conflict">
          <strong>Conflict Detected: </strong>
          {conflictWarning}
        </div>
      )}
      {successMessage && <div className="alert alert-success">{successMessage}</div>}

      {/* Subnavigation Tabs */}
      <div className="subnav" role="tablist" aria-label="Compliance Modules">
        <button
          className={`subnav-tab ${activeTab === "posture" ? "active" : ""}`}
          onClick={() => setActiveTab("posture")}
          role="tab"
          aria-selected={activeTab === "posture"}
        >
          Control Posture Matrix ({totalControls})
        </button>
        {canReadEvidence(userRole) && (
          <button
            className={`subnav-tab ${activeTab === "evidence" ? "active" : ""}`}
            onClick={() => setActiveTab("evidence")}
            role="tab"
            aria-selected={activeTab === "evidence"}
          >
            Evidence Repository ({evidenceItems.length})
          </button>
        )}
        {canReadPolicies(userRole) && (
          <button
            className={`subnav-tab ${activeTab === "policies" ? "active" : ""}`}
            onClick={() => setActiveTab("policies")}
            role="tab"
            aria-selected={activeTab === "policies"}
          >
            Policy Center ({policies.length})
          </button>
        )}
        <button
          className={`subnav-tab ${activeTab === "tasks" ? "active" : ""}`}
          onClick={() => setActiveTab("tasks")}
          role="tab"
          aria-selected={activeTab === "tasks"}
        >
          Tasks & Actions ({tasks.filter((t) => t.status !== "completed").length})
        </button>
        <button
          className={`subnav-tab ${activeTab === "findings" ? "active" : ""}`}
          onClick={() => setActiveTab("findings")}
          role="tab"
          aria-selected={activeTab === "findings"}
        >
          Findings & Remediation ({findings.filter((f) => f.remediation_status !== "resolved").length})
        </button>
        <button
          className={`subnav-tab ${activeTab === "automation" ? "active" : ""}`}
          onClick={() => setActiveTab("automation")}
          role="tab"
          aria-selected={activeTab === "automation"}
        >
          Preferences & Deterministic Automation
        </button>
      </div>

      {/* TAB 1: CONTROL POSTURE MATRIX */}
      {activeTab === "posture" && (
        <div>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-label">Readiness Score</div>
              <div className="stat-value">{compliancePercent}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Implemented</div>
              <div className="stat-value" style={{ color: "#166534" }}>
                {implementedCount}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">In Progress</div>
              <div className="stat-value" style={{ color: "#92400e" }}>
                {inProgressCount}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Assessed</div>
              <div className="stat-value" style={{ color: "#075985" }}>
                {assessedCount}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Not Started</div>
              <div className="stat-value" style={{ color: "#6b7280" }}>
                {notStartedCount}
              </div>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Identifier</th>
                  <th>Control Title</th>
                  <th>Source / Framework</th>
                  <th>Category</th>
                  <th>Implementation Status</th>
                  <th>Owner</th>
                  {canManageControlStatus(userRole) && <th>Action</th>}
                </tr>
              </thead>
              <tbody>
                {unifiedControls.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>
                      No controls found. Adopt a framework version or create custom controls first.
                    </td>
                  </tr>
                ) : (
                  unifiedControls.map((ctrl) => {
                    const statusRecord = controlStatuses.find(
                      (s) => s.control_type === ctrl.type && s.control_id === ctrl.id
                    );
                    const statusVal = statusRecord?.status ?? "not_started";
                    const badgeClass =
                      statusVal === "implemented"
                        ? "badge-success"
                        : statusVal === "assessed"
                        ? "badge-info"
                        : statusVal === "in_progress"
                        ? "badge-warning"
                        : "badge-neutral";

                    return (
                      <tr key={`${ctrl.type}-${ctrl.id}`}>
                        <td>
                          <strong>{ctrl.identifier}</strong>
                        </td>
                        <td>{ctrl.title}</td>
                        <td>
                          <span style={{ fontSize: "0.8rem", color: "#4a5d55" }}>
                            {ctrl.frameworkName}
                          </span>
                        </td>
                        <td>{ctrl.category}</td>
                        <td>
                          <span className={`badge ${badgeClass}`}>
                            {statusVal.replace("_", " ")}
                          </span>
                        </td>
                        <td>
                          <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                            {statusRecord?.assigned_owner_user_id || "Unassigned"}
                          </span>
                        </td>
                        {canManageControlStatus(userRole) && (
                          <td>
                            <button
                              className="secondary"
                              style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem", minHeight: "auto" }}
                              onClick={() => {
                                setSelectedControlForPosture(ctrl);
                                setPostureStatusInput(statusVal);
                                setPostureOwnerInput(statusRecord?.assigned_owner_user_id ?? "");
                                setPostureNotesInput(statusRecord?.notes ?? "");
                              }}
                            >
                              Update Posture
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: EVIDENCE REPOSITORY */}
      {activeTab === "evidence" && canReadEvidence(userRole) && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="ev-filter" style={{ margin: 0, fontWeight: 600, fontSize: "0.875rem" }}>
                Filter Status:
              </label>
              <select
                id="ev-filter"
                value={evidenceStatusFilter}
                onChange={(e) => setEvidenceStatusFilter(e.target.value)}
                style={{ width: "auto", minHeight: "2.2rem", padding: "0.25rem 0.5rem" }}
              >
                <option value="all">All Statuses</option>
                <option value="draft">Draft</option>
                <option value="submitted">Submitted</option>
                <option value="valid">Valid</option>
                <option value="expired">Expired</option>
                <option value="rejected">Rejected</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            {canManageEvidence(userRole) && (
              <button onClick={() => setShowCreateEvidence(true)}>
                + New Evidence Item
              </button>
            )}
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Status</th>
                  <th>Classification</th>
                  <th>Version</th>
                  <th>Validity Window</th>
                  <th>Attachments</th>
                  <th>Controls</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {evidenceItems
                  .filter((e) => evidenceStatusFilter === "all" || e.status === evidenceStatusFilter)
                  .map((item) => {
                    const statusBadge =
                      item.status === "valid"
                        ? "badge-success"
                        : item.status === "submitted"
                        ? "badge-warning"
                        : item.status === "expired" || item.status === "rejected"
                        ? "badge-danger"
                        : "badge-neutral";

                    const classBadge =
                      item.classification === "Restricted"
                        ? "badge-danger"
                        : item.classification === "Confidential"
                        ? "badge-warning"
                        : "badge-neutral";

                    return (
                      <tr key={item.id}>
                        <td>
                          <strong>{item.title}</strong>
                          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                            {item.description.slice(0, 70)}...
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${statusBadge}`}>{item.status.replace("_", " ")}</span>
                        </td>
                        <td>
                          <span className={`badge ${classBadge}`}>{item.classification}</span>
                        </td>
                        <td>v{item.version}</td>
                        <td style={{ fontSize: "0.8rem" }}>
                          {item.valid_until ? (
                            <span>Until {item.valid_until.slice(0, 10)}</span>
                          ) : (
                            <span style={{ color: "#6b7280" }}>No expiry</span>
                          )}
                        </td>
                        <td>{(item.file_links ?? []).length} file(s)</td>
                        <td>{(item.control_links ?? []).length} linked</td>
                        <td>
                          <button
                            className="secondary"
                            style={{ padding: "0.3rem 0.6rem", fontSize: "0.75rem", minHeight: "auto" }}
                            onClick={() => setSelectedEvidenceForDetail(item)}
                          >
                            Inspect & Manage
                          </button>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: POLICY CENTER */}
      {activeTab === "policies" && canReadPolicies(userRole) && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="pol-filter" style={{ margin: 0, fontWeight: 600, fontSize: "0.875rem" }}>
                Filter Status:
              </label>
              <select
                id="pol-filter"
                value={policyStatusFilter}
                onChange={(e) => setPolicyStatusFilter(e.target.value)}
                style={{ width: "auto", minHeight: "2.2rem", padding: "0.25rem 0.5rem" }}
              >
                <option value="all">All Statuses</option>
                <option value="draft">Draft</option>
                <option value="in_review">In Review</option>
                <option value="approved">Approved</option>
                <option value="published">Published</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            {canManagePolicies(userRole) && (
              <button onClick={() => setShowCreatePolicy(true)}>
                + New Policy
              </button>
            )}
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Classification</th>
                  <th>Next Review Due</th>
                  <th>Controls Linked</th>
                  <th>Lifecycle Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies
                  .filter((p) => policyStatusFilter === "all" || p.status === policyStatusFilter)
                  .map((policy) => {
                    const statusBadge =
                      policy.status === "published"
                        ? "badge-success"
                        : policy.status === "approved"
                        ? "badge-info"
                        : policy.status === "in_review"
                        ? "badge-warning"
                        : policy.status === "archived"
                        ? "badge-danger"
                        : "badge-neutral";

                    return (
                      <tr key={policy.id}>
                        <td>
                          <strong>{policy.title}</strong>
                          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                            {policy.description.slice(0, 60)}...
                          </div>
                        </td>
                        <td>v{policy.version_string} (rev {policy.version})</td>
                        <td>
                          <span className={`badge ${statusBadge}`}>{policy.status.replace("_", " ")}</span>
                        </td>
                        <td>
                          <span className="badge badge-neutral">{policy.classification}</span>
                        </td>
                        <td style={{ fontSize: "0.8rem" }}>
                          {policy.next_review_due ? policy.next_review_due.slice(0, 10) : "Not scheduled"}
                        </td>
                        <td>
                          <button
                            className="secondary"
                            style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                            onClick={() => setSelectedPolicyForDetail(policy)}
                          >
                            {(policy.control_links ?? []).length} controls (Manage)
                          </button>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
                            {canManagePolicies(userRole) && policy.status === "draft" && (
                              <button
                                style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                                onClick={() => void handleSubmitPolicyReview(policy)}
                              >
                                Submit Review
                              </button>
                            )}
                            {canManagePolicies(userRole) && policy.status === "in_review" && (
                              <button
                                style={{
                                  padding: "0.25rem 0.5rem",
                                  fontSize: "0.75rem",
                                  minHeight: "auto",
                                  backgroundColor: "#059669",
                                }}
                                onClick={() => void handleApprovePolicy(policy)}
                                title="Requires independent 2-person approval (approver cannot be author)"
                              >
                                Approve (2-Person)
                              </button>
                            )}
                            {canManagePolicies(userRole) && policy.status === "approved" && (
                              <button
                                style={{
                                  padding: "0.25rem 0.5rem",
                                  fontSize: "0.75rem",
                                  minHeight: "auto",
                                  backgroundColor: "#16a34a",
                                }}
                                onClick={() => void handlePublishPolicy(policy)}
                              >
                                Publish
                              </button>
                            )}
                            {canManagePolicies(userRole) && policy.status === "published" && (
                              <button
                                className="secondary"
                                style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                                onClick={() => void handleArchivePolicy(policy)}
                              >
                                Archive
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: TASKS & ACTIONS */}
      {activeTab === "tasks" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="tsk-filter" style={{ margin: 0, fontWeight: 600, fontSize: "0.875rem" }}>
                Filter Status:
              </label>
              <select
                id="tsk-filter"
                value={taskStatusFilter}
                onChange={(e) => setTaskStatusFilter(e.target.value)}
                style={{ width: "auto", minHeight: "2.2rem", padding: "0.25rem 0.5rem" }}
              >
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="overdue">Overdue</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            {canManageTasks(userRole) && (
              <button onClick={() => setShowCreateTask(true)}>
                + Create Task
              </button>
            )}
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Due Date</th>
                  <th>Assignee</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasks
                  .filter((t) => taskStatusFilter === "all" || t.status === taskStatusFilter)
                  .map((task) => {
                    const isOverdue =
                      task.status !== "completed" &&
                      task.status !== "cancelled" &&
                      new Date(task.due_date).getTime() < now;

                    const prioBadge =
                      task.priority === "critical"
                        ? "badge-danger"
                        : task.priority === "high"
                        ? "badge-warning"
                        : "badge-neutral";

                    const statusBadge =
                      task.status === "completed"
                        ? "badge-success"
                        : task.status === "in_progress"
                        ? "badge-info"
                        : task.status === "overdue"
                        ? "badge-danger"
                        : "badge-neutral";

                    return (
                      <tr key={task.id}>
                        <td>
                          <strong>{task.title}</strong>
                          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                            {task.description.slice(0, 60)}
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${prioBadge}`}>{task.priority}</span>
                        </td>
                        <td>
                          <span className={`badge ${statusBadge}`}>{task.status.replace("_", " ")}</span>
                        </td>
                        <td>
                          <span style={{ color: isOverdue ? "#dc2626" : "inherit", fontWeight: isOverdue ? 700 : 400 }}>
                            {task.due_date.slice(0, 10)} {isOverdue && "(Overdue)"}
                          </span>
                        </td>
                        <td style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                          {task.assignee_user_id || "Unassigned"}
                        </td>
                        <td>
                          {canManageTasks(userRole) && task.status !== "completed" && (
                            <button
                              style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto", backgroundColor: "#16a34a" }}
                              onClick={() => void handleCompleteTask(task)}
                            >
                              Mark Complete
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: FINDINGS & REMEDIATION */}
      {activeTab === "findings" && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
              <label htmlFor="fnd-filter" style={{ margin: 0, fontWeight: 600, fontSize: "0.875rem" }}>
                Filter Severity:
              </label>
              <select
                id="fnd-filter"
                value={findingSeverityFilter}
                onChange={(e) => setFindingSeverityFilter(e.target.value)}
                style={{ width: "auto", minHeight: "2.2rem", padding: "0.25rem 0.5rem" }}
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
            {canManageFindings(userRole) && (
              <button onClick={() => setShowCreateFinding(true)}>
                + Report Finding
              </button>
            )}
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Remediation Status</th>
                  <th>Due Date</th>
                  <th>Remediation Summary</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {findings
                  .filter((f) => findingSeverityFilter === "all" || f.severity === findingSeverityFilter)
                  .map((finding) => {
                    const sevBadge =
                      finding.severity === "critical"
                        ? "badge-danger"
                        : finding.severity === "high"
                        ? "badge-warning"
                        : "badge-neutral";

                    const remBadge =
                      finding.remediation_status === "resolved"
                        ? "badge-success"
                        : finding.remediation_status === "in_remediation"
                        ? "badge-info"
                        : "badge-danger";

                    return (
                      <tr key={finding.id}>
                        <td>
                          <strong>{finding.title}</strong>
                          <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>
                            {finding.description.slice(0, 60)}
                          </div>
                        </td>
                        <td>
                          <span className={`badge ${sevBadge}`}>{finding.severity}</span>
                        </td>
                        <td>
                          <span className={`badge ${remBadge}`}>{finding.remediation_status.replace("_", " ")}</span>
                        </td>
                        <td style={{ fontSize: "0.8rem" }}>
                          {finding.due_date ? finding.due_date.slice(0, 10) : "None"}
                        </td>
                        <td style={{ fontSize: "0.8rem", color: "#4a5d55" }}>
                          {finding.remediation_summary || "Pending"}
                        </td>
                        <td>
                          {canManageFindings(userRole) && (
                            <button
                              className="secondary"
                              style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem", minHeight: "auto" }}
                              onClick={() => {
                                setSelectedFindingForRemediation(finding);
                                setRemediationStatusInput(finding.remediation_status);
                                setRemediationSummaryInput(finding.remediation_summary || "");
                              }}
                            >
                              Update Remediation
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: PREFERENCES & DETERMINISTIC AUTOMATION */}
      {activeTab === "automation" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
          {/* User Preferences Form */}
          <div className="card">
            <h3 style={{ margin: "0 0 1rem" }}>Notification Preferences</h3>
            <form onSubmit={(e) => void handleSavePreferences(e)}>
              <div style={{ marginBottom: "1rem" }}>
                <label style={{ margin: "0 0 0.25rem" }}>
                  <input
                    type="checkbox"
                    checked={prefEmailEnabled}
                    onChange={(e) => setPrefEmailEnabled(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Enable Email Notifications
                </label>
              </div>

              <div style={{ marginBottom: "1rem" }}>
                <label htmlFor="pref-digest" style={{ margin: "0 0 0.25rem" }}>
                  Digest Frequency
                </label>
                <select
                  id="pref-digest"
                  value={prefDigestFrequency}
                  onChange={(e) => setPrefDigestFrequency(e.target.value as DigestFrequency)}
                >
                  <option value="immediate">Immediate</option>
                  <option value="daily">Daily Digest</option>
                  <option value="weekly">Weekly Digest</option>
                  <option value="never">Never</option>
                </select>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1.5rem" }}>
                <label style={{ margin: 0, fontWeight: "normal" }}>
                  <input
                    type="checkbox"
                    checked={prefNotifyTaskAssigned}
                    onChange={(e) => setPrefNotifyTaskAssigned(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Notify on Task Assignment
                </label>
                <label style={{ margin: 0, fontWeight: "normal" }}>
                  <input
                    type="checkbox"
                    checked={prefNotifyTaskDue}
                    onChange={(e) => setPrefNotifyTaskDue(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Notify on Task Due Date Warning
                </label>
                <label style={{ margin: 0, fontWeight: "normal" }}>
                  <input
                    type="checkbox"
                    checked={prefNotifyEvidenceExpired}
                    onChange={(e) => setPrefNotifyEvidenceExpired(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Notify on Evidence Expiration
                </label>
                <label style={{ margin: 0, fontWeight: "normal" }}>
                  <input
                    type="checkbox"
                    checked={prefNotifyPolicyReview}
                    onChange={(e) => setPrefNotifyPolicyReview(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Notify on Policy Review Due
                </label>
                <label style={{ margin: 0, fontWeight: "normal" }}>
                  <input
                    type="checkbox"
                    checked={prefNotifyFindingRaised}
                    onChange={(e) => setPrefNotifyFindingRaised(e.target.checked)}
                    style={{ marginRight: "0.5rem" }}
                  />
                  Notify on Finding Raised
                </label>
              </div>

              <button type="submit">Save Preferences</button>
            </form>
          </div>

          {/* Deterministic Automation Jobs */}
          <div className="card">
            <h3 style={{ margin: "0 0 1rem" }}>Deterministic Automation Jobs</h3>
            <p style={{ fontSize: "0.875rem", color: "#4a5d55", lineHeight: 1.5 }}>
              Executes deterministic compliance checks without autonomous AI agents:
            </p>
            <ul style={{ fontSize: "0.875rem", color: "#4a5d55", paddingLeft: "1.25rem", margin: "0.5rem 0 1.5rem" }}>
              <li>Transitions expired evidence to <code>expired</code> state.</li>
              <li>Generates overdue task notifications with deduplicated idempotency keys.</li>
              <li>Calculates policy review reminders (30 days prior to review due date).</li>
              <li>Enqueues notifications with application-layer encryption in the outbox.</li>
            </ul>

            <button
              onClick={() => void handleRunJobs()}
              disabled={runningJobs}
              style={{ width: "100%", marginBottom: "1rem" }}
            >
              {runningJobs ? "Executing Deterministic Checks..." : "Run Compliance Checks Now"}
            </button>

            {lastJobResult && (
              <div style={{ background: "var(--bg-card)", padding: "1rem", borderRadius: "0.5rem", border: "1px solid var(--border-default)", fontSize: "0.875rem" }}>
                <strong style={{ color: "var(--accent)" }}>Last Run Summary:</strong>
                <div style={{ marginTop: "0.5rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                  <div>Evidence Checked: <strong>{lastJobResult.expired_evidence.processed_count}</strong></div>
                  <div>Evidence Alerts: <strong>{lastJobResult.expired_evidence.alerts_enqueued}</strong></div>
                  <div>Tasks Checked: <strong>{lastJobResult.overdue_tasks.processed_count}</strong></div>
                  <div>Tasks Alerts: <strong>{lastJobResult.overdue_tasks.alerts_enqueued}</strong></div>
                  <div>Policies Checked: <strong>{lastJobResult.policy_alerts.processed_count}</strong></div>
                  <div>Policy Alerts: <strong>{lastJobResult.policy_alerts.alerts_enqueued}</strong></div>
                  <div style={{ gridColumn: "1 / -1", color: "var(--color-success)" }}>
                    Total Notifications Queued:{" "}
                    <strong>
                      {lastJobResult.expired_evidence.alerts_enqueued +
                        lastJobResult.overdue_tasks.alerts_enqueued +
                        lastJobResult.policy_alerts.alerts_enqueued}
                    </strong>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL: POSTURE UPDATE */}
      {selectedControlForPosture && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Update Posture: {selectedControlForPosture.identifier}</h3>
            <p style={{ color: "#6b7280", fontSize: "0.875rem", margin: "0 0 1rem" }}>
              {selectedControlForPosture.title}
            </p>
            <form onSubmit={(e) => void handleSavePosture(e)}>
              <label htmlFor="posture-status">Implementation Status</label>
              <select
                id="posture-status"
                value={postureStatusInput}
                onChange={(e) => setPostureStatusInput(e.target.value as ControlImplementationStatus)}
              >
                <option value="not_started">Not Started</option>
                <option value="in_progress">In Progress</option>
                <option value="implemented">Implemented</option>
                <option value="assessed">Assessed</option>
              </select>

              <label htmlFor="posture-owner">Assigned Owner User ID</label>
              <input
                id="posture-owner"
                type="text"
                value={postureOwnerInput}
                onChange={(e) => setPostureOwnerInput(e.target.value)}
                placeholder="User UUID or email"
              />

              <label htmlFor="posture-notes">Operational Notes</label>
              <textarea
                id="posture-notes"
                rows={3}
                value={postureNotesInput}
                onChange={(e) => setPostureNotesInput(e.target.value)}
                placeholder="Document control execution, testing cadence, or audit evidence locations"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setSelectedControlForPosture(null)}
                >
                  Cancel
                </button>
                <button type="submit">Save Posture</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: CREATE EVIDENCE */}
      {showCreateEvidence && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Create Evidence Item</h3>
            <form onSubmit={(e) => void handleCreateEvidence(e)}>
              <label htmlFor="ev-title">Title *</label>
              <input
                id="ev-title"
                type="text"
                required
                value={newEvidenceTitle}
                onChange={(e) => setNewEvidenceTitle(e.target.value)}
                placeholder="e.g. AWS Production Security Group Audit"
              />

              <label htmlFor="ev-desc">Description *</label>
              <textarea
                id="ev-desc"
                rows={3}
                required
                value={newEvidenceDesc}
                onChange={(e) => setNewEvidenceDesc(e.target.value)}
                placeholder="Describe the proof and verification methodology"
              />

              <label htmlFor="ev-class">Data Classification</label>
              <select
                id="ev-class"
                value={newEvidenceClass}
                onChange={(e) => setNewEvidenceClass(e.target.value as DataClassification)}
              >
                <option value="Public">Public</option>
                <option value="Internal">Internal</option>
                <option value="Confidential">Confidential</option>
                <option value="Restricted">Restricted (Envelope Encrypted)</option>
              </select>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label htmlFor="ev-from">Valid From</label>
                  <input
                    id="ev-from"
                    type="date"
                    value={newEvidenceValidFrom}
                    onChange={(e) => setNewEvidenceValidFrom(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="ev-until">Valid Until</label>
                  <input
                    id="ev-until"
                    type="date"
                    value={newEvidenceValidUntil}
                    onChange={(e) => setNewEvidenceValidUntil(e.target.value)}
                  />
                </div>
              </div>

              <label htmlFor="ev-rest">Restricted Notes (AES-256-GCM Envelope Encrypted)</label>
              <textarea
                id="ev-rest"
                rows={2}
                value={newEvidenceRestrictedNotes}
                onChange={(e) => setNewEvidenceRestrictedNotes(e.target.value)}
                placeholder="Highly sensitive auditor remarks, key identifiers, or credential references"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowCreateEvidence(false)}
                >
                  Cancel
                </button>
                <button type="submit">Create Evidence</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: INSPECT & MANAGE EVIDENCE */}
      {selectedEvidenceForDetail && (
        <div className="modal-backdrop">
          <div className="modal-dialog" style={{ width: "min(100%, 46rem)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <h3 style={{ margin: 0 }}>Evidence: {selectedEvidenceForDetail.title}</h3>
                <p style={{ margin: "0.25rem 0", color: "#6b7280", fontSize: "0.875rem" }}>
                  Status: <strong>{selectedEvidenceForDetail.status}</strong> | Version: <strong>v{selectedEvidenceForDetail.version}</strong>
                </p>
              </div>
              <button
                className="secondary"
                style={{ padding: "0.25rem 0.5rem", minHeight: "auto" }}
                onClick={() => setSelectedEvidenceForDetail(null)}
              >
                Close
              </button>
            </div>

            <p style={{ fontSize: "0.875rem", margin: "1rem 0" }}>
              {selectedEvidenceForDetail.description}
            </p>

            {selectedEvidenceForDetail.restricted_notes && (
              <div className="alert alert-info" style={{ fontSize: "0.8rem" }}>
                <strong>Restricted Notes (Decrypted via Envelope Encryption):</strong>
                <p style={{ margin: "0.25rem 0 0" }}>{selectedEvidenceForDetail.restricted_notes}</p>
              </div>
            )}

            {/* Lifecycle Transitions */}
            <div className="card" style={{ padding: "1rem", marginTop: "1rem" }}>
              <h4 style={{ margin: "0 0 0.5rem" }}>Status Transition Pipeline</h4>
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                {selectedEvidenceForDetail.status === "draft" && (
                  <button onClick={() => void handleTransitionEvidence("submitted")}>
                    Submit for Review
                  </button>
                )}
                {selectedEvidenceForDetail.status === "submitted" && (
                  <>
                    <button
                      style={{ backgroundColor: "#16a34a" }}
                      onClick={() => void handleTransitionEvidence("valid")}
                    >
                      Accept & Validate
                    </button>
                    <button
                      style={{ backgroundColor: "#dc2626" }}
                      onClick={() => void handleTransitionEvidence("rejected")}
                    >
                      Reject
                    </button>
                  </>
                )}
                {selectedEvidenceForDetail.status === "valid" && (
                  <>
                    <button
                      className="secondary"
                      onClick={() => void handleTransitionEvidence("expired")}
                    >
                      Mark Expired
                    </button>
                    <button
                      className="secondary"
                      onClick={() => void handleTransitionEvidence("submitted")}
                    >
                      Re-open Review
                    </button>
                  </>
                )}
                {(selectedEvidenceForDetail.status === "expired" || selectedEvidenceForDetail.status === "rejected") && (
                  <button
                    className="secondary"
                    onClick={() => void handleTransitionEvidence("draft")}
                  >
                    Reset to Draft
                  </button>
                )}
              </div>
            </div>

            {/* Linked Files */}
            <div className="card" style={{ padding: "1rem", marginTop: "1rem" }}>
              <h4 style={{ margin: "0 0 0.5rem" }}>
                Attached Storage Files ({(selectedEvidenceForDetail.file_links ?? []).length})
              </h4>
              {(selectedEvidenceForDetail.file_links ?? []).length === 0 ? (
                <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>No files linked yet.</p>
              ) : (
                <ul style={{ fontSize: "0.85rem", paddingLeft: "1.25rem", margin: "0.5rem 0" }}>
                  {(selectedEvidenceForDetail.file_links ?? []).map((f) => (
                    <li key={f.id} style={{ marginBottom: "0.25rem" }}>
                      File UUID: <code>{f.file_id}</code> (Linked at: {f.created_at.slice(0, 10)}){" "}
                      <button
                        className="secondary"
                        style={{ padding: "0.1rem 0.4rem", fontSize: "0.7rem", minHeight: "auto", color: "#dc2626" }}
                        onClick={() => void handleRemoveFile(f.file_id)}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
                <input
                  type="text"
                  placeholder="Paste File ID to attach"
                  value={newFileIdToAttach}
                  onChange={(e) => setNewFileIdToAttach(e.target.value)}
                  style={{ width: "24rem" }}
                />
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void handleAttachFile()}
                >
                  Attach File
                </button>
              </div>
            </div>

            {/* Linked Controls */}
            <div className="card" style={{ padding: "1rem", marginTop: "1rem" }}>
              <h4 style={{ margin: "0 0 0.5rem" }}>
                Linked Framework Controls ({(selectedEvidenceForDetail.control_links ?? []).length})
              </h4>
              {(selectedEvidenceForDetail.control_links ?? []).length === 0 ? (
                <p style={{ fontSize: "0.8rem", color: "#6b7280" }}>No controls linked yet.</p>
              ) : (
                <ul style={{ fontSize: "0.85rem", paddingLeft: "1.25rem", margin: "0.5rem 0" }}>
                  {(selectedEvidenceForDetail.control_links ?? []).map((c) => {
                    const matchedCtrl = unifiedControls.find(
                      (u) => u.type === c.control_type && u.id === c.control_id
                    );
                    return (
                      <li key={c.id} style={{ marginBottom: "0.25rem" }}>
                        <strong>{matchedCtrl ? matchedCtrl.identifier : c.control_id}</strong>:{" "}
                        {matchedCtrl ? matchedCtrl.title : `Control (${c.control_type})`}{" "}
                        <button
                          className="secondary"
                          style={{ padding: "0.1rem 0.4rem", fontSize: "0.7rem", minHeight: "auto", color: "#dc2626" }}
                          onClick={() => void handleUnlinkControlFromEvidence(c.control_type, c.control_id)}
                        >
                          Unlink
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
                <select
                  value={linkControlType}
                  onChange={(e) => setLinkControlType(e.target.value as ControlEntityType)}
                  style={{ width: "auto" }}
                >
                  <option value="canonical">Canonical</option>
                  <option value="custom">Custom</option>
                </select>
                <select
                  value={linkControlId}
                  onChange={(e) => setLinkControlId(e.target.value)}
                  style={{ width: "20rem" }}
                >
                  <option value="">Select a control to link...</option>
                  {unifiedControls
                    .filter((u) => u.type === linkControlType)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.identifier} — {u.title}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void handleLinkControlToEvidence()}
                >
                  Link Control
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CREATE POLICY */}
      {showCreatePolicy && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Create Policy</h3>
            <form onSubmit={(e) => void handleCreatePolicy(e)}>
              <label htmlFor="pol-title">Title *</label>
              <input
                id="pol-title"
                type="text"
                required
                value={newPolicyTitle}
                onChange={(e) => setNewPolicyTitle(e.target.value)}
                placeholder="e.g. Access Control Policy"
              />

              <label htmlFor="pol-desc">Description *</label>
              <textarea
                id="pol-desc"
                rows={2}
                required
                value={newPolicyDesc}
                onChange={(e) => setNewPolicyDesc(e.target.value)}
                placeholder="High-level policy summary and intent"
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label htmlFor="pol-ver">Version Label</label>
                  <input
                    id="pol-ver"
                    type="text"
                    value={newPolicyVersionStr}
                    onChange={(e) => setNewPolicyVersionStr(e.target.value)}
                    placeholder="1.0"
                  />
                </div>
                <div>
                  <label htmlFor="pol-cycle">Review Cycle (Days)</label>
                  <input
                    id="pol-cycle"
                    type="number"
                    value={newPolicyCycleDays}
                    onChange={(e) => setNewPolicyCycleDays(Number(e.target.value))}
                  />
                </div>
              </div>

              <label htmlFor="pol-class">Classification</label>
              <select
                id="pol-class"
                value={newPolicyClass}
                onChange={(e) => setNewPolicyClass(e.target.value as DataClassification)}
              >
                <option value="Public">Public</option>
                <option value="Internal">Internal</option>
                <option value="Confidential">Confidential</option>
                <option value="Restricted">Restricted</option>
              </select>

              <label htmlFor="pol-content">Policy Content</label>
              <textarea
                id="pol-content"
                rows={4}
                value={newPolicyContent}
                onChange={(e) => setNewPolicyContent(e.target.value)}
                placeholder="Full markdown policy text"
              />

              <label htmlFor="pol-rest">Restricted Content (AES-256-GCM Envelope Encrypted)</label>
              <textarea
                id="pol-rest"
                rows={2}
                value={newPolicyRestrictedContent}
                onChange={(e) => setNewPolicyRestrictedContent(e.target.value)}
                placeholder="Highly confidential policy appendices or operational specifics"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowCreatePolicy(false)}
                >
                  Cancel
                </button>
                <button type="submit">Create Policy</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: POLICY CONTROL LINKS */}
      {selectedPolicyForDetail && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <h3 style={{ margin: 0 }}>Policy Controls: {selectedPolicyForDetail.title}</h3>
                <p style={{ margin: "0.25rem 0", color: "#6b7280", fontSize: "0.875rem" }}>
                  Version: v{selectedPolicyForDetail.version_string}
                </p>
              </div>
              <button
                className="secondary"
                style={{ padding: "0.25rem 0.5rem", minHeight: "auto" }}
                onClick={() => setSelectedPolicyForDetail(null)}
              >
                Close
              </button>
            </div>

            <div style={{ marginTop: "1rem" }}>
              <h4>Linked Controls ({(selectedPolicyForDetail.control_links ?? []).length})</h4>
              {(selectedPolicyForDetail.control_links ?? []).length === 0 ? (
                <p style={{ fontSize: "0.85rem", color: "#6b7280" }}>No controls linked to this policy.</p>
              ) : (
                <ul style={{ fontSize: "0.85rem", paddingLeft: "1.25rem" }}>
                  {(selectedPolicyForDetail.control_links ?? []).map((c) => {
                    const matched = unifiedControls.find(
                      (u) => u.type === c.control_type && u.id === c.control_id
                    );
                    return (
                      <li key={c.id} style={{ marginBottom: "0.25rem" }}>
                        <strong>{matched ? matched.identifier : c.control_id}</strong>:{" "}
                        {matched ? matched.title : c.control_type}{" "}
                        <button
                          className="secondary"
                          style={{ padding: "0.1rem 0.4rem", fontSize: "0.7rem", minHeight: "auto", color: "#dc2626" }}
                          onClick={() => void handleUnlinkControlFromPolicy(c.control_type, c.control_id)}
                        >
                          Unlink
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", flexWrap: "wrap" }}>
                <select
                  value={policyLinkControlType}
                  onChange={(e) => setPolicyLinkControlType(e.target.value as ControlEntityType)}
                  style={{ width: "auto" }}
                >
                  <option value="canonical">Canonical</option>
                  <option value="custom">Custom</option>
                </select>
                <select
                  value={policyLinkControlId}
                  onChange={(e) => setPolicyLinkControlId(e.target.value)}
                  style={{ width: "16rem" }}
                >
                  <option value="">Select a control...</option>
                  {unifiedControls
                    .filter((u) => u.type === policyLinkControlType)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.identifier} — {u.title}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => void handleLinkControlToPolicy()}
                >
                  Link
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: CREATE TASK */}
      {showCreateTask && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Create Compliance Task</h3>
            <form onSubmit={(e) => void handleCreateTask(e)}>
              <label htmlFor="tsk-title">Title *</label>
              <input
                id="tsk-title"
                type="text"
                required
                value={newTaskTitle}
                onChange={(e) => setNewTaskTitle(e.target.value)}
                placeholder="e.g. Conduct annual access control review"
              />

              <label htmlFor="tsk-desc">Description *</label>
              <textarea
                id="tsk-desc"
                rows={3}
                required
                value={newTaskDesc}
                onChange={(e) => setNewTaskDesc(e.target.value)}
                placeholder="Actionable steps and required evidence deliverable"
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label htmlFor="tsk-due">Due Date *</label>
                  <input
                    id="tsk-due"
                    type="date"
                    required
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="tsk-prio">Priority</label>
                  <select
                    id="tsk-prio"
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as TaskPriority)}
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <label htmlFor="tsk-assignee">Assignee User ID</label>
              <input
                id="tsk-assignee"
                type="text"
                value={newTaskAssignee}
                onChange={(e) => setNewTaskAssignee(e.target.value)}
                placeholder="Assignee UUID or email"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowCreateTask(false)}
                >
                  Cancel
                </button>
                <button type="submit">Create Task</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: CREATE FINDING */}
      {showCreateFinding && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Report Compliance Finding</h3>
            <form onSubmit={(e) => void handleCreateFinding(e)}>
              <label htmlFor="fnd-title">Finding Title *</label>
              <input
                id="fnd-title"
                type="text"
                required
                value={newFindingTitle}
                onChange={(e) => setNewFindingTitle(e.target.value)}
                placeholder="e.g. Unrestricted SSH port 22 open on bastion"
              />

              <label htmlFor="fnd-desc">Finding Description *</label>
              <textarea
                id="fnd-desc"
                rows={3}
                required
                value={newFindingDesc}
                onChange={(e) => setNewFindingDesc(e.target.value)}
                placeholder="Root cause, risk analysis, and observed deviation"
              />

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <label htmlFor="fnd-sev">Severity</label>
                  <select
                    id="fnd-sev"
                    value={newFindingSeverity}
                    onChange={(e) => setNewFindingSeverity(e.target.value as FindingSeverity)}
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="fnd-due">Remediation Due Date</label>
                  <input
                    id="fnd-due"
                    type="date"
                    value={newFindingDueDate}
                    onChange={(e) => setNewFindingDueDate(e.target.value)}
                  />
                </div>
              </div>

              <label htmlFor="fnd-plan">Initial Remediation Plan</label>
              <textarea
                id="fnd-plan"
                rows={2}
                value={newFindingPlan}
                onChange={(e) => setNewFindingPlan(e.target.value)}
                placeholder="Proposed corrective actions and validation timeline"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setShowCreateFinding(false)}
                >
                  Cancel
                </button>
                <button type="submit">Report Finding</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: REMEDIATE FINDING */}
      {selectedFindingForRemediation && (
        <div className="modal-backdrop">
          <div className="modal-dialog">
            <h3>Remediate Finding: {selectedFindingForRemediation.title}</h3>
            <form onSubmit={(e) => void handleRemediateFinding(e)}>
              <label htmlFor="rem-status">Remediation Status</label>
              <select
                id="rem-status"
                value={remediationStatusInput}
                onChange={(e) => setRemediationStatusInput(e.target.value as RemediationStatus)}
              >
                <option value="open">Open</option>
                <option value="in_remediation">In Remediation</option>
                <option value="resolved">Resolved</option>
                <option value="accepted_risk">Accepted Risk</option>
              </select>

              <label htmlFor="rem-summary">Remediation Summary & Evidence</label>
              <textarea
                id="rem-summary"
                rows={4}
                required
                value={remediationSummaryInput}
                onChange={(e) => setRemediationSummaryInput(e.target.value)}
                placeholder="Explain the corrective action taken, verified configurations, and test results"
              />

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem", marginTop: "1.5rem" }}>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setSelectedFindingForRemediation(null)}
                >
                  Cancel
                </button>
                <button type="submit">Update Remediation</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
