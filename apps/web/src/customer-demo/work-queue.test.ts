import { describe, expect, it } from "vitest";
import { AssessmentWorkItem } from "./assessment-types";
import { ControlWorkItem } from "./control-evidence-types";
import {
  buildWorkQueueItems,
  checkAssessmentNeeded,
  checkEvidenceAttention,
  filterAndSortWorkQueue,
  getWorkQueueBucketCounts,
  normalizeUtcDate,
} from "./work-queue";

const mockControls: ControlWorkItem[] = [
  {
    id: "work-1",
    adoption_id: "adopt-1",
    control_id: "CTRL-01",
    control_version_id: "cv-1",
    title: "Access Control Policy",
    provenance: "synthetic_nist",
    pack_version: 1,
    bundle_digest: "digest-1",
    requirement_results: [],
    owner_user_id: "usr-alice",
    owner_display_name: "Alice Security",
    due_date: "2026-10-25", // Overdue relative to 2026-10-29
    version: 1,
    is_current: true,
    is_stale: false,
    links: [
      {
        id: "link-1",
        evidence_id: "ev-1",
        revision_number: 1,
        digest: "sha256:111",
        file_ids: ["f-1"],
        filename: "policy.pdf",
        file_size: 1024,
        classification: "RESTRICTED",
        validity: "AVAILABLE",
        scan_status: "SCANNED_AT_LINK",
        scan_verified_at: "2026-10-20T00:00:00Z",
        review: "ACCEPTED",
        rationale: "Approved",
        created_at: "2026-10-20T00:00:00Z",
      },
    ],
  },
  {
    id: "work-2",
    adoption_id: "adopt-1",
    control_id: "CTRL-02",
    control_version_id: "cv-2",
    title: "Encryption at Rest",
    provenance: "synthetic_nist",
    pack_version: 1,
    bundle_digest: "digest-1",
    requirement_results: [],
    owner_user_id: null, // Unassigned
    owner_display_name: null,
    due_date: "2026-10-29", // Due today relative to 2026-10-29
    version: 1,
    is_current: true,
    is_stale: false,
    links: [], // Evidence attention needed (0 links)
  },
  {
    id: "work-3",
    adoption_id: "adopt-1",
    control_id: "CTRL-03",
    control_version_id: "cv-3",
    title: "Incident Response Plan",
    provenance: "synthetic_nist",
    pack_version: 1,
    bundle_digest: "digest-1",
    requirement_results: [],
    owner_user_id: "usr-bob",
    owner_display_name: "Bob Ops",
    due_date: "2026-11-05", // Future
    version: 1,
    is_current: true,
    is_stale: true, // Stale work
    links: [
      {
        id: "link-2",
        evidence_id: "ev-2",
        revision_number: 1,
        digest: "sha256:222",
        file_ids: ["f-2"],
        filename: "ir-plan.pdf",
        file_size: 2048,
        classification: "INTERNAL",
        validity: "EXPIRED", // Evidence attention needed
        scan_status: "UNVERIFIED",
        scan_verified_at: null,
        review: "PENDING",
        rationale: "Needs review",
        created_at: "2026-10-15T00:00:00Z",
      },
    ],
  },
];

const mockAssessments: AssessmentWorkItem[] = [
  {
    work_id: "work-1",
    control_version_id: "cv-1",
    work_version: 1,
    assessment_revision: 1,
    procedure: {
      id: "proc-1",
      version: "1.0",
      digest: "proc-dig-1",
      criteria: [],
      disclaimer: "Synthetic procedure",
    },
    latest_assessment: {
      event_id: "evt-1",
      revision: 1,
      result: "PASS",
      actor_id: "usr-auditor",
      created_at: "2026-10-22T00:00:00Z",
      rationale: "Meets criteria",
      criterion_results: [],
      evidence_pins: [],
      is_stale: false,
      stale_reasons: [],
    },
    primary_state: "PASS",
    blockers: [],
    findings: [],
    history: [],
  },
  {
    work_id: "work-2",
    control_version_id: "cv-2",
    work_version: 1,
    assessment_revision: 0,
    procedure: {
      id: "proc-2",
      version: "1.0",
      digest: "proc-dig-2",
      criteria: [],
      disclaimer: "Synthetic procedure",
    },
    latest_assessment: null, // Assessment needed
    primary_state: "UNASSESSED",
    blockers: ["NO_EVIDENCE"],
    findings: [
      {
        id: "fnd-101",
        source_event_id: "evt-10",
        current_event_id: "evt-10",
        severity: "HIGH",
        status: "OPEN",
        owner_user_id: "usr-alice",
        owner_display_name: "Alice Security",
        due_date: "2026-10-28", // Overdue finding
        version: 1,
        created_at: "2026-10-21T00:00:00Z",
        updated_at: "2026-10-21T00:00:00Z",
      },
    ],
    history: [],
  },
];

