import {
  AssessmentFinding,
  AssessmentWorkItem,
  FindingSeverity,
  FindingStatus,
} from "./assessment-types";
import {
  ControlEvidenceLink,
  ControlWorkItem,
} from "./control-evidence-types";

export type WorkQueueItemKind = "control" | "finding";

export type WorkQueueBucket =
  | "all"
  | "overdue"
  | "due_today"
  | "unassigned"
  | "evidence_attention"
  | "assessment_needed"
  | "open_findings";

export interface WorkQueueItem {
  id: string; // e.g. "ctrl-<id>" or "fnd-<id>"
  kind: WorkQueueItemKind;
  workId: string;
  controlId: string;
  controlTitle: string;
  findingId?: string;
  findingSeverity?: FindingSeverity;
  findingStatus?: FindingStatus;
  ownerUserId: string | null;
  ownerDisplayName: string | null;
  dueDate: string | null; // Normalized YYYY-MM-DD UTC or null
  rawDueDate: string | null;
  isStale: boolean;
  status: string;
  evidenceAttention: boolean;
  assessmentNeeded: boolean;
  isOverdue: boolean;
  isDueToday: boolean;
  isUnassigned: boolean;
  rawControl: ControlWorkItem;
  rawAssessment?: AssessmentWorkItem;
  rawFinding?: AssessmentFinding;
}

export interface WorkQueueFilters {
  owner?: string; // "all", "unassigned", or specific userId
  bucket?: WorkQueueBucket;
  status?: string; // "all" or specific status
  search?: string;
}

export interface WorkQueueBucketCounts {
  totalItems: number;
  distinctControls: number;
  overdue: number;
  dueToday: number;
  unassigned: number;
  evidenceAttention: number;
  assessmentNeeded: number | null;
  openFindings: number | null;
  isAssessmentAvailable: boolean;
  isControlsAvailable: boolean;
  isComplete: boolean;
}

/**
 * Normalizes an arbitrary due_date string to YYYY-MM-DD UTC, or returns null if invalid.
 */
export function normalizeUtcDate(dateStr: string | null | undefined): string | null {
  if (!dateStr || typeof dateStr !== "string") return null;
  const trimmed = dateStr.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
    const d = new Date(trimmed + "T00:00:00Z");
    if (!isNaN(d.getTime())) return trimmed;
  }
  const parsed = new Date(trimmed);
  if (isNaN(parsed.getTime())) return null;
  return parsed.toISOString().slice(0, 10);
}

/**
 * Evaluates whether a control requires evidence attention.
 * Attention needed if 0 links, or any link has non-ideal validity, pending/rejected review, or unverified scan.
 */
export function checkEvidenceAttention(links: ControlEvidenceLink[]): boolean {
  if (!links || links.length === 0) return true;
  return links.some((l) => {
    const invalidValidity =
      l.validity === "MISSING" ||
      l.validity === "NOT_YET_VALID" ||
      l.validity === "EXPIRED" ||
      l.validity === "QUARANTINED" ||
      l.validity === "UNAVAILABLE" ||
      l.validity === "UNVERIFIED";
    const pendingOrRejectedReview = l.review === "PENDING" || l.review === "REJECTED";
    const unverifiedScan = l.scan_status === "UNVERIFIED";
    return invalidValidity || pendingOrRejectedReview || unverifiedScan;
  });
}

/**
 * Evaluates whether a control requires assessment attention.
 * Assessment needed if no assessment item, no latest_assessment, primary_state is not assessed, or latest assessment is stale.
 */
export function checkAssessmentNeeded(assessment?: AssessmentWorkItem): boolean {
  if (!assessment) return true;
  if (!assessment.latest_assessment) return true;
  if (assessment.primary_state === "UNASSESSED") return true;
  if (assessment.latest_assessment.is_stale) return true;
  return false;
}

const SEVERITY_WEIGHT: Record<FindingSeverity, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

/**
 * Pure selector that combines controls and assessments into a flat, typed list of queue items.
 */
export function buildWorkQueueItems(
  controls: ControlWorkItem[],
  assessments?: AssessmentWorkItem[],
  asOfDateStr?: string
): WorkQueueItem[] {
  const asOfUtc = asOfDateStr || new Date().toISOString().slice(0, 10);
  const assessmentByWorkId = new Map<string, AssessmentWorkItem>();
  if (assessments && Array.isArray(assessments)) {
    for (const a of assessments) {
      if (a && a.work_id) {
        assessmentByWorkId.set(a.work_id, a);
      }
    }
  }

  const items: WorkQueueItem[] = [];

  for (const ctrl of controls) {
    if (!ctrl || !ctrl.id) continue;
    const aItem = assessmentByWorkId.get(ctrl.id);

    // Version pin compatibility check:
    // If assessment item exists, does its control_version_id match ctrl.control_version_id?
    const isControlVersionMismatch = Boolean(
      aItem &&
      aItem.control_version_id &&
      ctrl.control_version_id &&
      aItem.control_version_id !== ctrl.control_version_id
    );

    const normDueDate = normalizeUtcDate(ctrl.due_date);
    const isUnassigned = !ctrl.owner_user_id || ctrl.owner_user_id.trim() === "";
    const isOverdue = Boolean(normDueDate && normDueDate < asOfUtc);
    const isDueToday = Boolean(normDueDate && normDueDate === asOfUtc);
    const evidenceAttention = checkEvidenceAttention(ctrl.links || []);
    const assessmentNeeded = isControlVersionMismatch ? true : checkAssessmentNeeded(aItem);
    const isItemStale = Boolean(
      ctrl.is_stale ||
      isControlVersionMismatch ||
      (aItem && (aItem.latest_assessment?.is_stale || aItem.primary_state === "STALE_WORK"))
    );
    const statusText = isControlVersionMismatch
      ? "STALE (Version Pin Changed)"
      : (ctrl.is_stale || (aItem && (aItem.latest_assessment?.is_stale || aItem.primary_state === "STALE_WORK")))
      ? (aItem?.latest_assessment?.result ? `STALE (${aItem.latest_assessment.result})` : "STALE")
      : (aItem?.latest_assessment?.result || "INITIALIZED");

    // 1. Primary Control Row
    items.push({
      id: `ctrl-${ctrl.id}`,
      kind: "control",
      workId: ctrl.id,
      controlId: ctrl.control_id,
      controlTitle: ctrl.title,
      ownerUserId: ctrl.owner_user_id,
      ownerDisplayName: ctrl.owner_display_name,
      dueDate: normDueDate,
      rawDueDate: ctrl.due_date,
      isStale: isItemStale,
      status: statusText,
      evidenceAttention,
      assessmentNeeded,
      isOverdue,
      isDueToday,
      isUnassigned,
      rawControl: ctrl,
      rawAssessment: isControlVersionMismatch ? undefined : aItem,
    });

    // 2. Individual Open / In-Remediation Finding Rows
    // Incompatible control version pin findings must NOT be joined to this control
    if (aItem && !isControlVersionMismatch && Array.isArray(aItem.findings)) {
      for (const f of aItem.findings) {
        if (!f || f.status === "RESOLVED") continue; // Resolved findings are not active queue items
        const fDueDate = normalizeUtcDate(f.due_date);
        const fUnassigned = !f.owner_user_id || f.owner_user_id.trim() === "";
        const fOverdue = Boolean(fDueDate && fDueDate < asOfUtc);
        const fDueToday = Boolean(fDueDate && fDueDate === asOfUtc);

        items.push({
          id: `fnd-${f.id}`,
          kind: "finding",
          workId: ctrl.id,
          controlId: ctrl.control_id,
          controlTitle: `${ctrl.title} (Finding: ${f.severity})`,
          findingId: f.id,
          findingSeverity: f.severity,
          findingStatus: f.status,
          ownerUserId: f.owner_user_id || ctrl.owner_user_id,
          ownerDisplayName: f.owner_display_name || ctrl.owner_display_name,
          dueDate: fDueDate || normDueDate,
          rawDueDate: f.due_date || ctrl.due_date,
          isStale: isItemStale,
          status: f.status,
          evidenceAttention: false,
          assessmentNeeded: false,
          isOverdue: fOverdue,
          isDueToday: fDueToday,
          isUnassigned: fUnassigned,
          rawControl: ctrl,
          rawAssessment: aItem,
          rawFinding: f,
        });
      }
    }
  }

  return items;
}

/**
 * Pure function to calculate bucket counts.
 */