describe("work-queue pure selector utilities", () => {
  const asOf = "2026-10-29";

  it("normalizes ISO and YYYY-MM-DD dates to UTC YYYY-MM-DD cleanly and rejects invalid", () => {
    expect(normalizeUtcDate("2026-10-25")).toBe("2026-10-25");
    expect(normalizeUtcDate("2026-10-25T14:30:00Z")).toBe("2026-10-25");
    expect(normalizeUtcDate("   2026-10-25   ")).toBe("2026-10-25");
    expect(normalizeUtcDate("not-a-date")).toBeNull();
    expect(normalizeUtcDate("")).toBeNull();
    expect(normalizeUtcDate(null)).toBeNull();
    expect(normalizeUtcDate(undefined)).toBeNull();
  });

  it("correctly identifies evidence attention requirements", () => {
    // 0 links -> attention needed
    expect(checkEvidenceAttention([])).toBe(true);

    // Valid link -> no attention needed
    expect(
      checkEvidenceAttention([
        {
          id: "l-1",
          evidence_id: "e-1",
          revision_number: 1,
          digest: "d-1",
          file_ids: ["f-1"],
          filename: "f.pdf",
          file_size: 100,
          classification: "INTERNAL",
          validity: "AVAILABLE",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: "2026-10-01",
          review: "ACCEPTED",
          rationale: "ok",
          created_at: "2026-10-01",
        },
      ])
    ).toBe(false);

    // Pending review -> attention needed
    expect(
      checkEvidenceAttention([
        {
          id: "l-1",
          evidence_id: "e-1",
          revision_number: 1,
          digest: "d-1",
          file_ids: ["f-1"],
          filename: "f.pdf",
          file_size: 100,
          classification: "INTERNAL",
          validity: "AVAILABLE",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: "2026-10-01",
          review: "PENDING",
          rationale: "pending",
          created_at: "2026-10-01",
        },
      ])
    ).toBe(true);

    // Expired or Quarantined -> attention needed
    expect(
      checkEvidenceAttention([
        {
          id: "l-1",
          evidence_id: "e-1",
          revision_number: 1,
          digest: "d-1",
          file_ids: ["f-1"],
          filename: "f.pdf",
          file_size: 100,
          classification: "INTERNAL",
          validity: "QUARANTINED",
          scan_status: "SCANNED_AT_LINK",
          scan_verified_at: "2026-10-01",
          review: "ACCEPTED",
          rationale: "quarantine",
          created_at: "2026-10-01",
        },
      ])
    ).toBe(true);
  });

  it("correctly identifies assessment needed state", () => {
    expect(checkAssessmentNeeded(undefined)).toBe(true);
    expect(checkAssessmentNeeded(mockAssessments[1])).toBe(true); // latest_assessment: null
    expect(checkAssessmentNeeded(mockAssessments[0])).toBe(false); // PASS, not stale
  });

  it("builds flat work queue items with explicit different kinds for controls and findings", () => {
    const items = buildWorkQueueItems(mockControls, mockAssessments, asOf);

    // 3 controls + 1 open finding = 4 items
    expect(items).toHaveLength(4);

    const controlItems = items.filter((i) => i.kind === "control");
    const findingItems = items.filter((i) => i.kind === "finding");

    expect(controlItems).toHaveLength(3);
    expect(findingItems).toHaveLength(1);

    // Finding row has finding fields
    const fItem = findingItems[0];
    expect(fItem.findingId).toBe("fnd-101");
    expect(fItem.findingSeverity).toBe("HIGH");
    expect(fItem.findingStatus).toBe("OPEN");
    expect(fItem.isOverdue).toBe(true); // Due 2026-10-28 < asOf 2026-10-29
  });

  it("calculates honest bucket counts without double-counting controls", () => {
    const items = buildWorkQueueItems(mockControls, mockAssessments, asOf);
    const counts = getWorkQueueBucketCounts(items, mockControls.length);

    expect(counts.totalItems).toBe(4);
    expect(counts.distinctControls).toBe(3);
    expect(counts.overdue).toBe(2); // work-1 (due 10-25) and fnd-101 (due 10-28)
    expect(counts.dueToday).toBe(1); // work-2 (due 10-29)
    expect(counts.unassigned).toBe(1); // work-2
    expect(counts.evidenceAttention).toBe(2); // work-2 (0 links) and work-3 (expired link)
    expect(counts.assessmentNeeded).toBe(2); // work-2 and work-3 (no assessment)
    expect(counts.openFindings).toBe(1); // fnd-101
  });

  it("sorts deterministically: overdue first, then due today, then future, then missing dates, with stable tie-breakers", () => {
    const items = buildWorkQueueItems(mockControls, mockAssessments, asOf);
    const sorted = filterAndSortWorkQueue(items, {}, asOf);

    // Overdue items should be first: work-1 (2026-10-25), fnd-101 (2026-10-28)
    expect(sorted[0].id).toBe("ctrl-work-1");
    expect(sorted[1].id).toBe("fnd-fnd-101");

    // Due today: work-2 (2026-10-29)
    expect(sorted[2].id).toBe("ctrl-work-2");

    // Future due: work-3 (2026-11-05)
    expect(sorted[3].id).toBe("ctrl-work-3");
  });

  it("filters accurately by owner, bucket, status and text search", () => {
    const items = buildWorkQueueItems(mockControls, mockAssessments, asOf);

    // Owner filter: Alice
    const aliceItems = filterAndSortWorkQueue(items, { owner: "usr-alice" }, asOf);
    expect(aliceItems.map((i) => i.id)).toEqual(["ctrl-work-1", "fnd-fnd-101"]);

    // Owner filter: Unassigned
    const unassignedItems = filterAndSortWorkQueue(items, { owner: "unassigned" }, asOf);
    expect(unassignedItems.map((i) => i.id)).toEqual(["ctrl-work-2"]);

    // Bucket filter: overdue
    const overdueItems = filterAndSortWorkQueue(items, { bucket: "overdue" }, asOf);
    expect(overdueItems.map((i) => i.id)).toEqual(["ctrl-work-1", "fnd-fnd-101"]);

    // Bucket filter: open_findings
    const findingItems = filterAndSortWorkQueue(items, { bucket: "open_findings" }, asOf);
    expect(findingItems).toHaveLength(1);
    expect(findingItems[0].id).toBe("fnd-fnd-101");

    // Search filter: "encryption"
    const searchItems = filterAndSortWorkQueue(items, { search: "encryption" }, asOf);
    // fnd-fnd-101 is overdue (2026-10-28), so it sorts before ctrl-work-2 (due today 2026-10-29)
    expect(searchItems.map((i) => i.id)).toEqual(["fnd-fnd-101", "ctrl-work-2"]);

    // Empty filter returns empty list cleanly
    const emptySearch = filterAndSortWorkQueue(items, { search: "nonexistent-query" }, asOf);
    expect(emptySearch).toHaveLength(0);
  });

  it("handles control version pin mismatch by flagging stale and excluding incompatible findings", () => {
    const mismatchedAssessments = [
      {
        ...mockAssessments[0],
        control_version_id: "cv-outdated-version", // Does not match mockControls[0].control_version_id ("cv-1")
      },
    ];

    const items = buildWorkQueueItems([mockControls[0]], mismatchedAssessments, asOf);

    // Control row should be marked stale with version pin notice
    expect(items).toHaveLength(1); // Only the control row; findings from cv-outdated-version must NOT be joined
    expect(items[0].id).toBe("ctrl-work-1");
    expect(items[0].isStale).toBe(true);
    expect(items[0].assessmentNeeded).toBe(true);
    expect(items[0].status).toBe("STALE (Version Pin Changed)");
    expect(items[0].rawAssessment).toBeUndefined();
  });
});