export function getWorkQueueBucketCounts(
  items: WorkQueueItem[],
  controlsCount: number,
  isAssessmentAvailable = true,
  isControlsAvailable = true
): WorkQueueBucketCounts {
  let overdue = 0;
  let dueToday = 0;
  let unassigned = 0;
  let evidenceAttention = 0;
  let assessmentNeeded = 0;
  let openFindings = 0;

  for (const item of items) {
    if (item.isOverdue) overdue++;
    if (item.isDueToday) dueToday++;
    if (item.isUnassigned) unassigned++;
    if (item.evidenceAttention) evidenceAttention++;
    if (item.assessmentNeeded) assessmentNeeded++;
    if (item.kind === "finding" && (item.findingStatus === "OPEN" || item.findingStatus === "IN_REMEDIATION")) {
      openFindings++;
    }
  }

  return {
    totalItems: isControlsAvailable ? items.length : 0,
    distinctControls: isControlsAvailable ? controlsCount : 0,
    overdue: isControlsAvailable ? overdue : 0,
    dueToday: isControlsAvailable ? dueToday : 0,
    unassigned: isControlsAvailable ? unassigned : 0,
    evidenceAttention: isControlsAvailable ? evidenceAttention : 0,
    assessmentNeeded: isAssessmentAvailable ? assessmentNeeded : null,
    openFindings: isAssessmentAvailable ? openFindings : null,
    isAssessmentAvailable,
    isControlsAvailable,
    isComplete: isAssessmentAvailable && isControlsAvailable,
  };
}

/**
 * Filters and deterministically sorts queue items.
 * Ordering:
 * 1. Overdue first (ascending due date YYYY-MM-DD)
 * 2. Due today next
 * 3. Future due dates (ascending)
 * 4. Missing/null due dates last
 * Tie breaker:
 * 5. Finding severity (CRITICAL > HIGH > MEDIUM > LOW > Control)
 * 6. Stable ID alphabetical
 */
export function filterAndSortWorkQueue(
  items: WorkQueueItem[],
  filters: WorkQueueFilters,
  asOfDateStr?: string
): WorkQueueItem[] {
  void asOfDateStr;

  // 1. Filter
  const filtered = items.filter((item) => {
    // Owner filter
    if (filters.owner && filters.owner !== "all") {
      if (filters.owner === "unassigned") {
        if (!item.isUnassigned) return false;
      } else if (item.ownerUserId !== filters.owner) {
        return false;
      }
    }

    // Bucket filter
    if (filters.bucket && filters.bucket !== "all") {
      switch (filters.bucket) {
        case "overdue":
          if (!item.isOverdue) return false;
          break;
        case "due_today":
          if (!item.isDueToday) return false;
          break;
        case "unassigned":
          if (!item.isUnassigned) return false;
          break;
        case "evidence_attention":
          if (!item.evidenceAttention) return false;
          break;
        case "assessment_needed":
          if (!item.assessmentNeeded) return false;
          break;
        case "open_findings":
          if (item.kind !== "finding") return false;
          break;
      }
    }

    // Status filter
    if (filters.status && filters.status !== "all") {
      if (item.status.toUpperCase() !== filters.status.toUpperCase()) {
        return false;
      }
    }

    // Search filter
    if (filters.search && filters.search.trim()) {
      const q = filters.search.trim().toLowerCase();
      const matchTitle = item.controlTitle.toLowerCase().includes(q);
      const matchControlId = item.controlId.toLowerCase().includes(q);
      const matchOwner = Boolean(item.ownerDisplayName && item.ownerDisplayName.toLowerCase().includes(q));
      const matchSeverity = Boolean(item.findingSeverity && item.findingSeverity.toLowerCase().includes(q));
      const matchStatus = item.status.toLowerCase().includes(q);
      if (!matchTitle && !matchControlId && !matchOwner && !matchSeverity && !matchStatus) {
        return false;
      }
    }

    return true;
  });

  // 2. Sort
  return filtered.sort((a, b) => {
    // Overdue priority: both overdue -> compare dates ascending
    if (a.isOverdue && !b.isOverdue) return -1;
    if (!a.isOverdue && b.isOverdue) return 1;

    // Due today priority
    if (a.isDueToday && !b.isDueToday && !a.isOverdue && !b.isOverdue) return -1;
    if (!a.isDueToday && b.isDueToday && !a.isOverdue && !b.isOverdue) return 1;

    // Both have due dates: compare ascending
    if (a.dueDate && b.dueDate) {
      if (a.dueDate !== b.dueDate) {
        return a.dueDate.localeCompare(b.dueDate);
      }
    } else if (a.dueDate && !b.dueDate) {
      return -1; // Dates before null
    } else if (!a.dueDate && b.dueDate) {
      return 1;
    }

    // Tie breaker: Finding severity weight
    const aWeight = a.findingSeverity ? SEVERITY_WEIGHT[a.findingSeverity] || 0 : 0;
    const bWeight = b.findingSeverity ? SEVERITY_WEIGHT[b.findingSeverity] || 0 : 0;
    if (aWeight !== bWeight) {
      return bWeight - aWeight; // Higher severity first
    }

    // Tie breaker: Kind (finding before control when tied on same work)
    if (a.kind !== b.kind) {
      return a.kind === "finding" ? -1 : 1;
    }

    // Stable tie breaker: ID
    return a.id.localeCompare(b.id);
  });
}

